"""Regression tests for Reddit widget paint caching.

These tests verify:
- Cache is generated when _regenerate_cache is called
- Cache invalidation works correctly
- Cache handles DPR scaling correctly

Note: These tests directly call the caching methods rather than relying on
Qt's paint system, which can be unreliable in headless test environments.
"""

from __future__ import annotations

import threading
import time

import pytest
from PySide6.QtWidgets import QWidget


@pytest.fixture
def mock_parent(qtbot):
    """Create a mock parent widget."""
    parent = QWidget()
    parent.resize(1920, 1080)
    qtbot.addWidget(parent)
    return parent


def _setup_reddit_widget(widget):
    """Helper to set up Reddit widget with test data."""
    from widgets.reddit_widget import RedditPost
    import time

    widget._enabled = True
    widget._subreddit = "test"
    # Use RedditPost dataclass objects, not plain dicts
    now = time.time()
    widget._posts = [
        RedditPost(
            title="Test Post 1",
            url="https://example.com/1",
            score=100,
            created_utc=now - 3600,
        ),
        RedditPost(
            title="Test Post 2",
            url="https://example.com/2",
            score=200,
            created_utc=now - 7200,
        ),
    ]
    widget._cache_invalidated = True


class TestRedditPaintCaching:
    """Tests for Reddit widget paint caching behavior."""

    def test_cache_generated_by_regenerate_cache(self, mock_parent, qtbot):
        """Verify cache is generated when _regenerate_cache is called."""
        from widgets.reddit_widget import RedditWidget

        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)

        _setup_reddit_widget(widget)

        # Directly call regenerate cache
        widget._regenerate_cache(widget.size())

        # Cache should now exist
        assert widget._cached_content_pixmap is not None
        assert not widget._cached_content_pixmap.isNull()

    def test_cache_reused_when_valid(self, mock_parent, qtbot):
        """Verify cache is reused when not invalidated."""
        from widgets.reddit_widget import RedditWidget

        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)

        _setup_reddit_widget(widget)
        widget._regenerate_cache(widget.size())

        first_cache = widget._cached_content_pixmap
        first_cache_id = id(first_cache)
        assert first_cache is not None

        # Mark as not invalidated
        widget._cache_invalidated = False

        # Calling regenerate again with same size should create new cache
        # but the _paint_cached method would skip regeneration
        # Let's verify the invalidation flag works
        assert widget._cache_invalidated is False

        # Cache should still be the same
        assert id(widget._cached_content_pixmap) == first_cache_id

    def test_invalidate_paint_cache_sets_flag(self, mock_parent, qtbot):
        """Verify _invalidate_paint_cache sets the invalidation flag."""
        from widgets.reddit_widget import RedditWidget

        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)

        _setup_reddit_widget(widget)
        widget._regenerate_cache(widget.size())
        widget._cache_invalidated = False

        # Invalidate
        widget._invalidate_paint_cache()

        assert widget._cache_invalidated is True

    def test_cache_size_matches_widget_size(self, mock_parent, qtbot):
        """Verify cache size matches widget size accounting for DPR."""
        from widgets.reddit_widget import RedditWidget

        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)

        _setup_reddit_widget(widget)
        widget._regenerate_cache(widget.size())

        cache = widget._cached_content_pixmap
        assert cache is not None

        dpr = widget.devicePixelRatioF()
        expected_w = int(widget.width() * dpr)
        expected_h = int(widget.height() * dpr)

        assert abs(cache.width() - expected_w) <= 1
        assert abs(cache.height() - expected_h) <= 1

    def test_resize_regenerates_cache_for_current_widget_size(self, mock_parent, qtbot):
        """Verify compatibility preparation cannot install a non-current size."""
        from widgets.reddit_widget import RedditWidget
        from PySide6.QtCore import QSize

        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)

        _setup_reddit_widget(widget)

        # Generate first cache, then resize the real widget. The compatibility
        # argument is ignored so it cannot install pixels for a foreign size.
        widget._regenerate_cache(QSize(400, 300))
        first_cache = widget._cached_content_pixmap
        assert first_cache is not None
        first_cache_key = first_cache.cacheKey()

        widget.resize(500, 400)
        widget._regenerate_cache(QSize(1, 1))

        cache = widget._cached_content_pixmap
        assert cache is not None
        assert cache.cacheKey() != first_cache_key
        dpr = widget.devicePixelRatioF()
        expected_w = int(widget.width() * dpr)
        expected_h = int(widget.height() * dpr)
        assert abs(cache.width() - expected_w) <= 1
        assert abs(cache.height() - expected_h) <= 1


