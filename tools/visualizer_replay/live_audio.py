"""Recorded music into a live process: a capture backend that plays a recording's native PCM in real time.

Feature replay (``engine.ReplayBeatEngine``) enters at the post-DSP seam, so the live audio path (the capture
callback, the worker's mono mix, DSP and the analysis lane, all competing for the GIL) never runs. For live-shape
measurement (``tools/visualizer_live_check.py``) the same recorded music must instead arrive where the loopback does:
``RecordedLoopback`` is an ``AudioCaptureBackend`` that delivers the recording's PCM block by block at the real sample
rate, from its own thread, through the worker's ordinary callback.

Recordings keep each frame's newest native mono history (up to 4096 float32 samples, lossless); consecutive histories
overlap, so ``recorded_pcm`` stitches them back into the original stream by exact sample alignment (in silence, where
alignment is ambiguous, by the frames' time step). Blocks are delivered as identical stereo channels, so the worker's
channel mean gives back exactly the recorded mono. The stream loops at its end with a 10 ms crossfade.
"""
from __future__ import annotations

import base64
import json
import threading
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np

from utils.audio_capture import AudioCaptureBackend, AudioCaptureConfig

_ALIGN = 16          # samples matched exactly to place a history against the stream so far


def recorded_pcm(path: Path, *, start: float = 0.0, seconds: float | None = None) -> tuple[np.ndarray, int]:
    """The recording's native mono PCM as one float32 stream, and its sample rate."""
    pieces: list[np.ndarray] = []
    previous: np.ndarray | None = None
    serial, rate, origin, last_us = None, 48000, None, None
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            history, stamp = frame.get("capture_history"), int(frame["timestamp_us"])
            origin = stamp if origin is None else origin
            elapsed = (stamp - origin) / 1e6
            if seconds is not None and elapsed > start + seconds:
                break
            if elapsed < start or not history or history["capture_serial"] == serial:
                continue
            serial, rate = history["capture_serial"], int(history["sample_rate"])
            samples = np.frombuffer(base64.b64decode(history["samples"]), dtype="<f4").astype(np.float32)
            if previous is None:
                pieces.append(samples)
            else:
                expected = int((stamp - last_us) * rate / 1e6) if last_us is not None else len(samples)
                pieces.append(samples[len(samples) - _new_samples(previous, samples, expected):])
            previous, last_us = samples, stamp
    if not pieces:
        raise ValueError(f"{path} holds no native capture history")
    return np.concatenate(pieces), rate


def _new_samples(previous: np.ndarray, current: np.ndarray, expected: int) -> int:
    """How many samples ``current`` adds after ``previous`` (exact alignment; the time step breaks ties)."""
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


class RecordedLoopback(AudioCaptureBackend):
    """Plays recorded PCM into the capture callback at the real rate (a stand-in for WASAPI loopback)."""

    def __init__(self, config: AudioCaptureConfig | None, pcm: np.ndarray, rate: int) -> None:
        self._config = config or AudioCaptureConfig()
        self._pcm, self._rate = pcm, int(rate)
        fade = min(len(pcm) // 4, self._rate // 100)
        if fade:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            self._pcm = np.concatenate((pcm[fade:-fade], pcm[-fade:] * (1.0 - ramp) + pcm[:fade] * ramp))
        self._negotiated_block_size = 0
        self._position = 0
        self._running = False
        self._callback: Callable[[Any], None] | None = None
        self._thread: threading.Thread | None = None

    def start(self, callback: Callable[[Any], None]) -> bool:
        if self._running:
            return True
        self._callback, self._running = callback, True
        self._negotiated_block_size = int(self._config.block_size) or self._rate // 100
        self._note_capture_starting()
        self._thread = threading.Thread(target=self._run, name="recorded-loopback", daemon=True)
        self._thread.start()
        return True

    def _run(self) -> None:
        block = self._negotiated_block_size
        period, next_block = block / self._rate, time.monotonic()
        while self._running:
            end = self._position + block
            mono = (self._pcm[self._position:end] if end <= len(self._pcm)
                    else np.concatenate((self._pcm[self._position:], self._pcm[:end - len(self._pcm)])))
            self._position = end % len(self._pcm)
            try:
                self._callback(np.column_stack((mono, mono)))
                self._note_capture_callback()
            except Exception:
                self._report_native_callback_failure()
            next_block += period
            delay = next_block - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                next_block = time.monotonic()

    def stop(self) -> None:
        self._running = False
        thread, self._thread = self._thread, None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._note_capture_stopped()

    def restart(self) -> bool:
        callback = self._callback
        self.stop()
        return callback is not None and self.start(callback)

    def is_running(self) -> bool:
        return self._running

    @property
    def sample_rate(self) -> int:
        return self._rate

    @property
    def channels(self) -> int:
        return 2


__all__ = ["RecordedLoopback", "recorded_pcm"]
