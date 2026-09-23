"""Glass Shatter collisions and in-flight re-shattering (build-time events)."""

from __future__ import annotations

import math
import random

import numpy as np
import pytest

from rendering.quick.transitions.fracture_geometry import fracture_cells
from rendering.quick.transitions.glass_dynamics import (
    NO_EVENT,
    RANDOM_SPLIT_CHANCE,
    solve_glass_pieces,
    split_polygon,
)
from rendering.quick.transitions.run_geometry import build_glass_geometry, glass_geometry_key
from tools.transition_contact_sheet import TransitionCapture

ASPECT = 16 / 9
MODES = (
    {"collisions": True, "reshatter": False},
    {"collisions": False, "reshatter": True},
    {"collisions": True, "reshatter": True},
)


def _area(points, aspect=ASPECT):
    pts = [(x * aspect, y) for x, y in points]
    return 0.5 * abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1])))


def _convex(points):
    signs = set()
    for a, b, c in zip(points, points[1:] + points[:1], points[2:] + points[:2]):
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) > 1e-12:
            signs.add(cross > 0)
    return len(signs) <= 1


def test_both_off_leaves_every_shard_whole_and_eventless():
    shards = fracture_cells(417, 95, ASPECT)
    pieces = solve_glass_pieces(shards, ASPECT, "left", 1.0, 417, collisions=False, reshatter=False)
    assert [piece.shard for piece in pieces] == list(shards)
    assert all(piece.life == (0.0, NO_EVENT) and piece.kick[3] == NO_EVENT for piece in pieces)


def test_split_pieces_tile_their_shard_exactly():
    rng = random.Random(5)
    for shard in fracture_cells(88, 60, ASPECT):
        pieces = split_polygon(shard, ASPECT, rng)
        if not pieces:
            continue
        assert 2 <= len(pieces) <= 3
        assert all(_convex(list(piece)) for piece in pieces)
        assert sum(_area(piece) for piece in pieces) == pytest.approx(_area(shard.polygon), rel=1e-9)


def test_without_collisions_about_thirty_percent_of_shards_crack_in_flight():
    for seed in (417, 9001, 23):
        shards = fracture_cells(seed, 95, ASPECT)
        pieces = solve_glass_pieces(shards, ASPECT, "diag_tl_br", 1.0, seed,
                                    collisions=False, reshatter=True)
        parents = [piece for piece in pieces if piece.life[1] < NO_EVENT]
        assert 0.15 < len(parents) / len(shards) < 0.45
        assert RANDOM_SPLIT_CHANCE == 0.30
        for parent in parents:
            children = [piece for piece in pieces
                        if piece.life[0] == parent.life[1] and piece.pivot_center == parent.shard.center]
            assert 2 <= len(children) <= 3
            # Children follow the parent exactly until the split, then kick.
            assert all(child.kick[3] == parent.life[1] for child in children)


def test_with_collisions_shards_crack_only_when_they_collide():
    shards = fracture_cells(417, 95, ASPECT)
    both = solve_glass_pieces(shards, ASPECT, "left", 1.0, 417, collisions=True, reshatter=True)
    bounce = solve_glass_pieces(shards, ASPECT, "left", 1.0, 417, collisions=True, reshatter=False)
    hit_times = {piece.shard.center: piece.kick[3] for piece in bounce if piece.kick[3] < NO_EVENT}
    assert len(hit_times) >= 4
    split = {piece.shard.center: piece.life[1] for piece in both if piece.life[1] < NO_EVENT}
    assert split and split == {center: time for center, time in hit_times.items() if center in split}
    assert set(split) <= set(hit_times)


def test_collision_budget_keeps_crashes_occasional():
    for direction in ("left", "down", "diag_tr_bl", "center_out"):
        shards = fracture_cells(9001, 180, ASPECT)
        pieces = solve_glass_pieces(shards, ASPECT, direction, 1.0, 9001, collisions=True, reshatter=False)
        kicked = sum(1 for piece in pieces if piece.kick[3] < NO_EVENT)
        assert kicked <= 2 * round(180 * 0.12)


