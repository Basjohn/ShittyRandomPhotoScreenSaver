"""A Quick display window never asks Qt to activate itself when its native flags forbid focus.

The policy's ``accepts_focus`` was the only gate, but the live-run tools (``tools/visualizer_live_check.py``
``install_invisible_windows``) add ``WindowDoesNotAcceptFocus`` to the flags the policy built, so Qt logged
"requestActivate() called for QuickDisplayWindow ... which has Qt::WindowDoesNotAcceptFocus set" on every start. The
gate is now the window's actual flags, the one fact Qt itself checks.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QtMsgType, Qt, qInstallMessageHandler

from rendering.quick.state import QuickWindowPolicy
from rendering.quick.window import QuickDisplayWindow


def _window(qt_app, policy: QuickWindowPolicy) -> QuickDisplayWindow:
    return QuickDisplayWindow(
        screen_index=0, runtime_generation=1, screen=qt_app.primaryScreen(), policy=policy
    )


def _visibility_start(window: QuickDisplayWindow) -> list[str]:
    """Run the window's visible-edge handler (the start of a hidden-host show) and return Qt's warnings."""
    messages: list[str] = []
    previous = qInstallMessageHandler(
        lambda level, context, text: messages.append(text)
        if level in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg)
        else None
    )
    try:
        window._desired_visible = True
        window._on_window_visibility_changed(True)
    finally:
        qInstallMessageHandler(previous)
    return messages


def _activation_warnings(messages: list[str]) -> list[str]:
    return [text for text in messages if "requestActivate" in text]


def test_flag_added_after_the_policy_built_it_logs_no_activation_warning(qt_app):
    window = _window(qt_app, QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    try:
        assert window._policy.accepts_focus  # the policy alone says "focus"
        window.setFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)  # what the live-run tools do
        assert not _activation_warnings(_visibility_start(window))
    finally:
        window.deleteLater()


def test_policy_without_focus_logs_no_activation_warning(qt_app):
    window = _window(qt_app, QuickWindowPolicy(always_on_top=False, blank_cursor=False, accepts_focus=False))
    try:
        assert window.flags() & Qt.WindowType.WindowDoesNotAcceptFocus
        assert not _activation_warnings(_visibility_start(window))
    finally:
        window.deleteLater()


def test_a_focus_accepting_window_is_still_activated(qt_app, monkeypatch):
    window = _window(qt_app, QuickWindowPolicy(always_on_top=False, blank_cursor=False))
    calls: list[int] = []
    monkeypatch.setattr(QuickDisplayWindow, "requestActivate", lambda self: calls.append(1))
    try:
        assert not window.flags() & Qt.WindowType.WindowDoesNotAcceptFocus
        _visibility_start(window)
        assert calls == [1]
    finally:
        window.deleteLater()
