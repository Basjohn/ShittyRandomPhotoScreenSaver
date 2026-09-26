"""Crumble slab collisions: baked once per run, analytic on the GPU, off by default."""
from __future__ import annotations

from copy import deepcopy
import time

import numpy as np
import pytest

from rendering.quick.transitions import crumble_dynamics as cd
from rendering.quick.transitions.fracture_geometry import crumble_cells
from rendering.quick.transitions.run_geometry import (
    CRUMBLE_DEBRIS_STRIDE,
    build_crumble_geometry,
    crumble_geometry_key,
)
from tools.transition_contact_sheet import TransitionCapture

ASPECT = 16 / 9
BASE = {"seed": 713.0, "piece_count": 45, "crack_complexity": 1.8, "weight_mode": 3.0,
        "depth": 0.45, "thickness": 0.15, "debris": 0.85}


def _deep_overlaps(shards, motions, table, depth: float) -> int:
    """Samples where two moving, on-screen slabs sit well inside each other."""
    wall = cd._Wall(shards, motions, ASPECT, depth, 0.15)
    rest = np.stack((wall.cx, wall.cy), 1)
    gap = np.linalg.norm(rest[:, None] - rest[None], axis=2)
    reach = cd._XY_REACH * wall.radius
    limit = np.minimum(reach[:, None] + reach[None], cd._REST_GAP * gap)
    upper = np.triu(np.ones((len(shards),) * 2, bool), 1)
    total = 0
    for t in np.linspace(0.0, 0.9, 91):
        f = t / cd.PATH_END * (cd.MOTION_FRAMES - 1)
        k0, w = int(f), f - int(f)
        m = table[:, k0] * (1 - w) + table[:, min(k0 + 1, cd.MOTION_FRAMES - 1)] * w
        base, _v, angle, local = wall.state(t)
        position = base + m[:, :3]
        extent = wall.out_extent(local, angle + m[:, 3])
        moving, seen = t > wall.begin, wall.on_screen(position)
        d = position[None] - position[:, None]
        planar = np.hypot(d[..., 0], d[..., 1])
        total += int((upper & (planar < 0.75 * limit)
                      & (np.abs(d[..., 2]) < extent[:, None] + extent[None])
                      & moving[:, None] & moving[None] & (seen[:, None] | seen[None])).sum())
    return total


def test_release_motions_are_seeded_and_follow_the_weighting():
    shards = crumble_cells(713.0, 45, ASPECT, 1.8)
    first = cd.release_motions(shards, 713.0, 0.0)
    assert first == cd.release_motions(shards, 713.0, 0.0)
    assert first != cd.release_motions(shards, 714.0, 0.0)
    for motion in first:
        assert 0.28 <= motion.begin <= 0.60
        assert abs(np.linalg.norm(motion.axis) - 1.0) < 1e-9
    # Top first: higher chunks (smaller v) release earlier, within the jitter.
    top = [m.begin for s, m in zip(shards, first) if s.center[1] < 0.3]
    bottom = [m.begin for s, m in zip(shards, first) if s.center[1] > 0.7]
    assert max(top) < min(bottom)
    flipped = cd.release_motions(shards, 713.0, 1.0)
    assert np.mean([m.begin for s, m in zip(shards, flipped) if s.center[1] > 0.7]) < np.mean(top + [0.6])


def test_without_collisions_the_table_is_still_and_debris_breaks_off_with_its_chunk():
    geometry = build_crumble_geometry(crumble_geometry_key(BASE, ASPECT))
    table = np.frombuffer(geometry.motion, dtype=np.float32)
    assert table.size == geometry.chunk_count * cd.MOTION_FRAMES * 4 and not table.any()
    rows = np.frombuffer(geometry.chunks, dtype=np.float32).reshape(-1, 22)
    begin_by_row = {int(row): float(begin) for begin, row in zip(rows[:, 15], rows[:, 17])}
    assert sorted(begin_by_row) == list(range(geometry.chunk_count))
    chips = np.frombuffer(geometry.debris, dtype=np.float32).reshape(-1, CRUMBLE_DEBRIS_STRIDE)
    assert {round(float(v), 6) for v in chips[:, 6]} <= {round(b, 6) for b in begin_by_row.values()}


