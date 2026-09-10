from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


def _load_geometry_module():
    path = (
        Path(__file__).resolve().parents[1]
        / "rendering/quick/visualizer/implementations/sphere_voxel_geometry.py"
    )
    spec = importlib.util.spec_from_file_location("_srpss_sphere_voxel_geometry_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_voxel_cube_is_one_static_36_vertex_mesh() -> None:
    geometry = _load_geometry_module()
    mesh = geometry.build_voxel_cube_mesh().reshape(
        -1, geometry.VOXEL_VERTEX_STRIDE_FLOATS
    )
    assert mesh.shape == (36, 6)
    normals = mesh[:, 3:6]
    assert np.allclose(np.linalg.norm(normals, axis=1), 1.0)


def test_voxel_shell_is_deterministic_stepped_and_symmetric() -> None:
    geometry = _load_geometry_module()
    first = geometry.build_voxel_shell_instances().reshape(
        -1, geometry.VOXEL_INSTANCE_STRIDE_FLOATS
    )
    second = geometry.build_voxel_shell_instances().reshape(
        -1, geometry.VOXEL_INSTANCE_STRIDE_FLOATS
    )
    assert np.array_equal(first, second)
    assert first.shape == (278, 5)
    assert np.isfinite(first).all()
    assert ((0.0 <= first[:, 3]) & (first[:, 3] < 1.0)).all()
    polarity_values = np.unique(first[:, 4])
    assert len(polarity_values) == 2
    assert np.isclose(polarity_values[0], -0.62)
    assert np.isclose(polarity_values[1], 1.0)

    centres = first[:, :3]
    radii = np.linalg.norm(centres, axis=1)
    assert radii.min() >= 0.85 - 1e-6
    assert radii.max() <= 1.05 + 1e-6
    assert not np.any(np.all(np.isclose(centres, 0.0), axis=1))

    assert np.allclose(centres * 5.0, np.round(centres * 5.0))
    authored = {tuple(int(round(value * 5.0)) for value in row) for row in centres}
    assert all(tuple(-value for value in row) in authored for row in authored)


def test_voxel_shell_keeps_local_inward_outward_texture_without_frequency_metadata() -> None:
    geometry = _load_geometry_module()
    shell = geometry.build_voxel_shell_instances().reshape(
        -1, geometry.VOXEL_INSTANCE_STRIDE_FLOATS
    )
    polarities = shell[:, 4]
    assert np.count_nonzero(polarities < 0.0) >= 20
    assert np.count_nonzero(polarities > 0.0) >= 100
    assert geometry.VOXEL_INSTANCE_STRIDE_FLOATS == 5
