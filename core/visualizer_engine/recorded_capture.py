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

``PacedPcmSource`` (work order 5, slice 5.1) paces a continuous recorded PCM stream on the audio clock for a session
that ticks on its own cadence: at each cadence edge it hands over the blocks a device would have delivered since the
previous edge (the elapsed deadline time times the sample rate, in device-sized blocks, the remainder carried). It is
not a poll and adds no timer: it has no thread and never waits; it runs only inside the cadence's own step, which the
logical runtime already wakes for, and the audio clock is that step's deadline timestamp. ``pcm_from_capture_histories``
rebuilds a recording's continuous PCM (``CaptureHistoryStream``'s samples, concatenated).
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
        self._negotiate()
        self._callback: Callable[[Any], None] | None = None
        self._on_started = on_started
        self.restarts = 0

    def _negotiate(self) -> None:
        # What a device reports when it opens: the configured block, 0 on Auto (PortAudio's unspecified size, as
        # pyaudiowpatch and sounddevice report it; checkpoint audit 3, A3-L2). A restart re-negotiates (the capture
        # lane sets the new block size on ``_config`` before ``restart``).
        self._negotiated_block_size = int(self._config.block_size)
        self._delivered_block_size = self._negotiated_block_size or self._rate // 100

    @property
    def block_size(self) -> int:
        """The block each push delivers: the negotiated size, or a device's own 10 ms period on Auto."""
        return self._delivered_block_size

    def start(self, callback: Callable[[Any], None]) -> bool:
        self._negotiate()
        self._callback = callback
        self._note_capture_starting()
        if self._on_started is not None:
            self._on_started(self)
        return True

    def push(self, block: np.ndarray) -> None:
        """Deliver one mono block through the worker's capture callback, as the device's callback would."""
        if not self.offer(block):
            raise RuntimeError("the recorded capture backend is not open")

    def offer(self, block: np.ndarray) -> bool:
        """``push`` for a source that runs on its own clock: a block offered while capture is closed is not captured
        (a device delivers nothing once its stream stops; the capture lane may stop it at any time). Whether it was
        delivered."""
        callback = self._callback
        if callback is None:
            return False
        mono = np.ascontiguousarray(block, dtype=np.float32).reshape(-1)
        callback(np.column_stack((mono, mono)))
        self._note_capture_callback()
        return True

    def stop(self) -> None:
        self._callback = None
        self._note_capture_stopped()

    def restart(self) -> bool:
        callback = self._callback
        self.restarts += 1        # how often the capture lane restarted this source (wake's stale path, block size)
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


def pcm_from_capture_histories(frames: Any) -> tuple[np.ndarray, int]:
    """A recording's continuous mono PCM and its rate: every new publication's samples (``CaptureHistoryStream``) in
    order, the first history whole."""
    stream, pieces, rate = CaptureHistoryStream(), [], None
    for frame in frames:
        history = frame.capture_history
        if history is None:
            continue
        if rate is None:
            rate = int(history.sample_rate)
        elif int(history.sample_rate) != rate:
            raise ValueError("the recording changes its capture rate")
        pieces.extend(stream.blocks(history, frame.timestamp_us, 1 << 30))
    if not pieces:
        raise ValueError("the recording carries no native PCM")
    return np.concatenate(pieces).astype(np.float32), rate


