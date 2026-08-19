"""Prepare-before-paint coverage for the shared overlay frame shadow."""

from __future__ import annotations

import threading

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QWidget

from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition


class _Overlay(BaseOverlayWidget):
    def __init__(self, parent=None):
        super().__init__(parent, OverlayPosition.TOP_LEFT, "frame_cache_test")

    def _update_content(self) -> None:
        return


def _configured_overlay(qtbot) -> _Overlay:
    widget = _Overlay()
    qtbot.addWidget(widget)
    widget.resize(360, 180)
    widget.show()
    return widget


def test_shared_visible_frame_invalidations_commit_before_paint(
    qtbot,
    monkeypatch,
):
    widget = _configured_overlay(qtbot)
    build_keys = []
    original_prepare = widget._prepare_painted_frame_shadow_pixmap

    def _trace_prepare():
        before = widget._painted_frame_shadow_pixmap
        before_key = before.cacheKey() if before is not None else None
        result = original_prepare()
        after_key = result.cacheKey() if result is not None else None
        if after_key is not None and after_key != before_key:
            build_keys.append(after_key)
        return result

    monkeypatch.setattr(
        widget,
        "_prepare_painted_frame_shadow_pixmap",
        _trace_prepare,
    )

    widget.set_show_background(True)
    assert widget._prepared_painted_frame_shadow_pixmap_for_paint() is not None
    widget.set_background_color(QColor(24, 36, 48, 220))
    widget.set_background_opacity(0.72)
    widget.set_background_border(4, QColor(210, 180, 90, 230))
    widget.set_background_corner_radius(14)
    widget.set_shadow_config({"enabled": True})

    assert len(build_keys) == 6
    prepared = widget._prepared_painted_frame_shadow_pixmap_for_paint()
    assert prepared is not None
    monkeypatch.setattr(
        widget,
        "_prepare_painted_frame_shadow_pixmap",
        lambda: (_ for _ in ()).throw(AssertionError("paint built frame shadow")),
    )
    target = QPixmap(widget.size())
    target.fill()
    widget.render(target)

    assert widget._prepared_painted_frame_shadow_pixmap_for_paint() is prepared


def test_shared_frame_known_style_batch_builds_only_final_state(qtbot, monkeypatch):
    widget = _configured_overlay(qtbot)
    widget.set_show_background(True)
    build_keys = []
    original_prepare = widget._prepare_painted_frame_shadow_pixmap

    def _trace_prepare():
        before = widget._painted_frame_shadow_pixmap
        before_key = before.cacheKey() if before is not None else None
        result = original_prepare()
        after_key = result.cacheKey() if result is not None else None
        if after_key is not None and after_key != before_key:
            build_keys.append(after_key)
        return result

    monkeypatch.setattr(widget, "_prepare_painted_frame_shadow_pixmap", _trace_prepare)

    with widget.painted_frame_shadow_update_batch():
        widget.set_background_color(QColor(15, 25, 35, 220))
        widget.set_background_opacity(0.61)
        widget.set_background_border(5, QColor(90, 180, 220, 240))
        widget.set_background_corner_radius(16)
        assert build_keys == []

    assert len(build_keys) == 1
    prepared = widget._prepared_painted_frame_shadow_pixmap_for_paint()
    assert prepared is not None
    key = widget._painted_frame_shadow_cache_key
    assert key[3] == widget._bg_color.getRgb()
    assert key[4] == widget._bg_border_color.getRgb()
    assert key[5] == 5
    assert key[6] == 16


