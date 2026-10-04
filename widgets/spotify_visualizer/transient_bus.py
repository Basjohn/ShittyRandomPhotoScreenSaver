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

import itertools
import logging
import math
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


@dataclass(frozen=True, slots=True)
class MusicalOnset:
    """One detected onset, published once and never mutated (``TransientBus.recent_onsets``).

    ``serial`` is unique in the process (it never restarts, not even with a new bus), so a
    consumer takes every onset after the last serial it saw exactly once, however its own
    cadence relates to the analysis. ``strength`` is the bus's clipped 0..1 value;
    ``magnitude`` the unclipped one (0..3: how far above threshold, relative to it), which
    still tells a big hit from a medium one. ``loudness`` is the absolute post-noise-floor,
    pre-AGC level the onset happened at (the bus's own input is loudness-normalised, so a
    near-silent passage triggers as readily as a loud one); ``presence`` is that level
    against the recent running level (about 1 in steady music, low in a quiet passage of a
    loud track, 0 with no loudness supplied).
    """
    serial: int
    timestamp: float
    kind: str
    strength: float
    magnitude: float
    loudness: float = 0.0
    presence: float = 0.0


_ONSET_SERIALS = itertools.count(1)
# Time constant of the running loudness ``presence`` compares an onset with (seconds).
LOUDNESS_REFERENCE_SECONDS = 6.0

