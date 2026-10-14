"""Activation-fenced authored state for the Shockwave Grid Visualizer mode.

Spectrum's frame runtime (bars, peaks, temporal treatment, shape editor, energy distribution)
plus a bounded ring of shockwave events: each musical onset the transient bus publishes
(``MusicalOnset``, taken exactly once by serial, however the analysis and logical cadences
relate) and at least ``shockwave_gap`` after the last becomes one event, born when the onset
happened, with a deterministic origin (from its admission number and onset type) and a strength
from its magnitude, loudness and presence (``shockwave_strength``, its emphasis on the fixed
loudness scale), times the passage's share
(``shockwave_passage_share``); an onset too weak for a wave makes none. The gap and the share
both ramp on the passage intensity. Events are aged on the logical clock at capture and dropped after
``SHOCKWAVE_LIFETIME``; at most ``SHOCKWAVE_CAPACITY`` are held, the oldest giving way. Nothing
here touches Qt or GL.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_CAPACITY,
    SHOCKWAVE_LIFETIME,
    SHOCKWAVE_MIN_STRENGTH,
    shockwave_gap,
    shockwave_origin,
    shockwave_passage_share,
    shockwave_strength,
)
from widgets.spotify_visualizer.frame_runtime_lifecycle import retirement_fenced
from widgets.spotify_visualizer.spectrum_frame_runtime import SpectrumFrameRuntime

# One admitted shockwave: (birth time, x as a share of the half width, z, strength).
_Event = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class TerrainGrowthResolved:
    values: tuple[float, ...]
    changed: bool
    pending: bool


class ShockwaveGridFrameRuntime(SpectrumFrameRuntime):
    """Spectrum's state owner plus the shockwave event ring."""

    def __init__(self) -> None:
        super().__init__()
        self._events: list[_Event] = []
        self._event_serial = 0
        self._onset_serial = 0
        self._last_event_ts = float("-inf")
        self._reset_terrain_growth()

    def reset(self) -> None:
        super().reset()
        self._events = []
        self._event_serial = 0
        self._onset_serial = 0
        self._last_event_ts = float("-inf")
        self._reset_terrain_growth()

    def _reset_terrain_growth(self) -> None:
        self._terrain_growth = (0.0,) * 8
        self._terrain_targets = (0.0,) * 8
        self._terrain_last_ts = None
        self._terrain_identity = None
        self._terrain_growth_pending = False

    @property
    def terrain_growth_pending(self) -> bool:
        """A real unfinished growth/release step needs the existing logical wake owner."""
        return self._terrain_growth_pending

    @retirement_fenced
    def advance_terrain_growth(self, bars, *, now_ts: float, playing: bool,
                               identity: tuple[int, int, int], source_identity: tuple[int, int],
                               attack: float, release: float, enabled: bool = True,
                               musical_gain: float = 1.0) -> TerrainGrowthResolved | None:
        """Eight spatial envelopes on the capture clock; no paused Spectrum idle music.

        Spatial means integrate overlapping bar intervals, including profiles shorter
        than eight bars. Target hysteresis retains tiny fluctuations; exponential
        attack/release remains independent of event ages and capture partitioning.
        """
        now = float(now_ts)
        if not math.isfinite(now):
            raise ValueError("terrain growth capture time must be finite")
        if not enabled:
            # Movement=0 makes envelopes invisible. Drop their targets/time rather
            # than doing hidden musical work or resuming with accumulated growth.
            # The setting edge itself publishes the visible geometry change.
            if self._terrain_last_ts is not None:
                self._reset_terrain_growth()
            return TerrainGrowthResolved(self._terrain_growth, False, False)
        source_ready = (source_identity == identity[1:] and all(value >= 0 for value in identity))
        token = (identity, source_identity)
        previous = self._terrain_growth
        if token != self._terrain_identity or (self._terrain_last_ts is not None and now < self._terrain_last_ts):
            self._reset_terrain_growth()
            self._terrain_identity = token
        if not source_ready:
            self._reset_terrain_growth()
            self._terrain_identity = token
            self._terrain_last_ts = now
            return TerrainGrowthResolved(self._terrain_growth, previous != self._terrain_growth, False)
        musical_gain = float(musical_gain)
        if not math.isfinite(musical_gain) or not 0.0 <= musical_gain <= 1.0:
            raise ValueError("terrain growth musical gain must be finite within 0..1")
        targets = [0.0] * 8
        if playing and musical_gain > 0.0 and bars:
            count = len(bars)
            for region in range(8):
                lo, hi = region * count / 8.0, (region + 1) * count / 8.0
                for index in range(math.floor(lo), min(count, math.ceil(hi))):
                    overlap = max(0.0, min(hi, index + 1) - max(lo, index))
                    level = float(bars[index])
                    if not math.isfinite(level):
                        raise ValueError("terrain growth bars must be finite")
                    targets[region] += musical_gain * max(0.0, min(1.0, level)) * overlap / (hi - lo)
        targets = tuple(old if target > 0.0 and abs(target - old) < 0.015 else target
                        for old, target in zip(self._terrain_targets, targets))
        dt = 0.0 if self._terrain_last_ts is None else max(0.0, now - self._terrain_last_ts)
        attack, release = float(attack), float(release)
        if not math.isfinite(attack) or not math.isfinite(release) or attack <= 0.0 or release <= 0.0:
            raise ValueError("terrain growth attack/release must be finite positive seconds")
        values = []
        for value, target in zip(self._terrain_growth, targets):
            tau = attack if target > value else release
            advanced = target + (value - target) * math.exp(-dt / tau)
            values.append(target if dt > 0.0 and abs(advanced - target) < 0.0001 else advanced)
        self._terrain_growth = tuple(values)
        self._terrain_targets = targets
        self._terrain_last_ts = now
        self._terrain_growth_pending = any(abs(a - b) >= 0.0001 for a, b in zip(values, targets))
        return TerrainGrowthResolved(self._terrain_growth, previous != self._terrain_growth, self._terrain_growth_pending)

    @property
    def onset_serial(self) -> int:
        """The last onset serial taken: ask the engine only for the onsets after it."""
        return self._onset_serial

    @retirement_fenced
    def record_onsets(self, *, onsets, now_ts: float, playing: bool,
                      passage_intensity: float) -> tuple[tuple[float, float, float, float], ...]:
        """Admit the new published onsets (``MusicalOnset``, oldest first; any already taken
        are skipped) at ``passage_intensity`` (``BeatEngine.get_musical_intensity``) and return
        the live events as (age, x share, z, strength), oldest first."""
        now = float(now_ts)
        gap = shockwave_gap(passage_intensity)
        share = shockwave_passage_share(passage_intensity)
        if self._events and now < self._events[-1][0]:
            self._events = []                       # the clock went back (a new activation)
            self._last_event_ts = float("-inf")
        for onset in onsets:
            if onset.serial <= self._onset_serial:
                continue
            self._onset_serial = onset.serial
            birth = min(now, float(onset.timestamp))
            if not playing or birth - self._last_event_ts < gap:
                continue
            presence = float(onset.presence)
            strength = share * shockwave_strength(onset.magnitude, onset.loudness, presence)
            if strength < SHOCKWAVE_MIN_STRENGTH:
                continue
            x, z = shockwave_origin(self._event_serial, str(onset.kind))
            self._events.append((birth, x, z, strength))
            self._event_serial += 1
            self._last_event_ts = birth
        self._events = [event for event in self._events if now - event[0] < SHOCKWAVE_LIFETIME]
        del self._events[:-SHOCKWAVE_CAPACITY]
        return tuple((now - birth, x, z, s) for birth, x, z, s in self._events)


__all__ = ["ShockwaveGridFrameRuntime"]
