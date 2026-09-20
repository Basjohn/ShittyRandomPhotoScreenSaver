"""Opt-in retained master-volume OSD, fed by the existing Media Core Audio owner.

No endpoint, COM registration, volume poll or user-volume write lives here. The
presentation model owns one event-restarted inactivity deadline while admitted;
one ordinary runtime-service lease owns its participation in the shared source.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from typing import Any

from PySide6.QtCore import QObject, Property, QTimer, Signal
from PySide6.QtGui import QColor

from core.media.system_audio_osd_policy import SystemAudioOSDPolicy
from core.settings.default_contract import require_canonical_default
from ui.widget_theme_active import get_active_widget_theme
from .theme_projection import (
    configured_rgba_override, resolve_card_surface_colors,
    resolve_primary_text_color, resolve_rgba_role,
)
from .host import OrdinaryWidgetPresentationHost, OverlayCardStyle, OverlayWidgetGeometry, RetainedOverlayWidget


_DEFAULTS = require_canonical_default("widgets.system_audio_osd")


@dataclass(frozen=True)
class SystemAudioOSDConfig:
    preferred_width: float
    preferred_height: float
    inactivity_ms: int
    font_family: str
    font_size: int
    text_position: str
    text_color: tuple[int, int, int, int]
    accent_color: tuple[int, int, int, int]
    track_color: tuple[int, int, int, int]
    bar_thickness: float
    card_style: OverlayCardStyle

    @classmethod
    def from_widgets_mapping(cls, widgets: Mapping[str, object]) -> "SystemAudioOSDConfig":
        values = widgets.get("system_audio_osd", {})
        if not isinstance(values, Mapping):
            values = {}
        def get_number(name: str, minimum: float, maximum: float) -> float:
            try:
                value = float(values.get(name, _DEFAULTS[name]))
            except (TypeError, ValueError):
                value = float(_DEFAULTS[name])
            if not isfinite(value):
                value = float(_DEFAULTS[name])
            return max(minimum, min(maximum, value))

        def color(name: str) -> tuple[int, int, int, int]:
            value = values.get(name, _DEFAULTS[name])
            if not isinstance(value, (tuple, list)) or len(value) != 4:
                value = _DEFAULTS[name]
            return tuple(max(0, min(255, int(part))) for part in value)

        mode = str(values.get("text_position", _DEFAULTS["text_position"]))
        if mode not in ("left_of_bar", "inside_bar", "right_of_bar", "none", "numbers_only"):
            mode = str(_DEFAULTS["text_position"])
        bg = color("bg_color")
        border = color("border_color")
        current = values if isinstance(values, Mapping) else {}
        theme = get_active_widget_theme()
        # Canonical/default-valued swatches are implicit Inherit. Explicit
        # family colours remain authoritative, as with Media/System Stats.
        shell_bg, shell_border = resolve_card_surface_colors(
            values=current, defaults=_DEFAULTS,
            background_color=bg, background_opacity=1.0,
            border_color=border, border_opacity=1.0,
        )
        text = resolve_primary_text_color(
            values=current, defaults=_DEFAULTS, text_color=color("color"),
        )
        accent = resolve_rgba_role(
            "system_audio_osd.accent",
            local_roles={"local.accent": theme.color("card.border")},
            fallback=color("accent_color"),
            explicit=configured_rgba_override(
                current, _DEFAULTS, "accent_color", color("accent_color")
            ),
        )
        track = resolve_rgba_role(
            "system_audio_osd.track",
            local_roles={"local.surface": theme.color("card.background")},
            fallback=color("track_color"),
            explicit=configured_rgba_override(
                current, _DEFAULTS, "track_color", color("track_color")
            ),
        )
        return cls(
            preferred_width=get_number("preferred_width", 180.0, 900.0),
            preferred_height=get_number("preferred_height", 48.0, 220.0),
            inactivity_ms=int(get_number("inactivity_ms", 500.0, 12000.0)),
            font_family=str(values.get("font_family", _DEFAULTS["font_family"])),
            font_size=int(get_number("font_size", 11.0, 56.0)),
            text_position=mode,
            text_color=text,
            accent_color=accent,
            track_color=track,
            bar_thickness=get_number("bar_thickness", 3.0, 32.0),
            card_style=OverlayCardStyle(
                shell_enabled=bool(values.get("show_background", _DEFAULTS["show_background"])),
                background_color=QColor(*shell_bg), border_color=QColor(*shell_border),
                border_width=2.0, corner_radius=12.0, padding=10.0,
            ),
        )


class SystemAudioOSDPresentationModel(QObject):
    stateChanged = Signal()
    revealedChanged = Signal()
    contentExtentChanged = Signal()

    def __init__(self, config: SystemAudioOSDConfig, *, runtime_generation: int | None = None) -> None:
        super().__init__()
        self.config = config
        self._runtime_generation = runtime_generation
        self._system_mute_runtime_service: Any = None
        self._policy = SystemAudioOSDPolicy()
        self._active = False
        self._retired = False
        self._available = False
        self._muted = False
        self._volume = 0.0
        self._revealed = False
        self._extent: tuple[float, float] | None = None
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.timeout.connect(self._hide_on_deadline)

    def set_system_mute_runtime_service(self, service: Any) -> None:
        if self._retired or self._system_mute_runtime_service is not None:
            raise RuntimeError("OSD audio lease must be injected exactly once")
        service.attach_consumer(self)
        self._system_mute_runtime_service = service

    def is_system_mute_consumer_alive(self) -> bool:
        return self._active and not self._retired

    def activate(self, thread_manager: Any | None = None) -> bool:
        if self._retired or self._system_mute_runtime_service is None:
            return False
        if self._active:
            return True
        service = self._system_mute_runtime_service
        service.set_thread_manager(thread_manager)
        self._active = True
        try:
            started = bool(service.start())
        except Exception:
            self._active = False
            raise
        if not started:
            self._active = False
            return False
        return True

    def on_system_mute_runtime_snapshot(self, snapshot: object) -> None:
        if not self._active or self._retired:
            return
        decision = self._policy.accept(snapshot)
        if not decision.accepted:
            return
        new_volume = 0.0 if decision.volume is None else float(decision.volume)
        changed = (self._available, self._muted, self._volume) != (
            decision.available, decision.muted, new_volume
        )
        self._available, self._muted, self._volume = decision.available, decision.muted, new_volume
        if changed:
            self.stateChanged.emit()
        if not decision.available:
            self._deadline.stop()
            self._set_revealed(False)
        elif decision.reveal:
            self._set_revealed(True)
            # Restart the *same* deadline for a burst, never allocate per event.
            self._deadline.start(self.config.inactivity_ms)

    def _set_revealed(self, value: bool) -> None:
        if self._revealed == value:
            return
        self._revealed = value
        self.revealedChanged.emit()

    def _hide_on_deadline(self) -> None:
        if self._active and not self._retired:
            self._set_revealed(False)

    def set_content_extent(self, width: float, height: float) -> bool:
        extent = (max(1.0, float(width)), max(1.0, float(height)))
        if self._extent == extent:
            return False
        self._extent = extent
        self.contentExtentChanged.emit()
        return True

    def clear_content_extent(self) -> bool:
        if self._extent is None:
            return False
        self._extent = None
        self.contentExtentChanged.emit()
        return True

    @Property(bool, notify=stateChanged)
    def available(self) -> bool:
        return self._available

    @Property(bool, notify=stateChanged)
    def muted(self) -> bool:
        return self._muted

    @Property(float, notify=stateChanged)
    def volumeFraction(self) -> float:
        return self._volume

    @Property(str, notify=stateChanged)
    def percentageText(self) -> str:
        return "—" if not self._available else f"{round(self._volume * 100)}%"

    @Property(bool, notify=revealedChanged)
    def revealed(self) -> bool:
        return self._revealed

    @Property(float, notify=contentExtentChanged)
    def authoredWidth(self) -> float:
        return self._extent[0] if self._extent is not None else self.config.preferred_width

    @Property(float, notify=contentExtentChanged)
    def authoredHeight(self) -> float:
        return self._extent[1] if self._extent is not None else self.config.preferred_height

    @Property(str, constant=True)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(int, constant=True)
    def fontSize(self) -> int:
        return self.config.font_size

    @Property(str, constant=True)
    def textPosition(self) -> str:
        return self.config.text_position

    @Property(float, constant=True)
    def barThickness(self) -> float:
        return self.config.bar_thickness

    @Property(QColor, constant=True)
    def textColor(self) -> QColor:
        return QColor(*self.config.text_color)

    @Property(QColor, constant=True)
    def accentColor(self) -> QColor:
        return QColor(*self.config.accent_color)

    @Property(QColor, constant=True)
    def trackColor(self) -> QColor:
        return QColor(*self.config.track_color)

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._active = False
        self._deadline.stop()
        self._policy.retire()
        service, self._system_mute_runtime_service = self._system_mute_runtime_service, None
        if service is not None:
            service.stop()
            service.detach_consumer(self)
        self._set_revealed(False)


class RetainedSystemAudioOSDPresentation:
    def __init__(self, *, host: OrdinaryWidgetPresentationHost,
                 model: SystemAudioOSDPresentationModel, geometry: OverlayWidgetGeometry) -> None:
        self._model = model
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "system_audio_osd", initial_properties={"osdModel": model},
            object_name="system_audio_osd", model_identity="system_audio_osd",
            geometry=geometry, fade_opacity=0.0, card_style=model.config.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(self._apply_custom_layout_size_payload)
        model.revealedChanged.connect(self._sync_reveal)
        signal = getattr(self._retained.item, "customLayoutInputBlockedChanged", None)
        if signal is not None:
            signal.connect(self._sync_reveal)
        self._sync_reveal()

    def _sync_reveal(self) -> None:
        if self._retained.is_retired:
            return
        root = self._retained.item
        in_edit = bool(root.property("customLayoutInputBlocked"))
        self._retained.set_fade_opacity(1.0 if in_edit or self._model.revealed else 0.0)

    def _apply_custom_layout_size_payload(self, payload: Mapping[str, object]) -> None:
        extent = payload.get("content_extent")
        if isinstance(extent, (list, tuple)) and len(extent) == 2:
            self._model.set_content_extent(extent[0], extent[1])
        else:
            self._model.clear_content_extent()

    @property
    def item(self) -> Any:
        return self._retained.item

    @property
    def model(self) -> SystemAudioOSDPresentationModel:
        return self._model

    def activate(self, thread_manager: Any | None = None) -> bool:
        return self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def set_fade_opacity(self, opacity: float) -> None:
        # A general host fade is still the normal lifetime admission authority.
        self._retained.set_fade_opacity(opacity)

    def retire(self) -> bool:
        return self._retained.retire()
