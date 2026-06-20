"""Tests for RedditWidget behaviour and integration points.

These cover filtering, age label formatting, hide-on-error behaviour, and
click handling for posts and the header.
"""

import time
from datetime import datetime, timedelta
import json
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, QRect

from core.reddit_post_provider import RedditProviderResult
from widgets.reddit_widget import RedditWidget


@pytest.mark.qt
def test_reddit_filters_daily_weekly_question_threads(qt_app, qtbot):  # noqa: ARG001
    """Daily/Weekly/Question Thread posts should be filtered out.

    Titles containing these markers (case-insensitive) must not appear in the
    final `_posts` list used for painting/click handling.
    """

    widget = RedditWidget()
    qtbot.addWidget(widget)

    now = time.time()
    posts_data = [
        {
            "title": "Daily Discussion Thread",
            "url": "https://example.com/a",
            "score": 1,
            "created_utc": now - 60,
        },
        {
            "title": "weekly QUESTION thread",
            "url": "https://example.com/b",
            "score": 2,
            "created_utc": now - 120,
        },
        {
            "title": "Some normal wallpaper post",
            "url": "https://example.com/c",
            "score": 42,
            "created_utc": now - 300,
        },
    ]

    # Call the internal handler directly with synthetic data.
    widget._on_feed_fetched(posts_data)  # type: ignore[attr-defined]

    # Only the non-thread post should survive.
    assert len(widget._posts) == 1  # type: ignore[attr-defined]
    remaining = widget._posts[0]  # type: ignore[attr-defined]
    assert "daily" not in remaining.title.lower()
    assert "weekly" not in remaining.title.lower()
    assert "question thread" not in remaining.title.lower()


def test_reddit_format_age_variants():
    """_format_age should map seconds to human-readable buckets."""

    widget = RedditWidget()

    now = 1_000_000.0

    # Sub‑minute rounds up to 1M AGO.
    assert widget._format_age(now - 10, now) == "1M AGO"  # type: ignore[attr-defined]
    # Minutes under an hour.
    assert widget._format_age(now - 15 * 60, now) == "15M AGO"  # type: ignore[attr-defined]
    # Hours under a day.
    assert widget._format_age(now - 2 * 3600, now) == "2HR AGO"  # type: ignore[attr-defined]
    # Days under a week.
    assert widget._format_age(now - 3 * 86400, now) == "3D AGO"  # type: ignore[attr-defined]
    # Weeks under a year.
    assert widget._format_age(now - 3 * 7 * 86400, now) == "3W AGO"  # type: ignore[attr-defined]
    # Years.
    assert widget._format_age(now - 2 * 365 * 86400, now) == "2Y AGO"  # type: ignore[attr-defined]


@pytest.mark.qt
def test_reddit_item_limit_clamps_to_shared_capacity_policy(qt_app, qtbot):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)

    widget.set_item_limit(4)
    assert widget.configured_capacity == 5

    widget.set_item_limit(30)
    assert widget.configured_capacity == 25


@pytest.mark.qt
def test_reddit_custom_layout_rect_survives_content_height_recalc(qt_app, qtbot):  # noqa: ARG001
    from PySide6.QtWidgets import QApplication, QWidget

    parent = QWidget()
    parent.resize(1200, 900)
    widget = RedditWidget(parent)
    qtbot.addWidget(parent)
    qtbot.addWidget(widget)
    try:
        custom_rect = QRect(40, 50, 620, 344)
        widget._custom_layout_local_rect = QRect(custom_rect)  # type: ignore[attr-defined]
        widget._configured_capacity = 10  # type: ignore[attr-defined]
        widget._effective_visible_capacity = 10  # type: ignore[attr-defined]
        widget._update_position()  # type: ignore[attr-defined]

        widget.set_font_size(26)
        widget._update_card_height_from_content(10)  # type: ignore[attr-defined]
        QApplication.processEvents()

        assert widget.geometry() == custom_rect
    finally:
        widget.cleanup()
        parent.deleteLater()


@pytest.mark.qt
def test_reddit_content_height_updates_do_not_change_width_constraints(qt_app, qtbot):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)

    widget.resize(640, 200)
    widget.setMinimumWidth(640)
    widget.setMaximumWidth(640)
    widget._effective_visible_capacity = 10  # type: ignore[attr-defined]

    widget._update_card_height_from_content(10)  # type: ignore[attr-defined]

    assert widget.minimumWidth() == 640
    assert widget.maximumWidth() == 640
    assert widget.minimumHeight() == widget.maximumHeight()


