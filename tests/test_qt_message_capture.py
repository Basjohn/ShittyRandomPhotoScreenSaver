"""Qt/QML message capture into a bounded rotating sidecar.

Qt/QML engine diagnostics emit through Qt's stderr channel, bypassing the Python
log pipeline. `install_qt_message_capture` routes them into a rotating
`screensaver_qml.log` so QML issues (e.g. the Clock retirement null-model storm)
are diagnosable from files. These bars pin the routing, level mapping, bounded
rotation config, idempotency, and that genuine errors also reach the main log.
"""
from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QtMsgType

from core.logging import qt_message_capture as cap


@pytest.fixture(autouse=True)
def _fresh_capture():
    cap.uninstall_qt_message_capture()
    yield
    cap.uninstall_qt_message_capture()


def _read(path) -> str:
    for handler in cap._QML_LOGGER.handlers:
        handler.flush()
    return path.read_text(encoding="utf-8") if path.exists() else ""


def test_install_creates_sidecar_and_captures_qml_warning(tmp_path) -> None:
    path = cap.install_qt_message_capture(tmp_path)
    assert path == tmp_path / "screensaver_qml.log"

    cap._log_qt_message(
        QtMsgType.QtWarningMsg,
        category="qml",
        file="file:///x/ClockAnalogueFace.qml",
        line=107,
        message="file:///x/ClockAnalogueFace.qml:107: TypeError: Cannot read property 'textColor' of null",
    )

    text = _read(path)
    assert "ClockAnalogueFace.qml:107" in text
    assert "Cannot read property 'textColor' of null" in text
    assert "WARNING" in text


def test_rotation_is_bounded(tmp_path) -> None:
    cap.install_qt_message_capture(tmp_path)
    handler = cap._handler
    assert handler is not None
    assert handler.maxBytes == cap._MAX_BYTES
    assert handler.backupCount == cap._BACKUP_COUNT
    # Bounded ceiling stays modest (<= ~8 MB) so a storm cannot fill the disk.
    assert cap._MAX_BYTES * (cap._BACKUP_COUNT + 1) <= 8 * 1024 * 1024


def test_level_mapping_covers_qt_message_types() -> None:
    assert cap._level_for(QtMsgType.QtDebugMsg) == logging.DEBUG
    assert cap._level_for(QtMsgType.QtInfoMsg) == logging.INFO
    assert cap._level_for(QtMsgType.QtWarningMsg) == logging.WARNING
    assert cap._level_for(QtMsgType.QtCriticalMsg) == logging.ERROR
    assert cap._level_for(QtMsgType.QtFatalMsg) == logging.CRITICAL


def test_install_is_idempotent(tmp_path) -> None:
    first = cap.install_qt_message_capture(tmp_path)
    handler_after_first = cap._handler
    second = cap.install_qt_message_capture(tmp_path)
    assert first == second
    assert cap._handler is handler_after_first
    assert len(cap._QML_LOGGER.handlers) == 1


def test_qt_error_is_forwarded_to_main_log(tmp_path, caplog) -> None:
    cap.install_qt_message_capture(tmp_path)
    with caplog.at_level(logging.ERROR, logger="qt"):
        cap._log_qt_message(
            QtMsgType.QtCriticalMsg,
            category="default",
            file=None,
            line=0,
            message="QQmlComponent: Component is not ready",
        )
    assert any("Component is not ready" in rec.message for rec in caplog.records)
