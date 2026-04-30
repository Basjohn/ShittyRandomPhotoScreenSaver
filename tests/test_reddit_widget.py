"""Tests for RedditWidget behaviour and integration points.

These cover filtering, age label formatting, hide-on-error behaviour, and
click handling for posts and the header.
"""

import time

import pytest
from PySide6.QtCore import QPoint, QRect

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
