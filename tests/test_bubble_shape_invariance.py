"""R-170: Bubble moves and sizes like the canonical card on every card shape; only density scales.

Production seam: the real ``BubbleSimulation`` tick/snapshot and the real Quick layout
(``compute_quick_bubble_layout``) that turns its payload into pixels. Speeds are measured in
canonical-card pixels per second: card pixels at uniform scale 1, divided by the renderer's own
pixels-per-radius-unit over the canonical card's (so a capacity-zoomed world is compared like a
uniformly scaled card). Inputs and settings are test-owned; no preset or default value is pinned.
"""
from __future__ import annotations

import functools
import math
import random
from statistics import median

import pytest

import widgets.spotify_visualizer.bubble_simulation as bubble_simulation
from rendering.quick.visualizer.implementations.bubble import compute_quick_bubble_layout
from tests._visualizer_presentation import neutral_bubble_settings
from widgets.spotify_visualizer.bubble_simulation import BubbleSimulation
from widgets.spotify_visualizer.bubble_viewport_profile import (
    BUBBLE_LIVE_CAPACITY,
    resolve_bubble_world,
)

CANONICAL = (420.0, 280.0)
SHAPES = {
    "tall": (280.0, 1200.0),
    "wide": (2400.0, 300.0),
    "square": (600.0, 600.0),
    "tiny": (210.0, 140.0),
    "tv_card": (3874.710133891547, 1449.5065990010949),
}
_DT = 1.0 / 90.0
_STEPS = 540
_ENERGY = {"bass": 0.42, "mid": 0.36, "high": 0.18, "overall": 0.40,
           "smooth_mid": 0.36, "smooth_high": 0.18, "crest": 0.0}


def _pixels_per_unit(extent, world_scale) -> float:
    layout = compute_quick_bubble_layout(
        local_content_rect=(0.0, 0.0, *extent), visual_scale=1.0, viewport_extent=extent,
        baseline_viewport_size=CANONICAL, world_scale=world_scale)
    return layout.response_radius_scale * extent[1]


@functools.lru_cache(maxsize=None)
def _measure(extent, stream, *, seeds=(4411, 4412, 4413)):
    """Median along-stream and |velocity| in canonical-card px/s, payload radius per class, live density.

    Pooled over a few seeds so a quarter-size card still has enough bubbles for stable medians."""
    pooled = {"along": [], "speed": [], "big": [], "small": [], "density": []}
    for seed in seeds:
        result = _measure_seed(extent, stream, seed)
        for key in pooled:
            pooled[key].extend(result[key])
    return {"along": median(pooled["along"]), "speed": median(pooled["speed"]),
            "big": median(pooled["big"]), "small": median(pooled["small"]),
            "density": sum(pooled["density"]) / len(pooled["density"]), "world_scale": result["world_scale"]}


def _measure_seed(extent, stream, seed):
    random.seed(seed)
    sim = BubbleSimulation()
    settings = neutral_bubble_settings(
        viewport_extent=extent, bubble_big_count=6, bubble_small_count=24,
        bubble_stream_direction=stream, bubble_drift_direction="swish_horizontal",
        bubble_stream_constant_speed=0.35, bubble_stream_speed_cap=1.2, bubble_stream_reactivity=0.6,
        bubble_drift_amount=0.4, bubble_drift_speed=0.4, bubble_drift_frequency=0.4,
        bubble_surface_reach=1.0,
    )
    direction = {"up": (0.0, -1.0), "right": (1.0, 0.0)}[stream]
    previous, along, speeds, big, small, live = {}, [], [], [], [], []
    to_canonical = None
    for step in range(_STEPS):
        sim.tick(_DT, dict(_ENERGY), settings)
        positions, _extras, _trails = sim.snapshot()
        if to_canonical is None:
            to_canonical = CANONICAL[1] / _pixels_per_unit(extent, sim._world_scale)
        current = {}
        for index, bubble in enumerate(sim._bubbles):
            x, y, radius, alpha = positions[index * 4:index * 4 + 4]
            # Interior motion: entry/exit lanes are a perimeter effect (off-card collision weighting), so
            # their share of samples legitimately follows the card's perimeter-to-area ratio.
            interior = min(bubble.x, sim._domain_w - bubble.x, bubble.y, sim._domain_h - bubble.y) >= 0.12
            steady = alpha >= 0.99 and not bubble.popping and not bubble.exiting and interior
            current[id(bubble)] = (x * extent[0], y * extent[1], steady, bubble)
            before = previous.get(id(bubble))
            if step < 180 or not steady or before is None or not before[2] or before[3] is not bubble:
                continue
            dx = (x * extent[0] - before[0]) / _DT * to_canonical
            dy = (y * extent[1] - before[1]) / _DT * to_canonical
            along.append(dx * direction[0] + dy * direction[1])
            speeds.append(math.hypot(dx, dy))
            (big if bubble.is_big else small).append(radius)
        if step >= 180:
            live.append(sum(1 for b in sim._bubbles if not b.exiting))
        previous = current
    cards = (extent[0] / CANONICAL[0]) * (extent[1] / CANONICAL[1]) / sim._world_scale ** 2
    # Payload radius is in the world's units; the renderer draws one unit at the canonical card's
    # pixels (times the zoom, which ``to_canonical`` already removes from the speeds).
    return {"along": along, "speed": speeds, "big": big, "small": small,
            "density": [sum(live) / len(live) / cards], "world_scale": sim._world_scale}


