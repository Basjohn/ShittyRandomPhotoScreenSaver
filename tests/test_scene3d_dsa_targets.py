"""S13c: fixed-size scene targets use immutable DSA storage without changing host bindings.

These are real offscreen GL checks.  They cover construction only; draw-time texture
and framebuffer binding remains the existing explicit state-fenced path.
"""
from __future__ import annotations

import ctypes

import pytest
from OpenGL import GL as gl

from rendering.quick.scene3d.motion import MotionBlur
from rendering.quick.scene3d.post import BloomChain
from rendering.quick.scene3d.target import SceneTarget
from rendering.quick.scene3d.trails import MotionTrails
from tools.transition_contact_sheet import TransitionCapture

pytestmark = pytest.mark.qt


def _immutable(texture: int) -> None:
    value = (ctypes.c_int * 1)()
    gl.glGetTextureParameteriv(texture, gl.GL_TEXTURE_IMMUTABLE_FORMAT, value)
    assert int(value[0]) == gl.GL_TRUE


def _complete(framebuffer: int) -> None:
    assert gl.glCheckNamedFramebufferStatus(framebuffer, gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE


def _warm_all(target: SceneTarget) -> None:
    while not target.warm((191, 107), 4, motion_blur=True, bloom=True):
        pass


def _owned_textures(owner) -> tuple[int, ...]:
    if isinstance(owner, SceneTarget):
        return tuple(owner._names[key] for key in ("colour", "velocity", "resolve_texture", "resolve_velocity")
                     if owner._names[key])
    if isinstance(owner, BloomChain):
        return tuple(texture for texture, _fbo, _width, _height in owner._levels)
    if isinstance(owner, MotionBlur):
        return tuple(texture for texture, _fbo, _width, _height in owner._passes)
    return (owner._texture,) if owner._texture else ()


def test_fixed_scene_allocations_are_immutable_and_preserve_unrelated_host_bindings(qt_app):
    """All target/post/blur/trail creation is named: it cannot replace Quick's bindings."""
    capture = TransitionCapture(256, 144)
    target, trails = SceneTarget("DSA target test"), MotionTrails("DSA trails test")
    sentinel = int(gl.glGenTextures(1))
    try:
        gl.glActiveTexture(gl.GL_TEXTURE3)
        gl.glBindTexture(gl.GL_TEXTURE_2D, sentinel)
        active = int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE))
        draw = int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING))
        read = int(gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING))

        _warm_all(target)
        assert trails.warm(target) is False

        assert int(gl.glGetIntegerv(gl.GL_ACTIVE_TEXTURE)) == active
        assert int(gl.glGetIntegerv(gl.GL_TEXTURE_BINDING_2D)) == sentinel
        assert int(gl.glGetIntegerv(gl.GL_DRAW_FRAMEBUFFER_BINDING)) == draw
        assert int(gl.glGetIntegerv(gl.GL_READ_FRAMEBUFFER_BINDING)) == read

        for key in ("colour", "velocity", "resolve_texture", "resolve_velocity"):
            if texture := target._names[key]:
                _immutable(texture)
        for texture, _fbo, _width, _height in target._bloom._levels:
            _immutable(texture)
        for texture, _fbo, _width, _height in target._motion._passes:
            _immutable(texture)
        _immutable(trails._texture)

        for fbo in (target._names["fbo"], target._names["resolve_fbo"], trails._fbo):
            _complete(fbo)
        for _texture, fbo, _width, _height in target._bloom._levels:
            _complete(fbo)
        # Motion blur's tile max is a compute-written image with no framebuffer; the blurred scene has one.
        (_tiles, tiles_fbo, _w, _h), (_blurred, blurred_fbo, _bw, _bh) = target._motion._passes
        assert tiles_fbo == 0
        _complete(blurred_fbo)
    finally:
        trails.release()
        target.release()
        gl.glDeleteTextures([sentinel])
        capture.close()


@pytest.mark.parametrize(
    "owner_type,fail_symbol,prepare",
    (
        (SceneTarget, "glCreateRenderbuffers", lambda owner: owner.warm((64, 64), 4)),
        (SceneTarget, "glTextureStorage2DMultisample", lambda owner: owner.warm((64, 64), 4)),
        (BloomChain, "glCreateFramebuffers", lambda owner: owner.warm((64, 64))),
        (MotionBlur, "glCreateFramebuffers", lambda owner: owner.warm((64, 64))),
        (MotionBlur, "glTextureStorage2D", lambda owner: owner.warm((64, 64))),
        (MotionTrails, "glCreateFramebuffers", lambda owner: owner._allocate(64, 64)),
    ),
)
def test_partial_fixed_target_allocations_stay_owned_for_release_retry(qt_app, monkeypatch, owner_type, fail_symbol,
                                                                        prepare):
    """A named allocation that fails after a texture still has one retrying deletion owner."""
    capture = TransitionCapture(64, 64)
    owner = owner_type("DSA cleanup test")
    original = getattr(gl, fail_symbol)
    try:
        monkeypatch.setattr(gl, fail_symbol, lambda *_args: (_ for _ in ()).throw(RuntimeError("injected allocation failure")))
        with pytest.raises(RuntimeError, match="injected allocation failure"):
            prepare(owner)
        assert owner.has_resources
        created = _owned_textures(owner)
        assert created and all(gl.glIsTexture(texture) for texture in created)
        monkeypatch.setattr(gl, fail_symbol, original)
        owner.release()
        assert not owner.has_resources
        assert not any(gl.glIsTexture(texture) for texture in created)
    finally:
        monkeypatch.setattr(gl, fail_symbol, original)
        owner.release()
        capture.close()
