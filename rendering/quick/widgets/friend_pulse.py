"""Retained Quick presentation for the Steam Friend Pulse card.

The module projects accepted neutral Friend Pulse snapshots into one stable Qt
list model.  Network, cache, cadence, credentials and avatar hydration stay in
the generation-shared runtime owner; QML receives presentation-safe text and
local image sources only.
"""

from __future__ import annotations

import re
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
from rendering.custom_child_geometry import (
    CustomChildSize,
    child_role_map,
    clamp_child_geometry,
)
from rendering.widget_descriptors import get_widget_runtime_descriptor

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


_GRID_TILE_HEIGHT = 132
_GRID_GAP = 10
_FRIEND_NAME_WORD_RE = re.compile(r"[^\W_]+(?:['’][^\W_]+)*", re.UNICODE)
_FRIEND_NAME_CONTRACTION_SUFFIXES = frozenset({"d", "ll", "m", "re", "s", "t", "ve"})


def _title_case_friend_name(value: object) -> str:
    """Presentation-only title case for roster names, preserving punctuation."""

    text = str(value or "").strip()
    if not text:
        return ""

    def _normalize_word(match: re.Match[str]) -> str:
        word = match.group(0).lower()
        pieces = re.split(r"(['’])", word)
        if pieces and pieces[0]:
            pieces[0] = pieces[0][0].upper() + pieces[0][1:]
        for index in range(2, len(pieces), 2):
            segment = pieces[index]
            if segment and segment not in _FRIEND_NAME_CONTRACTION_SUFFIXES:
                pieces[index] = segment[0].upper() + segment[1:]
        return "".join(pieces)

    return _FRIEND_NAME_WORD_RE.sub(_normalize_word, text)


def _grid_columns_for(
    capacity: int,
    authored_width: int,
    *,
    custom_horizontal_extent: bool = False,
    avatar_scale: float = 1.0,
    frame_width_scale: float = 1.0,
    frame_baseline_width: float = 108.0,
) -> int:
    """Fit readable avatar cells to the current logical card width.

    ``visible_row_capacity`` owns the authored/baseline card, but a CUSTOM
    horizontal content extent is an explicit request to use additional width.
    In that mode the width itself may admit additional columns instead of
    retaining the baseline slot count as an accidental column ceiling.
    """

    normalized_capacity = max(1, min(24, int(capacity)))
    normalized_width = max(420, min(4000, int(authored_width)))
    content_width = normalized_width - 36
    try:
        resolved_avatar_scale = float(avatar_scale)
    except (TypeError, ValueError):
        resolved_avatar_scale = 1.0
    if (
        resolved_avatar_scale != resolved_avatar_scale
        or resolved_avatar_scale <= 0.0
        or resolved_avatar_scale == float("inf")
    ):
        resolved_avatar_scale = 1.0
    resolved_avatar_scale = max(0.55, min(2.00, resolved_avatar_scale))
    try:
        resolved_frame_scale = float(frame_width_scale)
    except (TypeError, ValueError):
        resolved_frame_scale = 1.0
    if (
        resolved_frame_scale != resolved_frame_scale
        or resolved_frame_scale <= 0.0
        or resolved_frame_scale == float("inf")
    ):
        resolved_frame_scale = 1.0
    resolved_frame_scale = max(0.60, min(1.80, resolved_frame_scale))
    # Shared avatar/frame customization changes only the retained cell footprint,
    # never roster/provider admission. The frame term keeps widened grouped tiles
    # from overlapping by allowing CUSTOM width to trade columns for room.
    try:
        resolved_frame_baseline = float(frame_baseline_width)
    except (TypeError, ValueError):
        resolved_frame_baseline = 108.0
    if (
        resolved_frame_baseline != resolved_frame_baseline
        or resolved_frame_baseline <= 0.0
        or resolved_frame_baseline == float("inf")
    ):
        resolved_frame_baseline = 108.0
    # Identity must be the exact pre-editor authored fit.  The shared frame role
    # may trade columns for room only by its *delta* from authored width; charging
    # the full frame width again at scale 1.0 made narrow authored grids lose a
    # column before the user had customized anything.
    frame_width_from_authored = 110.0 + (
        resolved_frame_baseline * (resolved_frame_scale - 1.0)
    )
    minimum_cell_width = max(
        72.0,
        110.0 * resolved_avatar_scale,
        frame_width_from_authored,
    )
    fitted = max(
        1, int((content_width + _GRID_GAP) // (minimum_cell_width + _GRID_GAP))
    )
    column_limit = 24 if custom_horizontal_extent else normalized_capacity
    return min(column_limit, fitted)


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
    show_names: bool
    show_online_count: bool
    name_font_size: int
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
                24,
            ),
            show_names=as_bool(
                merged_card.get("show_names"),
                bool(_FRIEND_DEFAULTS["show_names"]),
            ),
            show_online_count=as_bool(
                merged_card.get("show_online_count"),
                bool(_FRIEND_DEFAULTS["show_online_count"]),
            ),
            name_font_size=bounded_int(
                merged_card.get("name_font_size"),
                int(_FRIEND_DEFAULTS["name_font_size"]),
                8,
                18,
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
            return (
                120 + grid_rows * _GRID_TILE_HEIGHT + max(0, grid_rows - 1) * _GRID_GAP
            )
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
    PinnedRole = PrimaryRole + 9

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
        primary = _title_case_friend_name(row.primary)
        return {
            self.PrimaryRole: primary,
            self.SecondaryRole: row.secondary,
            self.PresenceRole: row.presence_text,
            self.OnlineRole: row.online,
            self.ChangedRole: row.changed,
            self.AvatarSourceRole: avatar_source,
            self.CountRole: row.count,
            self.FriendActionRole: row.friend_action_available,
            self.GameActionRole: bool(row.game_appid),
            self.PinnedRole: row.pinned,
            int(Qt.ItemDataRole.DisplayRole): primary,
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
            self.PinnedRole: b"pinned",
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
                    self.PinnedRole,
                ],
            )
        if new_count > common:
            self._rows = resolved
        return True


