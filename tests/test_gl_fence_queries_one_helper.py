"""Every per-frame GL state fence reads through ``rendering.quick.gl_query``, in its established order (AC-08).

The fences used PyOpenGL's checked getters (``gl.glGetIntegerv`` builds an array per call: about 14 us against
3.6 us for ``gl_query.get_int``) or a second private ctypes copy in ``visualizer/gl_state.py``. Now one helper
serves them all; the query order is unchanged (``clip_host`` and the CHK25/CHK26 fences depend on it).

No GL context: every reader is recorded and answers a neutral value, and ``gl`` is a recording proxy in the fence
modules, so the old readers are seen too (tagged ``legacy``). Each fence must ask the same states in the same order,
every one through ``gl_query``.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from OpenGL import GL as real_gl

_QUAD = {int(real_gl.GL_VIEWPORT), int(real_gl.GL_SCISSOR_BOX), int(real_gl.GL_COLOR_WRITEMASK),
         int(real_gl.GL_COLOR_CLEAR_VALUE)}


def _names(*names):
    return [int(getattr(real_gl, name)) for name in names]


CLIP_CAPTURE = _names(
    "GL_SCISSOR_TEST", "GL_SCISSOR_BOX", "GL_STENCIL_TEST", "GL_STENCIL_FUNC", "GL_STENCIL_REF",
    "GL_STENCIL_VALUE_MASK", "GL_STENCIL_WRITEMASK", "GL_STENCIL_FAIL", "GL_STENCIL_PASS_DEPTH_FAIL",
    "GL_STENCIL_PASS_DEPTH_PASS", "GL_STENCIL_BACK_FUNC", "GL_STENCIL_BACK_REF", "GL_STENCIL_BACK_VALUE_MASK",
    "GL_STENCIL_BACK_WRITEMASK", "GL_STENCIL_BACK_FAIL", "GL_STENCIL_BACK_PASS_DEPTH_FAIL",
    "GL_STENCIL_BACK_PASS_DEPTH_PASS")
CLIPPED_SHARED = _names(
    "GL_VIEWPORT", "GL_CURRENT_PROGRAM", "GL_VERTEX_ARRAY_BINDING", "GL_ARRAY_BUFFER_BINDING", "GL_BLEND",
    "GL_CULL_FACE", "GL_DEPTH_TEST", "GL_DEPTH_WRITEMASK", "GL_COLOR_WRITEMASK", "GL_BLEND_SRC_RGB",
    "GL_BLEND_DST_RGB", "GL_BLEND_SRC_ALPHA", "GL_BLEND_DST_ALPHA", "GL_BLEND_EQUATION_RGB",
    "GL_BLEND_EQUATION_ALPHA")
RENDER_HOST = _names(
    "GL_VIEWPORT", "GL_CURRENT_PROGRAM", "GL_VERTEX_ARRAY_BINDING", "GL_ARRAY_BUFFER_BINDING", "GL_BLEND",
    "GL_BLEND_SRC_RGB", "GL_BLEND_DST_RGB", "GL_BLEND_SRC_ALPHA", "GL_BLEND_DST_ALPHA", "GL_BLEND_EQUATION_RGB",
    "GL_BLEND_EQUATION_ALPHA", "GL_CULL_FACE", "GL_DEPTH_TEST", "GL_DEPTH_WRITEMASK")
BACKGROUND_BASE = _names(
    "GL_VIEWPORT", "GL_CURRENT_PROGRAM", "GL_VERTEX_ARRAY_BINDING", "GL_ARRAY_BUFFER_BINDING", "GL_ACTIVE_TEXTURE",
    "GL_TEXTURE_BINDING_2D", "GL_BLEND", "GL_CULL_FACE", "GL_DEPTH_TEST", "GL_STENCIL_TEST")


class _RecordingGL:
    """``OpenGL.GL`` for a fence module: constants are real, legacy readers are recorded, every other call is a
    no-op (nothing reaches a driver)."""

    def __init__(self, record):
        self._record = record

    def __getattr__(self, name):
        if not name.startswith("gl"):
            return getattr(real_gl, name)
        record = self._record
        if name == "glGetIntegerv":
            return lambda pname, *_a: record("legacy", pname) or ([0, 0, 1, 1] if int(pname) in _QUAD else 0)
        if name == "glGetBooleanv":
            return lambda pname, *_a: record("legacy", pname) or [1, 1, 1, 1]
        if name == "glIsEnabled":
            return lambda cap: record("legacy", cap) or 0
        return lambda *_a, **_k: 0


@pytest.fixture
def queries(monkeypatch):
    from rendering.quick import gl_query
    from rendering.quick.render import background_node
    from rendering.quick.visualizer import clip_host, gl_state, render_host
    seen: list = []

    def record(route, name):
        seen.append((route, int(name)))

    for name, answer in (("get_int", lambda n: 0), ("get_ints", lambda n, c: (0,) * c),
                         ("get_bool", lambda n: True), ("get_bools", lambda n, c: (True,) * c),
                         ("is_enabled", lambda n: False), ("get_floats", lambda n, c: (0.0,) * c)):
        monkeypatch.setattr(gl_query, name, lambda *a, _answer=answer: record("gl_query", a[0]) or _answer(*a))
    for module in (clip_host, gl_state, render_host, background_node):
        monkeypatch.setattr(module, "gl", _RecordingGL(record))
    # The former private ctypes readers in gl_state (present on the old code only).
    for name in ("_glGetIntegerv", "_glGetBooleanv"):
        monkeypatch.setattr(gl_state, name, lambda pname, *_a: record("legacy", pname), raising=False)
    monkeypatch.setattr(gl_state, "_glIsEnabled", lambda cap: record("legacy", cap) or 0, raising=False)
    return seen


def _check(seen, expected, fence):
    assert [name for _route, name in seen] == expected, f"{fence}: the GL query order changed"
    legacy = [name for route, name in seen if route != "gl_query"]
    assert legacy == [], f"{fence}: {len(legacy)} of {len(seen)} queries bypass rendering.quick.gl_query"


def test_clip_host_inherited_state_capture(queries):
    from rendering.quick.visualizer.clip_host import _InheritedClipState
    _InheritedClipState.capture()
    _check(queries, CLIP_CAPTURE, "clip inherited-state capture")


def test_shared_clipped_capture(queries):
    from rendering.quick.visualizer.gl_state import InheritedGlState
    InheritedGlState.capture_clipped_shared()
    _check(queries, CLIPPED_SHARED, "shared clipped capture")


def test_render_host_capture(queries):
    from rendering.quick.visualizer.gl_state import InheritedGlState
    InheritedGlState.capture_render_host()
    _check(queries, RENDER_HOST, "render-host capture")


def test_background_base_draw_fence(queries):
    from rendering.quick.render.background_node import BackgroundRenderNode
    import contextlib

    # The base program's values travel in its pass block (N1.6), which reads no GL state back: a scope that writes
    # nothing stands in for its ring here.
    node = SimpleNamespace(_program=0, _vao=0, _blocks=SimpleNamespace(bound=lambda _data: contextlib.nullcontext()),
                           _logical_size=(4.0, 4.0), _state=SimpleNamespace(progress=0.0))
    BackgroundRenderNode._draw_base(node, texture_id=0, viewport=(0, 0, 4, 4), matrix_values=(1.0,) * 16)
    _check(queries, BACKGROUND_BASE, "background base draw")
