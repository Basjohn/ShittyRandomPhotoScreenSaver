"""Focused F6 gates for retained Gmail presentation state."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QColor
from PySide6.QtQml import QQmlComponent, QQmlEngine
from PySide6.QtQuick import QQuickItem

from core.gmail.gmail_client import EmailMetadata
from rendering.quick.widgets.gmail import (
    GmailPresentationConfig,
    GmailPresentationModel,
    GmailPresentationStyle,
    RetainedGmailPresentation,
)
from rendering.quick.widgets.host import (
    OrdinaryWidgetPresentationHost,
    OverlayWidgetGeometry,
)
from rendering.quick.scene_controller import QuickSceneFactory
from widgets.gmail_runtime import GmailRuntimeSnapshot


ROOT = Path(__file__).resolve().parents[1]
QML_ROOT = ROOT / "rendering" / "quick" / "qml"


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


def _style_values(**overrides):
    values = {
        "enabled": True,
        "direction": "NW",
        "color": [0, 0, 0, 255],
        "blur_radius": 18,
        "frame_opacity": 0.7,
        "frame_extra_offset": 1,
        "text_enabled": True,
        "text_opacity": 0.4,
        "text_extra_offset": 2,
    }
    values.update(overrides)
    return values


def _style(config: GmailPresentationConfig) -> GmailPresentationStyle:
    return GmailPresentationStyle.project(config, _style_values())


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


def _find_visual_item(root: QQuickItem, object_name: str) -> QQuickItem | None:
    if root.objectName() == object_name:
        return root
    for child in root.childItems():
        found = _find_visual_item(child, object_name)
        if found is not None:
            return found
    return None


def _create_qml_item(model: GmailPresentationModel):
    engine = QQmlEngine()
    engine.addImportPath(str(QML_ROOT))
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "GmailPresentation.qml"))
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]
    item = component.createWithInitialProperties({"gmailModel": model})
    assert isinstance(item, QQuickItem), [error.toString() for error in component.errors()]
    item.setWidth(620.0)
    item.setHeight(360.0)
    return engine, component, item


def _create_retained_host(factory: QuickSceneFactory, owner: QObject):
    context, root = factory.create_display_root(
        owner=owner, screen_index=0, runtime_generation=71
    )
    host_item = root.findChild(QQuickItem, "ordinaryWidgetHost")
    assert host_item is not None
    engine = QQmlEngine.contextForObject(root).engine()
    component = QQmlComponent(
        engine, QUrl.fromLocalFile(str(QML_ROOT / "GmailPresentation.qml"))
    )
    assert component.status() == QQmlComponent.Status.Ready, [
        error.toString() for error in component.errors()
    ]

    def create_gmail(family_id, properties, item_context):
        assert family_id == "gmail"
        item = component.createWithInitialProperties(dict(properties), item_context)
        assert isinstance(item, QQuickItem), [
            error.toString() for error in component.errors()
        ]
        return item

    host = OrdinaryWidgetPresentationHost(
        host_item=host_item,
        context=context,
        create_overlay_item=factory.create_overlay_widget,
        create_family_item=create_gmail,
    )
    return context, root, host, component


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


@pytest.mark.qt
def test_gmail_qml_keeps_popup_and_dynamic_height_out_of_row_identity(qt_app) -> None:
    config = _config(
        group_threads=False,
        show_envelope_icon=True,
        desaturate_when_no_unread=True,
    )
    model = GmailPresentationModel(config, _style(config))
    model.activate()
    model.on_gmail_runtime_snapshot(_snapshot(1, (_email("one"),), unread=0))
    engine, component, item = _create_qml_item(model)
    try:
        qt_app.processEvents()
        row_model = model.row_model
        first_row = _find_visual_item(item, "gmailMessageRow_0")
        popup = _find_visual_item(item, "gmailActionPopup")
        header = _find_visual_item(item, "gmailHeaderFrame")
        logo_effect = _find_visual_item(item, "gmailHeaderLogoEffect")
        assert first_row is not None
        assert popup is not None
        assert header is not None
        assert logo_effect is not None
        assert popup.isVisible() is False
        assert logo_effect.property("saturation") == pytest.approx(-1.0)
        assert header.property("resolvedBorderColor") == model.headerBorderColor
        assert header.property("resolvedBorderWidth") == pytest.approx(
            model.headerBorderWidth
        )
        one_row_height = float(item.property("committedContentHeight"))

        item.setProperty("activeActionIdentity", "one")
        item.setProperty("activeActionMessageId", "one")
        item.setProperty("activeActionUnread", True)
        item.setProperty("activeActionArchiveSupported", True)
        qt_app.processEvents()
        assert popup.isVisible() is True
        assert float(item.property("committedContentHeight")) == pytest.approx(
            one_row_height
        )
        assert _find_visual_item(item, "gmailActionIcon_mark_read") is not None
        assert _find_visual_item(item, "gmailActionIcon_archive") is not None
        assert _find_visual_item(item, "gmailActionIcon_spam") is not None
        assert _find_visual_item(item, "gmailActionIcon_trash") is not None
        assert model.actionIconSource("mark_read").endswith("gmail-read.png")
        assert model.actionIconSource("mark_unread").endswith("gmail-envelope.png")
        assert model.actionIconSource("archive").endswith("gmail-archive.svg")
        assert model.actionIconSource("spam").endswith("gmail-spam.png")
        assert model.actionIconSource("trash").endswith("gmail-trash.png")

        model.on_gmail_runtime_snapshot(
            _snapshot(2, (_email("one"), _email("two", minute=2)), unread=1)
        )
        qt_app.processEvents()
        assert model.row_model is row_model
        assert _find_visual_item(item, "gmailMessageRow_0") is first_row
        assert float(item.property("committedContentHeight")) > one_row_height
        assert QQmlEngine.contextForObject(item).engine() is engine

        model.on_gmail_runtime_snapshot(_snapshot(3, (_email("two"),), unread=0))
        qt_app.processEvents()
        assert popup.isVisible() is False
    finally:
        item.setParentItem(None)
        item.setParent(None)
        item.deleteLater()
        component.deleteLater()
        engine.deleteLater()
        qt_app.processEvents()


def test_gmail_qml_is_presentation_only_and_keeps_popup_height_independent() -> None:
    qml = (QML_ROOT / "GmailPresentation.qml").read_text(encoding="utf-8")
    for marker in (
        "Timer {",
        "SettingsManager",
        "GmailRuntimeService",
        "GmailBackend",
        "QDesktopServices",
        "QWidget",
        "http://",
        "https://",
    ):
        assert marker not in qml
    assert "onDoubleTapped: gmailRoot.refreshRequested()" in qml
    assert "committedContentHeight: gmailModel.contentHeight" in qml
    assert "MultiEffect" in qml
    assert "gmailActionPopup" in qml
    assert "menuOpen ?" not in qml


@pytest.mark.qt
def test_retained_gmail_wrapper_routes_semantic_actions_without_recreation(qt_app) -> None:
    owner = QObject()
    factory = QuickSceneFactory(owner)
    context, root, host, component = _create_retained_host(factory, owner)
    service = _Service()
    config = _config(group_threads=False)
    model = GmailPresentationModel(config, _style(config), runtime_service=service)
    opened_inbox = []
    presentation = RetainedGmailPresentation(
        host=host,
        model=model,
        geometry=OverlayWidgetGeometry(25.0, 30.0, 620.0, 360.0),
        on_open_inbox_requested=lambda: opened_inbox.append("inbox") or True,
    )
    item = presentation.item
    engine = QQmlEngine.contextForObject(item).engine()
    try:
        presentation.activate("tm")
        model.on_gmail_runtime_snapshot(_snapshot(1, (_email("one"),)))
        qt_app.processEvents()
        row_model = model.row_model
        first_row = _find_visual_item(item, "gmailMessageRow_0")
        assert first_row is not None

        item.openInboxRequested.emit()
        item.openMessageRequested.emit("one")
        item.refreshRequested.emit()
        item.authRequested.emit()
        item.actionRequested.emit("trash", "one")
        assert opened_inbox == []
        assert service.opens == []
        assert service.refreshes == 0
        assert service.auth_requests == 0
        assert service.actions == []

        assert presentation.apply_input_state(
            {
                "admission_open": True,
                "exiting": False,
                "interaction_mode_enabled": True,
                "ctrl_held": False,
            }
        ) is True
        item.openInboxRequested.emit()
        item.openMessageRequested.emit("one")
        item.openMessageRequested.emit("missing")
        item.refreshRequested.emit()
        item.authRequested.emit()
        item.actionRequested.emit("trash", "one")
        item.actionRequested.emit("unknown", "one")
        assert opened_inbox == ["inbox"]
        assert service.opens == ["one"]
        assert service.refreshes == 1
        assert service.auth_requests == 1
        assert service.actions == [("trash", "one")]

        model.on_gmail_runtime_snapshot(
            _snapshot(2, (_email("one", subject="updated subject"),))
        )
        presentation.apply_config(replace(config, font_size=18), _style_values())
        presentation.set_geometry(OverlayWidgetGeometry(40.0, 50.0, 580.0, 320.0))
        qt_app.processEvents()
        assert presentation.item is item
        assert model.row_model is row_model
        assert _find_visual_item(item, "gmailMessageRow_0") is first_row
        assert QQmlEngine.contextForObject(item).engine() is engine
        assert item.x() == pytest.approx(40.0)
        assert item.y() == pytest.approx(50.0)
        assert item.width() == pytest.approx(580.0)
        assert item.height() == pytest.approx(320.0)
    finally:
        host.retire_all()
        root.setParentItem(None)
        root.setParent(None)
        root.deleteLater()
        context.deleteLater()
        component.deleteLater()
        owner.deleteLater()
        factory.deleteLater()
        qt_app.processEvents()

    assert model.is_active is False
    assert service.stopped == 1
    assert service.detached == 1
