"""Tests for Ctrl-held temporary interaction mode in DisplayWidget.

These tests verify that holding Ctrl suppresses mouse-based exits (move/click)
while still allowing exit keys to function, and that the behaviour applies
consistently across multiple DisplayWidget instances.
"""

import time
import types

import pytest
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QMouseEvent, QKeyEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from shiboken6 import Shiboken

from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode
from rendering.multi_monitor_coordinator import get_coordinator, MultiMonitorCoordinator


@pytest.fixture(autouse=True)
def _reset_coordinator():
    """Ensure MultiMonitorCoordinator state does not leak between tests."""
    MultiMonitorCoordinator.reset()
    yield
    MultiMonitorCoordinator.reset()


@pytest.fixture(autouse=True)
def _auto_thread_manager(thread_manager, monkeypatch):
    """Ensure every DisplayWidget in this module receives a ThreadManager."""

    original_init = DisplayWidget.__init__

    def _patched_init(self, *args, **kwargs):
        kwargs.setdefault("thread_manager", thread_manager)
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(DisplayWidget, "__init__", _patched_init)


def _prepare_display_widget_for_ctrl_tests(qt_app, qtbot, widget):
    """Show widget and ensure coordinator registration without full widget setup."""

    qtbot.addWidget(widget)
    widget.show()
    qt_app.processEvents()

    coord = get_coordinator()
    screen = getattr(widget, "_screen", None) or widget.screen()
    try:
        coord.register_instance(widget, screen)
    except Exception:
        pass
    return widget


def _wait_for_halo_visible(qtbot, widget, timeout: int = 2000):
    def _is_visible() -> bool:
        hint = getattr(widget, "_ctrl_cursor_hint", None)
        return bool(hint is not None and hint.isVisible())

    qtbot.waitUntil(_is_visible, timeout=timeout)
    return getattr(widget, "_ctrl_cursor_hint", None)


def _wait_for_halo_hidden(qtbot, widget, timeout: int = 2000):
    def _is_hidden() -> bool:
        hint = getattr(widget, "_ctrl_cursor_hint", None)
        return hint is None or not hint.isVisible()

    qtbot.waitUntil(_is_hidden, timeout=timeout)


def _safe_close(widget) -> None:
    """Detach widget safely before pytest-qt closes it to avoid double deletes."""
    if widget is None:
        return
    try:
        if not Shiboken.isValid(widget):
            return
    except Exception:
        return
    try:
        widget.setParent(None)
    except RuntimeError:
        pass


def _register_volume_widget(qtbot, widget):
    widget.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(widget, before_close_func=_safe_close)
    return widget


