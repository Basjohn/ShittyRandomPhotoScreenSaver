"""Sphere's shared UBO admission/retirement and driver layout contracts."""
from __future__ import annotations

import ctypes

import pytest
from OpenGL import GL as gl

from rendering.quick.visualizer.implementations.sphere_voxel import (
    QuickSphereVoxelRenderer, _SPHERE_FRAME_BLOCK,
)


def test_dormant_sphere_renderer_does_not_allocate_mesh_target_backdrop_or_stream():
    renderer = QuickSphereVoxelRenderer()
    assert not renderer.has_resources
    assert not renderer._stream.has_resources
    assert renderer._frame_block.layout.size == 1008
    # A shadow/outtake pair writes two copies per scoped pass, inside the
    # canonical bounded ring; no consumer-specific enlarged capacity exists.
    assert 2 * renderer._frame_block.layout.size <= renderer._stream.hold_bytes


@pytest.mark.qt
def test_sphere_programs_use_one_driver_layout_and_release_recreate_the_same_resource_owner(qt_app):
    from tools.transition_contact_sheet import TransitionCapture
    context = TransitionCapture(16, 16)
    renderer = QuickSphereVoxelRenderer()
    try:
        renderer._initialize()
        assert renderer.has_resources
        assert not renderer._stream.has_resources  # attaching programs cannot allocate a stream
        for program in (renderer._program, renderer._shadow_program):
            index = int(gl.glGetUniformBlockIndex(program, _SPHERE_FRAME_BLOCK.name))
            size = (ctypes.c_int * 1)()
            gl.glGetActiveUniformBlockiv(program, index, gl.GL_UNIFORM_BLOCK_DATA_SIZE, size)
            assert size[0] == _SPHERE_FRAME_BLOCK.size
        assert renderer._stream.warm() is False
        buffer = renderer._stream._buffer
        assert gl.glIsBuffer(buffer)
        assert renderer._stream.warm() is True
        assert renderer._stream._buffer == buffer
        renderer.release_resources()
        assert not renderer.has_resources
        assert not gl.glIsBuffer(buffer)
        assert renderer._frame_block._attached == set()
        renderer._initialize()
        assert renderer._program and renderer._shadow_program
        assert not renderer._stream.has_resources
        assert renderer._stream.warm() is False
        assert renderer.has_resources
    finally:
        renderer.release_resources()
        context.close()


@pytest.mark.qt
@pytest.mark.parametrize("outtake", (False, True))
def test_retained_host_releases_sphere_stream_at_mode_boundary_after_bounded_shadow_passes(qt_app, outtake):
    from dataclasses import replace
    from rendering.quick import gl_query
    from rendering.quick.scene3d.uniforms import SCENE3D_UNIFORM_BINDING
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.transition_contact_sheet import TransitionCapture
    from widgets.spotify_visualizer.render_state import SphereParticleCohort, freeze_render_fields
    context = TransitionCapture(480, 270)
    host = QuickVisualizerRenderHost()
    sentinel = int(gl.glGenBuffers(1))
    try:
        gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, sentinel)
        gl.glBufferData(gl.GL_UNIFORM_BUFFER, 512, None, gl.GL_STATIC_DRAW)
        gl.glBindBufferRange(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, sentinel, 256, 128)
        gl.glBindBuffer(gl.GL_UNIFORM_BUFFER, 0)
        snapshot = _build_spectrum_preview_snapshot(width=480, height=270, mode="sphere")
        state = snapshot.logical.mode_state
        state = replace(state, particle_cohorts=tuple(SphereParticleCohort(
            progress=.45, strength=.8, density=.9, section=index, lane=index, outtake=outtake
        ) for index in range(4)), parameters=freeze_render_fields({**dict(state.parameters),
            "scene3d_detail": "High", "sphere_shadow_enabled": True,
            "sphere_shadow_softness": .45, "sphere_fade_incoming_blocks": True}))
        snapshot = replace(snapshot, logical=replace(snapshot.logical, mode_state=state))
        matrix = (2/480, 0, 0, 0, 0, -2/270, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
        for _ in range(12):  # crosses ring slots; four cohorts plus feather/core/hero
            host.render(snapshot=snapshot, viewport=(0, 0, 480, 270), logical_size=(480., 270.), matrix_values=matrix)
            assert gl_query.get_indexed_int(gl.GL_UNIFORM_BUFFER_BINDING, SCENE3D_UNIFORM_BINDING) == sentinel
            assert gl_query.get_indexed_int64(gl.GL_UNIFORM_BUFFER_START, SCENE3D_UNIFORM_BINDING) == 256
            assert gl_query.get_indexed_int64(gl.GL_UNIFORM_BUFFER_SIZE, SCENE3D_UNIFORM_BINDING) == 128
            assert gl_query.get_int(gl.GL_UNIFORM_BUFFER_BINDING) == 0
        renderer = host._implementations["sphere"]
        buffer = renderer._stream._buffer
        assert buffer and gl.glIsBuffer(buffer)
        target = _build_spectrum_preview_snapshot(width=480, height=270, mode="spectrum")
        host.render(snapshot=target, viewport=(0, 0, 480, 270), logical_size=(480., 270.), matrix_values=matrix)
        assert "sphere" not in host._implementations
        assert not renderer.has_resources and not gl.glIsBuffer(buffer)
    finally:
        host.release_resources()
        gl.glBindBufferBase(gl.GL_UNIFORM_BUFFER, SCENE3D_UNIFORM_BINDING, 0)
        gl.glDeleteBuffers(1, [sentinel])
        context.close()
