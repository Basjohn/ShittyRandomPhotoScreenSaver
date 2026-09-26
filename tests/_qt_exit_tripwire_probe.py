"""Probe for ``test_qt_exit_tripwire`` (not collected by default: no ``test_`` prefix).

Run only in a child pytest process. The first test reaches the real
``QCoreApplication.exit(1)``; the conftest tripwire must stop the session before
the second test, whose event loop would otherwise return without running its
timer.
"""
from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer


def test_reaches_the_real_qt_exit(qt_app):
    QCoreApplication.exit(1)


def test_later_event_loop_would_be_inert(qt_app):
    fired = []
    loop = QEventLoop()
    QTimer.singleShot(0, lambda: (fired.append(True), loop.quit()))
    QTimer.singleShot(500, loop.quit)
    loop.exec()
    assert fired, "poisoned event loop: exit() left Qt's quit flag set"
