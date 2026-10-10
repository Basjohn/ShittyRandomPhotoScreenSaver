"""Propagation field (shared primitive, proved on its own, on a real offscreen context, no window):
the GPU's arrival equals the CPU mirror's geodesic arrival, never exceeds the straight-line bound,
starts at each source's head start, runs ahead along a cheap channel (a front fingers rather than
swelling round), the extent is the largest arrival, the build is bounded per step, and release drops
everything."""
from __future__ import annotations

import numpy as np
import pytest

from rendering.quick.scene3d.propagation_field import (
    PROPAGATION_PASSES,
    PROPAGATION_PASSES_PER_STEP,
    PropagationField,
    propagation_reference,
    propagation_size,
)

# A cheap horizontal channel through the middle on otherwise uniform cost 2.
_COST_GLSL = "uniform float uChannel;\nfloat propagationCost(vec2 p) { return abs(p.y) < 0.03 ? uChannel : 2.0; }\n"
_SIZE = (256, 144)
_SOURCES = [(-0.7, 0.0, 0.0), (0.5, 0.3, 0.2)]


def _cost_grid(channel: float) -> np.ndarray:
    columns, rows = propagation_size(_SIZE)
    ys = 0.5 - (np.arange(rows) + 0.5) / rows
    return np.where(np.abs(ys)[:, None] < 0.03, channel, 2.0) * np.ones((rows, columns))


@pytest.fixture
def gl_resources(qt_app):
    from tests.test_scene3d_glsl_mirrors import _GlslProbe
    from rendering.quick.scene3d.resources import MeshResources

    probe = _GlslProbe()
    resources = MeshResources("propagation test")
    yield resources
    resources.release_resources()
    probe.close()


def _read(texture: int, size) -> np.ndarray:
    from OpenGL import GL as gl

    data = np.zeros(size[0] * size[1], dtype=np.float32)
    gl.glGetTextureImage(texture, 0, gl.GL_RED, gl.GL_FLOAT, data.nbytes, data)
    return data.reshape(size[1], size[0])


def _build(resources, channel: float) -> tuple[PropagationField, np.ndarray, float]:
    from OpenGL import GL as gl

    field = PropagationField("test", "test", _COST_GLSL)
    steps = 0
    while not field.build_step(resources, _SIZE, ("k", channel), _SOURCES, 2.0,
                               lambda locate: gl.glUniform1f(locate("uChannel"), channel)):
        steps += 1
        assert steps <= 1 + PROPAGATION_PASSES // PROPAGATION_PASSES_PER_STEP + 1
    arrival, extent = field.textures(resources, _SIZE, ("k", channel), _SOURCES, 2.0, lambda locate: None)
    return field, _read(arrival, propagation_size(_SIZE)), float(_read(extent, (1, 1))[0, 0])


@pytest.mark.qt
def test_the_gpu_arrival_matches_the_cpu_geodesic_and_fingers_along_a_channel(gl_resources):
    field, gpu, extent = _build(gl_resources, 0.3)
    cpu = propagation_reference(_cost_grid(0.3), _SOURCES, 2.0, passes=4 * PROPAGATION_PASSES)
    assert np.abs(gpu - cpu).mean() < 0.01 * cpu.mean() and np.abs(gpu - cpu).max() < 0.06 * cpu.max()
    assert extent == pytest.approx(float(gpu.max()))
    # Never above the straight-line bound, and zero-ish at the first source.
    rows, columns = gpu.shape
    xs = ((np.arange(columns) + 0.5) / columns - 0.5) * (columns / rows)
    ys = 0.5 - (np.arange(rows) + 0.5) / rows
    px, py = np.meshgrid(xs, ys)
    bound = np.minimum.reduce([head + 2.0 * np.hypot(px - x, py - y) for x, y, head in _SOURCES])
    assert (gpu <= bound + 1e-4).all()
    assert gpu.min() < 0.02
    # Along the channel the dye arrives far sooner than the same distance off it.
    middle, off = rows // 2, rows // 2 - 20
    assert gpu[middle, columns // 2] < 0.6 * gpu[off, columns // 2]
    field.release()
    assert not field.has_resources


@pytest.mark.qt
def test_without_a_channel_the_front_is_round(gl_resources):
    _field, flat, _extent = _build(gl_resources, 2.0)
    rows, columns = flat.shape
    xs = ((np.arange(columns) + 0.5) / columns - 0.5) * (columns / rows)
    ys = 0.5 - (np.arange(rows) + 0.5) / rows
    px, py = np.meshgrid(xs, ys)
    straight = np.minimum.reduce([head + 2.0 * np.hypot(px - x, py - y) for x, y, head in _SOURCES])
    assert np.abs(flat - straight).max() < 0.03 * straight.max()