def test_shared_frame_show_prewarm_makes_first_paint_consume_only(
    qtbot,
    monkeypatch,
):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.resize(800, 600)
    widget = _Overlay(parent)
    widget.resize(360, 180)
    widget.set_show_background(True)
    widget.set_shadow_config({"enabled": True})
    calls = []
    original_prepare = widget._prepare_painted_frame_shadow_pixmap
    monkeypatch.setattr(
        widget,
        "_prepare_painted_frame_shadow_pixmap",
        lambda: (calls.append("show"), original_prepare())[1],
    )

    parent.show()

    assert calls == ["show"]
    prepared = widget._prepared_painted_frame_shadow_pixmap_for_paint()
    assert prepared is not None

    monkeypatch.setattr(
        widget,
        "_prepare_painted_frame_shadow_pixmap",
        lambda: (_ for _ in ()).throw(AssertionError("paint built frame shadow")),
    )
    target = QPixmap(widget.size())
    target.fill()
    widget.render(target)

    assert widget._prepared_painted_frame_shadow_pixmap_for_paint() is prepared


@pytest.mark.parametrize("width_delta", [0, 2])
def test_shared_frame_border_change_commits_one_exact_cache(
    width_delta,
    qtbot,
    monkeypatch,
):
    widget = _configured_overlay(qtbot)
    widget.set_show_background(True)
    old_pixmap = widget._painted_frame_shadow_pixmap
    old_key = widget._painted_frame_shadow_cache_key
    assert old_pixmap is not None
    build_keys = []
    original_prepare = widget._prepare_painted_frame_shadow_pixmap

    def _trace_prepare():
        before = widget._painted_frame_shadow_pixmap
        before_key = before.cacheKey() if before is not None else None
        result = original_prepare()
        after_key = result.cacheKey() if result is not None else None
        if after_key is not None and after_key != before_key:
            build_keys.append(after_key)
        return result

    monkeypatch.setattr(
        widget,
        "_prepare_painted_frame_shadow_pixmap",
        _trace_prepare,
    )

    widget.set_background_border(
        widget._bg_border_width + width_delta,
        QColor(12, 210, 120, 240),
    )

    assert len(build_keys) == 1
    assert widget._prepared_painted_frame_shadow_pixmap_for_paint() is not None
    assert widget._painted_frame_shadow_pixmap is not old_pixmap
    assert widget._painted_frame_shadow_cache_key != old_key
    assert widget._painted_frame_shadow_cache_key[4] == (12, 210, 120, 240)


def test_shared_frame_dpr_change_commits_before_returning_to_paint(
    qtbot,
    monkeypatch,
):
    widget = _configured_overlay(qtbot)
    dpr = {"value": 1.0}
    monkeypatch.setattr(widget, "devicePixelRatioF", lambda: dpr["value"])
    widget.set_show_background(True)
    old_pixmap = widget._painted_frame_shadow_pixmap
    assert old_pixmap is not None
    assert old_pixmap.devicePixelRatio() == 1.0

    dpr["value"] = 1.5
    widget.event(QEvent(QEvent.Type.DevicePixelRatioChange))

    prepared = widget._prepared_painted_frame_shadow_pixmap_for_paint()
    assert prepared is not None
    assert prepared is not old_pixmap
    assert prepared.devicePixelRatio() == 1.5
    assert widget._painted_frame_shadow_cache_key[2] == 1.5


def test_shared_frame_prepare_rejects_worker_thread(qtbot):
    widget = _configured_overlay(qtbot)
    widget.set_show_background(True)
    prepared = widget._painted_frame_shadow_pixmap
    prepared_key = widget._painted_frame_shadow_cache_key
    results = []
    worker = threading.Thread(
        target=lambda: results.append(widget._prepare_painted_frame_shadow_pixmap())
    )
    worker.start()
    worker.join(timeout=5)

    assert worker.is_alive() is False
    assert results == [None]
    assert widget._painted_frame_shadow_pixmap is prepared
    assert widget._painted_frame_shadow_cache_key == prepared_key


def test_shared_frame_cleanup_cancels_and_clears(qtbot):
    widget = _configured_overlay(qtbot)
    widget.set_show_background(True)
    assert widget._painted_frame_shadow_pixmap is not None

    widget.cleanup()

    assert widget._painted_frame_shadow_pixmap is None
    assert widget._painted_frame_shadow_cache_key is None
    assert widget._painted_frame_shadow_cache_cancelled is True


