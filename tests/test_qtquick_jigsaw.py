"""Jigsaw Piece Flip: the shared piece layout (watertight shared cuts, simple faces, exact cover),
the order planner, the flip schedule's ends, and the renderer through the production host on a
real offscreen context (no window): exact and continuous ends on every tier, the order's start
corner flips first, warm-up, park/release and the resolver."""
from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.gl_programs.jigsaw_options import JIGSAW_ORDERS, JIGSAW_PIECES_RANGE
from rendering.gl_programs.jigsaw_program import (
    JIGSAW_FLIP_END,
    jigsaw_flip_pose,
    jigsaw_outline_alpha,
    jigsaw_outline_start,
    jigsaw_piece_phase,
    jigsaw_piece_start,
)
from rendering.quick.transitions.parameter_resolution import resolve_parameterized_phase_c_inputs
from rendering.quick.transitions.piece_layout import (
    JIGSAW_CURVE_TOLERANCE,
    PIECE_LAYOUT_MAX_PIECES,
    PIECE_VERTEX_FLOATS,
    EdgeShape,
    _edge_points,
    _seeded_edge,
    ear_clip,
    jigsaw_layout,
    piece_grid,
    piece_order,
    piece_vertices,
)
from tools.transition_contact_sheet import TransitionCapture

W, H = 320, 180


def _area(points: np.ndarray) -> float:
    x, y = points[:, 0], points[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(np.roll(x, -1), y))


@pytest.mark.parametrize("count,aspect", ((12, 0.75), (48, 16 / 9), (150, 21 / 9)))
def test_pieces_cover_the_picture_exactly_with_simple_faces(count, aspect):
    layout = jigsaw_layout(7, count, aspect)
    cols, rows = piece_grid(count, aspect)
    assert (layout.cols, layout.rows) == (cols, rows) and cols * rows <= PIECE_LAYOUT_MAX_PIECES
    total = 0.0
    for outline in layout.outlines:
        area = _area(outline)
        assert area > 0.0                                    # counter-clockwise
        triangles = np.asarray(ear_clip(outline))
        a, b, c = outline[triangles[:, 0]], outline[triangles[:, 1]], outline[triangles[:, 2]]
        signed = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
        assert np.all(signed > 0.0) and 0.5 * signed.sum() == pytest.approx(area, rel=1e-9)
        total += area
    # Shared cuts tile the plane: no gap, no overlap.
    assert total == pytest.approx(aspect, rel=1e-9)
    # Border edges are straight, so every point stays on the picture.
    points = np.vstack(layout.outlines)
    assert points[:, 0].min() >= -aspect / 2 - 1e-12 and points[:, 0].max() <= aspect / 2 + 1e-12
    assert points[:, 1].min() >= -0.5 - 1e-12 and points[:, 1].max() <= 0.5 + 1e-12


def test_neighbours_share_the_very_same_cut_points():
    layout = jigsaw_layout(3, 48, 16 / 9)
    cols, (cell_w, cell_h) = layout.cols, layout.cell
    for index in range(len(layout.outlines) - 1):
        if (index + 1) % cols == 0:
            continue
        r, c = divmod(index, cols)
        left, right = layout.outlines[index], layout.outlines[index + 1]
        # The left piece's right side runs from its bottom-right to its top-right corner.
        x = -layout.aspect / 2 + (c + 1) * cell_w
        rows = [tuple(p) for p in left]
        start = rows.index((x, 0.5 - (r + 1) * cell_h))
        end = rows.index((x, 0.5 - r * cell_h))
        cut = set(rows[start:end + 1])
        # Every point of that cut, knob included, is bit-identical in the right piece.
        assert len(cut) > 17 and cut <= {tuple(p) for p in right}


