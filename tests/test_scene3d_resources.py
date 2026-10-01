"""Real-GL admission bars for shared scene3d DSA resources and multi-bind."""
from __future__ import annotations

import numpy as np
import pytest

from OpenGL import GL as gl

from rendering.quick.scene3d.frame import ITEM_QUAD_VERTEX_SOURCE
from rendering.quick.scene3d import resources as resource_module
from rendering.quick.scene3d.resources import MeshResources, bind_frame
from tools.transition_contact_sheet import TransitionCapture


_TRIANGLE_VERTEX = """#version 460 core
layout(location = 0) in vec2 aPosition;
void main() { gl_Position = vec4(aPosition, 0.0, 1.0); }
"""
_SOLID_FRAGMENT = """#version 460 core
out vec4 FragColor;
void main() { FragColor = vec4(0.1, 0.8, 0.3, 1.0); }
"""
_FRAME_FRAGMENT = """#version 460 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
void main() {
    FragColor = vec4(texture(uOldTex, vUv).r, texture(uNewTex, vUv).g, 0.0, 1.0);
}
"""


def test_incomplete_dsa_mesh_is_never_reused_as_a_zero_count_mesh(monkeypatch):
    created = iter((41, 42))
    deleted = []

    def create_one(_count, names):
        names[0] = next(created)

    def fail_upload(*_args):
        raise RuntimeError("upload failed")

    monkeypatch.setattr(resource_module.gl, "glCreateVertexArrays", create_one)
    monkeypatch.setattr(resource_module.gl, "glCreateBuffers", create_one)
    monkeypatch.setattr(resource_module.gl, "glNamedBufferStorage", fail_upload)
    monkeypatch.setattr(resource_module.gl, "glDeleteBuffers", lambda _count, names: deleted.append(("buffer", names[0])))
    monkeypatch.setattr(resource_module.gl, "glDeleteVertexArrays", lambda _count, names: deleted.append(("vao", names[0])))
    resources = MeshResources("incomplete mesh probe")

    with pytest.raises(RuntimeError, match="upload failed"):
        resources.mesh("fixture", (0.0, 0.0, 1.0, 1.0), (2,))
    assert resources._meshes["fixture"] == (41, 42, -1)
    with pytest.raises(RuntimeError, match="allocation is incomplete"):
        resources.mesh("fixture", (0.0, 0.0, 1.0, 1.0), (2,))

    resources.drop_mesh("fixture")
    assert deleted == [("buffer", 42), ("vao", 41)]


@pytest.mark.qt
def test_failed_named_storage_keeps_real_partial_names_owned_until_release_then_allows_a_clean_rebuild(qt_app, monkeypatch):
    capture = TransitionCapture(64, 64)
    resources = MeshResources("failed storage probe")
    original = resource_module.gl.glNamedBufferStorage
    try:
        def fail_upload(*_args):
            raise RuntimeError("injected named storage failure")

        monkeypatch.setattr(resource_module.gl, "glNamedBufferStorage", fail_upload)
        with pytest.raises(RuntimeError, match="injected named storage failure"):
            resources.mesh("fixture", (0.0, 0.0, 1.0, 1.0), (2,))
        vao, vbo, count = resources._meshes["fixture"]
        assert vao > 0 and vbo > 0 and count == -1 and resources.has_resources
        with pytest.raises(RuntimeError, match="allocation is incomplete"):
            resources.mesh("fixture", (0.0, 0.0, 1.0, 1.0), (2,))

        resources.release_resources()
        assert not resources.has_resources
        monkeypatch.setattr(resource_module.gl, "glNamedBufferStorage", original)
        rebuilt_vao, rebuilt_count = resources.mesh("fixture", (0.0, 0.0, 1.0, 1.0), (2,))
        assert rebuilt_vao > 0 and rebuilt_count == 2
    finally:
        resources.release_resources()
        capture.close()