# How much an onset counts musically, for every consumer that rewards onsets (Shockwave Grid's
# waves, Voxel Sphere's fragments and particles): an absolute loudness below MUSICAL_QUIET's
# first edge counts for nothing (near-silence), and so does a presence below MUSICAL_PRESENCE's
# (a quiet passage inside a loud track). Against the track's usual onset presence, learned at
# MUSICAL_USUAL_RATE from onsets clearly part of the music, a louder onset stands out and a
# softer one recedes.
MUSICAL_QUIET = (0.08, 0.6)
MUSICAL_PRESENCE = (0.15, 0.8)
MUSICAL_USUAL_RATE = 0.12


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    t = max(0.0, min(1.0, (float(value) - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def musical_weight(loudness: float, presence: float) -> float:
    """0..1: how much an onset at ``loudness`` and ``presence`` (``MusicalOnset``) counts at all."""
    return (_smoothstep(MUSICAL_QUIET[0], MUSICAL_QUIET[1], loudness)
            * _smoothstep(MUSICAL_PRESENCE[0], MUSICAL_PRESENCE[1], presence))


def musical_emphasis(presence: float, usual: float) -> float:
    """How far an onset stands out against the track's ``usual`` onset presence: 1 for a usual
    one, up to 2^1.5 for a much louder one, down to 0.5^1.5 for a much softer one."""
    return max(0.5, min(2.0, float(presence) / max(float(usual), 1e-3))) ** 1.5


PASSAGE_RAMP_CURVE = 1.3


def passage_ramp(intensity: float, quiet: float) -> float:
    """The share of a reaction a passage earns: ``quiet`` in the track's quietest passage, 1 in its
    loudest, convex (``PASSAGE_RAMP_CURVE``) so a usual passage sits nearer quiet than loud.
    ``intensity`` is ``PassageIntensity`` (``BeatEngine.get_musical_intensity``)."""
    level = max(0.0, min(1.0, float(intensity)))
    return quiet + (1.0 - quiet) * pow(level, PASSAGE_RAMP_CURVE)


class PassageIntensity:
    """How loud the music is against the track's own recent loud level, 0..1, rising fast and
    falling gently ("everything ramps"): 0 in a passage at or below ``LOW`` of that level (or
    near-silence), 1 at ``HIGH`` of it and above, so a sustained loud passage stays at 1.

    The absolute loudness feeds an envelope (``ATTACK_S`` up, ``RELEASE_S`` down) compared with a
    peak tracker (rises in ``PEAK_RISE_S``, falls over ``PEAK_FALL_S``), seeded by the first music.
    Mastered music spans only about +-30% of its own loud level (recorded clips 2026-10-04: the
    envelope sits at 0.6-1.0 of the peak), so a raw ratio barely moves; mapped from ``LOW``-``HIGH``
    it spreads: p10 0-0.25, p50 ~0.65, p90 ~1 on those clips. Near-silence neither seeds nor moves
    the peak and reads 0. Time-based, so the analysis and replay rates agree.
    """

    ATTACK_S = 0.06
    RELEASE_S = 0.8
    PEAK_RISE_S = 2.0
    PEAK_FALL_S = 30.0
    LOW = 0.6
    HIGH = 1.0

    __slots__ = ("_envelope", "_peak", "_value")

    def __init__(self) -> None:
        self._envelope = 0.0
        self._peak = 0.0
        self._value = 0.0

    @property
    def value(self) -> float:
        return self._value

    @staticmethod
    def _follow(level: float, target: float, dt: float, up_s: float, down_s: float) -> float:
        tau = up_s if target > level else down_s
        return level + (target - level) * (1.0 - math.exp(-dt / tau))

    def update(self, loudness: float, dt: float) -> float:
        level = max(0.0, float(loudness))
        dt = max(0.0, min(1.0, float(dt)))
        self._envelope = self._follow(self._envelope, level, dt, self.ATTACK_S, self.RELEASE_S)
        if level < MUSICAL_QUIET[0]:
            self._value = 0.0
            return self._value
        if self._peak <= 0.0:                     # the first music seeds the loud level
            self._peak = level
        self._peak = self._follow(self._peak, self._envelope, dt, self.PEAK_RISE_S, self.PEAK_FALL_S)
        ratio = self._envelope / max(self._peak, 1e-6)
        self._value = max(0.0, min(1.0, (ratio - self.LOW) / (self.HIGH - self.LOW)))
        return self._value


def learn_usual_presence(usual: float, presence: float) -> float:
    """The track's usual onset presence after an onset at ``presence`` (start from 1.0, neutral):
    only an onset clearly part of the music moves it, and no more than the most it can stand out
    (``musical_emphasis``'s 2x) would, so one outlier cannot make every later onset look soft."""
    if float(presence) >= MUSICAL_PRESENCE[1]:
        learned = min(float(presence), 2.0 * float(usual))
        return float(usual) + (learned - float(usual)) * MUSICAL_USUAL_RATE
    return float(usual)


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
    # How many published onsets ``recent_onsets`` keeps (a consumer reading at its own
    # cadence never falls this far behind: onsets are at least ``min_onset_gap_s`` apart).
    PUBLISHED_ONSETS: int = 16

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
        # Published onsets (replaced, never mutated) and the running loudness.
        self._recent_onsets: tuple[MusicalOnset, ...] = ()
        self._loudness_reference: float = 0.0
        # The latest frame's (loudness, presence), replaced whole (readers never see half), and
        # where the music sits in the track's own dynamic range (``PassageIntensity``).
        self._musical_level: tuple[float, float] = (0.0, 0.0)
        self._intensity = PassageIntensity()

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
        *,
        loudness: float | None = None,
    ) -> TransientEnergyBands:
        """Process one FFT frame and return transient energy snapshot.

        Parameters are post-noise-floor, pre-AGC band energies (0..1 range).
        ``loudness`` is the frame's absolute level, before any normalisation of those
        energies; onsets carry it (see ``MusicalOnset``).
        """
        now = time.time()
        elapsed = now - self._last_update_ts if self._last_update_ts else 0.0
        self._last_update_ts = now
        self._frame_count += 1
        if loudness is not None:
            level = max(0.0, float(loudness))
            if level < MUSICAL_QUIET[0]:
                # Near-silence (a pause, a gap between tracks, the start before the music) is not
                # the music's level: it neither seeds nor drains the running level, so the music
                # starting or resuming is not "many times louder than usual" (it was: presence 46
                # after a 6 s pause, 363-1089 when a near-silent first frame seeded it).
                pass
            elif self._loudness_reference < MUSICAL_QUIET[0] or elapsed <= 0.0:
                self._loudness_reference = max(self._loudness_reference, level)
            else:
                alpha = 1.0 - math.exp(-min(elapsed, 1.0) / LOUDNESS_REFERENCE_SECONDS)
                self._loudness_reference += (level - self._loudness_reference) * alpha
            reference = self._loudness_reference
            self._musical_level = (level, level / reference if reference > 1e-6 else 0.0)
            self._intensity.update(level, elapsed)

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

                    # Publish it (one tuple replacement: readers never see a partial event).
                    level, presence = self._musical_level if loudness is not None else (0.0, 0.0)
                    self._recent_onsets = self._recent_onsets[1 - self.PUBLISHED_ONSETS:] + (MusicalOnset(
                        serial=next(_ONSET_SERIALS),
                        timestamp=now,
                        kind=self._onset_type,
                        strength=self._onset_strength,
                        magnitude=max_t,
                        loudness=level,
                        presence=presence,
                    ),)

                    # Feed event micro-scheduler (§2.4)
                    if self._scheduler is not None:
                        self._scheduler.feed(OnsetEvent(
                            timestamp=now,
                            event_type=self._onset_type,
                            strength=self._onset_strength,
                        ))

        result = self.snapshot()

        if (
            is_viz_diagnostics_enabled()
            and logger.isEnabledFor(logging.DEBUG)
            and self._frame_count % 120 == 1
        ):
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

    @property
    def recent_onsets(self) -> tuple[MusicalOnset, ...]:
        """The last ``PUBLISHED_ONSETS`` onsets, oldest first (an immutable tuple)."""
        return self._recent_onsets

    @property
    def musical_level(self) -> tuple[float, float]:
        """The latest frame's (loudness, presence), as an onset there would carry them."""
        return self._musical_level

    @property
    def musical_intensity(self) -> float:
        """Where the music sits in the track's own dynamic range, 0..1 (``PassageIntensity``)."""
        return self._intensity.value

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
