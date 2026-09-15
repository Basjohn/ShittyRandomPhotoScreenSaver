"""Explicit low-observer-effect publication -> Quick -> draw frame trace.

This is deliberately *not* Python logging and is never enabled by diagnostic-all.
Only an explicit ``--frame-trace`` creates the fixed-size in-memory ring, writer
thread or binary sidecar.  Hot boundaries pack integer records into a preallocated
buffer; formatting and file I/O happen only on the dedicated below-normal writer.
"""

from __future__ import annotations

from enum import IntEnum
from pathlib import Path
import atexit
import os
import struct
import threading
import time
from typing import Final

from core.windows.thread_priority import apply_best_effort_thread_priority


class FrameTraceEvent(IntEnum):
    LOGICAL_PUBLISH = 1
    GUI_WAKE_DELIVER = 2
    GUI_SNAPSHOT_PUBLISH = 3
    QUICK_SYNC_CONSUME = 4
    RENDER_DRAW = 5
    FRAME_SWAP = 6
    QUICK_SYNC_READY = 7
    RENDER_BEGIN = 8
    RENDER_PREP_READY = 9
    RENDER_HOST_BEGIN = 10
    RENDER_GL_STATE_READY = 11
    RENDER_MODE_BEGIN = 12
    RENDER_MODE_READY = 13
    RENDER_HOST_READY = 14
    AUDIO_ANALYSIS_BEGIN = 15
    AUDIO_ANALYSIS_READY = 16
    AUDIO_SMOOTH_BEGIN = 17
    AUDIO_SMOOTH_READY = 18
    BACKGROUND_RENDER_BEGIN = 19
    BACKGROUND_TEXTURE_READY = 20
    BACKGROUND_DRAW_BEGIN = 21
    BACKGROUND_DRAW_READY = 22
    BACKGROUND_RENDER_READY = 23


_MAGIC: Final[bytes] = b"SRPSSFT1"
_VERSION: Final[int] = 1
_RECORD = struct.Struct("<QHhqqq")
_HEADER = struct.Struct("<8sHHI")
_DEFAULT_CAPACITY: Final[int] = 65_536
_BATCH_RECORDS: Final[int] = 256