@pytest.mark.qt
def test_static_mesh_dsa_upload_draws_and_leaves_generic_vao_and_vbo_bindings_untouched(qt_app):
    capture = TransitionCapture(64, 64)
    resources = MeshResources("dsa mesh probe")
    sentinel_vao = int(gl.glGenVertexArrays(1))
    sentinel_vbo = int(gl.glGenBuffers(1))
    try:
        gl.glBindVertexArray(sentinel_vao)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, sentinel_vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, 16, None, gl.GL_STATIC_DRAW)
        before = (
            int(gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING)),
            int(gl.glGetIntegerv(gl.GL_ARRAY_BUFFER_BINDING)),
        )

        vao, count = resources.mesh("triangle", (-1.0, -1.0, 1.0, -1.0, 0.0, 1.0), (2,))

        assert (
            int(gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING)),
            int(gl.glGetIntegerv(gl.GL_ARRAY_BUFFER_BINDING)),
        ) == before
        immutable = (gl.GLint * 1)()
        gl.glGetNamedBufferParameteriv(resources._meshes["triangle"][1], gl.GL_BUFFER_IMMUTABLE_STORAGE, immutable)
        assert int(immutable[0])
        assert resources.mesh("triangle", (-1.0, -1.0, 1.0, -1.0, 0.0, 1.0), (2,)) == (vao, count)

        program = resources.program("triangle", _TRIANGLE_VERTEX, _SOLID_FRAGMENT)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glViewport(0, 0, capture.width, capture.height)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
        gl.glUseProgram(program)
        gl.glBindVertexArray(vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, count)
        pixels = np.frombuffer(
            bytes(gl.glReadPixels(0, 0, capture.width, capture.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)),
            dtype=np.uint8,
        )
        assert pixels.reshape(-1, 4)[:, 1].max() > 150
    finally:
        resources.release_resources()
        gl.glDeleteBuffers(1, [sentinel_vbo])
        gl.glDeleteVertexArrays(1, [sentinel_vao])
        capture.close()


@pytest.mark.qt
def test_frame_multibind_initializes_linked_program_once_and_leaves_active_and_unit_two_untouched(qt_app, monkeypatch):
    import rendering.quick.scene3d.resources as resource_module

    capture = TransitionCapture(64, 64)
    resources = MeshResources("frame multi-bind probe")
    try:
        run = capture.run("block_spins", direction="left")
        frame = capture.frame(run, 0.5)
        program = resources.program("frame", ITEM_QUAD_VERTEX_SOURCE, _FRAME_FRAGMENT)
        uniforms = resources.uniforms("frame", ("uMatrix", "uItemSize", "uOldTex", "uNewTex"))
        gl.glActiveTexture(gl.GL_TEXTURE2)
        gl.glBindTexture(gl.GL_TEXTURE_2D, capture.textures[2])
        gl.glActiveTexture(gl.GL_TEXTURE3)
        active_before = int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE))
        unit_two_before = int(capture.textures[2])
        calls = []
        original = resource_module.gl.glProgramUniform1i

        def record(*args):
            calls.append(args)
            return original(*args)

        monkeypatch.setattr(resource_module.gl, "glProgramUniform1i", record)
        bind_frame(program, uniforms, frame)
        bind_frame(program, uniforms, frame)

        assert calls == [
            (program, uniforms["uOldTex"], 0),
            (program, uniforms["uNewTex"], 1),
        ]
        assert int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)) == active_before
        gl.glActiveTexture(gl.GL_TEXTURE0)
        assert int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)) == frame.source_texture_id
        gl.glActiveTexture(gl.GL_TEXTURE1)
        assert int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)) == frame.destination_texture_id
        gl.glActiveTexture(gl.GL_TEXTURE2)
        assert int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)) == unit_two_before
        gl.glActiveTexture(active_before)

        resources.release_resources()
        replacement = resources.program("frame", ITEM_QUAD_VERTEX_SOURCE, _FRAME_FRAGMENT)
        replacement_uniforms = resources.uniforms("frame", ("uMatrix", "uItemSize", "uOldTex", "uNewTex"))
        assert replacement_uniforms is not uniforms
        bind_frame(replacement, replacement_uniforms, frame)
        assert calls[2:] == [
            (replacement, replacement_uniforms["uOldTex"], 0),
            (replacement, replacement_uniforms["uNewTex"], 1),
        ]

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
        gl.glViewport(0, 0, capture.width, capture.height)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
        pixels = np.frombuffer(
            bytes(gl.glReadPixels(0, 0, capture.width, capture.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)),
            dtype=np.uint8,
        )
        assert pixels.reshape(-1, 4)[:, :2].mean(axis=0).min() > 10.0
    finally:
        resources.release_resources()
        capture.close()