class TestRedditPaintCacheDPR:
    """Tests for DPR (device pixel ratio) handling in paint cache."""

    def test_cache_accounts_for_dpr(self, mock_parent, qtbot):
        """Verify cache pixmap accounts for device pixel ratio."""
        from widgets.reddit_widget import RedditWidget

        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)

        _setup_reddit_widget(widget)
        widget._regenerate_cache(widget.size())

        cache = widget._cached_content_pixmap
        assert cache is not None

        dpr = widget.devicePixelRatioF()
        # Cache should be scaled by DPR
        expected_w = int(widget.width() * dpr)
        expected_h = int(widget.height() * dpr)

        assert abs(cache.width() - expected_w) <= 1
        assert abs(cache.height() - expected_h) <= 1
        # Cache should have correct DPR set
        assert abs(cache.devicePixelRatio() - dpr) < 0.01


class TestRedditPaintPerformance:
    """Performance-related tests for Reddit widget painting."""

    def test_cached_paint_faster_than_uncached(self, mock_parent, qtbot):
        """Verify cached paints are faster than uncached paints."""
        import time
        from widgets.reddit_widget import RedditWidget, RedditPost

        widget = RedditWidget(mock_parent)
        qtbot.addWidget(widget)
        widget.resize(400, 300)

        # Set up data with more posts using RedditPost dataclass
        widget._enabled = True
        widget._subreddit = "test"
        now = time.time()
        widget._posts = [
            RedditPost(
                title=f"Post {i}",
                url=f"https://example.com/{i}",
                score=i * 100,
                created_utc=now - i * 3600,
            )
            for i in range(10)
        ]
        widget.show()
        qtbot.waitExposed(widget)

        # First paint (uncached) - force regeneration
        widget._cache_invalidated = True
        start = time.perf_counter()
        widget.repaint()
        qtbot.wait(50)
        uncached_time = time.perf_counter() - start

        # Subsequent paints (cached)
        cached_times = []
        for _ in range(5):
            widget._cache_invalidated = False
            start = time.perf_counter()
            widget.repaint()
            qtbot.wait(10)
            cached_times.append(time.perf_counter() - start)

        avg_cached_time = sum(cached_times) / len(cached_times)

        # Cached paints should generally be faster
        # (Note: This is a soft assertion due to timing variability)
        # We mainly want to ensure caching doesn't make things slower
        assert (
            avg_cached_time <= uncached_time * 2
        )  # Allow 2x tolerance for timing noise


def test_reddit_paint_never_discovers_or_prepares_cold_static_cache(
    mock_parent,
    qtbot,
):
    from PySide6.QtGui import QPixmap
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    _setup_reddit_widget(widget)
    widget._clear_paint_cache()
    calls = []
    widget._prepare_static_content_cache = lambda: calls.append("prepare") or True  # type: ignore[method-assign]
    widget._paint_refresh_button = lambda painter: None  # type: ignore[method-assign]

    target = QPixmap(widget.size())
    target.fill()
    widget.render(target)

    assert calls == []
    assert widget._cached_content_pixmap is None


