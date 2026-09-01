"""Permanent Qt Quick dimming/pixel-shift/native-cursor ownership gates."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtQuick import QQuickItem

from rendering.quick.auxiliary import QuickAuxiliaryController, QuickAuxiliaryState
from rendering.quick.cursor_controller import QuickCursorController
from rendering.quick.input_controller import QuickInputController
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickInputState, QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.window import QuickDisplayWindow


def test_auxiliary_controller_owns_bounded_state_and_visible_cadence(monkeypatch, qt_app) -> None:
    controller = QuickAuxiliaryController(screen_index=2, runtime_generation=17)
    published = []
    controller.state_changed.connect(published.append)

    assert controller.set_dimming(True, 1.4) is True
    assert controller.state.dimming_enabled is True
    assert controller.state.dimming_opacity == pytest.approx(1.0)
    assert controller.configure_pixel_shift(True, 9) is True
    assert controller.state.shifts_per_minute == 5
    assert controller.describe()["pixel_shift_timer_active"] is False

    assert controller.resume() is True
    assert controller.describe()["pixel_shift_timer_active"] is True
    monkeypatch.setattr(controller, "_next_pixel_shift", lambda _x, _y: (2, -1))
    controller.set_pixel_shift_defer_check(lambda: True)
    controller._advance_pixel_shift()
    assert (controller.state.pixel_shift_x, controller.state.pixel_shift_y) == (0, 0)
    controller.set_pixel_shift_defer_check(lambda: False)
    controller._advance_pixel_shift()
    assert (controller.state.pixel_shift_x, controller.state.pixel_shift_y) == (2, -1)
    assert published[-1] is controller.state

    assert controller.pause() is True
    assert controller.describe()["pixel_shift_timer_active"] is False
    assert controller._pixel_shift_defer_check is not None
    assert controller.configure_pixel_shift(False, 1) is True
    assert (controller.state.pixel_shift_x, controller.state.pixel_shift_y) == (0, 0)
    assert controller.close() is True
    assert controller.state.admission_open is False
    assert controller._pixel_shift_defer_check is None
    assert controller.set_dimming(True, 0.5) is False


def test_pixel_shift_walk_stays_bounded_and_turns_inward_at_the_edge() -> None:
    x = 0
    y = 0
    for _ in range(200):
        x, y = QuickAuxiliaryController._next_pixel_shift(x, y)
        assert abs(x) <= QuickAuxiliaryController.MAX_PIXEL_SHIFT
        assert abs(y) <= QuickAuxiliaryController.MAX_PIXEL_SHIFT

    edge_x, edge_y = QuickAuxiliaryController._next_pixel_shift(4, 4)
    assert abs(edge_x) <= 4
    assert abs(edge_y) <= 4
    assert abs(edge_x) < 4 or abs(edge_y) < 4


def test_halo_follows_cross_display_ctrl_clear_after_focus_moves(qt_app) -> None:
    global_state = {"held": False}
    display_a = QuickInputController(
        screen_index=0,
        runtime_generation=7,
        global_ctrl_held_provider=lambda: global_state["held"],
        ctrl_state_publisher=lambda held: global_state.__setitem__("held", held),
    )
    aux_a = QuickAuxiliaryController(screen_index=0, runtime_generation=7)
    aux_a.resume()

    display_a.handle_key_press(
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Control, Qt.KeyboardModifier.NoModifier)
    )
    assert display_a.is_ctrl_mode_active() is True
    assert aux_a.apply_input_state(display_a.input_state) is True
    assert aux_a.state.halo_enabled is True
    assert aux_a.state.native_cursor_visible is False

    global_state["held"] = False
    display_a.is_ctrl_mode_active()
    assert display_a.input_state.ctrl_held is False
    aux_a.apply_input_state(display_a.input_state)
    assert aux_a.state.halo_enabled is False
    aux_a.close()


def test_halo_visibility_is_input_admitted_suppressed_and_shape_bounded(qt_app) -> None:
    controller = QuickAuxiliaryController(screen_index=1, runtime_generation=8)
    controller.resume()
    assert controller.state.halo_enabled is False

    assert controller.apply_input_state(
        QuickInputState(screen_index=1, runtime_generation=9, ctrl_held=True)
    ) is False
    assert controller.apply_input_state(
        QuickInputState(screen_index=1, runtime_generation=8, ctrl_held=True)
    ) is True
    assert controller.state.halo_enabled is True
    assert controller.state.native_cursor_visible is False

    assert controller.set_halo_shape("diamond") is True
    assert controller.state.halo_shape == "diamond"
    assert controller.set_halo_shape("not-a-shape") is True
    assert controller.state.halo_shape == "cursor_light"

    assert controller.set_halo_suppressed(True) is True
    assert controller.state.halo_enabled is False
    assert controller.set_halo_suppressed(False) is True
    assert controller.state.halo_enabled is True

    assert controller.apply_input_state(
        QuickInputState(
            screen_index=1,
            runtime_generation=8,
            ctrl_held=True,
            context_menu_active=True,
        )
    ) is True
    assert controller.state.halo_enabled is False
    assert controller.state.native_cursor_visible is True
    controller.close()


@pytest.mark.qt
def test_scene_projects_matching_auxiliary_state_without_item_recreation(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=44,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    try:
        root = controller.scene_root
        layer = root.findChild(QQuickItem, "pixelShiftLayer")
        dimming = root.findChild(QQuickItem, "backgroundDimming")
        ordinary_host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
        visualizer_loader = root.findChild(QQuickItem, "visualizerPresentationLoader")
        assert layer is not None
        assert dimming is not None
        assert ordinary_host_item is not None
        assert visualizer_loader is not None
        # R-64: Halo is native QCursor presentation; it must not return to the scene.
        assert root.findChild(QQuickItem, "cursorHalo") is None
        assert ordinary_host_item.parentItem() is layer
        assert visualizer_loader.parentItem() is layer

        retained = controller.ordinary_widget_host.create_widget(
            geometry=OverlayWidgetGeometry(10.0, 12.0, 100.0, 60.0)
        )
        retained_item = retained.item

        assert controller.apply_auxiliary_state(
            QuickAuxiliaryState(
                screen_index=0,
                runtime_generation=45,
                dimming_enabled=True,
                dimming_opacity=0.8,
                pixel_shift_enabled=True,
                pixel_shift_x=4,
                pixel_shift_y=4,
            )
        ) is False
        assert root.property("dimmingEnabled") is False

        assert controller.apply_auxiliary_state(
            QuickAuxiliaryState(
                screen_index=0,
                runtime_generation=44,
                dimming_enabled=True,
                dimming_opacity=0.35,
                pixel_shift_enabled=True,
                pixel_shift_x=3,
                pixel_shift_y=-2,
                halo_enabled=True,
                halo_shape="circle",
            )
        ) is True
        qt_app.processEvents()

        assert retained.item is retained_item
        assert root.property("dimmingEnabled") is True
        assert root.property("dimmingOpacity") == pytest.approx(0.35)
        assert root.property("pixelShiftX") == pytest.approx(3.0)
        assert root.property("pixelShiftY") == pytest.approx(-2.0)
        assert dimming.property("opacity") == pytest.approx(0.35)
        mapped_origin = layer.mapToScene(QPointF(0.0, 0.0))
        assert mapped_origin.x() == pytest.approx(3.0)
        assert mapped_origin.y() == pytest.approx(-2.0)

        assert controller.apply_auxiliary_state(
            QuickAuxiliaryState(screen_index=0, runtime_generation=44, admission_open=False)
        ) is True
        qt_app.processEvents()
        assert root.property("dimmingEnabled") is False
        assert root.property("pixelShiftX") == pytest.approx(0.0)
        assert root.property("pixelShiftY") == pytest.approx(0.0)
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_quick_window_routes_motion_only_to_native_cursor_owner(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=3,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )

    class _CursorProbe:
        tracks_pointer_motion = True

        def __init__(self) -> None:
            self.calls = 0

        def note_pointer_motion(self) -> bool:
            self.calls += 1
            return True

    cursor = _CursorProbe()
    window.bind_cursor_controller(cursor)
    try:
        event = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(45.5, 36.25),
            QPointF(45.5, 36.25),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QCoreApplication.sendEvent(window, event)
        assert cursor.calls == 1
        assert not hasattr(window, "pointer_position_changed")
    finally:
        window.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_all_native_halo_shapes_render_real_cursor_pixels(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=1,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    cursor = QuickCursorController(window=window, screen_index=0, runtime_generation=1)
    try:
        for shape in (
            "circle",
            "ring",
            "crosshair",
            "diamond",
            "dot",
            "cursor_light",
            "cursor_dark",
        ):
            pixmap, _hot_x, _hot_y = cursor._render_halo_pixmap(
                shape=shape, dpr=1.0, opacity=1.0
            )
            image = pixmap.toImage()
            assert not image.isNull(), shape
            visible_pixels = sum(
                image.pixelColor(x, y).alpha() > 8
                for y in range(image.height())
                for x in range(image.width())
            )
            assert visible_pixels >= 12, (shape, visible_pixels)
    finally:
        cursor.close()
        window.deleteLater()
        qt_app.processEvents()


def test_quick_auxiliary_and_cursor_owners_preserve_native_halo_contract() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    auxiliary = (root / "rendering" / "quick" / "auxiliary.py").read_text(encoding="utf-8")
    cursor = (root / "rendering" / "quick" / "cursor_controller.py").read_text(encoding="utf-8")
    window = (root / "rendering" / "quick" / "window.py").read_text(encoding="utf-8")

    for forbidden in ("QWidget", "SettingsManager", "DisplayWidget", "PixelShiftManager"):
        assert forbidden not in auxiliary
    for retired in ("update_halo_pointer", "halo_x", "halo_y", "halo_visible"):
        assert retired not in auxiliary
    assert '"halo_pointer_owner": "native_qcursor"' in auxiliary
    assert "QCursor" in cursor
    assert '"scene_position_binding": False' in cursor
    assert "def note_pointer_motion" in cursor
    assert "pointer_position_changed" not in window
    assert "cursor.note_pointer_motion()" in window

    qml_dir = root / "rendering" / "quick" / "qml"
    for qml_path in qml_dir.glob("*.qml"):
        if qml_path.name == "CursorHalo.qml":
            continue  # orphan resource is an explicit Phase-I deletion candidate
        assert "CursorHalo" not in qml_path.read_text(encoding="utf-8")
