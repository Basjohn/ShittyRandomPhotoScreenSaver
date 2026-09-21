"""Topology and material contracts for the two reworked organic surfaces."""

from __future__ import annotations

def test_ink_surface_is_gap_free_and_bounded_across_aspects():
    from rendering.gl_programs.ink_bloom_program import ink_surface_vertices
    import numpy as np

    for aspect in (0.28, 1.0, 16 / 9, 4.0):
        vertices = np.asarray(ink_surface_vertices(aspect)).reshape(-1, 3, 2)
        assert len(vertices) < 50000
        assert np.isfinite(vertices).all()
        assert vertices.min() == 0.0 and vertices.max() == 1.0
        ab, ac = vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0]
        areas = abs(ab[:, 0] * ac[:, 1] - ab[:, 1] * ac[:, 0]) * 0.5
        assert abs(areas.sum() - 1.0) < 1e-10
        assert (areas > 0.0).all()