@pytest.mark.parametrize("knob", (1 / 3, 1 / 9))
def test_knob_curves_stay_within_the_tolerance_of_the_true_beziers(knob):
    rng = random.Random(5)
    for _ in range(40):
        shape = _seeded_edge(rng, 1)
        points = _edge_points((0.0, 0.0), (knob, 0.0), knob, shape)
        dense = _edge_points((0.0, 0.0), (knob, 0.0), knob, shape, tolerance=JIGSAW_CURVE_TOLERANCE / 50)
        a, b = points[:-1], points[1:]
        ab = b - a
        # Distance of every dense point to the nearest flattened segment.
        w = dense[:, None, :] - a[None, :, :]
        u = np.clip(np.sum(w * ab, axis=2) / np.sum(ab * ab, axis=1), 0.0, 1.0)
        gap = np.linalg.norm(w - u[..., None] * ab[None, :, :], axis=2).min(axis=1)
        assert gap.max() <= JIGSAW_CURVE_TOLERANCE * 1.15   # three samples estimate the error
    # A straight border edge is just its two corners.
    assert len(_edge_points((0.0, 0.0), (knob, 0.0), knob, EdgeShape(0))) == 2


@pytest.mark.parametrize("count", (12, 48, 150))
def test_ring_insets_stay_simple_where_necks_curve_tighter_than_the_bevel(count):
    from rendering.quick.transitions.piece_layout import JIGSAW_BEVEL, _distinct, _inset, is_simple

    for outline in jigsaw_layout(2, count, 16 / 9).outlines:
        inner, _outward = _inset(outline, JIGSAW_BEVEL)
        assert len(inner) == len(outline) and is_simple(inner[_distinct(inner)])


def _knob_spread(layout) -> tuple[float, float]:
    """Relative spread (std / mean) of knob depth and head width over a layout's vertical cuts."""
    cols, (cell_w, _cell_h) = layout.cols, layout.cell
    depths, widths = [], []
    for r in range(layout.rows):
        for c in range(cols - 1):
            left, right = layout.outlines[r * cols + c], layout.outlines[r * cols + c + 1]
            shared = np.array(sorted({tuple(p) for p in left} & {tuple(p) for p in right}))
            deviation = np.abs(shared[:, 0] - (-layout.aspect / 2 + (c + 1) * cell_w))
            depths.append(deviation.max())
            head = shared[deviation > 0.6 * deviation.max()][:, 1]
            widths.append(head.max() - head.min())
    depths, widths = np.asarray(depths), np.asarray(widths)
    return float(depths.std() / depths.mean()), float(widths.std() / widths.mean())


@pytest.mark.parametrize("seed", (1, 4, 9))
def test_knobs_differ_in_shape_across_a_layout(seed):
    depth, width = _knob_spread(jigsaw_layout(seed, 48, 16 / 9))
    assert depth > 0.13 and width > 0.10


def test_the_rejected_near_identical_knobs_fail_the_variety_bar(monkeypatch):
    from rendering.quick.transitions import piece_layout

    def rejected(rng, sign, variety=1.0):          # the first draft: 3.5% jitter on a fixed tab
        jitter = [rng.uniform(-0.035, 0.035) for _ in range(5)]
        return piece_layout.EdgeShape(sign, 0.10 + rng.uniform(-0.012, 0.012), *jitter)

    monkeypatch.setattr(piece_layout, "_seeded_edge", rejected)
    _depth, width = _knob_spread(piece_layout.jigsaw_layout(4, 48, 16 / 9))
    assert width < 0.10


def test_vertices_lead_with_the_flat_front_faces_and_stay_on_the_picture():
    layout = jigsaw_layout(11, 24, 16 / 9)
    vertices, flat = piece_vertices(layout)
    assert vertices.shape[1] == PIECE_VERTEX_FLOATS and 0 < flat < len(vertices) and len(vertices) % 3 == 0
    uv = vertices[:, 0:2]
    assert uv.min() >= -1e-6 and uv.max() <= 1.0 + 1e-6
    assert np.all(vertices[:flat, 2] == 0.5)                 # the flat block is front faces and rings
    assert set(np.unique(vertices[:, 7]).astype(int)) == set(range(len(layout.outlines)))


