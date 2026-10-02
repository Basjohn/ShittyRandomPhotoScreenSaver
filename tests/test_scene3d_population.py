"""The compacted GPU population (S16/S18) on a real offscreen context (no window).

Live members, their slots and states equal a CPU reference exactly and in id order (stable
across frames and membership changes); the GPU-written indirect command draws exactly the
live members with no count read back by the runtime; capacity is fixed and loud; every
dispatch is followed by the barrier its reader needs; bindings come back; a population nobody
uses owns nothing; release returns to zero and rebuilds. Readbacks here are test-only.
"""
from __future__ import annotations

import ctypes

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.scene3d import SCENE3D_GLSL, scene3d_random
from rendering.quick import gl_query
from rendering.quick.render.gl_resources import compile_program
from rendering.quick.scene3d import population as population_module
from rendering.quick.scene3d.population import (
    POPULATION_DRAW_GLSL,
    POPULATION_FIRST_BINDING,
    POPULATION_GROUP,
    CompactedPopulation,
)
from rendering.quick.scene3d.resources import MeshResources
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt

_HOOKS = SCENE3D_GLSL + """
uniform float uThreshold;
uniform uint uSeed;
bool populationActive(uint id) { return sceneRandom(id, 1u, uSeed) < uThreshold; }
vec4 populationState(uint id) { return vec4(float(id), sceneRandom(id, 2u, uSeed), uThreshold, 1.0); }
"""


def _live(population: int, threshold: float, seed: int) -> list[int]:
    return [i for i in range(population) if scene3d_random(i, 1, seed) < threshold]


def _configure(threshold: float, seed: int):
    def configure(key, program):
        gl.glUniform1f(gl.glGetUniformLocation(program, "uThreshold"), threshold)
        gl.glUniform1ui(gl.glGetUniformLocation(program, "uSeed"), seed)
    return configure


def _read(buffer: int, count: int, dtype) -> np.ndarray:
    gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)       # this test-only readback follows shader writes
    out = np.zeros(count, dtype=dtype)
    if count:
        gl.glGetNamedBufferSubData(buffer, 0, out.nbytes, out)
    return out


@pytest.fixture
def context(qt_app):
    capture = TransitionCapture(16, 16)
    yield capture
    capture.close()


@pytest.mark.parametrize("population,threshold", ((1, 1.0), (255, 0.5), (256, 0.0), (POPULATION_GROUP * 37 + 11, 0.3),
                                                  (300_000, 0.12)))
def test_live_members_their_slots_states_and_count_match_the_reference(context, population, threshold):
    resources = MeshResources("population test")
    pool = CompactedPopulation("population test")
    try:
        assert pool.warm(population) is False and pool.warm(population) is True
        expected = _live(population, threshold, 77)
        with pool.bound():
            pool.update(resources, "probe", _HOOKS, population, 4, _configure(threshold, 77))
        names = pool._names
        command = _read(names[POPULATION_FIRST_BINDING + 2], 4, np.uint32)
        assert list(command) == [4, len(expected), 0, 0]
        ids = _read(names[POPULATION_FIRST_BINDING + 3], len(expected), np.uint32)
        assert ids.tolist() == expected                                    # every live member, in id order
        states = _read(names[POPULATION_FIRST_BINDING + 4], 4 * len(expected), np.float32).reshape(-1, 4)
        if expected:
            assert np.array_equal(states[:, 0], np.asarray(expected, np.float32))
            assert np.allclose(states[:, 1], [scene3d_random(i, 2, 77) for i in expected], atol=1e-6)
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        pool.release()
        resources.release_resources()


def test_membership_changes_keep_survivors_in_order(context):
    resources = MeshResources("population order test")
    pool = CompactedPopulation("population order test")
    try:
        pool.warm(20_000)
        orders = []
        for threshold in (0.5, 0.3, 0.5):
            with pool.bound():
                pool.update(resources, "probe", _HOOKS, 20_000, 4, _configure(threshold, 9))
            orders.append(_read(pool._names[POPULATION_FIRST_BINDING + 3], len(_live(20_000, threshold, 9)),
                                np.uint32).tolist())
        assert orders[0] == orders[2]                                       # the same membership, the same order
        survivors = set(orders[1])
        assert [i for i in orders[0] if i in survivors] == orders[1]        # dropping members never reorders the rest
    finally:
        pool.release()
        resources.release_resources()


_DRAW_VERTEX = ("#version 460 core\n" + POPULATION_DRAW_GLSL + """
uniform int uWidth;
flat out uint vId;
void main() {
    uint id = populationIds[gl_InstanceID];
    vec2 corner = vec2(gl_VertexID & 1, gl_VertexID >> 1);
    vec2 pixel = vec2(gl_InstanceID % uWidth, gl_InstanceID / uWidth) + corner;
    vId = id;
    gl_Position = vec4(pixel / vec2(uWidth) * 2.0 - 1.0, 0.0, 1.0);
}
""")
_DRAW_FRAGMENT = """#version 460 core
flat in uint vId;
layout(location = 0) out uvec4 Id;
void main() { Id = uvec4(vId + 1u, 0u, 0u, 1u); }
"""