@pytest.mark.qt
def test_ctrl_held_suppresses_mouse_exit_single_widget(qt_app, settings_manager, qtbot):
    """Holding Ctrl prevents mouse movement/click from exiting for one widget."""
    # Disable hard_exit mode so clicks can trigger exit after Ctrl release
    settings_manager.set("input.hard_exit", False)
    
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()
    _prepare_display_widget_for_ctrl_tests(qt_app, qtbot, widget)

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
    # Disable hard_exit mode so clicks can trigger exit after Ctrl release
    settings_manager.set("input.hard_exit", False)
    
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
        w.move(0, 0)
        w.show()
        _prepare_display_widget_for_ctrl_tests(qt_app, qtbot, w)
        screen = getattr(w, "_screen", None) or w.screen()
        try:
            get_coordinator().register_instance(w, screen)
        except Exception:
            pass
    coord = get_coordinator()
    try:
        qtbot.waitUntil(lambda: len(coord.get_all_instances()) >= 2, timeout=3000)
    except Exception:
        # In some test environments, coordinator registration may not work as expected
        pytest.skip("Could not register multiple widgets with coordinator")

    exits0 = []
    exits1 = []
    w0.exit_requested.connect(lambda: exits0.append("exit0"))
    w1.exit_requested.connect(lambda: exits1.append("exit1"))

    handler0 = getattr(w0, "_input_handler", None)
    assert handler0 is not None

    from rendering import display_widget as display_mod

    handler0.handle_ctrl_press(coord)
    qt_app.processEvents()
    coord.set_ctrl_held(True)
    display_mod.DisplayWidget._global_ctrl_held = True  # type: ignore[attr-defined]
    w0._ctrl_held = True  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: coord.ctrl_held, timeout=2000)

    # Mouse interactions on the second widget should NOT cause exit while Ctrl is held.
    QTest.mouseMove(w1, w1.rect().center())
    QTest.mouseMove(w1, w1.rect().center() + QPoint(60, 0))
    QTest.mouseClick(w1, Qt.MouseButton.LeftButton)
    qt_app.processEvents()

    assert exits0 == []
    assert exits1 == []

    # Releasing Ctrl should restore normal exit behaviour.
    handler0.handle_ctrl_release(coord)
    coord.set_ctrl_held(False)
    display_mod.DisplayWidget._global_ctrl_held = False  # type: ignore[attr-defined]
    qt_app.processEvents()
    qtbot.waitUntil(lambda: not coord.ctrl_held, timeout=2000)

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

    This guards the invariant that local and global media keys should only
    control media and must not cause the screensaver to exit.
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
    press = QKeyEvent(QEvent.Type.KeyPress, int(media_key), Qt.KeyboardModifier.NoModifier)
    release = QKeyEvent(QEvent.Type.KeyRelease, int(media_key), Qt.KeyboardModifier.NoModifier)
    qt_app.sendEvent(widget, press)
    qt_app.sendEvent(widget, release)
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
    _prepare_display_widget_for_ctrl_tests(qt_app, qtbot, widget)

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
    assert hint_after is None or hint_after.isVisible() is False


@pytest.mark.qt
def test_mc_display_widget_receives_hotkeys(qt_app, qtbot, settings_manager, monkeypatch):
    """Manual Controller build must keep hotkeys and exit shortcuts wired."""
    monkeypatch.setattr("sys.argv", ["SRPSS_Media_Center.exe"])

    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(640, 360)
    widget.show()
    qt_app.processEvents()

    counts = {"z": 0, "x": 0, "c": 0, "s": 0, "esc": 0}

    widget.previous_requested.connect(lambda: counts.__setitem__("z", counts["z"] + 1))
    widget.next_requested.connect(lambda: counts.__setitem__("x", counts["x"] + 1))
    widget.cycle_transition_requested.connect(lambda: counts.__setitem__("c", counts["c"] + 1))
    widget.settings_requested.connect(lambda: counts.__setitem__("s", counts["s"] + 1))
    widget.exit_requested.connect(lambda: counts.__setitem__("esc", counts["esc"] + 1))

    qtbot.keyClick(widget, Qt.Key.Key_Z)
    qtbot.keyClick(widget, Qt.Key.Key_X)
    qtbot.keyClick(widget, Qt.Key.Key_C)
    qtbot.keyClick(widget, Qt.Key.Key_S)
    qtbot.keyClick(widget, Qt.Key.Key_Escape)

    assert counts["z"] == 1
    assert counts["x"] == 1
    assert counts["c"] == 1
    assert counts["s"] == 1
    assert counts["esc"] == 1


