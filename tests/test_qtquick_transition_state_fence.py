"""C-T4: the common GL-state fence must restore inherited state exactly.

This is a state-contract test, so a fake GL state machine is the correct level
of evidence (the real-GL harnesses still own actual rendering, per C-T9). It
starts from deliberately non-default GL state, lets a renderer aggressively
mutate every fence-promised field, and proves ``QuickTransitionRenderHost``
restores the captured values -- including when ``renderer.render()`` raises,
because exception cleanup is part of the state-fence contract.

Scissor is asserted only as "preserved because the fence does not touch it":
the current fence deliberately does not capture/restore scissor, so the bar is
that neither host nor renderer silently disturbs it.
"""

from __future__ import annotations

import pytest

from rendering.quick.image_state import PresentationImage
from rendering.quick.transitions import render_host as render_host_module
from rendering.quick.transitions.render_host import QuickTransitionRenderHost
from rendering.quick.transitions.render_contract import QuickTransitionRenderFrame
from rendering.quick.transitions.state import TransitionRequest, TransitionRun


_IDENTITY_MATRIX = (
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
)


class _FakeGLState:
    """Minimal GL state machine covering exactly the fence-promised state."""

    GL_TRUE = 1
    GL_FALSE = 0
    GL_VIEWPORT = 100
    GL_CURRENT_PROGRAM = 101
    GL_VERTEX_ARRAY_BINDING = 102
    GL_ARRAY_BUFFER_BINDING = 103
    GL_ACTIVE_TEXTURE = 104
    GL_TEXTURE_BINDING_2D = 105
    GL_DEPTH_FUNC = 106
    GL_DEPTH_WRITEMASK = 107
    GL_DEPTH_CLEAR_VALUE = 108
    GL_BLEND = 110
    GL_CULL_FACE = 111
    GL_DEPTH_TEST = 112
    GL_STENCIL_TEST = 113
    GL_SCISSOR_TEST = 114
    GL_TEXTURE0 = 120
    GL_TEXTURE1 = 121
    GL_TEXTURE_2D = 130
    GL_ARRAY_BUFFER = 131
    GL_LESS = 201
    GL_GREATER = 202
    GL_LEQUAL = 203

    def __init__(self) -> None:
        self.viewport = (0, 0, 1, 1)
        self.program = 0
        self.vao = 0
        self.array_buffer = 0
        self.active_texture = self.GL_TEXTURE0
        self.tex = {self.GL_TEXTURE0: 0, self.GL_TEXTURE1: 0}
        self.enabled = {
            self.GL_BLEND: False,
            self.GL_CULL_FACE: False,
            self.GL_DEPTH_TEST: False,
            self.GL_STENCIL_TEST: False,
            self.GL_SCISSOR_TEST: False,
        }
        self.depth_write = True
        self.depth_func = self.GL_LESS
        self.depth_clear = 1.0

    # --- queries -------------------------------------------------------
    def glGetIntegerv(self, name):
        if name == self.GL_VIEWPORT:
            return tuple(self.viewport)
        if name == self.GL_CURRENT_PROGRAM:
            return self.program
        if name == self.GL_VERTEX_ARRAY_BINDING:
            return self.vao
        if name == self.GL_ARRAY_BUFFER_BINDING:
            return self.array_buffer
        if name == self.GL_ACTIVE_TEXTURE:
            return self.active_texture
        if name == self.GL_TEXTURE_BINDING_2D:
            return self.tex[self.active_texture]
        if name == self.GL_DEPTH_FUNC:
            return self.depth_func
        raise AssertionError(f"unexpected glGetIntegerv({name})")

    def glGetBooleanv(self, name):
        if name == self.GL_DEPTH_WRITEMASK:
            return [self.depth_write]
        raise AssertionError(f"unexpected glGetBooleanv({name})")

    def glGetFloatv(self, name):
        if name == self.GL_DEPTH_CLEAR_VALUE:
            return [self.depth_clear]
        raise AssertionError(f"unexpected glGetFloatv({name})")

    def glIsEnabled(self, cap):
        return self.enabled[cap]

    # --- mutators ------------------------------------------------------
    def glActiveTexture(self, unit):
        self.active_texture = unit

    def glBindTexture(self, target, texture):
        assert target == self.GL_TEXTURE_2D
        self.tex[self.active_texture] = texture

    def glBindVertexArray(self, vao):
        self.vao = vao

    def glBindBuffer(self, target, buffer):
        assert target == self.GL_ARRAY_BUFFER
        self.array_buffer = buffer

    def glUseProgram(self, program):
        self.program = program

    def glViewport(self, x, y, w, h):
        self.viewport = (x, y, w, h)

    def glDepthMask(self, flag):
        self.depth_write = bool(flag)

    def glDepthFunc(self, func):
        self.depth_func = func

    def glClearDepth(self, value):
        self.depth_clear = float(value)

    def glEnable(self, cap):
        self.enabled[cap] = True

    def glDisable(self, cap):
        self.enabled[cap] = False

    # --- helpers -------------------------------------------------------
    def snapshot(self) -> dict:
        return {
            "viewport": tuple(self.viewport),
            "program": self.program,
            "vao": self.vao,
            "array_buffer": self.array_buffer,
            "active_texture": self.active_texture,
            "tex0": self.tex[self.GL_TEXTURE0],
            "tex1": self.tex[self.GL_TEXTURE1],
            "blend": self.enabled[self.GL_BLEND],
            "cull": self.enabled[self.GL_CULL_FACE],
            "depth": self.enabled[self.GL_DEPTH_TEST],
            "stencil": self.enabled[self.GL_STENCIL_TEST],
            "depth_write": self.depth_write,
            "depth_func": self.depth_func,
            "depth_clear": self.depth_clear,
        }


