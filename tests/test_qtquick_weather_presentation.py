"""F2 production-shaped gates for the retained Quick Weather family."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QObject
from PySide6.QtQml import QQmlEngine
from PySide6.QtQuick import QQuickItem

from rendering.quick.scene_controller import QuickSceneController, QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from rendering.quick.widgets.host import (
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from rendering.quick.widgets.weather import (
    RetainedWeatherPresentation,
    WeatherPresentationConfig,
    WeatherPresentationModel,
    WeatherPresentationStyle,
)
from rendering.quick.widgets.registry import (
    ORDINARY_WIDGET_FAMILY_COMPONENTS,
    ordinary_widget_family_component,
)
from rendering.quick.window import QuickDisplayWindow
from rendering.widget_runtime_manager import WidgetRuntimeManager
from widgets.weather_runtime import WeatherRuntimeService


ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"


class _FakeWeatherRuntime:
    def __init__(self, cached_data=None) -> None:
        self.consumer = None
        self.thread_manager = None
        self.location = ""
        self.cached_data = cached_data
        self.running = False
        self.retired = False
        self.start_calls: list[bool] = []
        self.fetch_calls = 0
        self.stop_calls = 0

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def detach_consumer(self, consumer=None) -> None:
        if consumer is None or consumer is self.consumer:
            self.consumer = None

    def set_thread_manager(self, thread_manager) -> None:
        self.thread_manager = thread_manager

    def set_location(self, location: str) -> None:
        next_location = str(location or "").strip()
        if next_location.casefold() != self.location.casefold():
            self.cached_data = None
        self.location = next_location
        if not next_location:
            self.running = False

    def has_cached_data(self) -> bool:
        return bool(self.cached_data)

    def get_cached_data(self):
        return self.cached_data

    def start(self, *, immediate_refresh_on_miss: bool = False) -> bool:
        self.start_calls.append(bool(immediate_refresh_on_miss))
        if self.retired or not self.location:
            return False
        self.running = True
        if self.cached_data and self.consumer is not None:
            self.consumer.on_weather_state(self.cached_data, from_cache=True)
        return True

    def stop(self) -> None:
        self.stop_calls += 1
        self.running = False

    def is_running(self) -> bool:
        return self.running and not self.retired

    def fetch_weather(self) -> None:
        self.fetch_calls += 1

    def publish(self, data, *, from_cache: bool = False) -> None:
        self.cached_data = dict(data)
        if self.consumer is not None:
            self.consumer.on_weather_state(self.cached_data, from_cache=from_cache)

    def fail(self, error: str) -> None:
        if self.consumer is not None:
            if self.cached_data:
                self.consumer.apply_weather_data(self.cached_data)
            self.consumer.on_weather_error(error)


class _RuntimeRegistryHost:
    def get_runtime_widget_registry(self):
        return {}


def _weather_values(**overrides):
    values = {
        "location": "Cape Town",
        "font_family": "Inter",
        "font_size": 25,
        "color": [245, 248, 252, 235],
        "show_background": True,
        "bg_color": [25, 32, 42, 255],
        "bg_opacity": 0.7,
        "border_color": [120, 195, 255, 255],
        "border_opacity": 0.9,
        "show_forecast": True,
        "show_condition_icon": True,
        "icon_alignment": "RIGHT",
        "icon_size": 96,
        "show_details_row": True,
        "detail_icon_size": 20,
    }
    values.update(overrides)
    return values


def _shadow_values(**overrides):
    values = {
        "enabled": True,
        "color": [0, 0, 0, 255],
        "blur_radius": 18,
        "frame_opacity": 0.77,
        "frame_extra_offset": 1,
        "text_enabled": True,
        "text_opacity": 0.4,
        "text_extra_offset": 1,
        "direction": "SE",
    }
    values.update(overrides)
    return values


def _sample(**overrides):
    values = {
        "temperature": 22.4,
        "condition": "partly cloudy",
        "location": "Cape Town",
        "weather_code": 2,
        "is_day": 1,
        "precipitation_probability": 17,
        "humidity": 68,
        "windspeed": 12.6,
        "forecast": "Tomorrow: 19°C, light rain",
    }
    values.update(overrides)
    return values


def _model(runtime=None, **config_overrides):
    config = WeatherPresentationConfig.from_mapping(
        _weather_values(**config_overrides)
    )
    style = WeatherPresentationStyle.project(config, _shadow_values())
    service = runtime or _FakeWeatherRuntime()
    return WeatherPresentationModel(config, style, service), service


def _create_host(factory: QuickSceneFactory, owner: QObject):
    context, root = factory.create_display_root(
        owner=owner,
        screen_index=0,
        runtime_generation=23,
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    assert host_item is not None
    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=factory.create_ordinary_widget_family,
    )
    return context, root, host


def _find_visual_item(root: QQuickItem, object_name: str) -> QQuickItem | None:
    if root.objectName() == object_name:
        return root
    for child in root.childItems():
        found = _find_visual_item(child, object_name)
        if found is not None:
            return found
    return None


def test_weather_config_and_style_project_canonical_settings_and_direction() -> None:
    config = WeatherPresentationConfig.from_widgets_mapping(
        {
            "weather": {
                "location": "  Johannesburg  ",
                "font_size": 31,
                "icon_alignment": "left",
                "show_details_row": "false",
                "bg_opacity": 0.5,
            }
        }
    )
    style = WeatherPresentationStyle.project(
        config,
        _shadow_values(direction="NW", frame_extra_offset=2, text_extra_offset=3),
    )

    assert config.location == "Johannesburg"
    assert config.font_size == 31
    assert config.icon_alignment == "LEFT"
    assert config.show_details_row is False
    assert style.card_style.shadow_offset_x == pytest.approx(-4.0)
    assert style.card_style.shadow_offset_y == pytest.approx(-4.0)
    assert style.card_style.shadow_extend_left == pytest.approx(2.0)
    assert style.card_style.shadow_extend_top == pytest.approx(2.0)
    assert style.card_style.shadow_extend_right == pytest.approx(0.0)
    assert style.card_style.shadow_extend_bottom == pytest.approx(0.0)
    assert style.text_shadow_offset_x == pytest.approx(-5.0)
    assert style.text_shadow_offset_y == pytest.approx(-5.0)
    assert style.card_style.background_color.alpha() == 128


def test_weather_model_is_stable_runtime_consumer_for_loading_ready_and_cached_error() -> None:
    model, runtime = _model()
    manager = object()

    model.activate(manager)
    assert model.is_active is True
    assert runtime.consumer is model
    assert runtime.thread_manager is manager
    assert runtime.start_calls == [False]
    assert model.viewState == "loading"
    assert model.weather_pending_first_show() is True

    runtime.publish(_sample())
    assert model.viewState == "ready"
    assert model.locationText == "Cape Town"
    assert model.conditionText == "22°C - Partly Cloudy"
    assert model.rainText == "17%"
    assert model.humidityText == "68%"
    assert model.windText == "12.6 km/h"
    assert model.detailIconSize == 30.0
    assert model.forecastText == "Tomorrow: 19°C, light rain"
    assert model.conditionIconSource.endswith("partly-cloudy-day.png")
    assert "/images/weather/presented/" in model.conditionIconSource.replace("\\", "/")
    assert "/images/weather/presented/detail/" in model.rainIconSource.replace("\\", "/")
    assert "/images/weather/presented/detail/" in model.humidityIconSource.replace("\\", "/")
    assert "/images/weather/presented/detail/" in model.windIconSource.replace("\\", "/")
    assert model.weather_pending_first_show() is False

    runtime.fail("offline")
    assert model.viewState == "ready"
    assert model.errorText == "offline"
    assert model.conditionText == "22°C - Partly Cloudy"

    model.retire()
    assert model.is_active is False
    assert runtime.consumer is None
    assert runtime.running is False


def test_weather_model_rebinds_same_location_cached_state_without_discarding_it() -> None:
    cached = _sample(temperature=16.0, condition="fog", weather_code=45)
    runtime = _FakeWeatherRuntime(cached)
    runtime.location = "Cape Town"
    model, _ = _model(runtime)

    model.activate(object())

    assert runtime.cached_data is cached
    assert model.viewState == "ready"
    assert model.conditionText == "16°C - Fog"
    assert model.conditionIconSource.endswith("fog-day.png")


def test_weather_model_manual_refresh_uses_real_runtime_when_updates_are_disabled(
    monkeypatch,
) -> None:
    cached = _sample()
    runtime = WeatherRuntimeService(runtime_generation=41)
    runtime._location = "Cape Town"
    runtime._cached_data = cached
    calls: list[str] = []
    monkeypatch.setattr(
        "widgets.weather_runtime.automatic_service_updates_enabled",
        lambda: False,
    )
    monkeypatch.setattr(runtime, "fetch_weather", lambda: calls.append("fetch"))
    model, _ = _model(runtime)

    model.activate(object())
    assert runtime._consumer() is model
    assert model.viewState == "ready"
    assert model.request_refresh() is True
    assert calls == ["fetch"]

    model.retire()
    assert runtime._consumer() is None


@pytest.mark.qt
def test_weather_real_runtime_owner_injects_model_through_current_scene_host(
    qt_app,
    monkeypatch,
) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=42,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    owner = WidgetRuntimeManager(_RuntimeRegistryHost())
    config = WeatherPresentationConfig.from_mapping(_weather_values())
    style = WeatherPresentationStyle.project(config, _shadow_values())
    model = WeatherPresentationModel(config, style)
    service = owner.ensure_widget_service(
        "weather",
        model,
        {"weather": {"location": config.location}},
    )
    assert isinstance(service, WeatherRuntimeService)
    service._location = config.location
    service._cached_data = _sample()
    fetches: list[str] = []
    monkeypatch.setattr(
        "widgets.weather_runtime.automatic_service_updates_enabled",
        lambda: False,
    )
    monkeypatch.setattr(service, "fetch_weather", lambda: fetches.append("fetch"))
    try:
        presentation = RetainedWeatherPresentation(
            host=controller.ordinary_widget_host,
            model=model,
            geometry=OverlayWidgetGeometry(25.0, 30.0, 460.0, 300.0),
        )
        item = presentation.item
        engine = QQmlEngine.contextForObject(item).engine()

        presentation.activate(object())
        item.refreshRequested.emit()
        qt_app.processEvents()

        assert owner.get_widget_service("weather") is service
        assert service._consumer() is model
        assert service.is_running() is True
        assert model.viewState == "ready"
        assert model.conditionText == "22°C - Partly Cloudy"
        assert presentation.item is item
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert fetches == ["fetch"]

        controller.quiesce_for_retirement()
        assert service._consumer() is None
        assert service.is_running() is False
        assert owner.get_reusable_widget_service("weather", model) is None
        assert service.is_retired() is True
    finally:
        controller.quiesce_for_retirement()
        owner.cleanup()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()

    assert service.is_retired() is True


def test_weather_model_covers_missing_location_error_and_location_recovery_in_place() -> None:
    runtime = _FakeWeatherRuntime()
    model, _ = _model(runtime, location="")
    manager = object()
    model.activate(manager)

    assert model.viewState == "missing"
    assert model.locationText == "Weather location required"
    assert model.conditionText == "Open Weather Settings"
    assert runtime.start_calls == []

    published: list[str] = []
    model.stateChanged.connect(lambda: published.append(model.viewState))
    configured = replace(model.config, location="Durban")
    assert model.apply_config(configured) is True
    assert published == ["loading"]
    assert model.viewState == "loading"
    assert runtime.location == "Durban"
    assert runtime.start_calls == [True]

    runtime.fail("network unavailable")
    assert model.viewState == "error"
    assert model.conditionText == "Weather unavailable"
    assert model.errorText == "network unavailable"

    runtime.publish(_sample(location="Durban", condition="clear", weather_code=0))
    assert model.viewState == "ready"
    assert model.locationText == "Durban"
    assert model.conditionIconSource.endswith("clear-day.png")


@pytest.mark.qt
def test_weather_family_uses_current_scene_host_and_mutates_without_recreation(qt_app) -> None:
    screen = qt_app.primaryScreen()
    assert screen is not None
    window = QuickDisplayWindow(
        screen_index=0,
        runtime_generation=31,
        screen=screen,
        policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
    )
    factory = QuickSceneFactory()
    controller = QuickSceneController(window=window, factory=factory)
    runtime = _FakeWeatherRuntime()
    model, _ = _model(runtime)
    settings_targets: list[str] = []
    try:
        presentation = RetainedWeatherPresentation(
            host=controller.ordinary_widget_host,
            model=model,
            geometry=OverlayWidgetGeometry(40.0, 35.0, 460.0, 300.0),
            on_settings_requested=settings_targets.append,
        )
        item = presentation.item
        engine = QQmlEngine.contextForObject(item).engine()
        presentation.activate(object())
        runtime.publish(_sample())
        qt_app.processEvents()

        assert item.parentItem() is not None
        assert _find_visual_item(item, "weatherReadyContent") is not None
        assert _find_visual_item(item, "weatherConditionIconRight") is not None
        assert model.viewState == "ready"

        next_config = replace(
            model.config,
            font_size=34,
            icon_alignment="LEFT",
            show_background=False,
            show_forecast=False,
        )
        presentation.apply_config(
            next_config,
            _shadow_values(direction="W", text_extra_offset=2),
        )
        runtime.publish(_sample(temperature=18.0, condition="rain", weather_code=61))
        item.settingsRequested.emit("weather_location")
        item.refreshRequested.emit()
        qt_app.processEvents()

        assert presentation.item is item
        assert presentation.model is model
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert runtime.consumer is model
        assert model.fontSize == 34.0
        assert model.iconAlignment == "LEFT"
        assert model.showForecast is False
        assert model.conditionText == "18°C - Rain"
        assert model.textShadowOffsetX == pytest.approx(-4.0)
        assert model.textShadowOffsetY == pytest.approx(0.0)
        assert item.property("cardShellEnabled") is False
        assert settings_targets == ["weather_location"]
        assert runtime.fetch_calls == 1

        controller.quiesce_for_retirement()
        assert runtime.consumer is None
        assert runtime.running is False
    finally:
        controller.quiesce_for_retirement()
        window.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()


def test_weather_qml_and_registry_are_static_presentation_only() -> None:
    qml = (QML_ROOT / "WeatherPresentation.qml").read_text(encoding="utf-8")
    banned = (
        "Timer {",
        "SettingsManager",
        "WeatherRuntimeService",
        "OpenMeteoProvider",
        "QWidget",
        "MultiEffect",
        "layer.enabled",
    )
    for marker in banned:
        assert marker not in qml
    # Weather keeps native packaged texture resolution so high-DPI rendering does
    # not decode a 96 px source and then upscale it on a 150%/200% display.
    assert "sourceSize." not in qml
    assert "legacyHorizontalInset: 10.0" in qml
    assert "68.0" in qml
    for asset in (
        ROOT / "images" / "weather" / "presented" / "overcast-day.png",
        ROOT / "images" / "weather" / "presented" / "clear-night.png",
        ROOT / "images" / "weather" / "presented" / "detail" / "umbrella.png",
        ROOT / "images" / "weather" / "presented" / "detail" / "humidity.png",
        ROOT / "images" / "weather" / "presented" / "detail" / "wind.png",
    ):
        assert asset.is_file(), asset
    assert "WeatherPresentation 1.0 WeatherPresentation.qml" in (
        QML_ROOT / "qmldir"
    ).read_text(encoding="utf-8")

    weather_descriptors = [
        descriptor
        for descriptor in ORDINARY_WIDGET_FAMILY_COMPONENTS
        if descriptor.family_id == "weather"
    ]
    assert len(weather_descriptors) == 1
    descriptor = ordinary_widget_family_component("weather")
    assert descriptor.qml_filename == "WeatherPresentation.qml"
    assert descriptor.presentation_model_kind == "WeatherPresentationModel"
