"""Transient Bus — fast-path energy extraction for audio-reactive visualizers.

Dual-path architecture component (Approach A from Visualizer_Modes_Audit.md):
Receives raw FFT magnitudes each frame (post-noise-floor, pre-AGC) and produces
per-band transient energy values with 1-frame latency.  The smoothed/AGC path
continues unchanged alongside this bus.

Algorithm:
  1. Spectral flux: current_magnitude - previous_magnitude, half-wave rectified.
  2. Per-band (bass/mid/high) flux accumulation.
  3. Adaptive threshold: running_mean + k * sqrt(running_variance) per band.
  4. Onset detection: when flux exceeds threshold, emit a typed onset event
     into a ring buffer for downstream consumption.

Threading model:
  Single writer (COMPUTE pool via bar_computation), single reader (UI tick via
  beat_engine).  All public read methods return snapshots; no locks needed
  because CPython's GIL guarantees atomic float/reference assignment.

No external dependencies beyond numpy (already required by audio_worker).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import List

from core.logging.logger import get_logger, is_viz_diagnostics_enabled

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TransientEnergyBands:
    """Per-band transient energy snapshot (all values 0..1+)."""
    bass_transient: float = 0.0
    mid_transient: float = 0.0
    high_transient: float = 0.0
    onset_detected: bool = False
    onset_type: str = ""        # "kick", "snare", "vocal_swell", or ""
    onset_strength: float = 0.0  # 0..1 normalised onset magnitude


@dataclass(slots=True)
class OnsetEvent:
    """Timestamped onset event stored in the ring buffer."""
    timestamp: float = 0.0
    event_type: str = ""   # "kick", "snare", "vocal_swell"
    strength: float = 0.0  # 0..1


# ---------------------------------------------------------------------------
# Transient Bus
# ---------------------------------------------------------------------------

class TransientBus:
    """Fast-path transient energy extractor.

    Call ``update()`` once per FFT frame from the COMPUTE pool.
    Read ``snapshot()`` from the UI thread to get the latest transient state.
    """

    # Ring buffer capacity for onset events
    _RING_CAPACITY: int = 8

    def __init__(
        self,
        *,
        threshold_k: float = 1.5,
        mean_alpha: float = 0.08,
        var_alpha: float = 0.05,
        transient_decay: float = 0.55,
        min_onset_gap_s: float = 0.045,
    ) -> None:
        # Adaptive threshold tuning
        self._threshold_k = max(0.5, min(4.0, threshold_k))
        self._mean_alpha = max(0.01, min(0.3, mean_alpha))
        self._var_alpha = max(0.01, min(0.3, var_alpha))
        self._transient_decay = max(0.1, min(0.95, transient_decay))
        self._min_onset_gap_s = max(0.0, min(0.5, min_onset_gap_s))

        # Per-band running statistics (mean, variance of spectral flux)
        self._bass_flux_mean: float = 0.0
        self._bass_flux_var: float = 0.01
        self._mid_flux_mean: float = 0.0
        self._mid_flux_var: float = 0.01
        self._high_flux_mean: float = 0.0
        self._high_flux_var: float = 0.01

        # Previous frame energy for spectral flux computation
        self._prev_bass: float = 0.0
        self._prev_mid: float = 0.0
        self._prev_high: float = 0.0
        self._has_prev: bool = False

        # Current transient output (written by update, read by snapshot)
        self._bass_transient: float = 0.0
        self._mid_transient: float = 0.0
        self._high_transient: float = 0.0
        self._onset_detected: bool = False
        self._onset_type: str = ""
        self._onset_strength: float = 0.0

        # Onset ring buffer
        self._onset_ring: List[OnsetEvent] = [
            OnsetEvent() for _ in range(self._RING_CAPACITY)
        ]
        self._onset_ring_head: int = 0

        # Timing
        self._last_onset_ts: float = 0.0
        self._last_update_ts: float = 0.0
        self._frame_count: int = 0

        # Event micro-scheduler (§2.4) — created lazily on first access
        self._scheduler: "TransientEventScheduler | None" = None

    # ------------------------------------------------------------------
    # Public API — called from COMPUTE pool (single writer)
    # ------------------------------------------------------------------

    def update(
        self,
        bass_energy: float,
        mid_energy: float,
        high_energy: float,
    ) -> TransientEnergyBands:
        """Process one FFT frame and return transient energy snapshot.

        Parameters are post-noise-floor, pre-AGC band energies (0..1 range).
        """
        now = time.time()
        self._last_update_ts = now
        self._frame_count += 1

        if not self._has_prev:
            # First frame — seed previous values, no flux yet
            self._prev_bass = bass_energy
            self._prev_mid = mid_energy
            self._prev_high = high_energy
            self._has_prev = True
            return self.snapshot()

        # --- Spectral flux: half-wave rectified difference ---
        bass_flux = max(0.0, bass_energy - self._prev_bass)
        mid_flux = max(0.0, mid_energy - self._prev_mid)
        high_flux = max(0.0, high_energy - self._prev_high)

        self._prev_bass = bass_energy
        self._prev_mid = mid_energy
        self._prev_high = high_energy

        # --- Update running statistics per band ---
        alpha_m = self._mean_alpha
        alpha_v = self._var_alpha

        self._bass_flux_mean += (bass_flux - self._bass_flux_mean) * alpha_m
        self._mid_flux_mean += (mid_flux - self._mid_flux_mean) * alpha_m
        self._high_flux_mean += (high_flux - self._high_flux_mean) * alpha_m

        bass_diff = bass_flux - self._bass_flux_mean
        mid_diff = mid_flux - self._mid_flux_mean
        high_diff = high_flux - self._high_flux_mean

        self._bass_flux_var += (bass_diff * bass_diff - self._bass_flux_var) * alpha_v
        self._mid_flux_var += (mid_diff * mid_diff - self._mid_flux_var) * alpha_v
        self._high_flux_var += (high_diff * high_diff - self._high_flux_var) * alpha_v

        # Ensure variance stays positive
        self._bass_flux_var = max(1e-6, self._bass_flux_var)
        self._mid_flux_var = max(1e-6, self._mid_flux_var)
        self._high_flux_var = max(1e-6, self._high_flux_var)

        # --- Adaptive thresholds: mean + k * sqrt(variance) ---
        k = self._threshold_k
        bass_thresh = self._bass_flux_mean + k * (self._bass_flux_var ** 0.5)
        mid_thresh = self._mid_flux_mean + k * (self._mid_flux_var ** 0.5)
        high_thresh = self._high_flux_mean + k * (self._high_flux_var ** 0.5)

        # --- Transient detection ---
        # Normalised transient strength: how far above threshold (0 = at threshold)
        bass_above = max(0.0, bass_flux - bass_thresh)
        mid_above = max(0.0, mid_flux - mid_thresh)
        high_above = max(0.0, high_flux - high_thresh)

        # Normalise against threshold to get 0..1+ range
        bass_t = bass_above / max(bass_thresh, 0.01)
        mid_t = mid_above / max(mid_thresh, 0.01)
        high_t = high_above / max(high_thresh, 0.01)

        # Clamp to reasonable range
        bass_t = min(3.0, bass_t)
        mid_t = min(3.0, mid_t)
        high_t = min(3.0, high_t)

        # Decay previous transient values, then take max with new
        decay = self._transient_decay
        self._bass_transient = max(bass_t, self._bass_transient * decay)
        self._mid_transient = max(mid_t, self._mid_transient * decay)
        self._high_transient = max(high_t, self._high_transient * decay)

        # --- Onset event detection ---
        self._onset_detected = False
        self._onset_type = ""
        self._onset_strength = 0.0

        # Check if any band exceeds threshold and cooldown elapsed
        elapsed_since_last = now - self._last_onset_ts
        if elapsed_since_last >= self._min_onset_gap_s:
            # Determine onset type by which band is strongest
            if bass_t > 0.0 or mid_t > 0.0 or high_t > 0.0:
                max_t = max(bass_t, mid_t, high_t)
                if max_t > 0.0:
                    self._onset_detected = True
                    self._onset_strength = min(1.0, max_t)
                    self._last_onset_ts = now

                    # Classify onset type
                    if bass_t >= mid_t and bass_t >= high_t:
                        self._onset_type = "kick"
                    elif mid_t >= high_t:
                        # Mid-dominant: could be snare or vocal
                        if bass_t > mid_t * 0.4:
                            self._onset_type = "snare"
                        else:
                            self._onset_type = "vocal_swell"
                    else:
                        self._onset_type = "snare"

                    # Push to ring buffer
                    evt = self._onset_ring[self._onset_ring_head]
                    evt.timestamp = now
                    evt.event_type = self._onset_type
                    evt.strength = self._onset_strength
                    self._onset_ring_head = (
                        self._onset_ring_head + 1
                    ) % self._RING_CAPACITY

                    # Feed event micro-scheduler (§2.4)
                    if self._scheduler is not None:
                        self._scheduler.feed(OnsetEvent(
                            timestamp=now,
                            event_type=self._onset_type,
                            strength=self._onset_strength,
                        ))

        result = self.snapshot()

        if is_viz_diagnostics_enabled() and self._frame_count % 120 == 1:
            logger.debug(
                "[SPOTIFY_VIS][TRANSIENT] bass=%.3f mid=%.3f high=%.3f "
                "flux=%.3f/%.3f/%.3f thresh=%.3f/%.3f/%.3f onset=%s(%s,%.2f)",
                bass_energy, mid_energy, high_energy,
                bass_flux, mid_flux, high_flux,
                bass_thresh, mid_thresh, high_thresh,
                self._onset_detected, self._onset_type, self._onset_strength,
            )

        return result

    # ------------------------------------------------------------------
    # Public API — called from UI thread (single reader)
    # ------------------------------------------------------------------

    def snapshot(self) -> TransientEnergyBands:
        """Return a frozen snapshot of current transient state."""
        return TransientEnergyBands(
            bass_transient=self._bass_transient,
            mid_transient=self._mid_transient,
            high_transient=self._high_transient,
            onset_detected=self._onset_detected,
            onset_type=self._onset_type,
            onset_strength=self._onset_strength,
        )

    def get_scheduler(self) -> "TransientEventScheduler":
        """Return the event micro-scheduler, creating it on first access."""
        if self._scheduler is None:
            self._scheduler = TransientEventScheduler()
        return self._scheduler

    def get_recent_onsets(self, max_age_s: float = 0.5) -> List[OnsetEvent]:
        """Return onset events from the ring buffer within max_age_s."""
        now = time.time()
        cutoff = now - max_age_s
        results = []
        for evt in self._onset_ring:
            if evt.timestamp > cutoff and evt.event_type:
                results.append(OnsetEvent(
                    timestamp=evt.timestamp,
                    event_type=evt.event_type,
                    strength=evt.strength,
                ))
        results.sort(key=lambda e: e.timestamp, reverse=True)
        return results

    def get_kick_count(self, window_s: float = 0.3) -> int:
        """Count kick events in the last window_s seconds."""
        now = time.time()
        cutoff = now - window_s
        count = 0
        for evt in self._onset_ring:
            if evt.timestamp > cutoff and evt.event_type == "kick":
                count += 1
        return count

    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Reset all transient state (e.g. on mode switch)."""
        self._bass_flux_mean = 0.0
        self._bass_flux_var = 0.01
        self._mid_flux_mean = 0.0
        self._mid_flux_var = 0.01
        self._high_flux_mean = 0.0
        self._high_flux_var = 0.01
        self._prev_bass = 0.0
        self._prev_mid = 0.0
        self._prev_high = 0.0
        self._has_prev = False
        self._bass_transient = 0.0
        self._mid_transient = 0.0
        self._high_transient = 0.0
        self._onset_detected = False
        self._onset_type = ""
        self._onset_strength = 0.0
        self._last_onset_ts = 0.0
        self._frame_count = 0
        for evt in self._onset_ring:
            evt.timestamp = 0.0
            evt.event_type = ""
            evt.strength = 0.0
        self._onset_ring_head = 0
        if self._scheduler is not None:
            self._scheduler.reset()

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_threshold_k(self, k: float) -> None:
        """Adjust adaptive threshold sensitivity (lower = more sensitive)."""
        self._threshold_k = max(0.5, min(4.0, float(k)))

    def set_transient_decay(self, decay: float) -> None:
        """Adjust transient decay rate (0=instant, 1=hold forever)."""
        self._transient_decay = max(0.1, min(0.95, float(decay)))