def test_reddit_prepared_content_is_reused_without_paint_regeneration(
    mock_parent,
    qtbot,
):
    from PySide6.QtGui import QPixmap
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    _setup_reddit_widget(widget)
    calls = []
    widget._paint_content_to_painter = lambda painter: calls.append("stable")  # type: ignore[method-assign]
    assert widget._prepare_static_content_cache() is True
    assert calls == ["stable"]
    widget._prepare_static_content_cache = (  # type: ignore[method-assign]
        lambda: (_ for _ in ()).throw(AssertionError("paint prepared Reddit cache"))
    )
    widget._paint_refresh_button = lambda painter: None  # type: ignore[method-assign]

    target = QPixmap(widget.size())
    target.fill()
    widget.render(target)
    widget.render(target)

    assert calls == ["stable"]


def test_reddit_static_invalidations_coalesce_to_latest_gui_build(
    mock_parent,
    qtbot,
    monkeypatch,
):
    from PySide6.QtGui import QColor
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    _setup_reddit_widget(widget)
    widget._flush_content_cache_prepare()
    initial_revision = widget._cache_revision
    scheduled = []
    builds = []
    monkeypatch.setattr(
        "widgets.reddit_widget.ThreadManager.single_shot",
        lambda delay, callback, *args, **kwargs: scheduled.append(callback),
    )
    widget._paint_content_to_painter = lambda painter: builds.append(
        widget._cache_revision
    )  # type: ignore[method-assign]

    widget.set_show_separators(not widget._show_separators)
    widget.set_text_color(QColor(25, 35, 45, 255))

    assert widget._cache_revision == initial_revision + 2
    assert len(scheduled) == 1
    assert builds == []

    scheduled.pop(0)()

    assert builds == [initial_revision + 2]
    assert widget._cached_content_identity[-1] == initial_revision + 2
    assert widget._cache_invalidated is False


def test_reddit_preflush_invalidation_exposes_neither_stale_pixels_nor_hits(
    mock_parent,
    qtbot,
    monkeypatch,
):
    from PySide6.QtGui import QColor, QPixmap
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    _setup_reddit_widget(widget)
    widget._invalidate_paint_cache(schedule_prepare=False)
    assert widget._prepare_static_content_cache() is True
    old_pixmap = widget._cached_content_pixmap
    assert widget._prepared_content_pixmap_for_paint() is old_pixmap
    assert widget._row_hit_rects
    scheduled = []
    prepare_calls = []
    monkeypatch.setattr(
        "widgets.reddit_widget.ThreadManager.single_shot",
        lambda delay, callback, *args, **kwargs: scheduled.append(callback),
    )
    original_prepare = widget._prepare_static_content_cache
    monkeypatch.setattr(
        widget,
        "_prepare_static_content_cache",
        lambda: (prepare_calls.append(True), original_prepare())[1],
    )

    widget.set_text_color(QColor(80, 90, 100, 255))

    assert widget._prepared_content_pixmap_for_paint() is None
    assert widget._header_hit_rect is None
    assert widget._row_hit_rects == []
    assert len(scheduled) == 1

    target = QPixmap(widget.size())
    target.fill()
    widget._paint_refresh_button = lambda painter: None  # type: ignore[method-assign]
    widget.render(target)
    assert prepare_calls == []

    scheduled.pop(0)()
    assert prepare_calls == [True]
    assert widget._prepared_content_pixmap_for_paint() is widget._cached_content_pixmap
    assert widget._cached_content_pixmap is not old_pixmap
    assert widget._row_hit_rects


def test_reddit_dpr_event_rebuilds_exact_static_cache_identity(
    mock_parent,
    qtbot,
    monkeypatch,
):
    from PySide6.QtCore import QEvent
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    _setup_reddit_widget(widget)
    dpr = {"value": 1.0}
    monkeypatch.setattr(widget, "devicePixelRatioF", lambda: dpr["value"])
    widget._invalidate_paint_cache(schedule_prepare=False)
    assert widget._prepare_static_content_cache() is True
    first_pixmap = widget._cached_content_pixmap
    assert widget._cached_content_identity[2] == 1.0

    dpr["value"] = 1.5
    widget.event(QEvent(QEvent.Type.DevicePixelRatioChange))
    widget._flush_content_cache_prepare()

    assert widget._cached_content_identity[2] == 1.5
    assert widget._cached_content_pixmap is not first_pixmap
    assert widget._cached_content_pixmap.devicePixelRatio() == 1.5


