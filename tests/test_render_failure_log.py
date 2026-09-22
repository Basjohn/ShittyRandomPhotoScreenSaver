"""Render-node failure logging stays bounded while a failure persists (PR-06)."""

from __future__ import annotations

import logging

from rendering.quick.render_failure_log import RenderFailureLog


def _fail(log: RenderFailureLog, message: str) -> None:
    try:
        raise RuntimeError(message)
    except RuntimeError as exc:
        log.note_failure(f"{type(exc).__name__}: {exc}", exc)


def _records(caplog, level: int) -> list[logging.LogRecord]:
    return [record for record in caplog.records if record.levelno == level]


def test_persistent_failure_logs_one_traceback_then_sparse_milestones(caplog) -> None:
    logger = logging.getLogger("test.render_failure_log.persistent")
    log = RenderFailureLog(logger, "Visualizer render node")

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        for _ in range(1000):
            _fail(log, "draw exploded")

    errors = _records(caplog, logging.ERROR)
    tracebacks = [record for record in errors if record.exc_info]
    assert len(tracebacks) == 1
    assert tracebacks[0].getMessage() == (
        "[QUICK] Visualizer render node failed: draw exploded"
    )
    milestones = [record.getMessage() for record in errors if not record.exc_info]
    assert milestones == [
        "[QUICK] Visualizer render node still failing after 100 repeat(s): "
        "RuntimeError: draw exploded",
    ]
    assert log.failing


def test_new_signature_is_never_suppressed_and_reports_prior_run(caplog) -> None:
    logger = logging.getLogger("test.render_failure_log.superseded")
    log = RenderFailureLog(logger, "Background render node")

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        _fail(log, "first")
        _fail(log, "first")
        _fail(log, "second")

    messages = [record.getMessage() for record in _records(caplog, logging.ERROR)]
    assert messages == [
        "[QUICK] Background render node failed: first",
        "[QUICK] Background render node failure superseded after 1 repeat(s): "
        "RuntimeError: first",
        "[QUICK] Background render node failed: second",
    ]
    assert sum(1 for record in caplog.records if record.exc_info) == 2


def test_recovery_is_reported_once_and_rearms_first_occurrence(caplog) -> None:
    logger = logging.getLogger("test.render_failure_log.recovered")
    log = RenderFailureLog(logger, "Visualizer render node")

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        _fail(log, "transient")
        _fail(log, "transient")
        log.note_success()
        assert not log.failing
        _fail(log, "transient")

    warnings = [record.getMessage() for record in _records(caplog, logging.WARNING)]
    assert warnings == [
        "[QUICK] Visualizer render node recovered after 1 repeat(s) of: "
        "RuntimeError: transient",
    ]
    assert sum(1 for record in caplog.records if record.exc_info) == 2