# ---------------------------------------------------------------------------
# Event Micro-Scheduler (§2.4)
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class _ScheduledEvent:
    """Internal bookkeeping wrapper around an onset event."""
    event: OnsetEvent
    consumed: bool = False


class TransientEventScheduler:
    """Consumer-side debounce + consume-once layer for onset events.

    Sits between the ``TransientBus`` onset ring buffer and renderers.
    The bus calls ``feed()`` whenever a new onset is detected; the scheduler
    stores it with per-type debounce and exposes two consumption patterns:

    - ``consume_next(type)`` — returns the oldest unconsumed event of the
      given type and marks it consumed.  Used by Bubble (each kick drives
      exactly one promotion batch).
    - ``peek_latest(type, max_age_s)`` — returns the most recent event of
      the given type within *max_age_s* without consuming it.  Use this only
      inside a mode-owned handoff or fanout that intentionally wants a level-
      like recent-event view; do not poll it per frame where a consume-once
      edge is the correct contract.

    Threading model:
      Single writer (COMPUTE pool via ``TransientBus.update`` → ``feed``),
      single reader (UI tick).  CPython GIL guarantees atomic reference
      assignment so no locks are needed.
    """

    _CAPACITY: int = 16

    # Per-type minimum spacing (seconds).  Events arriving faster than
    # the debounce window are silently dropped.
    _DEFAULT_DEBOUNCE: dict = {
        "kick": 0.090,
        "snare": 0.120,
        "vocal_swell": 0.200,
    }
    _FALLBACK_DEBOUNCE: float = 0.100

    def __init__(self) -> None:
        self._ring: List[_ScheduledEvent] = []
        self._head: int = 0
        # Last accepted timestamp per event type (for debounce)
        self._last_accepted_ts: dict = {}

    # ------------------------------------------------------------------
    # Writer API — called from COMPUTE pool (single writer)
    # ------------------------------------------------------------------

    def feed(self, event: OnsetEvent) -> bool:
        """Attempt to schedule *event*.  Returns True if accepted.

        Rejected if the per-type debounce window has not elapsed since
        the last accepted event of the same type.
        """
        if not event.event_type:
            return False

        debounce = self._DEFAULT_DEBOUNCE.get(
            event.event_type, self._FALLBACK_DEBOUNCE
        )
        last_ts = self._last_accepted_ts.get(event.event_type, 0.0)
        if event.timestamp - last_ts < debounce:
            return False

        self._last_accepted_ts[event.event_type] = event.timestamp

        entry = _ScheduledEvent(
            event=OnsetEvent(
                timestamp=event.timestamp,
                event_type=event.event_type,
                strength=event.strength,
            )
        )

        if len(self._ring) < self._CAPACITY:
            self._ring.append(entry)
        else:
            # Overwrite oldest slot
            self._ring[self._head] = entry
            self._head = (self._head + 1) % self._CAPACITY

        return True

    # ------------------------------------------------------------------
    # Reader API — called from UI thread (single reader)
    # ------------------------------------------------------------------

    def consume_next(self, event_type: str, max_age_s: float = 0.5) -> "OnsetEvent | None":
        """Return the oldest unconsumed event of *event_type* and mark it consumed.

        Only events younger than *max_age_s* are considered.  Returns None
        if no qualifying event exists.
        """
        now = time.time()
        cutoff = now - max_age_s
        best: "_ScheduledEvent | None" = None

        for entry in self._ring:
            if (
                not entry.consumed
                and entry.event.event_type == event_type
                and entry.event.timestamp > cutoff
            ):
                if best is None or entry.event.timestamp < best.event.timestamp:
                    best = entry

        if best is not None:
            best.consumed = True
            return OnsetEvent(
                timestamp=best.event.timestamp,
                event_type=best.event.event_type,
                strength=best.event.strength,
            )
        return None

    def peek_latest(self, event_type: str, max_age_s: float = 0.3) -> "OnsetEvent | None":
        """Return the most recent event of *event_type* without consuming it.

        Only events younger than *max_age_s* are considered.
        """
        now = time.time()
        cutoff = now - max_age_s
        best: "_ScheduledEvent | None" = None

        for entry in self._ring:
            if (
                entry.event.event_type == event_type
                and entry.event.timestamp > cutoff
            ):
                if best is None or entry.event.timestamp > best.event.timestamp:
                    best = entry

        if best is not None:
            return OnsetEvent(
                timestamp=best.event.timestamp,
                event_type=best.event.event_type,
                strength=best.event.strength,
            )
        return None

    def has_recent(self, event_type: str, max_age_s: float = 0.2) -> bool:
        """Return True if any event of *event_type* exists within *max_age_s*."""
        now = time.time()
        cutoff = now - max_age_s
        for entry in self._ring:
            if (
                entry.event.event_type == event_type
                and entry.event.timestamp > cutoff
            ):
                return True
        return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Clear all scheduled events (e.g. on mode switch)."""
        self._ring.clear()
        self._head = 0
        self._last_accepted_ts.clear()
