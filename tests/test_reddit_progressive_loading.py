"""Tests for the retired Reddit progressive-growth seam.

Reddit now fetches/caches a max candidate window and immediately renders the
configured visible count. This file exists so the old staged-growth concept does
not quietly creep back in.
"""
from __future__ import annotations

from pathlib import Path

from core.settings.widget_capacity_policy import (
    LIST_WIDGET_MAX_CAPACITY,
    LIST_WIDGET_MIN_CAPACITY,
    clamp_list_capacity,
)


def test_list_capacity_policy_has_no_progressive_stage_builder():
    source = Path("core/settings/widget_capacity_policy.py").read_text(encoding="utf-8")

    assert "build_progressive_capacity_stages" not in source
    assert "STAGE_MID" not in source


def test_reddit_runtime_fetches_candidate_window_not_visible_limit():
    source = Path("widgets/reddit_widget.py").read_text(encoding="utf-8")

    assert "fetch_limit = LIST_WIDGET_MAX_CAPACITY" in source
    assert "_display_configured_posts" in source
    assert "_start_growth_timer" not in source
    assert "_progressive_stage" not in source


def test_capacity_clamp_preserves_visible_range_and_candidate_ceiling():
    assert clamp_list_capacity(1) == LIST_WIDGET_MIN_CAPACITY
    assert clamp_list_capacity(10) == 10
    assert clamp_list_capacity(99) == LIST_WIDGET_MAX_CAPACITY


def test_reddit_settings_spinboxes_use_shared_capacity_range():
    source = Path("ui/tabs/widgets_tab_reddit.py").read_text(encoding="utf-8")

    assert "tab.reddit_items.setRange(LIST_WIDGET_MIN_CAPACITY, LIST_WIDGET_MAX_CAPACITY)" in source
    assert "tab.reddit2_items.setRange(LIST_WIDGET_MIN_CAPACITY, LIST_WIDGET_MAX_CAPACITY)" in source


def test_reddit_settings_are_bucketed_by_instance():
    source = Path("ui/tabs/widgets_tab_reddit.py").read_text(encoding="utf-8")

    assert '"Reddit 1"' in source
    assert '"Reddit 2"' in source
    assert '"Link Behavior"' in source
    assert '"Shared Layout & Typography"' in source
    assert '"Shared Appearance"' in source