def test_clock_analogue_and_imgur_custom_painters_do_not_build_base_frame(qtbot):
    from widgets.clock_widget import ClockWidget
    from widgets.imgur.widget import ImgurWidget

    clock = ClockWidget()
    qtbot.addWidget(clock)
    clock.resize(360, 180)
    clock.set_display_mode("analog")
    clock.set_show_background(True)
    assert clock.uses_painted_frame_shadow() is True
    assert clock.uses_shared_painted_frame_shadow_cache() is False
    assert clock._ensure_painted_frame_shadow_pixmap() is None

    clock.set_display_mode("digital")
    assert clock.uses_shared_painted_frame_shadow_cache() is True
    assert clock._ensure_painted_frame_shadow_pixmap() is not None

    imgur = ImgurWidget()
    qtbot.addWidget(imgur)
    imgur.resize(360, 180)
    imgur.set_show_background(True)
    assert imgur.uses_painted_frame_shadow() is True
    assert imgur.uses_shared_painted_frame_shadow_cache() is False
    assert imgur._ensure_painted_frame_shadow_pixmap() is None


@pytest.mark.parametrize("family", ["gmail", "reddit", "weather", "clock"])
def test_representative_base_widget_families_blit_shared_prepared_frame(
    family,
    qtbot,
    monkeypatch,
):
    if family == "gmail":
        from widgets.gmail_widget import GmailWidget

        widget = GmailWidget()
    elif family == "reddit":
        from widgets.reddit_widget import RedditWidget

        widget = RedditWidget()
    elif family == "weather":
        from widgets.weather_widget import WeatherWidget

        widget = WeatherWidget()
    else:
        from widgets.clock_widget import ClockWidget

        widget = ClockWidget()

    qtbot.addWidget(widget)
    widget.resize(360, 180)
    widget.set_show_background(True)
    widget.set_shadow_config({"enabled": True})
    widget.show()
    qtbot.wait(10)
    prepared = widget._ensure_painted_frame_shadow_pixmap()
    assert prepared is not None
    assert widget._prepared_painted_frame_shadow_pixmap_for_paint() is prepared

    monkeypatch.setattr(
        widget,
        "_prepare_painted_frame_shadow_pixmap",
        lambda: (_ for _ in ()).throw(AssertionError(f"{family} paint built frame shadow")),
    )
    target = QPixmap(widget.size())
    target.fill()
    widget.render(target)

    assert widget._prepared_painted_frame_shadow_pixmap_for_paint() is prepared


# ---------------------------------------------------------------------------
# P2-PERF-B: an unchanged style must not rebuild the painted frame shadow
# ---------------------------------------------------------------------------


