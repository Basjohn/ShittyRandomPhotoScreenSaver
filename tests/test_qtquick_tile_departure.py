"""Focused geometry and departure regressions for Exploding Tiles."""

from __future__ import annotations

from collections import Counter
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from tools.transition_contact_sheet import TransitionCapture


ROOT = Path(__file__).resolve().parents[1]


def _effect():
    spec = importlib.util.spec_from_file_location(
        "_tile_departure", ROOT / "rendering/gl_programs/exploding_tiles_program.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _slab_positions(
    vertices: tuple[float, ...], stride: int
) -> list[tuple[float, ...]]:
    return [
        tuple(round(component, 6) for component in vertices[index : index + 3])
        for index in range(0, len(vertices), stride)
    ]


def test_beveled_slab_is_closed_and_encloses_positive_volume():
    effect = _effect()
    positions = _slab_positions(
        effect.exploding_tiles_box_vertices(),
        effect.EXPLODING_TILES_VERTEX_STRIDE_FLOATS,
    )
    edges: Counter[tuple[tuple[float, ...], tuple[float, ...]]] = Counter()
    signed_volume = 0.0
    for index in range(0, len(positions), 3):
        first, second, third = positions[index : index + 3]
        for start, end in ((first, second), (second, third), (third, first)):
            assert start != end
            edges[tuple(sorted((start, end)))] += 1
        signed_volume += (
            sum(
                first[axis]
                * (
                    second[(axis + 1) % 3] * third[(axis + 2) % 3]
                    - second[(axis + 2) % 3] * third[(axis + 1) % 3]
                )
                for axis in range(3)
            )
            / 6.0
        )

    # Each geometric edge is shared by two outward faces. This rejects a raised
    # lip or an open back even when a front-facing contact sheet looks plausible.
    assert set(edges.values()) == {2}
    assert signed_volume > 0.9
    assert {position[2] for position in positions} == {-0.5, -0.38, 0.38, 0.5}


def test_source_plane_and_normals_remain_continuous_until_release():
    effect = _effect()
    source = effect.EXPLODING_TILES_VERTEX_SOURCE
    phases = [
        effect.exploding_tile_state(progress, 0.17)
        for progress in (0.17, 0.45, 0.76, 0.98)
    ]

    assert phases == sorted(phases)
    assert phases[0] == 0.0 and phases[-1] == pytest.approx(1.0)
    assert "aPosition.z*slabDepth" in source
    assert "vec3(aNormal.x,-aNormal.y,aNormal.z)" in source
    assert "exitDistance=min(edge.x,edge.y)" in source
    assert "10.0" not in source
    assert "shrink" not in source.lower()


@pytest.mark.qt
@pytest.mark.parametrize("size", ((160, 480), (720, 180)))
def test_weak_force_geometry_clears_portrait_and_wide_viewports_before_retirement(
    qt_app, size
):
    capture = TransitionCapture(*size)
    try:
        destination = np.asarray(capture.images[1], dtype=np.int16)
        parameters = {"force": 0.5, "thickness": 1.0, "depth": 1.5}
        for direction in ("left", "up", "center_out"):
            run = capture.run(
                "exploding_tiles", direction=direction, parameters=parameters
            )
            late_frame = np.asarray(capture.render(run, 0.98)[0], dtype=np.int16)
            assert np.abs(late_frame - destination).mean() < 0.5, (size, direction)
    finally:
        capture.close()
