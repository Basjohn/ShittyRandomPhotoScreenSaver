"""
Centralized logging configuration for screensaver application.

Uses rotating file handler with logs stored in logs/ directory.
Includes colored console output for debug mode.
"""
import atexit
import logging
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import traceback
from dataclasses import dataclass
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterable, Optional

from core.build_profile import is_compiled_runtime, is_diagnostic_build
from core.logging.tags import (
    KNOWN_LOG_FAMILIES,
    LOG_FAMILY_CACHE,
    LOG_FAMILY_FIELD,
    LOG_FAMILY_GEOMETRY,
    LOG_FAMILY_LIFECYCLE,
    LOG_FAMILY_PERF,
    LOG_FAMILY_SETTINGS,
    LOG_FAMILY_STEAM,
    LOG_FAMILY_USAGE,
    LOG_FAMILY_VISUALIZER,
    LOG_FAMILY_VISUALIZER_VOLUME,
    LOG_FAMILY_WIDGET_PERF,
    normalize_log_families,
)

_IS_FROZEN: bool = is_compiled_runtime()

_VERBOSE: bool = False
# PERF metrics default to False for production builds. Script mode and frozen
# builds opt in explicitly through CLI/config, not environment toggles.
_PERF_METRICS_ENABLED: bool = False
# Owner-local OpenGL timer queries cross into the driver and are deliberately
# separated from ordinary PERF telemetry.  ``--gpu-timing`` implies PERF logs,
# but ``--perf`` alone must remain free of query polling/begin/end overhead.
_GPU_TIMING_ENABLED: bool = False
_USAGE_LOGGING_ENABLED: bool = False
# Widget PERF verbosity flag controls whether per-call summaries land in main log
_WIDGET_PERF_VERBOSE: bool = False
# Visualizer logging defaults to False (opt-in via --viz). When enabled, logs
# [SPOTIFY_VIS] and [SPOTIFY_VOL] detailed metrics.
_VIZ_LOGGING_ENABLED: bool = False
# Spotify visualizer diagnostics flag (high-volume DSP traces)
_VIZ_DIAGNOSTICS_ENABLED: bool = False
_GEOMETRY_LOGGING_ENABLED: bool = False
_SETTINGS_LOGGING_ENABLED: bool = False
_LIFECYCLE_LOGGING_ENABLED: bool = False
_CACHE_LOGGING_ENABLED: bool = False
_STEAM_LOGGING_ENABLED: bool = False
# Logging defaults to disabled for frozen builds unless explicitly enabled via
# the general logging config file next to the executable.
_LOGGING_DISABLED: bool = _IS_FROZEN
# Base directory for logs and related artefacts. This is initialised to the
# project root by default and updated by setup_logging() for frozen builds so
# helpers like get_log_dir() always point at the effective runtime location.
_BASE_DIR: Path = Path(__file__).parent.parent.parent
_FORCED_LOG_DIR: Path | None = None
_ACTIVE_LOG_DIR: Path | None = None

# Ordinary logging is process-owned rather than tied to a recreatable runtime
# generation. Caller threads only snapshot/enqueue records; one writer owns
# filtering, formatting, rotation and normal file output.
_LOG_QUEUE_CAPACITY = 4096
_LOG_FLUSH_TIMEOUT_SECONDS = 3.0
_ACTIVE_LOGGING_CONTROLLER = None
_ACTIVE_CLOSING_WARNING_HANDLER = None
_LOGGING_CONTROLLER_LOCK = threading.RLock()
_LOGGING_LIFECYCLE_LOCK = threading.RLock()


def _safe_log_text(value: object) -> str:
    try:
        return str(value)
    except Exception:
        return f"<{type(value).__name__}>"


def _notify_handler_error(handler: logging.Handler) -> None:
    callback = getattr(handler, "_srpss_error_callback", None)
    if not callable(callback):
        return
    try:
        callback()
    except Exception:
        pass


def _snapshot_log_value(value: Any, *, depth: int = 0) -> Any:
    """Detach common mutable/Qt values without formatting the whole message."""

    if value is None or isinstance(value, (str, bytes, bool, int, float, complex)):
        return value
    if depth >= 6:
        return _safe_log_text(value)
    if isinstance(value, tuple):
        return tuple(_snapshot_log_value(item, depth=depth + 1) for item in value)
    if isinstance(value, list):
        return [_snapshot_log_value(item, depth=depth + 1) for item in value]
    if isinstance(value, dict):
        return {
            _snapshot_log_value(key, depth=depth + 1): _snapshot_log_value(
                item,
                depth=depth + 1,
            )
            for key, item in value.items()
        }
    if isinstance(value, set):
        return {_snapshot_log_value(item, depth=depth + 1) for item in value}
    if isinstance(value, frozenset):
        return frozenset(
            _snapshot_log_value(item, depth=depth + 1) for item in value
        )
    if isinstance(value, Path):
        return str(value)
    return _safe_log_text(value)


def _snapshot_log_record(record: logging.LogRecord) -> logging.LogRecord:
    """Copy a record for deferred formatting without retaining traceback frames."""

    state = {
        key: _snapshot_log_value(value)
        for key, value in record.__dict__.items()
        if key not in {"args", "exc_info", "exc_text", "message", "msg"}
    }
    state["msg"] = _snapshot_log_value(record.msg)
    state["args"] = _snapshot_log_value(record.args)
    state["exc_info"] = None
    exc_text = getattr(record, "exc_text", None)
    traceback_snapshot = None
    if record.exc_info and not exc_text:
        try:
            traceback_snapshot = traceback.TracebackException(
                *record.exc_info,
                lookup_lines=False,
                capture_locals=False,
                compact=True,
            )
        except Exception:
            exc_text = "<exception formatting failed>"
    state["exc_text"] = _snapshot_log_value(exc_text)
    state["_srpss_traceback"] = traceback_snapshot
    state["_srpss_queue_enqueued_ns"] = time.perf_counter_ns()
    return logging.makeLogRecord(state)


def _render_queued_exception(record: logging.LogRecord) -> None:
    """Render a detached traceback snapshot on the writer thread."""

    snapshot = getattr(record, "_srpss_traceback", None)
    if snapshot is None or getattr(record, "exc_text", None):
        return
    try:
        record.exc_text = "".join(snapshot.format()).rstrip()
    except Exception:
        record.exc_text = "<exception formatting failed>"
    finally:
        try:
            delattr(record, "_srpss_traceback")
        except Exception:
            pass


class _QueuedLogHandler(logging.Handler):
    """Producer-facing handler; routing and formatting stay behind the queue."""

    def __init__(self, controller: "_QueuedLoggingController") -> None:
        super().__init__(logging.NOTSET)
        self._controller = controller

    def emit(self, record: logging.LogRecord) -> None:
        self._controller.enqueue(record)


class _ClosingWarningHandler(logging.Handler):
    """Keep WARNING+ main-visible after ordinary queue shutdown handoff."""

    def __init__(self, controller: "_QueuedLoggingController") -> None:
        super().__init__(logging.WARNING)
        self.controller = controller

    def emit(self, record: logging.LogRecord) -> None:
        self.controller._emergency_emit(record, allow_reopen=True)

    def close(self) -> None:
        try:
            self.controller.close_emergency_output()
        finally:
            super().close()