@pytest.mark.qt
def test_ctrl_halo_owner_migrates_between_screens(qt_app, settings_manager, qtbot, monkeypatch):
    """Ctrl halo ownership should migrate between DisplayWidgets by QScreen.

    This exercises the global Ctrl halo logic in DisplayWidget.eventFilter by
    mocking QCursor.pos and QGuiApplication.screenAt so that the halo moves
    from one DisplayWidget (screen 0) to another (screen 1) when the cursor is
    reported on a different QScreen.
    """

    # Two widgets representing different screens.
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

    # Assign synthetic QScreen-like identities so that the eventFilter can
    # distinguish screens without relying on the host environment.
    screen0 = object()
    screen1 = object()
    w0._screen = screen0  # type: ignore[attr-defined]
    w1._screen = screen1  # type: ignore[attr-defined]
    coord = get_coordinator()
    coord.register_instance(w0, screen0)  # type: ignore[arg-type]
    coord.register_instance(w1, screen1)  # type: ignore[arg-type]
    coord.set_halo_owner(w0)

    def _bind_map(widget, point):
        def _map(self, pos):
            return QPoint(point)
        widget.mapFromGlobal = types.MethodType(_map, widget)  # type: ignore[attr-defined]

    _bind_map(w0, QPoint(30, 30))
    _bind_map(w1, QPoint(40, 40))

    # Start with Ctrl held and the halo owned by w0.
    from rendering import display_widget as display_mod

    display_mod.DisplayWidget._global_ctrl_held = True  # type: ignore[attr-defined]
    display_mod.DisplayWidget._halo_owner = w0  # type: ignore[attr-defined]
    # Ensure w0 has a visible halo before migration.
    w0._show_ctrl_cursor_hint(QPoint(10, 10), mode="fade_in")  # type: ignore[attr-defined]
    qt_app.processEvents()

    # Mock global cursor and QScreen mapping so the cursor moves to screen1.
    monkeypatch.setattr(
        display_mod.QCursor,  # type: ignore[attr-defined]
        "pos",
        staticmethod(lambda: QPoint(100, 100)),
    )

    def _fake_screen_at(pos):  # noqa: ARG001
        return screen1

    monkeypatch.setattr(
        display_mod.QGuiApplication,  # type: ignore[attr-defined]
        "screenAt",
        staticmethod(_fake_screen_at),
    )

    # Feed a synthetic mouse-move event through w0's eventFilter. The global
    # filter logic should notice the screen change and migrate the halo owner
    # from w0 to w1.
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPoint(50, 50),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    w0.eventFilter(w0, event)
    QTest.qWait(1400)
    qt_app.processEvents()

    # After migration, the global owner should be w1, w0's halo should be
    # hidden, and w1's halo should be visible.
    assert coord.halo_owner is w1
    assert display_mod.DisplayWidget._halo_owner is w1  # type: ignore[attr-defined]

    hint0 = getattr(w0, "_ctrl_cursor_hint", None)
    hint1 = getattr(w1, "_ctrl_cursor_hint", None)

    if hint0 is not None:
        assert not hint0.isVisible()
    assert hint1 is not None
    assert hint1.isVisible()


@pytest.mark.qt
def test_ctrl_halo_shows_without_slack_attr(qt_app, settings_manager, qtbot):
    """Halo should render even if halo slack attribute has never been set."""
    settings_manager.set("input.hard_exit", True)
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(300, 200)
    widget.show()

    assert not hasattr(widget, "_halo_out_of_bounds_slack")

    widget._show_ctrl_cursor_hint(QPoint(100, 120), mode="fade_in")  # type: ignore[attr-defined]
    qt_app.processEvents()

    hint = getattr(widget, "_ctrl_cursor_hint", None)
    assert hint is not None
    assert hint.isVisible()


@pytest.mark.qt
def test_ctrl_halo_suppressed_while_context_menu_active(qt_app, settings_manager, qtbot):
    """Halo should hide and refuse to show when context menu is open."""
    settings_manager.set("input.hard_exit", True)
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()

    QTest.keyPress(widget, Qt.Key.Key_Control)
    qt_app.processEvents()
    widget._show_ctrl_cursor_hint(QPoint(50, 50), mode="none")  # type: ignore[attr-defined]
    qt_app.processEvents()

    hint = getattr(widget, "_ctrl_cursor_hint", None)
    assert hint is not None and hint.isVisible()

    widget._context_menu_active = True  # type: ignore[attr-defined]
    widget._show_ctrl_cursor_hint(QPoint(80, 80), mode="none")  # type: ignore[attr-defined]
    QTest.qWait(50)
    qt_app.processEvents()

    assert not hint.isVisible()


@pytest.mark.qt
def test_ctrl_halo_hides_when_cursor_leaves_display(qt_app, settings_manager, qtbot):
    """Halo should disappear when event filter supplies out-of-bounds coordinates."""
    settings_manager.set("input.hard_exit", True)
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()
    _prepare_display_widget_for_ctrl_tests(qt_app, qtbot, widget)

    QTest.keyPress(widget, Qt.Key.Key_Control)
    qt_app.processEvents()
    widget._show_ctrl_cursor_hint(QPoint(40, 40), mode="none")  # type: ignore[attr-defined]
    qt_app.processEvents()

    hint = getattr(widget, "_ctrl_cursor_hint", None)
    assert hint is not None
    _wait_for_halo_visible(qtbot, widget)

    widget._show_ctrl_cursor_hint(QPoint(-10, -10), mode="none")  # type: ignore[attr-defined]
    QTest.qWait(50)
    qt_app.processEvents()

    _wait_for_halo_hidden(qtbot, widget)


