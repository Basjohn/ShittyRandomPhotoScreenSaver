"""Retained visualizer double-click mode-cycle admission bars (H Finding E)."""

from __future__ import annotations

from rendering.quick.visualizer.double_click_admission import (
    QuickVisualizerDoubleClickAdmission,
    compose_semantic_double_click_hit_tests,
    next_visualizer_mode_id,
)
from core.settings.visualizer_mode_registry import (
    get_default_visualizer_mode_id,
    iter_visualizer_mode_descriptors,
)


def test_next_mode_matches_registry_cycle_order() -> None:
    ids = [desc.mode_id for desc in iter_visualizer_mode_descriptors()]
    assert len(ids) >= 2
    for idx, mode_id in enumerate(ids):
        assert next_visualizer_mode_id(mode_id) == ids[(idx + 1) % len(ids)]
    # The unknown-id path normalizes through the canonical default before
    # advancing, so it must remain derived from registry order.
    assert next_visualizer_mode_id(ids[-1]) == ids[0]
    default_index = ids.index(get_default_visualizer_mode_id())
    expected_unknown = ids[(default_index + 1) % len(ids)]
    assert next_visualizer_mode_id("not_a_mode") == expected_unknown


def test_double_click_inside_region_cycles_and_consumes() -> None:
    cycled = []
    admission = QuickVisualizerDoubleClickAdmission(
        region_contains=lambda pos: pos == "inside",
        is_active=lambda: True,
        cycle_mode=lambda: cycled.append(True),
    )
    assert admission.handles_semantic_double_click_at("inside") is True
    assert cycled == [True]


def test_double_click_outside_region_declines_no_cycle() -> None:
    cycled = []
    admission = QuickVisualizerDoubleClickAdmission(
        region_contains=lambda pos: pos == "inside",
        is_active=lambda: True,
        cycle_mode=lambda: cycled.append(True),
    )
    assert admission.handles_semantic_double_click_at("outside") is False
    assert cycled == []


def test_inactive_visualizer_declines_even_inside_region() -> None:
    cycled = []
    admission = QuickVisualizerDoubleClickAdmission(
        region_contains=lambda pos: True,
        is_active=lambda: False,
        cycle_mode=lambda: cycled.append(True),
    )
    assert admission.handles_semantic_double_click_at("inside") is False
    assert cycled == []


def test_composition_orders_ordinary_before_visualizer_before_fallback() -> None:
    calls = []

    def ordinary(pos):
        calls.append("ordinary")
        return pos == "clock"

    cycled = []
    admission = QuickVisualizerDoubleClickAdmission(
        region_contains=lambda pos: pos == "visualizer",
        is_active=lambda: True,
        cycle_mode=lambda: cycled.append(True),
    )
    composed = compose_semantic_double_click_hit_tests(
        ordinary, admission.handles_semantic_double_click_at
    )

    # Family region wins first refusal; visualizer not consulted for its own action.
    assert composed("clock") is True
    assert cycled == []
    # Visualizer region: ordinary declines, visualizer consumes + cycles.
    assert composed("visualizer") is True
    assert cycled == [True]
    # Neither: unhandled -> falls through to the global next-image fallback.
    assert composed("elsewhere") is False
    assert cycled == [True]