class _QueuedLoggingController:
    """Bounded process-lifetime queue with one ordinary-log writer."""

    def __init__(
        self,
        output_handlers: Iterable[logging.Handler],
        *,
        main_handler: logging.Handler,
        console_handler: logging.Handler | None = None,
        capacity: int,
    ) -> None:
        self.output_handlers = tuple(output_handlers)
        self.main_handler = main_handler
        self.console_handler = console_handler
        self.capacity = max(1, int(capacity))
        self.ingress_handler = _QueuedLogHandler(self)
        self._queue: queue.Queue[logging.LogRecord] = queue.Queue(
            maxsize=self.capacity
        )
        self._accept_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._dispatch_lock = threading.RLock()
        self._metrics_lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._finalize_allowed = threading.Event()
        self._closed_event = threading.Event()
        self._dispatch_state = threading.local()
        self._accepting = True
        self._outputs_closed = False
        self._flush_started_ns = 0
        self._flush_duration_ns = 0
        self._flush_timed_out = False
        self._enqueued = 0
        self._dequeued = 0
        self._dropped_debug = 0
        self._dropped_info = 0
        self._dropped_other_low = 0
        self._emergency_attempts = 0
        self._emergency_writes = 0
        self._emergency_stderr_fallbacks = 0
        self._reentry_fallbacks = 0
        self._snapshot_errors = 0
        self._writer_errors = 0
        self._queue_high_water = 0
        self._caller_records = 0
        self._caller_total_ns = 0
        self._caller_max_ns = 0
        self._writer_lag_records = 0
        self._writer_lag_total_ns = 0
        self._writer_lag_max_ns = 0
        self._file_commit_lag_records = 0
        self._file_commit_lag_total_ns = 0
        self._file_commit_lag_max_ns = 0
        self._console_emit_records = 0
        self._console_emit_total_ns = 0
        self._console_emit_max_ns = 0
        self._thread = threading.Thread(
            target=self._run,
            name="SRPSSLogWriter",
            daemon=True,
        )
        for handler in self.output_handlers:
            try:
                setattr(
                    handler,
                    "_srpss_error_callback",
                    self._record_writer_error,
                )
            except Exception:
                pass
        self._thread.start()

    @property
    def writer_thread(self) -> threading.Thread:
        return self._thread

    def enqueue(self, source_record: logging.LogRecord) -> None:
        started_ns = time.perf_counter_ns()
        try:
            if bool(getattr(self._dispatch_state, "in_dispatch", False)):
                self._reentry_fallback(source_record)
                return
            try:
                record = _snapshot_log_record(source_record)
            except Exception:
                with self._metrics_lock:
                    self._snapshot_errors += 1
                if source_record.levelno >= logging.WARNING:
                    self._emergency_emit(
                        source_record,
                        allow_reopen=self._stop_requested.is_set(),
                    )
                else:
                    self._record_low_priority_drop(source_record.levelno)
                return

            emergency = False
            emergency_allow_reopen = False
            drop_level: int | None = None
            with self._accept_lock:
                if not self._accepting:
                    if record.levelno >= logging.WARNING:
                        emergency = True
                        emergency_allow_reopen = True
                    else:
                        drop_level = record.levelno
                else:
                    try:
                        self._queue.put_nowait(record)
                    except queue.Full:
                        if record.levelno >= logging.WARNING:
                            emergency = True
                        else:
                            drop_level = record.levelno
                    else:
                        depth = self._queue.qsize()
                        with self._metrics_lock:
                            self._enqueued += 1
                            self._queue_high_water = max(
                                self._queue_high_water,
                                depth,
                            )
            if emergency:
                # Saturation/closing is an exceptional direct path. The
                # dispatch lock serializes it with writer-owned rotation.
                self._emergency_emit(
                    record,
                    allow_reopen=emergency_allow_reopen,
                )
            elif drop_level is not None:
                self._record_low_priority_drop(drop_level)
        finally:
            elapsed_ns = max(0, time.perf_counter_ns() - started_ns)
            with self._metrics_lock:
                self._caller_records += 1
                self._caller_total_ns += elapsed_ns
                self._caller_max_ns = max(self._caller_max_ns, elapsed_ns)

    def _record_low_priority_drop(self, levelno: int) -> None:
        with self._metrics_lock:
            if levelno <= logging.DEBUG:
                self._dropped_debug += 1
            elif levelno <= logging.INFO:
                self._dropped_info += 1
            else:
                self._dropped_other_low += 1

    def _record_writer_error(self) -> None:
        with self._metrics_lock:
            self._writer_errors += 1

    def _direct_stderr(self, prefix: str, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:
            message = _safe_log_text(getattr(record, "msg", "<unavailable>"))
        message = message[:2000]
        try:
            sys.__stderr__.write(f"{prefix}{message}\n")
            sys.__stderr__.flush()
        except Exception:
            pass

    def _reentry_fallback(self, record: logging.LogRecord) -> None:
        with self._metrics_lock:
            self._reentry_fallbacks += 1
        self._direct_stderr("SRPSS logging reentry: ", record)

    def _emergency_emit(
        self,
        record: logging.LogRecord,
        *,
        allow_reopen: bool = False,
    ) -> None:
        with self._metrics_lock:
            self._emergency_attempts += 1
        if bool(getattr(self._dispatch_state, "in_dispatch", False)):
            self._reentry_fallback(record)
            return
        previous_dispatch = bool(
            getattr(self._dispatch_state, "in_dispatch", False)
        )
        self._dispatch_state.in_dispatch = True
        emitted = False
        should_fallback = False
        try:
            _render_queued_exception(record)
            with self._dispatch_lock:
                if self._outputs_closed and not allow_reopen:
                    raise RuntimeError("logging outputs already closed")
                with self._metrics_lock:
                    errors_before = self._writer_errors
                if record.levelno >= self.main_handler.level:
                    self.main_handler.handle(record)
                    with self._metrics_lock:
                        emitted = self._writer_errors == errors_before
                    should_fallback = not emitted
        except Exception:
            should_fallback = True
        finally:
            self._dispatch_state.in_dispatch = previous_dispatch
        if should_fallback:
            with self._metrics_lock:
                self._emergency_stderr_fallbacks += 1
            self._direct_stderr("SRPSS emergency log: ", record)
        if emitted:
            with self._metrics_lock:
                self._emergency_writes += 1

    def close_emergency_output(self) -> None:
        """Close a main handler that a late closing warning may have reopened."""

        with self._dispatch_lock:
            try:
                self.main_handler.flush()
            except Exception:
                self._record_writer_error()
            try:
                self.main_handler.close()
            except Exception:
                self._record_writer_error()
            try:
                setattr(self.main_handler, "_srpss_error_callback", None)
            except Exception:
                pass

    def _dispatch_record(
        self,
        record: logging.LogRecord,
        *,
        count_record: bool = True,
        measure_lag: bool = True,
    ) -> None:
        _render_queued_exception(record)
        enqueued_ns = 0
        if measure_lag:
            enqueued_ns = int(
                getattr(record, "_srpss_queue_enqueued_ns", 0) or 0
            )
            if enqueued_ns:
                lag_ns = max(0, time.perf_counter_ns() - enqueued_ns)
                with self._metrics_lock:
                    self._writer_lag_records += 1
                    self._writer_lag_total_ns += lag_ns
                    self._writer_lag_max_ns = max(
                        self._writer_lag_max_ns,
                        lag_ns,
                    )

        previous_dispatch = bool(
            getattr(self._dispatch_state, "in_dispatch", False)
        )
        self._dispatch_state.in_dispatch = True
        try:
            with self._dispatch_lock:
                # Persistent outputs always go first. This means expensive
                # human console formatting/output cannot postpone main/sidecar
                # visibility for the record currently being dispatched.
                for handler in self.output_handlers:
                    if handler is self.console_handler:
                        continue
                    if record.levelno < handler.level:
                        continue
                    try:
                        handler.handle(record)
                    except Exception:
                        self._record_writer_error()

                if enqueued_ns:
                    file_commit_lag_ns = max(
                        0,
                        time.perf_counter_ns() - enqueued_ns,
                    )
                    with self._metrics_lock:
                        self._file_commit_lag_records += 1
                        self._file_commit_lag_total_ns += file_commit_lag_ns
                        self._file_commit_lag_max_ns = max(
                            self._file_commit_lag_max_ns,
                            file_commit_lag_ns,
                        )

                if (
                    self.console_handler is not None
                    and record.levelno >= self.console_handler.level
                ):
                    console_started_ns = time.perf_counter_ns()
                    try:
                        self.console_handler.handle(record)
                    except Exception:
                        self._record_writer_error()
                    finally:
                        console_elapsed_ns = max(
                            0,
                            time.perf_counter_ns() - console_started_ns,
                        )
                        with self._metrics_lock:
                            self._console_emit_records += 1
                            self._console_emit_total_ns += console_elapsed_ns
                            self._console_emit_max_ns = max(
                                self._console_emit_max_ns,
                                console_elapsed_ns,
                            )
        finally:
            self._dispatch_state.in_dispatch = previous_dispatch
        if count_record:
            with self._metrics_lock:
                self._dequeued += 1

    def _run(self) -> None:
        try:
            while True:
                if self._stop_requested.is_set() and self._queue.empty():
                    break
                try:
                    record = self._queue.get(timeout=0.05)
                except queue.Empty:
                    continue
                try:
                    self._dispatch_record(record)
                finally:
                    self._queue.task_done()
        finally:
            self._finalize_allowed.wait()
            self._finalize_outputs()

    def _finalize_outputs(self) -> None:
        drain_ns = 0
        if self._flush_started_ns:
            drain_ns = max(0, time.perf_counter_ns() - self._flush_started_ns)
        with self._metrics_lock:
            self._flush_duration_ns = drain_ns
        metrics = self.metrics()
        caller_avg_ms = (
            metrics["caller_enqueue_total_ms"] / metrics["caller_records"]
            if metrics["caller_records"]
            else 0.0
        )
        writer_avg_ms = (
            metrics["writer_lag_total_ms"] / metrics["writer_lag_records"]
            if metrics["writer_lag_records"]
            else 0.0
        )
        file_commit_avg_ms = (
            metrics["file_commit_lag_total_ms"] / metrics["file_commit_lag_records"]
            if metrics["file_commit_lag_records"]
            else 0.0
        )
        console_emit_avg_ms = (
            metrics["console_emit_total_ms"] / metrics["console_emit_records"]
            if metrics["console_emit_records"]
            else 0.0
        )
        summary = logging.LogRecord(
            "core.logging.writer",
            logging.INFO,
            __file__,
            0,
            (
                "[LOG_QUEUE] final enqueued=%d dequeued=%d "
                "dropped_debug=%d dropped_info=%d dropped_other_low=%d "
                "emergency_attempts=%d emergency_main_writes=%d "
                "emergency_stderr_fallbacks=%d reentry_fallbacks=%d "
                "snapshot_errors=%d writer_errors=%d "
                "high_water=%d capacity=%d caller_avg_ms=%.4f "
                "caller_max_ms=%.4f writer_lag_avg_ms=%.4f "
                "writer_lag_max_ms=%.4f file_commit_lag_avg_ms=%.4f "
                "file_commit_lag_max_ms=%.4f console_emit_avg_ms=%.4f "
                "console_emit_max_ms=%.4f flush_ms=%.3f"
            ),
            (
                metrics["enqueued"],
                metrics["dequeued"],
                metrics["dropped_debug"],
                metrics["dropped_info"],
                metrics["dropped_other_low"],
                metrics["emergency_attempts"],
                metrics["emergency_writes"],
                metrics["emergency_stderr_fallbacks"],
                metrics["reentry_fallbacks"],
                metrics["snapshot_errors"],
                metrics["writer_errors"],
                metrics["queue_high_water"],
                metrics["capacity"],
                caller_avg_ms,
                metrics["caller_enqueue_max_ms"],
                writer_avg_ms,
                metrics["writer_lag_max_ms"],
                file_commit_avg_ms,
                metrics["file_commit_lag_max_ms"],
                console_emit_avg_ms,
                metrics["console_emit_max_ms"],
                metrics["flush_duration_ms"],
            ),
            None,
        )
        try:
            self._dispatch_record(
                summary,
                count_record=False,
                measure_lag=False,
            )
        finally:
            with self._dispatch_lock:
                for handler in self.output_handlers:
                    try:
                        handler.flush()
                    except Exception:
                        self._record_writer_error()
                for handler in self.output_handlers:
                    try:
                        handler.close()
                    except Exception:
                        self._record_writer_error()
                self._outputs_closed = True
            if self._flush_started_ns:
                with self._metrics_lock:
                    self._flush_duration_ns = max(
                        0,
                        time.perf_counter_ns() - self._flush_started_ns,
                    )
            self._closed_event.set()

    def begin_close(self) -> None:
        """Stop queue admission without waiting behind output I/O."""

        with self._close_lock:
            if not self._stop_requested.is_set():
                with self._accept_lock:
                    self._accepting = False
                    self._flush_started_ns = time.perf_counter_ns()
                    self._stop_requested.set()

    def allow_finalize(self) -> None:
        """Permit the drained writer to emit its summary and close outputs."""

        self._finalize_allowed.set()

    def wait_closed(
        self,
        timeout_seconds: float,
    ) -> dict[str, int | float | bool]:
        timeout = max(0.0, float(timeout_seconds))
        closed = self._closed_event.wait(timeout)
        if not closed:
            with self._metrics_lock:
                self._flush_timed_out = True
                if self._flush_started_ns:
                    self._flush_duration_ns = max(
                        0,
                        time.perf_counter_ns() - self._flush_started_ns,
                    )
        elif threading.current_thread() is not self._thread:
            self._thread.join(timeout=0.1)
        return self.metrics()

    def close(self, timeout_seconds: float) -> dict[str, int | float | bool]:
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        self.begin_close()
        self.allow_finalize()
        if threading.current_thread() is self._thread:
            return self.metrics()
        metrics = self.wait_closed(max(0.0, deadline - time.monotonic()))
        if not metrics["active"]:
            self.close_emergency_output()
            metrics = self.metrics()
        return metrics

    def flush(self, timeout_seconds: float) -> bool:
        """Wait for currently accepted records and flush outputs without stopping."""

        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        with self._queue.all_tasks_done:
            while self._queue.unfinished_tasks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._queue.all_tasks_done.wait(remaining)
        return True

    def metrics(self) -> dict[str, int | float | bool]:
        with self._metrics_lock:
            return {
                "active": not self._closed_event.is_set(),
                "capacity": self.capacity,
                "queue_depth": self._queue.qsize(),
                "queue_high_water": self._queue_high_water,
                "enqueued": self._enqueued,
                "dequeued": self._dequeued,
                "dropped_debug": self._dropped_debug,
                "dropped_info": self._dropped_info,
                "dropped_other_low": self._dropped_other_low,
                "emergency_attempts": self._emergency_attempts,
                "emergency_writes": self._emergency_writes,
                "emergency_stderr_fallbacks": self._emergency_stderr_fallbacks,
                "reentry_fallbacks": self._reentry_fallbacks,
                "snapshot_errors": self._snapshot_errors,
                "writer_errors": self._writer_errors,
                "caller_records": self._caller_records,
                "caller_enqueue_total_ms": self._caller_total_ns / 1_000_000.0,
                "caller_enqueue_max_ms": self._caller_max_ns / 1_000_000.0,
                "writer_lag_records": self._writer_lag_records,
                "writer_lag_total_ms": self._writer_lag_total_ns / 1_000_000.0,
                "writer_lag_max_ms": self._writer_lag_max_ns / 1_000_000.0,
                "file_commit_lag_records": self._file_commit_lag_records,
                "file_commit_lag_total_ms": self._file_commit_lag_total_ns / 1_000_000.0,
                "file_commit_lag_max_ms": self._file_commit_lag_max_ns / 1_000_000.0,
                "console_emit_records": self._console_emit_records,
                "console_emit_total_ms": self._console_emit_total_ns / 1_000_000.0,
                "console_emit_max_ms": self._console_emit_max_ns / 1_000_000.0,
                "flush_duration_ms": self._flush_duration_ns / 1_000_000.0,
                "flush_timed_out": self._flush_timed_out,
                "writer_alive": self._thread.is_alive(),
            }


@dataclass(frozen=True)
class LoggingBootstrapProfile:
    """One startup decision for handlers and diagnostic runtime collectors."""

    debug: bool = False
    verbose: bool = False
    perf: bool = False
    gpu_timing: bool = False
    usage: bool = False
    viz: bool = False
    viz_diag: bool = False
    geo: bool = False
    settings_trace: bool = False
    lifecycle: bool = False
    cache_trace: bool = False
    steam_trace: bool = False


def resolve_logging_bootstrap_profile(
    argv: Iterable[str],
    *,
    diagnostic_build: bool = False,
) -> LoggingBootstrapProfile:
    """Resolve CLI logging switches or the dedicated diagnostic-all policy."""

    args = {str(arg).strip().lower() for arg in argv}
    if diagnostic_build:
        return LoggingBootstrapProfile(
            debug=True,
            verbose=True,
            perf=True,
            gpu_timing=True,
            usage=True,
            viz=True,
            viz_diag=True,
            geo=True,
            settings_trace=True,
            lifecycle=True,
            cache_trace=True,
            steam_trace=True,
        )
    viz = "--viz" in args
    gpu_timing = "--gpu-timing" in args
    return LoggingBootstrapProfile(
        debug="--debug" in args or "-d" in args,
        verbose="--verbose" in args or "-v" in args,
        perf="--perf" in args or gpu_timing,
        gpu_timing=gpu_timing,
        usage="--usage" in args,
        viz=viz,
        viz_diag=viz or "--viz-diagnostics" in args or "--viz-diag" in args,
        geo="--geo" in args,
        settings_trace="--set" in args,
        lifecycle="--life" in args,
        cache_trace="--cache" in args,
        steam_trace="--steam" in args,
    )

def _parse_bool_token(value: Optional[str]) -> Optional[bool]:
    """Parse a string token into a boolean or None if indeterminate."""
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "on", "yes", "enable", "enabled"}:
        return True
    if lowered in {"0", "false", "off", "no", "disable", "disabled"}:
        return False
    return None


def _read_bool_flag_file(path: Path) -> Optional[bool]:
    """Read a boolean flag from the given path."""
    try:
        if not path.exists():
            return None
        raw = path.read_text(encoding="utf-8").strip()
        return _parse_bool_token(raw)
    except Exception:
        return None


_env_widget_perf_verbose = os.getenv("SRPSS_WIDGET_PERF_VERBOSE")
if _env_widget_perf_verbose is not None:
    try:
        parsed = _parse_bool_token(str(_env_widget_perf_verbose))
        if parsed is not None:
            _WIDGET_PERF_VERBOSE = parsed
    except Exception:
        pass

