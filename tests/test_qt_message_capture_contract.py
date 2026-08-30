from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


def _install_fake_pyside(monkeypatch):
    state = {"handler": None, "install_calls": []}

    qtcore = types.ModuleType("PySide6.QtCore")

    def qInstallMessageHandler(handler):
        previous = state["handler"]
        state["handler"] = handler
        state["install_calls"].append(handler)
        return previous

    qtcore.qInstallMessageHandler = qInstallMessageHandler
    pyside = types.ModuleType("PySide6")
    pyside.QtCore = qtcore
    monkeypatch.setitem(sys.modules, "PySide6", pyside)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)
    return state


def _fresh_module(monkeypatch):
    _install_fake_pyside(monkeypatch)
    import core.logging.qt_message_capture as capture

    # The production module may have been imported by another test. Restore a
    # clean module-level state without depending on real Qt.
    capture.uninstall_qt_message_capture()
    return importlib.reload(capture)


def test_install_eagerly_creates_sidecar_and_session_markers(tmp_path, monkeypatch):
    capture = _fresh_module(monkeypatch)

    path = capture.install_qt_message_capture(tmp_path)

    assert path == tmp_path / "screensaver_qml.log"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "event=session_start" in text
    assert "pid=" in text

    metrics = capture.get_qt_message_capture_metrics()
    assert metrics["installed"] is True
    assert metrics["message_count"] == 0
    assert metrics["write_errors"] == 0

    capture.uninstall_qt_message_capture()
    text = path.read_text(encoding="utf-8")
    assert "event=session_end" in text
    assert "messages=0" in text


def test_qt_callback_writes_structured_context_and_metrics(tmp_path, monkeypatch):
    state = _install_fake_pyside(monkeypatch)
    import core.logging.qt_message_capture as capture
    capture.uninstall_qt_message_capture()
    capture = importlib.reload(capture)

    class Mode:
        name = "QtWarningMsg"

    context = types.SimpleNamespace(
        category="qml.binding",
        file="C:/repo/rendering/quick/qml/MediaPresentation.qml",
        line=123,
        function="binding for source",
    )

    path = capture.install_qt_message_capture(tmp_path)
    callback = state["handler"]
    assert callable(callback)
    callback(Mode(), context, "Failed to get image from provider")
    assert capture.flush_qt_message_capture()

    text = Path(path).read_text(encoding="utf-8")
    assert "seq=1" in text
    assert "category=qml.binding" in text
    assert "MediaPresentation.qml:123::binding for source" in text
    assert "Failed to get image from provider" in text

    metrics = capture.get_qt_message_capture_metrics()
    assert metrics["message_count"] == 1
    assert metrics["counts_by_level"] == {"WARNING": 1}
    assert metrics["counts_by_category"] == {"qml.binding": 1}

    capture.uninstall_qt_message_capture()


def test_install_preserves_and_restores_prior_qt_handler(tmp_path, monkeypatch):
    state = _install_fake_pyside(monkeypatch)
    seen = []

    def previous(mode, context, message):
        seen.append((mode, context, message))

    state["handler"] = previous
    import core.logging.qt_message_capture as capture
    capture = importlib.reload(capture)

    class Mode:
        name = "QtInfoMsg"

    context = types.SimpleNamespace(category="default", file=None, line=0, function=None)
    capture.install_qt_message_capture(tmp_path)
    installed = state["handler"]
    assert installed is not previous

    installed(Mode(), context, "hello")
    assert len(seen) == 1
    assert seen[0][2] == "hello"

    capture.uninstall_qt_message_capture()
    assert state["handler"] is previous


def test_install_can_relocate_sink_without_replacing_qt_callback(tmp_path, monkeypatch):
    state = _install_fake_pyside(monkeypatch)
    import core.logging.qt_message_capture as capture
    capture = importlib.reload(capture)

    first = capture.install_qt_message_capture(tmp_path / "one")
    callback = state["handler"]
    second = capture.install_qt_message_capture(tmp_path / "two")

    assert first != second
    assert state["handler"] is callback
    assert Path(second).is_file()
    assert "event=sink_relocated" in Path(second).read_text(encoding="utf-8")

    capture.uninstall_qt_message_capture()