class FrameTraceSink:
    """One bounded binary ring drained by one demoted writer thread.

    Producers never wait for disk.  A full ring drops the incoming diagnostic
    record and increments ``dropped`` rather than perturbing presentation.
    """

    __slots__ = (
        "_path", "_capacity", "_storage", "_lock", "_wake", "_closed",
        "_write_index", "_read_index", "_count", "_dropped", "_written",
        "_thread", "_file", "_priority_applied", "_priority_mode",
        "_native_priority", "_write_errors",
    )

    def __init__(self, path: Path, *, capacity: int = _DEFAULT_CAPACITY) -> None:
        self._path = Path(path)
        self._capacity = max(_BATCH_RECORDS * 2, int(capacity))
        self._storage = bytearray(self._capacity * _RECORD.size)
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._closed = False
        self._write_index = 0
        self._read_index = 0
        self._count = 0
        self._dropped = 0
        self._written = 0
        self._priority_applied = False
        self._priority_mode = "not_started"
        self._native_priority: int | None = None
        self._write_errors = 0

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open("wb", buffering=1024 * 1024)
        self._file.write(_HEADER.pack(_MAGIC, _VERSION, _RECORD.size, self._capacity))
        self._thread = threading.Thread(
            target=self._writer_loop,
            name="frame_trace_writer",
            daemon=True,
        )
        self._thread.start()

    @property
    def path(self) -> Path:
        return self._path

    def record(
        self,
        event: FrameTraceEvent | int,
        *,
        screen_index: int = -1,
        revision: int = -1,
        logical_timestamp_ns: int = 0,
        auxiliary: int = 0,
        timestamp_ns: int | None = None,
    ) -> bool:
        if self._closed:
            return False
        now_ns = time.perf_counter_ns() if timestamp_ns is None else int(timestamp_ns)
        # Hot trace producers are presentation observers, never authorities. If
        # the writer/describe path momentarily owns the ring metadata, drop this
        # diagnostic record instead of making logical/GUI/render threads wait.
        if not self._lock.acquire(blocking=False):
            self._dropped += 1
            return False
        try:
            if self._closed:
                return False
            if self._count >= self._capacity:
                self._dropped += 1
                return False
            offset = self._write_index * _RECORD.size
            _RECORD.pack_into(
                self._storage,
                offset,
                now_ns,
                int(event),
                int(screen_index),
                int(revision),
                int(logical_timestamp_ns),
                int(auxiliary),
            )
            self._write_index = (self._write_index + 1) % self._capacity
            self._count += 1
            should_wake = self._count >= _BATCH_RECORDS
        except (OverflowError, struct.error, TypeError, ValueError):
            self._dropped += 1
            return False
        finally:
            self._lock.release()
        if should_wake:
            self._wake.set()
        return True

    def describe(self) -> dict[str, object]:
        with self._lock:
            return {
                "enabled": not self._closed,
                "path": str(self._path),
                "capacity_records": self._capacity,
                "pending_records": self._count,
                "written_records": self._written,
                "dropped_records": self._dropped,
                "write_errors": self._write_errors,
                "writer_alive": self._thread.is_alive(),
                "priority_applied": self._priority_applied,
                "priority_mode": self._priority_mode,
                "native_priority": self._native_priority,
            }

    def close(self, *, timeout: float = 3.0) -> dict[str, object]:
        # Close is idempotent but must still finish the file-handle edge after a
        # writer-side failure (for example Windows priority admission failing).
        # Do not return early merely because the writer marked the sink closed.
        with self._lock:
            self._closed = True
        self._wake.set()
        self._thread.join(max(0.0, float(timeout)))
        # If the writer could not finish, do not block the application on it.
        if not self._thread.is_alive() and not self._file.closed:
            try:
                self._file.flush()
            finally:
                self._file.close()
        return self.describe()

    def _take_batch(self) -> bytes:
        with self._lock:
            available = self._count
            if available <= 0:
                return b""
            take = min(available, 4096)
            first = min(take, self._capacity - self._read_index)
            start = self._read_index * _RECORD.size
            middle = start + first * _RECORD.size
            if first == take:
                data = bytes(self._storage[start:middle])
            else:
                second = take - first
                data = bytes(self._storage[start:middle]) + bytes(
                    self._storage[: second * _RECORD.size]
                )
            self._read_index = (self._read_index + take) % self._capacity
            self._count -= take
        return data

    def _writer_loop(self) -> None:
        try:
            applied, mode, native_priority = apply_best_effort_thread_priority()
            with self._lock:
                self._priority_applied = bool(applied)
                self._priority_mode = str(mode)
                self._native_priority = native_priority
            # Unlike speculative CPU work, tracing may execute on non-Windows test
            # hosts. On Windows a failed demotion disables writes rather than letting
            # a diagnostic writer compete at normal interactive priority.
            if os.name == "nt" and not applied:
                with self._lock:
                    self._write_errors += 1
                    self._closed = True
                return

            while True:
                self._wake.wait()
                self._wake.clear()
                wrote_any = False
                while True:
                    data = self._take_batch()
                    if not data:
                        break
                    try:
                        self._file.write(data)
                        wrote_any = True
                        with self._lock:
                            self._written += len(data) // _RECORD.size
                    except Exception:
                        with self._lock:
                            self._write_errors += 1
                            self._closed = True
                        return

                # The trace exists to survive a bad/hung run. Flush each bounded
                # writer drain into the OS cache so an abnormal process exit loses
                # at most the not-yet-drained ring tail rather than Python's large
                # userspace file buffer as well. This work is confined to the
                # explicit, demoted diagnostic writer and never runs on producers.
                if wrote_any:
                    try:
                        self._file.flush()
                    except Exception:
                        with self._lock:
                            self._write_errors += 1
                            self._closed = True
                        return

                with self._lock:
                    if self._closed and self._count == 0:
                        return
        finally:
            # Writer owns its file-handle lifetime too. close() still joins with a
            # bounded timeout, but once this thread exits there is no orphaned file
            # handle even after writer-side priority/I/O failure.
            if not self._file.closed:
                try:
                    self._file.flush()
                except Exception:
                    with self._lock:
                        self._write_errors += 1
                try:
                    self._file.close()
                except Exception:
                    with self._lock:
                        self._write_errors += 1


_active_sink: FrameTraceSink | None = None
_active_lock = threading.Lock()


def frame_trace_requested(argv: list[str] | tuple[str, ...]) -> bool:
    return any(str(arg).strip().lower() == "--frame-trace" for arg in argv)


def start_frame_trace(log_dir: Path, argv: list[str] | tuple[str, ...]) -> FrameTraceSink | None:
    """Start only for explicit ``--frame-trace`` admission."""

    if not frame_trace_requested(argv):
        return None
    global _active_sink
    with _active_lock:
        if _active_sink is not None:
            return _active_sink
        sink = FrameTraceSink(Path(log_dir) / "screensaver_frame_trace.bin")
        _active_sink = sink
        return sink


def current_frame_trace() -> FrameTraceSink | None:
    """Return the admitted sink; ordinary runtime receives ``None``."""

    return _active_sink


def close_frame_trace() -> dict[str, object] | None:
    global _active_sink
    with _active_lock:
        sink, _active_sink = _active_sink, None
    if sink is None:
        return None
    return sink.close()


def logical_timestamp_ns(value: object) -> int:
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return 0
    if seconds <= 0.0:
        return 0
    return int(seconds * 1_000_000_000.0)


atexit.register(close_frame_trace)

__all__ = [
    "FrameTraceEvent",
    "FrameTraceSink",
    "close_frame_trace",
    "current_frame_trace",
    "frame_trace_requested",
    "logical_timestamp_ns",
    "start_frame_trace",
]