@pytest.mark.qt
def test_reddit_small_font_compacts_age_column_width(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    from PySide6.QtGui import QPainter, QPixmap

    from widgets import reddit_widget as reddit_module
    from widgets.reddit_components import RedditPost

    widget = RedditWidget()
    qtbot.addWidget(widget)

    widget.resize(420, 220)
    widget._posts = [  # type: ignore[attr-defined]
        RedditPost(
            title="A longer post title that benefits from more horizontal room",
            url="https://example.com/post",
            score=10,
            created_utc=time.time() - 7200,
        )
    ]

    captured_age_widths: list[int] = []
    original_draw_text_rect_with_shadow = reddit_module.draw_text_rect_with_shadow

    def _capture_draw_text_rect_with_shadow(painter, rect, flags, text, **kwargs):
        if text in {"02", "HR", "AGO", "02 HR"}:
            captured_age_widths.append(rect.width())
        return original_draw_text_rect_with_shadow(painter, rect, flags, text, **kwargs)

    monkeypatch.setattr(
        reddit_module,
        "draw_text_rect_with_shadow",
        _capture_draw_text_rect_with_shadow,
    )

    def _paint_and_age_width() -> int:
        captured_age_widths.clear()
        pixmap = QPixmap(widget.size())
        pixmap.fill()
        painter = QPainter(pixmap)
        try:
            widget._paint_content_to_painter(painter)  # type: ignore[attr-defined]
        finally:
            painter.end()
        assert captured_age_widths
        return max(captured_age_widths)

    widget.set_font_size(18)
    baseline_width = _paint_and_age_width()

    widget.set_font_size(8)
    compact_width = _paint_and_age_width()

    assert compact_width < baseline_width


@pytest.mark.qt
def test_reddit_small_font_rebalances_budget_toward_title_text(qt_app, qtbot):  # noqa: ARG001
    from widgets.reddit_components import RedditPost

    widget = RedditWidget()
    qtbot.addWidget(widget)

    widget.resize(420, 220)
    widget._posts = [  # type: ignore[attr-defined]
        RedditPost(
            title="A longer post title that benefits from more horizontal room",
            url="https://example.com/post",
            score=10,
            created_utc=time.time() - (22 * 3600),
        )
    ]

    rect = widget.rect().adjusted(12, 12, -12, -12)
    age_labels = [widget._format_age(widget._posts[0].created_utc, time.time())]  # type: ignore[attr-defined]

    widget.set_font_size(18)
    baseline_metrics = widget._compute_post_layout_metrics(rect, age_labels)  # type: ignore[attr-defined]

    widget.set_font_size(8)
    compact_metrics = widget._compute_post_layout_metrics(rect, age_labels)  # type: ignore[attr-defined]

    assert compact_metrics["age_col_width"] < baseline_metrics["age_col_width"]
    assert compact_metrics["title_available_width"] > baseline_metrics["title_available_width"]


@pytest.mark.qt
def test_reddit_age_lane_budget_reserves_full_suffix_width(qt_app, qtbot):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)

    widget.resize(220, 140)
    widget.set_font_size(11)
    rect = widget.rect().adjusted(12, 12, -12, -12)
    age_labels = ["2W AGO"]

    metrics = widget._compute_post_layout_metrics(rect, age_labels)  # type: ignore[attr-defined]
    age_metrics = metrics["age_metrics"]
    suffix_width = age_metrics.horizontalAdvance("AGO")
    value_width = age_metrics.horizontalAdvance("2W")
    split_gap = metrics["age_split_gap"]

    assert metrics["age_col_width"] >= value_width + split_gap + suffix_width


@pytest.mark.qt
def test_reddit_error_hides_before_first_success(qt_app, qtbot):  # noqa: ARG001
    """On fetch error before any valid data, the widget should hide itself."""

    widget = RedditWidget()
    qtbot.addWidget(widget)

    # Sanity: no valid data yet.
    assert not widget._has_displayed_valid_data  # type: ignore[attr-defined]

    widget._on_fetch_error("boom")  # type: ignore[attr-defined]

    assert not widget.isVisible()
    assert not widget._has_displayed_valid_data  # type: ignore[attr-defined]


