"""Ordinary-widget outer-geometry resolver bars (H).

These prove the presentation-neutral anchor+margin+clamp resolver reproduces the
stable committed placement of the legacy ``_update_position`` path for every
anchor, honours the persisted ``position`` token spelling, and clamps to keep a
widget reachable on the display.
"""

from __future__ import annotations

import pytest

from rendering.quick.widgets.geometry_resolver import (
    MIN_VISIBLE_PX,
    OverlayAnchor,
    resolve_anchored_geometry,
)
from rendering.quick.widgets.host import OverlayWidgetGeometry


def _reference_xy(anchor: OverlayAnchor, w, h, W, H, m):
    """Independent reference of the legacy anchor formula (zero offsets)."""

    if anchor in (
        OverlayAnchor.TOP_LEFT,
        OverlayAnchor.MIDDLE_LEFT,
        OverlayAnchor.BOTTOM_LEFT,
    ):
        x = m
    elif anchor in (
        OverlayAnchor.TOP_RIGHT,
        OverlayAnchor.MIDDLE_RIGHT,
        OverlayAnchor.BOTTOM_RIGHT,
    ):
        x = W - w - m
    else:
        x = (W - w) / 2.0

    if anchor in (
        OverlayAnchor.TOP_LEFT,
        OverlayAnchor.TOP_CENTER,
        OverlayAnchor.TOP_RIGHT,
    ):
        y = m
    elif anchor in (
        OverlayAnchor.BOTTOM_LEFT,
        OverlayAnchor.BOTTOM_CENTER,
        OverlayAnchor.BOTTOM_RIGHT,
    ):
        y = H - h - m
    else:
        y = (H - h) / 2.0

    max_x, max_y = W - MIN_VISIBLE_PX, H - MIN_VISIBLE_PX
    min_x, min_y = MIN_VISIBLE_PX - w, MIN_VISIBLE_PX - h
    return max(min_x, min(x, max_x)), max(min_y, min(y, max_y))


@pytest.mark.parametrize("anchor", list(OverlayAnchor))
def test_anchor_math_matches_legacy_reference_for_every_anchor(anchor) -> None:
    bounds = OverlayWidgetGeometry(0.0, 0.0, 1920.0, 1080.0)
    content = (300.0, 160.0)
    margin = 30.0
    geometry = resolve_anchored_geometry(
        content_size=content,
        anchor=anchor,
        margin=margin,
        display_bounds=bounds,
    )
    ref_x, ref_y = _reference_xy(anchor, 300.0, 160.0, 1920.0, 1080.0, 30.0)
    assert geometry.x == pytest.approx(ref_x)
    assert geometry.y == pytest.approx(ref_y)
    # The resolved rectangle keeps the content size exactly.
    assert geometry.width == pytest.approx(300.0)
    assert geometry.height == pytest.approx(160.0)


def test_top_right_default_places_against_top_right_margin() -> None:
    bounds = OverlayWidgetGeometry(0.0, 0.0, 1000.0, 800.0)
    geometry = resolve_anchored_geometry(
        content_size=(200.0, 100.0),
        anchor="Top Right",
        margin=30.0,
        display_bounds=bounds,
    )
    assert geometry.x == pytest.approx(1000.0 - 200.0 - 30.0)
    assert geometry.y == pytest.approx(30.0)


def test_position_token_spellings_and_fallback() -> None:
    assert OverlayAnchor.from_setting("Top Right") is OverlayAnchor.TOP_RIGHT
    assert OverlayAnchor.from_setting("bottom_center") is OverlayAnchor.BOTTOM_CENTER
    assert OverlayAnchor.from_setting("  Middle Left  ") is OverlayAnchor.MIDDLE_LEFT
    assert OverlayAnchor.from_setting("Center") is OverlayAnchor.CENTER
    # Unknown / empty resolve to TOP_RIGHT, matching the legacy fallback.
    assert OverlayAnchor.from_setting("nonsense") is OverlayAnchor.TOP_RIGHT
    assert OverlayAnchor.from_setting("") is OverlayAnchor.TOP_RIGHT
    assert OverlayAnchor.from_setting(None) is OverlayAnchor.TOP_RIGHT


def test_center_anchor_centers_content() -> None:
    bounds = OverlayWidgetGeometry(0.0, 0.0, 1000.0, 600.0)
    geometry = resolve_anchored_geometry(
        content_size=(400.0, 200.0),
        anchor=OverlayAnchor.CENTER,
        margin=30.0,
        display_bounds=bounds,
    )
    assert geometry.x == pytest.approx((1000.0 - 400.0) / 2.0)
    assert geometry.y == pytest.approx((600.0 - 200.0) / 2.0)


def test_oversize_margin_clamps_to_keep_widget_reachable() -> None:
    bounds = OverlayWidgetGeometry(0.0, 0.0, 400.0, 300.0)
    # A margin larger than the display would push a left/top-anchored widget off
    # the right/bottom edge; the clamp keeps MIN_VISIBLE_PX reachable instead.
    geometry = resolve_anchored_geometry(
        content_size=(120.0, 80.0),
        anchor=OverlayAnchor.TOP_LEFT,
        margin=500.0,
        display_bounds=bounds,
    )
    assert geometry.x == pytest.approx(400.0 - MIN_VISIBLE_PX)
    assert geometry.y == pytest.approx(300.0 - MIN_VISIBLE_PX)


def test_content_larger_than_display_stays_within_clamp_range() -> None:
    bounds = OverlayWidgetGeometry(0.0, 0.0, 400.0, 300.0)
    # A card larger than the display, anchored bottom-right: the raw anchor
    # position is already within the clamp range, so it is used as-is and the
    # widget's near edge stays reachable on the display.
    geometry = resolve_anchored_geometry(
        content_size=(600.0, 500.0),
        anchor=OverlayAnchor.BOTTOM_RIGHT,
        margin=30.0,
        display_bounds=bounds,
    )
    assert geometry.x == pytest.approx(400.0 - 600.0 - 30.0)
    assert geometry.y == pytest.approx(300.0 - 500.0 - 30.0)
    # Reachability invariant: part of the widget remains on the display.
    assert geometry.x + geometry.width >= MIN_VISIBLE_PX
    assert geometry.y + geometry.height >= MIN_VISIBLE_PX


def test_display_origin_offsets_result() -> None:
    # A non-origin display bounds (e.g. a second monitor's host rect) shifts the
    # anchored result by the display origin.
    bounds = OverlayWidgetGeometry(1920.0, 0.0, 1000.0, 800.0)
    geometry = resolve_anchored_geometry(
        content_size=(200.0, 100.0),
        anchor=OverlayAnchor.TOP_LEFT,
        margin=25.0,
        display_bounds=bounds,
    )
    assert geometry.x == pytest.approx(1920.0 + 25.0)
    assert geometry.y == pytest.approx(25.0)


def test_zero_or_negative_content_size_is_rejected() -> None:
    bounds = OverlayWidgetGeometry(0.0, 0.0, 1000.0, 800.0)
    with pytest.raises(ValueError):
        resolve_anchored_geometry(
            content_size=(0.0, 100.0),
            anchor=OverlayAnchor.TOP_RIGHT,
            margin=30.0,
            display_bounds=bounds,
        )
