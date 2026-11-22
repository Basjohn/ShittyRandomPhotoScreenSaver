"""Bubble behaves the same on its card and on the display-wide card (operator, 21 Nov: "fullscreen they accelerate
massively and lose their breathing").

The display-wide card grows the card's world on the display's long axis (``resolve_expanded_visualizer_presentation``)
and the renderer lays Bubble's frame out on that drawn world. Bubble's simulation must therefore live in the same
world: its domain (canonical-card units, ``bubble_viewport_profile``) times its capacity zoom is the drawn card's
logical extent, at the card and display-wide. Measured on the drawn card against the drawn bubbles' own size
(canonical-card units over the capacity zoom), its travel speed is then the same at both sizes. Before the fix the simulation kept the ordinary card's world while the
expanded card drew a taller one, so every position and wake was stretched along the grown axis (here about 4.7x).

Driven through the production owner on an unshown runtime (``tools/expanded_visualizer_evidence.owner_replay``), on a
recorded fixture, with test-owned settings (the frozen Bubble copy; the stream turned to a vertical direction so the
grown axis carries the travel). No window is shown.
"""
from __future__ import annotations

import math
import statistics

import pytest

# A thin CUSTOM card, as the operator's (its world about 2.9 x 0.5 canonical cards): on any landscape display the
# display-wide card keeps its width and grows its height several times.
_EXTENT = (1200.0, 144.0)
_COMMITTED = ((40.0, 40.0, _EXTENT[0], _EXTENT[1]), _EXTENT)
_WARMUP_FRAMES = 40


@pytest.fixture(scope="module")
def looped_clip():
    from tools.expanded_visualizer_evidence import looped_fixture

    return looped_fixture(loops=6)


def _settings():
    from core.settings.visualizer_mode_settings import require_mode_settings
    from tests._visualizer_frozen_settings import frozen_visualizer_settings

    settings = frozen_visualizer_settings("bubble")
    choices = require_mode_settings("bubble").control("bubble_stream_direction").choices
    vertical = next(choice for choice in choices if choice in ("down", "up"))
    settings["bubble_stream_direction"] = vertical
    return settings


def _replay(clip, **kwargs):
    from tools.expanded_visualizer_evidence import owner_replay

    return owner_replay(clip, "bubble", settings=_settings(), committed=_COMMITTED, keep_frames=True, **kwargs)


def _drawn_world(presentation):
    """The drawn card's logical world in canonical-card units (what the renderer lays Bubble's frame onto)."""
    width, height = presentation.logical_viewport_extent
    base_w, base_h = presentation.baseline_viewport_size
    return width / base_w, height / base_h


def _content_units(presentation):
    """Canonical-card units across the drawn content rect, per axis (positions are fractions of it)."""
    _x, _y, width, height = presentation.content_rect
    scale = presentation.uniform_visual_scale
    base_w, base_h = presentation.baseline_viewport_size
    return width / scale / base_w, height / scale / base_h


def _speeds(result):
    """Median on-card travel per axis over consecutive frames of equal count, in the simulation's own units per
    second: canonical-card units over the frame's capacity zoom. A card whose area needs more heroes than the renderer
    holds zooms its whole world (bubbles, speeds and distances together, R-170), so this is travel measured against
    the drawn bubbles' own size."""
    frames, presentations = result["frames"], result["presentations"]
    along_x, along_y = [], []
    for index in range(_WARMUP_FRAMES, len(frames) - 1):
        a, b = frames[index].mode_state, frames[index + 1].mode_state
        presentation = presentations[index + 1]
        if presentation is None or presentations[index] != presentation:
            continue
        dt = b.simulation_timestamp - a.simulation_timestamp
        if dt <= 0.0 or a.bubble_count != b.bubble_count or a.bubble_count == 0:
            continue
        units_x, units_y = _content_units(presentation)
        units_x, units_y = units_x / b.world_scale, units_y / b.world_scale
        for i in range(a.bubble_count):
            along_x.append(abs(b.positions[4 * i] - a.positions[4 * i]) * units_x / dt)
            along_y.append(abs(b.positions[4 * i + 1] - a.positions[4 * i + 1]) * units_y / dt)
    assert len(along_y) > 200, len(along_y)
    return statistics.median(along_x), statistics.median(along_y)


def _sim_world(frame):
    diagnostics = dict(frame.mode_state.geometry_diagnostics)
    zoom = frame.mode_state.world_scale
    return diagnostics["domain_w"] * zoom, diagnostics["domain_h"] * zoom


@pytest.mark.qt
def test_bubbles_world_and_speed_are_the_drawn_cards_at_card_and_display_size(qt_app, looped_clip):
    card = _replay(looped_clip)
    wide = _replay(looped_clip, expand_at=0)
    card_drawn = card["presentations"][-1]
    wide_drawn = wide["presentations"][-1]
    assert wide_drawn.expanded_display and not card_drawn.expanded_display
    card_world, wide_world = _drawn_world(card_drawn), _drawn_world(wide_drawn)
    # The two sizes really differ: the display-wide card's world grew on its height several times.
    assert wide_world[0] == pytest.approx(card_world[0])
    assert wide_world[1] > 3.0 * card_world[1]
    # The simulation's world is the drawn card's world at both sizes.
    for result, world in ((card, card_world), (wide, wide_world)):
        for frame in result["frames"][_WARMUP_FRAMES:]:
            assert _sim_world(frame) == pytest.approx(world, rel=1e-9)
    # So travel on the drawn card, against the drawn bubbles' size, does not depend on the card's size, once the
    # display-wide card's motion scale (the card rule's square-root zoom over its own zoom-out, operator 22 Nov:
    # on-screen speed kept) is taken out: zoom = overflow ** E, so motion_scale = zoom ** (0.5 / E - 1).
    from widgets.spotify_visualizer.bubble_viewport_profile import DISPLAY_WIDE_ZOOM_EXPONENT

    (card_x, card_y), (wide_x, wide_y) = _speeds(card), _speeds(wide)
    wide_zoom = wide["frames"][-1].mode_state.world_scale
    motion_scale = wide_zoom ** (0.5 / DISPLAY_WIDE_ZOOM_EXPONENT - 1.0)
    assert motion_scale > 1.0
    wide_x, wide_y = wide_x / motion_scale, wide_y / motion_scale
    assert card_y > 0.0 and wide_y > 0.0
    assert math.isclose(wide_y, card_y, rel_tol=0.25), (card_y, wide_y)
    assert math.isclose(wide_x, card_x, rel_tol=0.25, abs_tol=1e-3), (card_x, wide_x)