class TestUnchangedStyleDoesNotRebuild:
    """Frame-shadow regeneration was measured at 8-20+ ms of synchronous GUI work.

    ``set_background_border()`` already returned early on an unchanged value;
    ``set_show_background()``, ``set_background_color()``,
    ``set_background_opacity()`` and ``set_background_corner_radius()`` did not,
    so every settings refresh, widget setup and runtime reconstruction paid a
    full rebuild per call even when the resolved style was identical.
    """

    def _widget(self, qtbot):
        from PySide6.QtGui import QColor

        from widgets.base_overlay_widget import BaseOverlayWidget

        widget = BaseOverlayWidget()
        qtbot.addWidget(widget)
        widget.set_show_background(True)
        widget.set_background_color(QColor(10, 20, 30, 200))
        widget.set_background_opacity(0.8)
        widget.set_background_corner_radius(12)
        return widget

    def _revision(self, widget):
        return int(widget._painted_frame_shadow_revision)

    def test_reapplying_the_same_show_background_is_a_no_op(self, qtbot):
        widget = self._widget(qtbot)
        before = self._revision(widget)
        widget.set_show_background(True)
        assert self._revision(widget) == before

    def test_reapplying_the_same_colour_is_a_no_op(self, qtbot):
        from PySide6.QtGui import QColor

        widget = self._widget(qtbot)
        before = self._revision(widget)
        widget.set_background_color(QColor(widget._bg_color))
        assert self._revision(widget) == before

    def test_reapplying_the_same_opacity_is_a_no_op(self, qtbot):
        widget = self._widget(qtbot)
        before = self._revision(widget)
        widget.set_background_opacity(0.8)
        assert self._revision(widget) == before

    def test_reapplying_the_same_corner_radius_is_a_no_op(self, qtbot):
        widget = self._widget(qtbot)
        before = self._revision(widget)
        widget.set_background_corner_radius(12)
        assert self._revision(widget) == before

    def test_a_repeated_full_style_apply_costs_nothing(self, qtbot):
        """The settings-refresh / reconstruction shape."""
        from PySide6.QtGui import QColor

        widget = self._widget(qtbot)
        before = self._revision(widget)
        for _ in range(5):
            widget.set_show_background(True)
            widget.set_background_color(QColor(widget._bg_color))
            widget.set_background_opacity(0.8)
            widget.set_background_corner_radius(12)
        assert self._revision(widget) == before, (
            "a repeated identical style apply rebuilt the frame shadow"
        )

    def test_a_genuine_change_still_rebuilds(self, qtbot):
        from PySide6.QtGui import QColor

        widget = self._widget(qtbot)

        before = self._revision(widget)
        widget.set_background_corner_radius(18)
        assert self._revision(widget) > before

        before = self._revision(widget)
        widget.set_background_color(QColor(200, 30, 40, 255))
        assert self._revision(widget) > before

        before = self._revision(widget)
        widget.set_background_opacity(0.35)
        assert self._revision(widget) > before

        before = self._revision(widget)
        widget.set_show_background(False)
        assert self._revision(widget) > before

    def test_an_opacity_change_still_updates_the_colour_alpha(self, qtbot):
        widget = self._widget(qtbot)
        widget.set_background_opacity(0.5)
        assert widget._bg_opacity == 0.5
        assert widget._bg_color.alpha() == int(255 * 0.5)

    def test_a_clamped_repeat_is_still_a_no_op(self, qtbot):
        widget = self._widget(qtbot)
        widget.set_background_opacity(1.0)
        before = self._revision(widget)
        widget.set_background_opacity(4.0)  # clamps to the same 1.0
        assert self._revision(widget) == before


# ---------------------------------------------------------------------------
# Pre-reveal preparation (Current_Plan section 7, candidate 2)
#
# The 2026-08-19 / 4.7.2 acceptance recorded, on the settings-close full
# restart, seven overlays each rebuilding their painted frame in the same
# reveal window:
#
#   weather 8.88ms  gmail 8.46ms  reddit2 12.08ms  reddit 16.25ms
#   media 6.45ms x3  achievement_pulse 7.99ms x2  abandonment_issues 8.62ms x2
#
# `_commit_painted_frame_shadow_cache()` returns early while a widget is hidden,
# so `showEvent` is the only builder during reconstruction - and the reveal
# starter is what calls `show()`. These bars hold the boundary: a hidden widget
# whose geometry and style are final can be prepared, and a prepared widget must
# reveal without building anything.
# ---------------------------------------------------------------------------


def _hidden_configured_overlay(qtbot) -> _Overlay:
    """A widget in the exact state a reveal starter finds it in."""
    widget = _Overlay()
    qtbot.addWidget(widget)
    widget.resize(360, 180)
    widget.set_show_background(True)
    widget.set_background_color(QColor(24, 36, 48, 220))
    widget.set_background_corner_radius(14)
    return widget