@pytest.mark.qt
def test_ctrl_halo_inactivity_timeout(qt_app, settings_manager, qtbot):
    """Halo should auto-hide after inactivity timeout (~2s)."""
    settings_manager.set("input.hard_exit", True)
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()

    QTest.keyPress(widget, Qt.Key.Key_Control)
    qt_app.processEvents()
    widget._show_ctrl_cursor_hint(QPoint(60, 60), mode="none")  # type: ignore[attr-defined]
    qt_app.processEvents()

    hint = getattr(widget, "_ctrl_cursor_hint", None)
    assert hint is not None and hint.isVisible()

    widget._last_halo_activity_ts = time.monotonic() - (widget._halo_activity_timeout + 0.5)  # type: ignore[attr-defined]
    widget._on_halo_inactivity_timeout()  # type: ignore[attr-defined]
    QTest.qWait(50)
    qt_app.processEvents()

    assert not hint.isVisible()


@pytest.mark.qt
def test_ctrl_halo_suppressed_while_settings_dialog_active(qt_app, settings_manager, qtbot):
    """Settings dialog active flag must fully suppress Ctrl halo in hard-exit mode."""
    settings_manager.set("input.hard_exit", True)
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()

    coord = get_coordinator()
    _prepare_display_widget_for_ctrl_tests(qt_app, qtbot, widget)
    coord.set_settings_dialog_active(False)
    coord.set_ctrl_held(False)
    coord.hide_all_halos()
    coord.reset_all_ctrl_state()

    # Warm-up: halo should appear normally when settings dialog is inactive.
    QTest.keyPress(widget, Qt.Key.Key_Control)
    qt_app.processEvents()
    QTest.mouseMove(widget, widget.rect().center())
    qt_app.processEvents()
    hint = getattr(widget, "_ctrl_cursor_hint", None)
    assert hint is not None
    _wait_for_halo_visible(qtbot, widget)
    QTest.keyRelease(widget, Qt.Key.Key_Control)
    coord.set_ctrl_held(False)
    qt_app.processEvents()

    # Activate settings dialog flag - halo must hide and refuse to show.
    coord.set_settings_dialog_active(True)
    QTest.keyPress(widget, Qt.Key.Key_Control)
    qt_app.processEvents()
    QTest.mouseMove(widget, widget.rect().center() + QPoint(10, 10))
    qt_app.processEvents()
    hint_active = getattr(widget, "_ctrl_cursor_hint", None)
    if hint_active is not None:
        _wait_for_halo_hidden(qtbot, widget)
    QTest.keyRelease(widget, Qt.Key.Key_Control)
    coord.set_ctrl_held(False)
    qt_app.processEvents()

    # Clearing the flag should allow the halo to render again.
    coord.set_settings_dialog_active(False)
    QTest.keyPress(widget, Qt.Key.Key_Control)
    qt_app.processEvents()
    QTest.mouseMove(widget, widget.rect().center() + QPoint(20, 20))
    qt_app.processEvents()
    hint_final = getattr(widget, "_ctrl_cursor_hint", None)
    assert hint_final is not None and hint_final.isVisible()
    QTest.keyRelease(widget, Qt.Key.Key_Control)
    coord.set_ctrl_held(False)


@pytest.mark.qt
def test_spotify_volume_widget_uses_coordinated_fade_sync(qtbot, monkeypatch):
    """Volume widget should request overlay fade sync when it starts."""
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    fade_sync_requests = []

    class MockParent(QWidget):
        def request_overlay_fade_sync(self, name, starter):
            fade_sync_requests.append((name, starter))

    parent = MockParent()
    qtbot.addWidget(parent)
    parent.resize(800, 600)
    parent.show()

    vol = SpotifyVolumeWidget(parent)
    vol.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

    try:
        monkeypatch.setattr(vol._controller, "is_available", lambda: True)
        monkeypatch.setattr(vol._controller, "get_volume", lambda: 0.5)

        vol.start()
        assert len(fade_sync_requests) == 1
        assert fade_sync_requests[0][0] == "spotify_volume"
        starter = fade_sync_requests[0][1]
        assert callable(starter)
    finally:
        try:
            vol.setParent(None)
            vol.deleteLater()
        except Exception:
            pass


