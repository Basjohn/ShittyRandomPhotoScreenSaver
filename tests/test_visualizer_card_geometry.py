from __future__ import annotations

from PySide6.QtCore import QRect

from widgets.spotify_visualizer.card_geometry import (
    DEFAULT_GROWTH,
    resolve_custom_card_size,
    resolve_card_metrics,
    resolve_relative_card_placement,
    should_place_below_media,
)


def test_card_metrics_preserve_mode_owned_growth_contract():
    metrics = resolve_card_metrics(
        "spectrum",
        80,
        {
            **DEFAULT_GROWTH,
            "spectrum": 1.75,
        },
    )
    assert metrics.growth_factor == 1.75
    assert metrics.preferred_height == 140
    assert metrics.force_base_height is False

    curated = resolve_card_metrics(
        "spectrum",
        80,
        {
            **DEFAULT_GROWTH,
            "spectrum": 5.0,
        },
    )
    assert curated.preferred_height == 400


def test_card_metrics_allow_shrinkable_modes_to_return_to_base_height():
    metrics = resolve_card_metrics(
        "oscilloscope",
        80,
        {
            **DEFAULT_GROWTH,
            "oscilloscope": 1.0,
        },
    )
    assert metrics.force_base_height is True
    assert metrics.preferred_height == 80


def test_relative_card_placement_uses_top_anchor_below_contract():
    placement = resolve_relative_card_placement(
        media_rect=QRect(20, 20, 300, 100),
        parent_width=1920,
        parent_height=1080,
        mode_id="spectrum",
        card_height=160,
        position_name="TOP_CENTER",
    )
    assert placement.place_below_media is True
    assert placement.x == 20
    assert placement.y == 140
    assert placement.width == 300
    assert placement.height == 160


def test_relative_card_placement_centers_blob_width_factor():
    placement = resolve_relative_card_placement(
        media_rect=QRect(100, 700, 300, 100),
        parent_width=1920,
        parent_height=1080,
        mode_id="blob",
        card_height=280,
        position_name="BOTTOM_LEFT",
        blob_width=0.5,
    )
    assert placement.place_below_media is False
    assert placement.width == 150
    assert placement.x == 175
    assert placement.y == 400


def test_should_place_below_media_handles_top_center_and_bottom_left():
    assert should_place_below_media("TOP_CENTER") is True
    assert should_place_below_media("BOTTOM_LEFT") is False


def test_resolve_custom_card_size_uses_current_mode_metrics():
    size = resolve_custom_card_size(
        mode_id="spectrum",
        media_width=300,
        base_height=80,
        growth_by_mode=DEFAULT_GROWTH,
        width_scale=1.0,
        height_scale=1.0,
        maximum_envelope=False,
    )
    assert size.width() == 300
    assert size.height() == 160


def test_resolve_custom_card_size_maximum_envelope_uses_largest_mode_metrics():
    size = resolve_custom_card_size(
        mode_id="spectrum",
        media_width=300,
        base_height=80,
        growth_by_mode=DEFAULT_GROWTH,
        width_scale=1.0,
        height_scale=1.0,
        maximum_envelope=True,
    )
    assert size.width() == 300
    assert size.height() == 280


def test_resolve_custom_card_size_scales_blob_width_and_height_contract():
    size = resolve_custom_card_size(
        mode_id="blob",
        media_width=280,
        base_height=80,
        growth_by_mode=DEFAULT_GROWTH,
        blob_width=0.5,
        width_scale=1.5,
        height_scale=1.25,
        maximum_envelope=False,
    )
    assert size.width() == 210
    assert size.height() == 350