@pytest.mark.qt
def test_reddit_fetch_error_keeps_displayed_cache_visible(qt_app, qtbot):  # noqa: ARG001
    """Fetch errors should not replace already-visible Reddit content."""

    from widgets.reddit_components import RedditPost

    widget = RedditWidget()
    qtbot.addWidget(widget)

    hide_calls = []
    try:
        widget._posts = [  # type: ignore[attr-defined]
            RedditPost(
                title="Visible post",
                url="https://example.com/post",
                score=10,
                created_utc=time.time(),
            )
        ]
        widget._has_displayed_valid_data = True  # type: ignore[attr-defined]
        widget.hide = lambda *args, **kwargs: hide_calls.append("hide")  # type: ignore[method-assign]

        widget._on_fetch_error("boom")  # type: ignore[attr-defined]

        assert len(widget._posts) == 1  # type: ignore[attr-defined]
        assert hide_calls == []
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_403_error_touches_cache_timestamp_and_starts_block_cooldown(qt_app, qtbot, tmp_path):  # noqa: ARG001
    from core.reddit_rate_limiter import RedditRateLimiter

    widget = RedditWidget()
    qtbot.addWidget(widget)
    cache_path = tmp_path / "reddit_cache.json"
    gate_path = tmp_path / "reddit_gate.touch"
    try:
        RedditRateLimiter.reset()
        widget._get_cache_file_path = lambda: Path(cache_path)  # type: ignore[method-assign]
        widget._get_service_gate_file_path = lambda: Path(gate_path)  # type: ignore[method-assign]

        widget._on_fetch_error("403 Client Error: Blocked for url: https://www.reddit.com/r/Games/hot.json?limit=25")  # type: ignore[attr-defined]

        assert cache_path.exists()
        assert gate_path.exists()
        assert RedditRateLimiter.get_blocked_cooldown_remaining() > 0
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_429_error_touches_cache_timestamp_and_starts_block_cooldown(qt_app, qtbot, tmp_path):  # noqa: ARG001
    from core.reddit_rate_limiter import RedditRateLimiter

    widget = RedditWidget()
    qtbot.addWidget(widget)
    cache_path = tmp_path / "reddit_cache.json"
    gate_path = tmp_path / "reddit_gate.touch"
    try:
        RedditRateLimiter.reset()
        widget._get_cache_file_path = lambda: Path(cache_path)  # type: ignore[method-assign]
        widget._get_service_gate_file_path = lambda: Path(gate_path)  # type: ignore[method-assign]

        widget._on_fetch_error("429 Client Error: Too Many Requests for url: https://www.reddit.com/r/SubredditDrama/.rss")  # type: ignore[attr-defined]

        assert cache_path.exists()
        assert gate_path.exists()
        assert RedditRateLimiter.get_blocked_cooldown_remaining() > 0
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_fetch_skips_network_while_blocked_cooldown_is_active(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    from core.reddit_rate_limiter import RedditRateLimiter

    widget = RedditWidget()
    qtbot.addWidget(widget)
    calls: list[str] = []
    try:
        RedditRateLimiter.reset()
        RedditRateLimiter.record_blocked_response(reason="test")
        monkeypatch.setattr("core.reddit_post_provider.requests.get", lambda *args, **kwargs: calls.append("get"))

        assert widget._fetch_feed(defer_for_transition=False) is True  # type: ignore[attr-defined]
        assert calls == []
    finally:
        widget.cleanup()
        RedditRateLimiter.reset()


@pytest.mark.qt
def test_reddit_blocked_slot_skip_does_not_fall_through_to_empty_listing_logs(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    from core.reddit_rate_limiter import RedditRateLimiter

    widget = RedditWidget()
    qtbot.addWidget(widget)
    empty_listing_logs: list[str] = []
    try:
        RedditRateLimiter.reset()
        monkeypatch.setattr(
            "widgets.reddit_widget.begin_fetch_guard",
            lambda *args, **kwargs: True,
        )
        monkeypatch.setattr(
            "widgets.reddit_widget.end_fetch_guard",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "widgets.reddit_widget.preserve_visible_fallback",
            lambda *args, **kwargs: True,
        )
        monkeypatch.setattr(
            RedditRateLimiter,
            "get_blocked_cooldown_remaining",
            staticmethod(lambda: 10.0),
        )
        monkeypatch.setattr(
            "widgets.reddit_widget.logger.warning",
            lambda msg, *args, **kwargs: empty_listing_logs.append(msg % args if args else msg),
        )

        assert widget._fetch_feed(defer_for_transition=False) is True  # type: ignore[attr-defined]

        assert not any("Empty listing" in message for message in empty_listing_logs)
    finally:
        widget.cleanup()
        RedditRateLimiter.reset()


@pytest.mark.qt
def test_reddit_startup_refresh_uses_shared_service_gate_before_rate_limiter(qt_app, qtbot, tmp_path):  # noqa: ARG001
    from datetime import timedelta
    import os

    widget = RedditWidget()
    qtbot.addWidget(widget)
    cache_path = tmp_path / "reddit_cache.json"
    gate_path = tmp_path / "reddit_gate.touch"
    try:
        cache_path.write_text("[]", encoding="utf-8")
        widget._get_cache_file_path = lambda: Path(cache_path)  # type: ignore[method-assign]
        widget._get_service_gate_file_path = lambda: Path(gate_path)  # type: ignore[method-assign]

        old_ts = time.time() - (2 * 3600)
        os.utime(cache_path, (old_ts, old_ts))
        widget._touch_service_gate_timestamp_now()  # type: ignore[attr-defined]

        decision = widget._get_startup_refresh_decision()  # type: ignore[attr-defined]

        assert decision.run is False
        assert decision.reason == "blocked_cooldown_cache_fresh"
        assert decision.age is not None
        assert decision.age < timedelta(minutes=1)
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_startup_refresh_skips_when_recent_startup_attempt_exists(qt_app, qtbot, tmp_path):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)
    cache_path = tmp_path / "reddit_cache.json"
    gate_path = tmp_path / "reddit_gate.touch"
    attempt_path = tmp_path / "reddit_attempt.touch"
    try:
        cache_path.write_text("[]", encoding="utf-8")
        widget._get_cache_file_path = lambda: Path(cache_path)  # type: ignore[method-assign]
        widget._get_service_gate_file_path = lambda: Path(gate_path)  # type: ignore[method-assign]
        widget._get_startup_attempt_file_path = lambda: Path(attempt_path)  # type: ignore[method-assign]

        widget._touch_startup_attempt_timestamp_now()  # type: ignore[attr-defined]
        decision = widget._get_startup_refresh_decision()  # type: ignore[attr-defined]

        assert decision.run is False
        assert decision.reason == "startup_attempt_cooldown"
        assert decision.age is not None
        assert decision.age < timedelta(minutes=1)
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_activate_skips_startup_fetch_when_recent_startup_attempt_exists(qt_app, qtbot, monkeypatch, tmp_path):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)
    cache_path = tmp_path / "reddit_cache.json"
    gate_path = tmp_path / "reddit_gate.touch"
    attempt_path = tmp_path / "reddit_attempt.touch"
    try:
        calls = []
        widget.set_thread_manager(object())
        widget._get_cache_file_path = lambda: Path(cache_path)  # type: ignore[method-assign]
        widget._get_service_gate_file_path = lambda: Path(gate_path)  # type: ignore[method-assign]
        widget._get_startup_attempt_file_path = lambda: Path(attempt_path)  # type: ignore[method-assign]
        widget._touch_startup_attempt_timestamp_now()  # type: ignore[attr-defined]

        monkeypatch.setattr(widget, "_load_cached_posts", lambda: [])
        monkeypatch.setattr(widget, "_schedule_timer", lambda: calls.append("timer"))
        monkeypatch.setattr(widget, "_fetch_feed", lambda **kwargs: calls.append(("fetch", kwargs)) or True)  # type: ignore[method-assign]

        widget._activate_impl()

        assert calls == ["timer"]
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit2_startup_refresh_shares_recent_attempt_gate_with_reddit1(qt_app, qtbot, monkeypatch, tmp_path):  # noqa: ARG001
    attempt_path = tmp_path / "reddit_attempt.touch"
    gate_path = tmp_path / "reddit_gate.touch"
    cache_path_1 = tmp_path / "reddit_posts.json"
    cache_path_2 = tmp_path / "reddit2_posts.json"

    widget1 = RedditWidget()
    widget2 = RedditWidget()
    qtbot.addWidget(widget1)
    qtbot.addWidget(widget2)

    try:
        widget1.set_thread_manager(object())
        widget2.set_thread_manager(object())
        widget1._cache_key = "reddit"  # type: ignore[attr-defined]
        widget2._cache_key = "reddit2"  # type: ignore[attr-defined]

        widget1._get_cache_file_path = lambda: Path(cache_path_1)  # type: ignore[method-assign]
        widget2._get_cache_file_path = lambda: Path(cache_path_2)  # type: ignore[method-assign]
        widget1._get_service_gate_file_path = lambda: Path(gate_path)  # type: ignore[method-assign]
        widget2._get_service_gate_file_path = lambda: Path(gate_path)  # type: ignore[method-assign]
        widget1._get_startup_attempt_file_path = lambda: Path(attempt_path)  # type: ignore[method-assign]
        widget2._get_startup_attempt_file_path = lambda: Path(attempt_path)  # type: ignore[method-assign]

        calls1 = []
        calls2 = []
        monkeypatch.setattr(widget1, "_load_cached_posts", lambda: [])
        monkeypatch.setattr(widget2, "_load_cached_posts", lambda: [])
        monkeypatch.setattr(widget1, "_schedule_timer", lambda: calls1.append("timer"))
        monkeypatch.setattr(widget2, "_schedule_timer", lambda: calls2.append("timer"))
        monkeypatch.setattr(widget1, "_fetch_feed", lambda **kwargs: calls1.append(("fetch", kwargs)) or True)  # type: ignore[method-assign]
        monkeypatch.setattr(widget2, "_fetch_feed", lambda **kwargs: calls2.append(("fetch", kwargs)) or True)  # type: ignore[method-assign]

        widget1._activate_impl()
        widget2._activate_impl()

        assert calls1 == ["timer", ("fetch", {})]
        assert calls2 == ["timer"]
        assert widget2._get_startup_refresh_decision().reason == "startup_attempt_cooldown"  # type: ignore[attr-defined]
    finally:
        widget1.cleanup()
        widget2.cleanup()


