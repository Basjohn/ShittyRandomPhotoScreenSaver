from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path

import pytest

from core.logging import logger as logger_mod


def _record(level: int, message: str, *args: object) -> logging.LogRecord:
    return logging.LogRecord(
        "test.queued_logging",
        level,
        __file__,
        1,
        message,
        args,
        None,
    )


@pytest.fixture(autouse=True)
def _close_process_logging_after_test(monkeypatch):
    yield
    logger_mod.flush_and_close_logging()


def _reset_logging_flags(monkeypatch, log_dir: Path) -> None:
    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", log_dir)
    monkeypatch.setattr(logger_mod, "_ACTIVE_LOG_DIR", None)
    monkeypatch.setattr(logger_mod, "_LOGGING_DISABLED", False)
    monkeypatch.setattr(logger_mod, "_VERBOSE", False)
    for name in (
        "_PERF_METRICS_ENABLED",
        "_USAGE_LOGGING_ENABLED",
        "_VIZ_LOGGING_ENABLED",
        "_VIZ_DIAGNOSTICS_ENABLED",
        "_GEOMETRY_LOGGING_ENABLED",
        "_SETTINGS_LOGGING_ENABLED",
        "_LIFECYCLE_LOGGING_ENABLED",
        "_CACHE_LOGGING_ENABLED",
        "_STEAM_LOGGING_ENABLED",
    ):
        monkeypatch.setattr(logger_mod, name, False)


def test_filters_and_formatters_run_on_the_writer_thread() -> None:
    filter_threads: list[str] = []
    format_threads: list[str] = []
    messages: list[str] = []

    class ThreadFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            filter_threads.append(threading.current_thread().name)
            return True

    class ThreadFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            format_threads.append(threading.current_thread().name)
            return super().format(record)

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            messages.append(self.format(record))

    handler = CaptureHandler()
    handler.setLevel(logging.DEBUG)
    handler.addFilter(ThreadFilter())
    handler.setFormatter(ThreadFormatter("%(message)s"))
    controller = logger_mod._QueuedLoggingController(
        (handler,),
        main_handler=handler,
        capacity=8,
    )

    controller.enqueue(_record(logging.INFO, "deferred %s", "formatting"))
    metrics = controller.close(1.0)

    assert "deferred formatting" in messages
    assert any("[LOG_QUEUE] final" in message for message in messages)
    assert set(filter_threads) == {"SRPSSLogWriter"}
    assert set(format_threads) == {"SRPSSLogWriter"}
    assert metrics["enqueued"] == 1
    assert metrics["dequeued"] == 1
    assert metrics["caller_records"] == 1
    assert metrics["writer_lag_records"] == 1
    assert metrics["flush_timed_out"] is False
    assert metrics["writer_alive"] is False


def test_exception_snapshot_detaches_traceback_before_queueing() -> None:
    try:
        raise ValueError("snapshot failure fixture")
    except ValueError:
        source = logging.LogRecord(
            "test.queued_logging",
            logging.ERROR,
            __file__,
            1,
            "caught fixture",
            (),
            sys.exc_info(),
        )

    snapshot = logger_mod._snapshot_log_record(source)

    assert snapshot.exc_info is None
    assert snapshot.exc_text is None
    assert snapshot._srpss_traceback is not None

    logger_mod._render_queued_exception(snapshot)

    assert "ValueError: snapshot failure fixture" in snapshot.exc_text
    assert not hasattr(snapshot, "_srpss_traceback")


