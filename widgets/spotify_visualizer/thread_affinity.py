"""GUI-thread affinity assertions for the logical/presentation boundary.

`Docs/P2_Visualizer_Recovery_Contract.md` section 10. The failed cadence attempt
was hidden rather than caught: the logical worker transitively reached
`begin_mode_fade_in()`, which mutates QWidget/QPixmap state, and the resulting
thread-affinity failures disappeared into the surrounding broad `except`
handlers. The suite stayed green while every mode switch presented nothing.

So GUI-only entry points declare their affinity. In tests and development that
is a loud failure; in production it degrades to a bounded error log, because a
screensaver should not die over it at 3am.

Set `SRPSS_STRICT_THREAD_AFFINITY=0` to force production behaviour, or `=1` to
force strict behaviour.
"""

from __future__ import annotations

import os
import sys
import threading

from core.logging.logger import get_logger

logger = get_logger(__name__)


class GuiThreadAffinityError(RuntimeError):
    """A GUI-only operation was attempted off the GUI thread."""


_reported: set[str] = set()


def _strict() -> bool:
    override = os.environ.get("SRPSS_STRICT_THREAD_AFFINITY")
    if override is not None:
        return override.strip() not in {"", "0", "false", "False"}
    # Under pytest an ownership violation must fail the suite, not be logged.
    return "pytest" in sys.modules


def is_gui_thread() -> bool:
    """True when the caller is on Qt's GUI thread (or Qt is absent)."""

    try:
        from PySide6.QtCore import QCoreApplication, QThread
    except Exception:
        return True
    app = QCoreApplication.instance()
    if app is None:
        # No Qt application: nothing owns GUI affinity yet.
        return True
    try:
        return QThread.currentThread() is app.thread()
    except Exception:
        return True


def assert_gui_thread(operation: str) -> None:
    """Declare that `operation` mutates GUI state and must run on the GUI thread."""

    if is_gui_thread():
        return
    message = (
        f"[SPOTIFY_VIS][AFFINITY] {operation}() ran on "
        f"{threading.current_thread().name!r}, not the GUI thread. This is the "
        "logical/presentation ownership boundary being violated."
    )
    if _strict():
        raise GuiThreadAffinityError(message)
    if operation not in _reported:
        _reported.add(operation)
        logger.error(message)
