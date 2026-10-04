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


class ShockwaveGridFrameRuntime(SpectrumFrameRuntime):
    """Spectrum's state owner plus the shockwave event ring."""

    def __init__(self) -> None:
        super().__init__()
        self._events: list[_Event] = []
        self._event_serial = 0
        self._onset_serial = 0
        self._last_event_ts = float("-inf")

    def reset(self) -> None:
        super().reset()
        self._events = []
        self._event_serial = 0
        self._onset_serial = 0
        self._last_event_ts = float("-inf")

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
