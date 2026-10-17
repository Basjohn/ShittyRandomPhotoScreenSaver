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
``SHOCKWAVE_EVENT_MEMORY``; at most ``SHOCKWAVE_EVENT_RING`` are held, the oldest giving way (the water draws
only its newest live ones; Neon's beat stars use the longer tail). Nothing here touches Qt or GL.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_EVENT_MEMORY,
    SHOCKWAVE_EVENT_RING,
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


# Terrain Reaction. Each lane's drive is mostly how far its energy rises above its own recent level
# (novelty) and a little its share of the whole (so a lane only ever claims its part), times the
# music's weight; a sustained wall of bass settles to a modest steady drive instead of pinning.
REACTION_SLOW_TAU = 4.0       # seconds: a lane's recent level
REACTION_SUSTAIN = 0.3        # the share part's weight
REACTION_NOVELTY = 0.7        # the rise part's weight
REACTION_NOVELTY_GAIN = 2.4
REACTION_MOTION = (0.15, 1.35)   # phase units per second at Motion Speed 0 and 1, at full drive


@dataclass(frozen=True, slots=True)
class TerrainReactionResolved:
    bands: tuple[float, ...]
    phase: float
    changed: bool
    pending: bool


def reaction_lane_targets(energies, recent, musical_gain: float) -> tuple[float, ...]:
    """Each lane's drive target (0..1) from its energy, its recent level and the music's weight."""
    total = sum(energies)
    lanes = len(energies)
    targets = []
    for energy, level in zip(energies, recent):
        share = energy / total if total > 1e-9 else 0.0
        rise = max(0.0, energy / (level + 0.05) - 1.0)
        drive = REACTION_SUSTAIN * min(1.0, lanes * share) + REACTION_NOVELTY * math.tanh(REACTION_NOVELTY_GAIN * rise)
        targets.append(max(0.0, min(1.0, musical_gain * drive)))
    return tuple(targets)


class ShockwaveGridFrameRuntime(SpectrumFrameRuntime):
    """Spectrum's state owner plus the shockwave event ring."""

    def __init__(self) -> None:
        super().__init__()
        self._events: list[_Event] = []
        self._event_serial = 0
        self._onset_serial = 0
        self._last_event_ts = float("-inf")
        self._reset_terrain_reaction()

    def reset(self) -> None:
        super().reset()
        self._events = []
        self._event_serial = 0
        self._onset_serial = 0
        self._last_event_ts = float("-inf")
        self._reset_terrain_reaction()

    def _reset_terrain_reaction(self) -> None:
        from rendering.gl_programs.neon_terrain_reaction import REACTION_LANES

        lanes = len(REACTION_LANES)
        self._terrain_bands = (0.0,) * lanes
        self._terrain_recent: tuple[float, ...] | None = None
        self._terrain_phase = 0.0
        self._terrain_last_ts = None
        self._terrain_identity = None
        self._terrain_pending = False

    @property
    def terrain_reaction_pending(self) -> bool:
        """An unfinished rise/settle or a wandering phase needs the existing logical wake owner."""
        return self._terrain_pending

    @retirement_fenced
    def advance_terrain_reaction(self, spectrum, *, now_ts: float, playing: bool,
                                 identity: tuple[int, int, int], source_identity: tuple[int, int],
                                 attack: float, release: float, motion_speed: float, enabled: bool = True,
                                 musical_gain: float = 1.0) -> TerrainReactionResolved | None:
        """Five lane drives eased on the capture clock, and the landforms' wander phase.

        The phase advances only while the music drives the land, so silence holds the land still.
        Disabled, nothing is kept or computed; re-enabling starts from rest.
        """
        from rendering.gl_programs.neon_terrain_reaction import reaction_band_energies

        now = float(now_ts)
        if not math.isfinite(now):
            raise ValueError("terrain reaction capture time must be finite")
        previous = (self._terrain_bands, self._terrain_phase)
        if not enabled:
            if self._terrain_last_ts is not None:
                self._reset_terrain_reaction()
            return TerrainReactionResolved(self._terrain_bands, self._terrain_phase, False, False)
        source_ready = (source_identity == identity[1:] and all(value >= 0 for value in identity))
        token = (identity, source_identity)
        if token != self._terrain_identity or (self._terrain_last_ts is not None and now < self._terrain_last_ts):
            self._reset_terrain_reaction()
            self._terrain_identity = token
        if not source_ready:
            self._reset_terrain_reaction()
            self._terrain_identity = token
            self._terrain_last_ts = now
            changed = previous != (self._terrain_bands, self._terrain_phase)
            return TerrainReactionResolved(self._terrain_bands, self._terrain_phase, changed, False)
        musical_gain = float(musical_gain)
        if not math.isfinite(musical_gain) or not 0.0 <= musical_gain <= 1.0:
            raise ValueError("terrain reaction musical gain must be finite within 0..1")
        attack, release, speed = float(attack), float(release), float(motion_speed)
        if not all(math.isfinite(v) for v in (attack, release, speed)) or attack <= 0.0 or release <= 0.0:
            raise ValueError("terrain reaction rise/settle must be finite positive seconds")
        dt = 0.0 if self._terrain_last_ts is None else max(0.0, now - self._terrain_last_ts)
        energies = reaction_band_energies(spectrum) if playing else (0.0,) * len(self._terrain_bands)
        if any(not math.isfinite(value) for value in energies):
            raise ValueError("terrain reaction spectrum must be finite")
        if self._terrain_recent is None:
            self._terrain_recent = energies
        targets = reaction_lane_targets(energies, self._terrain_recent, musical_gain if playing else 0.0)
        if dt > 0.0:
            keep = math.exp(-dt / REACTION_SLOW_TAU)
            self._terrain_recent = tuple(level * keep + energy * (1.0 - keep)
                                         for level, energy in zip(self._terrain_recent, energies))
        bands = []
        for value, target in zip(self._terrain_bands, targets):
            tau = attack if target > value else release
            advanced = target + (value - target) * math.exp(-dt / tau) if dt > 0.0 else value
            bands.append(target if dt > 0.0 and abs(advanced - target) < 0.0001 else advanced)
        drive = sum(bands) / len(bands)
        low, high = REACTION_MOTION
        rate = (low + (high - low) * max(0.0, min(1.0, speed))) * drive
        self._terrain_phase = math.fmod(self._terrain_phase + dt * rate, 1000.0 * math.pi)
        self._terrain_bands = tuple(bands)
        self._terrain_last_ts = now
        self._terrain_pending = rate > 0.0 or any(abs(a - b) >= 0.0001 for a, b in zip(bands, targets))
        changed = previous != (self._terrain_bands, self._terrain_phase)
        return TerrainReactionResolved(self._terrain_bands, self._terrain_phase, changed, self._terrain_pending)

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
        self._events = [event for event in self._events if now - event[0] < SHOCKWAVE_EVENT_MEMORY]
        del self._events[:-SHOCKWAVE_EVENT_RING]
        return tuple((now - birth, x, z, s) for birth, x, z, s in self._events)


__all__ = ["ShockwaveGridFrameRuntime"]