@pytest.fixture(scope="module")
def canonical():
    return {stream: _measure(CANONICAL, stream) for stream in ("up", "right")}


@pytest.mark.parametrize("stream", ("up", "right"))
@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_card_shape_streams_like_the_canonical_card(canonical, stream, shape) -> None:
    """A tall card does not stream faster and a wide one slower (the operator's 5 Nov report).

    The pre-R-170 projection measured +80..+186% (tall) and -48..-51% (wide) here; each shape now
    differs only by the sampling noise of independently seeded populations (<= ~6%). The exact
    per-bubble laws are pinned at 1e-9 in test_bubble_viewport_reflow / the scaling contracts."""
    result = _measure(SHAPES[shape], stream)
    base = canonical[stream]
    assert result["along"] == pytest.approx(base["along"], rel=0.08), (shape, result, base)
    assert result["speed"] == pytest.approx(base["speed"], rel=0.08), (shape, result, base)
    # A bubble is the canonical size in the world's units on every shape (a quarter card holds too
    # few heroes for a stable size median; its per-bubble size law is the same code path).
    if shape == "tiny":
        return
    assert result["big"] == pytest.approx(base["big"], rel=0.08), (shape, result, base)
    assert result["small"] == pytest.approx(base["small"], rel=0.08), (shape, result, base)


def test_density_follows_area_and_the_capacity_zoom_is_isotropic(canonical) -> None:
    for shape in ("tall", "wide", "square"):
        result = _measure(SHAPES[shape], "up")
        assert result["density"] == pytest.approx(canonical["up"]["density"], rel=0.06), (shape, result)
    tv = resolve_bubble_world(SHAPES["tv_card"], authored_population=18)
    assert tv.world_scale > 1.0
    assert tv.population_scale * 18 == pytest.approx(BUBBLE_LIVE_CAPACITY)
    assert tv.domain_w / tv.domain_h == pytest.approx(
        (SHAPES["tv_card"][0] / CANONICAL[0]) / (SHAPES["tv_card"][1] / CANONICAL[1]))


def test_negative_control_content_relative_motion_is_caught(canonical, monkeypatch) -> None:
    """The retired model (motion as a fraction of the current card) must fail this oracle."""
    real = bubble_simulation.resolve_bubble_world

    def content_relative(extent, *, authored_population):
        world = real(None, authored_population=authored_population)   # a 1x1 world on every card
        return world

    monkeypatch.setattr(bubble_simulation, "resolve_bubble_world", content_relative)
    uncached = _measure.__wrapped__
    tall = uncached(SHAPES["tall"], "up")
    wide = uncached(SHAPES["wide"], "right")
    assert tall["along"] > canonical["up"]["along"] * 1.5        # tall streams faster
    assert wide["along"] > canonical["right"]["along"] * 1.5     # wide's horizontal stream too


@pytest.mark.parametrize("scale", (0.5, 1.0, 1.7, 2.63))
@pytest.mark.parametrize("border", (0.0, 2.0, 3.0))
def test_canonical_card_projection_is_the_pre_r170_projection_exactly(scale, border) -> None:
    """On the canonical extent (any uniform scale/inset) the renderer projection is unchanged."""
    content = (border, border, 420.0 * scale - 2.0 * border, 280.0 * scale - 2.0 * border)
    layout = compute_quick_bubble_layout(local_content_rect=content, visual_scale=scale,
                                         viewport_extent=CANONICAL, baseline_viewport_size=CANONICAL)
    response_height = math.sqrt(content[2] * content[3] / (CANONICAL[0] / CANONICAL[1]))
    assert layout.response_radius_scale == response_height / content[3]
    assert layout.effect_scale == response_height / CANONICAL[1]
    assert layout.trail_radial_scale == 1.0
    assert layout.viewport_stroke_extra_half_px == 0.0


def test_canonical_world_is_the_unit_world_for_every_authored_population() -> None:
    for population in (0, 5, 49, 72, 110):
        world = resolve_bubble_world(CANONICAL, authored_population=population)
        assert (world.domain_w, world.domain_h, world.world_scale, world.population_scale) == (1.0, 1.0, 1.0, 1.0)
        assert resolve_bubble_world(None, authored_population=population) == world
