"""Recorded PCM into the live beat engine's own capture callback, offline (native core P2b, slice 1).

``RecordedCaptureBackend`` is an ``AudioCaptureBackend`` with no device and no thread: the audio worker's capture lane
opens it through the worker's one source seam (``SpotifyVisualizerAudioWorker.set_capture_backend_factory``) and
``start(callback)`` keeps the worker's callback, exactly as a device backend does; ``push(block)`` then delivers one
block through that callback on the caller's thread, as a device callback would on its own. Blocks go out as identical
stereo channels (the worker's channel mean gives back the recorded mono exactly).

``CaptureHistoryStream`` turns a recording's per-frame native capture histories (``FeatureFrame.capture_history``:
the newest <= 4096 mono samples at each source publication, consecutive histories overlapping) back into the samples
each publication added, by exact alignment (the frames' time step breaks ties in silence), and cuts them into the
blocks a device with the configured block size delivers: the newest block whole, older samples ahead of it.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

import numpy as np

from utils.audio_capture import AudioCaptureBackend, AudioCaptureConfig

_ALIGN = 16          # samples matched exactly to place a history against the previous one


def appended_sample_count(previous: np.ndarray, current: np.ndarray, expected: int) -> int:
    """How many samples ``current`` adds after ``previous`` (exact alignment; ``expected`` breaks ties)."""
    tail = previous[-_ALIGN:]
    if len(current) < _ALIGN or len(tail) < _ALIGN:
        return len(current)
    windows = np.lib.stride_tricks.sliding_window_view(current, _ALIGN)
    starts = np.flatnonzero((windows == tail).all(axis=1))
    if not len(starts):
        return len(current)                       # no overlap: a gap in the recording, keep the whole history
    added = len(current) - (starts + _ALIGN)
    if len(added) > 1:
        # A repeating or silent passage aligns in several places: keep those whose whole overlap matches.
        whole = [k for k in added
                 if np.array_equal(current[max(0, len(current) - k - len(previous)):len(current) - k],
                                   previous[-min(len(previous), len(current) - k):])]
        added = np.array(whole or added)
    return int(added[np.argmin(np.abs(added - expected))])


class CaptureHistoryStream:
    """The samples each new source publication of a recording added, as device-sized blocks (oldest first)."""

    def __init__(self) -> None:
        self._previous: Optional[np.ndarray] = None
        self._serial: Optional[int] = None
        self._last_us: Optional[int] = None

    def blocks(self, history: Any, timestamp_us: int, block: int) -> list[np.ndarray]:
        """The blocks ``history`` (a ``CaptureHistory``) delivers at ``timestamp_us``; none for a repeated serial."""
        if history is None:
            raise ValueError("a live input needs native capture history (the recording carries no PCM)")
        if history.capture_serial == self._serial:
            return []
        if self._serial is not None and history.capture_serial < self._serial:
            raise ValueError("capture history serials must advance")
        current = np.frombuffer(history.pcm_f32le, dtype="<f4").astype(np.float32)
        if self._previous is None:
            new = current
        else:
            expected = int((timestamp_us - self._last_us) * history.sample_rate / 1e6)
            new = current[len(current) - appended_sample_count(self._previous, current, expected):]
        self._previous, self._serial, self._last_us = current, history.capture_serial, int(timestamp_us)
        block = max(1, int(block))
        cuts = list(range(len(new) - block, 0, -block))[::-1]
        return [piece for piece in np.split(new, cuts) if len(piece)]


class RecordedCaptureBackend(AudioCaptureBackend):
    """A capture backend fed by ``push``: no device, no thread (see the module docstring)."""

    def __init__(self, config: AudioCaptureConfig | None = None, *,
                 on_started: Callable[["RecordedCaptureBackend"], None] | None = None) -> None:
        self._config = config or AudioCaptureConfig()
        self._rate = int(self._config.sample_rate)
        # What a device negotiates: the configured block, or its own 10 ms period on Auto (0).
        self._negotiated_block_size = int(self._config.block_size) or self._rate // 100
        self._callback: Callable[[Any], None] | None = None
        self._on_started = on_started

    @property
    def block_size(self) -> int:
        return self._negotiated_block_size

    def start(self, callback: Callable[[Any], None]) -> bool:
        self._callback = callback
        self._note_capture_starting()
        if self._on_started is not None:
            self._on_started(self)
        return True

    def push(self, block: np.ndarray) -> None:
        """Deliver one mono block through the worker's capture callback, as the device's callback would."""
        callback = self._callback
        if callback is None:
            raise RuntimeError("the recorded capture backend is not open")
        mono = np.ascontiguousarray(block, dtype=np.float32).reshape(-1)
        callback(np.column_stack((mono, mono)))
        self._note_capture_callback()

    def stop(self) -> None:
        self._callback = None
        self._note_capture_stopped()

    def restart(self) -> bool:
        callback = self._callback
        self.stop()
        return callback is not None and self.start(callback)

    def is_running(self) -> bool:
        return self._callback is not None

    @property
    def sample_rate(self) -> int:
        return self._rate

    @property
    def channels(self) -> int:
        return 2


__all__ = ["CaptureHistoryStream", "RecordedCaptureBackend", "appended_sample_count"]