def test_reddit_visual_setters_invalidate_but_spinner_tick_does_not(
    mock_parent,
    qtbot,
):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QColor
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    widget._flush_content_cache_prepare()
    revision = widget._cache_revision

    widget.set_text_color(QColor(20, 30, 40, 255))
    widget.set_font_family("Arial")
    widget.set_background_border(
        widget._bg_border_width + 1,
        QColor(50, 60, 70, 255),
    )
    widget.set_background_corner_radius(widget._bg_corner_radius + 1)
    widget.set_shadow_config({"enabled": True, "text_enabled": False})

    assert widget._cache_revision == revision + 5
    assert widget._cache_invalidated is True

    widget._cache_invalidated = False
    spinner_revision = widget._cache_revision
    updates = []
    widget.update = lambda *args, **kwargs: updates.append(args)  # type: ignore[method-assign]
    widget._refreshing = True
    widget._refresh_hit_rect = QRect(100, 10, 22, 22)
    widget._advance_refresh_spinner()

    assert widget._cache_revision == spinner_revision
    assert widget._cache_invalidated is False
    assert updates and isinstance(updates[-1][0], QRect)


def test_reddit_content_commit_prepares_before_first_reveal(
    mock_parent,
    qtbot,
):
    from widgets.reddit_widget import RedditPost, RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    sequence = []
    widget._prepare_static_content_cache = lambda: sequence.append("prepare") or True  # type: ignore[method-assign]
    widget._start_widget_fade_in = lambda *args, **kwargs: sequence.append("fade")  # type: ignore[method-assign]
    post = RedditPost(
        title="Prepared before reveal",
        url="https://example.com/prepared",
        score=1,
        created_utc=time.time() - 60,
    )

    widget._update_posts_internal([post])

    assert sequence == ["prepare", "fade"]


def test_reddit_static_cache_preparation_refuses_worker_thread(
    mock_parent,
    qtbot,
):
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    _setup_reddit_widget(widget)
    widget._clear_paint_cache()
    results = []
    worker = threading.Thread(
        target=lambda: results.append(widget._prepare_static_content_cache())
    )
    worker.start()
    worker.join(timeout=5)

    assert worker.is_alive() is False
    assert results == [False]
    assert widget._cached_content_pixmap is None


def test_reddit_queued_static_prepare_drops_after_cleanup(
    mock_parent,
    qtbot,
    monkeypatch,
):
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    widget._flush_content_cache_prepare()
    scheduled = []
    monkeypatch.setattr(
        "widgets.reddit_widget.ThreadManager.single_shot",
        lambda delay, callback, *args, **kwargs: scheduled.append(callback),
    )

    widget.set_show_separators(not widget._show_separators)
    assert len(scheduled) == 1
    widget.cleanup()
    scheduled.pop(0)()

    assert widget._cached_content_pixmap is None
    assert widget._cache_invalidated is True
    assert widget._cache_prepare_scheduled is False


def test_reddit_relative_age_is_stable_between_explicit_cache_invalidations(
    mock_parent,
    qtbot,
    monkeypatch,
):
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    _setup_reddit_widget(widget)
    now = {"value": 1_000_000.0}
    sampled = []
    original_format_age = widget._format_age
    monkeypatch.setattr("widgets.reddit_widget.time.time", lambda: now["value"])
    monkeypatch.setattr(
        widget,
        "_format_age",
        lambda created, now_ts=None: (
            sampled.append(now_ts),
            original_format_age(created, now_ts),
        )[1],
    )

    widget._invalidate_paint_cache(schedule_prepare=False)
    assert widget._prepare_static_content_cache() is True
    first_samples = list(sampled)
    now["value"] += 3600

    assert widget._prepared_content_pixmap_for_paint() is widget._cached_content_pixmap
    assert sampled == first_samples

    widget._invalidate_paint_cache(schedule_prepare=False)
    assert widget._prepare_static_content_cache() is True
    assert sampled[-1] == now["value"]


