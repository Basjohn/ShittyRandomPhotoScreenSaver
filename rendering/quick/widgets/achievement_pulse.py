"""Retained Achievement Pulse presentation state and runtime bridge.

Steam provider, cache, selection, request cadence and decoded-image ownership
remain in the existing Achievement Pulse runtime.  This module projects that
accepted state into stable Qt models and presentation-only style/config values.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    Property,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QImage

from core.settings.shadow_direction import resolve_signed_offset
from core.steam.achievement_pulse import AchievementPulseSelection
from widgets.steam_achievement_preparation import (
    AchievementPulsePreparedPresentation,
    AchievementPulseRuntimeConfig,
)
from widgets.steam_card_models import (
    SteamCardField,
    SteamCardViewModel,
    build_steam_connect_required_view_model,
)
from widgets.steam_components import (
    ACHIEVEMENT_CAPSULE_BORDER_RGBA,
    ACHIEVEMENT_CAPSULE_FILL_RGBA,
    achievement_capsule_geometry,
    achievement_field_rail_count,
    achievement_pulse_authored_size,
    normalize_achievement_artwork_shape,
    normalize_achievement_capsule_font_size,
    normalize_achievement_square_artwork_size,
)

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)


_STEAM_LOGO = Path(__file__).resolve().parents[3] / "images" / "Steam_Logo.png"
_FIELD_DEFAULTS: tuple[tuple[str, bool], ...] = (
    ("total", True),
    ("latest", True),
    ("playtime", True),
    ("previous", True),
    ("source", False),
    ("selected", False),
)


def _bounded_int(value: object, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = int(default)
    return max(low, min(high, parsed))


def _bounded_float(value: object, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
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
    return default if value is None else bool(value)


def _rgba(
    value: object,
    default: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    if isinstance(value, QColor):
        color = QColor(value)
    elif isinstance(value, (tuple, list)) and len(value) in {3, 4}:
        channels = list(value)
        if len(channels) == 3:
            channels.append(255)
        try:
            color = QColor(
                *(max(0, min(255, int(channel))) for channel in channels)
            )
        except (TypeError, ValueError):
            color = QColor(*default)
    else:
        color = QColor(str(value)) if value is not None else QColor()
    if not color.isValid():
        color = QColor(*default)
    return color.red(), color.green(), color.blue(), color.alpha()


def _with_alpha(
    rgba: tuple[int, int, int, int],
    scale: float,
) -> QColor:
    color = QColor(*rgba)
    color.setAlpha(max(0, min(255, int(round(color.alpha() * scale)))))
    return color


def _optional_appid(value: object) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _image_source(image: QImage, identity: object) -> str:
    """Return the accepted runtime asset path as a QML-safe local source."""

    normalized = str(identity or "").strip()
    if image.isNull() or not normalized:
        return ""
    if normalized.lower().startswith("file:"):
        return normalized
    return Path(normalized).resolve().as_uri()


@dataclass(frozen=True)
class AchievementPulsePresentationConfig:
    font_family: str = "Inter"
    font_size: int = 14
    text_color: tuple[int, int, int, int] = (255, 255, 255, 230)
    show_background: bool = True
    background_color: tuple[int, int, int, int] = (35, 35, 35, 255)
    background_opacity: float = 0.3
    border_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    border_opacity: float = 1.0
    selection_mode: str = "most_recent"
    custom_appid: int | None = None
    field_visibility: tuple[tuple[str, bool], ...] = _FIELD_DEFAULTS
    latest_unlock_count: int = 1
    show_latest_artwork: bool = True
    show_artwork: bool = True
    artwork_shape: str = "portrait"
    square_artwork_size: int = 140
    double_capsules: bool = True
    capsule_font_size: int = 12
    capsule_fill_color: tuple[int, int, int, int] = ACHIEVEMENT_CAPSULE_FILL_RGBA
    capsule_border_color: tuple[int, int, int, int] = ACHIEVEMENT_CAPSULE_BORDER_RGBA
    refresh_minutes: int = 10
    show_connection_info_icon: bool = True

    @classmethod
    def from_widgets_mapping(
        cls,
        widgets: Mapping[str, object],
    ) -> "AchievementPulsePresentationConfig":
        """Project canonical shared-Steam and Achievement Pulse settings."""

        from core.settings.defaults import get_default_settings

        defaults = get_default_settings().get("widgets", {})
        default_shared = defaults.get("steam", {}) if isinstance(defaults, Mapping) else {}
        default_card = (
            defaults.get("achievement_pulse", {})
            if isinstance(defaults, Mapping)
            else {}
        )
        shared = widgets.get("steam", {}) if isinstance(widgets, Mapping) else {}
        card = (
            widgets.get("achievement_pulse", {})
            if isinstance(widgets, Mapping)
            else {}
        )
        merged_shared = dict(default_shared) if isinstance(default_shared, Mapping) else {}
        merged_card = dict(default_card) if isinstance(default_card, Mapping) else {}
        if isinstance(shared, Mapping):
            merged_shared.update(shared)
        if isinstance(card, Mapping):
            merged_card.update(card)

        field_visibility = tuple(
            (
                field_id,
                _as_bool(merged_card.get(f"show_{field_id}"), default),
            )
            for field_id, default in _FIELD_DEFAULTS
        )
        return cls(
            font_family=str(merged_card.get("font_family", "Inter") or "Inter"),
            font_size=_bounded_int(merged_card.get("font_size"), 14, 8, 96),
            text_color=_rgba(
                merged_card.get("color"),
                (255, 255, 255, 230),
            ),
            show_background=_as_bool(
                merged_card.get("show_background"), True
            ),
            background_color=_rgba(
                merged_card.get("bg_color"),
                (35, 35, 35, 255),
            ),
            background_opacity=_bounded_float(
                merged_card.get("bg_opacity"), 0.3, 0.0, 1.0
            ),
            border_color=_rgba(
                merged_card.get("border_color"),
                (255, 255, 255, 255),
            ),
            border_opacity=_bounded_float(
                merged_card.get("border_opacity"), 1.0, 0.0, 1.0
            ),
            selection_mode=str(
                merged_card.get("selection_mode", "most_recent")
                or "most_recent"
            ),
            custom_appid=_optional_appid(merged_card.get("custom_appid")),
            field_visibility=field_visibility,
            latest_unlock_count=_bounded_int(
                merged_card.get("latest_unlock_count"), 1, 1, 5
            ),
            show_latest_artwork=_as_bool(
                merged_card.get("show_latest_achievement_artwork"), True
            ),
            show_artwork=_as_bool(merged_card.get("show_artwork"), True),
            artwork_shape=normalize_achievement_artwork_shape(
                merged_card.get("artwork_shape", "portrait")
            ),
            square_artwork_size=normalize_achievement_square_artwork_size(
                merged_card.get("square_artwork_size", 140)
            ),
            double_capsules=_as_bool(
                merged_card.get(
                    "double_capsules",
                    merged_card.get("double_capsule_long_data", True),
                ),
                True,
            ),
            capsule_font_size=normalize_achievement_capsule_font_size(
                merged_card.get("capsule_font_size", 12)
            ),
            capsule_fill_color=_rgba(
                merged_card.get("capsule_fill_color"),
                ACHIEVEMENT_CAPSULE_FILL_RGBA,
            ),
            capsule_border_color=_rgba(
                merged_card.get("capsule_border_color"),
                ACHIEVEMENT_CAPSULE_BORDER_RGBA,
            ),
            refresh_minutes=_bounded_int(
                merged_shared.get("refresh_minutes"), 10, 5, 1440
            ),
            show_connection_info_icon=_as_bool(
                merged_shared.get("show_connection_info_icon"), True
            ),
        )

    @property
    def runtime_config(self) -> AchievementPulseRuntimeConfig:
        return AchievementPulseRuntimeConfig(
            selection=AchievementPulseSelection(
                mode=self.selection_mode,
                custom_appid=self.custom_appid,
            ),
            field_visibility=dict(self.field_visibility),
            latest_unlock_count=self.latest_unlock_count,
            show_latest_artwork=self.show_latest_artwork,
            show_artwork=self.show_artwork,
            artwork_shape=self.artwork_shape,
            refresh_minutes=self.refresh_minutes,
            show_connection_info_icon=self.show_connection_info_icon,
        )

    @property
    def authored_size(self) -> tuple[float, float]:
        field_count = sum(1 for _field_id, enabled in self.field_visibility if enabled)
        capsule_height, capsule_gap = achievement_capsule_geometry(
            font_family=self.font_family,
            capsule_font_size=self.capsule_font_size,
        )
        size = achievement_pulse_authored_size(
            show_artwork=self.show_artwork,
            artwork_shape=self.artwork_shape,
            artwork_size=self.square_artwork_size,
            field_rail_count=achievement_field_rail_count(
                field_count,
                double_capsules=self.double_capsules,
            ),
            capsule_height=capsule_height,
            capsule_gap=capsule_gap,
        )
        return float(size.width()), float(size.height())


@dataclass(frozen=True)
class AchievementPulsePresentationStyle:
    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float

    @classmethod
    def project(
        cls,
        config: AchievementPulsePresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "AchievementPulsePresentationStyle":
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
        shadow_rgba = _rgba(shadow_values.get("color"), (0, 0, 0, 255))
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
                corner_radius=10.0,
                padding=0.0,
                shadow_enabled=(
                    config.show_background
                    and _as_bool(shadow_values.get("enabled"), True)
                ),
                shadow_color=_with_alpha(
                    shadow_rgba,
                    _bounded_float(
                        shadow_values.get("frame_opacity"), 0.77, 0.0, 1.0
                    ),
                ),
                shadow_blur=_bounded_float(
                    shadow_values.get("blur_radius"), 18.0, 0.0, 80.0
                ),
                shadow_offset_x=card_offset[0],
                shadow_offset_y=card_offset[1],
            ),
            text_shadow_enabled=_as_bool(
                shadow_values.get("text_enabled"), True
            ),
            text_shadow_color=_with_alpha(
                shadow_rgba,
                _bounded_float(
                    shadow_values.get("text_opacity"), 0.33, 0.0, 1.0
                ),
            ),
            text_shadow_offset_x=text_offset[0],
            text_shadow_offset_y=text_offset[1],
        )


class AchievementPulseFieldListModel(QAbstractListModel):
    FieldIdRole = int(Qt.ItemDataRole.UserRole) + 1
    LabelRole = FieldIdRole + 1
    ValueRole = FieldIdRole + 2

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[SteamCardField, ...] = ()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        return {
            self.FieldIdRole: row.field_id,
            self.LabelRole: row.label,
            self.ValueRole: row.value,
            int(Qt.ItemDataRole.DisplayRole): row.value,
        }.get(int(role))

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            self.FieldIdRole: b"fieldId",
            self.LabelRole: b"fieldLabel",
            self.ValueRole: b"fieldValue",
        }

    @property
    def rows(self) -> tuple[SteamCardField, ...]:
        return self._rows

    def replace_rows(self, rows: Iterable[SteamCardField]) -> bool:
        resolved = tuple(row for row in rows if row.enabled)
        if resolved == self._rows:
            return False
        previous = self._rows
        old_count = len(previous)
        new_count = len(resolved)
        common = min(old_count, new_count)
        if new_count < old_count:
            self.beginRemoveRows(QModelIndex(), new_count, old_count - 1)
            self._rows = previous[:new_count]
            self.endRemoveRows()
        elif new_count > old_count:
            self.beginInsertRows(QModelIndex(), old_count, new_count - 1)
            self._rows = (*previous, *resolved[old_count:])
            self.endInsertRows()
        if common:
            mutable = list(self._rows)
            changed = []
            for index in range(common):
                if mutable[index] != resolved[index]:
                    mutable[index] = resolved[index]
                    changed.append(index)
            self._rows = tuple(mutable)
            if changed:
                self.dataChanged.emit(
                    self.index(min(changed), 0),
                    self.index(max(changed), 0),
                    [self.FieldIdRole, self.LabelRole, self.ValueRole],
                )
        if new_count > common:
            self._rows = resolved
        return True


@dataclass(frozen=True)
class AchievementPulseUnlockRow:
    identity: str
    text: str


class AchievementPulseUnlockListModel(QAbstractListModel):
    IdentityRole = int(Qt.ItemDataRole.UserRole) + 1
    TextRole = IdentityRole + 1

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[AchievementPulseUnlockRow, ...] = ()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        return {
            self.IdentityRole: row.identity,
            self.TextRole: row.text,
            int(Qt.ItemDataRole.DisplayRole): row.text,
        }.get(int(role))

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            self.IdentityRole: b"unlockIdentity",
            self.TextRole: b"unlockText",
        }

    @property
    def rows(self) -> tuple[AchievementPulseUnlockRow, ...]:
        return self._rows

    def replace_rows(self, values: Iterable[str]) -> bool:
        resolved = tuple(
            AchievementPulseUnlockRow(f"{index}:{text}", str(text))
            for index, text in enumerate(values)
            if str(text).strip()
        )
        if resolved == self._rows:
            return False
        previous = self._rows
        old_count = len(previous)
        new_count = len(resolved)
        common = min(old_count, new_count)
        if new_count < old_count:
            self.beginRemoveRows(QModelIndex(), new_count, old_count - 1)
            self._rows = previous[:new_count]
            self.endRemoveRows()
        elif new_count > old_count:
            self.beginInsertRows(QModelIndex(), old_count, new_count - 1)
            self._rows = (*previous, *resolved[old_count:])
            self.endInsertRows()
        if common:
            mutable = list(self._rows)
            changed = []
            for index in range(common):
                if mutable[index] != resolved[index]:
                    mutable[index] = resolved[index]
                    changed.append(index)
            self._rows = tuple(mutable)
            if changed:
                self.dataChanged.emit(
                    self.index(min(changed), 0),
                    self.index(max(changed), 0),
                    [self.IdentityRole, self.TextRole],
                )
        if new_count > common:
            self._rows = resolved
        return True


@dataclass(frozen=True)
class AchievementPulsePresentationSnapshot:
    config: AchievementPulsePresentationConfig
    style: AchievementPulsePresentationStyle
    card: SteamCardViewModel
    artwork_source: str = ""
    artwork_identity: str = ""
    latest_artwork_source: str = ""
    latest_artwork_identity: str = ""
    interaction_enabled: bool = False


class AchievementPulsePresentationModel(QObject):
    """Stable retained state for one Achievement Pulse card."""

    stateChanged = Signal()
    fadeRequested = Signal()

    def __init__(
        self,
        config: AchievementPulsePresentationConfig,
        style: AchievementPulsePresentationStyle,
        *,
        runtime_service: Any | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        card = build_steam_connect_required_view_model("achievement_pulse")
        self._snapshot = AchievementPulsePresentationSnapshot(
            config=config,
            style=style,
            card=card,
        )
        self._field_model = AchievementPulseFieldListModel(self)
        self._unlock_model = AchievementPulseUnlockListModel(self)
        self._achievement_runtime_service = runtime_service
        self._runtime_attached = False
        self._active = False
        self._retired = False

    @property
    def config(self) -> AchievementPulsePresentationConfig:
        return self._snapshot.config

    @property
    def style(self) -> AchievementPulsePresentationStyle:
        return self._snapshot.style

    @property
    def card(self) -> SteamCardViewModel:
        return self._snapshot.card

    @property
    def field_model(self) -> AchievementPulseFieldListModel:
        return self._field_model

    @property
    def unlock_model(self) -> AchievementPulseUnlockListModel:
        return self._unlock_model

    @property
    def is_active(self) -> bool:
        return self._active and not self._retired

    def is_achievement_consumer_alive(self) -> bool:
        return self.is_active

    def set_achievement_runtime_service(self, service: Any) -> None:
        if self._retired or self._active:
            raise RuntimeError(
                "cannot replace Achievement Pulse runtime after activation"
            )
        if self._achievement_runtime_service is service:
            return
        if self._achievement_runtime_service is not None:
            raise RuntimeError(
                "Achievement Pulse presentation already has a runtime service"
            )
        self._achievement_runtime_service = service

    def activate(self, thread_manager: Any | None = None) -> bool:
        if self._retired:
            raise RuntimeError("cannot activate a retired Achievement Pulse model")
        if self._active:
            return True
        service = self._achievement_runtime_service
        if service is not None:
            if thread_manager is None:
                raise RuntimeError(
                    "Achievement Pulse runtime activation requires ThreadManager"
                )
            service.configure(self.config.runtime_config)
            service.set_thread_manager(thread_manager)
            service.attach_consumer(self)
            self._runtime_attached = True
        self._active = True
        if service is not None and not service.start(start_fade_after_load=True):
            self._active = False
            service.detach_consumer(self)
            self._runtime_attached = False
            self._achievement_runtime_service = None
            raise RuntimeError("Achievement Pulse runtime service failed to start")
        return True

    def on_achievement_presentation(
        self,
        presentation: AchievementPulsePreparedPresentation,
        *,
        animate: bool,
    ) -> None:
        del animate
        if not self.is_active or presentation.model.card_id != "achievement_pulse":
            return
        card = presentation.model
        rows_changed = self._field_model.replace_rows(card.fields)
        unlocks_changed = self._unlock_model.replace_rows(card.latest_unlocks)
        snapshot = replace(
            self._snapshot,
            card=card,
            artwork_source=_image_source(
                presentation.artwork,
                presentation.artwork_identity,
            ),
            artwork_identity=str(presentation.artwork_identity or ""),
            latest_artwork_source=_image_source(
                presentation.latest_artwork,
                presentation.latest_artwork_identity,
            ),
            latest_artwork_identity=str(
                presentation.latest_artwork_identity or ""
            ),
        )
        state_changed = snapshot != self._snapshot
        self._snapshot = snapshot
        if rows_changed or unlocks_changed or state_changed:
            self.stateChanged.emit()

    def request_achievement_fade(self) -> None:
        if self.is_active:
            self.fadeRequested.emit()

    def request_manual_refresh(self) -> bool:
        return bool(
            self.is_active
            and self._snapshot.interaction_enabled
            and self._achievement_runtime_service is not None
            and self._achievement_runtime_service.request_manual_refresh()
        )

    def notify_fade_complete(self) -> None:
        if self.is_active and self._achievement_runtime_service is not None:
            self._achievement_runtime_service.on_presentation_fade_complete()

    def set_interaction_enabled(self, enabled: bool) -> bool:
        normalized = bool(enabled)
        if normalized == self._snapshot.interaction_enabled:
            return False
        self._snapshot = replace(
            self._snapshot,
            interaction_enabled=normalized,
        )
        self.stateChanged.emit()
        return True

    def apply_style(self, style: AchievementPulsePresentationStyle) -> bool:
        if self._retired or style == self.style:
            return False
        self._snapshot = replace(self._snapshot, style=style)
        self.stateChanged.emit()
        return True

    def retire(self) -> None:
        if self._retired:
            return
        self._retired = True
        self._active = False
        if self._achievement_runtime_service is not None and self._runtime_attached:
            self._achievement_runtime_service.stop()
            self._achievement_runtime_service.detach_consumer(self)
        self._runtime_attached = False
        self._achievement_runtime_service = None
        self._field_model.replace_rows(())
        self._unlock_model.replace_rows(())

    @Property(QObject, constant=True)
    def fieldModel(self) -> QObject:
        return self._field_model

    @Property(QObject, constant=True)
    def unlockModel(self) -> QObject:
        return self._unlock_model

    @Property(str, notify=stateChanged)
    def headerText(self) -> str:
        return self.card.header

    @Property(str, notify=stateChanged)
    def title(self) -> str:
        return self.card.title

    @Property(str, notify=stateChanged)
    def subtitle(self) -> str:
        return self.card.subtitle

    @Property(str, notify=stateChanged)
    def metricLabel(self) -> str:
        return self.card.metric_label

    @Property(str, notify=stateChanged)
    def metricValue(self) -> str:
        return self.card.metric_value

    @Property(str, notify=stateChanged)
    def statusText(self) -> str:
        return self.card.status

    @Property(str, notify=stateChanged)
    def viewState(self) -> str:
        return self.card.state

    @Property(bool, notify=stateChanged)
    def interactionEnabled(self) -> bool:
        return self._snapshot.interaction_enabled

    @Property(bool, notify=stateChanged)
    def showConnectionInfo(self) -> bool:
        return self.card.show_connection_info

    @Property(str, notify=stateChanged)
    def connectionInfoTarget(self) -> str:
        return self.card.connection_info_target

    @Property(str, notify=stateChanged)
    def connectionInfoTooltip(self) -> str:
        return self.card.connection_info_tooltip

    @Property(str, notify=stateChanged)
    def settingsTarget(self) -> str:
        return self.card.settings_target

    @Property(str, notify=stateChanged)
    def actionText(self) -> str:
        return self.card.action_text

    @Property(str, notify=stateChanged)
    def actionLabel(self) -> str:
        return self.card.action_label

    @Property(QColor, notify=stateChanged)
    def accentColor(self) -> QColor:
        color = QColor(self.card.accent)
        return color if color.isValid() else QColor(199, 213, 224, 255)

    @Property(str, constant=True)
    def logoSource(self) -> str:
        return _STEAM_LOGO.resolve().as_uri() if _STEAM_LOGO.is_file() else ""

    @Property(str, notify=stateChanged)
    def artworkSource(self) -> str:
        return self._snapshot.artwork_source

    @Property(str, notify=stateChanged)
    def latestArtworkSource(self) -> str:
        return self._snapshot.latest_artwork_source

    @Property(bool, notify=stateChanged)
    def showArtwork(self) -> bool:
        return self.config.show_artwork

    @Property(bool, notify=stateChanged)
    def showLatestArtwork(self) -> bool:
        return self.config.show_latest_artwork

    @Property(str, notify=stateChanged)
    def artworkShape(self) -> str:
        return self.config.artwork_shape

    @Property(float, notify=stateChanged)
    def squareArtworkSize(self) -> float:
        return float(self.config.square_artwork_size)

    @Property(bool, notify=stateChanged)
    def doubleCapsules(self) -> bool:
        return self.config.double_capsules

    @Property(float, notify=stateChanged)
    def capsuleFontSize(self) -> float:
        return float(self.config.capsule_font_size)

    @Property(float, notify=stateChanged)
    def capsuleHeight(self) -> float:
        return achievement_capsule_geometry(
            font_family=self.config.font_family,
            capsule_font_size=self.config.capsule_font_size,
        )[0]

    @Property(float, notify=stateChanged)
    def capsuleGap(self) -> float:
        return achievement_capsule_geometry(
            font_family=self.config.font_family,
            capsule_font_size=self.config.capsule_font_size,
        )[1]

    @Property(QColor, notify=stateChanged)
    def capsuleFillColor(self) -> QColor:
        return QColor(*self.config.capsule_fill_color)

    @Property(QColor, notify=stateChanged)
    def capsuleBorderColor(self) -> QColor:
        return QColor(*self.config.capsule_border_color)

    @Property(str, notify=stateChanged)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(float, notify=stateChanged)
    def fontSize(self) -> float:
        return float(self.config.font_size)

    @Property(QColor, notify=stateChanged)
    def textColor(self) -> QColor:
        return QColor(*self.config.text_color)

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
        return self.config.authored_size[0]

    @Property(float, notify=stateChanged)
    def authoredHeight(self) -> float:
        return self.config.authored_size[1]


class RetainedAchievementPulsePresentation:
    """One retained Achievement Pulse item with semantic action routing."""

    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: AchievementPulsePresentationModel,
        geometry: OverlayWidgetGeometry,
        fade_opacity: float = 0.0,
        on_settings_requested: Callable[[str], Any] | None = None,
    ) -> None:
        self._host = host
        self._model = model
        self._on_settings_requested = on_settings_requested
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "achievement_pulse",
            initial_properties={"achievementModel": model},
            object_name="achievement_pulse",
            geometry=geometry,
            fade_opacity=fade_opacity,
            card_style=model.style.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        self._connect("refreshRequested", model.request_manual_refresh)
        self._connect("settingsRequested", self._handle_settings_requested)
        model.fadeRequested.connect(self._handle_fade_requested)

    def _connect(self, signal_name: str, callback: Callable[..., Any]) -> None:
        signal = getattr(self._retained.item, signal_name, None)
        if signal is not None and hasattr(signal, "connect"):
            signal.connect(callback)

    @property
    def item(self):
        return self._retained.item

    @property
    def model(self) -> AchievementPulsePresentationModel:
        return self._model

    def activate(self, thread_manager: Any | None = None) -> bool:
        return self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def set_fade_opacity(self, opacity: float) -> None:
        self._retained.set_fade_opacity(opacity)

    def set_interaction_enabled(self, enabled: bool) -> bool:
        return self._model.set_interaction_enabled(enabled)

    def apply_input_state(self, input_state: object) -> bool:
        if isinstance(input_state, Mapping):
            value = input_state.get
        else:
            def value(name, default):
                return getattr(input_state, name, default)
        enabled = (
            bool(value("admission_open", True))
            and not bool(value("exiting", False))
            and (
                bool(value("interaction_mode_enabled", False))
                or bool(value("ctrl_held", False))
            )
        )
        return self._model.set_interaction_enabled(enabled)

    def apply_style(
        self,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> None:
        style = AchievementPulsePresentationStyle.project(
            self._model.config,
            shadow_values,
            border_width=border_width,
        )
        self._model.apply_style(style)
        self._retained.set_card_style(style.card_style)

    def _handle_settings_requested(self, target: str) -> bool:
        normalized = str(target or "").strip()
        if (
            not self._model.is_active
            or not self._model.interactionEnabled
            or not normalized
            or self._on_settings_requested is None
        ):
            return False
        return bool(self._on_settings_requested(normalized))

    def _handle_fade_requested(self) -> None:
        if not self._model.is_active:
            return
        self._retained.set_fade_opacity(1.0)
        self._model.notify_fade_complete()

    def retire(self) -> bool:
        return self._host.retire_widget(self._retained)


__all__ = [
    "AchievementPulseFieldListModel",
    "AchievementPulsePresentationConfig",
    "AchievementPulsePresentationModel",
    "AchievementPulsePresentationSnapshot",
    "AchievementPulsePresentationStyle",
    "AchievementPulseUnlockListModel",
    "AchievementPulseUnlockRow",
    "RetainedAchievementPulsePresentation",
]
