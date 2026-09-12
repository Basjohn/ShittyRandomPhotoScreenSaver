"""Retained Quick presentation for the Steam Friend Pulse card.

The module projects accepted neutral Friend Pulse snapshots into one stable Qt
list model.  Network, cache, cadence, credentials and avatar hydration stay in
the generation-shared runtime owner; QML receives presentation-safe text and
local image sources only.
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
from PySide6.QtGui import QColor

from core.settings.default_contract import require_canonical_default
from core.steam.friend_pulse import (
    FriendPulseProjection,
    FriendPulseRow,
    FriendPulseSnapshot,
)
from core.steam.models import SteamResultStatus

from .host import (
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)
from .steam_common import (
    SteamSemanticPalette,
    as_bool,
    bounded_float,
    bounded_int,
    project_steam_card_style,
    project_steam_semantic_palette,
    rgba,
)
from .theme_projection import (
    resolve_card_surface_colors,
    resolve_header_colors,
    resolve_primary_text_color,
    resolve_rgba_role,
)


_STEAM_LOGO = Path(__file__).resolve().parents[3] / "images" / "Steam_Logo_Cropped.png"
_STEAM_DEFAULTS = require_canonical_default("widgets.steam")
_FRIEND_DEFAULTS = require_canonical_default("widgets.friend_pulse")
if not isinstance(_STEAM_DEFAULTS, Mapping) or not isinstance(
    _FRIEND_DEFAULTS, Mapping
):
    raise TypeError("Canonical Steam/Friend Pulse defaults must be mappings")


def _grid_columns_for(capacity: int, authored_width: int) -> int:
    """Choose columns that leave changed-tile titles readable at narrow widths."""
    normalized_capacity = max(1, min(6, int(capacity)))
    normalized_width = max(420, min(900, int(authored_width)))
    if normalized_capacity <= 4:
        return 2
    # Three columns are attractive at large widths, but at the supported narrow
    # end they leave a changed tile only a few pixels after avatar and NEW-badge
    # reservations. Two columns keep the title allocation meaningful.
    return 2 if normalized_width < 540 else 3


@dataclass(frozen=True)
class FriendPulsePresentationConfig:
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
    accent_color: tuple[int, int, int, int]
    semantic_palette: SteamSemanticPalette
    refresh_minutes: int
    privacy_mode: str
    view_mode: str
    capacity: int
    authored_width: int

    @classmethod
    def from_widgets_mapping(
        cls, widgets: Mapping[str, object]
    ) -> "FriendPulsePresentationConfig":
        shared = widgets.get("steam", {}) if isinstance(widgets, Mapping) else {}
        card = widgets.get("friend_pulse", {}) if isinstance(widgets, Mapping) else {}
        merged_shared = dict(_STEAM_DEFAULTS)
        merged_card = dict(_FRIEND_DEFAULTS)
        if isinstance(shared, Mapping):
            merged_shared.update(shared)
        if isinstance(card, Mapping):
            merged_card.update(card)

        mode = str(merged_shared.get("privacy_mode", "Rich") or "Rich").title()
        if mode not in {"Strict", "Balanced", "Rich"}:
            mode = "Rich"
        view_mode = str(merged_card.get("view_mode", "grid") or "grid").lower()
        if view_mode not in {"rows", "grid"}:
            view_mode = "grid"
        config = cls(
            font_family=str(
                merged_card.get("font_family") or _FRIEND_DEFAULTS["font_family"]
            ),
            font_size=bounded_int(
                merged_card.get("font_size"),
                int(_FRIEND_DEFAULTS["font_size"]),
                8,
                96,
            ),
            text_color=rgba(merged_card.get("color"), tuple(_FRIEND_DEFAULTS["color"])),
            show_background=as_bool(
                merged_card.get("show_background"),
                bool(_FRIEND_DEFAULTS["show_background"]),
            ),
            background_color=rgba(
                merged_card.get("bg_color"), tuple(_FRIEND_DEFAULTS["bg_color"])
            ),
            background_opacity=bounded_float(
                merged_card.get("bg_opacity"),
                float(_FRIEND_DEFAULTS["bg_opacity"]),
                0.0,
                1.0,
            ),
            border_color=rgba(
                merged_card.get("border_color"),
                tuple(_FRIEND_DEFAULTS["border_color"]),
            ),
            border_opacity=bounded_float(
                merged_card.get("border_opacity"),
                float(_FRIEND_DEFAULTS["border_opacity"]),
                0.0,
                1.0,
            ),
            header_fill_color=rgba(
                merged_card.get("header_fill_color"),
                tuple(_FRIEND_DEFAULTS["header_fill_color"]),
            ),
            header_border_color=rgba(
                merged_card.get("header_border_color"),
                tuple(_FRIEND_DEFAULTS["header_border_color"]),
            ),
            header_text_color=rgba(
                merged_card.get("header_text_color"),
                tuple(_FRIEND_DEFAULTS["header_text_color"]),
            ),
            accent_color=rgba(
                merged_card.get("accent_color"),
                tuple(_FRIEND_DEFAULTS["accent_color"]),
            ),
            semantic_palette=SteamSemanticPalette(),
            refresh_minutes=bounded_int(
                merged_shared.get("refresh_minutes"),
                int(_STEAM_DEFAULTS["refresh_minutes"]),
                5,
                240,
            ),
            privacy_mode=mode,
            view_mode=view_mode,
            capacity=bounded_int(
                merged_card.get("visible_row_capacity"),
                int(_FRIEND_DEFAULTS["visible_row_capacity"]),
                1,
                6,
            ),
            authored_width=bounded_int(
                merged_card.get("preferred_width"),
                int(_FRIEND_DEFAULTS["preferred_width"]),
                420,
                900,
            ),
        )
        header_fill, header_border, header_text = resolve_header_colors(
            "friend_pulse",
            values=card if isinstance(card, Mapping) else {},
            defaults=_FRIEND_DEFAULTS,
            fill=config.header_fill_color,
            border=config.header_border_color,
            text=config.header_text_color,
        )
        card_background, card_border = resolve_card_surface_colors(
            values=card if isinstance(card, Mapping) else {},
            defaults=_FRIEND_DEFAULTS,
            background_color=config.background_color,
            background_opacity=config.background_opacity,
            border_color=config.border_color,
            border_opacity=config.border_opacity,
        )
        text_color = resolve_primary_text_color(
            values=card if isinstance(card, Mapping) else {},
            defaults=_FRIEND_DEFAULTS,
            text_color=config.text_color,
        )
        accent = resolve_rgba_role(
            "steam.friend_pulse.accent",
            local_roles={"local.accent": config.accent_color},
            fallback=config.accent_color,
        )
        palette = project_steam_semantic_palette(
            fallback=SteamSemanticPalette(
                metric_surface=(25, 90, 128, 92),
                metric_border=(102, 192, 244, 205),
                metric_inner_border=(102, 192, 244, 92),
                metric_separator=(146, 202, 232, 92),
            )
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
            accent_color=accent,
            semantic_palette=palette,
        )

    @property
    def authored_height(self) -> int:
        # Header/summary/footer remain fixed; configured capacity/view alone
        # own body height. Source row count never changes geometry.
        if self.view_mode == "grid":
            columns = _grid_columns_for(self.capacity, self.authored_width)
            grid_rows = (self.capacity + columns - 1) // columns
            return 120 + grid_rows * 102 + max(0, grid_rows - 1) * 10
        return 102 + self.capacity * 58


@dataclass(frozen=True)
class FriendPulsePresentationStyle:
    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float

    @classmethod
    def project(
        cls,
        config: FriendPulsePresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "FriendPulsePresentationStyle":
        projected = project_steam_card_style(
            show_background=config.show_background,
            background_color=config.background_color,
            background_opacity=config.background_opacity,
            border_color=config.border_color,
            border_opacity=config.border_opacity,
            shadow_values=shadow_values,
            border_width=border_width,
        )
        return cls(
            card_style=projected.card_style,
            text_shadow_enabled=projected.text_shadow_enabled,
            text_shadow_color=projected.text_shadow_color,
            text_shadow_offset_x=projected.text_shadow_offset_x,
            text_shadow_offset_y=projected.text_shadow_offset_y,
        )


class FriendPulseRowListModel(QAbstractListModel):
    PrimaryRole = int(Qt.ItemDataRole.UserRole) + 1
    SecondaryRole = PrimaryRole + 1
    PresenceRole = PrimaryRole + 2
    OnlineRole = PrimaryRole + 3
    ChangedRole = PrimaryRole + 4
    AvatarSourceRole = PrimaryRole + 5
    CountRole = PrimaryRole + 6
    FriendActionRole = PrimaryRole + 7
    GameActionRole = PrimaryRole + 8

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[FriendPulseRow, ...] = ()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(
        self,
        index: QModelIndex,
        role: int = int(Qt.ItemDataRole.DisplayRole),
    ) -> Any:
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        avatar_source = str(getattr(row, "avatar_url", "") or "")
        if avatar_source and not avatar_source.lower().startswith("file:"):
            avatar_source = ""
        return {
            self.PrimaryRole: row.primary,
            self.SecondaryRole: row.secondary,
            self.PresenceRole: row.presence_text,
            self.OnlineRole: row.online,
            self.ChangedRole: row.changed,
            self.AvatarSourceRole: avatar_source,
            self.CountRole: row.count,
            self.FriendActionRole: row.friend_action_available,
            self.GameActionRole: bool(row.game_appid),
            int(Qt.ItemDataRole.DisplayRole): row.primary,
        }.get(int(role))

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            self.PrimaryRole: b"primaryText",
            self.SecondaryRole: b"secondaryText",
            self.PresenceRole: b"presenceText",
            self.OnlineRole: b"isOnline",
            self.ChangedRole: b"changed",
            self.AvatarSourceRole: b"avatarSource",
            self.CountRole: b"friendCount",
            self.FriendActionRole: b"friendActionAvailable",
            self.GameActionRole: b"gameActionAvailable",
        }

    @property
    def rows(self) -> tuple[FriendPulseRow, ...]:
        return self._rows

    def replace_rows(self, rows: Iterable[FriendPulseRow]) -> bool:
        resolved = tuple(rows)
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
        changed_indices: list[int] = []
        mutable = list(self._rows)
        for offset in range(common):
            if mutable[offset] != resolved[offset]:
                mutable[offset] = resolved[offset]
                changed_indices.append(offset)
        self._rows = tuple(mutable)
        if changed_indices:
            self.dataChanged.emit(
                self.index(min(changed_indices), 0),
                self.index(max(changed_indices), 0),
                [
                    self.PrimaryRole,
                    self.SecondaryRole,
                    self.PresenceRole,
                    self.OnlineRole,
                    self.ChangedRole,
                    self.AvatarSourceRole,
                    self.CountRole,
                    self.FriendActionRole,
                    self.GameActionRole,
                ],
            )
        if new_count > common:
            self._rows = resolved
        return True


class FriendPulsePresentationModel(QObject):
    stateChanged = Signal()

    def __init__(
        self,
        config: FriendPulsePresentationConfig,
        style: FriendPulsePresentationStyle,
        *,
        runtime_generation: int | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.style = style
        self._runtime_generation = runtime_generation
        self._thread_manager: Any | None = None
        self._runtime_service: Any | None = None
        self._runtime_attached = False
        self._row_model = FriendPulseRowListModel(self)
        self._snapshot: FriendPulseSnapshot | None = None
        self._projection = FriendPulseProjection("loading", "Checking Steam", ())
        self._active = False
        self._retired = False
        self._interaction_enabled = False

    @property
    def is_active(self) -> bool:
        return self._active and not self._retired

    def is_lifecycle_active(self) -> bool:
        return self.is_active

    def is_friend_pulse_consumer_alive(self) -> bool:
        return self.is_active

    def set_runtime_service(self, service: Any) -> None:
        if self._retired or self._active:
            raise RuntimeError("cannot replace Friend Pulse runtime after activation")
        if self._runtime_service is service:
            return
        if self._runtime_service is not None:
            raise RuntimeError("Friend Pulse already has a runtime service")
        self._runtime_service = service

    def activate(self, thread_manager: Any | None = None) -> bool:
        if self._retired:
            raise RuntimeError("cannot activate retired Friend Pulse model")
        if self._active:
            return True
        service = self._runtime_service
        if service is None or thread_manager is None:
            raise RuntimeError("Friend Pulse activation requires its shared service")
        from widgets.friend_pulse_runtime import FriendPulseRuntimeConfig

        self._thread_manager = thread_manager
        service.set_thread_manager(thread_manager)
        service.configure(
            FriendPulseRuntimeConfig(
                refresh_minutes=self.config.refresh_minutes,
                privacy_mode=self.config.privacy_mode,
                capacity=self.config.capacity,
            )
        )
        service.attach_consumer(self)
        self._runtime_attached = True
        self._active = True
        if not service.start():
            self._active = False
            service.detach_consumer(self)
            self._runtime_attached = False
            raise RuntimeError("Friend Pulse shared service failed to start")
        return True

    def on_friend_pulse_runtime_snapshot(
        self,
        snapshot: FriendPulseSnapshot,
        projection: FriendPulseProjection,
    ) -> None:
        if not self.is_active:
            return
        if snapshot == self._snapshot and projection == self._projection:
            return
        rows_changed = self._row_model.replace_rows(projection.rows)
        previous_state = (
            self._projection.state,
            self._projection.primary_metric,
            self._projection.overflow_count,
            self._snapshot.online_count if self._snapshot else None,
        )
        self._snapshot = snapshot
        self._projection = projection
        current_state = (
            projection.state,
            projection.primary_metric,
            projection.overflow_count,
            snapshot.online_count,
        )
        if rows_changed or current_state != previous_state:
            self.stateChanged.emit()

    def request_manual_refresh(self) -> bool:
        return bool(
            self.is_active
            and self._interaction_enabled
            and self._runtime_service is not None
            and self._runtime_service.refresh()
        )

    def friend_action_target(self, row_index: int) -> str | None:
        """Resolve a visible row through the owner-only private ID map."""

        if (
            not self.is_active
            or not self._interaction_enabled
            or self._runtime_service is None
        ):
            return None
        try:
            row = self._row_model.rows[int(row_index)]
        except (IndexError, TypeError, ValueError):
            return None
        if not row.identity_fingerprint or not row.friend_action_available:
            return None
        return self._runtime_service.friend_steam_id(row.identity_fingerprint)

    def game_action_target(self, row_index: int) -> str | None:
        if not self.is_active or not self._interaction_enabled:
            return None
        try:
            appid = self._row_model.rows[int(row_index)].game_appid
        except (IndexError, TypeError, ValueError):
            return None
        return str(appid) if appid is not None and int(appid) > 0 else None

    def set_interaction_enabled(self, enabled: bool) -> bool:
        value = bool(enabled)
        if value == self._interaction_enabled:
            return False
        self._interaction_enabled = value
        self.stateChanged.emit()
        return True

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
        self._snapshot = None
        self._row_model.replace_rows(())

    @Property(QObject, constant=True)
    def rowModel(self) -> QObject:
        return self._row_model

    @Property(bool, notify=stateChanged)
    def hasRows(self) -> bool:
        return bool(self._row_model.rows)

    @Property(str, notify=stateChanged)
    def viewState(self) -> str:
        if (
            self._snapshot is not None
            and self._snapshot.status == SteamResultStatus.NOT_CONFIGURED
        ):
            return "connect_required"
        return self._projection.state

    @Property(str, notify=stateChanged)
    def primaryMetric(self) -> str:
        return self._projection.primary_metric

    @Property(str, notify=stateChanged)
    def secondaryMetric(self) -> str:
        if self._projection.overflow_count > 0:
            return f"+{self._projection.overflow_count} more playing"
        online = self._snapshot.online_count if self._snapshot is not None else None
        if online is not None and online > 0:
            return f"{online} online"
        if self._projection.state == "stale":
            return "Cached Steam snapshot"
        return ""

    @Property(bool, notify=stateChanged)
    def interactionEnabled(self) -> bool:
        return self._interaction_enabled

    @Property(str, constant=True)
    def headerText(self) -> str:
        return "Friend Pulse"

    @Property(str, constant=True)
    def viewMode(self) -> str:
        return self.config.view_mode

    @Property(int, constant=True)
    def gridColumns(self) -> int:
        return _grid_columns_for(self.config.capacity, self.config.authored_width)

    @Property(str, constant=True)
    def logoSource(self) -> str:
        return _STEAM_LOGO.resolve().as_uri() if _STEAM_LOGO.is_file() else ""

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
        color.setAlpha(max(90, int(color.alpha() * 0.68)))
        return color

    @Property(QColor, notify=stateChanged)
    def accentColor(self) -> QColor:
        return QColor(*self.config.accent_color)

    @Property(QColor, notify=stateChanged)
    def rowSurfaceColor(self) -> QColor:
        return QColor(*self.config.semantic_palette.metric_surface)

    @Property(QColor, notify=stateChanged)
    def rowBorderColor(self) -> QColor:
        return QColor(*self.config.semantic_palette.metric_border)

    @Property(QColor, notify=stateChanged)
    def rowInnerBorderColor(self) -> QColor:
        return QColor(*self.config.semantic_palette.metric_inner_border)

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


class RetainedFriendPulsePresentation:
    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: FriendPulsePresentationModel,
        geometry: OverlayWidgetGeometry,
        on_steam_action_requested: Callable[[str, str], bool] | None = None,
    ) -> None:
        self._model = model
        self._on_steam_action_requested = on_steam_action_requested
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "friend_pulse",
            initial_properties={"friendPulseModel": model},
            object_name="friend_pulse",
            model_identity="friend_pulse",
            geometry=geometry,
            fade_opacity=1.0,
            card_style=model.style.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(lambda _payload: None)
        host.set_widget_input_state_handler(self._retained, self.apply_input_state)
        refresh = getattr(self._retained.item, "refreshRequested", None)
        if refresh is not None and hasattr(refresh, "connect"):
            refresh.connect(model.request_manual_refresh)
        self._connect("friendActionRequested", self._handle_friend_action)
        self._connect("gameActionRequested", self._handle_game_action)

    def _connect(self, signal_name: str, callback: Callable[..., Any]) -> None:
        signal = getattr(self._retained.item, signal_name, None)
        if signal is not None and hasattr(signal, "connect"):
            signal.connect(callback)

    def _handle_friend_action(self, row_index: int) -> bool:
        target = self._model.friend_action_target(row_index)
        if target is None or self._on_steam_action_requested is None:
            return False
        return bool(self._on_steam_action_requested("friend_message", target))

    def _handle_game_action(self, row_index: int) -> bool:
        target = self._model.game_action_target(row_index)
        if target is None or self._on_steam_action_requested is None:
            return False
        return bool(self._on_steam_action_requested("store", target))

    @property
    def item(self) -> Any:
        return self._retained.item

    @property
    def model(self) -> FriendPulsePresentationModel:
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
        value = (
            input_state.get
            if isinstance(input_state, Mapping)
            else lambda name, default: getattr(input_state, name, default)
        )
        enabled = (
            bool(value("admission_open", True))
            and not bool(value("exiting", False))
            and (
                bool(value("interaction_mode_enabled", False))
                or bool(value("ctrl_held", False))
            )
        )
        return self._model.set_interaction_enabled(enabled)

    def retire(self) -> bool:
        return self._retained.retire()


__all__ = [
    "FriendPulsePresentationConfig",
    "FriendPulsePresentationModel",
    "FriendPulsePresentationStyle",
    "FriendPulseRowListModel",
    "RetainedFriendPulsePresentation",
]
