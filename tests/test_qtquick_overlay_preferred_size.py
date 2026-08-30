"""Content-driven preferred-size contract bars (H option A, QML half).

These prove the retained shell exposes a family-declared *preferred* content size
that derives from intrinsic content (not the assigned width), and that the Python
geometry binding turns that size-only report into an anchored outer rectangle,
with Python remaining the sole anchor/clamp authority.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from PySide6.QtQuick import QQuickItem

from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.widgets.clock import (
    ClockPresentationConfig,
    ClockPresentationModel,
    ClockPresentationStyle,
)
from rendering.quick.widgets.geometry_resolver import (
    OverlayAnchor,
    OverlayGeometryBinding,
    OverlayGeometryPolicy,
    connect_overlay_preferred_size,
)
from rendering.quick.widgets.host import (
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)


def _shadow_values():
    return {
        "enabled": True,
        "color": [0, 0, 0, 255],
        "blur_radius": 18,
        "frame_opacity": 0.77,
        "text_enabled": True,
        "text_opacity": 0.33,
        "direction": "SE",
    }


def _clock_model(display_mode: str) -> ClockPresentationModel:
    config = ClockPresentationConfig(
        widget_id="clock", font_size=48, display_mode=display_mode
    )
    style = ClockPresentationStyle.project(config, _shadow_values())
    return ClockPresentationModel(config, style)


def _make_host(factory: QuickSceneFactory, owner: QObject):
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=7
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    assert host_item is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
    )
    return root, host


@pytest.mark.qt
def test_clock_reports_real_non_placeholder_preferred_size(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    root, host = _make_host(factory, owner)
    try:
        model = _clock_model("digital")
        widget = host.create_family_widget(
            "clocks",
            initial_properties={"clockModel": model},
            model_identity="clock",
        )
        item = widget.item
        width = float(item.property("preferredContentWidth"))
        height = float(item.property("preferredContentHeight"))
        # A real, non-placeholder content size that includes the shell inset.
        assert width > float(item.property("shellInset"))
        assert height > float(item.property("shellInset"))
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_clock_preferred_size_differs_between_digital_and_analogue(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    root, host = _make_host(factory, owner)
    try:
        digital = _clock_model("digital")
        analogue = _clock_model("analog")
        digital_item = host.create_family_widget(
            "clocks",
            initial_properties={"clockModel": digital},
            model_identity="clock",
        ).item
        analogue_item = host.create_family_widget(
            "clocks",
            initial_properties={"clockModel": analogue},
            model_identity="clock2",
        ).item
        # Both modes declare a real preferred size; the analogue square is not the
        # same as the digital text block.
        assert float(digital_item.property("preferredContentHeight")) > 0.0
        assert float(analogue_item.property("preferredContentHeight")) > 0.0
        assert float(analogue_item.property("preferredContentWidth")) != pytest.approx(
            float(digital_item.property("preferredContentWidth"))
        )
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_preferred_size_drives_anchored_geometry_through_binding(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory()
    root, host = _make_host(factory, owner)
    try:
        model = _clock_model("digital")
        widget = host.create_family_widget(
            "clocks",
            initial_properties={"clockModel": model},
            model_identity="clock",
        )
        item = widget.item
        bounds = OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0)
        policy = OverlayGeometryPolicy(
            widget_id="clock", anchor=OverlayAnchor.TOP_RIGHT, margin=30.0
        )
        applied: list[OverlayWidgetGeometry] = []
        binding = OverlayGeometryBinding(
            policy=policy, display_bounds=bounds, geometry_sink=applied.append
        )

        geometry = connect_overlay_preferred_size(item, binding)

        assert geometry is not None
        # Python owns anchor/clamp: a Top-Right clock sits against the right/top
        # margin with the reported content size as its dimensions.
        expected_w = float(item.property("preferredContentWidth"))
        assert geometry.width == pytest.approx(expected_w)
        assert geometry.x == pytest.approx(1920.0 - expected_w - 30.0)
        assert geometry.y == pytest.approx(30.0)
        assert applied == [geometry]

        assert binding.retire() is True
        item.preferredContentSizeChanged.emit(999.0, 999.0)
        assert applied == [geometry]
        assert binding.retire() is False
    finally:
        host.retire_all()
        factory.deleteLater()
        qt_app.processEvents()
