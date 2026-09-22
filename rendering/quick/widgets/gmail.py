"""Stable retained Gmail presentation state and semantic action admission."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
import math
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import (
    QAbstractListModel,
    QModelIndex,
    QObject,
    Property,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QColor

from core.settings.default_contract import require_canonical_default
from core.settings.shadow_direction import (
    resolve_directional_extensions,
    resolve_signed_offset,
)
from rendering.quick.shadow_snapshot import QuickShadowSnapshot
from rendering.custom_child_geometry import CustomChildSize, child_role_map, clamp_child_geometry
from rendering.quick.column_rails import normalize_column_rails
from rendering.widget_descriptors import get_widget_runtime_descriptor
from core.settings.widget_capacity_policy import LIST_WIDGET_MAX_CAPACITY
from rendering.quick.widgets.theme_projection import (
    configured_rgba_override,
    resolve_card_surface_colors,
    resolve_header_colors,
    resolve_primary_text_color,
    resolve_rgba_role,
)
from widgets.gmail_components import (
    clean_sender_name,
    format_email_date,
    group_emails,
    shorten_subject,
    smart_title_case_subject,
)

if TYPE_CHECKING:
    from widgets.gmail_runtime import GmailRuntimeSnapshot

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OrdinaryWidgetPresentationHost,
    OverlayCardStyle,
    OverlayWidgetGeometry,
    RetainedOverlayWidget,
)


_GMAIL_LOGO = Path(__file__).resolve().parents[3] / "images" / "google-gmail.png"
_GMAIL_UNREAD_ENVELOPE = Path(__file__).resolve().parents[3] / "images" / "gmail-envelope.png"
_GMAIL_READ_ENVELOPE = Path(__file__).resolve().parents[3] / "images" / "gmail-read.png"
_GMAIL_ACTION_ICONS = {
    "mark_read": _GMAIL_READ_ENVELOPE,
    "mark_unread": _GMAIL_UNREAD_ENVELOPE,
    "archive": Path(__file__).resolve().parents[3] / "images" / "gmail-archive.svg",
    "spam": Path(__file__).resolve().parents[3] / "images" / "gmail-spam.png",
    "trash": Path(__file__).resolve().parents[3] / "images" / "gmail-trash.png",
}


def _bounded_int(value: object, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(low, min(high, parsed))


def _bounded_float(value: object, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
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
    color.setAlpha(max(0, min(255, round(color.alpha() * scale))))
    return color


@dataclass(frozen=True)
class GmailPresentationConfig:
    limit: int
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
    group_threads: bool
    show_sender: bool
    show_subject: bool
    show_envelope_icon: bool
    show_three_dot_menu: bool
    show_refresh_spiral: bool
    show_timestamp: bool
    show_unread_count_in_header: bool
    show_separators: bool
    show_header_border: bool
    desaturate_when_no_unread: bool
    separator_color: tuple[int, int, int, int]
    separator_thickness: int
    boundary_separator_color: tuple[int, int, int, int]
    boundary_separator_thickness: int
    action_popup_surface_color: tuple[int, int, int, int]
    action_popup_border_color: tuple[int, int, int, int]
    action_popup_hover_color: tuple[int, int, int, int]
    action_popup_text_color: tuple[int, int, int, int]
    auto_title_case: bool
    clean_sender_names: bool
    max_sender_words: int
    max_subject_words: int
    sender_subject_ratio: int
    date_display_mode: str
    width: int

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "GmailPresentationConfig":
        """Normalize Gmail state with canonical defaults as the repair baseline."""

        defaults = require_canonical_default("widgets.gmail")
        if not isinstance(defaults, Mapping):
            raise TypeError("Canonical widgets.gmail default must be a mapping")
        merged = dict(defaults)
        if isinstance(values, Mapping):
            merged.update(values)
        return cls(
            limit=_bounded_int(merged["limit"], int(defaults["limit"]), 1, LIST_WIDGET_MAX_CAPACITY),
            font_family=str(merged["font_family"] or defaults["font_family"]),
            font_size=_bounded_int(merged["font_size"], int(defaults["font_size"]), 8, 96),
            text_color=_rgba(merged["color"], tuple(defaults["color"])),
            show_background=_as_bool(merged["show_background"], bool(defaults["show_background"])),
            background_color=_rgba(merged["bg_color"], tuple(defaults["bg_color"])),
            background_opacity=_bounded_float(merged["bg_opacity"], float(defaults["bg_opacity"]), 0.0, 1.0),
            border_color=_rgba(merged["border_color"], tuple(defaults["border_color"])),
            border_opacity=_bounded_float(merged["border_opacity"], float(defaults["border_opacity"]), 0.0, 1.0),
            header_fill_color=_rgba(merged["header_fill_color"], tuple(defaults["header_fill_color"])),
            header_border_color=_rgba(merged["header_border_color"], tuple(defaults["header_border_color"])),
            header_text_color=_rgba(merged["header_text_color"], tuple(defaults["header_text_color"])),
            group_threads=_as_bool(merged["group_threads"], bool(defaults["group_threads"])),
            show_sender=_as_bool(merged["show_sender"], bool(defaults["show_sender"])),
            show_subject=_as_bool(merged["show_subject"], bool(defaults["show_subject"])),
            show_envelope_icon=_as_bool(merged["show_envelope_icon"], bool(defaults["show_envelope_icon"])),
            show_three_dot_menu=_as_bool(merged["show_three_dot_menu"], bool(defaults["show_three_dot_menu"])),
            show_refresh_spiral=_as_bool(merged["show_refresh_spiral"], bool(defaults["show_refresh_spiral"])),
            show_timestamp=_as_bool(merged["show_timestamp"], bool(defaults["show_timestamp"])),
            show_unread_count_in_header=_as_bool(merged["show_unread_count_in_header"], bool(defaults["show_unread_count_in_header"])),
            show_separators=_as_bool(merged["show_separators"], bool(defaults["show_separators"])),
            show_header_border=_as_bool(merged["show_header_border"], bool(defaults["show_header_border"])),
            desaturate_when_no_unread=_as_bool(merged["desaturate_when_no_unread"], bool(defaults["desaturate_when_no_unread"])),
            separator_color=_rgba(merged["separator_color"], tuple(defaults["separator_color"])),
            separator_thickness=_bounded_int(merged["separator_thickness"], int(defaults["separator_thickness"]), 0, 12),
            boundary_separator_color=_rgba(
                merged["boundary_separator_color"], tuple(defaults["boundary_separator_color"])
            ),
            boundary_separator_thickness=_bounded_int(
                merged["boundary_separator_thickness"], int(defaults["boundary_separator_thickness"]), 0, 12
            ),
            auto_title_case=_as_bool(merged["auto_title_case"], bool(defaults["auto_title_case"])),
            clean_sender_names=_as_bool(merged["clean_sender_names"], bool(defaults["clean_sender_names"])),
            max_sender_words=_bounded_int(merged["max_sender_words"], int(defaults["max_sender_words"]), 0, 20),
            max_subject_words=_bounded_int(merged["max_subject_words"], int(defaults["max_subject_words"]), 0, 30),
            sender_subject_ratio=_bounded_int(merged["sender_subject_ratio"], int(defaults["sender_subject_ratio"]), 10, 90),
            date_display_mode=str(merged["date_display_mode"] or defaults["date_display_mode"]),
            width=_bounded_int(merged["width"], int(defaults["width"]), 200, 1200),
            # Semantic-only action palette seeds inherit widget-local roles.
            # ``from_widgets_mapping`` resolves them through the active Widget Theme.
            action_popup_surface_color=_rgba(merged["bg_color"], tuple(defaults["bg_color"])),
            action_popup_border_color=_rgba(merged["border_color"], tuple(defaults["border_color"])),
            action_popup_hover_color=_rgba(merged["bg_color"], tuple(defaults["bg_color"])),
            action_popup_text_color=_rgba(merged["color"], tuple(defaults["color"])),
        )

    @classmethod
    def from_widgets_mapping(cls, widgets: Mapping[str, object]) -> "GmailPresentationConfig":
        defaults = require_canonical_default("widgets.gmail")
        if not isinstance(defaults, Mapping):
            raise TypeError("Canonical widgets.gmail default must be a mapping")
        current = widgets.get("gmail", {}) if isinstance(widgets, Mapping) else {}
        merged = dict(defaults)
        if not isinstance(current, Mapping):
            current = {}
        else:
            merged.update(current)
        config = cls.from_mapping(merged)
        header_fill, header_border, header_text = resolve_header_colors(
            "gmail",
            values=current,
            defaults=defaults,
            fill=config.header_fill_color,
            border=config.header_border_color,
            text=config.header_text_color,
        )
        separator_override = configured_rgba_override(
            current, defaults,
            "separator_color", config.separator_color,
        )
        boundary_override = configured_rgba_override(
            current, defaults,
            "boundary_separator_color", config.boundary_separator_color,
        )
        separator_local = {
            "local.separator": config.separator_color,
            "local.border": config.border_color,
            "local.text": config.text_color,
        }
        card_background, card_border = resolve_card_surface_colors(
            values=current,
            defaults=defaults,
            background_color=config.background_color,
            background_opacity=config.background_opacity,
            border_color=config.border_color,
            border_opacity=config.border_opacity,
        )
        text_color = resolve_primary_text_color(
            values=current,
            defaults=defaults,
            text_color=config.text_color,
        )
        separator_local["local.text"] = text_color
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
            separator_color=resolve_rgba_role(
                "gmail.separator", local_roles=separator_local,
                fallback=config.separator_color, explicit=separator_override,
            ),
            boundary_separator_color=resolve_rgba_role(
                "gmail.boundary_separator",
                local_roles={**separator_local, "local.separator": config.boundary_separator_color},
                fallback=config.boundary_separator_color, explicit=boundary_override,
            ),
            action_popup_surface_color=resolve_rgba_role(
                "gmail.action.surface",
                local_roles={"local.surface": config.action_popup_surface_color},
                fallback=config.action_popup_surface_color,
            ),
            action_popup_border_color=resolve_rgba_role(
                "gmail.action.border",
                local_roles={"local.border": config.action_popup_border_color},
                fallback=config.action_popup_border_color,
            ),
            action_popup_hover_color=resolve_rgba_role(
                "gmail.action.hover",
                local_roles={"local.surface.alt": config.action_popup_hover_color},
                fallback=config.action_popup_hover_color,
            ),
            action_popup_text_color=resolve_rgba_role(
                "gmail.action.text",
                local_roles={"local.text": config.action_popup_text_color},
                fallback=config.action_popup_text_color,
            ),
        )


@dataclass(frozen=True)
class GmailPresentationStyle:
    card_style: OverlayCardStyle
    text_shadow_enabled: bool
    text_shadow_color: QColor
    text_shadow_offset_x: float
    text_shadow_offset_y: float

    @classmethod
    def project(
        cls,
        config: GmailPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> "GmailPresentationStyle":
        shadow = QuickShadowSnapshot.from_mapping(shadow_values)
        card_offset = resolve_signed_offset(shadow.direction, *ORDINARY_CARD_SHADOW_BASE)
        card_extensions = resolve_directional_extensions(
            shadow.direction, shadow.frame_extra_offset
        )
        text_offset = resolve_signed_offset(
            shadow.direction,
            ORDINARY_TEXT_SHADOW_BASE[0] + shadow.text_extra_offset,
            ORDINARY_TEXT_SHADOW_BASE[1] + shadow.text_extra_offset,
        )
        shadow_rgba = shadow.color
        return cls(
            card_style=OverlayCardStyle(
                shell_enabled=config.show_background,
                background_color=_with_alpha(config.background_color, config.background_opacity),
                border_color=_with_alpha(config.border_color, config.border_opacity),
                border_width=max(0.0, float(border_width)),
                corner_radius=8.0,
                padding=14.0,
                shadow_enabled=config.show_background and shadow.enabled,
                shadow_color=_with_alpha(
                    shadow_rgba,
                    shadow.frame_opacity,
                ),
                shadow_blur=min(80.0, shadow.blur_radius),
                shadow_offset_x=card_offset[0],
                shadow_offset_y=card_offset[1],
                shadow_extend_left=card_extensions[0],
                shadow_extend_top=card_extensions[1],
                shadow_extend_right=card_extensions[2],
                shadow_extend_bottom=card_extensions[3],
            ),
            text_shadow_enabled=shadow.text_enabled,
            text_shadow_color=_with_alpha(
                shadow_rgba,
                shadow.text_opacity,
            ),
            text_shadow_offset_x=text_offset[0],
            text_shadow_offset_y=text_offset[1],
        )


@dataclass(frozen=True)
class GmailPresentationRow:
    identity: str
    message_id: str
    sender: str
    subject: str
    timestamp: str
    unread: bool
    count: int
    archive_supported: bool
    boundary_before: bool


class GmailRowListModel(QAbstractListModel):
    IdentityRole = int(Qt.ItemDataRole.UserRole) + 1
    MessageIdRole = IdentityRole + 1
    SenderRole = IdentityRole + 2
    SubjectRole = IdentityRole + 3
    TimestampRole = IdentityRole + 4
    UnreadRole = IdentityRole + 5
    CountRole = IdentityRole + 6
    ArchiveSupportedRole = IdentityRole + 7
    BoundaryBeforeRole = IdentityRole + 8

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: tuple[GmailPresentationRow, ...] = ()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = int(Qt.ItemDataRole.DisplayRole)):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        return {
            self.IdentityRole: row.identity,
            self.MessageIdRole: row.message_id,
            self.SenderRole: row.sender,
            self.SubjectRole: row.subject,
            self.TimestampRole: row.timestamp,
            self.UnreadRole: row.unread,
            self.CountRole: row.count,
            self.ArchiveSupportedRole: row.archive_supported,
            self.BoundaryBeforeRole: row.boundary_before,
            int(Qt.ItemDataRole.DisplayRole): row.subject,
        }.get(int(role))

    def roleNames(self) -> dict[int, bytes]:  # noqa: N802
        return {
            self.IdentityRole: b"messageIdentity",
            self.MessageIdRole: b"messageId",
            self.SenderRole: b"messageSender",
            self.SubjectRole: b"messageSubject",
            self.TimestampRole: b"messageTimestamp",
            self.UnreadRole: b"messageUnread",
            self.CountRole: b"messageCount",
            self.ArchiveSupportedRole: b"archiveSupported",
            self.BoundaryBeforeRole: b"boundaryBefore",
        }

    @property
    def rows(self) -> tuple[GmailPresentationRow, ...]:
        return self._rows

    def replace_rows(self, rows: Iterable[GmailPresentationRow]) -> bool:
        resolved = tuple(rows)
        if resolved == self._rows:
            return False
        old_count = len(self._rows)
        new_count = len(resolved)
        common = min(old_count, new_count)
        previous = self._rows
        if new_count < old_count:
            self.beginRemoveRows(QModelIndex(), new_count, old_count - 1)
            self._rows = previous[:new_count]
            self.endRemoveRows()
        elif new_count > old_count:
            self.beginInsertRows(QModelIndex(), old_count, new_count - 1)
            self._rows = (*previous, *resolved[old_count:])
            self.endInsertRows()
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
                list(self.roleNames()),
            )
        if new_count > common:
            self._rows = resolved
        return True


@dataclass(frozen=True)
class GmailPresentationSnapshot:
    config: GmailPresentationConfig
    style: GmailPresentationStyle
    runtime_revision: int = 0
    view_state: str = "loading"
    error_text: str = ""
    unread_count: int = 0
    refreshing: bool = False
    interaction_enabled: bool = False


# The model retains a buffer up to the list-widget capacity cap so a CUSTOM
# vertical content-extent can reveal more than the authored ``limit`` (the SSOT
# default visible count) without a re-fetch. ``limit`` still governs the default
# shown count; this is only a data buffer, never a second count authority.
_MAX_HELD_EMAILS = LIST_WIDGET_MAX_CAPACITY


class GmailPresentationModel(QObject):
    stateChanged = Signal()
    customGeometryChanged = Signal()
    columnOrderChanged = Signal()  # Discrete rail reorder, independent of child/parent geometry.

    _ACTIONS = frozenset({"mark_read", "mark_unread", "archive", "spam", "trash"})

    def __init__(
        self,
        config: GmailPresentationConfig,
        style: GmailPresentationStyle,
        *,
        runtime_service: Any | None = None,
        runtime_generation: int | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._runtime_generation = runtime_generation
        self._row_model = GmailRowListModel(self)
        # Keep the accepted source window in Python.  The QML Repeater must not
        # instantiate every buffered row merely so CUSTOM can reveal it later.
        # ``_refresh_materialized_rows`` projects only the rows the current
        # authored/CUSTOM geometry can plausibly display.
        self._held_rows: tuple[GmailPresentationRow, ...] = ()
        self._runtime_service = runtime_service
        self._snapshot = GmailPresentationSnapshot(config=config, style=style)
        self._last_runtime_snapshot: GmailRuntimeSnapshot | None = None
        self._runtime_attached = False
        self._active = False
        self._retired = False
        # CUSTOM content-extent override (logical content box, pre-uniform-scale).
        # None on every non-CUSTOM path -> authored size + ``limit`` govern.
        self._content_extent: tuple[int, int] | None = None
        descriptor = get_widget_runtime_descriptor("gmail")
        if descriptor is None:
            raise RuntimeError("Missing runtime descriptor for 'gmail'")
        self._custom_child_roles = child_role_map(descriptor.custom_child_roles)
        self._custom_column_order: tuple[str, ...] | None = None
        self._custom_child_geometry: dict[str, CustomChildSize] = {
            role_id: CustomChildSize() for role_id in self._custom_child_roles
        }

    @property
    def config(self) -> GmailPresentationConfig:
        return self._snapshot.config

    @property
    def style(self) -> GmailPresentationStyle:
        return self._snapshot.style

    @property
    def row_model(self) -> GmailRowListModel:
        return self._row_model

    @property
    def is_active(self) -> bool:
        return self._active and not self._retired

    def is_gmail_consumer_alive(self) -> bool:
        return self.is_active

    def set_runtime_service(self, service: Any) -> None:
        if self._retired or self._active:
            raise RuntimeError("cannot replace Gmail runtime after activation")
        if self._runtime_service is service:
            return
        if self._runtime_service is not None:
            raise RuntimeError("Gmail presentation already has a runtime service")
        self._runtime_service = service

    def activate(self, thread_manager: Any | None = None) -> bool:
        if self._retired:
            raise RuntimeError("cannot activate a retired Gmail model")
        if self._active:
            return True
        service = self._runtime_service
        if service is not None:
            if thread_manager is None:
                raise RuntimeError("Gmail runtime activation requires ThreadManager")
            service.set_thread_manager(thread_manager)
            service.attach_consumer(self)
            self._runtime_attached = True
        self._active = True
        if service is not None and not service.start():
            self._active = False
            service.detach_consumer(self)
            self._runtime_attached = False
            self._runtime_service = None
            raise RuntimeError("Gmail runtime service failed to start")
        return True

    def apply_config(self, config: GmailPresentationConfig) -> bool:
        if self._retired or config == self.config:
            return False
        self._snapshot = replace(self._snapshot, config=config)
        if self._last_runtime_snapshot is not None:
            self._project_runtime_snapshot(self._last_runtime_snapshot)
        else:
            self.stateChanged.emit()
        return True

    def apply_style(self, style: GmailPresentationStyle) -> bool:
        if self._retired or style == self.style:
            return False
        self._snapshot = replace(self._snapshot, style=style)
        self.stateChanged.emit()
        return True

    def on_gmail_runtime_snapshot(self, snapshot: GmailRuntimeSnapshot) -> None:
        if not self.is_active or snapshot.revision <= self._snapshot.runtime_revision:
            return
        self._last_runtime_snapshot = snapshot
        self._project_runtime_snapshot(snapshot)

    def _project_runtime_snapshot(self, snapshot: GmailRuntimeSnapshot) -> None:
        config = self.config
        if snapshot.error is not None:
            display_rows = ()
        elif config.group_threads:
            # ``limit`` is a visible-row contract, not a pre-group source-message
            # budget. Group the accepted shared inbox window first, then cap the
            # resulting rows so a six-message conversation does not silently turn
            # a requested 10-row widget into only five visible entries.
            display_rows = group_emails(list(snapshot.emails))[:_MAX_HELD_EMAILS]
        else:
            display_rows = list(snapshot.emails[:_MAX_HELD_EMAILS])
        rows = []
        for item in display_rows:
            email = item.email if hasattr(item, "email") else item
            count = int(getattr(item, "count", 1))
            message_id = email.imap_uid if email.provider in {"gmail", "imap"} and email.imap_uid else email.id
            rows.append(
                GmailPresentationRow(
                    identity=str(email.thread_id or email.id) if config.group_threads else str(email.id),
                    message_id=str(message_id),
                    sender=clean_sender_name(
                        email.sender,
                        enabled=config.clean_sender_names,
                        max_words=config.max_sender_words,
                    ) if config.show_sender else "",
                    subject=shorten_subject(
                        smart_title_case_subject(email.subject)
                        if config.auto_title_case
                        else email.subject,
                        max_words=config.max_subject_words,
                    ) if config.show_subject else "",
                    timestamp=format_email_date(email.date, config.date_display_mode) if config.show_timestamp else "",
                    unread=bool(email.is_unread),
                    count=count,
                    archive_supported=(
                        email.provider != "imap"
                        and not bool(
                            self._runtime_service is not None
                            and self._runtime_service.is_imap_backend()
                        )
                    ),
                    boundary_before=bool(
                        rows and rows[-1].unread != bool(email.is_unread)
                    ),
                )
            )
        self._held_rows = tuple(rows)
        self._refresh_materialized_rows()
        if snapshot.error:
            state = "error"
        elif self._held_rows:
            state = "ready"
        elif snapshot.refreshing:
            state = "loading"
        else:
            state = "empty"
        self._snapshot = replace(
            self._snapshot,
            runtime_revision=snapshot.revision,
            view_state=state,
            error_text=str(snapshot.error or ""),
            unread_count=max(0, int(snapshot.unread_count)),
            refreshing=bool(snapshot.refreshing),
        )
        self.stateChanged.emit()

    def request_refresh(self) -> bool:
        return bool(
            self.is_active
            and self._snapshot.interaction_enabled
            and self._runtime_service is not None
            and self._runtime_service.refresh()
        )

    def request_auth(self) -> bool:
        return bool(
            self.is_active
            and self._snapshot.interaction_enabled
            and self._runtime_service is not None
            and self._runtime_service.start_auth_flow()
        )

    def request_open(self, message_id: str) -> bool:
        # Refuse a browser-open that belongs to a just-dismissed context-menu
        # gesture. A retained-menu item tap is also recognised by this row's
        # TapHandler (non-exclusive Qt Quick passive grabs), so without this the
        # same click both selects the menu item and opens Gmail. The shared
        # pointer guard is armed at the menu-action boundary; this mirrors the
        # check the Reddit open path already performs.
        from rendering.runtime_input import runtime_pointer_input_is_suppressed

        if runtime_pointer_input_is_suppressed("gmailOpenMessageRequested"):
            return False
        if not self.is_active or not self._snapshot.interaction_enabled or self._runtime_service is None:
            return False
        if not any(row.message_id == message_id for row in self._row_model.rows):
            return False
        return bool(self._runtime_service.open_message_in_browser(str(message_id)))

    def request_action(self, action: str, message_id: str) -> bool:
        if not self.is_active or not self._snapshot.interaction_enabled or self._runtime_service is None:
            return False
        normalized = str(action)
        row = next((item for item in self._row_model.rows if item.message_id == message_id), None)
        if row is None or normalized not in self._ACTIONS:
            return False
        if normalized == "archive" and not row.archive_supported:
            return False
        return bool(self._runtime_service.dispatch_action(normalized, str(message_id)))

    def set_interaction_enabled(self, enabled: bool) -> bool:
        normalized = bool(enabled)
        if normalized == self._snapshot.interaction_enabled:
            return False
        self._snapshot = replace(self._snapshot, interaction_enabled=normalized)
        self.stateChanged.emit()
        return True

    def set_content_extent(
        self,
        width: float | None,
        height: float | None,
    ) -> bool:
        """Apply a CUSTOM content-box override, or clear it when either is None.

        Presentation/layout-only: the box overrides the effective visible count
        and row spread while in CUSTOM. The ``limit`` setting remains the SSOT
        default; this never writes settings.
        """

        if width is None or height is None:
            return self.clear_content_extent()
        try:
            resolved_width = int(round(float(width)))
            resolved_height = int(round(float(height)))
        except (TypeError, ValueError):
            return False
        resolved_width = max(300, min(2000, resolved_width))
        resolved_height = max(80, min(4000, resolved_height))
        extent = (resolved_width, resolved_height)
        if extent == self._content_extent:
            return False
        self._content_extent = extent
        self._refresh_materialized_rows()
        self.stateChanged.emit()
        return True

    def clear_content_extent(self) -> bool:
        if self._content_extent is None:
            return False
        self._content_extent = None
        self._refresh_materialized_rows()
        self.stateChanged.emit()
        return True

    def _refresh_materialized_rows(self) -> bool:
        """Project the Python buffer into the retained QML delegate model.

        Non-CUSTOM runtime materializes exactly the authored visible limit.
        CUSTOM may need more rows as the card grows vertically.  The estimate
        intentionally ignores header/chrome height, so it can over-materialize
        a small number of rows but can never under-materialize rows that QML's
        stricter rail-budget calculation could reveal.
        """

        held_count = len(self._held_rows)
        if held_count <= 0:
            return self._row_model.replace_rows(())
        materialized = min(held_count, max(1, int(self.config.limit)))
        if self._content_extent is not None:
            natural_row_height = max(28.0, float(self.config.font_size) * 1.65)
            # No repeated child geometry: authored row height is the sole density baseline.
            conservative_row_height = natural_row_height
            conservative_fit = max(
                1,
                int(
                    math.ceil(
                        float(self._content_extent[1])
                        / max(1.0, conservative_row_height + 4.0)
                    )
                ),
            )
            materialized = min(
                held_count,
                max(materialized, conservative_fit),
            )
        return self._row_model.replace_rows(self._held_rows[:materialized])


    def set_custom_child_geometry(self, child_geometry: object) -> bool:
        """Project shared Gmail child-role geometry without touching mail runtime state."""

        raw = child_geometry if isinstance(child_geometry, Mapping) else {}
        resolved: dict[str, CustomChildSize] = {}
        for role_id, role in self._custom_child_roles.items():
            value = raw.get(role_id) if isinstance(raw, Mapping) else None
            if not isinstance(value, Mapping):
                resolved[role_id] = CustomChildSize()
                continue
            resolved[role_id] = clamp_child_geometry(
                role,
                value.get("width_scale", 1.0),
                value.get("height_scale", 1.0),
                value.get("x_offset", 0.0),
                value.get("y_offset", 0.0),
                value.get("alignment"),
                value.get("anchor"),
            )
        if resolved == self._custom_child_geometry:
            return False
        self._custom_child_geometry = resolved
        self.customGeometryChanged.emit()
        return True

    def set_custom_column_order(self, order: object) -> bool:
        normalized = normalize_column_rails("gmail", order)
        if self._custom_column_order == normalized:
            return False
        self._custom_column_order = normalized
        self.columnOrderChanged.emit()
        return True

    @Property("QVariantList", notify=columnOrderChanged)
    def customColumnOrder(self) -> list[str]:
        return list(self._custom_column_order or ())

    @Property("QVariantMap", notify=customGeometryChanged)
    def customChildGeometry(self) -> dict[str, dict[str, object]]:
        return {
            role_id: geometry.to_mapping()
            for role_id, geometry in self._custom_child_geometry.items()
            if not geometry.is_authored
        }

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
        self._last_runtime_snapshot = None
        self._held_rows = ()
        self._row_model.replace_rows(())

    @Property(QObject, constant=True)
    def rowModel(self) -> QObject:
        return self._row_model

    @Property(str, notify=stateChanged)
    def viewState(self) -> str:
        return self._snapshot.view_state

    @Property(str, notify=stateChanged)
    def errorText(self) -> str:
        return self._snapshot.error_text

    @Property(int, notify=stateChanged)
    def unreadCount(self) -> int:
        return self._snapshot.unread_count

    @Property(bool, notify=stateChanged)
    def refreshing(self) -> bool:
        return self._snapshot.refreshing

    @Property(bool, notify=stateChanged)
    def interactionEnabled(self) -> bool:
        return self._snapshot.interaction_enabled

    @Property(str, notify=stateChanged)
    def headerText(self) -> str:
        if self.config.show_unread_count_in_header and self._snapshot.unread_count > 0:
            return f"Gmail ( {self._snapshot.unread_count} )"
        return "Gmail"

    @Property(str, constant=True)
    def logoSource(self) -> str:
        return _GMAIL_LOGO.resolve().as_uri() if _GMAIL_LOGO.is_file() else ""

    @Property(str, constant=True)
    def unreadEnvelopeSource(self) -> str:
        return (
            _GMAIL_UNREAD_ENVELOPE.resolve().as_uri()
            if _GMAIL_UNREAD_ENVELOPE.is_file()
            else ""
        )

    @Property(str, constant=True)
    def readEnvelopeSource(self) -> str:
        return (
            _GMAIL_READ_ENVELOPE.resolve().as_uri()
            if _GMAIL_READ_ENVELOPE.is_file()
            else ""
        )

    @Property(str, notify=stateChanged)
    def fontFamily(self) -> str:
        return self.config.font_family

    @Property(float, notify=stateChanged)
    def fontSize(self) -> float:
        return float(self.config.font_size)

    @Property(float, notify=stateChanged)
    def timestampFontSize(self) -> float:
        return float(max(8, self.config.font_size - 5))

    @Property(QColor, notify=stateChanged)
    def textColor(self) -> QColor:
        return QColor(*self.config.text_color)

    @Property(QColor, notify=stateChanged)
    def senderColor(self) -> QColor:
        fallback = (200, 200, 200, 255)
        return QColor(*resolve_rgba_role(
            "gmail.sender", local_roles={"local.muted": fallback}, fallback=fallback
        ))

    @Property(QColor, notify=stateChanged)
    def readSenderColor(self) -> QColor:
        fallback = (180, 180, 180, 220)
        return QColor(*resolve_rgba_role(
            "gmail.read_sender", local_roles={"local.muted": fallback}, fallback=fallback
        ))

    @Property(QColor, notify=stateChanged)
    def readSubjectColor(self) -> QColor:
        fallback = (220, 220, 220, 230)
        return QColor(*resolve_rgba_role(
            "gmail.read_subject", local_roles={"local.muted": fallback}, fallback=fallback
        ))

    @Property(QColor, notify=stateChanged)
    def timestampColor(self) -> QColor:
        fallback = (180, 180, 180, 200)
        return QColor(*resolve_rgba_role(
            "gmail.timestamp", local_roles={"local.muted": fallback}, fallback=fallback
        ))

    @Property(QColor, notify=stateChanged)
    def separatorColor(self) -> QColor:
        return QColor(*self.config.separator_color)

    @Property(QColor, notify=stateChanged)
    def boundarySeparatorColor(self) -> QColor:
        return QColor(*self.config.boundary_separator_color)

    @Property(QColor, notify=stateChanged)
    def actionPopupSurfaceColor(self) -> QColor:
        return QColor(*self.config.action_popup_surface_color)

    @Property(QColor, notify=stateChanged)
    def actionPopupBorderColor(self) -> QColor:
        return QColor(*self.config.action_popup_border_color)

    @Property(QColor, notify=stateChanged)
    def actionPopupHoverColor(self) -> QColor:
        return QColor(*self.config.action_popup_hover_color)

    @Property(QColor, notify=stateChanged)
    def actionPopupTextColor(self) -> QColor:
        return QColor(*self.config.action_popup_text_color)

    @Property(bool, notify=stateChanged)
    def showSender(self) -> bool:
        return self.config.show_sender

    @Property(bool, notify=stateChanged)
    def showSubject(self) -> bool:
        return self.config.show_subject

    @Property(bool, notify=stateChanged)
    def showEnvelopeIcon(self) -> bool:
        return self.config.show_envelope_icon

    @Property(bool, notify=stateChanged)
    def showThreeDotMenu(self) -> bool:
        return self.config.show_three_dot_menu

    @Property(bool, notify=stateChanged)
    def showRefreshSpiral(self) -> bool:
        return self.config.show_refresh_spiral

    @Property(bool, notify=stateChanged)
    def showSeparators(self) -> bool:
        return self.config.show_separators

    @Property(bool, notify=stateChanged)
    def showHeaderBorder(self) -> bool:
        return self.config.show_header_border

    @Property(bool, notify=stateChanged)
    def desaturateLogo(self) -> bool:
        return self.config.desaturate_when_no_unread and self._snapshot.unread_count == 0

    @Property(int, notify=stateChanged)
    def separatorThickness(self) -> int:
        return self.config.separator_thickness

    @Property(int, notify=stateChanged)
    def boundarySeparatorThickness(self) -> int:
        return self.config.boundary_separator_thickness

    @Property(float, notify=stateChanged)
    def senderSubjectRatio(self) -> float:
        return float(self.config.sender_subject_ratio) / 100.0

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

    @Property(float, notify=stateChanged)
    def contentWidth(self) -> float:
        return float(self.config.width)

    @Property(int, notify=stateChanged)
    def emailLimit(self) -> int:
        # SSOT default visible count (non-CUSTOM). CUSTOM content-extent overrides
        # the *effective* count in QML but never rewrites this setting.
        return int(self.config.limit)

    @Property(int, constant=True)
    def maxHeldEmails(self) -> int:
        return int(_MAX_HELD_EMAILS)

    @Property(float, notify=stateChanged)
    def contentExtentWidth(self) -> float:
        return float(self._content_extent[0]) if self._content_extent else 0.0

    @Property(float, notify=stateChanged)
    def contentExtentHeight(self) -> float:
        return float(self._content_extent[1]) if self._content_extent else 0.0

    @Property(float, notify=stateChanged)
    def contentHeight(self) -> float:
        """Authored row capacity, never a measurement of current mail availability.

        The Settings ``limit`` reserves the same natural height during loading,
        empty, cached, and live states. The previous live-row/boundary count
        changed the *parent* preferred height as messages arrived; entering
        CUSTOM before the first refresh could then freeze a 110px reference,
        making Reset collapse an otherwise full-height Gmail card. Actual row
        population remains a presentation-only choice inside this fixed space.
        """
        slots = max(1, int(self.config.limit))
        row_height = max(28.0, self.fontSize * 1.65)
        # Boundaries are data-dependent. Reserve their maximum authored budget
        # once, instead of letting incoming message grouping resize the card.
        boundary_budget = (
            max(0, slots - 1) * float(self.config.boundary_separator_thickness)
            if self.config.show_separators else 0.0
        )
        return 36.0 + row_height * slots + 4.0 * slots + boundary_budget

    @Slot(str, result=str)
    def actionIconSource(self, action: str) -> str:
        path = _GMAIL_ACTION_ICONS.get(str(action))
        return path.resolve().as_uri() if path is not None and path.is_file() else ""

    @Slot(str, result=bool)
    def ownsMessage(self, message_id: str) -> bool:
        return any(row.message_id == str(message_id) for row in self._row_model.rows)


class RetainedGmailPresentation:
    """One retained Gmail item with semantic action routing."""

    def __init__(
        self,
        *,
        host: OrdinaryWidgetPresentationHost,
        model: GmailPresentationModel,
        geometry: OverlayWidgetGeometry,
        fade_opacity: float = 1.0,
        on_open_inbox_requested: Callable[[], Any] | None = None,
        on_browser_opened: Callable[[], Any] | None = None,
        on_auth_requested: Callable[[], Any] | None = None,
    ) -> None:
        self._model = model
        self._on_open_inbox_requested = on_open_inbox_requested
        self._on_browser_opened = on_browser_opened
        self._on_auth_requested = on_auth_requested
        self._retained: RetainedOverlayWidget = host.create_family_widget(
            "gmail",
            initial_properties={"gmailModel": model},
            object_name="gmail",
            model_identity="gmail",
            geometry=geometry,
            fade_opacity=fade_opacity,
            card_style=model.style.card_style,
        )
        self._retained.add_retirement_callback(model.retire)
        self._retained.set_custom_layout_size_payload_handler(
            self._apply_custom_layout_size_payload
        )
        host.set_widget_input_state_handler(self._retained, self.apply_input_state)
        self._connect("openInboxRequested", self._handle_open_inbox_requested)
        self._connect("openMessageRequested", self._handle_open_message_requested)
        self._connect("refreshRequested", model.request_refresh)
        self._connect("authRequested", self._handle_auth_requested)
        self._connect("actionMenuPointerGesture", self._arm_action_menu_pointer_guard)
        self._connect("actionRequested", model.request_action)

    def _connect(self, signal_name: str, callback: Callable[..., Any]) -> None:
        signal = getattr(self._retained.item, signal_name, None)
        if signal is not None and hasattr(signal, "connect"):
            signal.connect(callback)

    @property
    def item(self):
        return self._retained.item

    @property
    def model(self) -> GmailPresentationModel:
        return self._model

    def activate(self, thread_manager: Any | None = None) -> bool:
        return self._model.activate(thread_manager)

    def set_geometry(self, geometry: OverlayWidgetGeometry) -> None:
        self._retained.set_geometry(geometry)

    def _apply_custom_layout_size_payload(
        self,
        payload: Mapping[str, object],
    ) -> None:
        # Stale pre-migration ``font_size`` payloads stay ignored. The one key
        # honoured is ``content_extent`` (the CUSTOM-scoped side-resize box):
        # vertical drives the effective visible count + row/separator spread,
        # horizontal widens the card (less width-elide). Its absence clears any
        # override so the card returns to its ``limit``/authored size. Runs for
        # both live edit and committed replay, so a saved extent restores on load
        # + slot.
        extent = payload.get("content_extent") if isinstance(payload, Mapping) else None
        if isinstance(extent, (tuple, list)) and len(extent) == 2:
            self._model.set_content_extent(extent[0], extent[1])
        else:
            self._model.clear_content_extent()
        child_geometry = payload.get("child_geometry") if isinstance(payload, Mapping) else None
        self._model.set_custom_child_geometry(child_geometry)
        order = payload.get("column_rails") if isinstance(payload, Mapping) else None
        self._model.set_custom_column_order(order)

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

    def apply_config(
        self,
        config: GmailPresentationConfig,
        shadow_values: Mapping[str, object],
        *,
        border_width: float = 4.0,
    ) -> None:
        self._model.apply_config(config)
        style = GmailPresentationStyle.project(
            config, shadow_values, border_width=border_width
        )
        self._model.apply_style(style)
        self._retained.set_card_style(style.card_style)

    @staticmethod
    def _arm_action_menu_pointer_guard() -> None:
        """Suppress same-gesture click-through from Gmail's retained action popup."""

        from rendering.runtime_input import suppress_runtime_pointer_input

        # Match the retained context-menu action boundary. This is only a
        # monotonic deadline flag consumed by existing open guards; it owns no
        # timer, polling loop, pointer-motion cadence, or presentation lifetime.
        suppress_runtime_pointer_input(700, reason="gmail_action_menu")

    def _handle_open_inbox_requested(self) -> bool:
        # Same context-menu click-through guard as request_open: the inbox/header
        # tap target can sit under a dismissed menu item too.
        from rendering.runtime_input import runtime_pointer_input_is_suppressed

        if runtime_pointer_input_is_suppressed("gmailOpenInboxRequested"):
            return False
        if (
            not self._model.is_active
            or not self._model.interactionEnabled
            or self._on_open_inbox_requested is None
        ):
            return False
        return bool(self._on_open_inbox_requested())

    def _handle_open_message_requested(self, message_id: str) -> bool:
        opened = bool(self._model.request_open(str(message_id)))
        if opened and self._on_browser_opened is not None:
            self._on_browser_opened()
        return opened

    def _handle_auth_requested(self) -> bool:
        # Production routes authorization to interactive Settings so the OAuth
        # browser is never born on the saver/Winlogon desktop. Admission remains
        # identical to every other retained Gmail action: a synthetic/stale QML
        # signal cannot open Settings before runtime input has been admitted.
        if not self._model.is_active or not self._model.interactionEnabled:
            return False
        if self._on_auth_requested is not None:
            return bool(self._on_auth_requested())
        return bool(self._model.request_auth())

    def retire(self) -> bool:
        return self._retained.retire()


__all__ = [
    "GmailPresentationConfig",
    "GmailPresentationModel",
    "GmailPresentationRow",
    "GmailPresentationSnapshot",
    "GmailPresentationStyle",
    "GmailRowListModel",
    "RetainedGmailPresentation",
]
