"""Topology and material contracts for the two reworked organic surfaces."""

from __future__ import annotations

from rendering.gl_programs.tendril_reveal_program import (
    TENDRIL_CANOPY_FRAGMENT,
    TENDRIL_FRAGMENT,
    TENDRIL_VERTEX,
    tendril_branches,
    tendril_canopy_segments,
    tendril_tube_vertices,
)


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


def test_tendrils_have_seeded_parent_branches_and_finite_round_tube_topology():
    first = tendril_branches(713, 1.0)
    assert first == tendril_branches(713, 1.0)
    assert first != tendril_branches(714, 1.0)
    # Every primary is followed by two children rooted on that parent's curve.
    assert len(first) == 15
    assert any(branch.radius < first[0].radius for branch in first[1:])
    vertices = tendril_tube_vertices(first)
    stride = 12
    assert len(vertices) % stride == 0
    assert len(vertices) // stride == len(first) * ((32 - 1) * 16 * 6 + 2 * 16 * 3)
    # Tube vertices contain nonzero signed Z and circular normal components,
    # which distinguishes an actual mesh from feathered 2D stroke quads.
    assert any(
        abs(vertices[index]) > 0.001 for index in range(2, len(vertices), stride)
    )
    assert any(abs(vertices[index]) > 0.1 for index in range(7, len(vertices), stride))
    assert "layout(location=0) in vec3 aPosition" in TENDRIL_VERTEX
    assert "clip.z=" in TENDRIL_VERTEX
    assert "vNormal" in TENDRIL_FRAGMENT
    assert "uGloss" in TENDRIL_FRAGMENT
    starts, ends = tendril_canopy_segments(first)
    assert len(starts) == len(ends) == len(first) * 5 * 4
    assert starts[:2] == first[0].root
    assert "uSegmentsA[105]" in TENDRIL_CANOPY_FRAGMENT
    assert "uSegmentsB[105]" in TENDRIL_CANOPY_FRAGMENT


def test_tendril_canopy_is_a_bounded_branch_coupled_continuation_not_a_terminal_cut(
    qt_app,
):
    from tools.transition_contact_sheet import TransitionCapture
    import numpy as np

    capture = TransitionCapture(256, 144)
    try:
        run = capture.run("tendril_reveal")
        frames = [
            np.asarray(capture.render(run, progress)[0], dtype=np.int16)
            for progress in (0.95, 0.969, 0.971, 0.979, 0.981, 0.99)
        ]
        destination = np.asarray(capture.images[1], dtype=np.int16)
        # The late frames converge without a destination branch jump.  The
        # canopy remains rendered from its bounded branch field until endpoint.
        assert all(np.abs(frame - destination).mean() < 8.0 for frame in frames)
        assert (
            max(
                np.abs(after - before).mean()
                for before, after in zip(frames, frames[1:])
            )
            < 5.0
        )
    finally:
        capture.close()