def test_depth_and_thickness_only_key_the_geometry_when_collisions_are_on():
    off = crumble_geometry_key(BASE, ASPECT)
    assert off == crumble_geometry_key({**BASE, "depth": 1.2, "thickness": 0.9}, ASPECT)
    on = crumble_geometry_key({**BASE, "collisions": True}, ASPECT)
    assert on != off
    assert on != crumble_geometry_key({**BASE, "collisions": True, "depth": 1.2}, ASPECT)


@pytest.mark.parametrize("depth", (0.2, 0.45, 1.0))
def test_collisions_stop_slabs_passing_through_each_other(depth):
    before = after = 0
    for seed in (713.0, 12.5):
        shards = crumble_cells(seed, 45, ASPECT, 1.8)
        still = cd.release_motions(shards, seed, 3.0)
        released, table = cd.bake_crumble_motion(shards, still, ASPECT, depth, 0.15, seed)
        before += _deep_overlaps(shards, still, cd.still_motion_table(len(shards)), depth)
        after += _deep_overlaps(shards, released, table, depth)
    assert before > 200
    assert after <= 0.05 * before, (before, after)


def test_a_struck_standing_slab_is_knocked_loose_and_its_debris_follows():
    knocked = 0
    for seed in (713.0, 12.5, 404.4, 88.8, 5.5, 250.0):
        params = {**BASE, "seed": seed, "depth": 0.2, "collisions": True}
        shards = crumble_cells(seed, 45, ASPECT, 1.8)
        still = cd.release_motions(shards, seed, 3.0)
        released, table = cd.bake_crumble_motion(shards, still, ASPECT, 0.2, 0.15, seed)
        early = [i for i, (a, b) in enumerate(zip(still, released)) if b.begin < a.begin - 1e-9]
        frames = np.linspace(0.0, cd.PATH_END, cd.MOTION_FRAMES)
        for index in early:
            # It stood still in the wall until the blow.
            assert not table[index, frames < released[index].begin - 1e-6, :3].any()
        knocked += len(early)
        geometry = build_crumble_geometry(crumble_geometry_key(params, ASPECT))
        chips = np.frombuffer(geometry.debris, dtype=np.float32).reshape(-1, CRUMBLE_DEBRIS_STRIDE)
        releases = {round(float(m.begin), 5) for m in released}
        assert {round(float(v), 5) for v in chips[:, 6]} <= releases
    assert knocked > 0


@pytest.mark.parametrize("pieces", (12, 45, 128))
def test_every_chunk_still_leaves_the_frame(pieces):
    for seed in (713.0, 12.5):
        shards = crumble_cells(seed, pieces, ASPECT, 1.8)
        released, table = cd.bake_crumble_motion(
            shards, cd.release_motions(shards, seed, 3.0), ASPECT, 0.45, 0.15, seed)
        wall = cd._Wall(shards, released, ASPECT, 0.45, 0.15)
        end = wall.state(cd.PATH_END)[0] + table[:, -1, :3]
        assert not wall.on_screen(end).any()


def test_baked_motion_is_continuous_and_deterministic():
    shards = crumble_cells(713.0, 96, ASPECT, 1.8)
    still = cd.release_motions(shards, 713.0, 3.0)
    first = cd.bake_crumble_motion(shards, still, ASPECT, 0.45, 0.15, 713.0)
    second = cd.bake_crumble_motion(shards, still, ASPECT, 0.45, 0.15, 713.0)
    assert first[0] == second[0] and np.array_equal(first[1], second[1])
    step = np.abs(np.diff(first[1][:, :, :3], axis=1)).max()
    assert step < 0.12  # scene units per keyframe (1.5% of the transition)


def test_the_bake_stays_cheap_enough_for_the_compute_lane():
    shards = crumble_cells(713.0, 128, ASPECT, 1.8)
    still = cd.release_motions(shards, 713.0, 3.0)
    best = float("inf")
    for _ in range(3):
        start = time.perf_counter()
        cd.bake_crumble_motion(shards, still, ASPECT, 0.45, 0.15, 713.0)
        best = min(best, time.perf_counter() - start)
    assert best < 0.25


