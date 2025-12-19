import pytest
from PySide6.QtCore import Qt


@pytest.mark.qt
def test_mc_display_widget_receives_hotkeys(qt_app, qtbot, settings_manager, monkeypatch):
    # Force MC-mode detection in DisplayWidget by spoofing argv[0]
    monkeypatch.setattr("sys.argv", ["SRPSS_MC.exe"])

    from rendering.display_widget import DisplayWidget

    w = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(w)
    w.resize(640, 360)
    w.show()
    qt_app.processEvents()

    counts = {"z": 0, "x": 0, "c": 0, "s": 0, "esc": 0}

    w.previous_requested.connect(lambda: counts.__setitem__("z", counts["z"] + 1))
    w.next_requested.connect(lambda: counts.__setitem__("x", counts["x"] + 1))
    w.cycle_transition_requested.connect(lambda: counts.__setitem__("c", counts["c"] + 1))
    w.settings_requested.connect(lambda: counts.__setitem__("s", counts["s"] + 1))
    w.exit_requested.connect(lambda: counts.__setitem__("esc", counts["esc"] + 1))

    qtbot.keyClick(w, Qt.Key.Key_Z)
    qtbot.keyClick(w, Qt.Key.Key_X)
    qtbot.keyClick(w, Qt.Key.Key_C)
    qtbot.keyClick(w, Qt.Key.Key_S)
    qtbot.keyClick(w, Qt.Key.Key_Escape)

    assert counts["z"] == 1
    assert counts["x"] == 1
    assert counts["c"] == 1
    assert counts["s"] == 1
    assert counts["esc"] == 1
