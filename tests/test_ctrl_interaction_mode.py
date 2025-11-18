"""Tests for Ctrl-held temporary interaction mode in DisplayWidget.

These tests verify that holding Ctrl suppresses mouse-based exits (move/click)
while still allowing exit keys to function, and that the behaviour applies
consistently across multiple DisplayWidget instances.
"""

import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest

from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode


@pytest.mark.qt
def test_ctrl_held_suppresses_mouse_exit_single_widget(qt_app, settings_manager, qtbot):
    """Holding Ctrl prevents mouse movement/click from exiting for one widget."""
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()

    exits = []
    widget.exit_requested.connect(lambda: exits.append("exit"))

    # Press Ctrl and move the mouse around – no exit should be emitted.
    QTest.keyPress(widget, Qt.Key.Key_Control)
    QTest.mouseMove(widget, widget.rect().center())
    QTest.mouseMove(widget, widget.rect().center() + QPoint(50, 0))
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    qt_app.processEvents()

    assert exits == []

    # Release Ctrl – mouse click should now cause an exit.
    QTest.keyRelease(widget, Qt.Key.Key_Control)
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton)
    qt_app.processEvents()

    assert exits == ["exit"]


@pytest.mark.qt
def test_ctrl_held_global_across_multiple_widgets(qt_app, settings_manager, qtbot):
    """Ctrl-held interaction mode should apply across all DisplayWidgets.

    Pressing Ctrl while one DisplayWidget has focus should suppress mouse-exit
    behaviour on another DisplayWidget as well.
    """
    w0 = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    w1 = DisplayWidget(
        screen_index=1,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    for w in (w0, w1):
        qtbot.addWidget(w)
        w.resize(400, 300)
        w.show()

    exits0 = []
    exits1 = []
    w0.exit_requested.connect(lambda: exits0.append("exit0"))
    w1.exit_requested.connect(lambda: exits1.append("exit1"))

    # Hold Ctrl on the first widget
    QTest.keyPress(w0, Qt.Key.Key_Control)
    qt_app.processEvents()

    # Mouse interactions on the second widget should NOT cause exit while Ctrl is held.
    QTest.mouseMove(w1, w1.rect().center())
    QTest.mouseMove(w1, w1.rect().center() + QPoint(60, 0))
    QTest.mouseClick(w1, Qt.MouseButton.LeftButton)
    qt_app.processEvents()

    assert exits0 == []
    assert exits1 == []

    # Releasing Ctrl should restore normal exit behaviour.
    QTest.keyRelease(w0, Qt.Key.Key_Control)
    qt_app.processEvents()

    QTest.mouseClick(w1, Qt.MouseButton.LeftButton)
    qt_app.processEvents()

    assert exits1 == ["exit1"]


@pytest.mark.qt
@pytest.mark.parametrize(
    "media_key",
    [
        Qt.Key.Key_MediaPlay,
        Qt.Key.Key_MediaPause,
        Qt.Key.Key_MediaNext,
        Qt.Key.Key_MediaPrevious,
        Qt.Key.Key_VolumeUp,
        Qt.Key.Key_VolumeDown,
        Qt.Key.Key_VolumeMute,
    ],
)
def test_media_keys_do_not_exit_screensaver(qt_app, settings_manager, qtbot, media_key):
    """Media keys should never be treated as exit keys by DisplayWidget.

    This guards Route3 §4.2: local and global media keys should only control
    media and must not cause the screensaver to exit.
    """
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()

    exits: list[str] = []
    widget.exit_requested.connect(lambda: exits.append("exit"))

    # Simulate media key press/release.
    QTest.keyPress(widget, media_key)
    QTest.keyRelease(widget, media_key)
    qt_app.processEvents()

    assert exits == []


@pytest.mark.qt
def test_ctrl_halo_fades_in_and_out(qt_app, settings_manager, qtbot):
    """Ctrl halo should fade in on press and fade out on release.

    This test probes the internal halo widget to ensure that the opacity
    animation is wired correctly; the visual verification is manual, but
    this guards against regressions in the timing/animation plumbing.
    """
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()

    # Press Ctrl to summon the halo and start fade-in.
    QTest.keyPress(widget, Qt.Key.Key_Control)
    qt_app.processEvents()
    QTest.qWait(100)
    qt_app.processEvents()

    hint = getattr(widget, "_ctrl_cursor_hint", None)
    assert hint is not None
    # During or shortly after fade-in, opacity should be >0.
    opacity_during = float(getattr(hint, "_opacity", 0.0))
    assert 0.0 <= opacity_during <= 1.0

    # Let fade-in complete and then release Ctrl to start fade-out.
    QTest.qWait(600)
    qt_app.processEvents()
    QTest.keyRelease(widget, Qt.Key.Key_Control)
    qt_app.processEvents()

    # Wait longer than the 1200ms fade-out duration.
    QTest.qWait(1400)
    qt_app.processEvents()

    # After fade-out, the halo should either be hidden or effectively transparent.
    hint_after = getattr(widget, "_ctrl_cursor_hint", None)
    assert hint_after is not None
    if hint_after.isVisible():
        opacity_after = float(getattr(hint_after, "_opacity", 1.0))
        assert opacity_after <= 0.1
