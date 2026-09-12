"""Retained whole-system CPU/RAM card presentation.

The model consumes one generation-shared immutable sample.  It owns no timer,
worker, source handle or history and exposes only stable, fixed-capacity card
state to QML.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, Signal
from PySide6.QtGui import QColor

from core.settings.default_contract import require_canonical_default
from core.settings.shadow_direction import (
    resolve_directional_extensions,
    resolve_signed_offset,
)
from core.system_stats.source import CpuRamSample
from rendering.quick.shadow_snapshot import QuickShadowSnapshot

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)
from .steam_common import as_bool, bounded_float, bounded_int, rgba, with_alpha
from .theme_projection import (
    resolve_card_surface_colors,
    resolve_header_colors,
    resolve_primary_text_color,
    resolve_rgba_role,
)


_SYSTEM_STATS_ICON = (
    Path(__file__).resolve().parents[3] / "images" / "system_stats_tools.svg"
)
_DEFAULTS = require_canonical_default("widgets.system_stats")
if not isinstance(_DEFAULTS, Mapping):
    raise TypeError("Canonical System Stats defaults must be a mapping")


@dataclass(frozen=True)
class SystemStatsPresentationConfig:
    font_family: str
    font_size: int
    text_color: tuple[int, int, int, int]
    show_background: bool
    background_color: tuple[int, int, int, int]
    background_opacity: float
    border_color: tuple[int, int, int, int]
    border_opacity: float
    header_fill_color: tuple[int, int, int, int]
    header_border_color: tuple[int, int, int, int]
    header_text_color: tuple[int, int, int, int]
    cpu_accent_color: tuple[int, int, int, int]
    ram_accent_color: tuple[int, int, int, int]
    metric_surface_color: tuple[int, int, int, int]
    metric_border_color: tuple[int, int, int, int]
    track_color: tuple[int, int, int, int]
    metric_capacity: int
    authored_width: int

    @classmethod
    def from_widgets_mapping(
        cls, widgets: Mapping[str, object]
    ) -> "SystemStatsPresentationConfig":
        values = widgets.get("system_stats", {}) if isinstance(widgets, Mapping) else {}
        merged = dict(_DEFAULTS)
        if isinstance(values, Mapping):
            merged.update(values)
        config = cls(
            font_family=str(merged.get("font_family") or _DEFAULTS["font_family"]),
            font_size=bounded_int(
                merged.get("font_size"), int(_DEFAULTS["font_size"]), 8, 96
            ),
            text_color=rgba(merged.get("color"), tuple(_DEFAULTS["color"])),
            show_background=as_bool(
                merged.get("show_background"), bool(_DEFAULTS["show_background"])
            ),
            background_color=rgba(merged.get("bg_color"), tuple(_DEFAULTS["bg_color"])),
            background_opacity=bounded_float(
                merged.get("bg_opacity"),
                float(_DEFAULTS["bg_opacity"]),
                0.0,
                1.0,
            ),
            border_color=rgba(
                merged.get("border_color"), tuple(_DEFAULTS["border_color"])
            ),
            border_opacity=bounded_float(
                merged.get("border_opacity"),
                float(_DEFAULTS["border_opacity"]),
                0.0,
                1.0,
            ),
            header_fill_color=rgba(
                merged.get("header_fill_color"),
                tuple(_DEFAULTS["header_fill_color"]),
            ),
            header_border_color=rgba(
                merged.get("header_border_color"),
                tuple(_DEFAULTS["header_border_color"]),
            ),
            header_text_color=rgba(
                merged.get("header_text_color"),
                tuple(_DEFAULTS["header_text_color"]),
            ),
            cpu_accent_color=rgba(
                merged.get("cpu_accent_color"),
                tuple(_DEFAULTS["cpu_accent_color"]),
            ),
            ram_accent_color=rgba(
                merged.get("ram_accent_color"),
                tuple(_DEFAULTS["ram_accent_color"]),
            ),
            metric_surface_color=(35, 46, 62, 188),
            metric_border_color=(151, 187, 214, 128),
            track_color=(8, 14, 22, 176),
            metric_capacity=bounded_int(
                merged.get("metric_capacity"),
                int(_DEFAULTS["metric_capacity"]),
                2,
                2,
            ),
            authored_width=bounded_int(
                merged.get("preferred_width"),
                int(_DEFAULTS["preferred_width"]),
                440,
                900,
            ),
        )
        header_fill, header_border, header_text = resolve_header_colors(
            "system_stats",
            values=values if isinstance(values, Mapping) else {},
            defaults=_DEFAULTS,
            fill=config.header_fill_color,
            border=config.header_border_color,
            text=config.header_text_color,
        )
        card_background, card_border = resolve_card_surface_colors(
            values=values if isinstance(values, Mapping) else {},
            defaults=_DEFAULTS,
            background_color=config.background_color,
            background_opacity=config.background_opacity,
            border_color=config.border_color,
            border_opacity=config.border_opacity,
        )
        text_color = resolve_primary_text_color(
            values=values if isinstance(values, Mapping) else {},
            defaults=_DEFAULTS,
            text_color=config.text_color,
        )
        cpu = resolve_rgba_role(
            "system_stats.cpu.accent",
            local_roles={"local.accent": config.cpu_accent_color},
            fallback=config.cpu_accent_color,
        )
        ram = resolve_rgba_role(
            "system_stats.ram.accent",
            local_roles={"local.accent.alt": config.ram_accent_color},
            fallback=config.ram_accent_color,
        )
        metric_surface = resolve_rgba_role(
            "system_stats.metric.surface",
            local_roles={"local.surface.alt": config.metric_surface_color},
            fallback=config.metric_surface_color,
        )
        metric_border = resolve_rgba_role(
            "system_stats.metric.border",
            local_roles={"local.border": config.metric_border_color},
            fallback=config.metric_border_color,
        )
        track = resolve_rgba_role(
            "system_stats.metric.track",
            local_roles={"local.surface": config.track_color},
            fallback=config.track_color,
        )
        return replace(
            config,
            text_color=text_color,
            background_color=card_background,
            background_opacity=1.0,
            border_color=card_border,
            border_opacity=1.0,
            header_fill_color=header_fill,
            header_border_color=header_border,
            header_text_color=header_text,
            cpu_accent_color=cpu,
            ram_accent_color=ram,
            metric_surface_color=metric_surface,
            metric_border_color=metric_border,
            track_color=track,
        )

    @property
    def authored_height(self) -> int:
        return 110 + self.metric_capacity * 80


@dataclass(frozen=True)
class SystemStatsPresentationStyle:
    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float

    @classmethod
    def project(
        cls,
        config: SystemStatsPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "SystemStatsPresentationStyle":
        shadow = QuickShadowSnapshot.from_mapping(shadow_values)
        card_offset = resolve_signed_offset(
            shadow.direction, *ORDINARY_CARD_SHADOW_BASE
        )
        card_extensions = resolve_directional_extensions(
            shadow.direction, shadow.frame_extra_offset
        )
        text_offset = resolve_signed_offset(
            shadow.direction,
            ORDINARY_TEXT_SHADOW_BASE[0] + shadow.text_extra_offset,
            ORDINARY_TEXT_SHADOW_BASE[1] + shadow.text_extra_offset,
        )
        return cls(
            card_style=OverlayCardStyle(
                shell_enabled=config.show_background,
                background_color=with_alpha(
                    config.background_color, config.background_opacity
                ),
                border_color=with_alpha(config.border_color, config.border_opacity),
                border_width=max(0.0, float(border_width)),
                corner_radius=12.0,
                padding=0.0,
                shadow_enabled=config.show_background and shadow.enabled,
                shadow_color=with_alpha(shadow.color, shadow.frame_opacity),
                shadow_blur=min(80.0, shadow.blur_radius),
                shadow_offset_x=card_offset[0],
                shadow_offset_y=card_offset[1],
                shadow_extend_left=card_extensions[0],
                shadow_extend_top=card_extensions[1],
                shadow_extend_right=card_extensions[2],
                shadow_extend_bottom=card_extensions[3],
            ),
            text_shadow_enabled=shadow.text_enabled,
            text_shadow_color=with_alpha(shadow.color, shadow.text_opacity),
            text_shadow_offset_x=text_offset[0],
            text_shadow_offset_y=text_offset[1],
        )


def _format_bytes(value: int | None) -> str:
    if value is None or value < 0:
        return "Unavailable"
    gib = value / float(1024**3)
    return f"{gib:.1f} GB"


class SystemStatsPresentationModel(QObject):
    stateChanged = Signal()

    def __init__(
        self,
        config: SystemStatsPresentationConfig,
        style: SystemStatsPresentationStyle,
        *,
        runtime_generation: int | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.style = style
        self._runtime_generation = runtime_generation
        self._runtime_service: Any | None = None
        self._runtime_attached = False
        self._thread_manager: Any | None = None
        self._sample = CpuRamSample("warming", None, "warming", None, None)
        self._revision = 0
        self._active = False
        self._retired = False

    @property
    def is_active(self) -> bool:
        return self._active and not self._retired

    def is_lifecycle_active(self) -> bool:
        return self.is_active

    def is_system_stats_consumer_alive(self) -> bool:
        return self.is_active

    def set_runtime_service(self, service: Any) -> None:
        if self._retired or self._active:
            raise RuntimeError("cannot replace System Stats runtime after activation")
        if self._runtime_service is service:
            return
        if self._runtime_service is not None:
            raise RuntimeError("System Stats already has a runtime service")
        self._runtime_service = service

    def activate(self, thread_manager: Any | None = None) -> bool:
        if self._retired:
            raise RuntimeError("cannot activate retired System Stats model")
        if self._active:
            return True
        service = self._runtime_service
        if service is None or thread_manager is None:
            raise RuntimeError("System Stats activation requires its shared service")
        self._thread_manager = thread_manager
        service.set_thread_manager(thread_manager)
        service.attach_consumer(self)
        self._runtime_attached = True
        self._active = True
        if not service.start():
            self._active = False
            service.detach_consumer(self)
            self._runtime_attached = False
            raise RuntimeError("System Stats shared service failed to start")
        return True

    def on_system_stats_runtime_snapshot(self, snapshot: Any) -> None:
        if not self.is_active:
            return
        revision = int(getattr(snapshot, "revision", 0))
        sample = getattr(snapshot, "sample", None)
        if revision <= self._revision or not isinstance(sample, CpuRamSample):
            return
        self._revision = revision
        self._sample = sample
        self.stateChanged.emit()

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._active = False
        if self._runtime_service is not None and self._runtime_attached:
            self._runtime_service.stop()
            self._runtime_service.detach_consumer(self)
        self._runtime_attached = False
        self._runtime_service = None
        self._thread_manager = None

    @Property(str, constant=True)
    def headerText(self) -> str:
        return "System Stats"

    @Property(str, constant=True)
    def iconSource(self) -> str:
        return (
            _SYSTEM_STATS_ICON.resolve().as_uri()
            if _SYSTEM_STATS_ICON.is_file()
            else ""
        )

    @Property(str, notify=stateChanged)
    def cadenceText(self) -> str:
        return "WHOLE SYSTEM  •  10 SEC"

    @Property(str, notify=stateChanged)
    def cpuValue(self) -> str:
        if self._sample.cpu_status != "ok" or self._sample.cpu_pct is None:
            return "—"
        return f"{round(self._sample.cpu_pct)}%"

    @Property(float, notify=stateChanged)
    def cpuPercent(self) -> float:
        return (
            max(0.0, min(100.0, float(self._sample.cpu_pct)))
            if self._sample.cpu_status == "ok" and self._sample.cpu_pct is not None
            else 0.0
        )

    @Property(str, notify=stateChanged)
    def cpuDetail(self) -> str:
        if self._sample.cpu_status == "warming":
            return "Warming the independent CPU baseline"
        if self._sample.cpu_status != "ok":
            return "Whole-system CPU unavailable"
        return "Across all logical processors"

    @Property(str, notify=stateChanged)
    def ramValue(self) -> str:
        if (
            self._sample.ram_status != "ok"
            or self._sample.ram_used_bytes is None
            or self._sample.ram_total_bytes is None
        ):
            return "—"
        return f"{round(self.ramPercent)}%"

    @Property(float, notify=stateChanged)
    def ramPercent(self) -> float:
        used = self._sample.ram_used_bytes
        total = self._sample.ram_total_bytes
        if (
            self._sample.ram_status != "ok"
            or used is None
            or total is None
            or total <= 0
        ):
            return 0.0
        return max(0.0, min(100.0, 100.0 * used / total))

    @Property(str, notify=stateChanged)
    def ramDetail(self) -> str:
        if self._sample.ram_status != "ok":
            return "Whole-system memory unavailable"
        return f"{_format_bytes(self._sample.ram_used_bytes)} of {_format_bytes(self._sample.ram_total_bytes)} used"

    @Property(str, notify=stateChanged)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(float, notify=stateChanged)
    def fontSize(self) -> float:
        return float(self.config.font_size)

    @Property(QColor, notify=stateChanged)
    def textColor(self) -> QColor:
        return QColor(*self.config.text_color)

    @Property(QColor, notify=stateChanged)
    def mutedTextColor(self) -> QColor:
        color = QColor(*self.config.text_color)
        color.setAlpha(max(90, int(color.alpha() * 0.64)))
        return color

    @Property(QColor, notify=stateChanged)
    def cpuAccentColor(self) -> QColor:
        return QColor(*self.config.cpu_accent_color)

    @Property(QColor, notify=stateChanged)
    def ramAccentColor(self) -> QColor:
        return QColor(*self.config.ram_accent_color)

    @Property(QColor, notify=stateChanged)
    def metricSurfaceColor(self) -> QColor:
        return QColor(*self.config.metric_surface_color)

    @Property(QColor, notify=stateChanged)
    def metricBorderColor(self) -> QColor:
        return QColor(*self.config.metric_border_color)

    @Property(QColor, notify=stateChanged)
    def trackColor(self) -> QColor:
        return QColor(*self.config.track_color)

    @Property(QColor, notify=stateChanged)
    def headerFillColor(self) -> QColor:
        return QColor(*self.config.header_fill_color)

    @Property(QColor, notify=stateChanged)
    def headerBorderColor(self) -> QColor:
        return QColor(*self.config.header_border_color)

    @Property(QColor, notify=stateChanged)
    def headerTextColor(self) -> QColor:
        return QColor(*self.config.header_text_color)

    @Property(float, notify=stateChanged)
    def headerBorderWidth(self) -> float:
        return max(1.0, self.style.card_style.border_width - 3.0)

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

    @Property(float, notify=stateChanged)
    def authoredWidth(self) -> float:
        return float(self.config.authored_width)

    @Property(float, notify=stateChanged)
    def authoredHeight(self) -> float:
        return float(self.config.authored_height)


class RetainedSystemStatsPresentation:
    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: SystemStatsPresentationModel,
        geometry: OverlayWidgetGeometry,
    ) -> None:
        self._model = model
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "system_stats",
            initial_properties={"systemStatsModel": model},
            object_name="system_stats",
            model_identity="system_stats",
            geometry=geometry,
            fade_opacity=1.0,
            card_style=model.style.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(lambda _payload: None)

    @property
    def item(self) -> Any:
        return self._retained.item

    @property
    def model(self) -> SystemStatsPresentationModel:
        return self._model

    def activate(self, thread_manager: Any | None = None) -> bool:
        return self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def set_fade_opacity(self, opacity: float) -> None:
        self._retained.set_fade_opacity(opacity)

    def retire(self) -> bool:
        return self._retained.retire()


__all__ = [
    "RetainedSystemStatsPresentation",
    "SystemStatsPresentationConfig",
    "SystemStatsPresentationModel",
    "SystemStatsPresentationStyle",
]
