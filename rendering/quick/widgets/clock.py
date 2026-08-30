"""Stable retained Clock-family presentation model and geometry seam.

The model owns presentation-ready time text, calendar text, hand angles and
resolved style values. It deliberately owns no SettingsManager, QWidget,
provider or persistence object. ``GlobalClockTicker`` remains the sole cadence
owner and the model subscribes only while its retained presentation is live.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone, tzinfo
import time
from typing import Any

from PySide6.QtCore import QObject, Property, Signal
from PySide6.QtGui import QColor

from core.settings.shadow_direction import resolve_signed_offset
from widgets.clock_ticker import GlobalClockTicker, get_global_clock_ticker

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
)

try:
    import pytz
except ImportError:  # pragma: no cover - the frozen/runtime dependency is present
    pytz = None


_WEEKDAYS = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
)

# Family-authored analogue relationships protected by the F1 Clock contract.
_ANALOG_RING_SHADOW_BASE = (3.0, 3.0)
_ANALOG_HAND_SHADOW_BASE = (4.0, 4.0)
_ANALOG_NUMERAL_CONTACT_BASE = (1.0, 1.0)


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


def _with_alpha(
    rgba: tuple[int, int, int, int],
    alpha_scale: float,
) -> QColor:
    color = QColor(*rgba)
    color.setAlpha(
        max(0, min(255, int(round(color.alpha() * float(alpha_scale)))))
    )
    return color


def normalize_clock_display_mode(value: object) -> str:
    return "analog" if str(value or "").strip().lower() == "analog" else "digital"


@dataclass(frozen=True)
class ClockPresentationConfig:
    """Resolved presentation inputs for one logical Clock instance."""

    widget_id: str = "clock"
    time_format: str = "12h"
    show_seconds: bool = True
    timezone_name: str = "local"
    show_timezone: bool = False
    show_day_of_week: bool = False
    show_date: bool = False
    show_separator: bool = False
    calendar_layout: str = "shared_line"
    calendar_font_size: int = 20
    font_family: str = "Inter"
    font_size: int = 48
    text_color: tuple[int, int, int, int] = (255, 255, 255, 230)
    show_background: bool = False
    background_color: tuple[int, int, int, int] = (35, 35, 35, 255)
    background_opacity: float = 0.3
    border_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    border_opacity: float = 1.0
    display_mode: str = "digital"
    show_numerals: bool = True
    analog_face_shadow: bool = True

    @classmethod
    def from_mapping(
        cls,
        widget_id: str,
        values: Mapping[str, object],
    ) -> "ClockPresentationConfig":
        """Normalize an already-resolved Clock mapping into explicit state."""

        time_format = "24h" if str(values.get("format", "12h")).lower() == "24h" else "12h"
        calendar_layout = (
            "two_lines"
            if str(values.get("calendar_layout", "shared_line")).lower() == "two_lines"
            else "shared_line"
        )
        return cls(
            widget_id=str(widget_id or "clock"),
            time_format=time_format,
            show_seconds=_as_bool(values.get("show_seconds"), True),
            timezone_name=str(values.get("timezone", "local") or "local"),
            show_timezone=_as_bool(values.get("show_timezone"), False),
            show_day_of_week=_as_bool(values.get("show_day_of_week"), False),
            show_date=_as_bool(values.get("show_date"), False),
            show_separator=_as_bool(values.get("show_digital_separator"), False),
            calendar_layout=calendar_layout,
            calendar_font_size=_bounded_int(values.get("calendar_font_size"), 20, 8, 256),
            font_family=str(values.get("font_family", "Inter") or "Inter"),
            font_size=_bounded_int(values.get("font_size"), 48, 8, 512),
            text_color=_rgba(values.get("color"), (255, 255, 255, 230)),
            show_background=_as_bool(values.get("show_background"), False),
            background_color=_rgba(values.get("bg_color"), (35, 35, 35, 255)),
            background_opacity=_bounded_float(values.get("bg_opacity"), 0.3, 0.0, 1.0),
            border_color=_rgba(values.get("border_color"), (255, 255, 255, 255)),
            border_opacity=_bounded_float(values.get("border_opacity"), 1.0, 0.0, 1.0),
            display_mode=normalize_clock_display_mode(values.get("display_mode")),
            show_numerals=_as_bool(values.get("show_numerals"), True),
            analog_face_shadow=_as_bool(values.get("analog_face_shadow"), True),
        )

    @classmethod
    def from_widgets_mapping(
        cls,
        widget_id: str,
        widgets: Mapping[str, object],
        *,
        display_signature: str | None = None,
    ) -> "ClockPresentationConfig":
        """Project canonical Clock-family settings into detached presentation state.

        Secondary clocks retain the established base-Clock style inheritance while
        keeping their own timezone and per-display mode override.  The caller feeds
        plain resolved mappings only; no SettingsManager or persistence owner crosses
        the presentation boundary.
        """

        normalized_id = str(widget_id or "clock")
        if normalized_id not in {"clock", "clock2", "clock3"}:
            raise ValueError(f"unsupported Clock widget id: {normalized_id}")

        from core.settings.defaults import get_default_settings

        defaults = get_default_settings().get("widgets", {})
        values = widgets.get(normalized_id, {})
        base_values = widgets.get("clock", {})
        canonical = defaults.get(normalized_id, {})
        base_canonical = defaults.get("clock", {})
        if not isinstance(values, Mapping):
            values = {}
        if not isinstance(base_values, Mapping):
            base_values = {}
        if not isinstance(canonical, Mapping):
            canonical = {}
        if not isinstance(base_canonical, Mapping):
            base_canonical = {}

        def inherited(key: str, fallback: object = None) -> object:
            canonical_value = canonical.get(
                key,
                base_canonical.get(key, fallback),
            )
            if normalized_id == "clock":
                return values.get(key, canonical_value)
            if key in base_values:
                return base_values.get(key, canonical_value)
            return values.get(key, canonical_value)

        projected = {
            key: inherited(key)
            for key in (
                "format",
                "show_seconds",
                "show_timezone",
                "show_day_of_week",
                "show_date",
                "show_digital_separator",
                "calendar_layout",
                "calendar_font_size",
                "font_family",
                "font_size",
                "color",
                "show_background",
                "bg_color",
                "bg_opacity",
                "border_color",
                "border_opacity",
                "display_mode",
                "show_numerals",
                "analog_face_shadow",
            )
        }
        projected["timezone"] = values.get("timezone", "local")

        overrides = values.get("display_mode_overrides", {})
        if display_signature and isinstance(overrides, Mapping):
            projected["display_mode"] = overrides.get(
                display_signature,
                projected["display_mode"],
            )
        return cls.from_mapping(normalized_id, projected)


@dataclass(frozen=True)
class ClockPresentationStyle:
    """Fully resolved retained Clock shadow and card presentation values."""

    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float
    analog_shadow_color: QColor
    analog_ring_offset_x: float
    analog_ring_offset_y: float
    analog_numeral_main_offset_x: float
    analog_numeral_main_offset_y: float
    analog_numeral_contact_offset_x: float
    analog_numeral_contact_offset_y: float
    analog_hand_offset_x: float
    analog_hand_offset_y: float

    @classmethod
    def project(
        cls,
        config: ClockPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "ClockPresentationStyle":
        """Resolve canonical settings into signed retained presentation values."""

        direction = shadow_values.get("direction", "SE")
        frame_extra = _bounded_float(
            shadow_values.get("frame_extra_offset"), 0.0, 0.0, 40.0
        )
        text_extra = _bounded_float(
            shadow_values.get("text_extra_offset"), 0.0, 0.0, 40.0
        )
        card_offset = resolve_signed_offset(
            direction,
            ORDINARY_CARD_SHADOW_BASE[0] + frame_extra,
            ORDINARY_CARD_SHADOW_BASE[1] + frame_extra,
        )
        text_offset = resolve_signed_offset(
            direction,
            ORDINARY_TEXT_SHADOW_BASE[0] + text_extra,
            ORDINARY_TEXT_SHADOW_BASE[1] + text_extra,
        )
        ring_offset = resolve_signed_offset(direction, *_ANALOG_RING_SHADOW_BASE)
        numeral_drop = 3.0 if config.show_background else 2.0
        numeral_main_offset = resolve_signed_offset(
            direction, numeral_drop, numeral_drop
        )
        numeral_contact_offset = resolve_signed_offset(
            direction, *_ANALOG_NUMERAL_CONTACT_BASE
        )
        hand_offset = resolve_signed_offset(direction, *_ANALOG_HAND_SHADOW_BASE)

        shadow_rgba = _rgba(shadow_values.get("color"), (0, 0, 0, 255))
        frame_opacity = _bounded_float(
            shadow_values.get("frame_opacity"), 0.77, 0.0, 1.0
        )
        text_opacity = _bounded_float(
            shadow_values.get("text_opacity"), 0.33, 0.0, 1.0
        )
        frame_shadow_enabled = _as_bool(shadow_values.get("enabled"), True)
        text_shadow_enabled = _as_bool(
            shadow_values.get("text_enabled"), True
        )

        return cls(
            card_style=OverlayCardStyle(
                shell_enabled=config.show_background,
                background_color=_with_alpha(
                    config.background_color, config.background_opacity
                ),
                border_color=_with_alpha(
                    config.border_color, config.border_opacity
                ),
                border_width=max(0.0, float(border_width)),
                corner_radius=12.0,
                padding=10.0,
                shadow_enabled=(
                    config.show_background and frame_shadow_enabled
                ),
                shadow_color=_with_alpha(shadow_rgba, frame_opacity),
                shadow_blur=_bounded_float(
                    shadow_values.get("blur_radius"), 18.0, 0.0, 80.0
                ),
                shadow_offset_x=card_offset[0],
                shadow_offset_y=card_offset[1],
                shadow_spread=0.0,
            ),
            text_shadow_enabled=text_shadow_enabled,
            text_shadow_color=_with_alpha(shadow_rgba, text_opacity),
            text_shadow_offset_x=text_offset[0],
            text_shadow_offset_y=text_offset[1],
            # Analogue depth is family-authored; General Card/Text opacity and
            # magnitude do not become a third analogue tuning authority.
            analog_shadow_color=QColor(0, 0, 0, 230),
            analog_ring_offset_x=ring_offset[0],
            analog_ring_offset_y=ring_offset[1],
            analog_numeral_main_offset_x=numeral_main_offset[0],
            analog_numeral_main_offset_y=numeral_main_offset[1],
            analog_numeral_contact_offset_x=numeral_contact_offset[0],
            analog_numeral_contact_offset_y=numeral_contact_offset[1],
            analog_hand_offset_x=hand_offset[0],
            analog_hand_offset_y=hand_offset[1],
        )


@dataclass(frozen=True)
class ClockPresentationSnapshot:
    config: ClockPresentationConfig
    style: ClockPresentationStyle
    time_text: str
    calendar_text: str
    timezone_text: str
    hour_angle: float
    minute_angle: float
    second_angle: float


def _parse_timezone(name: str) -> tzinfo | None:
    normalized = str(name or "local").strip()
    if not normalized or normalized.lower() == "local":
        return None
    if pytz is not None:
        try:
            return pytz.timezone(normalized)
        except pytz.UnknownTimeZoneError:
            pass
    if normalized.upper().startswith("UTC"):
        suffix = normalized[3:]
        if suffix in {"", "+0", "-0"}:
            return timezone.utc
        try:
            sign = -1 if suffix.startswith("-") else 1
            suffix = suffix[1:] if suffix[:1] in {"+", "-"} else suffix
            hour_text, _, minute_text = suffix.partition(":")
            offset = timedelta(
                hours=sign * int(hour_text),
                minutes=sign * int(minute_text or "0"),
            )
            return timezone(offset)
        except (TypeError, ValueError):
            return None
    return None


def _standardize_timezone_abbreviation(abbreviation: str) -> str:
    return {
        "CAT": "SAST",
        "South Africa Standard Time": "SAST",
        "GMT Standard Time": "GMT",
        "GMT Daylight Time": "BST",
        "Pacific Standard Time": "PST",
        "Pacific Daylight Time": "PDT",
        "Eastern Standard Time": "EST",
        "Eastern Daylight Time": "EDT",
        "Central Standard Time": "CST",
        "Central Daylight Time": "CDT",
        "Mountain Standard Time": "MST",
        "Mountain Daylight Time": "MDT",
        "Japan Standard Time": "JST",
        "China Standard Time": "CST",
        "India Standard Time": "IST",
        "Australian Eastern Standard Time": "AEST",
        "Australian Eastern Daylight Time": "AEDT",
    }.get(abbreviation, abbreviation)


def _hand_angles(now: datetime) -> tuple[float, float, float]:
    second = float(now.second)
    minute = float(now.minute) + second / 60.0
    hour = float(now.hour % 12) + minute / 60.0
    return (
        hour * 30.0,
        minute * 6.0,
        second * 6.0,
    )


class ClockPresentationModel(QObject):
    """One stable presentation-oriented model per logical Clock instance."""

    stateChanged = Signal()

    def __init__(
        self,
        config: ClockPresentationConfig,
        style: ClockPresentationStyle,
        *,
        now_provider: Callable[[tzinfo | None], datetime] | None = None,
        ticker_provider: Callable[[], GlobalClockTicker] = get_global_clock_ticker,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._now_provider = now_provider or (
            lambda zone: datetime.now() if zone is None else datetime.now(zone)
        )
        self._ticker_provider = ticker_provider
        self._ticker: GlobalClockTicker | None = None
        self._active = False
        self._timezone = _parse_timezone(config.timezone_name)
        self._snapshot = self._build_snapshot(config, style)

    @property
    def config(self) -> ClockPresentationConfig:
        return self._snapshot.config

    @property
    def style(self) -> ClockPresentationStyle:
        return self._snapshot.style

    @property
    def is_active(self) -> bool:
        return self._active

    def activate(self, thread_manager: Any) -> None:
        """Subscribe this model to the existing process-global one-second owner."""

        if self._active:
            return
        ticker = self._ticker_provider()
        ticker.set_thread_manager(thread_manager)
        self._ticker = ticker
        self._active = True
        self._publish_tick()
        ticker.subscribe(self._publish_tick)

    def retire(self) -> None:
        """Stop publication without constructing a replacement ticker."""

        ticker = self._ticker
        self._ticker = None
        self._active = False
        if ticker is not None:
            ticker.unsubscribe(self._publish_tick)

    def apply_config(self, config: ClockPresentationConfig) -> bool:
        """Atomically apply settings-derived presentation inputs in place."""

        if config == self._snapshot.config:
            return False
        self._timezone = _parse_timezone(config.timezone_name)
        next_snapshot = self._build_snapshot(config, self._snapshot.style)
        self._replace_snapshot(next_snapshot)
        return True

    def apply_style(self, style: ClockPresentationStyle) -> bool:
        """Atomically update resolved retained style properties in place."""

        if style == self._snapshot.style:
            return False
        self._replace_snapshot(replace(self._snapshot, style=style))
        return True

    def set_display_mode(self, mode: object) -> bool:
        normalized = normalize_clock_display_mode(mode)
        if normalized == self._snapshot.config.display_mode:
            return False
        return self.apply_config(
            replace(self._snapshot.config, display_mode=normalized)
        )

    def _publish_tick(self) -> None:
        next_snapshot = self._build_snapshot(
            self._snapshot.config,
            self._snapshot.style,
        )
        self._replace_snapshot(next_snapshot)

    def _replace_snapshot(self, snapshot: ClockPresentationSnapshot) -> None:
        if snapshot == self._snapshot:
            return
        self._snapshot = snapshot
        self.stateChanged.emit()

    def _build_snapshot(
        self,
        config: ClockPresentationConfig,
        style: ClockPresentationStyle,
    ) -> ClockPresentationSnapshot:
        now = self._now_provider(self._timezone)
        if config.time_format == "12h":
            time_text = now.strftime(
                "%I:%M:%S %p" if config.show_seconds else "%I:%M %p"
            ).lstrip("0")
        else:
            time_text = now.strftime(
                "%H:%M:%S" if config.show_seconds else "%H:%M"
            )

        weekday = _WEEKDAYS[now.weekday()] if config.show_day_of_week else ""
        date_text = now.strftime("%d/%m/%Y") if config.show_date else ""
        if weekday and date_text:
            calendar_text = (
                f"{weekday}\n{date_text}"
                if config.calendar_layout == "two_lines"
                else f"{weekday} - {date_text}"
            )
        else:
            calendar_text = weekday or date_text

        timezone_text = ""
        if config.show_timezone:
            if self._timezone is None:
                timezone_text = _standardize_timezone_abbreviation(
                    time.tzname[time.daylight]
                )
            elif isinstance(self._timezone, timezone):
                offset = self._timezone.utcoffset(None) or timedelta(0)
                if offset == timedelta(0):
                    timezone_text = "UTC"
                else:
                    total_seconds = int(offset.total_seconds())
                    hours = int(total_seconds / 3600)
                    minutes = abs(total_seconds) % 3600 // 60
                    timezone_text = (
                        f"UTC{hours:+d}"
                        if minutes == 0
                        else f"UTC{hours:+d}:{minutes:02d}"
                    )
            else:
                timezone_text = _standardize_timezone_abbreviation(
                    now.strftime("%Z")
                )
        hour_angle, minute_angle, second_angle = _hand_angles(now)
        return ClockPresentationSnapshot(
            config=config,
            style=style,
            time_text=time_text,
            calendar_text=calendar_text,
            timezone_text=timezone_text,
            hour_angle=hour_angle,
            minute_angle=minute_angle,
            second_angle=second_angle,
        )

    @Property(str, notify=stateChanged)
    def timeText(self) -> str:
        return self._snapshot.time_text

    @Property(str, notify=stateChanged)
    def calendarText(self) -> str:
        return self._snapshot.calendar_text

    @Property(str, notify=stateChanged)
    def timezoneText(self) -> str:
        return self._snapshot.timezone_text

    @Property(str, notify=stateChanged)
    def displayMode(self) -> str:
        return self._snapshot.config.display_mode

    @Property(str, notify=stateChanged)
    def geometryVariant(self) -> str:
        return self._snapshot.config.display_mode

    @Property(bool, notify=stateChanged)
    def showSeconds(self) -> bool:
        return self._snapshot.config.show_seconds

    @Property(bool, notify=stateChanged)
    def showNumerals(self) -> bool:
        return self._snapshot.config.show_numerals

    @Property(bool, notify=stateChanged)
    def showSeparator(self) -> bool:
        return (
            self._snapshot.config.show_separator
            and bool(self._snapshot.calendar_text)
        )

    @Property(bool, notify=stateChanged)
    def analogFaceShadow(self) -> bool:
        return self._snapshot.config.analog_face_shadow

    @Property(str, notify=stateChanged)
    def fontFamily(self) -> str:
        return self._snapshot.config.font_family

    @Property(float, notify=stateChanged)
    def fontSize(self) -> float:
        return float(self._snapshot.config.font_size)

    @Property(float, notify=stateChanged)
    def calendarFontSize(self) -> float:
        return float(self._snapshot.config.calendar_font_size)

    @Property(float, notify=stateChanged)
    def secondaryFontSize(self) -> float:
        return float(max(8, self._snapshot.config.font_size // 4))

    @Property(QColor, notify=stateChanged)
    def textColor(self) -> QColor:
        return QColor(*self._snapshot.config.text_color)

    @Property(bool, notify=stateChanged)
    def textShadowEnabled(self) -> bool:
        return self._snapshot.style.text_shadow_enabled

    @Property(QColor, notify=stateChanged)
    def textShadowColor(self) -> QColor:
        return QColor(self._snapshot.style.text_shadow_color)

    @Property(float, notify=stateChanged)
    def textShadowOffsetX(self) -> float:
        return self._snapshot.style.text_shadow_offset_x

    @Property(float, notify=stateChanged)
    def textShadowOffsetY(self) -> float:
        return self._snapshot.style.text_shadow_offset_y

    @Property(QColor, notify=stateChanged)
    def separatorColor(self) -> QColor:
        color = QColor(*self._snapshot.config.text_color)
        color.setAlpha(max(0, min(255, int(round(color.alpha() * 0.45)))))
        return color

    @Property(float, notify=stateChanged)
    def hourAngle(self) -> float:
        return self._snapshot.hour_angle

    @Property(float, notify=stateChanged)
    def minuteAngle(self) -> float:
        return self._snapshot.minute_angle

    @Property(float, notify=stateChanged)
    def secondAngle(self) -> float:
        return self._snapshot.second_angle

    @Property(QColor, notify=stateChanged)
    def analogShadowColor(self) -> QColor:
        return QColor(self._snapshot.style.analog_shadow_color)

    @Property(float, notify=stateChanged)
    def analogRingOffsetX(self) -> float:
        return self._snapshot.style.analog_ring_offset_x

    @Property(float, notify=stateChanged)
    def analogRingOffsetY(self) -> float:
        return self._snapshot.style.analog_ring_offset_y

    @Property(float, notify=stateChanged)
    def analogNumeralMainOffsetX(self) -> float:
        return self._snapshot.style.analog_numeral_main_offset_x

    @Property(float, notify=stateChanged)
    def analogNumeralMainOffsetY(self) -> float:
        return self._snapshot.style.analog_numeral_main_offset_y

    @Property(float, notify=stateChanged)
    def analogNumeralContactOffsetX(self) -> float:
        return self._snapshot.style.analog_numeral_contact_offset_x

    @Property(float, notify=stateChanged)
    def analogNumeralContactOffsetY(self) -> float:
        return self._snapshot.style.analog_numeral_contact_offset_y

    @Property(float, notify=stateChanged)
    def analogHandOffsetX(self) -> float:
        return self._snapshot.style.analog_hand_offset_x

    @Property(float, notify=stateChanged)
    def analogHandOffsetY(self) -> float:
        return self._snapshot.style.analog_hand_offset_y


@dataclass(frozen=True)
class ClockGeometryVariantState:
    """One mode-specific Clock CUSTOM shape plus its resize-derived font scale."""

    geometry: OverlayWidgetGeometry
    font_size: int


class ClockGeometryVariantStore:
    """Session-owned exact Clock geometry/scale keyed by display and variant."""

    def __init__(self) -> None:
        self._states: dict[
            tuple[str, str, str], ClockGeometryVariantState
        ] = {}

    @staticmethod
    def _key(widget_id: str, display_identity: str, variant: object) -> tuple[str, str, str]:
        return (
            str(widget_id),
            str(display_identity),
            normalize_clock_display_mode(variant),
        )

    def remember(
        self,
        widget_id: str,
        display_identity: str,
        variant: object,
        geometry: OverlayWidgetGeometry,
        *,
        font_size: int,
    ) -> None:
        self._states[self._key(widget_id, display_identity, variant)] = (
            ClockGeometryVariantState(
                geometry=geometry,
                font_size=max(8, int(font_size)),
            )
        )

    def state_for(
        self,
        widget_id: str,
        display_identity: str,
        variant: object,
    ) -> ClockGeometryVariantState | None:
        return self._states.get(self._key(widget_id, display_identity, variant))

    def geometry_for(
        self,
        widget_id: str,
        display_identity: str,
        variant: object,
    ) -> OverlayWidgetGeometry | None:
        state = self.state_for(widget_id, display_identity, variant)
        return None if state is None else state.geometry


def _natural_geometry(config: ClockPresentationConfig) -> tuple[float, float]:
    font_size = float(max(8, config.font_size))
    if config.display_mode == "analog":
        width = max(160.0, round(font_size * 4.5))
        footer_rows = int(bool(config.show_day_of_week or config.show_date)) + int(
            config.show_timezone
        )
        footer_height = footer_rows * max(16.0, float(config.calendar_font_size))
        return width, max(width * 1.3, width + footer_height + 20.0)
    characters = 11 if config.time_format == "12h" and config.show_seconds else 8
    if config.time_format == "12h" and not config.show_seconds:
        characters = 8
    elif config.time_format == "24h" and not config.show_seconds:
        characters = 5
    width = max(160.0, font_size * characters * 0.62 + 28.0)
    footer_rows = int(bool(config.show_day_of_week or config.show_date)) + int(
        config.show_timezone
    )
    height = max(72.0, font_size * 1.45 + footer_rows * 28.0 + 16.0)
    return width, height


def derive_clock_variant_geometry(
    current: OverlayWidgetGeometry,
    bounds: OverlayWidgetGeometry,
    config: ClockPresentationConfig,
) -> OverlayWidgetGeometry:
    target_width, target_height = _natural_geometry(config)
    width = min(max(1.0, target_width), max(1.0, bounds.width))
    height = min(max(1.0, target_height), max(1.0, bounds.height))
    center_x = current.x + current.width / 2.0
    center_y = current.y + current.height / 2.0
    x = max(bounds.x, min(center_x - width / 2.0, bounds.x + bounds.width - width))
    y = max(bounds.y, min(center_y - height / 2.0, bounds.y + bounds.height - height))
    return OverlayWidgetGeometry(x, y, width, height)


class RetainedClockPresentation:
    """One retained Clock item, stable model, and exact variant geometry owner."""

    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: ClockPresentationModel,
        geometry: OverlayWidgetGeometry,
        display_bounds: OverlayWidgetGeometry,
        display_identity: str,
        geometry_store: ClockGeometryVariantStore | None = None,
        fade_opacity: float = 1.0,
        on_mode_toggle: Callable[
            [str, OverlayWidgetGeometry, Mapping[str, object]], None
        ] | None = None,
    ) -> None:
        self._model = model
        self._display_bounds = display_bounds
        self._display_identity = str(display_identity)
        self._geometry_store = geometry_store or ClockGeometryVariantStore()
        self._on_mode_toggle = on_mode_toggle
        self._geometry_commit_handler: (
            Callable[[OverlayWidgetGeometry], object] | None
        ) = None
        self._retained = host.create_family_widget(
            "clocks",
            initial_properties={"clockModel": model},
            object_name=model.config.widget_id,
            model_identity=model.config.widget_id,
            geometry=geometry,
            fade_opacity=fade_opacity,
            card_style=model.style.card_style,
        )
        self._geometry_store.remember(
            model.config.widget_id,
            self._display_identity,
            model.config.display_mode,
            geometry,
            font_size=model.config.font_size,
        )
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(
            self._apply_custom_layout_size_payload
        )
        toggle_signal = getattr(self._retained.item, "toggleModeRequested", None)
        if toggle_signal is not None and hasattr(toggle_signal, "connect"):
            toggle_signal.connect(self.toggle_display_mode)

    @property
    def item(self):
        return self._retained.item

    @property
    def model(self) -> ClockPresentationModel:
        return self._model

    @property
    def geometry(self) -> OverlayWidgetGeometry:
        item = self._retained.item
        return OverlayWidgetGeometry(item.x(), item.y(), item.width(), item.height())

    def activate(self, thread_manager: Any) -> None:
        self._model.activate(thread_manager)

    def set_fade_opacity(self, opacity: float) -> None:
        self._retained.set_fade_opacity(opacity)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)
        self._geometry_store.remember(
            self._model.config.widget_id,
            self._display_identity,
            self._model.config.display_mode,
            geometry,
            font_size=self._model.config.font_size,
        )

    def _apply_custom_layout_size_payload(
        self,
        payload: Mapping[str, object],
    ) -> None:
        font_size = int(payload.get("font_size", self._model.config.font_size))
        if self._model.apply_config(
            replace(self._model.config, font_size=max(8, font_size))
        ):
            self._geometry_store.remember(
                self._model.config.widget_id,
                self._display_identity,
                self._model.config.display_mode,
                self.geometry,
                font_size=self._model.config.font_size,
            )

    def set_geometry_commit_handler(
        self,
        handler: Callable[[OverlayWidgetGeometry], object] | None,
    ) -> None:
        """Bind the display-owned committed-geometry seam for CUSTOM variants."""

        self._geometry_commit_handler = handler

    def seed_geometry_variant(
        self,
        mode: object,
        geometry: OverlayWidgetGeometry,
        size_payload: Mapping[str, object] | None = None,
    ) -> None:
        """Seed one committed mode-specific CUSTOM state without changing pixels."""

        payload = size_payload if isinstance(size_payload, Mapping) else {}
        font_size = int(payload.get("font_size", self._model.config.font_size))
        self._geometry_store.remember(
            self._model.config.widget_id,
            self._display_identity,
            mode,
            geometry,
            font_size=max(8, font_size),
        )

    def set_display_mode(self, mode: object) -> bool:
        target = normalize_clock_display_mode(mode)
        current_mode = self._model.config.display_mode
        if target == current_mode:
            return False
        current_geometry = self.geometry
        self._geometry_store.remember(
            self._model.config.widget_id,
            self._display_identity,
            current_mode,
            current_geometry,
            font_size=self._model.config.font_size,
        )
        target_state = self._geometry_store.state_for(
            self._model.config.widget_id,
            self._display_identity,
            target,
        )
        target_font_size = (
            self._model.config.font_size
            if target_state is None
            else target_state.font_size
        )
        self._model.apply_config(
            replace(
                self._model.config,
                display_mode=target,
                font_size=target_font_size,
            )
        )
        if target_state is None:
            target_geometry = derive_clock_variant_geometry(
                current_geometry,
                self._display_bounds,
                self._model.config,
            )
            self._geometry_store.remember(
                self._model.config.widget_id,
                self._display_identity,
                target,
                target_geometry,
                font_size=self._model.config.font_size,
            )
        else:
            target_geometry = target_state.geometry
        geometry_commit = self._geometry_commit_handler
        if geometry_commit is not None:
            geometry_commit(target_geometry)
        else:
            self.set_geometry(target_geometry)
        return True

    def toggle_display_mode(self) -> None:
        target = (
            "digital"
            if self._model.config.display_mode == "analog"
            else "analog"
        )
        if self.set_display_mode(target) and self._on_mode_toggle is not None:
            self._on_mode_toggle(
                target,
                self.geometry,
                {"font_size": int(self._model.config.font_size)},
            )

    def apply_config(
        self,
        config: ClockPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> None:
        target_mode = config.display_mode
        current_mode = self._model.config.display_mode
        self._model.apply_config(replace(config, display_mode=current_mode))
        style = ClockPresentationStyle.project(
            self._model.config,
            shadow_values,
            border_width=border_width,
        )
        self._model.apply_style(style)
        self._retained.set_card_style(style.card_style)
        if target_mode != current_mode:
            self.set_display_mode(target_mode)

    def retire(self) -> bool:
        self._geometry_commit_handler = None
        return self._retained.retire()


__all__ = [
    "ClockGeometryVariantState",
    "ClockGeometryVariantStore",
    "ClockPresentationConfig",
    "ClockPresentationModel",
    "ClockPresentationSnapshot",
    "ClockPresentationStyle",
    "derive_clock_variant_geometry",
    "RetainedClockPresentation",
    "normalize_clock_display_mode",
]
