"""Neon Lake's land under the music, on the GPU's own height function (1B.6): the reshaping is smooth, and the
optional Growth and Indents are deformations of that one surface that do nothing at rest or when off.

Operator, 11 Nov: "Land reactivity deserves an adjustment pass for true smooth (no tearing/jagged edges)
deformation. We want optional growth of spires, mounds and land that doesn't visibly exist at low reactivity and
indents of land that does."

The probe evaluates the production ``basinSurface`` (the vertex shader's functions, verbatim) over a dense uv grid.
"""
from __future__ import annotations

import numpy as np
import pytest

from rendering.gl_programs.heightfield import normalize_heightfield
from rendering.gl_programs.neon_terrain_reaction import (
    GROWTH_EYE_CLEAR, GROWTH_FAR_LAND, INDENT_EYE_CLEAR, INDENT_FLOOR, REACTION_FLOOR, REACTION_LANES, normalize_terrain_shaper,
)
from tests.test_neon_lake_reaction import _SurfaceProbe

pytestmark = pytest.mark.qt
SIZE = 33
HEIGHT = 1.5            # the probe's Terrain Height
HALF_WIDTH, DEPTH = 1.7, 2.4   # the probe's basin, in world units


def _slope() -> dict:
    """Land rising evenly from the front (0.06) to the back (1.0): elevation contours are straight rows."""
    heights = [0.06 + 0.94 * row / (SIZE - 1) for row in range(SIZE) for _col in range(SIZE)]
    return normalize_heightfield({"version": 1, "size": SIZE, "heights": heights})


def _plain() -> dict:
    """Level land (0.3) round a square pool."""
    heights = [0.0 if 12 <= row <= 20 and 12 <= col <= 20 else 0.3 for row in range(SIZE) for col in range(SIZE)]
    return normalize_heightfield({"version": 1, "size": SIZE, "heights": heights})


SHAPER = {"nodes": [[0.0, 1.0], [1.0, 1.0]],
          "notches": [[0.0, "Bass"], [0.2, "Low-Mid"], [0.4, "Vocal"], [0.6, "Hi-Mid"], [0.8, "Treble"]],
          "lanes": {lane: 1.0 for lane in REACTION_LANES}}


@pytest.fixture
def probe(qt_app):
    probes = []

    def make(terrain):
        probes.append(_SurfaceProbe(terrain))
        return probes[-1]
    yield make
    for item in probes:
        item.close()


def _shaper():
    from core.settings.default_contract import require_canonical_default
    return normalize_terrain_shaper(SHAPER, require_canonical_default(
        "widgets.spotify_visualizer.shockwave_grid_terrain_shaper"))


def test_lanes_meet_without_a_tear_along_their_contour(probe, monkeypatch):
    """Alternate lanes driven hard over an even slope: across each lane boundary's contour the reshaping changes
    gradually. With the lanes' cross-fade taken away (the control) the same drives bend the land at each boundary
    several times harder."""
    from rendering.gl_programs import neon_terrain_reaction as reaction
    surface = probe(_slope())
    rect = (0.3, 0.05, 0.7, 0.95)                    # across every boundary, away from the grid's edge
    drives = dict(bands=(1.0, 0.0, 1.0, 0.0, 1.0), amounts=(1.0, 0.0, 0.0), phase=1.3, shaper=_shaper(), uv_rect=rect)
    rest = surface.draw(movement=0.0, uv_rect=rect)[..., 0]

    def bend():
        moved = surface.draw(movement=1.0, **drives)[..., 0] - rest
        assert np.abs(moved).max() > 0.05 * HEIGHT               # the land does reshape
        return float(np.abs(np.diff(moved, n=2, axis=0)).max()), moved

    smooth, moved = bend()
    # Nothing steps: neighbouring samples (1/64 of the slope apart) differ by a share of the reshaping (the
    # patterns' own slope; a switch at a contour stepped by the whole of it).
    assert np.abs(np.diff(moved, axis=0)).max() < 0.35 * np.abs(moved).max()
    monkeypatch.setattr(reaction, "REACTION_LANE_BLEND", 1e-4)
    control, _moved = bend()
    assert control > 2.0 * smooth, (smooth, control)


