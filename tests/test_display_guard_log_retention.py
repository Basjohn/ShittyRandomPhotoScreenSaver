"""A logged display-window refusal does not keep the refused runtime alive (the ``test_s_hotkey_workflow.py`` exit).

Production's show-failure path (``DisplayManager._show_display_widget``) logs the refusal with ``exc_info`` and the
exception as an argument. Production's queued log handler snapshots records without their traceback; pytest's log
capture keeps the record for the whole test. The traceback's frames chain back to the caller that built the display
units, so the units stayed referenced, the runtime-destruction barrier timed out and reached the real
``QCoreApplication.exit(1)``. ``tests/conftest.py`` now detaches records about the guard's own refusal; any other
record keeps its ``exc_info`` for the tests that inspect it.
"""
from __future__ import annotations

import gc
import logging
import sys
import weakref


def _display_window_blocked() -> type[BaseException]:
    return next(module.DisplayWindowBlocked for module in list(sys.modules.values())
                if isinstance(getattr(module, "_DISPLAY_GUARD", None), dict)
                and isinstance(getattr(module, "DisplayWindowBlocked", None), type))


class _Unit:
    """Stands in for a display unit held in the caller's locals."""


def _show(error: type[BaseException], logger: logging.Logger) -> None:
    try:
        raise error("refused")
    except Exception as exc:                       # production's own shape: exc_info and the exception as an argument
        logger.error("Failed to show display for screen %s: %s", 0, exc, exc_info=True)


def _build_and_show(error: type[BaseException], logger: logging.Logger) -> weakref.ref:
    unit = _Unit()
    units = [unit]                                 # the caller's locals hold what it built
    _show(error, logger)
    assert units
    return weakref.ref(unit)


def test_a_logged_guard_refusal_does_not_keep_its_callers_locals_alive(caplog) -> None:
    logger = logging.getLogger("tests.display_guard_log_retention")
    with caplog.at_level(logging.ERROR, logger=logger.name):
        unit = _build_and_show(_display_window_blocked(), logger)
        gc.collect()
        assert unit() is None, "the captured refusal record keeps the refused display unit alive"
        record = caplog.records[-1]
        assert record.exc_info is None and "refused" in (record.exc_text or "")
        assert "refused" in record.getMessage()


def test_any_other_error_keeps_its_exc_info_for_tests_that_inspect_it(caplog) -> None:
    logger = logging.getLogger("tests.display_guard_log_retention")
    with caplog.at_level(logging.ERROR, logger=logger.name):
        _build_and_show(RuntimeError, logger)
        record = caplog.records[-1]
        assert record.exc_info is not None and isinstance(record.exc_info[1], RuntimeError)
