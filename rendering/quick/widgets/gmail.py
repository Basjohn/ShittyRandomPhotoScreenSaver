"""Stable retained Gmail presentation state and semantic action admission."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from typing import Any

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Property, Qt, Signal
from PySide6.QtGui import QColor

from core.settings.shadow_direction import resolve_signed_offset
from core.settings.widget_capacity_policy import LIST_WIDGET_MAX_CAPACITY
from widgets.gmail_components import (
    clean_sender_name,
    format_email_date,
    group_emails,
    shorten_subject,
    smart_title_case_subject,
)
from widgets.gmail_runtime import GmailRuntimeSnapshot

from .host import (
    ORDINARY_CARD_SHADOW_BASE,
    ORDINARY_TEXT_SHADOW_BASE,
    OverlayCardStyle,
)


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
    limit: int = 10
    font_family: str = "Inter"
    font_size: int = 12
    text_color: tuple[int, int, int, int] = (255, 255, 255, 230)
    show_background: bool = True
    background_color: tuple[int, int, int, int] = (35, 35, 35, 255)
    background_opacity: float = 0.3
    border_color: tuple[int, int, int, int] = (255, 255, 255, 255)
    border_opacity: float = 1.0
    group_threads: bool = True
    show_sender: bool = True
    show_subject: bool = True
    show_envelope_icon: bool = False
    show_three_dot_menu: bool = True
    show_refresh_spiral: bool = True
    show_timestamp: bool = True
    show_unread_count_in_header: bool = True
    show_separators: bool = True
    auto_title_case: bool = True
    clean_sender_names: bool = True
    max_sender_words: int = 3
    max_subject_words: int = 4
    sender_subject_ratio: int = 35
    date_display_mode: str = "numeric"
    header_logo_px_adjust: int = 2

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "GmailPresentationConfig":
        return cls(
            limit=_bounded_int(values.get("limit"), 10, 1, LIST_WIDGET_MAX_CAPACITY),
            font_family=str(values.get("font_family", "Inter") or "Inter"),
            font_size=_bounded_int(values.get("font_size"), 12, 8, 96),
            text_color=_rgba(values.get("color"), (255, 255, 255, 230)),
            show_background=_as_bool(values.get("show_background"), True),
            background_color=_rgba(values.get("bg_color"), (35, 35, 35, 255)),
            background_opacity=_bounded_float(values.get("bg_opacity"), 0.3, 0.0, 1.0),
            border_color=_rgba(values.get("border_color"), (255, 255, 255, 255)),
            border_opacity=_bounded_float(values.get("border_opacity"), 1.0, 0.0, 1.0),
            group_threads=_as_bool(values.get("group_threads"), True),
            show_sender=_as_bool(values.get("show_sender"), True),
            show_subject=_as_bool(values.get("show_subject"), True),
            show_envelope_icon=_as_bool(values.get("show_envelope_icon"), False),
            show_three_dot_menu=_as_bool(values.get("show_three_dot_menu"), True),
            show_refresh_spiral=_as_bool(values.get("show_refresh_spiral"), True),
            show_timestamp=_as_bool(values.get("show_timestamp"), True),
            show_unread_count_in_header=_as_bool(values.get("show_unread_count_in_header"), True),
            show_separators=_as_bool(values.get("show_separators"), True),
            auto_title_case=_as_bool(values.get("auto_title_case"), True),
            clean_sender_names=_as_bool(values.get("clean_sender_names"), True),
            max_sender_words=_bounded_int(values.get("max_sender_words"), 3, 0, 20),
            max_subject_words=_bounded_int(values.get("max_subject_words"), 4, 0, 30),
            sender_subject_ratio=_bounded_int(values.get("sender_subject_ratio"), 35, 10, 90),
            date_display_mode=str(values.get("date_display_mode", "numeric") or "numeric"),
            header_logo_px_adjust=_bounded_int(values.get("header_logo_px_adjust"), 2, -128, 128),
        )

    @classmethod
    def from_widgets_mapping(cls, widgets: Mapping[str, object]) -> "GmailPresentationConfig":
        from core.settings.defaults import get_default_settings

        defaults = get_default_settings().get("widgets", {}).get("gmail", {})
        current = widgets.get("gmail", {}) if isinstance(widgets, Mapping) else {}
        merged = dict(defaults) if isinstance(defaults, Mapping) else {}
        if isinstance(current, Mapping):
            merged.update(current)
        return cls.from_mapping(merged)


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
        frame_extra = _bounded_float(shadow_values.get("frame_extra_offset"), 0.0, 0.0, 40.0)
        text_extra = _bounded_float(shadow_values.get("text_extra_offset"), 0.0, 0.0, 40.0)
        direction = shadow_values.get("direction", "SE")
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
                background_color=_with_alpha(config.background_color, config.background_opacity),
                border_color=_with_alpha(config.border_color, config.border_opacity),
                border_width=max(0.0, float(border_width)),
                corner_radius=8.0,
                padding=14.0,
                shadow_enabled=config.show_background and _as_bool(shadow_values.get("enabled"), True),
                shadow_color=_with_alpha(
                    shadow_rgba,
                    _bounded_float(shadow_values.get("frame_opacity"), 0.77, 0.0, 1.0),
                ),
                shadow_blur=_bounded_float(shadow_values.get("blur_radius"), 18.0, 0.0, 80.0),
                shadow_offset_x=card_offset[0],
                shadow_offset_y=card_offset[1],
            ),
            text_shadow_enabled=_as_bool(shadow_values.get("text_enabled"), True),
            text_shadow_color=_with_alpha(
                shadow_rgba,
                _bounded_float(shadow_values.get("text_opacity"), 0.33, 0.0, 1.0),
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


class GmailRowListModel(QAbstractListModel):
    IdentityRole = int(Qt.ItemDataRole.UserRole) + 1
    MessageIdRole = IdentityRole + 1
    SenderRole = IdentityRole + 2
    SubjectRole = IdentityRole + 3
    TimestampRole = IdentityRole + 4
    UnreadRole = IdentityRole + 5
    CountRole = IdentityRole + 6
    ArchiveSupportedRole = IdentityRole + 7

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


class GmailPresentationModel(QObject):
    stateChanged = Signal()

    _ACTIONS = frozenset({"mark_read", "mark_unread", "archive", "spam", "trash"})

    def __init__(
        self,
        config: GmailPresentationConfig,
        style: GmailPresentationStyle,
        *,
        runtime_service: Any | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._row_model = GmailRowListModel(self)
        self._runtime_service = runtime_service
        self._snapshot = GmailPresentationSnapshot(config=config, style=style)
        self._last_runtime_snapshot: GmailRuntimeSnapshot | None = None
        self._runtime_attached = False
        self._active = False
        self._retired = False

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
        candidates = list(snapshot.emails[: config.limit])
        if snapshot.error is not None:
            display_rows = ()
        elif config.group_threads:
            display_rows = group_emails(candidates)[: config.limit]
        else:
            display_rows = candidates
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
                )
            )
        self._row_model.replace_rows(rows)
        if snapshot.error:
            state = "error"
        elif rows:
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
        self._row_model.replace_rows(())

    @Property(QObject, constant=True)
    def rows(self) -> QObject:
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


__all__ = [
    "GmailPresentationConfig",
    "GmailPresentationModel",
    "GmailPresentationRow",
    "GmailPresentationSnapshot",
    "GmailPresentationStyle",
    "GmailRowListModel",
]