class FriendPulsePresentationModel(QObject):
    stateChanged = Signal()
    customGeometryChanged = Signal()
    friendChangePulseRequested = Signal(int)

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
        self._visible_row_range: tuple[int, int] | None = (0, config.capacity - 1)
        self._pending_pulse_indices: tuple[int, ...] = ()
        # CUSTOM content-extent override. ``None`` means the card uses its
        # canonical config-derived authored size (normal + every non-CUSTOM
        # path). A live edit or a committed CUSTOM entry sets a logical content
        # box here so the card reflows (vertical -> more rows, horizontal ->
        # grid column reflow / less truncation) instead of uniformly scaling.
        # This is presentation-only session/layout state; it never mutates the
        # normalized ``visible_row_capacity``/``preferred_width`` settings.
        self._content_extent: tuple[int, int] | None = None
        # CUSTOM child geometry is still persisted only by the shared layout
        # session. Friend Pulse projects six descriptor-backed role records into
        # retained presentation state. Repeated roles are deliberately *grouped*:
        # every friend frame/avatar/username consumes the same record, so roster
        # size never creates per-friend settings, I/O, or provider work.
        self._custom_header_geometry: tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.0)
        self._custom_header_alignment = "left"
        self._custom_header_anchor = ""
        self._custom_online_count_geometry: tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.0)
        self._custom_online_count_alignment = "right"
        self._custom_separator_geometry: tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.0)
        self._custom_friend_frame_geometry: tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.0)
        self._custom_avatar_geometry: tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.0)
        self._custom_username_geometry: tuple[float, float, float, float] = (1.0, 1.0, 0.0, 0.0)
        descriptor = get_widget_runtime_descriptor("friend_pulse")
        if descriptor is None or not descriptor.custom_child_roles:
            raise RuntimeError("Friend Pulse CUSTOM child-role descriptor is missing")
        self._custom_child_roles = child_role_map(descriptor.custom_child_roles)

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
        visible_range = getattr(service, "update_visible_range", None)
        if callable(visible_range):
            visible_range(0, self.config.capacity - 1)
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
        previous_event_keys = {
            (row.identity_fingerprint, row.game_appid)
            for row in self._projection.rows
            if row.changed and row.identity_fingerprint and row.game_appid
        }
        previous_row_count = len(self._row_model.rows)
        self._pending_pulse_indices = ()
        # Update the retained row model first.  Its synchronous count/content
        # signals queue a viewport clamp before event admission is finalized,
        # so a stale pre-shrink range cannot queue a delayed glow.
        rows_changed = self._row_model.replace_rows(projection.rows)
        prior_observation_was_visible = (
            self._snapshot is not None
            and self._projection.state in {"ready", "stale"}
            and self._visible_row_range is not None
        )
        event_indices = tuple(
            index
            for index, row in enumerate(projection.rows)
            if prior_observation_was_visible
            and row.changed
            and row.identity_fingerprint
            and row.game_appid
            and (row.identity_fingerprint, row.game_appid) not in previous_event_keys
        )
        if len(projection.rows) != previous_row_count:
            clamped: tuple[int, int] | None = None
            if len(projection.rows) < previous_row_count:
                # Roster shrank: the Quick view can be left scrolled past its
                # content (StopAtBounds only self-corrects during a live flick),
                # so relying solely on the view's forced report can publish a
                # stale, out-of-range window to the avatar-hydration runtime and
                # drop a legitimate change pulse.  Re-clamp the runtime window
                # ourselves; the view's later async report is idempotent against
                # this clamped range.  A growing/first-populated roster keeps the
                # historical defer-to-view behaviour.
                clamped = self._clamp_visible_range_to_rows()
            if clamped is None:
                self._pending_pulse_indices = event_indices
                pulse_indices: tuple[int, ...] = ()
            else:
                first, last = clamped
                self._pending_pulse_indices = ()
                pulse_indices = tuple(
                    index for index in event_indices if first <= index <= last
                )
        else:
            visible_first, visible_last = self._visible_row_range or (0, -1)
            pulse_indices = tuple(
                index
                for index in event_indices
                if visible_first <= index <= visible_last
            )
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
        for index in pulse_indices:
            self.friendChangePulseRequested.emit(index)

    def request_manual_refresh(self) -> bool:
        return bool(
            self.is_active
            and self._interaction_enabled
            and self._runtime_service is not None
            and self._runtime_service.refresh()
        )

    def toggle_pin(self, row_index: int) -> bool:
        if (
            not self.is_active
            or not self._interaction_enabled
            or self._runtime_service is None
            or self.config.privacy_mode == "Strict"
        ):
            return False
        try:
            row = self._row_model.rows[int(row_index)]
        except (IndexError, TypeError, ValueError):
            return False
        if not row.identity_fingerprint or not row.friend_action_available:
            return False
        toggle = getattr(self._runtime_service, "toggle_pin", None)
        return bool(callable(toggle) and toggle(row.identity_fingerprint))

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

    def menu_action_target(
        self,
        action: str,
        row_index: int,
    ) -> tuple[str, str] | None:
        """Revalidate a QML row/action pair against current private owner state."""

        normalized = str(action or "").strip().lower()
        if normalized == "store":
            target = self.game_action_target(row_index)
            return ("store", target) if target is not None else None
        if normalized not in {"profile", "chat", "copy_id"}:
            return None
        target = self.friend_action_target(row_index)
        if target is None:
            return None
        return {
            "profile": ("friend_profile", target),
            "chat": ("friend_message", target),
            "copy_id": ("copy_steam_id", target),
        }[normalized]

    def _clamp_visible_range_to_rows(self) -> tuple[int, int] | None:
        """Clamp and republish the runtime visible window against the roster.

        Used when the roster count changes.  The window width follows the
        configured visible capacity (the same width used to seed the range at
        construction), anchored at its previous start but pulled fully in-bounds,
        so a shrunk roster never leaves the runtime hydrating rows that no longer
        exist.  Returns the clamped range, or ``None`` when there is nothing to
        show or no live reporter.
        """

        if not self.is_active or self._runtime_service is None:
            return None
        reporter = getattr(self._runtime_service, "update_visible_range", None)
        if not callable(reporter):
            return None
        row_count = len(self._row_model.rows)
        if row_count <= 0:
            self._visible_row_range = None
            reporter(-1, -1)
            return None
        window = max(1, int(self.config.capacity))
        previous_first = 0
        if self._visible_row_range is not None:
            previous_first = max(0, int(self._visible_row_range[0]))
        first = max(0, min(previous_first, max(0, row_count - window)))
        last = min(row_count - 1, first + window - 1)
        self._visible_row_range = (first, last)
        reporter(first, last)
        return (first, last)

    def report_visible_range(self, first_index: int, last_index: int) -> bool:
        # NOTE: This is deliberately a plain method, not a ``@Slot(..., result=bool)``.
        # It is the QML ``visibleRangeChanged(int, int)`` handler, and PySide6
        # faults (native access violation) when a QML signal is delivered to a
        # decorated slot that declares a non-void result across the QML->Python
        # boundary during ListView layout/scroll. Every other QML-signal handler
        # in this family is a plain bound method for the same reason; the direct
        # Python callers below still receive the bool return normally.
        if not self.is_active or self._runtime_service is None:
            return False
        try:
            requested_first = int(first_index)
            requested_last = int(last_index)
        except (TypeError, ValueError):
            return False
        reporter = getattr(self._runtime_service, "update_visible_range", None)
        if not callable(reporter):
            return False
        if requested_first < 0 and requested_last < 0:
            self._visible_row_range = None
            self._pending_pulse_indices = ()
            return bool(reporter(-1, -1))
        first = max(0, requested_first)
        last = min(len(self._row_model.rows) - 1, requested_last)
        if last < first:
            self._pending_pulse_indices = ()
            return False
        self._visible_row_range = (first, last)
        reported = bool(reporter(first, last))
        pending, self._pending_pulse_indices = self._pending_pulse_indices, ()
        for index in pending:
            if first <= index <= last:
                self.friendChangePulseRequested.emit(index)
        return reported

    def set_interaction_enabled(self, enabled: bool) -> bool:
        value = bool(enabled)
        if value == self._interaction_enabled:
            return False
        self._interaction_enabled = value
        self.stateChanged.emit()
        return True

    def set_content_extent(
        self,
        width: float | None,
        height: float | None,
    ) -> bool:
        """Apply a CUSTOM content-box override, or clear it when either is None.

        The box is a logical (pre-uniform-scale) content size. Width follows the
        canonical authored-width bounds; height is floored at one row's worth of
        card so the ListView/Grid always has real content room. Returns True when
        the effective override changed.
        """

        if width is None or height is None:
            return self.clear_content_extent()
        try:
            resolved_width = int(round(float(width)))
            resolved_height = int(round(float(height)))
        except (TypeError, ValueError):
            return False
        resolved_width = max(420, min(4000, resolved_width))
        resolved_height = max(120, min(4000, resolved_height))
        extent = (resolved_width, resolved_height)
        if extent == self._content_extent:
            return False
        self._content_extent = extent
        self.stateChanged.emit()
        self.customGeometryChanged.emit()
        return True

    def clear_content_extent(self) -> bool:
        """Drop any CUSTOM content-box override and return to the authored size."""

        if self._content_extent is None:
            return False
        self._content_extent = None
        self.stateChanged.emit()
        self.customGeometryChanged.emit()
        return True

    def set_custom_child_geometry(self, child_geometry: object) -> bool:
        """Project grouped Friend Pulse CUSTOM child geometry.

        The shared CUSTOM owner remains the only gesture/persistence authority.
        Repeated roster primitives intentionally consume one role record each;
        this method therefore stays O(role-count), independent of friend count,
        and emits one narrow geometry signal for an applied payload.
        """

        raw = child_geometry if isinstance(child_geometry, Mapping) else {}

        def _resolved(role_id: str) -> CustomChildSize:
            role = self._custom_child_roles[role_id]
            value = raw.get(role_id) if isinstance(raw, Mapping) else None
            if not isinstance(value, Mapping):
                return CustomChildSize()
            return clamp_child_geometry(
                role,
                value.get("width_scale", 1.0),
                value.get("height_scale", 1.0),
                value.get("x_offset", 0.0),
                value.get("y_offset", 0.0),
                value.get("alignment"),
                value.get("anchor"),
            )

        header = _resolved("header")
        online_count = _resolved("online_count")
        separator = _resolved("separator")
        friend_frames = _resolved("friend_frames")
        avatars = _resolved("avatars")
        usernames = _resolved("usernames")
        next_values = (
            (header.width_scale, header.height_scale, header.x_offset, header.y_offset),
            header.alignment or self._custom_child_roles["header"].authored_alignment,
            str(header.anchor or ""),
            (online_count.width_scale, online_count.height_scale, online_count.x_offset, online_count.y_offset),
            online_count.alignment or self._custom_child_roles["online_count"].authored_alignment,
            (separator.width_scale, separator.height_scale, separator.x_offset, separator.y_offset),
            (friend_frames.width_scale, friend_frames.height_scale, friend_frames.x_offset, friend_frames.y_offset),
            (avatars.width_scale, avatars.height_scale, avatars.x_offset, avatars.y_offset),
            (usernames.width_scale, usernames.height_scale, usernames.x_offset, usernames.y_offset),
        )
        current_values = (
            self._custom_header_geometry,
            self._custom_header_alignment,
            self._custom_header_anchor,
            self._custom_online_count_geometry,
            self._custom_online_count_alignment,
            self._custom_separator_geometry,
            self._custom_friend_frame_geometry,
            self._custom_avatar_geometry,
            self._custom_username_geometry,
        )
        if next_values == current_values:
            return False
        (
            self._custom_header_geometry,
            self._custom_header_alignment,
            self._custom_header_anchor,
            self._custom_online_count_geometry,
            self._custom_online_count_alignment,
            self._custom_separator_geometry,
            self._custom_friend_frame_geometry,
            self._custom_avatar_geometry,
            self._custom_username_geometry,
        ) = next_values
        self.customGeometryChanged.emit()
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
        self._pending_pulse_indices = ()
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
    def onlineFriendsText(self) -> str:
        if (
            not self.config.show_online_count
            or self._snapshot is None
            or self._projection.state not in {"ready", "stale"}
        ):
            return ""
        count = max(0, int(self._snapshot.online_count or 0))
        noun = "FRIEND" if count == 1 else "FRIENDS"
        return f"{count} {noun} ONLINE"

    @Property(bool, constant=True)
    def showOnlineCount(self) -> bool:
        return self.config.show_online_count

    @Property(bool, notify=stateChanged)
    def interactionEnabled(self) -> bool:
        return self._interaction_enabled

    @Property(str, constant=True)
    def headerText(self) -> str:
        return "Friend Pulse"

    @Property(str, constant=True)
    def viewMode(self) -> str:
        return self.config.view_mode

    @Property(int, notify=customGeometryChanged)
    def gridColumns(self) -> int:
        # A horizontal content-extent override reflows the avatar grid. The
        # authored baseline still respects ``visible_row_capacity``; once the
        # user explicitly widens the CUSTOM content box, width owns how many
        # readable columns can fit (up to the project-wide 24-friend ceiling).
        custom_extent = self._content_extent is not None
        width = (
            self._content_extent[0]
            if custom_extent
            else self.config.authored_width
        )
        base_columns = _grid_columns_for(
            self.config.capacity,
            self.config.authored_width,
            custom_horizontal_extent=False,
            avatar_scale=1.0,
            frame_width_scale=1.0,
        )
        base_tile_width = max(
            72.0,
            (max(420, self.config.authored_width) - 36.0) / max(1, base_columns)
                - 12.0,
        )
        return _grid_columns_for(
            self.config.capacity,
            width,
            custom_horizontal_extent=custom_extent,
            avatar_scale=float(self._custom_avatar_geometry[0]),
            frame_width_scale=float(self._custom_friend_frame_geometry[0]),
            frame_baseline_width=base_tile_width,
        )

    @Property(int, constant=True)
    def baseGridColumns(self) -> int:
        return _grid_columns_for(
            self.config.capacity,
            self.config.authored_width,
            custom_horizontal_extent=False,
            avatar_scale=1.0,
            frame_width_scale=1.0,
        )

    @Property(float, notify=customGeometryChanged)
    def customAvatarScale(self) -> float:
        return float(self._custom_avatar_geometry[0])

    @Property(float, notify=customGeometryChanged)
    def customAvatarXOffset(self) -> float:
        return float(self._custom_avatar_geometry[2])

    @Property(float, notify=customGeometryChanged)
    def customAvatarYOffset(self) -> float:
        return float(self._custom_avatar_geometry[3])

    @Property(float, notify=customGeometryChanged)
    def customFriendFrameWidthScale(self) -> float:
        return float(self._custom_friend_frame_geometry[0])

    @Property(float, notify=customGeometryChanged)
    def customFriendFrameHeightScale(self) -> float:
        return float(self._custom_friend_frame_geometry[1])

    @Property(float, notify=customGeometryChanged)
    def customUsernameWidthScale(self) -> float:
        return float(self._custom_username_geometry[0])

    @Property(float, notify=customGeometryChanged)
    def customUsernameHeightScale(self) -> float:
        return float(self._custom_username_geometry[1])

    @Property(float, notify=customGeometryChanged)
    def customUsernameXOffset(self) -> float:
        return float(self._custom_username_geometry[2])

    @Property(float, notify=customGeometryChanged)
    def customUsernameYOffset(self) -> float:
        return float(self._custom_username_geometry[3])

    @Property(float, notify=customGeometryChanged)
    def customHeaderWidthScale(self) -> float:
        return float(self._custom_header_geometry[0])

    @Property(float, notify=customGeometryChanged)
    def customHeaderHeightScale(self) -> float:
        return float(self._custom_header_geometry[1])

    @Property(float, notify=customGeometryChanged)
    def customHeaderXOffset(self) -> float:
        return float(self._custom_header_geometry[2])

    @Property(float, notify=customGeometryChanged)
    def customHeaderYOffset(self) -> float:
        return float(self._custom_header_geometry[3])

    @Property(str, notify=customGeometryChanged)
    def customHeaderAlignment(self) -> str:
        return self._custom_header_alignment

    @Property(str, notify=customGeometryChanged)
    def customHeaderAnchor(self) -> str:
        return self._custom_header_anchor

    @Property(float, notify=customGeometryChanged)
    def customOnlineCountWidthScale(self) -> float:
        return float(self._custom_online_count_geometry[0])

    @Property(float, notify=customGeometryChanged)
    def customOnlineCountHeightScale(self) -> float:
        return float(self._custom_online_count_geometry[1])

    @Property(float, notify=customGeometryChanged)
    def customOnlineCountXOffset(self) -> float:
        return float(self._custom_online_count_geometry[2])

    @Property(float, notify=customGeometryChanged)
    def customOnlineCountYOffset(self) -> float:
        return float(self._custom_online_count_geometry[3])

    @Property(str, notify=customGeometryChanged)
    def customOnlineCountAlignment(self) -> str:
        return self._custom_online_count_alignment

    @Property(float, notify=customGeometryChanged)
    def customSeparatorWidthScale(self) -> float:
        return float(self._custom_separator_geometry[0])

    @Property(float, notify=customGeometryChanged)
    def customSeparatorHeightScale(self) -> float:
        return float(self._custom_separator_geometry[1])

    @Property(float, notify=customGeometryChanged)
    def customSeparatorXOffset(self) -> float:
        return float(self._custom_separator_geometry[2])

    @Property(float, notify=customGeometryChanged)
    def customSeparatorYOffset(self) -> float:
        return float(self._custom_separator_geometry[3])

    @Property(int, constant=True)
    def visibleCapacity(self) -> int:
        return self.config.capacity

    @Property(bool, constant=True)
    def showNames(self) -> bool:
        # Strict rows are aggregate labels rather than personal identities.
        return self.config.privacy_mode == "Strict" or self.config.show_names

    @Property(float, constant=True)
    def nameFontSize(self) -> float:
        return float(self.config.name_font_size)

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

    @Property(float, constant=True)
    def baseAuthoredWidth(self) -> float:
        return float(self.config.authored_width)

    @Property(float, constant=True)
    def baseAuthoredHeight(self) -> float:
        return float(self.config.authored_height)

    @Property(float, notify=stateChanged)
    def authoredWidth(self) -> float:
        if self._content_extent is not None:
            return float(self._content_extent[0])
        return float(self.config.authored_width)

    @Property(float, notify=stateChanged)
    def authoredHeight(self) -> float:
        if self._content_extent is not None:
            return float(self._content_extent[1])
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
        self._retained.set_custom_layout_size_payload_handler(
            self._apply_custom_layout_size_payload
        )
        host.set_widget_input_state_handler(self._retained, self.apply_input_state)
        refresh = getattr(self._retained.item, "refreshRequested", None)
        if refresh is not None and hasattr(refresh, "connect"):
            refresh.connect(model.request_manual_refresh)
        self._connect("friendActionRequested", self._handle_friend_action)
        self._connect("gameActionRequested", self._handle_game_action)
        self._connect("friendPinToggleRequested", model.toggle_pin)
        self._connect("friendMenuActionRequested", self._handle_menu_action)
        self._connect("actionMenuPointerGesture", self._arm_action_menu_pointer_guard)
        self._connect(
            "visibleRangeChanged",
            model.report_visible_range,
            connection_type=Qt.ConnectionType.QueuedConnection,
        )

    def _connect(
        self,
        signal_name: str,
        callback: Callable[..., Any],
        *,
        connection_type: Qt.ConnectionType | None = None,
    ) -> None:
        signal = getattr(self._retained.item, signal_name, None)
        if signal is not None and hasattr(signal, "connect"):
            if connection_type is None:
                signal.connect(callback)
            else:
                signal.connect(callback, connection_type)

    def _handle_friend_action(self, row_index: int) -> bool:
        from rendering.runtime_input import runtime_pointer_input_is_suppressed

        if runtime_pointer_input_is_suppressed("friendPulseFriendActionRequested"):
            return False
        target = self._model.friend_action_target(row_index)
        if target is None or self._on_steam_action_requested is None:
            return False
        return bool(self._on_steam_action_requested("friend_message", target))

    def _handle_game_action(self, row_index: int) -> bool:
        from rendering.runtime_input import runtime_pointer_input_is_suppressed

        if runtime_pointer_input_is_suppressed("friendPulseGameActionRequested"):
            return False
        target = self._model.game_action_target(row_index)
        if target is None or self._on_steam_action_requested is None:
            return False
        return bool(self._on_steam_action_requested("store", target))

    def _handle_menu_action(self, action: str, row_index: int) -> bool:
        resolved = self._model.menu_action_target(action, row_index)
        if resolved is None or self._on_steam_action_requested is None:
            return False
        kind, target = resolved
        return bool(self._on_steam_action_requested(kind, target))

    @staticmethod
    def _arm_action_menu_pointer_guard() -> None:
        from rendering.runtime_input import suppress_runtime_pointer_input

        suppress_runtime_pointer_input(700, reason="friend_pulse_action_menu")

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

    def _apply_custom_layout_size_payload(
        self,
        payload: Mapping[str, Any],
    ) -> None:
        """Consume the CUSTOM content-box override from the layout payload.

        ``content_extent`` owns the outer logical reflow while the shared
        ``child_geometry`` payload may project the one grouped avatar-size role.
        Their absence clears prior overrides so normal/non-CUSTOM presentation
        returns to authored truth. Legacy per-value keys stay ignored (H9). The
        handler runs for live edits and committed CUSTOM replay/slot restore.
        """

        extent = payload.get("content_extent") if isinstance(payload, Mapping) else None
        if isinstance(extent, (tuple, list)) and len(extent) == 2:
            self._model.set_content_extent(extent[0], extent[1])
        else:
            self._model.clear_content_extent()

        child_geometry = payload.get("child_geometry") if isinstance(payload, Mapping) else None
        self._model.set_custom_child_geometry(child_geometry)

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