def test_the_indirect_draw_draws_exactly_the_live_members(context):
    width, population, threshold = 64, 6000, 0.4
    expected = _live(population, threshold, 3)
    resources = MeshResources("population draw test")
    pool = CompactedPopulation("population draw test")
    program = compile_program(_DRAW_VERTEX, _DRAW_FRAGMENT, label="population draw probe")
    texture, fbo, vao = int(gl.glGenTextures(1)), int(gl.glGenFramebuffers(1)), int(gl.glGenVertexArrays(1))
    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_R32UI, width, width, 0, gl.GL_RED_INTEGER, gl.GL_UNSIGNED_INT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, texture, 0)
        gl.glClearBufferuiv(gl.GL_COLOR, 0, (ctypes.c_uint * 4)(0, 0, 0, 0))
        gl.glViewport(0, 0, width, width)
        pool.warm(population)
        with pool.bound():
            pool.update(resources, "probe", _HOOKS, population, 4, _configure(threshold, 3))
            gl.glUseProgram(program)
            gl.glUniform1i(gl.glGetUniformLocation(program, "uWidth"), width)
            gl.glBindVertexArray(vao)
            pool.draw(gl.GL_TRIANGLE_STRIP)
        drawn = np.asarray(gl.glReadPixels(0, 0, width, width, gl.GL_RED_INTEGER, gl.GL_UNSIGNED_INT)).reshape(-1)
        assert drawn[:len(expected)].tolist() == [i + 1 for i in expected]
        assert not drawn[len(expected):].any()
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, context.fbo)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([texture])
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)
        pool.release()
        resources.release_resources()


def test_each_dispatch_issues_the_barrier_its_reader_needs(context, monkeypatch):
    events = []
    for name in ("glDispatchCompute", "glMemoryBarrier"):
        original = getattr(gl, name)
        monkeypatch.setattr(gl, name, lambda *args, _n=name, _o=original: (events.append((_n, args)), _o(*args))[1])
    resources = MeshResources("population barrier test")
    pool = CompactedPopulation("population barrier test")
    try:
        pool.warm(1000)
        with pool.bound():
            pool.update(resources, "probe", _HOOKS, 1000, 4, _configure(0.5, 1))
        assert [name for name, _args in events] == ["glDispatchCompute", "glMemoryBarrier"] * 3
        barriers = [args[0] for name, args in events if name == "glMemoryBarrier"]
        assert all(bits & gl.GL_SHADER_STORAGE_BARRIER_BIT for bits in barriers)
        assert barriers[-1] & gl.GL_COMMAND_BARRIER_BIT                   # the indirect draw reads the command
    finally:
        monkeypatch.undo()
        pool.release()
        resources.release_resources()


def test_capacity_is_fixed_and_loud_and_bindings_come_back(context):
    resources = MeshResources("population capacity test")
    pool = CompactedPopulation("population capacity test")
    sentinel, indirect = int(gl.glGenBuffers(1)), int(gl.glGenBuffers(1))
    try:
        gl.glBindBuffer(gl.GL_SHADER_STORAGE_BUFFER, sentinel)
        gl.glBufferData(gl.GL_SHADER_STORAGE_BUFFER, 256, None, gl.GL_STATIC_DRAW)
        gl.glBindBufferRange(gl.GL_SHADER_STORAGE_BUFFER, POPULATION_FIRST_BINDING + 1, sentinel, 64, 32)
        gl.glBindBuffer(gl.GL_DRAW_INDIRECT_BUFFER, indirect)
        pool.warm(500)
        with pytest.raises(RuntimeError, match="capacity"):
            with pool.bound():
                pool.update(resources, "probe", _HOOKS, 501, 4, _configure(0.5, 1))
        assert gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING, POPULATION_FIRST_BINDING + 1) == sentinel
        assert gl_query.get_indexed_int64(gl.GL_SHADER_STORAGE_BUFFER_START, POPULATION_FIRST_BINDING + 1) == 64
        assert gl_query.get_indexed_int(gl.GL_SHADER_STORAGE_BUFFER_BINDING, POPULATION_FIRST_BINDING) == 0
        assert gl_query.get_int(gl.GL_DRAW_INDIRECT_BUFFER_BINDING) == indirect
        with pytest.raises(ValueError):
            pool.warm(0)
    finally:
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, POPULATION_FIRST_BINDING + 1, 0)
        gl.glBindBuffer(gl.GL_DRAW_INDIRECT_BUFFER, 0)
        gl.glDeleteBuffers(2, [sentinel, indirect])
        pool.release()
        resources.release_resources()


def test_an_unused_population_owns_nothing_and_touches_no_gl(monkeypatch):
    for name in ("glCreateBuffers", "glDispatchCompute", "glBindBuffersBase"):
        monkeypatch.setattr(population_module.gl, name, lambda *_a: pytest.fail("dormant population touched GL"))
    pool = CompactedPopulation("dormant population")
    assert not pool.has_resources and pool.capacity == 0
    pool.release()


def test_release_returns_to_zero_and_rebuilds(context):
    resources = MeshResources("population release test")
    pool = CompactedPopulation("population release test")
    try:
        pool.warm(4000)
        first = dict(pool._names)
        pool.release()
        assert not pool.has_resources and not any(gl.glIsBuffer(name) for name in first.values())
        pool.warm(2000)
        with pool.bound():
            pool.update(resources, "probe", _HOOKS, 2000, 4, _configure(0.25, 4))
        assert _read(pool._names[POPULATION_FIRST_BINDING + 2], 4, np.uint32)[1] == len(_live(2000, 0.25, 4))
    finally:
        pool.release()
        resources.release_resources()