@pytest.mark.qt
def test_collisions_render_change_the_collapse_and_keep_exact_endpoints(qt_app):
    params = {**BASE, "weight_mode": 0.0}
    geometry = build_crumble_geometry(crumble_geometry_key({**params, "collisions": True}, 320 / 180))
    table = np.frombuffer(geometry.motion, dtype=np.float32).reshape(-1, cd.MOTION_FRAMES, 4)
    moving_frames = np.flatnonzero(np.abs(table).max(axis=(0, 2)) > 0)
    first_contact = moving_frames[0] * cd.PATH_END / (cd.MOTION_FRAMES - 1)
    capture = TransitionCapture(320, 180)
    try:
        source, destination = (np.asarray(i, dtype=np.int16) for i in capture.images)
        plain = capture.run("crumble", seed=713, parameters=params)
        colliding = capture.run("crumble", seed=713, parameters={**params, "collisions": True})
        after_contact = min(0.9, first_contact + 0.08)
        a = np.asarray(capture.render(plain, after_contact)[0], dtype=np.int16)
        b = np.asarray(capture.render(colliding, after_contact)[0], dtype=np.int16)
        assert np.abs(a - b).mean() > 1.0
        early = min(0.29, first_contact - 0.01)
        assert np.array_equal(np.asarray(capture.render(plain, early)[0]),
                              np.asarray(capture.render(colliding, early)[0]))
        for progress, expected in ((0.0001, source), (0.9999, destination)):
            frame = np.asarray(capture.render(colliding, progress)[0], dtype=np.int16)
            assert np.abs(frame - expected).mean() < 0.5, progress
        # No pops through the contacts: a jump keeps its size however small the
        # step, while continuous (if faster) motion shrinks with it.
        def change(t, h):
            before = np.asarray(capture.render(colliding, t - h)[0], dtype=np.int16)
            after = np.asarray(capture.render(colliding, t + h)[0], dtype=np.int16)
            return float(np.abs(before - after).mean())

        # Sweep a quarter keyframe at a time so every keyframe boundary is hit.
        spacing = cd.PATH_END / (cd.MOTION_FRAMES - 1)
        for t in np.arange(first_contact, min(0.95, first_contact + 0.12), spacing / 4):
            wide, narrow = change(t, spacing / 8), change(t, spacing / 64)
            assert narrow <= 0.35 * wide + 0.05, (t, wide, narrow)
    finally:
        capture.close()


@pytest.mark.qt
def test_the_motion_table_is_released_with_the_renderer(qt_app):
    from rendering.quick.transitions.implementations.crumble import QuickCrumbleRenderer

    capture = TransitionCapture(160, 90)
    try:
        capture.render(capture.run("crumble", seed=713, parameters={**BASE, "collisions": True}), 0.5)
        renderer = capture.host._renderers.get("crumble") if hasattr(capture.host, "_renderers") else None
        if renderer is None:
            renderer = QuickCrumbleRenderer()
            renderer.render(capture.frame(capture.run("crumble", seed=713,
                                                      parameters={**BASE, "collisions": True}), 0.5))
        assert renderer._motion_texture
        renderer.release_resources()
        assert not renderer._motion_texture and not renderer.has_resources
    finally:
        capture.close()


def test_crumble_collision_option_loads_and_persists(qapp, settings_manager, qtbot):
    from ui.tabs.transitions_tab import TransitionsTab

    transitions = deepcopy(settings_manager.get("transitions", {}))
    crumble = dict(transitions.get("crumble") or {})
    crumble["collisions"] = True
    transitions["crumble"] = crumble
    transitions.setdefault("activation", {})["Crumble"] = True
    settings_manager.set("transitions", transitions)

    tab = TransitionsTab(settings_manager)
    qtbot.addWidget(tab)
    tab._on_nav_selected("Crumble")
    assert tab.crumble_collisions_check.isChecked()

    tab.crumble_collisions_check.setChecked(False)
    tab._save_settings()
    assert settings_manager.get("transitions", {})["crumble"]["collisions"] is False