def _load_deliberately_non_default(fake: _FakeGLState) -> None:
    fake.viewport = (10, 20, 640, 480)
    fake.program = 55
    fake.vao = 7
    fake.array_buffer = 9
    fake.active_texture = fake.GL_TEXTURE1
    fake.tex[fake.GL_TEXTURE0] = 21
    fake.tex[fake.GL_TEXTURE1] = 22
    fake.enabled[fake.GL_BLEND] = True
    fake.enabled[fake.GL_CULL_FACE] = True
    fake.enabled[fake.GL_DEPTH_TEST] = True
    fake.enabled[fake.GL_STENCIL_TEST] = True
    fake.enabled[fake.GL_SCISSOR_TEST] = True
    fake.depth_write = False
    fake.depth_func = fake.GL_LEQUAL
    fake.depth_clear = 0.25


class _MutatingRenderer:
    transition_id = "crossfade"

    def __init__(self, fake: _FakeGLState, *, raises: bool = False) -> None:
        self._fake = fake
        self._raises = raises
        self.has_resources = True
        self.render_calls = 0

    def render(self, frame) -> None:
        self.render_calls += 1
        g = self._fake
        g.glUseProgram(999)
        g.glBindVertexArray(888)
        g.glBindBuffer(g.GL_ARRAY_BUFFER, 777)
        g.glActiveTexture(g.GL_TEXTURE0)
        g.glBindTexture(g.GL_TEXTURE_2D, 66)
        g.glActiveTexture(g.GL_TEXTURE1)
        g.glBindTexture(g.GL_TEXTURE_2D, 67)
        g.glActiveTexture(g.GL_TEXTURE0)
        g.glViewport(1, 2, 3, 4)
        g.glEnable(g.GL_BLEND)
        g.glEnable(g.GL_CULL_FACE)
        g.glEnable(g.GL_DEPTH_TEST)
        g.glEnable(g.GL_STENCIL_TEST)
        g.glDepthMask(g.GL_TRUE)
        g.glDepthFunc(g.GL_GREATER)
        g.glClearDepth(0.75)
        if self._raises:
            raise RuntimeError("boom during transition render")

    def release_resources(self) -> None:
        self.has_resources = False