def test_the_reshaping_never_passes_the_lands_floor_and_eases_onto_it(probe):
    """Everything that lowers the land at once, as hard as it goes: never below the floor share of the authored
    height, and reaching toward it without stopping dead on it (a hard stop creased the land along that line).
    Indents carve on top, onto their own lower floor share, and never pin a plateau on it either."""
    surface = probe(_slope())
    rect = (0.1, 0.1, 0.9, 0.9)
    rest = surface.draw(movement=0.0, uv_rect=rect)[..., 0]
    lowered = dict(movement=1.0, bands=(1.0,) * 5, amounts=(1.0, 0.0, 1.0), phase=0.7, shaper=_shaper(),
                   uv_rect=rect)
    for floor, extra in ((REACTION_FLOOR, {}), (INDENT_FLOOR, dict(forms=(0.0, 0.0, 1.0), drives=(0.0, 1.0)))):
        share = surface.draw(**lowered, **extra)[..., 0] / rest
        assert (share >= floor - 1e-5).all() and share.min() < 0.6
        assert (np.isclose(share, floor, atol=1e-3)).mean() < 0.02            # no plateau pinned on the floor


def test_growth_and_indents_do_nothing_off_or_at_rest(probe):
    surface = probe(_plain())
    rest = surface.draw(movement=1.0, level=0.0)
    assert np.array_equal(rest, surface.draw(movement=1.0, level=0.0, forms=(0.0, 1.0, 0.0), drives=(1.0, 1.0)))
    assert np.array_equal(rest, surface.draw(movement=1.0, level=0.0, forms=(1.0, 1.0, 1.0), drives=(0.0, 0.0)))
    # React to Music off (strength 0): the amounts cannot act however the music drives them.
    still = surface.draw(movement=0.0, level=0.0)
    assert np.array_equal(still, surface.draw(movement=0.0, level=0.0, forms=(1.0, 1.0, 1.0), drives=(1.0, 1.0)))


@pytest.mark.parametrize("shape", [0.0, 1.0])
def test_growth_raises_smooth_landforms_on_land_only_and_more_with_the_drive(probe, shape):
    surface = probe(_plain())
    rest = surface.draw(movement=1.0, level=0.0)
    water = rest[..., 1] > 0.5
    lifts = [surface.draw(movement=1.0, level=0.0, forms=(1.0, shape, 0.0), drives=(drive, 0.0))[..., 0]
             - rest[..., 0] for drive in (0.35, 0.6, 0.95)]
    for lift in lifts:
        assert (lift >= -1e-6).all() and not lift[water].any()            # it only raises, and never the water
    assert lifts[0].mean() < lifts[1].mean() < lifts[2].mean()             # the louder, the more land stands
    assert (lifts[0] <= lifts[1] + 1e-5).all() and (lifts[1] <= lifts[2] + 1e-5).all()   # each form only grows
    assert (lifts[0] > 0.01).mean() < (lifts[2] > 0.01).mean()             # and more of them stand
    assert lifts[2].max() > 0.15 * HEIGHT
    # Smooth: a close look at the tallest form on open land has no step or crease (its samples a thirtieth of a
    # cell apart). At the pool's sheer bank the forms rise with the bank itself, within its quarter cell.
    columns, rows = np.meshgrid(np.linspace(0.0, 1.0, surface.SIZE), np.linspace(0.0, 1.0, surface.SIZE))
    open_land = (np.maximum(np.abs(columns - 0.5), np.abs(rows - 0.5)) > 0.3) & (columns > 0.05) & (columns < 0.95) \
        & (rows > 0.05) & (rows < 0.95)
    row, col = np.unravel_index(int(np.where(open_land, lifts[2], 0.0).argmax()), lifts[2].shape)
    u, v = col / (surface.SIZE - 1), row / (surface.SIZE - 1)
    rect = (u - 0.03, v - 0.03, u + 0.03, v + 0.03)
    close = (surface.draw(movement=1.0, level=0.0, forms=(1.0, shape, 0.0), drives=(0.95, 0.0), uv_rect=rect)[..., 0]
             - surface.draw(movement=1.0, level=0.0, uv_rect=rect)[..., 0])
    assert np.abs(np.diff(close, axis=0)).max() < 0.05 * lifts[2].max()
    assert np.abs(np.diff(close, axis=1)).max() < 0.05 * lifts[2].max()


def test_spires_stand_taller_and_slimmer_than_mounds(probe):
    surface = probe(_plain())
    rest = surface.draw(movement=1.0, level=0.0)[..., 0]
    mounds, spires = (surface.draw(movement=1.0, level=0.0, forms=(1.0, shape, 0.0), drives=(0.95, 0.0))[..., 0] - rest
                      for shape in (0.0, 1.0))
    assert spires.max() > 1.5 * mounds.max()
    assert (spires > 0.5 * spires.max()).mean() < (mounds > 0.5 * mounds.max()).mean()


