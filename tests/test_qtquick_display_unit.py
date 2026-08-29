"""Per-display Quick assembly bars (H).

Prove one QuickDisplayUnit assembles the full destination chain for a display -
runtime + one manager + presenter families + option-A geometry + shared Ctrl
coordination - and drives it through clean operations, retiring in clean owner
order and dropping its Ctrl contribution.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor, QPixmap

from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator
from rendering.quick.display_unit import create_quick_display_unit
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.family_binder import ClockFamilyAdapter
from rendering.display_modes import DisplayMode


def _pixmap(w: int, h: int) -> QPixmap:
    pixmap = QPixmap(w, h)
    pixmap.fill(QColor("#224466"))
    return pixmap


def _make_unit(qt_app, generation: int, ctrl_coordinator):
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    unit = create_quick_display_unit(
        screen=screen,
        screen_index=0,
        runtime_generation=generation,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        ctrl_coordinator=ctrl_coordinator,
        interaction_mode_provider=lambda: True,
        adapters=(ClockFamilyAdapter(),),
    )
    return unit, factory


@pytest.mark.qt
def test_unit_assembles_chain_and_binds_families(qt_app) -> None:
    coord = SharedCtrlCoordinator()
    unit, factory = _make_unit(qt_app, 96, coord)
    try:
        host = unit.runtime.scene_controller.ordinary_widget_host
        # One manager owner for this display generation.
        assert unit.runtime.widget_runtime_manager.is_retired is False

        built = unit.bind_families(
            widgets_config={"clock": {"enabled": True, "position": "Top Right"}},
            shadow_values={"enabled": True, "direction": "SE"},
        )
        assert built == ("clock",)
        assert host.live_count == 1
        # The family was placed by Python from its declared preferred size.
        assert unit.presenter.geometry_for("clock") is not None

        # Base image routes through the runtime's explicit API.
        unit.present_image(_pixmap(8, 6), image_path="x.jpg")
        assert unit.runtime.scene_controller.presentation_image.pixel_size == (8, 6)
        unit.clear()
        assert unit.runtime.scene_controller.presentation_image is None
        assert unit.target_size().width() > 0
        target = unit.processing_descriptor(DisplayMode.FIT)
        assert target.screen_index == 0
        assert target.get_target_size() == unit.target_size()
        assert (
            target.logical_size.width(),
            target.logical_size.height(),
        ) == unit.runtime.display_identity.geometry[2:]
        assert target.display_mode is DisplayMode.FIT
        assert target.device_pixel_ratio == pytest.approx(
            unit.runtime.display_identity.device_pixel_ratio
        )
    finally:
        unit.retire()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_unit_retire_is_clean_and_drops_ctrl_contribution(qt_app) -> None:
    coord = SharedCtrlCoordinator()
    unit, factory = _make_unit(qt_app, 97, coord)
    try:
        host = unit.runtime.scene_controller.ordinary_widget_host
        manager = unit.runtime.widget_runtime_manager
        unit.bind_families(
            widgets_config={"clock": {"enabled": True}},
            shadow_values={"enabled": True, "direction": "SE"},
        )
        # Simulate Ctrl held on this display, then never released before retire.
        unit.runtime.input_controller.set_ctrl_held(True)
        assert coord.is_held() is True

        assert unit.retire() is True
        # Families retired, neutral manager retired, Ctrl contribution dropped.
        assert host.live_count == 0
        assert manager.is_retired is True
        assert coord.is_held() is False
        assert unit.is_retired is True
        # Idempotent.
        assert unit.retire() is False
    finally:
        factory.deleteLater()
        qt_app.processEvents()