def test_dynamic_geometry_is_deterministic_per_seed():
    params = {"seed": 417, "shards": 95, "depth": 1.0, "collisions": True, "reshatter": True}
    first = build_glass_geometry(glass_geometry_key(params, ASPECT, "left")).vertices
    assert first == build_glass_geometry(glass_geometry_key(params, ASPECT, "left")).vertices
    other = build_glass_geometry(glass_geometry_key({**params, "seed": 418}, ASPECT, "left")).vertices
    assert first != other


@pytest.mark.qt
@pytest.mark.parametrize("mode", MODES, ids=("collide", "reshatter", "both"))
@pytest.mark.parametrize("size", ((160, 480), (720, 180), (320, 180)))
def test_every_piece_still_leaves_the_frame(qt_app, mode, size):
    capture = TransitionCapture(*size)
    try:
        source, destination = (np.asarray(i, dtype=np.int16) for i in capture.images)
        for direction in ("left", "up", "diag_tr_bl", "center_out"):
            run = capture.run("glass_shatter", seed=417, direction=direction,
                              parameters={"shards": 120, "depth": 1.5, "thickness": 1.0, **mode})
            first = np.asarray(capture.render(run, 0.0001)[0], dtype=np.int16)
            last = np.asarray(capture.render(run, 0.9999)[0], dtype=np.int16)
            assert np.abs(first - source).mean() < 0.5, (direction, mode)
            assert np.abs(last - destination).mean() < 0.5, (direction, mode)
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("mode", MODES, ids=("collide", "reshatter", "both"))
def test_events_do_not_pop(qt_app, mode):
    capture = TransitionCapture(320, 180)
    try:
        params = {"shards": 95, "depth": 1.0, **mode}
        run = capture.run("glass_shatter", seed=417, direction="left", parameters=params)
        resolved = run.request.parameter_dict()
        pieces = solve_glass_pieces(fracture_cells(resolved["seed"], 95, 320 / 180), 320 / 180,
                                    "left", 1.0, resolved["seed"], **mode)
        times = sorted({piece.kick[3] for piece in pieces if piece.kick[3] < NO_EVENT}
                       | {piece.life[1] for piece in pieces if piece.life[1] < NO_EVENT})
        assert times
        for t in times[:: max(1, len(times) // 6)]:
            before = np.asarray(capture.render(run, t - 0.0004)[0], dtype=np.int16)
            after = np.asarray(capture.render(run, t + 0.0004)[0], dtype=np.int16)
            assert np.abs(before - after).mean() < 3.0, t
    finally:
        capture.close()


@pytest.mark.qt
@pytest.mark.parametrize("mode", MODES, ids=("collide", "reshatter", "both"))
def test_each_option_changes_the_flight(qt_app, mode):
    capture = TransitionCapture(320, 180)
    try:
        base = {"shards": 95, "depth": 1.0}
        plain = capture.render(capture.run("glass_shatter", seed=417, direction="left",
                                           parameters=base), 0.55)[0]
        changed = capture.render(capture.run("glass_shatter", seed=417, direction="left",
                                             parameters={**base, **mode}), 0.55)[0]
        diff = np.abs(np.asarray(plain, dtype=np.int16) - np.asarray(changed, dtype=np.int16))
        assert diff.mean() > 1.0
    finally:
        capture.close()


def test_solver_stays_cheap_enough_for_the_compute_lane():
    import time
    shards = fracture_cells(417, 180, ASPECT)
    best = math.inf
    for _ in range(3):
        start = time.perf_counter()
        solve_glass_pieces(shards, ASPECT, "left", 1.0, 417, collisions=True, reshatter=True)
        best = min(best, time.perf_counter() - start)
    assert best < 0.25