_env_log_dir = os.getenv("SRPSS_FORCE_LOG_DIR")
if _env_log_dir:
    try:
        candidate = Path(_env_log_dir).expanduser()
        if not candidate.is_absolute():
            candidate = candidate.resolve()
        _FORCED_LOG_DIR = candidate
    except Exception:
        _FORCED_LOG_DIR = None


def _determine_logging_disabled(exe_path: Path | None) -> bool:
    """Decide whether logging should be disabled for this runtime."""
    logging_disabled = _LOGGING_DISABLED

    if exe_path:
        if not logging_disabled:
            # Frozen builds default to logging disabled unless explicitly re-enabled.
            logging_disabled = True
        logging_cfg = exe_path.parent / f"{exe_path.stem}.logging.cfg"
        cfg_value = _read_bool_flag_file(logging_cfg)
        if cfg_value is not None:
            # File stores "1" to enable logging, "0" to disable.
            logging_disabled = not cfg_value

    env_disable = _parse_bool_token(os.getenv("SRPSS_DISABLE_LOGS"))
    if env_disable is True:
        logging_disabled = True
    elif env_disable is False:
        logging_disabled = False

    env_force = _parse_bool_token(os.getenv("SRPSS_FORCE_LOGS"))
    if env_force is True:
        logging_disabled = False

    return logging_disabled


