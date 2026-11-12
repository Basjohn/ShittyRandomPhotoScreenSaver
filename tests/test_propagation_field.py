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
    field = PropagationField("test", "test", _COST_GLSL)
    steps = 0
    # The cost's uniform is a member of the seed's pass block (N1.6), given by name.
    while not field.build_step(resources, _SIZE, ("k", channel), _SOURCES, 2.0, {"uChannel": channel}):
        steps += 1
        assert steps <= 1 + PROPAGATION_PASSES // PROPAGATION_PASSES_PER_STEP + 1
    arrival, extent = field.textures(resources, _SIZE, ("k", channel), _SOURCES, 2.0, {})
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


# A cost that varies everywhere, so a race between neighbouring texels shows in the result.
_VARIED_COST_GLSL = ("uniform float uChannel;\nfloat propagationCost(vec2 p) {"
                     " return abs(p.y) < 0.03 ? uChannel : 2.0 + sin(9.0 * p.x) * cos(7.0 * p.y); }\n")


@pytest.mark.qt
@pytest.mark.parametrize("size", [(1920, 1080), _SIZE])
def test_the_build_is_bit_repeatable_and_independent_of_its_step_split(gl_resources, size):
    """Relax never reads the field it writes (ping-pong), so ten builds of one input are bit-identical, and a build
    split into odd-sized warm-up steps ends bit-identical to one built in a single frame."""
    field = PropagationField("test", "repeat", _VARIED_COST_GLSL)
    sources, cost = [(-0.7, 0.0, 0.0), (0.5, 0.3, 0.2), (0.1, -0.35, 0.05)], {"uChannel": 0.3}
    try:
        runs = []
        for run in range(10):
            arrival, extent = field.textures(gl_resources, size, ("repeat", run), sources, 2.6, cost)
            runs.append((_read(arrival, propagation_size(size)), _read(extent, (1, 1))))
        differing = [index for index, (arrival, extent) in enumerate(runs)
                     if arrival.tobytes() != runs[0][0].tobytes() or extent.tobytes() != runs[0][1].tobytes()]
        assert differing == [], (f"runs {differing} differ from run 0 in up to "
                                 f"{max(np.count_nonzero(a != runs[0][0]) for a, _ in runs)} values")
        while not field.build_step(gl_resources, size, ("split",), sources, 2.6, cost, passes=37):
            pass
        arrival, extent = field.textures(gl_resources, size, ("split",), sources, 2.6, cost)
        assert _read(arrival, propagation_size(size)).tobytes() == runs[0][0].tobytes()
        assert _read(extent, (1, 1)).tobytes() == runs[0][1].tobytes()
    finally:
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