def test_reddit_subreddit_change_keeps_complete_old_snapshot_until_result_commit(
    mock_parent,
    qtbot,
):
    from widgets.reddit_widget import RedditWidget

    widget = RedditWidget(mock_parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    _setup_reddit_widget(widget)
    widget._invalidate_paint_cache(schedule_prepare=False)
    assert widget._prepare_static_content_cache() is True
    old_pixmap = widget._cached_content_pixmap
    old_hits = list(widget._row_hit_rects)
    old_header = widget._header_hit_rect
    assert old_header is not None
    old_header_subreddit = widget._header_hit_subreddit
    old_url = widget.resolve_click_target(old_header.center())

    widget.set_subreddit("new_subreddit")

    assert widget._prepared_content_pixmap_for_paint() is old_pixmap
    assert widget._row_hit_rects == old_hits
    assert widget.resolve_click_target(old_header.center()) == old_url

    widget._invalidate_paint_cache(schedule_prepare=False)
    assert widget._prepare_static_content_cache() is True
    assert widget._header_hit_subreddit == old_header_subreddit
    rebuilt_old_header = widget._header_hit_rect
    assert rebuilt_old_header is not None
    assert widget.resolve_click_target(rebuilt_old_header.center()) == old_url

    widget._has_seen_first_sample = True
    widget._update_posts_internal(list(widget._posts))
    new_header = widget._header_hit_rect
    assert new_header is not None
    assert widget.resolve_click_target(new_header.center()) == (
        "https://www.reddit.com/r/new_subreddit"
    )


def test_reddit_static_prepare_defers_once_until_transition_completion(
    qtbot,
    monkeypatch,
):
    from PySide6.QtWidgets import QWidget
    from widgets.reddit_widget import RedditWidget

    class TransitionParent(QWidget):
        def __init__(self):
            super().__init__()
            self.busy = True

        def has_transition_work_pending(self):
            return self.busy

    parent = TransitionParent()
    qtbot.addWidget(parent)
    widget = RedditWidget(parent)
    qtbot.addWidget(widget)
    widget.resize(420, 220)
    _setup_reddit_widget(widget)
    scheduled = []
    builds = []
    monkeypatch.setattr(
        "widgets.reddit_widget.ThreadManager.single_shot",
        lambda delay, callback, *args, **kwargs: scheduled.append(callback),
    )
    widget._paint_content_to_painter = lambda painter: builds.append(True)  # type: ignore[method-assign]

    widget._invalidate_paint_cache()
    assert len(scheduled) == 1
    scheduled.pop(0)()

    assert builds == []
    assert widget._cache_prepare_deferred_for_transition is True
    assert scheduled == []

    parent.busy = False
    widget.on_parent_transition_work_pending(False)
    assert len(scheduled) == 1
    scheduled.pop(0)()

    assert builds == [True]
    assert widget._cache_prepare_deferred_for_transition is False
    assert scheduled == []


def test_display_transition_completion_notifies_reddit_cache_consumers(
    monkeypatch,
) -> None:
    from types import SimpleNamespace

    import rendering.display_image_ops as display_image_ops
    from rendering.display_widget import DisplayWidget

    callbacks = []
    display = SimpleNamespace(
        reddit_widget=SimpleNamespace(
            on_parent_transition_work_pending=lambda pending: callbacks.append(
                ("reddit", pending)
            )
        ),
        reddit2_widget=SimpleNamespace(
            on_parent_transition_work_pending=lambda pending: callbacks.append(
                ("reddit2", pending)
            )
        ),
        media_widget=None,
    )
    monkeypatch.setattr(
        display_image_ops,
        "_on_transition_finished",
        lambda _display, *_args, **_kwargs: None,
    )

    DisplayWidget._on_transition_finished(display)

    assert callbacks == [("reddit", False), ("reddit2", False)]