def test_full_queue_drops_low_severity_but_preserves_warning() -> None:
    first_started = threading.Event()
    release_first = threading.Event()
    messages: list[str] = []

    class BlockingHandler(logging.Handler):
        def __init__(self) -> None:
            super().__init__(logging.DEBUG)
            self._blocked_once = False

        def emit(self, record: logging.LogRecord) -> None:
            if not self._blocked_once:
                self._blocked_once = True
                first_started.set()
                assert release_first.wait(2.0)
            messages.append(self.format(record))

    handler = BlockingHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    controller = logger_mod._QueuedLoggingController(
        (handler,),
        main_handler=handler,
        capacity=1,
    )
    controller.enqueue(_record(logging.INFO, "first"))
    assert first_started.wait(1.0)

    controller.enqueue(_record(logging.INFO, "second"))
    controller.enqueue(_record(logging.DEBUG, "drop-debug"))
    controller.enqueue(_record(logging.INFO, "drop-info"))

    warning_done = threading.Event()

    try:
        raise RuntimeError("saturated traceback")
    except RuntimeError:
        warning_record = logging.LogRecord(
            "test.queued_logging",
            logging.WARNING,
            __file__,
            1,
            "must-survive",
            (),
            sys.exc_info(),
        )

    def emit_warning() -> None:
        controller.enqueue(warning_record)
        warning_done.set()

    warning_thread = threading.Thread(target=emit_warning, name="WarningProducer")
    warning_thread.start()
    deadline = time.monotonic() + 1.0
    while controller.metrics()["emergency_attempts"] == 0 and time.monotonic() < deadline:
        time.sleep(0.005)

    release_first.set()
    assert warning_done.wait(1.0)
    warning_thread.join(timeout=1.0)
    metrics = controller.close(1.0)

    assert "first" in messages
    assert "second" in messages
    assert any("must-survive" in message for message in messages)
    assert any("RuntimeError: saturated traceback" in message for message in messages)
    assert "drop-debug" not in messages
    assert "drop-info" not in messages
    assert metrics["enqueued"] == 2
    assert metrics["dequeued"] == 2
    assert metrics["dropped_debug"] == 1
    assert metrics["dropped_info"] == 1
    assert metrics["emergency_writes"] == 1
    assert metrics["queue_high_water"] == 1
    assert metrics["flush_timed_out"] is False


def test_saturated_warning_cannot_defeat_bounded_close_timeout() -> None:
    first_started = threading.Event()
    release_first = threading.Event()

    class BlockingHandler(logging.Handler):
        def __init__(self) -> None:
            super().__init__(logging.DEBUG)
            self._blocked_once = False

        def emit(self, record: logging.LogRecord) -> None:
            if not self._blocked_once:
                self._blocked_once = True
                first_started.set()
                release_first.wait(2.0)

    handler = BlockingHandler()
    controller = logger_mod._QueuedLoggingController(
        (handler,),
        main_handler=handler,
        capacity=1,
    )
    controller.enqueue(_record(logging.INFO, "first"))
    assert first_started.wait(1.0)
    controller.enqueue(_record(logging.INFO, "second"))

    warning_thread = threading.Thread(
        target=lambda: controller.enqueue(
            _record(logging.WARNING, "saturated warning")
        ),
        name="WarningProducer",
    )
    warning_thread.start()
    deadline = time.monotonic() + 1.0
    while controller.metrics()["emergency_attempts"] == 0 and time.monotonic() < deadline:
        time.sleep(0.005)

    started = time.monotonic()
    timed_out = controller.close(0.02)
    elapsed = time.monotonic() - started

    assert elapsed < 0.2
    assert timed_out["flush_timed_out"] is True
    assert timed_out["writer_alive"] is True

    release_first.set()
    warning_thread.join(timeout=1.0)
    final = controller.close(1.0)
    assert final["writer_alive"] is False


def test_writer_handler_reentry_falls_back_without_recursive_queueing() -> None:
    logger = logging.getLogger("test.queued_logging.reentry")
    original_handlers = list(logger.handlers)
    original_propagate = logger.propagate
    original_level = logger.level
    messages: list[str] = []
    stderr_fallbacks: list[str] = []

    class ReentrantHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            message = record.getMessage()
            messages.append(message)
            if message == "outer":
                logger.warning("nested handler log")

    handler = ReentrantHandler(logging.DEBUG)
    controller = logger_mod._QueuedLoggingController(
        (handler,),
        main_handler=handler,
        capacity=8,
    )
    controller._direct_stderr = (
        lambda prefix, record: stderr_fallbacks.append(
            prefix + record.getMessage()
        )
    )
    logger.handlers = [controller.ingress_handler]
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    try:
        logger.info("outer")
        metrics = controller.close(1.0)
    finally:
        logger.handlers = original_handlers
        logger.propagate = original_propagate
        logger.setLevel(original_level)

    assert "outer" in messages
    assert "nested handler log" not in messages
    assert stderr_fallbacks == ["SRPSS logging reentry: nested handler log"]
    assert metrics["reentry_fallbacks"] == 1
    assert metrics["dequeued"] == 1


def test_emergency_success_metric_excludes_swallowed_handler_failure() -> None:
    stderr_fallbacks: list[str] = []

    class SwallowingFailureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            callback = getattr(self, "_srpss_error_callback", None)
            assert callable(callback)
            callback()

    handler = SwallowingFailureHandler(logging.INFO)
    controller = logger_mod._QueuedLoggingController(
        (handler,),
        main_handler=handler,
        capacity=1,
    )
    controller._direct_stderr = (
        lambda prefix, record: stderr_fallbacks.append(
            prefix + record.getMessage()
        )
    )
    controller.begin_close()
    controller.enqueue(_record(logging.WARNING, "failed emergency write"))
    metrics = controller.close(1.0)

    assert metrics["emergency_attempts"] == 1
    assert metrics["emergency_writes"] == 0
    assert metrics["emergency_stderr_fallbacks"] == 1
    assert metrics["writer_errors"] >= 1
    assert stderr_fallbacks == ["SRPSS emergency log: failed emergency write"]