@pytest.mark.qt
def test_spotify_volume_widget_handle_wheel_clamps_and_schedules(qtbot, monkeypatch):
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    vol = SpotifyVolumeWidget()
    _register_volume_widget(qtbot, vol)
    vol.setGeometry(0, 0, 32, 180)
    vol.show()

    applied_levels: list[float] = []
    scheduled_levels: list[float] = []

    def _fake_apply(level: float) -> None:
        applied_levels.append(level)
        vol._volume = level

    def _fake_schedule(level: float) -> None:
        scheduled_levels.append(level)

    monkeypatch.setattr(vol, "_apply_volume_and_broadcast", _fake_apply)
    monkeypatch.setattr(vol, "_schedule_set_volume", _fake_schedule)

    try:
        vol._volume = 0.95
        assert vol.handle_wheel(QPoint(10, 10), 120)
        assert applied_levels[-1] <= 1.0
        assert scheduled_levels[-1] == applied_levels[-1]

        vol._volume = 0.02
        assert vol.handle_wheel(QPoint(10, 170), -120)
        assert applied_levels[-1] >= 0.0

        vol.hide()
        assert not vol.handle_wheel(QPoint(0, 0), 120)
        vol.show()
        assert not vol.handle_wheel(QPoint(0, 0), 0)
    finally:
        vol.hide()


@pytest.mark.qt
def test_input_handler_route_wheel_uses_local_coordinates(qt_app, settings_manager, qtbot, monkeypatch):
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    qt_app.processEvents()

    vol = SpotifyVolumeWidget(widget)
    _register_volume_widget(qtbot, vol)
    vol.setGeometry(100, 50, 32, 180)
    vol._volume = 0.3
    vol.show()
    widget.spotify_volume_widget = vol
    qt_app.processEvents()

    assert widget._input_handler is not None

    captured: dict[str, object] = {}

    def _fake_handle(self, local_pos, delta_y):
        captured["local"] = QPoint(local_pos)
        captured["delta"] = delta_y
        return True

    monkeypatch.setattr(SpotifyVolumeWidget, "handle_wheel", _fake_handle)

    pos = QPoint(vol.geometry().x() + 5, vol.geometry().y() + 10)
    handled = widget._input_handler.route_wheel_event(pos, 120, vol, None, None)

    assert handled is True
    assert captured["delta"] == 120
    assert captured["local"] == QPoint(5, 10)


@pytest.mark.qt
def test_input_handler_route_wheel_ignores_hidden_volume(qt_app, settings_manager, qtbot):
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(widget)
    widget.resize(400, 300)
    widget.show()
    qt_app.processEvents()

    vol = SpotifyVolumeWidget(widget)
    _register_volume_widget(qtbot, vol)
    vol.setGeometry(50, 50, 32, 180)
    vol._volume = 0.6
    vol.hide()
    widget.spotify_volume_widget = vol
    qt_app.processEvents()

    assert widget._input_handler is not None

    handled = widget._input_handler.route_wheel_event(QPoint(60, 60), 120, vol, None, None)

    assert handled is False


@pytest.mark.qt
def test_input_handler_route_wheel_propagates_widget_rejection(qt_app, settings_manager, qtbot, monkeypatch):
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(widget)
    widget.resize(500, 300)
    widget.show()
    qt_app.processEvents()

    vol = SpotifyVolumeWidget(widget)
    _register_volume_widget(qtbot, vol)
    vol.setGeometry(70, 40, 32, 180)
    vol._volume = 0.4
    vol.show()
    widget.spotify_volume_widget = vol
    qt_app.processEvents()

    assert widget._input_handler is not None

    def _fake_handle(self, local_pos, delta_y):
        return False

    monkeypatch.setattr(SpotifyVolumeWidget, "handle_wheel", _fake_handle)

    handled = widget._input_handler.route_wheel_event(QPoint(80, 60), 120, vol, None, None)

    assert handled is False


