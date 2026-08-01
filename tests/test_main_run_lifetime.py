"""RUN-session application lifetime regressions."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from engine.runtime_destruction import RuntimeDestructionBarrier


def test_run_session_disables_last_window_auto_quit_only_after_startup_gate():
    source = (Path(__file__).parents[1] / "main.py").read_text(encoding="utf-8")

    startup_gate = source.index("if not engine.start():")
    fallback = source.index("return run_config(app)", startup_gate)
    lifetime_policy = source.index(
        "app.setQuitOnLastWindowClosed(False)",
        startup_gate,
    )
    event_loop = source.index("return app.exec()", lifetime_policy)

    assert fallback < lifetime_policy < event_loop


@pytest.mark.qt
def test_run_lifetime_survives_zero_window_dialog_destruction_barrier(qt_app, qtbot):
    class _Engine:
        _terminal_shutdown_requested = False
        _pending_runtime_destruction_barrier = None

    prior_policy = qt_app.quitOnLastWindowClosed()
    about_to_quit = []
    completed = []

    def _record_quit() -> None:
        about_to_quit.append(True)

    qt_app.aboutToQuit.connect(_record_quit)
    qt_app.setQuitOnLastWindowClosed(False)

    try:
        dialog = QWidget()
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.show()

        engine = _Engine()
        barrier = RuntimeDestructionBarrier(
            engine,
            reason="settings_dialog_close",
            retiring_generation=None,
        )
        engine._pending_runtime_destruction_barrier = barrier
        barrier.watch_qobject(dialog, label="SettingsDialog")
        barrier.seal()
        barrier.then(lambda: completed.append(True))

        dialog.close()
        qtbot.waitUntil(lambda: completed == [True], timeout=2000)

        assert about_to_quit == []
        assert barrier.is_complete is True
    finally:
        qt_app.aboutToQuit.disconnect(_record_quit)
        qt_app.setQuitOnLastWindowClosed(prior_policy)
