"""Per-display Quick presenter bars (H).

These prove the thin presenter assembles a display generation's families into the
retained scene and places them under option A: content anchoring is the default
placement (Python owns the outer rect from the family's declared preferred size),
a committed rect overrides it completely, a topology change re-anchors only the
content-anchored families, and retirement drops everything exactly once.
"""

from __future__ import annotations

import pytest

from rendering.quick.display_presenter import QuickDisplayPresenter
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.family_binder import ClockFamilyAdapter, WeatherFamilyAdapter
from rendering.quick.widgets.geometry_resolver import (
    OverlayAnchor,
    resolve_anchored_geometry,
)
from rendering.quick.widgets.host import OverlayWidgetGeometry


_BOUNDS = OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0)
_SHADOWS = {"enabled": True, "direction": "SE"}


def _make_runtime(qt_app, generation: int):
    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=generation,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    return runtime, factory


@pytest.mark.qt
def test_presenter_places_content_anchored_families(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 90)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        presenter = QuickDisplayPresenter(runtime, adapters=(ClockFamilyAdapter(),))

        built = presenter.bind_families(
            widgets_config={"clock": {"enabled": True, "position": "Top Right"}},
            display_bounds=_BOUNDS,
            shadow_values=_SHADOWS,
        )
        assert built == ("clock",)
        assert host.live_count == 1

        item = host.presentation_for_model_identity("clock").item
        expected = resolve_anchored_geometry(
            content_size=(
                float(item.property("preferredContentWidth")),
                float(item.property("preferredContentHeight")),
            ),
            anchor=OverlayAnchor.TOP_RIGHT,
            margin=30.0,
            display_bounds=_BOUNDS,
        )
        # Python assigned the outer rect from the family's declared preferred size.
        assert item.x() == pytest.approx(expected.x)
        assert item.y() == pytest.approx(expected.y)
        assert item.width() == pytest.approx(expected.width)
        geometry = presenter.geometry_for("clock")
        assert geometry is not None
        assert geometry.x == pytest.approx(expected.x)
    finally:
        presenter.retire()
        assert host.live_count == 0
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_presenter_committed_rect_overrides_content_anchoring(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 91)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        presenter = QuickDisplayPresenter(runtime, adapters=(ClockFamilyAdapter(),))
        committed = OverlayWidgetGeometry(200.0, 150.0, 480.0, 300.0)

        presenter.bind_families(
            widgets_config={"clock": {"enabled": True, "position": "Top Right"}},
            display_bounds=_BOUNDS,
            shadow_values=_SHADOWS,
            committed_rect_resolver=lambda wid: committed if wid == "clock" else None,
        )

        item = host.presentation_for_model_identity("clock").item
        # Option A: the committed rect wins outright over content anchoring.
        assert item.x() == pytest.approx(200.0)
        assert item.y() == pytest.approx(150.0)
        assert item.width() == pytest.approx(480.0)
        assert item.height() == pytest.approx(300.0)
        assert presenter.geometry_for("clock") == committed
    finally:
        presenter.retire()
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_presenter_reanchors_content_family_but_not_committed_on_topology(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 92)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        presenter = QuickDisplayPresenter(
            runtime, adapters=(ClockFamilyAdapter(), WeatherFamilyAdapter())
        )
        committed = OverlayWidgetGeometry(100.0, 100.0, 500.0, 260.0)
        presenter.bind_families(
            widgets_config={
                "clock": {"enabled": True, "position": "Top Right"},
                "weather": {"enabled": True, "position": "Bottom Right"},
            },
            display_bounds=_BOUNDS,
            shadow_values=_SHADOWS,
            committed_rect_resolver=lambda wid: committed if wid == "weather" else None,
        )
        clock_before = presenter.geometry_for("clock")

        wider = OverlayWidgetGeometry(0.0, 0.0, 2560.0, 1440.0)
        presenter.set_display_bounds(wider)

        # The content-anchored clock re-anchors to the new right edge.
        clock_after = presenter.geometry_for("clock")
        assert clock_after is not None and clock_before is not None
        assert clock_after.x == pytest.approx(
            2560.0 - clock_after.width - 30.0
        )
        assert clock_after.x != pytest.approx(clock_before.x)
        # The committed-rect weather card is unaffected by topology.
        assert presenter.geometry_for("weather") == committed
    finally:
        presenter.retire()
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_presenter_binds_once_and_retires_idempotently(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 93)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        presenter = QuickDisplayPresenter(runtime, adapters=(ClockFamilyAdapter(),))
        presenter.bind_families(
            widgets_config={"clock": {"enabled": True}},
            display_bounds=_BOUNDS,
            shadow_values=_SHADOWS,
        )
        with pytest.raises(RuntimeError):
            presenter.bind_families(
                widgets_config={"clock": {"enabled": True}},
                display_bounds=_BOUNDS,
            )
        presenter.retire()
        assert host.live_count == 0
        presenter.retire()  # idempotent
        assert presenter.is_retired is True
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
