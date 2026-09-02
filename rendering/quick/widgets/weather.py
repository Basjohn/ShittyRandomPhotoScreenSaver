"""Stable retained Weather presentation model and packaged-icon bridge.

``WeatherRuntimeService`` keeps provider, cache, refresh, retry and generation
ownership.  This module implements only its detached consumer protocol and
projects accepted state into one retained QML item.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, Signal
from PySide6.QtGui import QColor

from core.settings.shadow_direction import (
    resolve_directional_extensions,
    resolve_signed_offset,
)

from .theme_projection import resolve_card_surface_colors, resolve_rgba_role

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)


_WEATHER_ICON_DIR = Path(__file__).resolve().parents[3] / "images" / "weather"
_WEATHER_SETTINGS_TARGET = "weather_location"
_WEATHER_CODE_ICON_MAP: tuple[tuple[frozenset[int], str], ...] = (
    (frozenset({0}), "clear-day.png"),
    (frozenset({1, 2}), "partly-cloudy-day.png"),
    (frozenset({3}), "overcast-day.png"),
    (frozenset({45, 48}), "fog-day.png"),
    (frozenset({51, 53, 55, 56, 57}), "drizzle.png"),
    (frozenset({61, 63, 65, 80, 81, 82}), "rain.png"),
    (frozenset({66, 67}), "hail.png"),
    (frozenset({71, 73, 75, 77, 85, 86}), "snow.png"),
    (frozenset({95, 96, 99}), "thunderstorms-day.png"),
)
_CONDITION_ICON_MAP: tuple[tuple[str, str], ...] = (
    ("clear", "clear-day.png"),
    ("partly", "partly-cloudy-day.png"),
    ("overcast", "overcast-day.png"),
    ("cloud", "partly-cloudy-day.png"),
    ("fog", "fog-day.png"),
    ("haze", "haze-day.png"),
    ("smoke", "smoke.png"),
    ("drizzle", "drizzle.png"),
    ("rain", "rain.png"),
    ("snow", "snow.png"),
    ("sleet", "partly-cloudy-day-sleet.png"),
    ("thunder", "thunderstorms-day-rain.png"),
)
_DETAIL_ICON_FILES = {
    "rain": "umbrella.png",
    "humidity": "humidity.png",
    "wind": "wind.png",
}


def _bounded_float(value: object, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(low, min(high, parsed))


def _bounded_int(value: object, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(low, min(high, parsed))


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _rgba(value: object, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if isinstance(value, QColor):
        color = QColor(value)
    elif isinstance(value, (tuple, list)) and len(value) in {3, 4}:
        channels = list(value)
        if len(channels) == 3:
            channels.append(255)
        try:
            color = QColor(*(max(0, min(255, int(channel))) for channel in channels))
        except (TypeError, ValueError):
            color = QColor(*default)
    else:
        color = QColor(str(value)) if value is not None else QColor()
    if not color.isValid():
        color = QColor(*default)
    return color.red(), color.green(), color.blue(), color.alpha()


def _with_alpha(rgba: tuple[int, int, int, int], scale: float) -> QColor:
    color = QColor(*rgba)
    color.setAlpha(max(0, min(255, int(round(color.alpha() * float(scale))))))
    return color


def _optional_float(value: object) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _file_source(filename: str) -> str:
    path = _WEATHER_ICON_DIR / filename
    return path.resolve().as_uri() if path.is_file() else ""


def _condition_icon_source(
    weather_code: object,
    condition: str,
    is_day: bool,
) -> str:
    icon_name = ""
    try:
        code = int(weather_code) if weather_code is not None else None
    except (TypeError, ValueError):
        code = None
    if code is not None:
        for codes, candidate in _WEATHER_CODE_ICON_MAP:
            if code in codes:
                icon_name = candidate
                break
    if not icon_name:
        lowered = condition.lower()
        for keyword, candidate in _CONDITION_ICON_MAP:
            if keyword in lowered:
                icon_name = candidate
                break
    if not icon_name:
        return ""
    candidates = [icon_name]
    if not is_day:
        if "-day" in icon_name:
            candidates.insert(0, icon_name.replace("-day", "-night"))
        elif icon_name.endswith(".png"):
            candidates.insert(0, f"{icon_name[:-4]}-night.png")
    for candidate in candidates:
        source = _file_source(candidate)
        if source:
            return source
    return ""


@dataclass(frozen=True)
class WeatherPresentationConfig:
    """Resolved presentation inputs for one Weather instance."""

    widget_id: str = "weather"
    location: str = ""
    font_family: str = "Inter"
    font_size: int = 25
    text_color: tuple[int, int, int, int] = (255, 255, 255, 230)
    show_background: bool = True
    background_color: tuple[int, int, int, int] = (35, 35, 35, 255)
    background_opacity: float = 0.3
    border_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    border_opacity: float = 1.0
    show_forecast: bool = True
    show_condition_icon: bool = True
    icon_alignment: str = "RIGHT"
    icon_size: int = 96
    show_details_row: bool = True
    detail_icon_size: int = 16

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[str, object],
        *,
        widget_id: str = "weather",
    ) -> "WeatherPresentationConfig":
        alignment = str(values.get("icon_alignment", "RIGHT") or "RIGHT").upper()
        if alignment not in {"LEFT", "RIGHT", "NONE"}:
            alignment = "RIGHT"
        return cls(
            widget_id=str(widget_id or "weather"),
            location=str(values.get("location", "") or "").strip(),
            font_family=str(values.get("font_family", "Inter") or "Inter"),
            font_size=_bounded_int(values.get("font_size"), 25, 8, 256),
            text_color=_rgba(values.get("color"), (255, 255, 255, 230)),
            show_background=_as_bool(values.get("show_background"), True),
            background_color=_rgba(values.get("bg_color"), (35, 35, 35, 255)),
            background_opacity=_bounded_float(values.get("bg_opacity"), 0.3, 0.0, 1.0),
            border_color=_rgba(values.get("border_color"), (255, 255, 255, 255)),
            border_opacity=_bounded_float(values.get("border_opacity"), 1.0, 0.0, 1.0),
            show_forecast=_as_bool(values.get("show_forecast"), True),
            show_condition_icon=_as_bool(values.get("show_condition_icon"), True),
            icon_alignment=alignment,
            icon_size=_bounded_int(values.get("icon_size"), 96, 32, 256),
            show_details_row=_as_bool(values.get("show_details_row"), True),
            detail_icon_size=_bounded_int(values.get("detail_icon_size"), 16, 8, 96),
        )

    @classmethod
    def from_widgets_mapping(
        cls,
        widgets: Mapping[str, object],
    ) -> "WeatherPresentationConfig":
        """Project canonical Weather settings without leaking persistence ownership."""

        from core.settings.defaults import get_default_settings

        defaults = get_default_settings().get("widgets", {}).get("weather", {})
        values = widgets.get("weather", {})
        if not isinstance(defaults, Mapping):
            defaults = {}
        if not isinstance(values, Mapping):
            values = {}
        merged = dict(defaults)
        merged.update(values)
        config = cls.from_mapping(merged)
        card_background, card_border = resolve_card_surface_colors(
            values=values,
            defaults=defaults,
            background_color=config.background_color,
            background_opacity=config.background_opacity,
            border_color=config.border_color,
            border_opacity=config.border_opacity,
        )
        return replace(
            config,
            background_color=card_background,
            background_opacity=1.0,
            border_color=card_border,
            border_opacity=1.0,
        )


@dataclass(frozen=True)
class WeatherPresentationStyle:
    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float

    @classmethod
    def project(
        cls,
        config: WeatherPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "WeatherPresentationStyle":
        direction = shadow_values.get("direction", "SE")
        frame_extra = _bounded_float(
            shadow_values.get("frame_extra_offset"), 0.0, 0.0, 40.0
        )
        text_extra = _bounded_float(
            shadow_values.get("text_extra_offset"), 0.0, 0.0, 40.0
        )
        card_offset = resolve_signed_offset(direction, *ORDINARY_CARD_SHADOW_BASE)
        card_extensions = resolve_directional_extensions(direction, frame_extra)
        text_offset = resolve_signed_offset(
            direction,
            ORDINARY_TEXT_SHADOW_BASE[0] + text_extra,
            ORDINARY_TEXT_SHADOW_BASE[1] + text_extra,
        )
        shadow_rgba = _rgba(shadow_values.get("color"), (0, 0, 0, 255))
        frame_opacity = _bounded_float(
            shadow_values.get("frame_opacity"), 0.77, 0.0, 1.0
        )
        text_opacity = _bounded_float(
            shadow_values.get("text_opacity"), 0.33, 0.0, 1.0
        )
        return cls(
            card_style=OverlayCardStyle(
                shell_enabled=config.show_background,
                background_color=_with_alpha(
                    config.background_color, config.background_opacity
                ),
                border_color=_with_alpha(config.border_color, config.border_opacity),
                border_width=max(0.0, float(border_width)),
                corner_radius=8.0,
                padding=14.0,
                shadow_enabled=(
                    config.show_background
                    and _as_bool(shadow_values.get("enabled"), True)
                ),
                shadow_color=_with_alpha(shadow_rgba, frame_opacity),
                shadow_blur=_bounded_float(
                    shadow_values.get("blur_radius"), 18.0, 0.0, 80.0
                ),
                shadow_offset_x=card_offset[0],
                shadow_offset_y=card_offset[1],
                shadow_extend_left=card_extensions[0],
                shadow_extend_top=card_extensions[1],
                shadow_extend_right=card_extensions[2],
                shadow_extend_bottom=card_extensions[3],
            ),
            text_shadow_enabled=_as_bool(
                shadow_values.get("text_enabled"), True
            ),
            text_shadow_color=_with_alpha(shadow_rgba, text_opacity),
            text_shadow_offset_x=text_offset[0],
            text_shadow_offset_y=text_offset[1],
        )


@dataclass(frozen=True)
class WeatherPresentationSnapshot:
    config: WeatherPresentationConfig
    style: WeatherPresentationStyle
    view_state: str
    location_text: str
    condition_text: str
    forecast_text: str
    error_text: str
    condition_icon_source: str
    rain_text: str
    humidity_text: str
    wind_text: str
    from_cache: bool


def _initial_snapshot(
    config: WeatherPresentationConfig,
    style: WeatherPresentationStyle,
) -> WeatherPresentationSnapshot:
    missing = not bool(config.location)
    return WeatherPresentationSnapshot(
        config=config,
        style=style,
        view_state="missing" if missing else "loading",
        location_text="Weather location required" if missing else config.location.title(),
        condition_text="Open Weather Settings" if missing else "Loading weather…",
        forecast_text="",
        error_text="",
        condition_icon_source="",
        rain_text="0%",
        humidity_text="0%",
        wind_text="0.0 km/h",
        from_cache=False,
    )


class WeatherPresentationModel(QObject):
    """Stable Weather runtime consumer and QML-facing state model."""

    stateChanged = Signal()

    def __init__(
        self,
        config: WeatherPresentationConfig,
        style: WeatherPresentationStyle,
        runtime_service: Any | None = None,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._runtime_service = runtime_service
        self._snapshot = _initial_snapshot(config, style)
        self._active = False
        self._retired = False

    def set_runtime_service(self, runtime_service: Any) -> None:
        """Accept the neutral owner injected by ``WidgetRuntimeManager``."""

        if self._retired:
            raise RuntimeError("cannot inject a retired Weather presentation model")
        if self._active and runtime_service is not self._runtime_service:
            raise RuntimeError("cannot replace the active Weather runtime service")
        self._runtime_service = runtime_service

    @property
    def config(self) -> WeatherPresentationConfig:
        return self._snapshot.config

    @property
    def style(self) -> WeatherPresentationStyle:
        return self._snapshot.style

    @property
    def is_active(self) -> bool:
        return self._active and not self._retired

    def activate(self, thread_manager: Any) -> None:
        if self._retired:
            raise RuntimeError("cannot activate a retired Weather presentation model")
        if self._active:
            return
        service = self._runtime_service
        if service is None:
            raise RuntimeError("Weather runtime service is not configured")
        service.attach_consumer(self)
        service.set_thread_manager(thread_manager)
        current_location = str(getattr(service, "location", "") or "").strip()
        if current_location.casefold() != self.config.location.casefold():
            service.set_location(self.config.location)
        self._active = True
        if not self.config.location:
            service.stop()
            self._replace_snapshot(_initial_snapshot(self.config, self.style))
            return
        if not service.has_cached_data():
            self._replace_snapshot(_initial_snapshot(self.config, self.style))
        if not service.start(immediate_refresh_on_miss=False):
            self.on_weather_error("Weather runtime service failed to start")

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._active = False
        service = self._runtime_service
        if service is None:
            return
        service.stop()
        service.detach_consumer(self)

    def apply_config(self, config: WeatherPresentationConfig) -> bool:
        if config == self.config:
            return False
        previous_location = self.config.location
        if config.location != previous_location:
            # Publish the new location and its loading/missing state as one
            # coherent snapshot; never expose new config with old-place data.
            self._snapshot = replace(self._snapshot, config=config)
            self._apply_location_change(config.location)
        else:
            self._replace_snapshot(replace(self._snapshot, config=config))
        return True

    def _apply_location_change(self, location: str) -> None:
        service = self._runtime_service
        if service is None:
            self._replace_snapshot(_initial_snapshot(self.config, self.style))
            return
        was_running = service.is_running()
        service.set_location(location)
        self._replace_snapshot(_initial_snapshot(self.config, self.style))
        if not self.is_active or not location:
            service.stop()
            return
        if was_running and service.is_running():
            service.fetch_weather()
        elif not service.start(immediate_refresh_on_miss=True):
            self.on_weather_error("Weather runtime service failed to start")

    def apply_style(self, style: WeatherPresentationStyle) -> bool:
        if style == self.style:
            return False
        self._replace_snapshot(replace(self._snapshot, style=style))
        return True

    def is_weather_consumer_alive(self) -> bool:
        return self.is_active

    def weather_pending_first_show(self) -> bool:
        return self.is_active and self._snapshot.view_state == "loading"

    def request_refresh(self) -> bool:
        """Request the existing runtime owner to perform a manual refresh."""

        if (
            not self.is_active
            or not self.config.location
            or self._runtime_service is None
        ):
            return False
        try:
            self._runtime_service.fetch_weather()
        except Exception:
            return False
        return True

    def on_weather_state(self, data: Mapping[str, Any], *, from_cache: bool) -> None:
        if not self.is_weather_consumer_alive():
            return
        self._publish_data(data, from_cache=from_cache)

    def apply_weather_data(self, data: Mapping[str, Any]) -> None:
        if not self.is_weather_consumer_alive():
            return
        self._publish_data(data, from_cache=self._snapshot.from_cache)

    def on_weather_error(self, error: str) -> None:
        if not self.is_weather_consumer_alive():
            return
        if self._snapshot.view_state == "ready":
            self._replace_snapshot(replace(self._snapshot, error_text=str(error)))
            return
        self._replace_snapshot(
            replace(
                self._snapshot,
                view_state="error",
                condition_text="Weather unavailable",
                error_text=str(error),
            )
        )

    def _publish_data(self, data: Mapping[str, Any], *, from_cache: bool) -> None:
        temperature = data.get("temperature")
        condition = data.get("condition")
        location = data.get("location") or data.get("name") or self.config.location
        weather_code = data.get("weather_code")
        is_day = data.get("is_day", 1)
        if temperature is None and isinstance(data.get("main"), Mapping):
            temperature = data["main"].get("temp")
        if condition is None and isinstance(data.get("weather"), list) and data["weather"]:
            weather_entry = data["weather"][0]
            if isinstance(weather_entry, Mapping):
                condition = weather_entry.get("main") or weather_entry.get("description")
                weather_code = weather_entry.get("id") or weather_code
                is_day = weather_entry.get("is_day", is_day)
        temp = _optional_float(temperature)
        temp = 0.0 if temp is None else temp
        condition_text = str(condition or "Unknown").title()
        try:
            is_day_value = bool(int(is_day))
        except (TypeError, ValueError):
            is_day_value = bool(is_day)
        precipitation = _optional_float(data.get("precipitation_probability"))
        humidity = _optional_float(data.get("humidity"))
        wind = _optional_float(data.get("windspeed"))
        if humidity is None and isinstance(data.get("main"), Mapping):
            humidity = _optional_float(data["main"].get("humidity"))
        if wind is None and isinstance(data.get("wind"), Mapping):
            wind = _optional_float(data["wind"].get("speed"))
        self._replace_snapshot(
            replace(
                self._snapshot,
                view_state="ready",
                location_text=str(location or self.config.location).title(),
                condition_text=f"{temp:.0f}°C - {condition_text}",
                forecast_text=str(data.get("forecast") or ""),
                error_text="",
                condition_icon_source=_condition_icon_source(
                    weather_code, condition_text, is_day_value
                ),
                rain_text=f"{(precipitation or 0.0):.0f}%",
                humidity_text=f"{(humidity or 0.0):.0f}%",
                wind_text=f"{(wind or 0.0):.1f} km/h",
                from_cache=bool(from_cache),
            )
        )

    def _replace_snapshot(self, snapshot: WeatherPresentationSnapshot) -> None:
        if snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        self.stateChanged.emit()

    @Property(str, notify=stateChanged)
    def viewState(self) -> str:
        return self._snapshot.view_state

    @Property(str, notify=stateChanged)
    def locationText(self) -> str:
        return self._snapshot.location_text

    @Property(str, notify=stateChanged)
    def conditionText(self) -> str:
        return self._snapshot.condition_text

    @Property(str, notify=stateChanged)
    def forecastText(self) -> str:
        return self._snapshot.forecast_text

    @Property(str, notify=stateChanged)
    def errorText(self) -> str:
        return self._snapshot.error_text

    @Property(str, notify=stateChanged)
    def conditionIconSource(self) -> str:
        return self._snapshot.condition_icon_source

    @Property(str, notify=stateChanged)
    def rainIconSource(self) -> str:
        return _file_source(_DETAIL_ICON_FILES["rain"])

    @Property(str, notify=stateChanged)
    def humidityIconSource(self) -> str:
        return _file_source(_DETAIL_ICON_FILES["humidity"])

    @Property(str, notify=stateChanged)
    def windIconSource(self) -> str:
        return _file_source(_DETAIL_ICON_FILES["wind"])

    @Property(str, notify=stateChanged)
    def rainText(self) -> str:
        return self._snapshot.rain_text

    @Property(str, notify=stateChanged)
    def humidityText(self) -> str:
        return self._snapshot.humidity_text

    @Property(str, notify=stateChanged)
    def windText(self) -> str:
        return self._snapshot.wind_text

    @Property(str, notify=stateChanged)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(float, notify=stateChanged)
    def fontSize(self) -> float:
        return float(self.config.font_size)

    @Property(float, notify=stateChanged)
    def conditionFontSize(self) -> float:
        return float(max(10, int(self.config.font_size * 0.8)))

    @Property(float, notify=stateChanged)
    def detailFontSize(self) -> float:
        return float(max(8, int(self.config.font_size * 0.5)))

    @Property(QColor, notify=stateChanged)
    def textColor(self) -> QColor:
        return QColor(*self.config.text_color)

    @Property(str, notify=stateChanged)
    def iconAlignment(self) -> str:
        return self.config.icon_alignment

    @Property(float, notify=stateChanged)
    def iconSize(self) -> float:
        return float(self.config.icon_size)

    @Property(float, notify=stateChanged)
    def detailIconSize(self) -> float:
        return float(max(30, self.config.detail_icon_size))

    @Property(bool, notify=stateChanged)
    def showConditionIcon(self) -> bool:
        return (
            self._snapshot.view_state == "ready"
            and self.config.show_condition_icon
            and self.config.icon_alignment != "NONE"
            and bool(self._snapshot.condition_icon_source)
        )

    @Property(bool, notify=stateChanged)
    def showDetails(self) -> bool:
        return self._snapshot.view_state == "ready" and self.config.show_details_row

    @Property(bool, notify=stateChanged)
    def showForecast(self) -> bool:
        return (
            self._snapshot.view_state == "ready"
            and self.config.show_forecast
            and bool(self._snapshot.forecast_text)
        )

    @Property(bool, notify=stateChanged)
    def textShadowEnabled(self) -> bool:
        return self.style.text_shadow_enabled

    @Property(QColor, notify=stateChanged)
    def textShadowColor(self) -> QColor:
        return QColor(self.style.text_shadow_color)

    @Property(float, notify=stateChanged)
    def textShadowOffsetX(self) -> float:
        return self.style.text_shadow_offset_x

    @Property(float, notify=stateChanged)
    def textShadowOffsetY(self) -> float:
        return self.style.text_shadow_offset_y

    @Property(QColor, notify=stateChanged)
    def separatorColor(self) -> QColor:
        color = QColor(*self.config.text_color)
        color.setAlpha(max(0, min(255, int(round(color.alpha() * 0.55)))))
        fallback = (color.red(), color.green(), color.blue(), color.alpha())
        resolved = resolve_rgba_role(
            "weather.separator",
            local_roles={"local.separator": fallback},
            fallback=fallback,
        )
        return QColor(*resolved)


class RetainedWeatherPresentation:
    """One retained Weather item bound to one neutral runtime service."""

    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: WeatherPresentationModel,
        geometry: OverlayWidgetGeometry,
        fade_opacity: float = 1.0,
        on_settings_requested: Callable[[str], None] | None = None,
    ) -> None:
        self._model = model
        self._on_settings_requested = on_settings_requested
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "weather",
            initial_properties={"weatherModel": model},
            object_name=model.config.widget_id,
            model_identity=model.config.widget_id,
            geometry=geometry,
            fade_opacity=fade_opacity,
            card_style=model.style.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(
            self._apply_custom_layout_size_payload
        )
        signal = getattr(self._retained.item, "settingsRequested", None)
        if signal is not None and hasattr(signal, "connect"):
            signal.connect(self._handle_settings_requested)
        refresh_signal = getattr(self._retained.item, "refreshRequested", None)
        if refresh_signal is not None and hasattr(refresh_signal, "connect"):
            refresh_signal.connect(self._model.request_refresh)

    @property
    def item(self):
        return self._retained.item

    @property
    def model(self) -> WeatherPresentationModel:
        return self._model

    def activate(self, thread_manager: Any) -> None:
        self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def _apply_custom_layout_size_payload(
        self,
        payload: Mapping[str, object],
    ) -> None:
        config = self._model.config
        self._model.apply_config(
            replace(
                config,
                font_size=int(payload.get("font_size", config.font_size)),
                icon_size=int(payload.get("icon_size", config.icon_size)),
                detail_icon_size=int(
                    payload.get("detail_icon_size", config.detail_icon_size)
                ),
            )
        )

    def set_fade_opacity(self, opacity: float) -> None:
        self._retained.set_fade_opacity(opacity)

    def apply_config(
        self,
        config: WeatherPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> None:
        self._model.apply_config(config)
        style = WeatherPresentationStyle.project(
            config,
            shadow_values,
            border_width=border_width,
        )
        self._model.apply_style(style)
        self._retained.set_card_style(style.card_style)

    def _handle_settings_requested(self, target: str) -> None:
        if self._on_settings_requested is not None:
            self._on_settings_requested(str(target))

    def retire(self) -> bool:
        return self._retained.retire()


__all__ = [
    "RetainedWeatherPresentation",
    "WeatherPresentationConfig",
    "WeatherPresentationModel",
    "WeatherPresentationSnapshot",
    "WeatherPresentationStyle",
]
