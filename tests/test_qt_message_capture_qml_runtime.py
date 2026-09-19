from __future__ import annotations

from pathlib import Path

import pytest


pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer, QUrl
from PySide6.QtQml import QQmlComponent, QQmlEngine

from core.logging.qt_message_capture import (
    flush_qt_message_capture,
    install_qt_message_capture,
    uninstall_qt_message_capture,
)


def test_real_qml_warning_reaches_always_on_sidecar(tmp_path):
    """Exercise real Qt/QML message delivery without retiring foreign test objects."""

    app = QCoreApplication.instance() or QCoreApplication([])
    del app  # lifetime remains process-owned by Qt/PySide

    uninstall_qt_message_capture()
    path = install_qt_message_capture(tmp_path)
    engine = None
    component = None
    obj = None
    try:
        assert path == tmp_path / "screensaver_qml.log"

        engine = QQmlEngine()
        component = QQmlComponent(engine)
        component.setData(
            b'import QtQml\nQtObject { Component.onCompleted: console.warn("SRPSS_QML_CAPTURE_PROBE") }',
            QUrl("inline:qt_message_capture_probe.qml"),
        )
        # Inline QML compilation may remain Loading after setData(). Drive a real
        # event loop until statusChanged rather than creating a not-yet-ready type.
        if component.status() == QQmlComponent.Status.Loading:
            loop = QEventLoop()
            component.statusChanged.connect(lambda _status: loop.quit())
            QTimer.singleShot(5000, loop.quit)
            loop.exec()
        assert component.status() == QQmlComponent.Status.Ready, [
            error.toString() for error in component.errors()
        ]
        obj = component.create()
        assert obj is not None, [error.toString() for error in component.errors()]

        assert flush_qt_message_capture()
        text = Path(path).read_text(encoding="utf-8")
        assert "SRPSS_QML_CAPTURE_PROBE" in text
        assert "event=session_start" in text
    finally:
        # Even a failing assertion must not leave a process-global message
        # handler installed or queued deletes for a subsequent shared-process
        # Qt test. Delete only the three QObjects we created, child first.
        for owned in (obj, component, engine):
            if owned is not None:
                owned.deleteLater()
                QCoreApplication.sendPostedEvents(owned, QEvent.Type.DeferredDelete)
        QCoreApplication.processEvents()
        uninstall_qt_message_capture()

    assert "event=session_end" in Path(path).read_text(encoding="utf-8")
