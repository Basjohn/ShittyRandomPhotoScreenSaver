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
