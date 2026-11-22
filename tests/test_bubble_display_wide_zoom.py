"""The display-wide Bubble card zooms out from the card's capacity zoom (operator, 22 Nov: fullscreen bubbles were
too large for the screen and breathed less than the card's; candidate C: smaller heroes, more of them, room to
breathe), while the card itself keeps its world exactly.

Driven through the production owner on an unshown runtime (``tools/expanded_visualizer_evidence.owner_replay``), on a
recorded fixture, with test-owned settings (the frozen Bubble copy), at the card and display-wide. Expectations come
from the world owner (``bubble_viewport_profile``), never from preset or default values. No window is shown.
"""
from __future__ import annotations

import statistics

import pytest

# A thin CUSTOM card, as the operator's: display-wide, its world grows several times on the display's short axis.
_EXTENT = (1200.0, 144.0)
_COMMITTED = ((40.0, 40.0, _EXTENT[0], _EXTENT[1]), _EXTENT)
_WARMUP_FRAMES = 40


@pytest.fixture(scope="module")
def looped_clip():
    from tools.expanded_visualizer_evidence import looped_fixture

    return looped_fixture(loops=6)


def _settings():
    from tests._visualizer_frozen_settings import frozen_visualizer_settings

    return frozen_visualizer_settings("bubble")


def _replay(clip, **kwargs):
    from tools.expanded_visualizer_evidence import owner_replay

    return owner_replay(clip, "bubble", settings=_settings(), committed=_COMMITTED, keep_frames=True, **kwargs)


def _population():
    settings = _settings()
    return int(settings["bubble_big_count"]) + int(settings["bubble_small_count"])


def _breathing(frames):
    """Median displayed radius over nominal radius of the big heroes (the payload radius against the simulation's
    own nominal one, ``geometry_diagnostics``' tracked big hero), per frame after the warm-up."""
    ratios = []
    for frame in frames[_WARMUP_FRAMES:]:
        diagnostics = dict(frame.mode_state.geometry_diagnostics)
        base = diagnostics.get("tracked_big_base_radius", 0.0)
        if base > 0.0:
            ratios.append(diagnostics["tracked_big_display_radius"] / base)
    assert len(ratios) > 50, len(ratios)
    return statistics.median(ratios)


@pytest.mark.qt
def test_display_wide_zooms_out_with_more_heroes_while_the_card_keeps_its_world(qt_app, looped_clip):
    from widgets.spotify_visualizer.bubble_viewport_profile import (
        BUBBLE_CARD_CAPACITY,
        resolve_bubble_world,
    )

    card = _replay(looped_clip)
    wide = _replay(looped_clip, expand_at=0)
    card_drawn, wide_drawn = card["presentations"][-1], wide["presentations"][-1]
    assert wide_drawn.expanded_display and not card_drawn.expanded_display
    population = _population()
    card_rule = resolve_bubble_world(card_drawn.logical_viewport_extent, authored_population=population)
    wide_card_rule = resolve_bubble_world(wide_drawn.logical_viewport_extent, authored_population=population)
    # The display-wide world overflows the live capacity (else neither rule zooms and there is nothing to test).
    assert wide_card_rule.world_scale > 1.0

    # The card: exactly the card rule's world, and never more heroes than the card's capacity.
    for frame in card["frames"][_WARMUP_FRAMES:]:
        state = frame.mode_state
        assert state.world_scale == card_rule.world_scale
        assert state.bubble_count <= BUBBLE_CARD_CAPACITY

    # Display-wide: a smaller zoom than the card rule would give that world (smaller heroes against the display) and
    # more live heroes than the card rule's capped count.
    wide_scales = {frame.mode_state.world_scale for frame in wide["frames"][_WARMUP_FRAMES:]}
    assert len(wide_scales) == 1
    wide_scale = wide_scales.pop()
    assert 1.0 < wide_scale < 0.8 * wide_card_rule.world_scale, (wide_scale, wide_card_rule.world_scale)
    card_rule_live = population * wide_card_rule.population_scale
    late = [frame.mode_state.bubble_count for frame in wide["frames"][len(wide["frames"]) // 2:]]
    assert statistics.median(late) > 1.2 * card_rule_live, (statistics.median(late), card_rule_live)

    # Each hero's swing about its own size is the card's times the display-wide world's screen gain (operator, 22 Nov:
    # the zoom-out made fullscreen breathing ~20 % weak on screen; the gain gives that back, exactly overflow ** 0.24).
    from widgets.spotify_visualizer.bubble_viewport_profile import DISPLAY_WIDE_BREATH_GAIN_SHARE

    screen_gain = resolve_bubble_world(wide_drawn.logical_viewport_extent, authored_population=population,
                                       display_wide=True).screen_gain
    gain = 1.0 + DISPLAY_WIDE_BREATH_GAIN_SHARE * (screen_gain - 1.0)   # 70 % of the extra (operator, 22 Nov)
    assert 1.03 < gain < screen_gain
    card_swing, wide_swing = _breathing(card["frames"]) - 1.0, _breathing(wide["frames"]) - 1.0
    assert card_swing > 0.05
    assert wide_swing == pytest.approx(card_swing * gain, rel=0.2), (card_swing, wide_swing, gain)
    assert wide_swing > card_swing * 1.02          # still above the pre-gain swing (the old assertion: equal)


def test_display_wide_motion_keeps_the_card_rules_on_screen_speed():
    # On-screen speed scales with the world's zoom; the display-wide card zooms less than the card rule, so its movement
    # per step is scaled back up by exactly the card rule's zoom over its own (operator, 22 Nov: ~20 % slow).
    import math

    from widgets.spotify_visualizer.bubble_viewport_profile import (
        BUBBLE_LIVE_CAPACITY, DISPLAY_WIDE_ZOOM_EXPONENT, resolve_bubble_world,
    )

    extent = (1920.0, 1080.0)
    population = 60
    card = resolve_bubble_world(extent, authored_population=population)
    wide = resolve_bubble_world(extent, authored_population=population, display_wide=True)
    assert card.screen_gain == 1.0                      # every card world: motion unchanged
    assert resolve_bubble_world((420.0, 280.0), authored_population=population).screen_gain == 1.0
    overflow = population * (1920.0 / 420.0) * (1080.0 / 280.0) / max(population, BUBBLE_LIVE_CAPACITY)
    assert wide.world_scale == pytest.approx(overflow ** DISPLAY_WIDE_ZOOM_EXPONENT)
    assert wide.screen_gain == pytest.approx(math.sqrt(overflow) / wide.world_scale)
    assert wide.screen_gain > 1.0
    # On-screen speed (motion per step times zoom, over the cards spanned) equals the card rule's.
    assert wide.screen_gain * wide.world_scale == pytest.approx(card.world_scale)
