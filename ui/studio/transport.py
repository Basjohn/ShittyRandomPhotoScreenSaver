"""Preview transport: time, play/pause, scrub and loop on the Studio's own frames.

No timer: the Studio surface reports each Quick frame start (``afterAnimating``)
to :meth:`StudioTransport.on_frame`, which advances playback by the measured wall
time between frames and asks for one more frame only while playing. Paused, the
transport does nothing and requests nothing. ``stop`` makes it permanently inert.
"""
from __future__ import annotations

import time


class StudioTransport:
    def __init__(self, duration: float = 0.0, *, clock=time.perf_counter) -> None:
        self._clock = clock
        self.duration = max(0.0, float(duration))
        self.time = 0.0
        self.playing = False
        self.loop = True
        self.stopped = False
        self._last_wall: float | None = None
        self.frames_advanced = 0

    def set_duration(self, duration: float) -> None:
        self.duration = max(0.0, float(duration))
        self.time = min(self.time, self.duration)

    def play(self) -> None:
        if self.stopped:
            return
        if self.duration > 0.0 and self.time >= self.duration:
            self.time = 0.0
        self.playing = True
        self._last_wall = None

    def pause(self) -> None:
        self.playing = False
        self._last_wall = None

    def seek(self, seconds: float) -> None:
        self.time = min(self.duration, max(0.0, float(seconds)))
        self._last_wall = None

    def stop(self) -> None:
        """Retire: no further advancement or frame requests, ever."""
        self.playing = False
        self.stopped = True
        self._last_wall = None

    def on_frame(self) -> bool:
        """Advance by wall time since the previous frame. Returns True if time moved."""
        if not self.playing or self.stopped:
            return False
        now = self._clock()
        last, self._last_wall = self._last_wall, now
        if last is None:
            return False          # first frame after play: establish the wall reference
        step = min(0.1, max(0.0, now - last))  # a stalled frame never jumps the timeline
        if step <= 0.0:
            return False
        moved = self.time + step
        if self.duration > 0.0 and moved >= self.duration:
            if self.loop:
                moved = moved % self.duration
            else:
                moved = self.duration
                self.playing = False
        self.time = moved
        self.frames_advanced += 1
        return True

    @property
    def wants_frames(self) -> bool:
        return self.playing and not self.stopped


__all__ = ["StudioTransport"]
