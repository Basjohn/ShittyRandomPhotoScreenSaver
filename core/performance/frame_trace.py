"""Explicit low-observer-effect publication -> Quick -> draw frame trace.

This is deliberately *not* Python logging and is never enabled by diagnostic-all.
Only an explicit ``--frame-trace`` creates the fixed-size in-memory ring, writer
thread or binary sidecar.  Hot boundaries pack integer records into a preallocated
buffer; formatting and file I/O happen only on the dedicated below-normal writer.
The on-disk trace is a bounded rolling set of valid v1 segments so an explicitly
traced soak cannot grow without limit; all admitted event types remain present in
the retained window.
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
    CLIP_BEGIN_RESOURCES_READY = 24
    CLIP_BEGIN_INHERITED_READY = 25
    CLIP_BEGIN_SETUP_READY = 26
    CLIP_BEGIN_MASK_STATE_READY = 27
    CLIP_BEGIN_MASK_DRAW_READY = 28
    CLIP_BEGIN_MASK_RESTORE_READY = 29
    CLIP_END_SETUP_READY = 30
    CLIP_END_MASK_STATE_READY = 31
    CLIP_END_MASK_DRAW_READY = 32
    CLIP_END_MASK_RESTORE_READY = 33
    CLIP_END_INHERITED_READY = 34
    # CHK25 refined clip attribution. These remain explicit --frame-trace-only
    # sidecar events and preserve binary format/version 1.
    CLIP_BEGIN_INHERITED_SCISSOR_READY = 35
    CLIP_BEGIN_INHERITED_FRONT_READY = 36
    CLIP_BEGIN_MASK_BINDINGS_READY = 37
    CLIP_BEGIN_MASK_GL_STATE_APPLIED = 38
    CLIP_BEGIN_MASK_UNIFORMS_READY = 39
    CLIP_END_MASK_BINDINGS_READY = 40
    CLIP_END_MASK_GL_STATE_APPLIED = 41
    CLIP_END_MASK_UNIFORMS_READY = 42
    # CHK26 clipped-path state reuse: marks the extra render-host blend state
    # captured once at the first mask boundary and carried through begin/mode/end.
    CLIP_BEGIN_SHARED_GL_STATE_READY = 43
    # CHK27 GUI publication -> Qt Quick synchronization attribution. These are
    # explicit --frame-trace-only sidecar markers; ordinary runtime remains free
    # of timestamping/record work when no trace sink exists.
    GUI_PRESENTATION_COMMIT_READY = 44
    GUI_PRESENT_REQUEST_READY = 45
    QUICK_SYNC_ITEM_ENTRY = 46
    QUICK_SYNC_SNAPSHOT_ACQUIRED = 47
    # CHK28 Qt-native scenegraph phase attribution. These direct QQuickWindow
    # signal markers exist only for explicit --frame-trace and use a per-window
    # render-cycle sequence rather than visualizer logical revision identity.
    QUICK_BEFORE_FRAME_BEGIN = 48
    QUICK_BEFORE_SYNCHRONIZING = 49
    QUICK_AFTER_SYNCHRONIZING = 50
    QUICK_BEFORE_RENDERING = 51
    QUICK_BEFORE_RENDER_PASS_RECORDING = 52
    QUICK_AFTER_RENDER_PASS_RECORDING = 53
    QUICK_AFTER_RENDERING = 54
    # CHK29 Bubble render-body attribution. These remain explicit
    # --frame-trace-only deferred sidecar samples; they are timestamped in the
    # mode renderer and flushed only after the parent RENDER_DRAW marker.
    BUBBLE_LAYOUT_PAYLOAD_READY = 55
    BUBBLE_PROGRAM_READY = 56
    BUBBLE_COMMON_UNIFORMS_READY = 57
    BUBBLE_REACTIVE_UNIFORMS_READY = 58
    BUBBLE_STYLE_UNIFORMS_READY = 59
    BUBBLE_VAO_READY = 60
    BUBBLE_DRAW_READY = 61


_MAGIC: Final[bytes] = b"SRPSSFT1"
_VERSION: Final[int] = 1
_RECORD = struct.Struct("<QHhqqq")
_HEADER = struct.Struct("<8sHHI")
_DEFAULT_CAPACITY: Final[int] = 65_536
_BATCH_RECORDS: Final[int] = 256
# --frame-trace is intentionally high-density. Keep its disk footprint bounded
# for accidental/intentional soaks without thinning any event family. The base
# file is the newest segment; .1, .2, .3 are progressively older.
_DEFAULT_SEGMENT_BYTES: Final[int] = 32 * 1024 * 1024
_DEFAULT_RETAINED_SEGMENTS: Final[int] = 4


class FrameTraceSink:
    """One bounded binary ring drained by one demoted writer thread.

    Producers never wait for disk.  A full ring drops the incoming diagnostic
    record and increments ``dropped`` rather than perturbing presentation.
    """

    __slots__ = (
        "_path", "_capacity", "_storage", "_lock", "_wake", "_closed",
        "_write_index", "_read_index", "_count", "_dropped", "_written",
        "_thread", "_file", "_priority_applied", "_priority_mode",
        "_native_priority", "_write_errors", "_segment_bytes_limit",
        "_retained_segments", "_segment_bytes_written", "_rotations",
    )

    def __init__(
        self,
        path: Path,
        *,
        capacity: int = _DEFAULT_CAPACITY,
        segment_bytes: int = _DEFAULT_SEGMENT_BYTES,
        retained_segments: int = _DEFAULT_RETAINED_SEGMENTS,
    ) -> None:
        self._path = Path(path)
        self._capacity = max(_BATCH_RECORDS * 2, int(capacity))
        self._segment_bytes_limit = max(
            _HEADER.size + _RECORD.size, int(segment_bytes)
        )
        self._retained_segments = max(1, int(retained_segments))
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
        self._segment_bytes_written = 0
        self._rotations = 0

        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._clear_stale_segments()
        self._file = self._open_segment()
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
                "segment_bytes_limit": self._segment_bytes_limit,
                "retained_segments": self._retained_segments,
                "retained_bytes_limit": (
                    self._segment_bytes_limit * self._retained_segments
                ),
                "rotations": self._rotations,
                "priority_applied": self._priority_applied,
                "priority_mode": self._priority_mode,
                "native_priority": self._native_priority,
            }

    def _rotated_path(self, index: int) -> Path:
        return self._path.with_name(
            f"{self._path.stem}.{int(index)}{self._path.suffix}"
        )

    def _clear_stale_segments(self) -> None:
        """Remove only numeric rolling siblings left by an older traced run."""

        prefix = f"{self._path.stem}."
        suffix = self._path.suffix
        for candidate in self._path.parent.glob(f"{self._path.stem}.*{suffix}"):
            name = candidate.name
            if not name.startswith(prefix) or not name.endswith(suffix):
                continue
            middle = name[len(prefix): -len(suffix)] if suffix else name[len(prefix):]
            if middle.isdigit():
                try:
                    candidate.unlink()
                except FileNotFoundError:
                    pass

    def _open_segment(self):
        file = self._path.open("wb", buffering=1024 * 1024)
        header = _HEADER.pack(_MAGIC, _VERSION, _RECORD.size, self._capacity)
        file.write(header)
        self._segment_bytes_written = len(header)
        return file

    def _rotate_segment(self) -> None:
        """Roll the writer-owned file without involving any producer thread."""

        self._file.flush()
        self._file.close()
        if self._retained_segments <= 1:
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass
        else:
            oldest = self._rotated_path(self._retained_segments - 1)
            try:
                oldest.unlink()
            except FileNotFoundError:
                pass
            for index in range(self._retained_segments - 2, 0, -1):
                source = self._rotated_path(index)
                if source.exists():
                    source.replace(self._rotated_path(index + 1))
            if self._path.exists():
                self._path.replace(self._rotated_path(1))
        self._file = self._open_segment()
        self._rotations += 1

    def _write_trace_data(self, data: bytes) -> int:
        """Write record-aligned data across bounded rolling segments."""

        view = memoryview(data)
        written_records = 0
        while view:
            remaining_bytes = self._segment_bytes_limit - self._segment_bytes_written
            writable = (remaining_bytes // _RECORD.size) * _RECORD.size
            if writable <= 0:
                self._rotate_segment()
                continue
            take = min(len(view), writable)
            take -= take % _RECORD.size
            if take <= 0:
                self._rotate_segment()
                continue
            self._file.write(view[:take])
            self._segment_bytes_written += take
            written_records += take // _RECORD.size
            view = view[take:]
            if view:
                self._rotate_segment()
        return written_records

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
                        written_records = self._write_trace_data(data)
                        wrote_any = written_records > 0
                        with self._lock:
                            self._written += written_records
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