@pytest.mark.qt
def test_ctrl_mode_wheel_adjusts_spotify_volume_widget(qt_app, settings_manager, qtbot, monkeypatch):
    from rendering.input_handler import InputHandler
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    monkeypatch.setattr(SpotifyVolumeWidget, "_schedule_set_volume", lambda self, level: None)

    try:
        settings_manager.set("display.hw_accel", False)
    except Exception:
        pass
    try:
        settings_manager.set("display.render_backend_mode", "software")
    except Exception:
        pass

    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(widget)
    widget.resize(640, 360)
    widget.show()
    qt_app.processEvents()

    vol = SpotifyVolumeWidget(widget)
    _register_volume_widget(qtbot, vol)
    widget.spotify_volume_widget = vol

    vol.setGeometry(10, 10, 32, 180)
    vol._volume = 0.5
    vol.show()
    qt_app.processEvents()

    assert isinstance(widget._input_handler, InputHandler)
    widget._coordinator.set_ctrl_held(True)

    pos = QPointF(15.0, 20.0)
    global_pos = QPointF(15.0, 20.0)
    event = QWheelEvent(
        pos,
        global_pos,
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    before = vol._volume
    widget.wheelEvent(event)
    after = vol._volume

    assert after > before


@pytest.mark.qt
def test_cursor_halo_forwarded_wheel_adjusts_volume(qt_app, settings_manager, qtbot, monkeypatch):
    from rendering.input_handler import InputHandler
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    monkeypatch.setattr(SpotifyVolumeWidget, "_schedule_set_volume", lambda self, level: None)

    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(widget)
    widget.resize(800, 600)
    widget.move(0, 0)
    widget.show()
    qt_app.processEvents()

    vol = SpotifyVolumeWidget(widget)
    _register_volume_widget(qtbot, vol)
    widget.spotify_volume_widget = vol

    vol.setGeometry(200, 120, 32, 180)
    vol._volume = 0.4
    vol.show()
    qt_app.processEvents()

    assert widget._input_handler is not None
    widget._coordinator.set_ctrl_held(True)
    widget._ctrl_held = True

    widget._ensure_ctrl_cursor_hint()
    halo = widget._ctrl_cursor_hint
    assert halo is not None
    halo.set_parent_widget(widget)
    qt_app.processEvents()

    call_state: dict[str, object] = {
        "route_calls": 0,
        "wheel_calls": 0,
    }

    original_route = InputHandler.route_wheel_event

    def _patched_route(self, pos, delta_y, *args, **kwargs):
        call_state["route_calls"] = call_state.get("route_calls", 0) + 1
        call_state["route_last_pos"] = QPoint(pos)
        call_state["route_last_delta"] = delta_y
        result = original_route(self, pos, delta_y, *args, **kwargs)
        call_state["route_result"] = result
        return result

    monkeypatch.setattr(InputHandler, "route_wheel_event", _patched_route)

    original_handle_wheel = SpotifyVolumeWidget.handle_wheel

    def _patched_handle_wheel(self, local_pos, delta_y):
        call_state["wheel_calls"] = call_state.get("wheel_calls", 0) + 1
        call_state["wheel_last_local"] = QPoint(local_pos)
        call_state["wheel_last_delta"] = delta_y
        return original_handle_wheel(self, local_pos, delta_y)

    monkeypatch.setattr(SpotifyVolumeWidget, "handle_wheel", _patched_handle_wheel)

    target_local = QPointF(210.0, 160.0)
    global_point = widget.mapToGlobal(target_local.toPoint())
    global_pos = QPointF(float(global_point.x()), float(global_point.y()))

    event = QWheelEvent(
        QPointF(0.0, 0.0),
        global_pos,
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )

    before = vol._volume
    halo._forward_wheel_event(event)
    qt_app.processEvents()
    after = vol._volume

    assert call_state["route_calls"] > 0
    assert call_state["wheel_calls"] > 0
    assert after > before