@pytest.mark.qt
def test_reddit_empty_fetch_keeps_displayed_cache_visible(qt_app, qtbot):  # noqa: ARG001
    """An empty live fetch must not replace valid displayed Reddit content."""

    from widgets.reddit_components import RedditPost

    widget = RedditWidget()
    qtbot.addWidget(widget)

    hide_calls = []
    try:
        widget._posts = [  # type: ignore[attr-defined]
            RedditPost(
                title="Visible post",
                url="https://example.com/post",
                score=10,
                created_utc=time.time(),
            )
        ]
        widget._has_displayed_valid_data = True  # type: ignore[attr-defined]
        widget.hide = lambda *args, **kwargs: hide_calls.append("hide")  # type: ignore[method-assign]

        widget._on_feed_fetched([])  # type: ignore[attr-defined]

        assert len(widget._posts) == 1  # type: ignore[attr-defined]
        assert hide_calls == []
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_handle_click_row_opens_url(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    """handle_click should call QDesktopServices.openUrl for row hits."""

    widget = RedditWidget()
    qtbot.addWidget(widget)

    opened = []

    def _fake_open(url):  # noqa: ANN001
        opened.append(str(url.toString()))
        return True

    monkeypatch.setattr(
        "widgets.reddit_widget.QDesktopServices.openUrl",
        _fake_open,
    )

    # Inject a synthetic row hit rect without relying on paintEvent.
    widget._row_hit_rects = [  # type: ignore[attr-defined]
        (QRect(0, 20, 100, 20), "https://example.com/post", "Some Title"),
    ]

    handled = widget.handle_click(QPoint(10, 30))

    assert handled is True
    assert opened == ["https://example.com/post"]


@pytest.mark.qt
def test_reddit_handle_click_header_opens_subreddit(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    """Clicking inside the header hit-rect should open the subreddit URL."""

    widget = RedditWidget(subreddit="wallpapers")
    qtbot.addWidget(widget)

    opened = []

    def _fake_open(url):  # noqa: ANN001
        opened.append(str(url.toString()))
        return True

    monkeypatch.setattr(
        "widgets.reddit_widget.QDesktopServices.openUrl",
        _fake_open,
    )

    # Simulate a header area and ensure handle_click routes there first.
    widget._header_hit_rect = QRect(0, 0, 200, 30)  # type: ignore[attr-defined]

    handled = widget.handle_click(QPoint(10, 10))

    assert handled is True
    assert opened == ["https://www.reddit.com/r/wallpapers"]


@pytest.mark.qt
def test_reddit_manual_refresh_defers_during_parent_transition(qt_app, qtbot):  # noqa: ARG001
    """Refresh spiral work should wait until the parent transition is idle."""
    from PySide6.QtWidgets import QWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.running = True

        def has_running_transition(self):
            return self.running

    parent = TransitionParent()
    widget = RedditWidget(parent)
    qtbot.addWidget(parent)
    qtbot.addWidget(widget)
    calls = []
    try:
        widget._enabled = True  # type: ignore[attr-defined]
        widget._fetch_feed = lambda **kwargs: calls.append(kwargs) or True  # type: ignore[method-assign]

        assert widget._trigger_manual_refresh() is True  # type: ignore[attr-defined]
        assert widget._pending_refresh_after_transition is True  # type: ignore[attr-defined]
        assert calls == []

        parent.running = False
        widget._flush_deferred_refresh()  # type: ignore[attr-defined]

        assert widget._pending_refresh_after_transition is False  # type: ignore[attr-defined]
        assert calls == [{}]
    finally:
        widget.cleanup()
        parent.deleteLater()


@pytest.mark.qt
def test_reddit_manual_refresh_ignores_duplicate_fetch(qt_app, qtbot):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)
    try:
        widget._enabled = True  # type: ignore[attr-defined]
        widget._fetch_in_progress = True  # type: ignore[attr-defined]
        calls = []
        widget._fetch_feed = lambda **kwargs: calls.append(kwargs) or True  # type: ignore[method-assign]

        started = widget._trigger_manual_refresh()  # type: ignore[attr-defined]

        assert started is True
        assert calls == []
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_activate_runs_startup_fetch_when_cache_is_fresh(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)
    try:
        calls = []
        widget.set_thread_manager(object())
        monkeypatch.setattr(widget, "_load_cached_posts", lambda: [])
        monkeypatch.setattr(widget, "_get_cache_timestamp", lambda: datetime.now())
        monkeypatch.setattr(widget, "_get_service_gate_timestamp", lambda: None)
        monkeypatch.setattr(widget, "_get_startup_attempt_timestamp", lambda: None)
        monkeypatch.setattr(widget, "_schedule_timer", lambda: calls.append("timer"))
        monkeypatch.setattr(widget, "_fetch_feed", lambda **kwargs: calls.append(("fetch", kwargs)) or True)  # type: ignore[method-assign]

        widget._activate_impl()

        assert calls == ["timer", ("fetch", {})]
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_activate_runs_startup_fetch_when_cache_is_old(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)
    try:
        calls = []
        widget.set_thread_manager(object())
        monkeypatch.setattr(widget, "_load_cached_posts", lambda: [])
        monkeypatch.setattr(widget, "_get_cache_timestamp", lambda: datetime.now() - timedelta(days=3))
        monkeypatch.setattr(widget, "_get_service_gate_timestamp", lambda: None)
        monkeypatch.setattr(widget, "_get_startup_attempt_timestamp", lambda: None)
        monkeypatch.setattr(widget, "_schedule_timer", lambda: calls.append("timer"))
        monkeypatch.setattr(widget, "_fetch_feed", lambda **kwargs: calls.append(("fetch", kwargs)) or True)  # type: ignore[method-assign]

        widget._activate_impl()

        assert calls == ["timer", ("fetch", {})]
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_activate_uses_cached_posts_before_refresh(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    from widgets.reddit_components import RedditPost

    widget = RedditWidget()
    qtbot.addWidget(widget)
    try:
        widget.set_thread_manager(object())
        cached_posts = [
            RedditPost(
                title="Cached post",
                url="https://example.com/post",
                score=10,
                created_utc=time.time(),
            )
        ]
        calls = []
        monkeypatch.setattr(widget, "_load_cached_posts", lambda: list(cached_posts))
        monkeypatch.setattr(widget, "_get_service_gate_timestamp", lambda: None)
        monkeypatch.setattr(widget, "_get_startup_attempt_timestamp", lambda: None)
        monkeypatch.setattr(widget, "_schedule_timer", lambda: calls.append("timer"))
        monkeypatch.setattr(widget, "_fetch_feed", lambda **kwargs: calls.append(("fetch", kwargs)) or True)  # type: ignore[method-assign]

        widget._activate_impl()

        assert len(widget._posts) == 1  # type: ignore[attr-defined]
        assert widget._posts[0].title == "Cached post"  # type: ignore[attr-defined]
        assert calls == ["timer", ("fetch", {})]
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_activate_disables_automatic_updates_under_noupdates(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)
    try:
        calls = []
        widget.set_thread_manager(object())
        monkeypatch.setattr("widgets.reddit_widget.automatic_service_updates_enabled", lambda: False)
        monkeypatch.setattr(widget, "_load_cached_posts", lambda: [])
        monkeypatch.setattr(widget, "_schedule_timer", lambda: calls.append("timer"))
        monkeypatch.setattr(widget, "_fetch_feed", lambda **kwargs: calls.append(("fetch", kwargs)) or True)  # type: ignore[method-assign]

        widget._activate_impl()

        assert calls == []
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_fetch_result_defers_apply_during_parent_transition(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    """Fetched Reddit data should not invalidate/repaint content mid-transition."""
    from PySide6.QtWidgets import QWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.running = True

        def has_running_transition(self):
            return self.running

    parent = TransitionParent()
    widget = RedditWidget(parent)
    qtbot.addWidget(parent)
    qtbot.addWidget(widget)
    try:
        monkeypatch.setattr(widget, "_save_cached_posts", lambda posts: None)
        widget._fetch_in_progress = True  # type: ignore[attr-defined]
        posts_data = [
            {
                "title": "A normal post",
                "url": "https://example.com/post",
                "score": 1,
                "created_utc": time.time(),
            }
        ]

        widget._on_feed_fetched(posts_data)  # type: ignore[attr-defined]

        assert widget._fetch_in_progress is False  # type: ignore[attr-defined]
        assert widget._posts == []  # type: ignore[attr-defined]
        assert widget._deferred_posts_data == posts_data  # type: ignore[attr-defined]

        parent.running = False
        widget._flush_deferred_refresh()  # type: ignore[attr-defined]

        assert len(widget._posts) == 1  # type: ignore[attr-defined]
        assert widget._deferred_posts_data is None  # type: ignore[attr-defined]
    finally:
        widget.cleanup()
        parent.deleteLater()


@pytest.mark.qt
def test_reddit_fetch_uses_injected_post_provider(qt_app, qtbot):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)
    calls = []

    class StubProvider:
        def fetch_posts(self, request):
            calls.append(request)
            return RedditProviderResult(
                posts=[
                    {
                        "title": "Injected post",
                        "url": "https://example.com/post",
                        "score": 3,
                        "created_utc": time.time(),
                    }
                ],
                skip_reason=None,
            )

    try:
        widget.set_post_provider(StubProvider())
        widget._fetch_in_progress = False  # type: ignore[attr-defined]
        widget._subreddit = "wallpapers"  # type: ignore[attr-defined]

        # Drive the sync path so the provider contract is exercised directly.
        widget._thread_manager = None  # type: ignore[attr-defined]
        assert widget._fetch_feed(defer_for_transition=False) is True  # type: ignore[attr-defined]

        assert len(calls) == 1
        assert calls[0].subreddit == "wallpapers"
        assert len(widget._posts) == 1  # type: ignore[attr-defined]
        assert widget._posts[0].title == "Injected post"  # type: ignore[attr-defined]
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_fetch_writes_cache_file_from_provider_result(qt_app, qtbot, tmp_path):  # noqa: ARG001
    widget = RedditWidget()
    qtbot.addWidget(widget)
    cache_path = tmp_path / "reddit_posts.json"
    calls = []

    class StubProvider:
        def fetch_posts(self, request):
            calls.append(request)
            return RedditProviderResult(
                posts=[
                    {
                        "title": "Cached from provider",
                        "url": "https://example.com/cached",
                        "score": 11,
                        "created_utc": 1710001111,
                    }
                ],
                skip_reason=None,
            )

    try:
        widget.set_post_provider(StubProvider())
        widget._fetch_in_progress = False  # type: ignore[attr-defined]
        widget._subreddit = "wallpapers"  # type: ignore[attr-defined]
        widget._thread_manager = None  # type: ignore[attr-defined]
        widget._get_cache_file_path = lambda: Path(cache_path)  # type: ignore[method-assign]

        assert widget._fetch_feed(defer_for_transition=False) is True  # type: ignore[attr-defined]

        assert len(calls) == 1
        assert cache_path.exists()
        saved = json.loads(cache_path.read_text(encoding="utf-8"))
        assert saved == [
            {
                "title": "Cached from provider",
                "url": "https://example.com/cached",
                "score": 11,
                "created_utc": 1710001111.0,
            }
        ]
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_provider_error_keeps_displayed_cache_visible(qt_app, qtbot):  # noqa: ARG001
    from widgets.reddit_components import RedditPost

    widget = RedditWidget()
    qtbot.addWidget(widget)

    class FailingProvider:
        def fetch_posts(self, request):  # noqa: ANN001
            raise RuntimeError("pullpush unavailable")

    try:
        widget._posts = [  # type: ignore[attr-defined]
            RedditPost(
                title="Visible post",
                url="https://example.com/post",
                score=10,
                created_utc=time.time(),
            )
        ]
        widget._has_displayed_valid_data = True  # type: ignore[attr-defined]
        widget._thread_manager = None  # type: ignore[attr-defined]
        widget.set_post_provider(FailingProvider())

        assert widget._fetch_feed(defer_for_transition=False) is False  # type: ignore[attr-defined]
        assert len(widget._posts) == 1  # type: ignore[attr-defined]
        assert widget._posts[0].title == "Visible post"  # type: ignore[attr-defined]
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_empty_provider_result_keeps_displayed_cache_visible(qt_app, qtbot):  # noqa: ARG001
    from widgets.reddit_components import RedditPost

    widget = RedditWidget()
    qtbot.addWidget(widget)

    class EmptyProvider:
        def fetch_posts(self, request):  # noqa: ANN001
            return RedditProviderResult(posts=[], skip_reason=None)

    try:
        widget._posts = [  # type: ignore[attr-defined]
            RedditPost(
                title="Visible post",
                url="https://example.com/post",
                score=10,
                created_utc=time.time(),
            )
        ]
        widget._has_displayed_valid_data = True  # type: ignore[attr-defined]
        widget._thread_manager = None  # type: ignore[attr-defined]
        widget.set_post_provider(EmptyProvider())

        assert widget._fetch_feed(defer_for_transition=False) is True  # type: ignore[attr-defined]
        assert len(widget._posts) == 1  # type: ignore[attr-defined]
        assert widget._posts[0].title == "Visible post"  # type: ignore[attr-defined]
    finally:
        widget.cleanup()


@pytest.mark.qt
def test_reddit_fetch_result_defers_apply_during_parent_transition_pending(qt_app, qtbot, monkeypatch):  # noqa: ARG001
    """Fetched Reddit data should wait during the accepted-before-running transition window."""
    from PySide6.QtWidgets import QWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.pending = True

        def has_transition_work_pending(self):
            return self.pending

        def has_running_transition(self):
            return False

    parent = TransitionParent()
    widget = RedditWidget(parent)
    qtbot.addWidget(parent)
    qtbot.addWidget(widget)
    try:
        monkeypatch.setattr(widget, "_save_cached_posts", lambda posts: None)
        posts_data = [
            {
                "title": "A pending post",
                "url": "https://example.com/post",
                "score": 1,
                "created_utc": time.time(),
            }
        ]

        widget._on_feed_fetched(posts_data)  # type: ignore[attr-defined]

        assert widget._posts == []  # type: ignore[attr-defined]
        assert widget._deferred_posts_data == posts_data  # type: ignore[attr-defined]

        parent.pending = False
        widget._flush_deferred_refresh()  # type: ignore[attr-defined]

        assert len(widget._posts) == 1  # type: ignore[attr-defined]
    finally:
        widget.cleanup()
        parent.deleteLater()


@pytest.mark.qt
def test_reddit_transition_pending_parent_chain_and_spinner_suspend(qt_app, qtbot):  # noqa: ARG001
    """A Reddit refresh already in flight should stop spinner repaint when transition work starts."""
    from PySide6.QtWidgets import QWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.pending = False

        def has_transition_work_pending(self):
            return self.pending

    parent = TransitionParent()
    container = QWidget(parent)
    widget = RedditWidget(container)
    qtbot.addWidget(parent)
    qtbot.addWidget(container)
    qtbot.addWidget(widget)
    updates = []
    try:
        widget.update = lambda *args, **kwargs: updates.append(args)  # type: ignore[method-assign]
        widget._start_refresh_spinner()  # type: ignore[attr-defined]
        assert widget._refreshing is True  # type: ignore[attr-defined]
        assert widget._refresh_spinner_suspended_for_transition is False  # type: ignore[attr-defined]
        assert widget._refresh_spin_timer is not None  # type: ignore[attr-defined]
        assert widget._refresh_spin_timer.isActive()  # type: ignore[attr-defined]

        parent.pending = True
        assert widget._parent_transition_running() is True  # type: ignore[attr-defined]
        widget.on_parent_transition_work_pending(True)  # type: ignore[attr-defined]

        assert widget._refreshing is True  # type: ignore[attr-defined]
        assert widget._refresh_spinner_suspended_for_transition is True  # type: ignore[attr-defined]
        assert not widget._refresh_spin_timer.isActive()  # type: ignore[attr-defined]
        assert updates
    finally:
        widget.cleanup()
        container.deleteLater()
        parent.deleteLater()


@pytest.mark.qt
def test_reddit_deferred_refresh_timer_is_cleared_on_cleanup(qt_app, qtbot):  # noqa: ARG001
    """Deferred Reddit refresh timer should not survive cleanup."""
    widget = RedditWidget()
    qtbot.addWidget(widget)
    widget._schedule_deferred_refresh()  # type: ignore[attr-defined]

    assert widget._deferred_refresh_timer is not None  # type: ignore[attr-defined]
    assert widget._deferred_refresh_timer.isActive() is True  # type: ignore[attr-defined]

    widget.cleanup()

    assert widget._deferred_refresh_timer is None  # type: ignore[attr-defined]


@pytest.mark.qt
def test_reddit_cache_regeneration_defers_during_transition(qt_app, qtbot):  # noqa: ARG001
    """Reddit should keep blitting an old cache instead of regenerating during transitions."""
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QWidget
    from widgets.reddit_components import RedditPost

    class TransitionParent(QWidget):
        def has_running_transition(self):
            return True

    parent = TransitionParent()
    widget = RedditWidget(parent)
    qtbot.addWidget(parent)
    qtbot.addWidget(widget)
    calls = []
    try:
        widget.resize(300, 180)
        widget._posts = [  # type: ignore[attr-defined]
            RedditPost(
                title="Cached",
                url="https://example.com/cached",
                score=1,
                created_utc=time.time(),
            )
        ]
        widget._cached_content_pixmap = QPixmap(widget.size())  # type: ignore[attr-defined]
        widget._cached_content_pixmap.fill()  # type: ignore[attr-defined]
        widget._cache_invalidated = True  # type: ignore[attr-defined]
        widget._regenerate_cache = lambda size: calls.append(size)  # type: ignore[method-assign]
        widget._paint_refresh_button = lambda painter: None  # type: ignore[method-assign]

        target = QPixmap(widget.size())
        target.fill()
        widget.render(target)

        assert calls == []
        assert widget._cache_invalidated is True  # type: ignore[attr-defined]
    finally:
        widget.cleanup()
        parent.deleteLater()
