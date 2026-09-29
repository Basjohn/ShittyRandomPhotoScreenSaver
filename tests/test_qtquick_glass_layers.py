"""Glass shards keep from passing through each other: depth layers solved per run.

The measure replicates GLASS_VERTEX for each shard's mid-plane polygon (the
prisms are thin) and counts on-screen moments where two shards' polygons cross.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from rendering.quick.transitions.fracture_geometry import fracture_cells
from rendering.quick.transitions.glass_dynamics import LAYER_RANGE, _Paths, separation_layers, solve_glass_pieces

_ASPECT = 16 / 9


def _rotate(points, axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    return points * c + np.cross(axis, points) * s + np.outer(points @ axis, axis) * (1 - c)


def _crosses(a, b) -> bool:
    normal = np.cross(a[1] - a[0], a[2] - a[0])
    normal /= np.linalg.norm(normal)
    d = (b - a[0]) @ normal
    for k in range(len(b)):
        dp, dq = d[k], d[(k + 1) % len(b)]
        if dp * dq >= 0:
            continue
        x = b[k] + (b[(k + 1) % len(b)] - b[k]) * (dp / (dp - dq))
        signs = [np.dot(np.cross(a[(m + 1) % len(a)] - a[m], x - a[m]), normal) for m in range(len(a))]
        if all(value >= 0 for value in signs) or all(value <= 0 for value in signs):
            return True
    return False


def _on_screen_intersections(seed: int, direction: str, layers) -> int:
    shards = fracture_cells(seed, 95, _ASPECT)
    paths = _Paths(shards, _ASPECT, direction, 1.0)
    shapes = []
    for shard in shards:
        v = shard.variation
        axis = np.array((math.cos(v * 37.0), math.sin(v * 29.0), 0.18 * math.sin(v * 17.0)))
        shapes.append((axis / np.linalg.norm(axis), (3.8 + 4.5 * v) * 1.15,
                       np.array([((x - shard.center[0]) * _ASPECT, shard.center[1] - y, 0.0) for x, y in shard.polygon])))
    times = np.linspace(0.02, 0.98, 25)
    centres = paths.at(times)
    hits = 0
    for step, t in enumerate(times):
        local = np.clip((t - paths.delay) / (0.98 - paths.delay), 0.0, 1.0)
        ramp = np.clip(local / 0.10, 0.0, 1.0)
        ramp = ramp * ramp * (3 - 2 * ramp)
        lift = layers * ramp
        z = centres[:, step, 2] + lift
        scale = 3.0 / (3.0 - z)
        sx, sy = centres[:, step, 0] / _ASPECT * scale + 0.5, -centres[:, step, 1] * scale + 0.5
        on = (sx > 0) & (sx < 1) & (sy > 0) & (sy < 1)
        world = [_rotate(deltas, axis, local[i] * rate) + centres[i, step] + np.array((0.0, 0.0, lift[i]))
                 for i, (axis, rate, deltas) in enumerate(shapes)]
        for i in range(len(shards)):
            for j in range(i + 1, len(shards)):
                if local[i] <= 0 or local[j] <= 0 or not (on[i] or on[j]):
                    continue
                if np.linalg.norm(world[i].mean(axis=0) - world[j].mean(axis=0)) > paths.radius[i] + paths.radius[j]:
                    continue
                hits += _crosses(world[i], world[j]) or _crosses(world[j], world[i])
    return hits


@pytest.mark.parametrize("seed,direction", ((713, "center_out"), (1234, "diag_tl_br")))
def test_depth_layers_keep_most_shards_from_passing_through_each_other(seed, direction):
    shards = fracture_cells(seed, 95, _ASPECT)
    layers = separation_layers(_Paths(shards, _ASPECT, direction, 1.0))
    assert np.all(np.abs(layers) <= LAYER_RANGE + 1e-9) and np.any(layers != 0.0)
    before = _on_screen_intersections(seed, direction, np.zeros(len(shards)))  # negative control
    after = _on_screen_intersections(seed, direction, layers)
    assert before > 50
    assert after <= 0.35 * before, (before, after)


def test_crash_partners_share_a_layer_and_split_pieces_keep_theirs():
    shards = fracture_cells(713, 95, _ASPECT)
    paths = _Paths(shards, _ASPECT, "left", 1.0)
    layers = separation_layers(paths, ((3, 40), (7, 8)))
    assert layers[3] == layers[40] and layers[7] == layers[8]
    pieces = solve_glass_pieces(shards, _ASPECT, "left", 1.0, 713, collisions=True, reshatter=True)
    by_pivot: dict[tuple[float, float], set[float]] = {}
    for piece in pieces:
        by_pivot.setdefault(piece.pivot_center, set()).add(piece.layer)
    assert all(len(values) == 1 for values in by_pivot.values())
    assert len({value for values in by_pivot.values() for value in values}) > 3
