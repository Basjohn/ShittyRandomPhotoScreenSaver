"""H family/runtime binder bars.

These prove the thin per-display ordinary-family presentation binder connects the
existing destination pieces exactly once: the single display-owned
``WidgetRuntimeManager`` gates capability effectiveness, the existing
``Retained*Presentation`` constructors build items into the real
``OrdinaryWidgetPresentationHost``, per-instance ``enabled`` stays distinct from
family effectiveness, and retirement drops every held item exactly once.
"""

from __future__ import annotations

import pytest

from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.family_binder import (
    ClockFamilyAdapter,
    OrdinaryFamilyPresentationBinder,
)
from rendering.quick.widgets.host import OverlayWidgetGeometry


_DISPLAY_BOUNDS = OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0)


def _widgets_config(**overrides) -> dict:
    config = {
        "clock": {"enabled": True, "font_size": 48},
        "clock2": {"enabled": False},
        "clock3": {"enabled": False},
    }
    config.update(overrides)
    return config


def _geometry_resolver(widget_id: str) -> OverlayWidgetGeometry:
    lane = {"clock": 0, "clock2": 1, "clock3": 2}.get(widget_id, 0)
    return OverlayWidgetGeometry(120.0 + lane * 40.0, 90.0, 300.0, 160.0)


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


def _binder(runtime, **overrides) -> OrdinaryFamilyPresentationBinder:
    kwargs = dict(
        host=runtime.scene_controller.ordinary_widget_host,
        runtime_manager=runtime.widget_runtime_manager,
        geometry_resolver=_geometry_resolver,
        display_bounds=_DISPLAY_BOUNDS,
        display_identity="screen:a",
        shadow_values={"enabled": True, "direction": "SE"},
    )
    kwargs.update(overrides)
    return OrdinaryFamilyPresentationBinder(**kwargs)


@pytest.mark.qt
def test_binder_builds_only_enabled_instances_into_the_host(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 80)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        binder = _binder(runtime)

        built = binder.bind(_widgets_config(clock2={"enabled": True}))

        # clock + clock2 are enabled; clock3 stays off. Effectiveness admits the
        # family; per-instance enabled selects the instances.
        assert built == ("clock", "clock2")
        assert host.live_count == 2
        assert set(host.model_identities()) == {"clock", "clock2"}
        assert binder.live_count == 2
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_binder_retire_all_drops_every_item_exactly_once(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 81)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        binder = _binder(runtime)
        binder.bind(_widgets_config())
        assert host.live_count == 1

        binder.retire_all()
        assert host.live_count == 0
        assert binder.live_count == 0
        assert binder.is_retired is True

        # Idempotent: a second retire does not underflow the host.
        binder.retire_all()
        assert host.live_count == 0
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_binder_skips_family_when_capability_not_effective(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 82)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        binder = _binder(runtime)

        # Clock capability deactivated -> not effective -> nothing built even
        # though the instance is enabled.
        config = _widgets_config()
        config["family_activation"] = {"clocks": False}
        built = binder.bind(config)

        assert built == ()
        assert host.live_count == 0
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_binder_binds_once_per_generation(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 83)
    try:
        binder = _binder(runtime)
        binder.bind(_widgets_config())
        with pytest.raises(RuntimeError):
            binder.bind(_widgets_config())
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


def test_clock_adapter_enumerates_enabled_instances_without_qt() -> None:
    adapter = ClockFamilyAdapter()
    assert adapter.family_id == "clocks"
    assert adapter.enabled_instance_ids(_widgets_config()) == ("clock",)
    assert adapter.enabled_instance_ids(
        _widgets_config(clock2={"enabled": True}, clock3={"enabled": True})
    ) == ("clock", "clock2", "clock3")
    # A disabled base clock is honoured too.
    assert adapter.enabled_instance_ids({"clock": {"enabled": False}}) == ()