class PacedPcmSource:
    """Recorded PCM on the audio clock, handed over at the cadence's own edges (module docstring).

    ``due(now, block, running=...)`` at each edge: the whole device blocks the audio clock has produced since the
    previous edge (``now`` is the edge's deadline timestamp, seconds), the remainder carried to the next edge; the
    stream loops at its end. Nothing is due, and the elapsed audio is dropped, while capture is closed or Media is not
    playing (``running`` False: a closed stream captures nothing, and paused playback produces no audio, so the
    playhead holds), and on the first edge after ``rebase`` (capture just (re)opened: audio before it was never
    captured, so an unpark or reopen delivers no burst for the closed gap). ``rebase`` may be called from any thread
    (the capture lane's open): it only raises a flag the next edge consumes.
    """

    def __init__(self, pcm: Any, sample_rate: int) -> None:
        self._pcm = np.ascontiguousarray(pcm, dtype=np.float32).reshape(-1)
        if not len(self._pcm):
            raise ValueError("a paced PCM source needs samples")
        self.sample_rate = int(sample_rate)
        self._cursor = 0
        self._owed = 0.0
        self._last: float | None = None
        self._rebase = True
        self.delivered_samples = 0          # handed over to the capture (by ``due``)
        self.paced_seconds = 0.0            # audio-clock time accounted while running
        self.edges = 0
        self.most_blocks = 0                # the most blocks one edge handed over (a late edge catches up)

    def rebase(self) -> None:
        self._rebase = True

    def due(self, now: float, block: int, *, running: bool) -> list[np.ndarray]:
        self.edges += 1
        block = max(1, int(block))
        if self._rebase or not running or self._last is None:
            self._rebase = False
            self._last, self._owed = float(now), 0.0
            return []
        elapsed = max(0.0, float(now) - self._last)
        self._last = float(now)
        self.paced_seconds += elapsed
        self._owed += elapsed * self.sample_rate
        count = int(self._owed // block)
        self._owed -= count * block
        self.most_blocks = max(self.most_blocks, count)
        blocks = [np.take(self._pcm, np.arange(self._cursor + k * block, self._cursor + (k + 1) * block),
                          mode="wrap") for k in range(count)]
        self._cursor = (self._cursor + count * block) % len(self._pcm)
        self.delivered_samples += count * block
        return blocks

    def describe(self) -> dict:
        return {"sample_rate": self.sample_rate, "edges": self.edges, "delivered_samples": self.delivered_samples,
                "delivered_s": self.delivered_samples / self.sample_rate, "paced_s": self.paced_seconds,
                "most_blocks_per_edge": self.most_blocks}


def synthesise_pause(frames: Any, *, at_s: float, pause_s: float, resume_frames: int = 2) -> tuple:
    """``frames`` (a recording's ``FeatureFrame``s) with Media paused for ``pause_s`` once ``at_s`` seconds have
    played, as the recorder would record it (P2b slice 2, the off-steady-state gate clips; audit H3).

    The recorder records the engine's waveform history each tick, and a paused engine consumes no capture, so every
    paused tick (``playing=False``, at the recording's own cadence) carries the last playing frame's history: no new
    publication. Then ``resume_frames`` playing ticks still carry it (capture reopening or warming up: the next
    publication lands after them), and the rest of the recording follows shifted by the inserted time (playback
    continues where it paused). Only the live-engine fields matter here (timestamp, playing, capture history)."""
    import dataclasses

    frames = tuple(frames)
    start = frames[0].timestamp_us
    head = [frame for frame in frames if frame.timestamp_us - start < at_s * 1e6]
    if not head or len(head) == len(frames):
        raise ValueError("the pause must start inside the recording")
    steps = np.diff([frame.timestamp_us for frame in frames])
    step = int(np.median(steps))
    last = head[-1]
    paused = max(1, round(pause_s * 1e6 / step))
    inserted = [dataclasses.replace(last, timestamp_us=last.timestamp_us + step * (k + 1), playing=k >= paused)
                for k in range(paused + max(0, int(resume_frames)))]
    shift = step * len(inserted)
    tail = [dataclasses.replace(frame, timestamp_us=frame.timestamp_us + shift) for frame in frames[len(head):]]
    return (*head, *inserted, *tail)


__all__ = ["CaptureHistoryStream", "PacedPcmSource", "RecordedCaptureBackend", "appended_sample_count",
           "pcm_from_capture_histories", "synthesise_pause"]