def _image(identity: str) -> PresentationImage:
    return PresentationImage(
        identity=identity,
        source_path="synthetic",
        logical_size=(1, 1),
        device_pixel_ratio=1,
        pixel_size=(1, 1),
        row_stride=4,
        rgba8=b"\x00\x00\x00\xff",
    )


def _frame() -> QuickTransitionRenderFrame:
    request = TransitionRequest(
        runtime_generation=3,
        transition_id="crossfade",
        requested_name="Crossfade",
        selected_from_random=False,
        duration_ms=1000,
        direction=None,
        parameters={},
        source_image=_image("old"),
        destination_image=_image("new"),
    )
    run = TransitionRun.start(run_id=1, request=request, start_ns=0)
    sample = run.sample(run.start_ns + (run.end_ns - run.start_ns) // 2)
    return QuickTransitionRenderFrame(
        run=run,
        sample=sample,
        viewport=(0, 0, 1920, 1080),
        logical_size=(1920.0, 1080.0),
        matrix_values=_IDENTITY_MATRIX,
        quad_vao=7,
        source_texture_id=8,
        destination_texture_id=9,
    )


def _host_with(fake: _FakeGLState, renderer) -> QuickTransitionRenderHost:
    host = QuickTransitionRenderHost(enabled_transition_ids={"crossfade"})
    host._implementations["crossfade"] = renderer  # type: ignore[assignment]
    return host


def test_state_fence_restores_every_promised_field_after_render(monkeypatch):
    fake = _FakeGLState()
    monkeypatch.setattr(render_host_module, "gl", fake)
    _load_deliberately_non_default(fake)
    baseline = fake.snapshot()
    scissor_before = fake.enabled[fake.GL_SCISSOR_TEST]

    renderer = _MutatingRenderer(fake)
    host = _host_with(fake, renderer)

    assert host.render(_frame()) == "crossfade"

    assert renderer.render_calls == 1
    assert fake.snapshot() == baseline
    # Scissor is not fence-owned; the host must nonetheless leave it untouched.
    assert fake.enabled[fake.GL_SCISSOR_TEST] == scissor_before


def test_state_fence_restores_every_promised_field_when_render_raises(monkeypatch):
    fake = _FakeGLState()
    monkeypatch.setattr(render_host_module, "gl", fake)
    _load_deliberately_non_default(fake)
    baseline = fake.snapshot()
    scissor_before = fake.enabled[fake.GL_SCISSOR_TEST]

    renderer = _MutatingRenderer(fake, raises=True)
    host = _host_with(fake, renderer)

    with pytest.raises(RuntimeError, match="boom during transition render"):
        host.render(_frame())

    assert renderer.render_calls == 1
    assert fake.snapshot() == baseline
    assert fake.enabled[fake.GL_SCISSOR_TEST] == scissor_before


def test_state_fence_actually_applies_transition_setup_before_restore(monkeypatch):
    # Guard against a vacuous fence: prove the fenced region really did disable
    # blend/cull/depth/stencil and install the frame viewport while the renderer
    # ran, so the restoration under test is meaningful rather than a no-op.
    fake = _FakeGLState()
    monkeypatch.setattr(render_host_module, "gl", fake)
    _load_deliberately_non_default(fake)

    observed: dict = {}

    class _ObservingRenderer(_MutatingRenderer):
        def render(self, frame) -> None:
            observed["viewport"] = tuple(self._fake.viewport)
            observed["blend"] = self._fake.enabled[self._fake.GL_BLEND]
            observed["cull"] = self._fake.enabled[self._fake.GL_CULL_FACE]
            observed["depth"] = self._fake.enabled[self._fake.GL_DEPTH_TEST]
            observed["stencil"] = self._fake.enabled[self._fake.GL_STENCIL_TEST]
            super().render(frame)

    host = _host_with(fake, _ObservingRenderer(fake))
    host.render(_frame())

    assert observed["viewport"] == (0, 0, 1920, 1080)
    assert observed["blend"] is False
    assert observed["cull"] is False
    assert observed["depth"] is False
    assert observed["stencil"] is False
