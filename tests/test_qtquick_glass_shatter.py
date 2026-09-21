"""Fracture coverage and context-resource regression bars for real mesh effects."""
from __future__ import annotations

import math

import pytest

from rendering.quick.transitions.fracture_geometry import fracture_cells, fracture_vertices
from rendering.quick.transitions import mesh_support


def _area(polygon):
    return abs(sum(a[0]*b[1]-b[0]*a[1]
                   for a, b in zip(polygon, (*polygon[1:], polygon[0])))) * .5


@pytest.mark.parametrize("aspect", [.3, 1.0, 16/9, 4.0])
@pytest.mark.parametrize("count", [24, 90, 180])
def test_fracture_is_repeatable_gap_free_bounded_and_convex(aspect, count):
    cells = fracture_cells(713, count, aspect)
    assert cells == fracture_cells(713, count, aspect)
    assert cells != fracture_cells(714, count, aspect)
    assert len(cells) == count
    assert sum(_area(cell.polygon) for cell in cells) == pytest.approx(1.0, abs=1e-12)
    for cell in cells:
        assert _area(cell.polygon) > 0.0
        cx, cy = cell.center
        for a, b in zip(cell.polygon, (*cell.polygon[1:], cell.polygon[0])):
            assert 0 <= a[0] <= 1 and 0 <= a[1] <= 1
            assert (b[0]-a[0])*(cy-a[1])-(b[1]-a[1])*(cx-a[0]) >= -1e-12
    vertices = fracture_vertices(cells, aspect)
    assert len(vertices) % 36 == 0
    assert all(math.isfinite(v) for v in vertices)
    # Closed bevel/wall/back geometry stays linear in the planar subdivision.
    assert len(vertices) // 12 < count * 192
    rows = [vertices[i:i+12] for i in range(0, len(vertices), 12)]
    assert {row[9] for row in rows} == {0., 1., 2., 3.}
    assert {row[4] for row in rows} == {0., -.22, -.78, -1.}


def test_fracture_hard_cap_and_global_random_independence():
    import random
    before = random.getstate()
    assert len(fracture_cells(1, 10_000, 1.7)) == 180
    assert random.getstate() == before


def test_each_fracture_prism_is_closed_with_real_side_volume():
    from collections import Counter
    import numpy as np

    for shard in fracture_cells(713, 24, 16/9):
        rows = np.asarray(fracture_vertices((shard,), 16/9)).reshape(-1, 12)
        inset = 1. - .07 * rows[:, 8] * .55
        points = np.column_stack(((rows[:, 0]-rows[:, 2]) * (16/9) * inset,
                                  (rows[:, 3]-rows[:, 1]) * inset,
                                  rows[:, 4] * rows[:, 11] * .65 * .55))
        triangles = points.reshape(-1, 3, 3)
        edges = Counter()
        for triangle in triangles:
            for a, b in zip(triangle, (triangle[1], triangle[2], triangle[0])):
                edges[tuple(sorted((tuple(a.round(9)), tuple(b.round(9)))))] += 1
        assert set(edges.values()) == {2}, "an open sheet cannot show a solid broken edge"
        volume = np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum()/6
        assert volume > 0., "closed outward winding must enclose actual volume"


class _DepthGL:
    GL_SCISSOR_TEST = 1
    GL_SCISSOR_BOX = 2
    GL_TRUE = 1
    GL_DEPTH_BUFFER_BIT = 3
    GL_DEPTH_TEST = 4
    GL_LESS = 5

    def __init__(self, enabled, fail=False):
        self.enabled = enabled
        self.box = (20, 10, 100, 70)
        self.cleared = None
        self.fail = fail

    def glIsEnabled(self, _): return self.enabled
    def glGetIntegerv(self, _): return self.box
    def glDepthMask(self, _): pass
    def glClearDepth(self, _): pass
    def glDepthFunc(self, _): pass
    def glEnable(self, capability):
        if capability == self.GL_SCISSOR_TEST: self.enabled = True
    def glDisable(self, capability):
        if capability == self.GL_SCISSOR_TEST: self.enabled = False
    def glScissor(self, *box): self.box = box
    def glClear(self, _):
        self.cleared = self.box
        if self.fail: raise RuntimeError("injected clear failure")


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("fail", [False, True])
def test_depth_clear_is_bounded_and_restores_scissor_on_failure(monkeypatch, enabled, fail):
    from types import SimpleNamespace
    fake = _DepthGL(enabled, fail)
    monkeypatch.setattr(mesh_support, "gl", fake)
    frame = SimpleNamespace(viewport=(5, 5, 70, 60))
    if fail:
        with pytest.raises(RuntimeError, match="injected"):
            mesh_support.MeshResources.begin_depth(frame)
    else:
        mesh_support.MeshResources.begin_depth(frame)
    assert fake.cleared == ((20, 10, 55, 55) if enabled else frame.viewport)
    assert fake.enabled == enabled
    assert fake.box == (20, 10, 100, 70)


def test_mesh_cleanup_retains_only_failed_handles_for_retry(monkeypatch):
    from types import SimpleNamespace
    deleted = []
    failures = {8}

    def delete_vao(_count, handles):
        if handles[0] in failures:
            raise RuntimeError("injected deletion failure")
        deleted.append(("vao", handles[0]))

    monkeypatch.setattr(mesh_support, "gl", SimpleNamespace(
        glDeleteBuffers=lambda count, handles: deleted.append(("vbo", handles[0])),
        glDeleteVertexArrays=delete_vao,
        glDeleteProgram=lambda handle: deleted.append(("program", handle)),
    ))
    resources = mesh_support.MeshResources("test")
    resources._meshes["fixture"] = (8, 9, 3)
    resources._programs["fixture"] = 10
    with pytest.raises(RuntimeError, match="cleanup incomplete"):
        resources.release_resources()
    assert resources.has_resources
    assert resources._meshes["fixture"] == (8, 0, 3)
    assert not resources._programs
    failures.clear()
    resources.release_resources()
    resources.release_resources()
    assert not resources.has_resources
    assert deleted == [("vbo", 9), ("program", 10), ("vao", 8)]