def test_setup_owns_outputs_behind_one_ingress_and_reentry_drains_old_writer(
    tmp_path,
    monkeypatch,
) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    _reset_logging_flags(monkeypatch, first_dir)

    logger_mod.setup_logging()
    first_controller = logger_mod._ACTIVE_LOGGING_CONTROLLER
    assert first_controller is not None
    assert len(logging.getLogger().handlers) == 1
    assert isinstance(logging.getLogger().handlers[0], logger_mod._QueuedLogHandler)
    assert {Path(handler.baseFilename).name for handler in logger_mod.get_logging_output_handlers()} == {
        "screensaver.log"
    }
    logging.getLogger("test.reentry").info("first-writer-record")

    monkeypatch.setattr(logger_mod, "_FORCED_LOG_DIR", second_dir)
    logger_mod.setup_logging()
    assert first_controller.writer_thread.is_alive() is False
    logging.getLogger("test.reentry").info("second-writer-record")
    metrics = logger_mod.flush_and_close_logging()

    first_text = (first_dir / "screensaver.log").read_text(encoding="utf-8")
    second_text = (second_dir / "screensaver.log").read_text(encoding="utf-8")
    assert "first-writer-record" in first_text
    assert "second-writer-record" not in first_text
    assert "second-writer-record" in second_text
    assert metrics["flush_timed_out"] is False
    assert metrics["writer_alive"] is False


def test_shutdown_changes_admission_before_root_ingress_handoff(
    tmp_path,
    monkeypatch,
) -> None:
    _reset_logging_flags(monkeypatch, tmp_path)
    logger_mod.setup_logging()
    controller = logger_mod._ACTIVE_LOGGING_CONTROLLER
    assert controller is not None
    original_allow_finalize = controller.allow_finalize

    def allow_finalize_after_concurrent_warning() -> None:
        logging.getLogger("test.shutdown_handoff").warning(
            "warning after ingress handoff"
        )
        original_allow_finalize()

    monkeypatch.setattr(
        controller,
        "allow_finalize",
        allow_finalize_after_concurrent_warning,
    )
    metrics = logger_mod.flush_and_close_logging()

    text = (tmp_path / "screensaver.log").read_text(encoding="utf-8")
    assert "warning after ingress handoff" in text
    assert metrics["emergency_writes"] == 1
    assert metrics["flush_timed_out"] is False


def test_bounded_flush_makes_accepted_records_visible_without_closing(
    tmp_path,
    monkeypatch,
) -> None:
    _reset_logging_flags(monkeypatch, tmp_path)
    logger_mod.setup_logging()
    logging.getLogger("test.flush").info("visible before close")

    assert logger_mod.flush_logging(1.0) is True
    assert "visible before close" in (tmp_path / "screensaver.log").read_text(
        encoding="utf-8"
    )
    assert logger_mod.get_logging_queue_metrics()["active"] is True


def test_closing_warning_sink_keeps_late_warning_main_visible(
    tmp_path,
    monkeypatch,
) -> None:
    _reset_logging_flags(monkeypatch, tmp_path)
    logger_mod.setup_logging()
    controller = logger_mod._ACTIVE_LOGGING_CONTROLLER
    assert controller is not None
    first_close = logger_mod.flush_and_close_logging()
    assert first_close["active"] is False

    logging.getLogger("test.late_warning").warning(
        "warning after writer finalization"
    )
    logger_mod.flush_and_close_logging()

    text = (tmp_path / "screensaver.log").read_text(encoding="utf-8")
    assert "warning after writer finalization" in text
    assert controller.metrics()["emergency_writes"] == 1


def test_queued_delivery_preserves_consecutive_duplicate_suppression(
    tmp_path,
    monkeypatch,
) -> None:
    _reset_logging_flags(monkeypatch, tmp_path)
    logger_mod.setup_logging()

    for _ in range(3):
        logging.getLogger("test.dedup").info("same queued record")
    logger_mod.flush_and_close_logging()

    text = (tmp_path / "screensaver.log").read_text(encoding="utf-8")
    assert text.count("same queued record") == 1
    assert "[2 duplicates suppressed]" in text
