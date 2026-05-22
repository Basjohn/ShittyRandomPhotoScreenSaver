"""Tests for shared browser window routing helpers."""
from __future__ import annotations

from core.windows.browser_window_routing import (
    build_url_title_keywords,
    select_preferred_hwnd,
)


def test_build_url_title_keywords_adds_gmail_alias_and_dedupes():
    keywords = build_url_title_keywords(
        "https://mail.google.com/mail/u/0/#inbox",
        fallback_keywords=("gmail", "reddit", "gmail"),
    )

    assert "google" in keywords
    assert "gmail" in keywords
    assert "reddit" in keywords
    assert keywords.count("gmail") == 1


def test_select_preferred_hwnd_prefers_window_on_requested_monitor():
    candidates = [101, 202, 303]
    monitor_map = {
        101: 2,
        202: 7,
        303: 2,
    }

    chosen = select_preferred_hwnd(
        candidates,
        preferred_monitor=7,
        monitor_for_hwnd=lambda hwnd: monitor_map.get(hwnd),
    )

    assert chosen == 202


def test_select_preferred_hwnd_preserves_order_when_preferred_monitor_absent():
    candidates = [11, 22, 33]

    chosen = select_preferred_hwnd(
        candidates,
        preferred_monitor=9,
        monitor_for_hwnd=lambda _hwnd: 3,
    )

    assert chosen == 11
