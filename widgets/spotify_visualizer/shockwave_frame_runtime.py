"""Activation-fenced authored state for the Shockwave Grid Visualizer mode.

Spectrum's frame runtime (bars, peaks, temporal treatment, shape editor, energy distribution)
plus a bounded ring of shockwave events: each admitted musical onset (the rising edge of the
transient bus's onset flag, at least ``SHOCKWAVE_MIN_GAP`` after the last) becomes one event
with a deterministic origin (from its serial number and onset type) and the onset's strength.
Events are aged on the logical clock at capture and dropped after ``SHOCKWAVE_LIFETIME``; at most
``SHOCKWAVE_CAPACITY`` are held, the oldest giving way. Nothing here touches Qt or GL.
"""

from __future__ import annotations

from rendering.gl_programs.shockwave_grid_program import (
    SHOCKWAVE_CAPACITY,
    SHOCKWAVE_LIFETIME,
    SHOCKWAVE_MIN_GAP,
    shockwave_origin,
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
        self._onset_held = False
        self._last_event_ts = float("-inf")

    def reset(self) -> None:
        super().reset()
        self._events = []
        self._event_serial = 0
        self._onset_held = False
        self._last_event_ts = float("-inf")

    @retirement_fenced
    def record_onsets(self, *, onset: bool, kind: str, strength: float, now_ts: float,
                      playing: bool) -> tuple[tuple[float, float, float, float], ...]:
        """Admit this tick's onset (if it is a new one) and return the live events as
        (age, x share, z, strength), oldest first."""
        rising = bool(onset) and not self._onset_held
        self._onset_held = bool(onset)
        now = float(now_ts)
        if self._events and now < self._events[-1][0]:
            self._events = []                       # the clock went back (a new activation)
            self._last_event_ts = float("-inf")
        if rising and playing and now - self._last_event_ts >= SHOCKWAVE_MIN_GAP:
            x, z = shockwave_origin(self._event_serial, str(kind))
            self._events.append((now, x, z, max(0.25, min(1.0, float(strength)))))
            self._event_serial += 1
            self._last_event_ts = now
        self._events = [event for event in self._events if now - event[0] < SHOCKWAVE_LIFETIME]
        del self._events[:-SHOCKWAVE_CAPACITY]
        return tuple((now - birth, x, z, s) for birth, x, z, s in self._events)


__all__ = ["ShockwaveGridFrameRuntime"]
