from __future__ import annotations

import pytest

from core.widget_product_actions import (
    dispatch_reddit_url_product_action,
    update_clock_display_mode_override,
)


def test_clock_override_updates_only_target_display_and_preserves_shared_baseline():
    original = {
        "clock": {
            "display_mode": "digital",
            "font_size": 48,
            "display_mode_overrides": {"screen-A": "digital"},
        },
        "media": {"enabled": True},
    }

    updated, changed = update_clock_display_mode_override(
        original,
        widget_id="clock",
        display_identity="screen-B",
        normalized_mode="analog",
    )

    assert changed is True
    assert updated["clock"]["display_mode"] == "digital"
    assert updated["clock"]["font_size"] == 48
    assert updated["clock"]["display_mode_overrides"] == {
        "screen-A": "digital",
        "screen-B": "analog",
    }
    assert updated["media"] == {"enabled": True}
    assert original["clock"]["display_mode_overrides"] == {"screen-A": "digital"}


def test_clock_override_is_per_clock_instance_and_idempotent():
    original = {
        "clock": {"display_mode": "digital"},
        "clock2": {
            "display_mode": "digital",
            "display_mode_overrides": {"screen-B": "analog"},
        },
    }

    unchanged, changed = update_clock_display_mode_override(
        original,
        widget_id="clock2",
        display_identity="screen-B",
        normalized_mode="analog",
    )

    assert changed is False
    assert unchanged["clock2"]["display_mode_overrides"] == {"screen-B": "analog"}
    assert "display_mode_overrides" not in unchanged["clock"]


@pytest.mark.parametrize("widget_id", ["weather", "", "clock4"])
def test_clock_override_rejects_non_clock_identity(widget_id):
    with pytest.raises(ValueError):
        update_clock_display_mode_override(
            {},
            widget_id=widget_id,
            display_identity="screen-A",
            normalized_mode="digital",
        )


def test_reddit_saver_handoff_opens_once_then_requests_normal_exit_once():
    opened = []
    exits = []

    assert dispatch_reddit_url_product_action(
        "https://www.reddit.com/r/example/comments/abc",
        opener=lambda url: opened.append(url) or True,
        request_saver_exit=lambda: exits.append("exit"),
        interactive_build=False,
    )
    assert opened == ["https://www.reddit.com/r/example/comments/abc"]
    assert exits == ["exit"]


def test_reddit_interactive_open_does_not_exit():
    opened = []
    exits = []

    assert dispatch_reddit_url_product_action(
        "https://www.reddit.com/r/example/comments/abc",
        opener=lambda url: opened.append(url) or True,
        request_saver_exit=lambda: exits.append("exit"),
        interactive_build=True,
    )
    assert len(opened) == 1
    assert exits == []


def test_reddit_failed_open_does_not_exit_and_empty_url_is_rejected():
    exits = []
    attempts = []

    assert not dispatch_reddit_url_product_action(
        "https://www.reddit.com/r/example/comments/abc",
        opener=lambda url: attempts.append(url) or False,
        request_saver_exit=lambda: exits.append("exit"),
        interactive_build=False,
    )
    assert len(attempts) == 1
    assert exits == []

    assert not dispatch_reddit_url_product_action(
        "   ",
        opener=lambda url: attempts.append(url) or True,
        request_saver_exit=lambda: exits.append("exit"),
        interactive_build=False,
    )
    assert len(attempts) == 1
    assert exits == []