def _peaks(lift: np.ndarray) -> int:
    """Local maxima of a lift field that stand clear of the flat (one per standing form)."""
    inner = lift[1:-1, 1:-1]
    around = np.max([lift[1 + dy:lift.shape[0] - 1 + dy, 1 + dx:lift.shape[1] - 1 + dx]
                     for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx], axis=0)
    return int(((inner > around) & (inner > 0.02)).sum())


def test_growth_density_packs_more_narrower_forms_and_is_neutral_at_the_usual(probe):
    """Growth Density scales the site cell: the usual (0.5) is a scale of exactly 1, so it changes nothing; denser
    stands more, narrower forms over the same land, sparser fewer and wider."""
    from rendering.gl_programs.neon_terrain_reaction import growth_cell_scale
    assert growth_cell_scale(0.5) == 1.0 and growth_cell_scale(1.0) < 1.0 < growth_cell_scale(0.0)
    surface = probe(_plain())
    rest = surface.draw(movement=1.0, level=0.0)[..., 0]
    grown = dict(movement=1.0, level=0.0, forms=(1.0, 0.0, 0.0), drives=(0.95, 0.0))
    counts = [_peaks(surface.draw(place=(growth_cell_scale(d), 0.0), **grown)[..., 0] - rest) for d in (0.0, 0.5, 1.0)]
    assert counts[0] < counts[1] < counts[2], counts


def test_growth_region_far_land_and_by_elevation(probe):
    """Far Land raises nothing on the authored terrain and the usual Growth past its edge; By Elevation follows the
    shaper's curve, so a curve that is zero over the low half of the land grows nothing there."""
    surface = probe(_slope())
    grown = dict(movement=1.0, level=0.0, forms=(1.0, 0.0, 0.0), drives=(0.95, 0.0))
    past = 1.0 + GROWTH_FAR_LAND[1] + 0.02                                # wholly in by here
    for rect in ((0.05, 0.05, 0.95, 0.95), (past, 0.1, past + 1.0, 0.9)):   # on the terrain, and far land past it
        rest = surface.draw(movement=1.0, level=0.0, uv_rect=rect)[..., 0]
        everywhere = surface.draw(uv_rect=rect, **grown)[..., 0] - rest
        far = surface.draw(uv_rect=rect, place=(1.0, 1.0), **grown)[..., 0] - rest
        assert everywhere.max() > 0.05
        if rect[0] < 1.0:
            assert not far.any()                                          # none on the authored terrain
        else:
            assert np.allclose(far, everywhere, atol=1e-6)                # the usual Growth past it
    rect = (0.05, 0.05, 0.95, 0.95)
    rest = surface.draw(movement=1.0, level=0.0, uv_rect=rect)[..., 0]
    high_only = {**SHAPER, "nodes": [[0.0, 0.0], [0.5, 0.0], [1.0, 1.0]]}
    shaper = normalize_terrain_shaper(high_only, _shaper())
    by_height = surface.draw(uv_rect=rect, place=(1.0, 2.0), shaper=shaper, **grown)[..., 0] - rest
    rows = np.linspace(rect[1], rect[3], surface.SIZE)
    low, high = rows < 0.4, rows > 0.7                                    # the slope rises front to back
    assert not by_height[low].any() and by_height[high].max() > 0.05


def test_growth_stands_back_from_the_eye(probe):
    """The camera floor does not know the music's landforms, so they give way round the eye instead."""
    surface = probe(_plain())
    rest = surface.draw(movement=1.0, level=0.0)[..., 0]
    eye = (0.4 * HALF_WIDTH, 0.5, -0.25 * DEPTH)                           # over the land at uv (0.7, 0.25)
    grown = dict(movement=1.0, level=0.0, forms=(1.0, 1.0, 0.0), drives=(0.95, 0.0))
    far = surface.draw(**grown)[..., 0] - rest
    near = surface.draw(eye=eye, **grown)[..., 0] - rest
    columns, rows = np.meshgrid(np.linspace(0.0, 1.0, surface.SIZE), np.linspace(0.0, 1.0, surface.SIZE))
    distance = np.hypot((columns * 2.0 - 1.0) * HALF_WIDTH - eye[0], -rows * DEPTH - eye[2])
    assert far[distance < GROWTH_EYE_CLEAR[0]].max() > 0.05                 # a form stood there
    assert not near[distance < GROWTH_EYE_CLEAR[0]].any()                   # and gives way to the eye
    assert np.allclose(near[distance > GROWTH_EYE_CLEAR[1]], far[distance > GROWTH_EYE_CLEAR[1]], atol=1e-5)
    assert (near <= far + 1e-5).all()


def _level(height: float) -> dict:
    heights = [0.0 if 12 <= row <= 20 and 12 <= col <= 20 else height for row in range(SIZE) for col in range(SIZE)]
    return normalize_heightfield({"version": 1, "size": SIZE, "heights": heights})