@pytest.mark.parametrize("order", ("top_left", "top_right", "bottom_left", "bottom_right"))
def test_a_corner_order_starts_at_its_corner_and_turns_pieces_away_from_it(order):
    layout = jigsaw_layout(5, 48, 16 / 9)
    ranks, axes = piece_order(order, layout.centres, layout.cell, layout.aspect, 5)
    assert sorted(ranks.tolist()) == list(range(len(ranks)))
    sx = -1.0 if "left" in order else 1.0
    sy = 1.0 if "top" in order else -1.0
    corner = np.array((sx * layout.aspect / 2, sy * 0.5))
    distance = np.linalg.norm(layout.centres - corner, axis=1)
    assert distance[ranks == 0][0] == pytest.approx(distance.min())
    assert np.corrcoef(ranks, distance)[0, 1] > 0.95
    # The axis is across the way the flips travel.
    away = layout.centres - corner
    heading = np.stack((np.cos(axes - 0.5 * math.pi), np.sin(axes - 0.5 * math.pi)), axis=1)
    assert np.all(np.sum(heading * away, axis=1) > 0.0)


def test_random_start_and_unordered_orders_are_seeded_permutations():
    layout = jigsaw_layout(5, 48, 16 / 9)
    for order in ("random_start", "unordered"):
        ranks, _ = piece_order(order, layout.centres, layout.cell, layout.aspect, 9)
        again, _ = piece_order(order, layout.centres, layout.cell, layout.aspect, 9)
        other, _ = piece_order(order, layout.centres, layout.cell, layout.aspect, 10)
        assert sorted(ranks.tolist()) == list(range(len(ranks)))
        assert np.array_equal(ranks, again) and not np.array_equal(ranks, other)


@pytest.mark.parametrize("count", (10, 48, 144))
def test_cut_lines_sweep_in_from_the_flip_start_and_are_whole_before_each_lift(count):
    starts = [jigsaw_outline_start(rank, count) for rank in range(count)]
    assert starts[0] == 0.0 and starts == sorted(starts) and starts[-1] > starts[0]
    for rank in range(count):
        lift = jigsaw_piece_start(rank, count)
        assert jigsaw_outline_alpha(lift, rank, count) == pytest.approx(1.0)
        # Each piece's outline appears as one shape: before its start nothing, after it rising.
        assert jigsaw_outline_alpha(starts[rank], rank, count) == 0.0
    # Midway through the sweep the first pieces are outlined and the last are not yet.
    middle = 0.5 * (starts[0] + starts[-1])
    assert jigsaw_outline_alpha(middle, 0, count) > jigsaw_outline_alpha(middle, count - 1, count)


@pytest.mark.parametrize("count", (10, 48, 144))
def test_every_piece_lands_and_every_cut_line_is_gone_by_the_end(count):
    for rank in range(count):
        assert jigsaw_piece_phase(0.0, rank, count) == 0.0
        assert jigsaw_piece_phase(JIGSAW_FLIP_END, rank, count) == pytest.approx(1.0)
        assert jigsaw_outline_alpha(0.0, rank, count) == 0.0
        assert jigsaw_outline_alpha(1.0, rank, count) == pytest.approx(0.0, abs=1e-12)
    assert jigsaw_flip_pose(0.0) == (0.0, 0.0, 0.0)
    angle, morph, light = jigsaw_flip_pose(1.0)
    assert angle == pytest.approx(math.pi) and morph == 1.0 and light == pytest.approx(0.0, abs=1e-12)
    # Mid-flip the card is edge-on while its outline morphs into its mirror image.
    angle, morph, _ = jigsaw_flip_pose(0.5)
    assert angle == pytest.approx(0.5 * math.pi) and morph == pytest.approx(0.5)


