"""Focused F6 gates for retained Gmail presentation state."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest
from PySide6.QtGui import QColor

from core.gmail.gmail_client import EmailMetadata
from rendering.quick.widgets.gmail import (
    GmailPresentationConfig,
    GmailPresentationModel,
    GmailPresentationStyle,
)
from widgets.gmail_runtime import GmailRuntimeSnapshot


def _config(**overrides) -> GmailPresentationConfig:
    values = {
        "limit": 4,
        "font_family": "Inter",
        "font_size": 13,
        "group_threads": True,
        "show_sender": True,
        "show_subject": True,
        "show_timestamp": True,
        "clean_sender_names": True,
        "auto_title_case": True,
        "max_sender_words": 3,
        "max_subject_words": 4,
        "date_display_mode": "numeric",
    }
    values.update(overrides)
    return GmailPresentationConfig.from_mapping(values)


def _style(config: GmailPresentationConfig) -> GmailPresentationStyle:
    return GmailPresentationStyle.project(
        config,
        {
            "enabled": True,
            "direction": "NW",
            "color": [0, 0, 0, 255],
            "blur_radius": 18,
            "frame_opacity": 0.7,
            "frame_extra_offset": 1,
            "text_enabled": True,
            "text_opacity": 0.4,
            "text_extra_offset": 2,
        },
    )


def _email(
    identity: str,
    *,
    thread_id: str | None = None,
    sender: str = '"Example Sender" <sender@example.com>',
    subject: str = "a retained gmail subject line",
    unread: bool = True,
    provider: str = "gmail_api",
    imap_uid: str | None = None,
    minute: int = 0,
) -> EmailMetadata:
    return EmailMetadata(
        id=identity,
        thread_id=thread_id or f"thread-{identity}",
        sender=sender,
        subject=subject,
        date=datetime(2026, 8, 25, 12, minute, tzinfo=timezone.utc),
        labels=("INBOX", "UNREAD") if unread else ("INBOX",),
        is_unread=unread,
        provider=provider,
        imap_uid=imap_uid,
    )


def _snapshot(revision: int, emails, *, error=None, refreshing=False, unread=1):
    return GmailRuntimeSnapshot(
        revision=revision,
        emails=tuple(emails),
        unread_count=unread,
        error=error,
        refreshing=refreshing,
        source="test",
    )


class _Service:
    def __init__(self, *, start_result: bool = True) -> None:
        self.consumer = None
        self.started = 0
        self.stopped = 0
        self.detached = 0
        self.refreshes = 0
        self.auth_requests = 0
        self.opens = []
        self.actions = []
        self.thread_manager = None
        self.start_result = start_result

    def attach_consumer(self, consumer) -> None:
        self.consumer = consumer

    def set_thread_manager(self, manager) -> None:
        self.thread_manager = manager

    def start(self) -> bool:
        self.started += 1
        return self.start_result

    def stop(self) -> None:
        self.stopped += 1

    def detach_consumer(self, consumer) -> None:
        assert consumer is self.consumer
        self.consumer = None
        self.detached += 1

    def refresh(self) -> bool:
        self.refreshes += 1
        return True

    def start_auth_flow(self) -> bool:
        self.auth_requests += 1
        return True

    def is_imap_backend(self) -> bool:
        return False

    def open_message_in_browser(self, message_id: str) -> bool:
        self.opens.append(message_id)
        return True

    def dispatch_action(self, action: str, message_id: str) -> bool:
        self.actions.append((action, message_id))
        return True


def test_gmail_config_projects_current_bounded_presentation_contract() -> None:
    config = GmailPresentationConfig.from_mapping(
        {
            "limit": 999,
            "font_size": 2,
            "sender_subject_ratio": 95,
            "show_envelope_icon": "true",
            "show_background": "false",
            "date_display_mode": "words",
        }
    )

    assert config.limit == 25
    assert config.font_size == 8
    assert config.sender_subject_ratio == 90
    assert config.show_envelope_icon is True
    assert config.show_background is False
    assert config.date_display_mode == "words"


def test_gmail_style_uses_canonical_card_and_text_shadow_direction() -> None:
    style = _style(_config())

    assert style.card_style.shadow_enabled is True
    assert style.card_style.shadow_offset_x < 0
    assert style.card_style.shadow_offset_y < 0
    assert style.text_shadow_offset_x < 0
    assert style.text_shadow_offset_y < 0
    assert isinstance(style.text_shadow_color, QColor)


def test_gmail_model_groups_rows_and_keeps_stable_thread_identity() -> None:
    model = GmailPresentationModel(_config(), _style(_config()))
    row_model = model.row_model
    model.activate()
    older = _email("one", thread_id="thread-stable", minute=1)
    newer = _email("two", thread_id="thread-stable", minute=2)

    model.on_gmail_runtime_snapshot(_snapshot(1, (newer, older), unread=2))

    assert model.row_model is row_model
    assert row_model.rowCount() == 1
    assert row_model.rows[0].identity == "thread-stable"
    assert row_model.rows[0].count == 2
    assert row_model.rows[0].sender == "Example Sender"
    assert row_model.rows[0].subject == "A Retained Gmail Subject..."
    assert model.unreadCount == 2
    assert model.viewState == "ready"


def test_gmail_model_rejects_stale_snapshot_and_mutates_rows_in_place() -> None:
    config = _config(group_threads=False)
    model = GmailPresentationModel(config, _style(config))
    row_model = model.row_model
    model.activate()
    model.on_gmail_runtime_snapshot(_snapshot(2, (_email("fresh"),)))
    model.on_gmail_runtime_snapshot(_snapshot(1, (_email("stale"),)))

    assert model.row_model is row_model
    assert row_model.rows[0].message_id == "fresh"

    assert model.apply_config(replace(config, font_size=18)) is True
    assert model.row_model is row_model
    assert model.config.font_size == 18


def test_gmail_grouping_setting_reprojects_accepted_snapshot_in_place() -> None:
    config = _config(group_threads=True)
    model = GmailPresentationModel(config, _style(config))
    row_model = model.row_model
    model.activate()
    emails = (
        _email("new", thread_id="thread-stable", minute=2),
        _email("old", thread_id="thread-stable", minute=1),
    )
    model.on_gmail_runtime_snapshot(_snapshot(1, emails, unread=2))
    assert row_model.rowCount() == 1

    assert model.apply_config(replace(config, group_threads=False)) is True

    assert model.row_model is row_model
    assert row_model.rowCount() == 2
    assert [row.message_id for row in row_model.rows] == ["new", "old"]
    assert [row.identity for row in row_model.rows] == ["new", "old"]


def test_gmail_error_replaces_cached_rows_and_refreshing_empty_stays_loading() -> None:
    config = _config()
    model = GmailPresentationModel(config, _style(config))
    model.activate()
    model.on_gmail_runtime_snapshot(_snapshot(1, (), refreshing=True, unread=0))
    assert model.viewState == "loading"

    model.on_gmail_runtime_snapshot(_snapshot(2, (_email("cached"),), unread=1))
    assert model.viewState == "ready"
    assert model.row_model.rowCount() == 1

    model.on_gmail_runtime_snapshot(
        _snapshot(3, (_email("cached"),), error="auth", unread=1)
    )
    assert model.viewState == "error"
    assert model.errorText == "auth"
    assert model.row_model.rowCount() == 0


def test_gmail_failed_runtime_start_detaches_and_fails_closed() -> None:
    service = _Service(start_result=False)
    config = _config()
    model = GmailPresentationModel(config, _style(config), runtime_service=service)

    with pytest.raises(RuntimeError, match="failed to start"):
        model.activate(thread_manager="tm")

    assert model.is_active is False
    assert service.detached == 1
    assert model.request_refresh() is False


def test_gmail_semantic_actions_require_active_interaction_and_owned_row() -> None:
    service = _Service()
    config = _config(group_threads=False)
    model = GmailPresentationModel(config, _style(config), runtime_service=service)
    assert service.consumer is None
    assert model.activate(thread_manager="tm") is True
    model.on_gmail_runtime_snapshot(
        _snapshot(
            1,
            (
                _email("oauth"),
                _email("imap", provider="imap", imap_uid="uid-9"),
            ),
        )
    )

    assert model.request_open("oauth") is False
    assert model.request_refresh() is False
    assert model.set_interaction_enabled(True) is True
    assert model.request_open("missing") is False
    assert model.request_open("oauth") is True
    assert model.request_action("trash", "oauth") is True
    assert model.request_action("archive", "uid-9") is False
    assert model.request_action("spam", "uid-9") is True
    assert model.request_action("unknown", "oauth") is False
    assert model.request_refresh() is True
    assert model.request_auth() is True

    assert service.opens == ["oauth"]
    assert service.actions == [("trash", "oauth"), ("spam", "uid-9")]
    assert service.refreshes == 1
    assert service.auth_requests == 1
    assert service.thread_manager == "tm"

    model.retire()
    assert service.stopped == 1
    assert service.detached == 1
    assert model.row_model.rowCount() == 0
    assert model.request_open("oauth") is False
