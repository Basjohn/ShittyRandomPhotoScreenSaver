import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent


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