@pytest.fixture
def capture(qt_app):
    capture = TransitionCapture(W, H)
    yield capture
    capture.close()


def _pixels(image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


@pytest.mark.qt
@pytest.mark.parametrize("detail", ("High", "Balanced", "Performance"))
def test_ends_are_exact_and_continuous_on_every_tier(capture, detail):
    run = capture.run("jigsaw", settings={"scene3d_detail": detail, "jigsaw": {"direction": "Top Left"}},
                      duration_ms=7000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    assert np.array_equal(_pixels(capture.render(run, 0.0)[0]), source)
    assert np.array_equal(_pixels(capture.render(run, 1.0)[0]), destination)
    assert np.abs(_pixels(capture.render(run, 0.003)[0]) - source).mean() < 1.0
    assert np.abs(_pixels(capture.render(run, 0.997)[0]) - destination).mean() < 1.0


@pytest.mark.qt
@pytest.mark.parametrize("label", ("Top Left", "Bottom Right"))
def test_the_order_corner_turns_to_the_new_picture_first(capture, label):
    run = capture.run("jigsaw", settings={"jigsaw": {"direction": label, "pieces": 24}}, duration_ms=7000)
    source, destination = _pixels(capture.images[0]), _pixels(capture.images[1])
    frame = _pixels(capture.render(run, 0.45)[0])
    near = np.s_[:H // 3, :W // 3] if label == "Top Left" else np.s_[-H // 3:, -W // 3:]
    far = np.s_[-H // 3:, -W // 3:] if label == "Top Left" else np.s_[:H // 3, :W // 3]

    def newness(region):
        return float(np.abs(frame[region] - source[region]).mean() - np.abs(frame[region] - destination[region]).mean())

    assert newness(near) > 10 and newness(far) < -10


@pytest.mark.qt
def test_warmed_runs_compile_and_allocate_nothing_on_their_first_frames(qt_app, monkeypatch):
    from rendering.quick.transitions.run_geometry import prepare_run_geometry
    from tests.test_transition_warmup import _Work

    capture = TransitionCapture(256, 144)
    try:
        work = _Work(monkeypatch)
        run = capture.run("jigsaw", settings={"scene3d_detail": "High"}, duration_ms=3000)
        parameters, size = run.request.parameter_dict(), (capture.width, capture.height)
        # Production prepares the layout on COMPUTE when the batch resolves.
        prepare_run_geometry("jigsaw", parameters, (capture.width / capture.height,), None)
        steps = 0
        while not capture.host.warm_step("jigsaw", parameters, size):
            steps += 1
            assert work.total <= steps and steps < 50
        renderer = capture.host._implementations["jigsaw"]
        assert renderer._resources.has_mesh("pieces")
        meshes = dict(renderer._resources._meshes)
        warmed, allocated = work.total, list(work.allocations)
        capture.render(run, 0.0)
        capture.render(run, 0.4)
        assert work.total == warmed and work.allocations == allocated
        assert renderer._resources._meshes == meshes
        capture.host.park()
        assert not renderer._target.has_resources and not renderer._environment.has_resources
        assert not renderer._resources.has_mesh("pieces")
        renderer.release_resources()
        assert not renderer.has_resources
    finally:
        capture.close()


def test_the_resolver_picks_orders_and_repairs_values():
    seen = {resolve_parameterized_phase_c_inputs("jigsaw", {}, random_source=random.Random(seed))
            .parameter_dict()["order"] for seed in range(60)}
    assert seen == set(JIGSAW_ORDERS.values())
    resolved = resolve_parameterized_phase_c_inputs(
        "jigsaw", {"jigsaw": {"direction": "Unordered", "pieces": 10_000}}, random_source=random.Random(1))
    parameters = resolved.parameter_dict()
    assert resolved.direction is None
    assert parameters["order"] == "unordered" and parameters["pieces"] == JIGSAW_PIECES_RANGE[1]