class ColoredFormatter(logging.Formatter):
    """Comprehensive human-facing console formatter for debug mode.

    Goals:
      * the terminal owns no accidental wrapping;
      * metadata columns remain fixed on every continuation row;
      * structured key/value telemetry is presented as aligned tables;
      * long values receive full-width rows rather than destroying the grid;
      * WARNING+ records use heavier diagnostic cards and named sections;
      * source names cannot push the message column sideways;
      * the underlying LogRecord payload is never mutated.

    This class is console presentation only. File persistence, sidecars,
    queueing, rotation, emergency WARNING+ writes and Diagnostic crash capture
    remain independent of it.
    """

    COLORS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    SOURCE_COLOR = "\033[38;5;75m"
    TAG_COLOR = "\033[38;5;141m"
    KEY_COLOR = "\033[38;5;110m"
    VALUE_COLOR = "\033[97m"
    LABEL_COLOR = "\033[38;5;75m"
    PROSE_COLOR = "\033[97m"
    DIM = "\033[2m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    _TIME_WIDTH = 8
    _LEVEL_WIDTH = 8
    _SOURCE_WIDTH = 46
    _MIN_CONSOLE_WIDTH = 112
    _DEFAULT_CONSOLE_WIDTH = 144
    _MAX_CONSOLE_WIDTH = 164
    _MIN_MESSAGE_WIDTH = 36

    _FRAME_GAP_SECTIONS = (
        (
            "FRAME",
            (
                "severity", "screen", "gap_ms", "paint_ms", "request_age_ms",
                "source_age_ms", "simulation_age_ms", "render_state_age_ms",
                "target_hz",
            ),
        ),
        (
            "STATE",
            (
                "transition_active", "transition", "vis_mode", "vis_phase",
                "waiting_engine", "waiting_frame", "bubble_worker", "bubble_result",
            ),
        ),
        (
            "WORK",
            (
                "io_queue", "compute_queue", "io_active", "compute_active",
                "io_callbacks", "compute_callbacks", "io_queue_wait_ms",
                "compute_queue_wait_ms", "io_exec_ms", "compute_exec_ms",
                "io_callback_ms", "compute_callback_ms",
            ),
        ),
        (
            "GUI",
            (
                "ui_callbacks", "ui_active", "ui_queue", "ui_failed",
                "last_ui", "last_ui_ms", "last_ui_age_ms",
            ),
        ),
        (
            "PRESENT",
            (
                "media_display", "media_emit", "media_repaints", "overlay_set",
                "overlay_repaints", "overlay_paints", "render_requests",
                "skipped_requests",
            ),
        ),
        ("GC", ("gc_enabled", "gc_counts")),
    )

    def __init__(self, *args, use_color: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_color = bool(use_color)

        # One terminal-size query at logger setup. We intentionally avoid doing
        # this on every record. Leave one spare visible column so PowerShell does
        # not soft-wrap exactly at the right edge.
        terminal_columns = shutil.get_terminal_size(
            fallback=(self._DEFAULT_CONSOLE_WIDTH, 30)
        ).columns
        self.console_width = max(
            self._MIN_CONSOLE_WIDTH,
            min(self._MAX_CONSOLE_WIDTH, int(terminal_columns) - 1),
        )
        self.prefix_width = (
            self._TIME_WIDTH
            + 3
            + self._LEVEL_WIDTH
            + 3
            + self._SOURCE_WIDTH
            + 3
        )
        self.message_width = max(
            self._MIN_MESSAGE_WIDTH,
            self.console_width - self.prefix_width,
        )
        self.card_width = self.console_width
        self.card_body_width = max(48, self.card_width - 4)

    def _paint(
        self,
        text: str,
        color: str = "",
        *,
        bold: bool = False,
        dim: bool = False,
    ) -> str:
        if not self.use_color:
            return text
        prefix = ""
        if bold:
            prefix += self.BOLD
        if dim:
            prefix += self.DIM
        prefix += color
        return f"{prefix}{text}{self.RESET}"

    @staticmethod
    def _split_canonical(rendered: str) -> tuple[str, str, str, str] | None:
        pieces = rendered.split(" - ", 3)
        if len(pieces) != 4:
            return None
        when, source, level, payload = pieces
        return when.strip(), source.strip(), level.strip(), payload

    @staticmethod
    def _is_separator_message(message: str) -> bool:
        stripped = message.strip()
        return len(stripped) >= 20 and set(stripped) == {"="}

    @staticmethod
    def _tag_prefix(payload: str) -> tuple[str, str]:
        cursor = 0
        tags: list[str] = []
        length = len(payload)
        while cursor < length:
            while cursor < length and payload[cursor].isspace():
                cursor += 1
            if cursor >= length or payload[cursor] != "[":
                break
            end = payload.find("]", cursor + 1)
            if end < 0:
                break
            tags.append(payload[cursor : end + 1])
            cursor = end + 1
        return "".join(tags), payload[cursor:].lstrip()

    @staticmethod
    def _field_key(token: str) -> str | None:
        if "=" not in token:
            return None
        key, _value = token.split("=", 1)
        if not key:
            return None
        if not (key[0].isalpha() or key[0] == "_"):
            return None
        if not all(char.isalnum() or char == "_" for char in key):
            return None
        return key

    @staticmethod
    def _field_parts(token: str) -> tuple[str, str] | None:
        if "=" not in token:
            return None
        key, value = token.split("=", 1)
        if not key:
            return None
        if not (key[0].isalpha() or key[0] == "_"):
            return None
        if not all(char.isalnum() or char == "_" for char in key):
            return None
        return key, value

    @staticmethod
    def _compact_source(source: str, width: int) -> str:
        """Fit a logger name without letting it move the message column."""

        if len(source) <= width:
            return source
        if width <= 5:
            return source[:width]
        # Preserve both hierarchy root and the useful leaf name.
        left = max(1, (width - 1) // 2)
        right = max(1, width - left - 1)
        return f"{source[:left]}…{source[-right:]}"

    @staticmethod
    def _wrap_words(words: list[str], width: int) -> list[list[str]]:
        target = max(12, int(width))
        rows: list[list[str]] = []
        current: list[str] = []
        current_len = 0

        for word in words:
            word_len = len(word)
            separator = 1 if current else 0
            if current and current_len + separator + word_len > target:
                rows.append(current)
                current = [word]
                current_len = word_len
            else:
                current.append(word)
                current_len += separator + word_len

        if current:
            rows.append(current)
        return rows or [[]]

    @staticmethod
    def _split_long_value(value: str, width: int) -> list[str]:
        """Wrap a long value at sensible punctuation before hard slicing."""

        if len(value) <= width:
            return [value]

        chunks: list[str] = []
        remaining = value
        preferred = ("/", "\\", ".", ":", ",", ";", "_", "-", ">")

        while len(remaining) > width:
            split_at = -1
            window = remaining[: width + 1]
            # Prefer a break late in the available window.
            for marker in preferred:
                candidate = window.rfind(marker, max(1, width // 2))
                if candidate > split_at:
                    split_at = candidate + 1
            if split_at <= 0:
                split_at = width
            chunks.append(remaining[:split_at])
            remaining = remaining[split_at:]
        if remaining:
            chunks.append(remaining)
        return chunks

    def _format_key(self, key: str, width: int) -> str:
        padded = f"{key:<{width}}"
        return self._paint(padded, self.KEY_COLOR)

    def _format_value(self, value: str) -> str:
        return self._paint(value, self.VALUE_COLOR)

    def _format_equals(self) -> str:
        return self._paint(" = ", dim=True)

    def _render_field_table(
        self,
        tokens: list[str],
        *,
        width: int,
        preferred_columns: int = 2,
    ) -> list[str]:
        """Render key=value tokens as a real aligned table.

        Pair short fields into two columns. Any field that cannot fit cleanly in
        one half-width cell is promoted to a full-width row. Long full-width
        values wrap underneath their own value column.
        """

        fields: list[tuple[str, str]] = []
        leftovers: list[str] = []
        for token in tokens:
            parts = self._field_parts(token)
            if parts is None:
                leftovers.append(token)
            else:
                fields.append(parts)

        lines: list[str] = []

        if leftovers:
            lines.extend(
                " ".join(row)
                for row in self._wrap_words(leftovers, width)
            )

        if not fields:
            return lines

        key_width = min(
            22,
            max(8, max(len(key) for key, _value in fields)),
        )
        gap = 4
        columns = 2 if preferred_columns >= 2 and width >= 70 else 1
        cell_width = (
            (width - gap) // 2
            if columns == 2
            else width
        )
        value_width_in_cell = max(
            8,
            cell_width - key_width - 3,
        )

        def pairable(field: tuple[str, str]) -> bool:
            key, value = field
            return (
                len(key) <= key_width
                and len(value) <= value_width_in_cell
            )

        pair_buffer: list[tuple[str, str]] = []

        def flush_pairs() -> None:
            nonlocal pair_buffer
            while pair_buffer:
                if columns == 2 and len(pair_buffer) >= 2:
                    left = pair_buffer.pop(0)
                    right = pair_buffer.pop(0)
                    left_text = (
                        self._format_key(left[0], key_width)
                        + self._format_equals()
                        + self._format_value(left[1])
                    )
                    # Pad by visible width, not ANSI byte length.
                    left_visible_len = key_width + 3 + len(left[1])
                    padding = max(1, cell_width - left_visible_len + gap)
                    right_text = (
                        self._format_key(right[0], key_width)
                        + self._format_equals()
                        + self._format_value(right[1])
                    )
                    lines.append(left_text + (" " * padding) + right_text)
                else:
                    field = pair_buffer.pop(0)
                    lines.extend(render_full(field))

        def render_full(field: tuple[str, str]) -> list[str]:
            key, value = field
            value_width = max(12, width - key_width - 3)
            value_chunks = self._split_long_value(value, value_width)
            rendered: list[str] = []
            for index, chunk in enumerate(value_chunks):
                if index == 0:
                    rendered.append(
                        self._format_key(key, key_width)
                        + self._format_equals()
                        + self._format_value(chunk)
                    )
                else:
                    rendered.append(
                        (" " * key_width)
                        + self._format_equals()
                        + self._format_value(chunk)
                    )
            return rendered

        for field in fields:
            if pairable(field):
                pair_buffer.append(field)
                if len(pair_buffer) == columns:
                    flush_pairs()
            else:
                flush_pairs()
                lines.extend(render_full(field))

        flush_pairs()
        return lines

    def _ordinary_prefix(
        self,
        when: str,
        level: str,
        source: str,
        *,
        continuation: bool,
    ) -> str:
        if continuation:
            plain = (
                f"{'':<{self._TIME_WIDTH}}"
                f" │ {'':<{self._LEVEL_WIDTH}}"
                f" │ {'':<{self._SOURCE_WIDTH}}"
                " │ "
            )
            return self._paint(plain, dim=True)

        compact_source = self._compact_source(source, self._SOURCE_WIDTH)
        level_color = self.COLORS.get(level, self.COLORS["INFO"])
        return (
            self._paint(f"{when:<{self._TIME_WIDTH}}", dim=True)
            + " │ "
            + self._paint(
                f"{level:<{self._LEVEL_WIDTH}}",
                level_color,
                bold=True,
            )
            + " │ "
            + self._paint(
                f"{compact_source:<{self._SOURCE_WIDTH}}",
                self.SOURCE_COLOR,
            )
            + " │ "
        )

    def _wrap_prose(self, text: str, width: int) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        return [" ".join(row) for row in self._wrap_words(words, width)]

    def _ordinary_message_lines(self, payload: str) -> list[str]:
        tags, rest = self._tag_prefix(payload)
        rows: list[str] = []

        logical_lines = rest.splitlines() if rest else []
        if not logical_lines and not tags:
            logical_lines = payload.splitlines() or [""]

        # Put a tag chain on its own row whenever there is meaningful payload
        # after it. This gives every structured record a visual heading.
        if tags:
            rows.append(self._paint(tags, self.TAG_COLOR, bold=True))

        for logical_line in logical_lines:
            stripped = logical_line.strip()
            if not stripped:
                rows.append("")
                continue

            tokens = stripped.split()
            first_field = next(
                (
                    index
                    for index, token in enumerate(tokens)
                    if self._field_key(token) is not None
                ),
                None,
            )

            if first_field is None:
                rows.extend(self._wrap_prose(stripped, self.message_width))
                continue

            prose_tokens = tokens[:first_field]
            field_tokens = tokens[first_field:]

            if prose_tokens:
                rows.extend(
                    self._wrap_prose(
                        " ".join(prose_tokens),
                        self.message_width,
                    )
                )

            rows.extend(
                self._render_field_table(
                    field_tokens,
                    width=self.message_width,
                    preferred_columns=2,
                )
            )

        # A tag-only event remains useful by itself.
        if tags and not logical_lines:
            return rows

        return rows or [""]

    def _ordinary_record(
        self,
        when: str,
        source: str,
        level: str,
        payload: str,
    ) -> str:
        rows = self._ordinary_message_lines(payload)
        first_prefix = self._ordinary_prefix(
            when,
            level,
            source,
            continuation=False,
        )
        continuation_prefix = self._ordinary_prefix(
            "",
            "",
            "",
            continuation=True,
        )
        return "\n".join(
            (first_prefix if index == 0 else continuation_prefix) + row
            for index, row in enumerate(rows)
        )

    def _frame_gap_body(self, payload: str) -> list[str]:
        tags, rest = self._tag_prefix(payload)
        ordered: list[tuple[str | None, str]] = []
        by_key: dict[str, str] = {}
        free_tokens: list[str] = []

        for token in rest.split():
            key = self._field_key(token)
            ordered.append((key, token))
            if key is None:
                free_tokens.append(token)
            else:
                by_key[key] = token

        consumed: set[str] = set()
        body: list[str] = []

        if tags:
            body.append(self._paint(tags, self.TAG_COLOR, bold=True))

        if free_tokens:
            body.extend(
                self._wrap_prose(
                    " ".join(free_tokens),
                    self.card_body_width,
                )
            )

        for label, keys in self._FRAME_GAP_SECTIONS:
            section_tokens = [by_key[key] for key in keys if key in by_key]
            consumed.update(key for key in keys if key in by_key)
            if not section_tokens:
                continue

            if body:
                body.append("")
            body.append(self._paint(label, self.LABEL_COLOR, bold=True))
            body.extend(
                self._render_field_table(
                    section_tokens,
                    width=self.card_body_width,
                    preferred_columns=2,
                )
            )

        leftovers = [
            token
            for key, token in ordered
            if key is not None and key not in consumed
        ]
        if leftovers:
            if body:
                body.append("")
            body.append(self._paint("OTHER", self.LABEL_COLOR, bold=True))
            body.extend(
                self._render_field_table(
                    leftovers,
                    width=self.card_body_width,
                    preferred_columns=2,
                )
            )

        return body or [payload]

    def _generic_severity_body(self, payload: str) -> list[str]:
        tags, rest = self._tag_prefix(payload)
        body: list[str] = []

        if tags:
            body.append(self._paint(tags, self.TAG_COLOR, bold=True))

        logical_lines = rest.splitlines() if rest else []
        if not logical_lines and not tags:
            logical_lines = payload.splitlines() or [""]

        for line_index, logical_line in enumerate(logical_lines):
            # Traceback continuations and explicitly indented lines should keep
            # their original visual structure rather than being tokenized into
            # telemetry fields.
            if line_index > 0 or logical_line[:1].isspace():
                raw = logical_line.rstrip()
                if len(raw) <= self.card_body_width:
                    body.append(raw)
                else:
                    body.extend(
                        self._split_long_value(
                            raw,
                            self.card_body_width,
                        )
                    )
                continue

            stripped = logical_line.strip()
            if not stripped:
                body.append("")
                continue

            tokens = stripped.split()
            first_field = next(
                (
                    index
                    for index, token in enumerate(tokens)
                    if self._field_key(token) is not None
                ),
                None,
            )

            if first_field is None:
                body.extend(
                    self._wrap_prose(
                        stripped,
                        self.card_body_width,
                    )
                )
                continue

            prose_tokens = tokens[:first_field]
            field_tokens = tokens[first_field:]
            if prose_tokens:
                body.extend(
                    self._wrap_prose(
                        " ".join(prose_tokens),
                        self.card_body_width,
                    )
                )
            body.extend(
                self._render_field_table(
                    field_tokens,
                    width=self.card_body_width,
                    preferred_columns=2,
                )
            )

        return body or [""]

    def _severity_card(
        self,
        record: logging.LogRecord,
        when: str,
        source: str,
        payload: str,
    ) -> str:
        level = str(record.levelname or "WARNING")
        color = self.COLORS.get(level, self.COLORS["WARNING"])

        if record.levelno >= logging.CRITICAL:
            icon, corners, rule = "☠", ("╔", "╠", "╚"), "═"
        elif record.levelno >= logging.ERROR:
            icon, corners, rule = "✖", ("╔", "╠", "╚"), "═"
        else:
            icon, corners, rule = "⚠", ("╭", "├", "╰"), "─"

        top_corner, middle_corner, bottom_corner = corners
        label_plain = f" {icon}  {level} "
        rule_count = max(8, self.card_width - len(label_plain) - 4)
        top_plain = f"{top_corner}{rule * 3}{label_plain}{rule * rule_count}"
        divider_plain = f"{middle_corner}{rule * (self.card_width - 1)}"
        bottom_plain = f"{bottom_corner}{rule * (self.card_width - 1)}"

        meta_source = self._compact_source(source, self.card_width - 24)
        meta = (
            f"│  {self._paint(when, dim=True)}"
            f"   {self._paint('·', dim=True)}   "
            f"{self._paint(meta_source, self.SOURCE_COLOR, bold=True)}"
        )

        if "[FRAME_GAP_OWNER]" in payload:
            body_lines = self._frame_gap_body(payload)
        else:
            body_lines = self._generic_severity_body(payload)

        body = "\n".join(
            "│  " + line if line else "│"
            for line in body_lines
        )

        return "\n".join(
            (
                self._paint(top_plain, color, bold=True),
                meta,
                self._paint(divider_plain, color),
                body,
                self._paint(bottom_plain, color),
            )
        )

    def _separator_rule(self) -> str:
        return self._paint(
            "━" * self.console_width,
            self.SOURCE_COLOR,
            bold=True,
        )

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        rendered = super().format(record)
        split = self._split_canonical(rendered)
        if split is None:
            return rendered

        when, source, level, payload = split

        if self._is_separator_message(record.getMessage()):
            return self._separator_rule()

        if record.levelno >= logging.WARNING:
            return self._severity_card(record, when, source, payload)

        return self._ordinary_record(when, source, level, payload)


class SpacedLogFormatter(logging.Formatter):
    """Formatter that inserts a blank line between records for scan-heavy logs."""

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        return super().format(record) + "\n"


class MainLogFormatter(logging.Formatter):
    """Polished human-facing formatter for ``screensaver.log`` only.

    The record's message text is never rewritten: SRPSS tags, key=value fields,
    warnings, exception text and traceback content remain intact. The formatter
    changes presentation only, on the writer-owned logging path.

    Dedicated PERF/usage/lifecycle/cache/visualizer/etc. sidecars continue using
    the ordinary canonical formatter and are therefore layout-compatible with
    the existing evidence parsers.
    """

    _RULE_WIDTH = 112
    _TIME_WIDTH = 19
    _LEVEL_WIDTH = 8
    _SOURCE_WIDTH = 30

    @staticmethod
    def _is_separator_message(message: str) -> bool:
        stripped = message.strip()
        return len(stripped) >= 20 and set(stripped) == {"="}

    @staticmethod
    def _severity_style(levelno: int) -> tuple[str, str, str, str, str]:
        if levelno >= logging.CRITICAL:
            return ("☠  CRITICAL", "╔", "╠", "╚", "═")
        if levelno >= logging.ERROR:
            return ("✖  ERROR", "╔", "╠", "╚", "═")
        return ("⚠  WARNING", "╭", "├", "╰", "─")

    def _split_canonical(self, rendered: str) -> tuple[str, str, str, str] | None:
        pieces = rendered.split(" - ", 3)
        if len(pieces) != 4:
            return None
        when, source, level, payload = pieces
        return when.strip(), source.strip(), level.strip(), payload

    @staticmethod
    def _indent_multiline(prefix: str, payload: str, continuation_prefix: str) -> str:
        lines = payload.splitlines() or [""]
        if len(lines) == 1:
            return prefix + lines[0]
        return "\n".join(
            [prefix + lines[0]]
            + [continuation_prefix + line for line in lines[1:]]
        )

    def _format_normal(
        self,
        when: str,
        source: str,
        level: str,
        payload: str,
    ) -> str:
        prefix = (
            f"{when:<{self._TIME_WIDTH}}"
            f" │ {level:<{self._LEVEL_WIDTH}}"
            f" │ {source:<{self._SOURCE_WIDTH}}"
            " │ "
        )
        continuation = (
            f"{'':<{self._TIME_WIDTH}}"
            f" │ {'':<{self._LEVEL_WIDTH}}"
            f" │ {'':<{self._SOURCE_WIDTH}}"
            " │ "
        )
        return self._indent_multiline(prefix, payload, continuation)

    def _format_severity(
        self,
        record: logging.LogRecord,
        when: str,
        source: str,
        payload: str,
    ) -> str:
        label, top_corner, middle_corner, bottom_corner, rule = self._severity_style(
            record.levelno
        )
        top_label = f" {label} "
        top_fill = max(8, self._RULE_WIDTH - len(top_label) - 1)
        top = f"{top_corner}{rule * 3}{top_label}{rule * top_fill}"

        meta = f"│  {when}   ·   {source}"
        divider = f"{middle_corner}{rule * (self._RULE_WIDTH - 1)}"

        payload_lines = payload.splitlines() or [""]
        body = "\n".join(f"│  {line}" for line in payload_lines)
        bottom = f"{bottom_corner}{rule * (self._RULE_WIDTH - 1)}"
        return f"{top}\n{meta}\n{divider}\n{body}\n{bottom}"

    def _format_startup_separator(self, when: str) -> str:
        # RotatingFileHandler may format the same record more than once while
        # deciding whether to roll over. Keep separator presentation stateless,
        # idempotent and deliberately low-noise.
        return "━" * self._RULE_WIDTH

    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        rendered = super().format(record)
        split = self._split_canonical(rendered)
        if split is None:
            return rendered

        when, source, level, payload = split

        if self._is_separator_message(record.getMessage()):
            return self._format_startup_separator(when)

        if record.levelno >= logging.WARNING:
            return self._format_severity(record, when, source, payload)

        return self._format_normal(when, source, level, payload)


class DeduplicatingRotatingFileHandler(RotatingFileHandler):
    """Rotating file handler that suppresses consecutive duplicate log lines.
    
    Thread-safe line-by-line deduplication for file logs. When consecutive
    identical messages are detected, they are collapsed with a count:
    "[N duplicates suppressed]"
    
    This significantly reduces log file size without losing information.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._lock = threading.Lock()
        self._last_message: str | None = None
        self._suppress_count: int = 0
        self._last_record: logging.LogRecord | None = None
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a record with deduplication."""
        try:
            # Get the formatted message
            msg_text = record.getMessage()
            
            with self._lock:
                # Always emit WARNING+ immediately
                if record.levelno >= logging.WARNING:
                    self._flush_suppression()
                    super().emit(record)
                    self._last_message = None
                    self._suppress_count = 0
                    self._last_record = None
                    return
                
                # First message or different from last
                if self._last_message is None or msg_text != self._last_message:
                    self._flush_suppression()
                    super().emit(record)
                    self._last_message = msg_text
                    self._suppress_count = 0
                    self._last_record = record
                else:
                    # Duplicate detected - increment counter
                    self._suppress_count += 1
                    if self._last_record is None:
                        self._last_record = record
        except Exception:
            _notify_handler_error(self)
            self.handleError(record)
    
    def _flush_suppression(self) -> None:
        """Flush any pending suppression count."""
        if self._suppress_count > 0 and self._last_record is not None:
            # Create a summary record
            msg = f"[{self._suppress_count} duplicates suppressed]"
            summary = logging.LogRecord(
                self._last_record.name,
                self._last_record.levelno,
                self._last_record.pathname,
                self._last_record.lineno,
                msg,
                args=None,
                exc_info=None,
            )
            summary.created = self._last_record.created
            summary.msecs = self._last_record.msecs
            summary.relativeCreated = self._last_record.relativeCreated
            summary.thread = self._last_record.thread
            summary.threadName = self._last_record.threadName
            summary.process = self._last_record.process
            summary.processName = self._last_record.processName
            
            # Emit the suppression summary
            super().emit(summary)
            
            self._suppress_count = 0
            self._last_record = None
    
    def close(self) -> None:
        """Close handler and flush any pending suppression."""
        try:
            with self._lock:
                self._flush_suppression()
        finally:
            super().close()


class SuppressingStreamHandler(logging.StreamHandler):
    """Stream handler that suppresses consecutive duplicate sources.

    Repeated DEBUG/INFO lines from the same logger/level are collapsed into a
    single summary line like "[N Suppressed: CHECK screensaver_verbose.log]"
    while file logs remain unaffected.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_name: str | None = None
        self._last_level: int | None = None
        self._last_message: str | None = None
        self._suppress_count: int = 0
        self._last_record: logging.LogRecord | None = None

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._emit_with_suppression(record)
        except Exception:
            _notify_handler_error(self)
            self.handleError(record)

    def _emit_with_suppression(self, record: logging.LogRecord) -> None:
        if record.levelno >= logging.WARNING:
            self._flush_summary()
            self._emit_record(record)
            self._last_name = None
            self._last_level = None
            self._last_message = None
            self._suppress_count = 0
            self._last_record = None
            return

        name = record.name
        level = record.levelno
        try:
            msg_text = record.getMessage()
        except Exception:
            msg_text = str(record.msg)

        if "🔴" in msg_text or "Initializing Screensaver Engine" in msg_text:
            self._flush_summary()
            self._emit_record(record)
            self._last_name = name
            self._last_level = level
            self._suppress_count = 0
            self._last_record = record
            return

        if self._last_name is None:
            self._emit_record(record)
            self._last_name = name
            self._last_level = level
            self._last_message = msg_text
            self._suppress_count = 0
            self._last_record = record
            return

        if name == self._last_name and level == self._last_level and msg_text == self._last_message:
            self._suppress_count += 1
            if self._last_record is None:
                self._last_record = record
            return

        self._flush_summary()
        self._emit_record(record)
        self._last_name = name
        self._last_level = level
        self._last_message = msg_text
        self._suppress_count = 0
        self._last_record = record

    def _emit_record(self, record: logging.LogRecord) -> None:
        """Emit a single record to the underlying stream with Unicode-safe fallback.

        File handlers always receive the original record; this handler is only
        responsible for console output. When the console encoding cannot represent
        some characters (e.g. Windows cp1252 vs arrows/emoji), we degrade the
        console line using replacement characters instead of raising a logging
        error while keeping file logs intact.
        """

        try:
            msg = self.format(record)
            stream = self.stream
            if stream is None:
                return
            text = msg + self.terminator
            try:
                stream.write(text)
            except UnicodeEncodeError:
                try:
                    encoding = getattr(stream, "encoding", None) or "ascii"
                    safe_text = text.encode(encoding, errors="replace").decode(
                        encoding, errors="replace"
                    )
                    stream.write(safe_text)
                except Exception:
                    # As a last resort, drop the console write; file logs still
                    # contain the full Unicode record.
                    return
            try:
                stream.flush()
            except Exception:
                # Ignore flush errors for console output.
                pass
        except Exception:
            _notify_handler_error(self)
            self.handleError(record)

    def _flush_summary(self) -> None:
        if self._suppress_count <= 0 or self._last_record is None:
            self._suppress_count = 0
            self._last_record = None
            self._last_message = None
            return

        last = self._last_record
        # Build a compact summary. For PERF lines that already contain
        # metrics like "avg_fps=78.5" we try to surface that token so
        # grouped telemetry is still somewhat informative in the console.
        avg_suffix = ""
        try:
            text = last.getMessage()
        except Exception:
            text = str(last.msg)
        if "[PERF]" in text and "avg_fps=" in text:
            try:
                idx = text.find("avg_fps=")
                if idx != -1:
                    # Take the avg_fps token up to the next comma or end.
                    tail = text[idx:].split(",", 1)[0].strip()
                    if tail:
                        avg_suffix = f", {tail}"
            except Exception:
                avg_suffix = ""

        msg = f"[{self._suppress_count} Suppressed: CHECK screensaver_verbose.log{avg_suffix}]"
        summary = logging.LogRecord(
            last.name,
            last.levelno,
            last.pathname,
            last.lineno,
            msg,
            args=None,
            exc_info=None,
        )
        summary.created = last.created
        summary.msecs = last.msecs
        summary.relativeCreated = last.relativeCreated
        summary.thread = last.thread
        summary.threadName = last.threadName
        summary.process = last.process
        summary.processName = last.processName
        # Use the same Unicode-safe path as ordinary console records so rich
        # box-drawing/ANSI presentation cannot turn suppression summaries into
        # logging errors on legacy Windows console encodings.
        self._emit_record(summary)

        self._suppress_count = 0
        self._last_record = None
        self._last_message = None

    def close(self) -> None:
        try:
            self._flush_summary()
        finally:
            super().close()


def _explicit_log_family_match(
    record: logging.LogRecord,
    *expected: str,
) -> bool | None:
    """Return a metadata match, or ``None`` for legacy/unclassified records."""

    families = normalize_log_families(getattr(record, LOG_FAMILY_FIELD, None))
    if not families:
        return None
    return any(family in expected for family in families)


class NonPerfFilter(logging.Filter):
    """Filter that drops dedicated PERF/USAGE records from the main log file.

    Detailed performance telemetry is already written to a dedicated
    ``screensaver_perf.log`` via PerfLogFilter, so the primary
    ``screensaver.log`` can omit those high-volume lines to keep logs
    smaller and more focused while preserving all metrics.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if record.levelno >= logging.WARNING:
            return True
        explicit = _explicit_log_family_match(
            record,
            LOG_FAMILY_PERF,
            LOG_FAMILY_USAGE,
        )
        if explicit is not None:
            return not explicit
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return "[PERF]" not in msg and "[USAGE]" not in msg


class NonSpotifyFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(
            record,
            LOG_FAMILY_VISUALIZER,
            LOG_FAMILY_VISUALIZER_VOLUME,
        )
        if explicit is not None:
            return not explicit
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return "[SPOTIFY_VIS]" not in msg and "[SPOTIFY_VOL]" not in msg


class GeometryLogFilter(logging.Filter):
    """Filter for geometry/z-order/CUSTOM-layout diagnostic records."""

    _NAME_PREFIXES = (
        "win_diag",
        "rendering.custom_layout_manager",
        "rendering.display_context_menu",
        "rendering.display_setup",
        "rendering.widget_manager",
        "rendering.widget_positioner",
        "widgets.base_overlay_widget",
    )
    _NAME_EXACT = {
        "rendering.display",
    }
    _MESSAGE_TOKENS = (
        "[CUSTOM_LAYOUT]",
        "[INPUT_GUARD]",
        "[MENU_OPEN]",
        "[ZORDER]",
        "[REFRESH_DIAG]",
    )

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(record, LOG_FAMILY_GEOMETRY)
        if explicit is not None:
            return explicit
        name = str(getattr(record, "name", "") or "")
        if name in self._NAME_EXACT or any(name.startswith(prefix) for prefix in self._NAME_PREFIXES):
            return True
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return any(token in msg for token in self._MESSAGE_TOKENS)


class SettingsLogFilter(logging.Filter):
    """Filter for settings mutation/import/schema diagnostics."""

    _NAME_PREFIXES = (
        "core.settings",
        "ui.tabs.settings_binding",
    )
    _NAME_EXACT = {
        "SettingsManager",
    }
    _MESSAGE_TOKENS = (
        "[SETTINGS]",
        "[SST]",
        "SettingsManager",
    )
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(record, LOG_FAMILY_SETTINGS)
        if explicit is not None:
            return explicit
        name = str(getattr(record, "name", "") or "")
        if name in self._NAME_EXACT or any(name.startswith(prefix) for prefix in self._NAME_PREFIXES):
            return True
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return any(token in msg for token in self._MESSAGE_TOKENS)


class LifecycleLogFilter(logging.Filter):
    """Filter for widget/worker/engine lifecycle diagnostics."""

    _NAME_PREFIXES = (
        "core.process.supervisor",
        "engine.engine_lifecycle",
        "rendering.widget_setup_all",
        "rendering.display_setup",
    )
    _MESSAGE_TOKENS = (
        "[LIFECYCLE]",
        "ProcessSupervisor initialized",
        "ProcessSupervisor shutting down",
        "ProcessSupervisor shutdown complete",
    )

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(record, LOG_FAMILY_LIFECYCLE)
        if explicit is not None:
            return explicit
        name = str(getattr(record, "name", "") or "")
        if any(name.startswith(prefix) for prefix in self._NAME_PREFIXES):
            return True
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return any(token in msg for token in self._MESSAGE_TOKENS)


class CacheLogFilter(logging.Filter):
    """Filter for image-cache/prefetch/cache-authority diagnostics."""

    _NAME_PREFIXES = (
        "engine.image_pipeline",
        "utils.image_prefetcher",
    )
    _MESSAGE_TOKENS = (
        "[CACHE]",
        "[GL CACHE]",
    )

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(record, LOG_FAMILY_CACHE)
        if explicit is not None:
            return explicit
        name = str(getattr(record, "name", "") or "")
        if any(name.startswith(prefix) for prefix in self._NAME_PREFIXES):
            try:
                msg = record.getMessage()
            except Exception:
                msg = str(record.msg)
            return any(token in msg for token in self._MESSAGE_TOKENS)
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return any(token in msg for token in self._MESSAGE_TOKENS)


class SteamLogFilter(logging.Filter):
    """Filter for Steam widget family diagnostics."""

    _NAME_PREFIXES = (
        "core.steam",
        "widgets.steam",
        "ui.tabs.widgets_tab_steam",
    )
    _MESSAGE_TOKENS = (
        "[STEAM]",
        "[STEAM_WIDGET]",
    )

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(record, LOG_FAMILY_STEAM)
        if explicit is not None:
            return explicit
        name = str(getattr(record, "name", "") or "")
        if any(name.startswith(prefix) for prefix in self._NAME_PREFIXES):
            return True
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return any(token in msg for token in self._MESSAGE_TOKENS)


class DedicatedFamilySuppressFilter(logging.Filter):
    """Suppress INFO/DEBUG records from a family when its sidecar log is active."""

    def __init__(self, family_filter: logging.Filter, enabled_getter):
        super().__init__()
        self._family_filter = family_filter
        self._enabled_getter = enabled_getter

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        try:
            enabled = bool(self._enabled_getter())
        except Exception:
            enabled = False
        if not enabled or record.levelno >= logging.WARNING:
            return True
        try:
            return not bool(self._family_filter.filter(record))
        except Exception:
            return True


class VerboseLogFilter(logging.Filter):
    """Filter for verbose debug log - accepts DEBUG and INFO, excludes PERF.
    
    This log captures everything that would be suppressed in console output,
    providing a complete debug trail without the noise of PERF metrics.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        # Only DEBUG and INFO levels (not WARNING+)
        if record.levelno > logging.INFO:
            return False
        explicit = _explicit_log_family_match(record, LOG_FAMILY_PERF)
        if explicit is not None:
            return not explicit
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        # Exclude PERF records (they have their own log)
        return "[PERF]" not in msg


class PerfLogFilter(logging.Filter):
    """Filter that accepts only PERF metric records.

    Structured metadata is authoritative when declared. Legacy call sites
    retain the visible ``[PERF]`` compatibility fallback.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(record, LOG_FAMILY_PERF)
        if explicit is not None:
            return explicit
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return "[PERF]" in msg


class UsageLogFilter(logging.Filter):
    """Filter that accepts only whole-process usage telemetry records."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(record, LOG_FAMILY_USAGE)
        if explicit is not None:
            return explicit
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return "[USAGE]" in msg


class WidgetPerfLogFilter(logging.Filter):
    """Filter that accepts only widget PERF instrumentation records."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(record, LOG_FAMILY_WIDGET_PERF)
        if explicit is not None:
            return explicit
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        return "[PERF_WIDGET]" in msg


class WidgetPerfVisibilityFilter(logging.Filter):
    """Blocks widget PERF records from a handler unless verbose mode is enabled."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if record.levelno >= logging.WARNING:
            return True
        explicit = _explicit_log_family_match(record, LOG_FAMILY_WIDGET_PERF)
        if explicit is not None:
            if not explicit:
                return True
            return is_widget_perf_verbose()
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        if "[PERF_WIDGET]" not in msg:
            return True
        return is_widget_perf_verbose()


class SpotifyVisLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(record, LOG_FAMILY_VISUALIZER)
        if explicit is not None:
            return explicit
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        if "[SPOTIFY_VIS]" in msg:
            return True
        name = str(getattr(record, "name", ""))
        return (
            "spotify_visualizer" in name
            or "spotify_bars_gl_overlay" in name
            or name.endswith("widgets.beat_engine")
            or name.endswith("widgets.spotify_visualizer_widget")
        )


class SpotifyVolLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        explicit = _explicit_log_family_match(
            record,
            LOG_FAMILY_VISUALIZER_VOLUME,
        )
        if explicit is not None:
            return explicit
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        if "[SPOTIFY_VOL]" in msg:
            return True
        name = str(getattr(record, "name", ""))
        return "spotify_volume" in name or "media_volume_runtime" in name


def get_log_dir() -> Path:
    """Return the directory used for log files.
    
    setup_logging() should be called once at startup so that _BASE_DIR is
    updated for frozen builds and the returned path matches the location used
    by the active RotatingFileHandler.
    """
    if _ACTIVE_LOG_DIR is not None:
        return _ACTIVE_LOG_DIR
    if is_diagnostic_build():
        return _resolve_runtime_log_dir(diagnostic_build=True)
    if _FORCED_LOG_DIR is not None:
        return _FORCED_LOG_DIR
    return _BASE_DIR / "logs"


def _install_closing_warning_handoff(
    controller: _QueuedLoggingController,
) -> _ClosingWarningHandler:
    """Atomically replace queue ingress with a late WARNING+ main sink."""

    global _ACTIVE_CLOSING_WARNING_HANDLER

    with _LOGGING_CONTROLLER_LOCK:
        existing = _ACTIVE_CLOSING_WARNING_HANDLER
        if existing is not None and existing.controller is controller:
            return existing
        closing_handler = _ClosingWarningHandler(controller)
        root_logger = logging.getLogger()
        logging._acquireLock()
        try:
            handlers = list(root_logger.handlers)
            replaced = False
            for index, handler in enumerate(handlers):
                if handler is controller.ingress_handler:
                    handlers[index] = closing_handler
                    replaced = True
            if not replaced:
                handlers.append(closing_handler)
            root_logger.handlers = handlers
        finally:
            logging._releaseLock()
        _ACTIVE_CLOSING_WARNING_HANDLER = closing_handler
    try:
        controller.ingress_handler.close()
    except Exception:
        pass
    return closing_handler


def _retire_closing_warning_handoff() -> None:
    """Remove the late-warning sink and close any reopened main output."""

    global _ACTIVE_CLOSING_WARNING_HANDLER

    with _LOGGING_CONTROLLER_LOCK:
        closing_handler = _ACTIVE_CLOSING_WARNING_HANDLER
        _ACTIVE_CLOSING_WARNING_HANDLER = None
    if closing_handler is None:
        return
    root_logger = logging.getLogger()
    logging._acquireLock()
    try:
        root_logger.handlers = [
            handler
            for handler in root_logger.handlers
            if handler is not closing_handler
        ]
    finally:
        logging._releaseLock()
    try:
        closing_handler.close()
    except Exception:
        pass


def _inactive_logging_metrics() -> dict[str, int | float | bool]:
    return {
        "active": False,
        "capacity": _LOG_QUEUE_CAPACITY,
        "queue_depth": 0,
        "queue_high_water": 0,
        "enqueued": 0,
        "dequeued": 0,
        "dropped_debug": 0,
        "dropped_info": 0,
        "dropped_other_low": 0,
        "emergency_attempts": 0,
        "emergency_writes": 0,
        "emergency_stderr_fallbacks": 0,
        "reentry_fallbacks": 0,
        "snapshot_errors": 0,
        "writer_errors": 0,
        "caller_records": 0,
        "caller_enqueue_total_ms": 0.0,
        "caller_enqueue_max_ms": 0.0,
        "writer_lag_records": 0,
        "writer_lag_total_ms": 0.0,
        "writer_lag_max_ms": 0.0,
        "flush_duration_ms": 0.0,
        "flush_timed_out": False,
        "writer_alive": False,
    }


def get_logging_queue_metrics() -> dict[str, int | float | bool]:
    """Return a passive snapshot of the process-owned logging queue."""

    with _LOGGING_CONTROLLER_LOCK:
        controller = _ACTIVE_LOGGING_CONTROLLER
    if controller is None:
        return _inactive_logging_metrics()
    return controller.metrics()


def get_logging_output_handlers() -> tuple[logging.Handler, ...]:
    """Expose writer-owned outputs for bounded diagnostics and configuration tests."""

    with _LOGGING_CONTROLLER_LOCK:
        controller = _ACTIVE_LOGGING_CONTROLLER
    if controller is None:
        return ()
    return controller.output_handlers


def flush_logging(timeout_seconds: float = _LOG_FLUSH_TIMEOUT_SECONDS) -> bool:
    """Boundedly flush records accepted so far while keeping logging active."""

    with _LOGGING_CONTROLLER_LOCK:
        controller = _ACTIVE_LOGGING_CONTROLLER
    if controller is None:
        return True
    return controller.flush(timeout_seconds)


def flush_and_close_logging(
    timeout_seconds: float = _LOG_FLUSH_TIMEOUT_SECONDS,
) -> dict[str, int | float | bool]:
    """Stop admission, drain accepted records and close ordinary log outputs."""

    global _ACTIVE_LOGGING_CONTROLLER

    with _LOGGING_LIFECYCLE_LOCK:
        with _LOGGING_CONTROLLER_LOCK:
            controller = _ACTIVE_LOGGING_CONTROLLER
        if controller is None:
            _retire_closing_warning_handoff()
            return _inactive_logging_metrics()

        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        controller.begin_close()
        _install_closing_warning_handoff(controller)
        controller.allow_finalize()

        metrics = controller.wait_closed(
            max(0.0, deadline - time.monotonic())
        )
        if not metrics["active"]:
            with _LOGGING_CONTROLLER_LOCK:
                if _ACTIVE_LOGGING_CONTROLLER is controller:
                    _ACTIVE_LOGGING_CONTROLLER = None
        return metrics


atexit.register(flush_and_close_logging)


def _resolve_runtime_log_dir(*, diagnostic_build: bool = False) -> Path:
    """Resolve the log directory using the same rules as setup_logging()."""
    base_dir = _BASE_DIR
    exe_path_valid: Path | None = None
    if is_compiled_runtime():
        exe_path = Path(getattr(sys, "executable", "") or "")
        if exe_path.exists():
            exe_path_valid = exe_path
            base_dir = exe_path.parent

    if diagnostic_build:
        return _select_diagnostic_log_dir(exe_path_valid)

    forced_dir = _FORCED_LOG_DIR
    if exe_path_valid is not None and forced_dir is None:
        try:
            log_cfg_path = exe_path_valid.parent / f"{exe_path_valid.stem}.logdir.cfg"
            if log_cfg_path.exists():
                raw_dir = log_cfg_path.read_text(encoding="utf-8").strip()
                if raw_dir:
                    candidate = Path(raw_dir).expanduser()
                    forced_dir = candidate if candidate.is_absolute() else candidate.resolve()
        except Exception:
            pass

    return _select_log_dir(forced_dir, base_dir)


def clear_logs_for_fresh_start(*, diagnostic_build: bool = False) -> tuple[Path, int]:
    """Delete all log files in the resolved runtime log directory before startup.

    Returns:
        tuple[path, deleted_count]: resolved log dir and number of deleted files
    """
    log_dir = _resolve_runtime_log_dir(diagnostic_build=diagnostic_build)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    deleted = 0

    for path in log_dir.iterdir():
        if not path.is_file():
            continue
        try:
            path.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            continue

    return log_dir, deleted


def _candidate_programdata_dir() -> Path | None:
    program_data = os.getenv("PROGRAMDATA")
    if not program_data:
        return None
    return Path(program_data) / "SRPSS" / "logs"


def _candidate_localappdata_diagnostic_dir() -> Path | None:
    """Return the dedicated readable per-user diagnostic log location."""

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "SRPSS" / "Diagnostic" / "logs"
    return None


def _candidate_temp_diagnostic_dir() -> Path:
    return Path(tempfile.gettempdir()) / "SRPSS" / "Diagnostic" / "logs"


def _try_writable_log_dir(path: Path | None) -> Path | None:
    if path is None:
        return None
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".srpss_log_probe"
        with probe.open("w", encoding="utf-8") as handle:
            handle.write("ok")
        probe.unlink(missing_ok=True)
        return path
    except Exception:
        return None


def _select_diagnostic_log_dir(exe_path: Path | None) -> Path:
    """Select the diagnostic-only readable log directory in contract order."""

    global _ACTIVE_LOG_DIR
    candidates = (
        exe_path.parent / "logs" if exe_path is not None else None,
        _candidate_localappdata_diagnostic_dir(),
        _candidate_temp_diagnostic_dir(),
    )
    for candidate in candidates:
        chosen = _try_writable_log_dir(candidate)
        if chosen is not None:
            _ACTIVE_LOG_DIR = chosen
            return chosen
    fallback = _candidate_temp_diagnostic_dir()
    fallback.mkdir(parents=True, exist_ok=True)
    _ACTIVE_LOG_DIR = fallback
    return fallback


def _select_log_dir(
    forced_dir: Path | None,
    base_dir: Path,
) -> Path:
    """
    Determine a writable log directory, falling back to ProgramData or temp.
    """
    global _ACTIVE_LOG_DIR

    candidates: list[Path | None] = []
    candidates.append(forced_dir)
    candidates.append(base_dir / "logs")
    candidates.append(_candidate_programdata_dir())
    candidates.append(Path(tempfile.gettempdir()) / "SRPSS" / "logs")

    for candidate in candidates:
        chosen = _try_writable_log_dir(candidate)
        if chosen is not None:
            _ACTIVE_LOG_DIR = chosen
            return chosen

    # As a last resort, use current working directory logs/ without validation.
    fallback = Path.cwd() / "logs"
    fallback.mkdir(parents=True, exist_ok=True)
    _ACTIVE_LOG_DIR = fallback
    return fallback


def setup_logging(
    debug: bool = False,
    verbose: bool = False,
    perf: bool = False,
    gpu_timing: bool = False,
    usage: bool = False,
    viz: bool = False,
    viz_diag: bool = False,
    geo: bool = False,
    settings_trace: bool = False,
    lifecycle: bool = False,
    cache_trace: bool = False,
    steam_trace: bool = False,
    diagnostic_build: bool = False,
) -> None:
    """
    Configure application logging with file rotation.
    
    Args:
        debug: If True, set log level to DEBUG and enable console output.
        verbose: When True, enables additional high-volume debug logs in
            selected modules (media widget polling, raw settings dumps,
            etc.). Verbose mode also implies debug-level logging.
        perf: Enables performance/PERF logging families.
        gpu_timing: Enables sampled owner-context OpenGL timer queries and
            implies PERF logging. This is intentionally heavier than ordinary
            PERF telemetry.
        usage: Enables low-cadence whole-process resource telemetry.
        viz: When True, enables visualizer-specific logging ([SPOTIFY_VIS],
            [SPOTIFY_VOL]) and visualizer diagnostics.
        viz_diag: Legacy alias for enabling Spotify visualizer DSP diagnostics.
        geo: Enables geometry/z-order/CUSTOM-layout sidecar diagnostics.
        settings_trace: Enables settings mutation/import/schema sidecar diagnostics.
        lifecycle: Enables widget/worker/engine lifecycle sidecar diagnostics.
        cache_trace: Enables image-cache/prefetch/cache-authority sidecar diagnostics.
        steam_trace: Enables Steam widget family sidecar diagnostics.
        diagnostic_build: Forces bounded logging into the dedicated per-user
            diagnostic directory. Ordinary and Media Center release entry
            points never set this flag.
    """
    global _VERBOSE, _PERF_METRICS_ENABLED, _GPU_TIMING_ENABLED
    global _USAGE_LOGGING_ENABLED
    global _VIZ_LOGGING_ENABLED, _VIZ_DIAGNOSTICS_ENABLED
    global _GEOMETRY_LOGGING_ENABLED, _SETTINGS_LOGGING_ENABLED, _LIFECYCLE_LOGGING_ENABLED
    global _CACHE_LOGGING_ENABLED, _STEAM_LOGGING_ENABLED, _WIDGET_PERF_VERBOSE
    global _BASE_DIR, _FORCED_LOG_DIR, _ACTIVE_LOG_DIR
    global _ACTIVE_LOGGING_CONTROLLER

    previous_metrics = flush_and_close_logging()
    if previous_metrics["active"]:
        raise RuntimeError(
            "Previous logging writer did not stop within the bounded flush timeout"
        )
    _retire_closing_warning_handoff()

    if diagnostic_build:
        diagnostic_profile = resolve_logging_bootstrap_profile((), diagnostic_build=True)
        debug = diagnostic_profile.debug
        verbose = diagnostic_profile.verbose
        perf = diagnostic_profile.perf
        gpu_timing = diagnostic_profile.gpu_timing
        usage = diagnostic_profile.usage
        viz = diagnostic_profile.viz
        viz_diag = diagnostic_profile.viz_diag
        geo = diagnostic_profile.geo
        settings_trace = diagnostic_profile.settings_trace
        lifecycle = diagnostic_profile.lifecycle
        cache_trace = diagnostic_profile.cache_trace
        steam_trace = diagnostic_profile.steam_trace
        _WIDGET_PERF_VERBOSE = True

    debug_enabled = debug or verbose
    base_dir = _BASE_DIR
    forced_dir = _FORCED_LOG_DIR
    _ACTIVE_LOG_DIR = None
    exe_path_valid: Path | None = None
    if is_compiled_runtime():
        exe_path = Path(getattr(sys, "executable", "") or "")
        if exe_path.exists():
            exe_path_valid = exe_path
            base_dir = exe_path.parent

    # Command-line flag overrides config file / environment fallback.
    _GPU_TIMING_ENABLED = bool(gpu_timing)
    if _GPU_TIMING_ENABLED:
        perf = True
    if perf:
        _PERF_METRICS_ENABLED = True
    if usage:
        _USAGE_LOGGING_ENABLED = True
    if viz:
        _VIZ_LOGGING_ENABLED = True
        _VIZ_DIAGNOSTICS_ENABLED = True
    if viz_diag:
        _VIZ_DIAGNOSTICS_ENABLED = True
    if geo:
        _GEOMETRY_LOGGING_ENABLED = True
    if settings_trace:
        _SETTINGS_LOGGING_ENABLED = True
    if lifecycle:
        _LIFECYCLE_LOGGING_ENABLED = True
    if cache_trace:
        _CACHE_LOGGING_ENABLED = True
    if steam_trace:
        _STEAM_LOGGING_ENABLED = True

    logging_disabled = _determine_logging_disabled(exe_path_valid)
    if diagnostic_build:
        logging_disabled = False
    global _LOGGING_DISABLED
    _LOGGING_DISABLED = logging_disabled

    # Persist the resolved base_dir so helpers like get_log_dir() can return
    # a consistent location for logs and profiling artefacts.
    _BASE_DIR = base_dir
    if forced_dir is not None:
        _FORCED_LOG_DIR = forced_dir
    else:
        _FORCED_LOG_DIR = None

    specific_logging_enabled = any(
        (
            _PERF_METRICS_ENABLED,
            _GPU_TIMING_ENABLED,
            _USAGE_LOGGING_ENABLED,
            _VIZ_LOGGING_ENABLED,
            _VIZ_DIAGNOSTICS_ENABLED,
            _GEOMETRY_LOGGING_ENABLED,
            _SETTINGS_LOGGING_ENABLED,
            _LIFECYCLE_LOGGING_ENABLED,
            _CACHE_LOGGING_ENABLED,
            _STEAM_LOGGING_ENABLED,
        )
    )
    if logging_disabled and not debug_enabled and not specific_logging_enabled:
        _ACTIVE_LOG_DIR = None
        root = logging.getLogger()
        for handler in list(root.handlers):
            try:
                handler.close()
            except Exception:
                pass
            root.removeHandler(handler)
        root.addHandler(logging.NullHandler())
        root.setLevel(logging.CRITICAL + 10)
        return

    log_dir = _resolve_runtime_log_dir(diagnostic_build=diagnostic_build)
    
    # Reset root handlers on re-entry so repeated setup calls do not duplicate output.
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        try:
            handler.close()
        except Exception:
            pass
        root_logger.removeHandler(handler)

    log_file = log_dir / "screensaver.log"
    
    # Root logger must be DEBUG in debug/verbose modes so the verbose handler
    # can capture full traces. Individual handlers decide what they write.
    root_level = logging.DEBUG if debug_enabled else logging.INFO
    main_level = logging.INFO
    
    # Create formatter with aligned columns for logger name and level
    formatter = logging.Formatter(
        '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    main_formatter = MainLogFormatter(
        '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    spaced_formatter = SpacedLogFormatter(
        '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    output_handlers: list[logging.Handler] = []
    
    # File handler with rotation and deduplication (2MB cap with line-by-line
    # duplicate suppression keeps logs small and readable).
    main_handler = DeduplicatingRotatingFileHandler(
        log_file,
        maxBytes=2 * 1024 * 1024,  # 2 MiB chunks
        # Main is the chronological/warning spine. Keep more overlap with the
        # family sidecars without making ordinary captures unbounded.
        backupCount=11 if diagnostic_build else 7,
        encoding='utf-8'
    )
    main_handler.setFormatter(main_formatter)
    main_handler.setLevel(main_level)
    
    # PERF-tagged records are redirected to the dedicated PERF log, so we
    # drop them from the main screensaver.log to reduce noise and keep
    # per-run logs smaller and easier to inspect.
    main_handler.addFilter(NonPerfFilter())
    main_handler.addFilter(DedicatedFamilySuppressFilter(SpotifyVisLogFilter(), is_viz_logging_enabled))
    main_handler.addFilter(DedicatedFamilySuppressFilter(SpotifyVolLogFilter(), is_viz_logging_enabled))
    main_handler.addFilter(DedicatedFamilySuppressFilter(GeometryLogFilter(), is_geometry_logging_enabled))
    main_handler.addFilter(DedicatedFamilySuppressFilter(SettingsLogFilter(), is_settings_logging_enabled))
    main_handler.addFilter(DedicatedFamilySuppressFilter(LifecycleLogFilter(), is_lifecycle_logging_enabled))
    main_handler.addFilter(DedicatedFamilySuppressFilter(CacheLogFilter(), is_cache_logging_enabled))
    main_handler.addFilter(DedicatedFamilySuppressFilter(SteamLogFilter(), is_steam_logging_enabled))
    main_handler.addFilter(WidgetPerfVisibilityFilter())
    
    console_handler = SuppressingStreamHandler(sys.stdout)
    console_formatter = ColoredFormatter(
        '%(asctime)s - %(name)-30s - %(levelname)-8s - %(message)s',
        datefmt='%H:%M:%S',
        use_color=bool(debug_enabled and sys.stdout.isatty()),
    )
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(main_level)
    console_handler.addFilter(NonPerfFilter())
    console_handler.addFilter(DedicatedFamilySuppressFilter(SpotifyVisLogFilter(), is_viz_logging_enabled))
    console_handler.addFilter(DedicatedFamilySuppressFilter(SpotifyVolLogFilter(), is_viz_logging_enabled))
    console_handler.addFilter(DedicatedFamilySuppressFilter(GeometryLogFilter(), is_geometry_logging_enabled))
    console_handler.addFilter(DedicatedFamilySuppressFilter(SettingsLogFilter(), is_settings_logging_enabled))
    console_handler.addFilter(DedicatedFamilySuppressFilter(LifecycleLogFilter(), is_lifecycle_logging_enabled))
    console_handler.addFilter(DedicatedFamilySuppressFilter(CacheLogFilter(), is_cache_logging_enabled))
    console_handler.addFilter(DedicatedFamilySuppressFilter(SteamLogFilter(), is_steam_logging_enabled))
    console_handler.addFilter(WidgetPerfVisibilityFilter())
    
    # Configure the producer-facing root logger. All real outputs remain
    # writer-owned behind the bounded queue.
    root_logger.setLevel(root_level)
    output_handlers.append(main_handler)
    
    # Dedicated PERF metrics log capturing any record whose message contains
    # the "[PERF]" tag. This keeps performance summaries readable even when
    # the main log is busy with other diagnostics.
    if _PERF_METRICS_ENABLED:
        perf_log_file = log_dir / "screensaver_perf.log"
        perf_handler = DeduplicatingRotatingFileHandler(
            perf_log_file,
            maxBytes=2 * 1024 * 1024,  # 2MB
            backupCount=5,
            encoding='utf-8',
        )
        perf_handler.setFormatter(formatter)
        perf_handler.setLevel(logging.INFO)
        perf_handler.addFilter(PerfLogFilter())
        output_handlers.append(perf_handler)

        widget_perf_log_file = log_dir / "perf_widgets.log"
        widget_perf_handler = DeduplicatingRotatingFileHandler(
            widget_perf_log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        widget_perf_handler.setFormatter(formatter)
        widget_perf_handler.setLevel(logging.INFO)
        widget_perf_handler.addFilter(WidgetPerfLogFilter())
        output_handlers.append(widget_perf_handler)

    if _USAGE_LOGGING_ENABLED:
        usage_log_file = log_dir / "screensaver_usage.log"
        usage_handler = DeduplicatingRotatingFileHandler(
            usage_log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=11 if diagnostic_build else 5,
            encoding='utf-8',
        )
        usage_handler.setFormatter(formatter)
        usage_handler.setLevel(logging.INFO)
        usage_handler.addFilter(UsageLogFilter())
        output_handlers.append(usage_handler)

    if _VIZ_LOGGING_ENABLED:
        spotify_vis_log_file = log_dir / "screensaver_spotify_vis.log"
        spotify_vis_handler = DeduplicatingRotatingFileHandler(
            spotify_vis_log_file,
            maxBytes=2 * 1024 * 1024,  # 2MB
            backupCount=5,
            encoding='utf-8',
        )
        spotify_vis_handler.setFormatter(spaced_formatter)
        spotify_vis_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        spotify_vis_handler.addFilter(SpotifyVisLogFilter())
        output_handlers.append(spotify_vis_handler)

        spotify_vol_log_file = log_dir / "screensaver_spotify_vol.log"
        spotify_vol_handler = DeduplicatingRotatingFileHandler(
            spotify_vol_log_file,
            maxBytes=2 * 1024 * 1024,  # 2MB
            backupCount=5,
            encoding='utf-8',
        )
        spotify_vol_handler.setFormatter(formatter)
        spotify_vol_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        spotify_vol_handler.addFilter(SpotifyVolLogFilter())
        output_handlers.append(spotify_vol_handler)

    if _GEOMETRY_LOGGING_ENABLED:
        geometry_log_file = log_dir / "screensaver_geometry.log"
        geometry_handler = DeduplicatingRotatingFileHandler(
            geometry_log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        geometry_handler.setFormatter(formatter)
        geometry_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        geometry_handler.addFilter(GeometryLogFilter())
        output_handlers.append(geometry_handler)

    if _SETTINGS_LOGGING_ENABLED:
        settings_log_file = log_dir / "screensaver_settings.log"
        settings_handler = DeduplicatingRotatingFileHandler(
            settings_log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        settings_handler.setFormatter(formatter)
        settings_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        settings_handler.addFilter(SettingsLogFilter())
        output_handlers.append(settings_handler)

    if _LIFECYCLE_LOGGING_ENABLED:
        lifecycle_log_file = log_dir / "screensaver_lifecycle.log"
        lifecycle_handler = DeduplicatingRotatingFileHandler(
            lifecycle_log_file,
            maxBytes=2 * 1024 * 1024,
            # Frozen-runtime/lifecycle soaks are exactly where hours-later
            # reconstruction history matters. Ordinary retention stays bounded.
            backupCount=11 if diagnostic_build else 5,
            encoding='utf-8',
        )
        lifecycle_handler.setFormatter(formatter)
        lifecycle_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        lifecycle_handler.addFilter(LifecycleLogFilter())
        output_handlers.append(lifecycle_handler)

    if _CACHE_LOGGING_ENABLED:
        cache_log_file = log_dir / "screensaver_cache.log"
        cache_handler = DeduplicatingRotatingFileHandler(
            cache_log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        cache_handler.setFormatter(formatter)
        cache_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        cache_handler.addFilter(CacheLogFilter())
        output_handlers.append(cache_handler)

    if _STEAM_LOGGING_ENABLED:
        steam_log_file = log_dir / "screensaver_steam.log"
        steam_handler = DeduplicatingRotatingFileHandler(
            steam_log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        steam_handler.setFormatter(formatter)
        steam_handler.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        steam_handler.addFilter(SteamLogFilter())
        output_handlers.append(steam_handler)
    
    # Verbose debug log - captures ALL DEBUG/INFO with deduplication.
    # This is the "messy" log for deep debugging when console suppression
    # hides important details. Now with 2MB limit and deduplication.
    # Log types summary:
    #   1. screensaver.log - Main log (INFO+, no PERF, no Spotify)
    #   2. screensaver_verbose.log - Full DEBUG/INFO with deduplication
    #   3. screensaver_perf.log - PERF metrics only
    #   4. screensaver_spotify_vis.log - Spotify visualizer logs
    #   5. screensaver_spotify_vol.log - Spotify volume logs
    if debug_enabled:
        verbose_log_file = log_dir / "screensaver_verbose.log"
        verbose_handler = DeduplicatingRotatingFileHandler(
            verbose_log_file,
            maxBytes=2 * 1024 * 1024,  # 2MB with deduplication
            backupCount=3,
            encoding='utf-8',
        )
        verbose_handler.setFormatter(formatter)
        verbose_handler.setLevel(logging.DEBUG)
        verbose_handler.addFilter(VerboseLogFilter())
        verbose_handler.addFilter(DedicatedFamilySuppressFilter(SpotifyVisLogFilter(), is_viz_logging_enabled))
        verbose_handler.addFilter(DedicatedFamilySuppressFilter(SpotifyVolLogFilter(), is_viz_logging_enabled))
        verbose_handler.addFilter(DedicatedFamilySuppressFilter(GeometryLogFilter(), is_geometry_logging_enabled))
        verbose_handler.addFilter(DedicatedFamilySuppressFilter(SettingsLogFilter(), is_settings_logging_enabled))
        verbose_handler.addFilter(DedicatedFamilySuppressFilter(LifecycleLogFilter(), is_lifecycle_logging_enabled))
        verbose_handler.addFilter(DedicatedFamilySuppressFilter(CacheLogFilter(), is_cache_logging_enabled))
        verbose_handler.addFilter(DedicatedFamilySuppressFilter(SteamLogFilter(), is_steam_logging_enabled))
        output_handlers.append(verbose_handler)

    # Human console output is deliberately last. All persistent file sinks are
    # attempted before terminal formatting/output for each record.
    if debug_enabled:
        output_handlers.append(console_handler)

    controller = _QueuedLoggingController(
        output_handlers,
        main_handler=main_handler,
        console_handler=console_handler if debug_enabled else None,
        capacity=_LOG_QUEUE_CAPACITY,
    )
    with _LOGGING_CONTROLLER_LOCK:
        _ACTIVE_LOGGING_CONTROLLER = controller
    root_logger.addHandler(controller.ingress_handler)

    # Tame particularly noisy third-party libraries so their DEBUG-level
    # chatter (HTTP connection pools, asyncio internals, etc.) only shows
    # up when explicit verbose logging is requested.
    noisy_level = logging.DEBUG if verbose else logging.INFO
    for name in ("urllib3", "urllib3.connectionpool", "asyncio"):
        logging.getLogger(name).setLevel(noisy_level)
    
    # NOISE REDUCTION: Silence high-frequency internal modules at DEBUG level
    # These modules produce excessive logs during normal operation that make
    # debugging other issues nearly impossible. They only log at INFO+ unless
    # --verbose is explicitly requested.
    NOISY_INTERNAL_MODULES = (
        # Animation system - logs every frame tick
        "core.animation.animator",
        "core.animation",
        # Rendering system - logs every paint/update
        "rendering.display",
        "rendering.display_widget", 
        "rendering.gl_format",
        "rendering.input_handler",
        "rendering.widget_manager",
        # Transitions - logs every frame during transitions
        "transitions.base_transition",
        "transitions.gl_crossfade_transition",
        "transitions.gl_slide_transition",
        "transitions.gl_wipe_transition",
        "transitions.gl_diffuse_transition",
        "transitions.gl_xfade",
        "transitions.gl_slide",
        "transitions.gl_wipe",
        "transitions.gl_diffuse",
        "transitions.gl_blockflip",
        "transitions.gl_blinds",
        "transitions.gl_compositor",
        "transitions.gl_compositor_crumble_transition",
        # Settings manager - logs on every widget interaction
        "SettingsManager",
        # Image queue - logs every image selection
        "engine.image_queue",
        # Widget spam
        "widgets.media_widget",
        # Windows diagnostics - very noisy during cleanup
        "win_diag",
        # GUI settings tabs - noisy during settings dialog
        "gui.tabs",
        "gui.settings_dialog",
        "gui.main_window",
        # Resource manager - logs on every registration/cleanup
        "resources.manager",
        "core.resources.manager",
        # Multi-monitor coordinator - logs halo owner on every check
        "rendering.multi_monitor_coordinator",
        # RSS source - logs every feed parse
        "sources.rss_source",
        # Gmail modules - logs on every fetch/auth
        "core.auth.gmail_oauth",
        "core.gmail.gmail_client",
    )
    internal_noisy_level = logging.DEBUG if verbose else logging.INFO
    for name in NOISY_INTERNAL_MODULES:
        logging.getLogger(name).setLevel(internal_noisy_level)
    
    # Log startup
    _VERBOSE = bool(verbose)

    root_logger.info("=" * 60)
    root_logger.info(
        "Screensaver logging initialized (debug=%s, verbose=%s, perf=%s, gpu_timing=%s, usage=%s, viz=%s, geo=%s, set=%s, life=%s, cache=%s, steam=%s)",
        debug_enabled,
        _VERBOSE,
        _PERF_METRICS_ENABLED,
        _GPU_TIMING_ENABLED,
        _USAGE_LOGGING_ENABLED,
        _VIZ_LOGGING_ENABLED,
        _GEOMETRY_LOGGING_ENABLED,
        _SETTINGS_LOGGING_ENABLED,
        _LIFECYCLE_LOGGING_ENABLED,
        _CACHE_LOGGING_ENABLED,
        _STEAM_LOGGING_ENABLED,
    )
    root_logger.info(
        "Specific logs available: --perf=screensaver_perf.log, --gpu-timing=sampled GL timer queries + screensaver_perf.log, --usage=screensaver_usage.log, --viz=screensaver_spotify_vis.log+screensaver_spotify_vol.log, --geo=screensaver_geometry.log, --set=screensaver_settings.log, --life=screensaver_lifecycle.log, --cache=screensaver_cache.log, --steam=screensaver_steam.log"
    )
    active_specific_logs: list[str] = []
    if _PERF_METRICS_ENABLED:
        active_specific_logs.append("perf=screensaver_perf.log")
    if _GPU_TIMING_ENABLED:
        active_specific_logs.append("gpu_timing=sampled_owner_gl_queries")
    if _USAGE_LOGGING_ENABLED:
        active_specific_logs.append("usage=screensaver_usage.log")
    if _VIZ_LOGGING_ENABLED:
        active_specific_logs.append("viz=screensaver_spotify_vis.log+screensaver_spotify_vol.log")
    if _GEOMETRY_LOGGING_ENABLED:
        active_specific_logs.append("geo=screensaver_geometry.log")
    if _SETTINGS_LOGGING_ENABLED:
        active_specific_logs.append("set=screensaver_settings.log")
    if _LIFECYCLE_LOGGING_ENABLED:
        active_specific_logs.append("life=screensaver_lifecycle.log")
    if _CACHE_LOGGING_ENABLED:
        active_specific_logs.append("cache=screensaver_cache.log")
    if _STEAM_LOGGING_ENABLED:
        active_specific_logs.append("steam=screensaver_steam.log")
    if active_specific_logs:
        root_logger.info("Specific logs active: %s", ", ".join(active_specific_logs))
    root_logger.info("=" * 60)


_SHORT_NAME_OVERRIDES = {
    "core.resources.manager": "resources.manager",
    "engine.screensaver_engine": "engine.screensaver",
    "engine.display_manager": "engine.display",
    "rendering.display_widget": "rendering.display",
    "rendering.gl_format": "rendering.gl_format",
    "transitions.gl_crossfade_transition": "transitions.gl_xfade",
    "transitions.gl_slide_transition": "transitions.gl_slide",
    "transitions.gl_wipe_transition": "transitions.gl_wipe",
    "transitions.gl_diffuse_transition": "transitions.gl_diffuse",
    "transitions.gl_block_puzzle_flip_transition": "transitions.gl_blockflip",
    "transitions.gl_blinds": "transitions.gl_blinds",
}


class LogFamilyAdapter(logging.LoggerAdapter):
    """Attach immutable SRPSS family metadata without rewriting log text."""

    def __init__(self, logger: logging.Logger, families: tuple[str, ...]) -> None:
        super().__init__(logger, {LOG_FAMILY_FIELD: families})
        self._families = families

    def process(self, msg: object, kwargs: dict[str, Any]):
        supplied = kwargs.get("extra")
        extra = dict(supplied) if supplied is not None else {}
        # The adapter's declared ownership is authoritative. Callers needing a
        # multi-family record bind every family on the adapter itself.
        extra[LOG_FAMILY_FIELD] = self._families
        kwargs["extra"] = extra
        return msg, kwargs


def get_logger(
    name: str,
    *,
    families: Iterable[str] | str = (),
) -> logging.Logger | LogFamilyAdapter:
    """Get a logger, optionally binding explicit structured family metadata."""

    actual = _SHORT_NAME_OVERRIDES.get(name, name)
    logger = logging.getLogger(actual)
    requested = (families,) if isinstance(families, str) else tuple(families)
    unknown = tuple(
        str(family)
        for family in requested
        if str(family or "").strip().lower() not in KNOWN_LOG_FAMILIES
    )
    if unknown:
        raise ValueError(f"unknown SRPSS log families: {unknown!r}")
    normalized = normalize_log_families(requested)
    if not normalized:
        return logger
    return LogFamilyAdapter(logger, normalized)


class ThrottledLogger:
    """Rate-limited logger for high-frequency log points.
    
    Wraps a standard logger and limits how often messages are emitted.
    Useful for hot paths like animation frames, visualizer ticks, etc.
    
    Usage:
        throttled = ThrottledLogger(logger, max_per_second=1.0)
        # In hot loop:
        throttled.debug("Frame %d", frame_num)  # Only logs ~1/second
    
    Features:
        - Per-message rate limiting (based on message template)
        - Configurable rate (messages per second)
        - Optional sampling mode (log 1 in N messages)
        - Thread-safe
        - Tracks suppressed count for diagnostics
    """
    
    def __init__(
        self,
        logger: logging.Logger,
        max_per_second: float = 1.0,
        sample_rate: int = 0,
    ):
        """Initialize throttled logger.
        
        Args:
            logger: Underlying logger to wrap
            max_per_second: Maximum messages per second (0 = unlimited)
            sample_rate: If > 0, log 1 in N messages instead of rate limiting
        """
        self._logger = logger
        self._max_per_second = max(0.0, float(max_per_second))
        self._sample_rate = max(0, int(sample_rate))
        self._lock = threading.Lock()
        # Track last emit time per message template
        self._last_emit: dict[str, float] = {}
        # Track call count for sampling mode
        self._call_count: dict[str, int] = {}
        # Track suppressed messages for diagnostics
        self._suppressed_count: int = 0
        self._emitted_count: int = 0
    
    def _should_emit(self, msg: str) -> bool:
        """Check if message should be emitted based on throttling rules."""
        import time
        
        with self._lock:
            # Sampling mode: log 1 in N
            if self._sample_rate > 0:
                count = self._call_count.get(msg, 0) + 1
                self._call_count[msg] = count
                if count % self._sample_rate == 1:
                    self._emitted_count += 1
                    return True
                self._suppressed_count += 1
                return False
            
            # Rate limiting mode
            if self._max_per_second <= 0:
                self._emitted_count += 1
                return True  # Unlimited
            
            now = time.monotonic()
            min_interval = 1.0 / self._max_per_second
            last = self._last_emit.get(msg, 0.0)
            
            if now - last >= min_interval:
                self._last_emit[msg] = now
                self._emitted_count += 1
                return True
            
            self._suppressed_count += 1
            return False
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message with throttling."""
        if self._should_emit(msg):
            self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message with throttling."""
        if self._should_emit(msg):
            self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message (never throttled)."""
        self._emitted_count += 1
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message (never throttled)."""
        self._emitted_count += 1
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message (never throttled)."""
        self._emitted_count += 1
        self._logger.critical(msg, *args, **kwargs)
    
    @property
    def suppressed_count(self) -> int:
        """Get count of suppressed messages."""
        with self._lock:
            return self._suppressed_count
    
    @property
    def emitted_count(self) -> int:
        """Get count of emitted messages."""
        with self._lock:
            return self._emitted_count
    
    def reset_counts(self) -> None:
        """Reset suppressed and emitted counts."""
        with self._lock:
            self._suppressed_count = 0
            self._emitted_count = 0
            self._call_count.clear()


def get_throttled_logger(
    name: str,
    max_per_second: float = 1.0,
    sample_rate: int = 0,
) -> ThrottledLogger:
    """Get a throttled logger instance.
    
    Args:
        name: Logger name (same as get_logger)
        max_per_second: Maximum messages per second per unique message
        sample_rate: If > 0, log 1 in N messages instead of rate limiting
    
    Returns:
        ThrottledLogger wrapping the named logger
    """
    return ThrottledLogger(get_logger(name), max_per_second, sample_rate)


def is_verbose_logging() -> bool:
    """Return True when verbose debug logging is enabled globally."""

    return _VERBOSE


def is_perf_metrics_enabled() -> bool:
    """Return True when PERF metrics/telemetry are enabled globally."""

    return _PERF_METRICS_ENABLED


def is_gpu_timing_enabled() -> bool:
    """Return True only for the explicitly heavy GL timer-query profile."""

    return _GPU_TIMING_ENABLED


def is_usage_logging_enabled() -> bool:
    """Return True when whole-process usage telemetry is enabled."""

    return _USAGE_LOGGING_ENABLED


def is_widget_perf_verbose() -> bool:
    """Return True when per-widget PERF logging should stay verbose."""

    return _WIDGET_PERF_VERBOSE


def is_viz_logging_enabled() -> bool:
    """Return True when visualizer logging is enabled globally.
    
    Visualizer logs ([SPOTIFY_VIS], [SPOTIFY_VOL]) are high-volume and only
    useful when debugging visualizer issues. Use the --viz flag to enable.
    """
    return _VIZ_LOGGING_ENABLED


def is_viz_diagnostics_enabled() -> bool:
    """Return True when Spotify visualizer diagnostics logging is enabled."""

    return _VIZ_DIAGNOSTICS_ENABLED


def is_geometry_logging_enabled() -> bool:
    """Return True when geometry/z-order diagnostics are enabled."""

    return _GEOMETRY_LOGGING_ENABLED


def is_settings_logging_enabled() -> bool:
    """Return True when settings diagnostics are enabled."""

    return _SETTINGS_LOGGING_ENABLED


def is_lifecycle_logging_enabled() -> bool:
    """Return True when lifecycle diagnostics are enabled."""

    return _LIFECYCLE_LOGGING_ENABLED


def is_cache_logging_enabled() -> bool:
    """Return True when cache/prefetch diagnostics are enabled."""

    return _CACHE_LOGGING_ENABLED


def is_steam_logging_enabled() -> bool:
    """Return True when Steam widget family diagnostics are enabled."""

    return _STEAM_LOGGING_ENABLED
