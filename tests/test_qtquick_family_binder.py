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
    AbandonmentIssuesFamilyAdapter,
    AchievementPulseFamilyAdapter,
    ClockFamilyAdapter,
    GmailFamilyAdapter,
    MediaFamilyAdapter,
    OrdinaryFamilyPresentationBinder,
    RedditFamilyAdapter,
    WeatherFamilyAdapter,
    default_ordinary_family_adapters,
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
        binder = _binder(runtime, adapters=(ClockFamilyAdapter(),))

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
        binder = _binder(runtime, adapters=(ClockFamilyAdapter(),))
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
        binder = _binder(runtime, adapters=(ClockFamilyAdapter(),))

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
        binder = _binder(runtime, adapters=(ClockFamilyAdapter(),))
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


def test_default_adapter_set_covers_every_wired_family_without_qt() -> None:
    families = [adapter.family_id for adapter in default_ordinary_family_adapters()]
    # Two Steam-family instances share the one capability family id.
    assert families == [
        "clocks",
        "weather",
        "media",
        "reddit",
        "gmail",
        "steam",
        "steam",
    ]


def test_reddit_adapter_enumerates_both_members_without_qt() -> None:
    adapter = RedditFamilyAdapter()
    assert adapter.family_id == "reddit"
    assert adapter.enabled_instance_ids(
        {"reddit": {"enabled": True}, "reddit2": {"enabled": True}}
    ) == ("reddit", "reddit2")
    assert adapter.enabled_instance_ids(
        {"reddit": {"enabled": True}, "reddit2": {"enabled": False}}
    ) == ("reddit",)


def test_steam_adapters_are_off_by_default_and_gate_on_enable_without_qt() -> None:
    achievement = AchievementPulseFamilyAdapter()
    abandonment = AbandonmentIssuesFamilyAdapter()
    assert achievement.family_id == "steam"
    assert abandonment.family_id == "steam"
    # Canonical default is disabled for both Steam cards.
    assert achievement.enabled_instance_ids({}) == ()
    assert abandonment.enabled_instance_ids({}) == ()
    assert achievement.enabled_instance_ids(
        {"achievement_pulse": {"enabled": True}}
    ) == ("achievement_pulse",)
    assert abandonment.enabled_instance_ids(
        {"abandonment_issues": {"enabled": True}}
    ) == ("abandonment_issues",)


@pytest.mark.qt
def test_provider_families_build_with_owned_runtime_services(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 84)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        manager = runtime.widget_runtime_manager
        binder = _binder(
            runtime,
            adapters=(WeatherFamilyAdapter(), GmailFamilyAdapter()),
        )

        built = binder.bind(
            {"weather": {"enabled": True}, "gmail": {"enabled": True}}
        )

        assert built == ("weather", "gmail")
        assert host.live_count == 2
        # The single display-owned neutral manager owns each instance's service.
        assert manager.get_widget_service("weather") is not None
        assert manager.get_widget_service("gmail") is not None
    finally:
        # Closing the runtime retires the neutral services exactly once.
        runtime.close_runtime()
        assert manager.is_retired is True
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_media_card_builds_with_all_three_owned_leases(qt_app) -> None:
    runtime, factory = _make_runtime(qt_app, 87)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        manager = runtime.widget_runtime_manager
        binder = _binder(
            runtime,
            adapters=(MediaFamilyAdapter(),),
            runtime_generation=87,
        )

        built = binder.bind({"media": {"enabled": True, "provider": "spotify"}})

        assert built == ("media",)
        assert host.live_count == 1
        # The single card owns three neutral leases through the one manager.
        assert manager.get_widget_service("media") is not None
        assert manager.get_widget_service("spotify_volume") is not None
        assert manager.get_widget_service("mute_button") is not None
    finally:
        runtime.close_runtime()
        assert manager.is_retired is True
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_steam_family_gated_off_builds_nothing_but_enabling_admits_card(
    qt_app,
) -> None:
    runtime, factory = _make_runtime(qt_app, 85)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        binder = _binder(runtime, adapters=(AchievementPulseFamilyAdapter(),))

        # Default: Steam card disabled -> nothing built.
        built = binder.bind({})
        assert built == ()
        assert host.live_count == 0
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()

    runtime, factory = _make_runtime(qt_app, 86)
    try:
        host = runtime.scene_controller.ordinary_widget_host
        binder = _binder(runtime, adapters=(AchievementPulseFamilyAdapter(),))
        built = binder.bind({"achievement_pulse": {"enabled": True}})
        assert built == ("achievement_pulse",)
        assert host.live_count == 1
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
