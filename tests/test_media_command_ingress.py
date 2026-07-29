from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

import rendering.display_native_events as display_native_events
import rendering.media_command_ingress as media_command_ingress
from rendering.display_native_events import (
    _dispatch_media_vk_feedback,
    dispatch_appcommand,
    handle_win_appcommand,
)
from rendering.input_handler import InputHandler


@pytest.fixture(autouse=True)
def _reset_process_media_gate():
    media_command_ingress.reset_media_command_ingress_for_tests()
    yield
    media_command_ingress.reset_media_command_ingress_for_tests()


def _media_key_event(key):
    event = MagicMock(spec=QKeyEvent)
    event.key.return_value = key
    event.nativeVirtualKey.return_value = 0
    return event


def test_process_gate_rejects_same_command_without_sliding_window():
    assert media_command_ingress.claim_external_media_command(
        "next",
        route="first",
        now=10.0,
    )
    assert not media_command_ingress.claim_external_media_command(
        "next",
        route="duplicate_a",
        now=10.10,
    )
    assert not media_command_ingress.claim_external_media_command(
        "next",
        route="duplicate_b",
        now=10.20,
    )
    assert media_command_ingress.claim_external_media_command(
        "next",
        route="new_press",
        now=10.21,
    )


def test_native_qt_and_appcommand_routes_accept_one_command_before_widget_lookup(
    monkeypatch,
    caplog,
):
    media_widget = MagicMock()
    media_widget.handle_transport_command.return_value = True
    visualizer = MagicMock()
    display = SimpleNamespace(
        media_widget=media_widget,
        findChildren=lambda _type: [visualizer],
    )
    handler = InputHandler(None)
    handler._parent = MagicMock()
    handler._resolve_media_widget = MagicMock(return_value=media_widget)

    monkeypatch.setattr(
        media_command_ingress,
        "is_perf_metrics_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        media_command_ingress,
        "any_display_transition_active",
        lambda: True,
    )

    with caplog.at_level(logging.INFO):
        _dispatch_media_vk_feedback(display, 0xB0)
        handler._handle_media_key_feedback(_media_key_event(Qt.Key.Key_MediaNext))
        assert dispatch_appcommand(display, 0x0005, "APPCOMMAND_MEDIA_NEXTTRACK")

    media_widget.handle_transport_command.assert_called_once_with(
        "next",
        source="media_vk:0xb0",
        execute=False,
    )
    handler._resolve_media_widget.assert_not_called()
    visualizer._trigger_wake.assert_called_once_with(
        reason="external_media_command"
    )

    ingress = [
        record.getMessage()
        for record in caplog.records
        if "[PERF][MEDIA_FEEDBACK] phase=ingress" in record.getMessage()
    ]
    assert len(ingress) == 3
    assert sum("duplicate_suppressed=False" in message for message in ingress) == 1
    assert sum("duplicate_suppressed=True" in message for message in ingress) == 2
    assert all("transition_active=True" in message for message in ingress)


def test_duplicate_appcommand_still_passes_through_to_windows(monkeypatch):
    media_widget = MagicMock()
    media_widget.handle_transport_command.return_value = True
    display = SimpleNamespace(
        media_widget=media_widget,
        findChildren=lambda _type: [],
        _mc_window_flag_mode="standard",
    )
    user32 = SimpleNamespace(DefWindowProcW=MagicMock(return_value=123))
    monkeypatch.setattr(display_native_events, "_USER32", user32)
    msg = SimpleNamespace(
        hwnd=101,
        wParam=202,
        lParam=(0x0005 << 16),
    )

    assert handle_win_appcommand(display, msg) == (True, 123)
    assert handle_win_appcommand(display, msg) == (True, 123)

    assert user32.DefWindowProcW.call_count == 2
    media_widget.handle_transport_command.assert_called_once()