@pytest.mark.parametrize("land", [0.3, 0.12])
def test_indents_carve_visible_bowls_and_never_below_their_floor(probe, land):
    """Low land (dunes a tenth of the height scale) as well as higher ground: at full drive a bowl's middle sinks
    most of the land's height (a share of it alone left dunes with dips too shallow to see, 1B.6 refinement),
    onto the Indents floor share and never to the water."""
    surface = probe(_level(land))
    rest = surface.draw(movement=1.0, level=0.0)
    water = rest[..., 1] > 0.5
    sunk = [surface.draw(movement=1.0, level=0.0, forms=(0.0, 0.0, 1.0), drives=(0.0, drive))
            for drive in (0.25, 0.5, 0.95)]
    for image in sunk:
        assert np.array_equal(image[..., 1], rest[..., 1])                 # the water's edge does not move
        assert (image[..., 0] <= rest[..., 0] + 1e-6).all()                # it only presses in
        assert np.array_equal(image[..., 0][water], rest[..., 0][water])
        assert (image[..., 0][~water] >= INDENT_FLOOR * rest[..., 0][~water] - 1e-5).all()
    sink = [rest[..., 0] - image[..., 0] for image in sunk]
    assert 0.0 < sink[0].mean() < sink[1].mean() < sink[2].mean()          # more with the drive
    assert (sink[0] <= sink[1] + 1e-5).all() and (sink[1] <= sink[2] + 1e-5).all()
    standing = rest[..., 0][~water].max()
    assert sink[2].max() > 0.55 * standing                                 # visible: over half the land's height
    assert (sink[2] > 0.25 * standing).mean() > 0.1                        # in many bowls, not one
    # Smooth: a close look at the deepest bowl has no step or crease (no shelf on the floor, no sharp rim).
    columns, rows = np.meshgrid(np.linspace(0.0, 1.0, surface.SIZE), np.linspace(0.0, 1.0, surface.SIZE))
    open_land = (np.maximum(np.abs(columns - 0.5), np.abs(rows - 0.5)) > 0.3) & (columns > 0.05) & (columns < 0.95) \
        & (rows > 0.05) & (rows < 0.95)
    row, col = np.unravel_index(int(np.where(open_land, sink[2], 0.0).argmax()), sink[2].shape)
    u, v = col / (surface.SIZE - 1), row / (surface.SIZE - 1)
    rect = (u - 0.05, v - 0.05, u + 0.05, v + 0.05)
    close = (surface.draw(movement=1.0, level=0.0, uv_rect=rect)[..., 0]
             - surface.draw(movement=1.0, level=0.0, forms=(0.0, 0.0, 1.0), drives=(0.0, 0.95), uv_rect=rect)[..., 0])
    for axis in (0, 1):
        assert np.abs(np.diff(close, axis=axis)).max() < 0.05 * close.max()
        # Its curvature is spread over the bowl, not gathered in a rim: a press saturated against the room above
        # the floor flattened low land's bowls into shelves (control: 10-13 times the mean, here under 2).
        curvature = np.abs(np.diff(close, n=2, axis=axis))
        assert curvature.max() < 3.0 * curvature.mean()


def test_indents_give_way_only_just_round_the_eye(probe):
    """Indents only lower the land, so they need not stand back as far as Growth: the near ground of a default view
    (inside Growth's clearance) is carved too, and only the ground just under the eye stays put."""
    surface = probe(_plain())
    rest = surface.draw(movement=1.0, level=0.0)[..., 0]
    eye = (0.4 * HALF_WIDTH, 0.5, -0.25 * DEPTH)
    pressed = dict(movement=1.0, level=0.0, forms=(0.0, 0.0, 1.0), drives=(0.0, 0.95))
    far = rest - surface.draw(**pressed)[..., 0]
    near = rest - surface.draw(eye=eye, **pressed)[..., 0]
    columns, rows = np.meshgrid(np.linspace(0.0, 1.0, surface.SIZE), np.linspace(0.0, 1.0, surface.SIZE))
    distance = np.hypot((columns * 2.0 - 1.0) * HALF_WIDTH - eye[0], -rows * DEPTH - eye[2])
    assert not near[distance < INDENT_EYE_CLEAR[0]].any()
    within_growth = (distance > INDENT_EYE_CLEAR[1]) & (distance < GROWTH_EYE_CLEAR[0])
    assert near[within_growth].max() > 0.05 and np.allclose(near[within_growth], far[within_growth], atol=1e-5)
    assert (near <= far + 1e-5).all()