def test_a_hidden_widget_coalesces_instead_of_building():
    """The premise: hidden style changes must not build eagerly."""
    widget = _Overlay()
    widget.resize(360, 180)
    widget.set_show_background(True)
    widget.set_background_color(QColor(10, 20, 30, 200))
    assert widget.isVisible() is False
    assert widget._painted_frame_shadow_pixmap is None


def test_a_hidden_widget_can_be_prepared_before_reveal(qtbot):
    widget = _hidden_configured_overlay(qtbot)
    assert widget._painted_frame_shadow_pixmap is None

    prepared = widget._prepare_painted_frame_shadow_pixmap()

    assert prepared is not None and not prepared.isNull(), (
        "a hidden widget with final geometry/style must be preparable"
    )
    assert widget._prepared_painted_frame_shadow_pixmap_for_paint() is prepared


def test_a_prepared_widget_reveals_without_building(qtbot, monkeypatch):
    """The actual saving: showEvent must find a cache hit."""
    widget = _hidden_configured_overlay(qtbot)
    prepared = widget._prepare_painted_frame_shadow_pixmap()
    assert prepared is not None

    builds = []
    original = widget._prepare_painted_frame_shadow_pixmap

    def _count_builds():
        before = widget._painted_frame_shadow_pixmap
        before_key = before.cacheKey() if before is not None else None
        result = original()
        after_key = result.cacheKey() if result is not None else None
        if after_key is not None and after_key != before_key:
            builds.append(after_key)
        return result

    monkeypatch.setattr(widget, "_prepare_painted_frame_shadow_pixmap", _count_builds)

    widget.show()
    qtbot.waitExposed(widget)

    assert builds == [], "the reveal rebuilt a frame that was already prepared"
    assert widget._prepared_painted_frame_shadow_pixmap_for_paint() is prepared


def test_an_unprepared_widget_still_builds_at_reveal(qtbot):
    """The negative control: without pre-reveal work the cost lands at show."""
    widget = _hidden_configured_overlay(qtbot)
    assert widget._painted_frame_shadow_pixmap is None

    widget.show()
    qtbot.waitExposed(widget)

    assert widget._painted_frame_shadow_pixmap is not None, (
        "showEvent remains the fallback builder"
    )


def test_pre_reveal_preparation_preserves_pixels(qtbot):
    """Same cache key in, same authored frame out."""
    early = _hidden_configured_overlay(qtbot)
    early_pixmap = early._prepare_painted_frame_shadow_pixmap()
    early.show()
    qtbot.waitExposed(early)

    late = _hidden_configured_overlay(qtbot)
    late.show()
    qtbot.waitExposed(late)
    late_pixmap = late._painted_frame_shadow_pixmap

    assert early_pixmap is not None and late_pixmap is not None
    # Everything the raster depends on - size, DPR, colours, border, radius and
    # tuning - must match. The trailing element is the invalidation counter,
    # which is bookkeeping rather than an input to a single pixel.
    assert (
        early._painted_frame_shadow_cache_key[:-1]
        == late._painted_frame_shadow_cache_key[:-1]
    )
    assert early_pixmap.toImage() == late_pixmap.toImage(), (
        "preparing earlier changed the authored frame"
    )


def test_a_geometry_change_after_preparation_still_rebuilds(qtbot):
    """Preparation is a cache, never a freeze."""
    widget = _hidden_configured_overlay(qtbot)
    first = widget._prepare_painted_frame_shadow_pixmap()
    assert first is not None

    widget.resize(420, 240)
    widget.show()
    qtbot.waitExposed(widget)

    assert widget._prepared_painted_frame_shadow_pixmap_for_paint() is not None
    assert widget._painted_frame_shadow_pixmap is not first, (
        "a stale frame survived a real geometry change"
    )


def test_preparing_twice_builds_once(qtbot):
    """Identical input is a no-op, per the runtime-efficiency guardrail."""
    widget = _hidden_configured_overlay(qtbot)
    first = widget._prepare_painted_frame_shadow_pixmap()
    second = widget._prepare_painted_frame_shadow_pixmap()
    assert first is second
