"""Phase G7 gates for same-scene dimming and pixel shift."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtQuick import QQuickItem

from rendering.quick.auxiliary import (
    QuickAuxiliaryController,
    QuickAuxiliaryState,
)
from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import OverlayWidgetGeometry
from rendering.quick.window import QuickDisplayWindow


def test_auxiliary_controller_owns_bounded_state_and_visible_cadence(
    monkeypatch,
    qt_app,
) -> None:
    controller = QuickAuxiliaryController(
        screen_index=2,
        runtime_generation=17,
    )
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
    assert (controller.state.pixel_shift_x, controller.state.pixel_shift_y) == (
        0,
        0,
    )
    controller.set_pixel_shift_defer_check(lambda: False)
    controller._advance_pixel_shift()
    assert (controller.state.pixel_shift_x, controller.state.pixel_shift_y) == (
        2,
        -1,
    )
    assert published[-1] is controller.state

    assert controller.pause() is True
    assert controller.describe()["pixel_shift_timer_active"] is False
    assert controller.configure_pixel_shift(False, 1) is True
    assert (controller.state.pixel_shift_x, controller.state.pixel_shift_y) == (
        0,
        0,
    )
    assert controller.close() is True
    assert controller.state.admission_open is False
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
        visualizer_loader = root.findChild(
            QQuickItem,
            "visualizerPresentationLoader",
        )
        assert layer is not None
        assert dimming is not None
        assert ordinary_host_item is not None
        assert visualizer_loader is not None
        assert ordinary_host_item.parentItem() is layer
        assert visualizer_loader.parentItem() is layer

        retained = controller.ordinary_widget_host.create_widget(
            geometry=OverlayWidgetGeometry(10.0, 12.0, 100.0, 60.0),
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
            QuickAuxiliaryState(
                screen_index=0,
                runtime_generation=44,
                admission_open=False,
            )
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


def test_quick_auxiliary_owner_has_no_qwidget_or_settings_authority() -> None:
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "rendering"
        / "quick"
        / "auxiliary.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("QWidget", "SettingsManager", "DisplayWidget", "PixelShiftManager"):
        assert forbidden not in source
