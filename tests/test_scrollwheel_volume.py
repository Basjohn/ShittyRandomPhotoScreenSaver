import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QWidget


@pytest.mark.qt
def test_spotify_volume_widget_handle_wheel_clamps_and_schedules(qtbot, monkeypatch):
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    vol = SpotifyVolumeWidget()
    qtbot.addWidget(vol)
    vol.setGeometry(0, 0, 32, 180)
    vol.show()
    qtbot.wait(1)

    applied_levels: list[float] = []
    scheduled_levels: list[float] = []

    def _fake_apply(level: float) -> None:
        applied_levels.append(level)
        vol._volume = level

    def _fake_schedule(level: float) -> None:
        scheduled_levels.append(level)

    monkeypatch.setattr(vol, "_apply_volume_and_broadcast", _fake_apply)
    monkeypatch.setattr(vol, "_schedule_set_volume", _fake_schedule)

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


@pytest.mark.qt
def test_input_handler_route_wheel_uses_local_coordinates(qt_app, settings_manager, qtbot, monkeypatch):
    from rendering.display_widget import DisplayWidget
    from rendering.multi_monitor_coordinator import MultiMonitorCoordinator
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    MultiMonitorCoordinator.reset()
    try:
        w = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
        qtbot.addWidget(w)
        w.resize(600, 400)
        w.show()
        qt_app.processEvents()

        vol = SpotifyVolumeWidget(w)
        qtbot.addWidget(vol)
        vol.setGeometry(100, 50, 32, 180)
        vol._volume = 0.3
        vol.show()
        w.spotify_volume_widget = vol
        qt_app.processEvents()

        assert w._input_handler is not None

        captured: dict[str, object] = {}

        def _fake_handle(self, local_pos, delta_y):
            captured["local"] = QPoint(local_pos)
            captured["delta"] = delta_y
            return True

        monkeypatch.setattr(SpotifyVolumeWidget, "handle_wheel", _fake_handle)

        pos = QPoint(vol.geometry().x() + 5, vol.geometry().y() + 10)
        handled = w._input_handler.route_wheel_event(pos, 120, vol, None, None)

        assert handled is True
        assert captured["delta"] == 120
        assert captured["local"] == QPoint(5, 10)
    finally:
        MultiMonitorCoordinator.reset()


@pytest.mark.qt
def test_input_handler_route_wheel_ignores_hidden_volume(qt_app, settings_manager, qtbot, monkeypatch):
    from rendering.display_widget import DisplayWidget
    from rendering.multi_monitor_coordinator import MultiMonitorCoordinator
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    MultiMonitorCoordinator.reset()
    try:
        w = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
        qtbot.addWidget(w)
        w.resize(400, 300)
        w.show()
        qt_app.processEvents()

        vol = SpotifyVolumeWidget(w)
        qtbot.addWidget(vol)
        vol.setGeometry(50, 50, 32, 180)
        vol._volume = 0.6
        vol.hide()
        w.spotify_volume_widget = vol
        qt_app.processEvents()

        assert w._input_handler is not None

        handled = w._input_handler.route_wheel_event(QPoint(60, 60), 120, vol, None, None)

        assert handled is False
    finally:
        MultiMonitorCoordinator.reset()


@pytest.mark.qt
def test_input_handler_route_wheel_propagates_widget_rejection(qt_app, settings_manager, qtbot, monkeypatch):
    from rendering.display_widget import DisplayWidget
    from rendering.multi_monitor_coordinator import MultiMonitorCoordinator
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    MultiMonitorCoordinator.reset()
    try:
        w = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
        qtbot.addWidget(w)
        w.resize(500, 300)
        w.show()
        qt_app.processEvents()

        vol = SpotifyVolumeWidget(w)
        qtbot.addWidget(vol)
        vol.setGeometry(70, 40, 32, 180)
        vol._volume = 0.4
        vol.show()
        w.spotify_volume_widget = vol
        qt_app.processEvents()

        assert w._input_handler is not None

        def _fake_handle(self, local_pos, delta_y):
            return False

        monkeypatch.setattr(SpotifyVolumeWidget, "handle_wheel", _fake_handle)

        handled = w._input_handler.route_wheel_event(QPoint(80, 60), 120, vol, None, None)

        assert handled is False
    finally:
        MultiMonitorCoordinato
@pytest.mark.qt
def test_ctrl_mode_wheel_adjusts_spotify_volume_widget(qt_app, settings_manager, qtbot, monkeypatch):
    from rendering.display_widget import DisplayWidget
    from rendering.input_handler import InputHandler
    from rendering.multi_monitor_coordinator import MultiMonitorCoordinator
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    monkeypatch.setattr(SpotifyVolumeWidget, "_schedule_set_volume", lambda self, level: None)

    # Keep the test independent of OpenGL availability.
    try:
        settings_manager.set("display.hw_accel", False)
    except Exception:
        pass
    try:
        settings_manager.set("display.render_backend_mode", "software")
    except Exception:
        pass

    MultiMonitorCoordinator.reset()
    try:
        w = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
        qtbot.addWidget(w)
        w.resize(640, 360)
        w.show()
        qt_app.processEvents()

        vol = SpotifyVolumeWidget(w)
        qtbot.addWidget(vol)
        w.spotify_volume_widget = vol

        vol.setGeometry(10, 10, 32, 180)
        vol._volume = 0.5
        vol.show()
        qt_app.processEvents()

        w._coordinator.set_ctrl_held(True)

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
        w.wheelEvent(event)
        after = vol._volume

        assert after > before
    finally:
        MultiMonitorCoordinator.reset()


@pytest.mark.qt
def test_cursor_halo_forwarded_wheel_adjusts_volume(qt_app, settings_manager, qtbot, monkeypatch):
    from rendering.display_widget import DisplayWidget
    from rendering.input_handler import InputHandler
    from rendering.multi_monitor_coordinator import MultiMonitorCoordinator
    from widgets.spotify_volume_widget import SpotifyVolumeWidget

    monkeypatch.setattr(SpotifyVolumeWidget, "_schedule_set_volume", lambda self, level: None)

    try:
        settings_manager.set("display.hw_accel", False)
    except Exception:
        pass

    MultiMonitorCoordinator.reset()
    try:
        w = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
        qtbot.addWidget(w)
        w.resize(800, 600)
        w.move(0, 0)
        w.show()
        qt_app.processEvents()

        vol = SpotifyVolumeWidget(w)
        qtbot.addWidget(vol)
        w.spotify_volume_widget = vol

        vol.setGeometry(200, 120, 32, 180)
        vol._volume = 0.4
        vol.show()
        qt_app.processEvents()

        assert w._input_handler is not None
        w._coordinator.set_ctrl_held(True)
        w._ctrl_held = True

        w._ensure_ctrl_cursor_hint()
        halo = w._ctrl_cursor_hint
        assert halo is not None
        halo.set_parent_widget(w)
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
        global_point = w.mapToGlobal(target_local.toPoint())
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

        assert call_state["route_calls"] > 0, "Halo wheel never reached InputHandler.route_wheel_event"
        assert call_state["wheel_calls"] > 0, "SpotifyVolumeWidget.handle_wheel was never invoked"
        assert after > before, "Cursor halo forwarded wheel should adjust Spotify volume"
    finally:
        MultiMonitorCoordinator.reset()
