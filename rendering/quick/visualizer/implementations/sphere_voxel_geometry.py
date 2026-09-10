"""Pure static geometry for the experimental voxel Sphere renderer.

The module owns no OpenGL state.  It stays local to the experimental mode so it
can disappear with the mode; a later independent 3D consumer may justify
extracting an identical cube/instance seam.
"""
from __future__ import annotations

import math

import numpy as np


VOXEL_SHELL_RADIUS = 5
VOXEL_SHELL_THICKNESS = 0.75
VOXEL_HALF_EXTENT = 0.090
VOXEL_VERTEX_STRIDE_FLOATS = 6
# xyz centre + deterministic visual seed + local radial polarity.
VOXEL_INSTANCE_STRIDE_FLOATS = 5


def _face(
    corners: tuple[tuple[float, float, float], ...],
    normal: tuple[float, float, float],
) -> tuple[float, ...]:
    values: list[float] = []
    for index in (0, 1, 2, 0, 2, 3):
        values.extend((*corners[index], *normal))
    return tuple(values)


def build_voxel_cube_mesh() -> np.ndarray:
    """Return one unit cube as position+normal triangles."""

    n = 1.0
    values = (
        *_face(((-n, -n, n), (n, -n, n), (n, n, n), (-n, n, n)), (0.0, 0.0, 1.0)),
        *_face(((n, -n, -n), (-n, -n, -n), (-n, n, -n), (n, n, -n)), (0.0, 0.0, -1.0)),
        *_face(((-n, -n, -n), (-n, -n, n), (-n, n, n), (-n, n, -n)), (-1.0, 0.0, 0.0)),
        *_face(((n, -n, n), (n, -n, -n), (n, n, -n), (n, n, n)), (1.0, 0.0, 0.0)),
        *_face(((-n, n, n), (n, n, n), (n, n, -n), (-n, n, -n)), (0.0, 1.0, 0.0)),
        *_face(((-n, -n, -n), (n, -n, -n), (n, -n, n), (-n, -n, n)), (0.0, -1.0, 0.0)),
    )
    return np.ascontiguousarray(values, dtype=np.float32)


def _mix_xyz(x: int, y: int, z: int) -> int:
    return (x * 73856093) ^ (y * 19349663) ^ (z * 83492791)


def _seed_for(x: int, y: int, z: int) -> float:
    return float(_mix_xyz(x, y, z) & 0xFFFF) / 65536.0


def _patch_polarity(x: int, y: int, z: int) -> float:
    """Give neighbouring blocks a stable mostly-outward in/out texture."""

    patch_x, patch_y, patch_z = x // 2, y // 2, z // 2
    mixed = _mix_xyz(patch_x, patch_y, patch_z) & 0xFFFFFFFF
    return 1.0 if (mixed & 0x3) != 0 else -0.62


def build_voxel_shell_instances(
    *,
    radius: int = VOXEL_SHELL_RADIUS,
    thickness: float = VOXEL_SHELL_THICKNESS,
) -> np.ndarray:
    """Return stepped lattice shell centres plus seed/polarity metadata."""

    radius_i = int(radius)
    shell_thickness = float(thickness)
    if radius_i < 2:
        raise ValueError("voxel shell radius must be at least two")
    if not math.isfinite(shell_thickness) or shell_thickness <= 0.0:
        raise ValueError("voxel shell thickness must be finite and positive")

    lower = radius_i - shell_thickness
    upper = radius_i + 0.25
    points: list[tuple[float, float, float, float, float]] = []
    scale = 1.0 / float(radius_i)
    for z in range(-radius_i - 1, radius_i + 2):
        for y in range(-radius_i - 1, radius_i + 2):
            for x in range(-radius_i - 1, radius_i + 2):
                distance = math.sqrt(float(x * x + y * y + z * z))
                if lower <= distance <= upper:
                    points.append((
                        x * scale,
                        y * scale,
                        z * scale,
                        _seed_for(x, y, z),
                        _patch_polarity(x, y, z),
                    ))
    if not points:
        raise RuntimeError("voxel shell generation produced no instances")
    return np.ascontiguousarray(points, dtype=np.float32).reshape(-1)


__all__ = [
    "VOXEL_HALF_EXTENT",
    "VOXEL_INSTANCE_STRIDE_FLOATS",
    "VOXEL_SHELL_RADIUS",
    "VOXEL_SHELL_THICKNESS",
    "VOXEL_VERTEX_STRIDE_FLOATS",
    "build_voxel_cube_mesh",
    "build_voxel_shell_instances",
]
