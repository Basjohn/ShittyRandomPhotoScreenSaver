"""Post-placement auto-scale keeps the largest proved fit and real clearance."""
from dataclasses import replace

from rendering.widget_stacking import (
    DisplayStackParticipant, DisplayStackObstacle, build_display_stack_plan,
    build_display_auto_scale_plan,
)


def _card(key, order, width=400, height=300):
    return DisplayStackParticipant(key, "Top Left", 20, 20, width, height, order, 20)


def _assert_clear(plan, cards, scales, width=800, height=400, obstacles=()):
    rects = [(o.x, o.y, o.width, o.height) for o in obstacles]
    for card in cards:
        p = plan.placements[card.key]
        w, h = round(card.width * scales[card.key]), round(card.height * scales[card.key])
        x, y = p.desired_x, p.desired_y
        assert 20 <= x and x + w <= width - 20
        assert 20 <= y and y + h <= height - 20
        for ox, oy, ow, oh in rects:
            assert x + w + 10 <= ox or ox + ow + 10 <= x or y + h + 10 <= oy or oy + oh + 10 <= y
        rects.append((x, y, w, h))


def test_full_size_stacking_is_preferred_without_shrink():
    cards = [_card("weather", 0), _card("gmail", 1)]
    original = build_display_stack_plan(cards, container_width=1200, container_height=700)
    plan, scales = build_display_auto_scale_plan(cards, eligible_keys=("weather", "gmail"),
        container_width=1200, container_height=700)
    assert plan == original
    assert scales == {"weather": 1., "gmail": 1.}


def test_shrink_only_unresolved_card_and_restack_into_freed_space():
    cards = [_card("clock", 0), _card("weather", 1), _card("tiny", 2, 20, 20)]
    plan, scales = build_display_auto_scale_plan(cards, eligible_keys=("weather", "tiny"),
        container_width=800, container_height=400)
    assert plan.all_fit
    assert scales == {"clock": 1., "weather": .87, "tiny": 1.}
    _assert_clear(plan, cards, scales)
    # One percent more no longer fits this display; the accepted scale is not
    # a gratuitous fixed shrink and the new placement uses its freed space.
    assert not build_display_stack_plan([cards[0], replace(cards[1], width=352, height=264), cards[2]],
        container_width=800, container_height=400).all_fit


def test_joint_shrink_when_unresolved_card_alone_cannot_fit():
    cards = [_card("weather", 0, 450), _card("gmail", 1, 450)]
    plan, scales = build_display_auto_scale_plan(cards, eligible_keys=("weather", "gmail"),
        container_width=800, container_height=400)
    assert plan.all_fit
    assert all(.8 <= s < 1. for s in scales.values())
    _assert_clear(plan, cards, scales)
    restored, full = build_display_auto_scale_plan(cards, eligible_keys=scales,
        container_width=1200, container_height=700)
    assert restored.all_fit and set(full.values()) == {1.}


def test_fixed_obstacle_and_ineligible_card_are_never_scaled():
    cards = [_card("weather", 0)]
    obstacles = (DisplayStackObstacle("media_visualizer", 20, 20, 400, 300),)
    plan, scales = build_display_auto_scale_plan(cards, eligible_keys=("weather",), obstacles=obstacles,
        container_width=800, container_height=400)
    assert plan.all_fit and scales["weather"] == .87
    _assert_clear(plan, cards, scales, obstacles=obstacles)
    failed, unchanged = build_display_auto_scale_plan(cards, eligible_keys=(), obstacles=obstacles,
        container_width=800, container_height=400)
    assert not failed.all_fit and unchanged == {"weather": 1.}


def test_infeasible_floor_is_explicit_and_does_not_waste_shrink():
    cards = [_card("weather", 0, 2000)]
    plan, scales = build_display_auto_scale_plan(cards, eligible_keys=("weather",),
        container_width=800, container_height=400)
    assert plan.unresolved == ("weather",)
    assert scales == {"weather": 1.}
