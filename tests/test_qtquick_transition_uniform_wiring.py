"""C-T3: resolved immutable request parameters must reach shader uniforms.

These are renderer-boundary WIRING tests. A recording/fake GL uniform sink is
the correct level of evidence here: it proves each authored request field is
uploaded to its intended uniform with the intended value, that boolean/integer
encodings are preserved, that Particle's ``u_resolution`` carries the physical
framebuffer size, and that Burn's ``u_time`` derives from the immutable run
clock. The separately-required real-GL harnesses still own actual rendering;
this file must never become a substitute for them.
"""

from __future__ import annotations

import pytest

from rendering.quick.image_state import PresentationImage
from rendering.quick.transitions.render_contract import QuickTransitionRenderFrame
from rendering.quick.transitions.state import TransitionRequest, TransitionRun

from rendering.quick.transitions.implementations import burn as burn_module
from rendering.quick.transitions.implementations import crumble as crumble_module
from rendering.quick.transitions.implementations import diffuse as diffuse_module
from rendering.quick.transitions.implementations import particle as particle_module
from rendering.quick.transitions.implementations import ripple as ripple_module


_IDENTITY_MATRIX = (
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
)
_FAKE_PROGRAM = 41


class _RecordingGL:
    """Fake OpenGL module that records uniform uploads by uniform name.

    Locations are assigned deterministically per uniform name. Names listed in
    ``absent`` resolve to ``-1`` so a renderer's optional-uniform guard path is
    exercised. Everything else is a no-op sufficient for the render call.
    """

    GL_FALSE = 0
    GL_TEXTURE_2D = 0x0DE1
    GL_TEXTURE0 = 0x84C0
    GL_TEXTURE1 = 0x84C1
    GL_TRIANGLE_STRIP = 0x0005

    def __init__(self, absent: frozenset[str] = frozenset()) -> None:
        self._absent = frozenset(absent)
        self._name_to_loc: dict[str, int] = {}
        self._loc_to_name: dict[int, str] = {}
        self._next_loc = 100
        self.uniforms: dict[str, object] = {}
        self.used_program: int | None = None
        self.draw_calls = 0

    def glGetUniformLocation(self, program, name):
        assert program == _FAKE_PROGRAM
        key = name.decode() if isinstance(name, bytes) else str(name)
        if key in self._absent:
            return -1
        if key not in self._name_to_loc:
            loc = self._next_loc
            self._next_loc += 1
            self._name_to_loc[key] = loc
            self._loc_to_name[loc] = key
        return self._name_to_loc[key]

    def _record(self, loc, value) -> None:
        name = self._loc_to_name.get(int(loc))
        assert name is not None, f"uniform upload to unknown location {loc}"
        self.uniforms[name] = value

    def glUseProgram(self, program) -> None:
        self.used_program = program

    def glUniformMatrix4fv(self, loc, count, transpose, values) -> None:
        self._record(loc, tuple(values))

    def glUniform1i(self, loc, value) -> None:
        self._record(loc, int(value))

    def glUniform1f(self, loc, value) -> None:
        self._record(loc, float(value))

    def glUniform2f(self, loc, a, b) -> None:
        self._record(loc, (float(a), float(b)))

    def glUniform4f(self, loc, a, b, c, d) -> None:
        self._record(loc, (float(a), float(b), float(c), float(d)))

    def glActiveTexture(self, unit) -> None:
        pass

    def glBindTexture(self, target, texture) -> None:
        pass

    def glBindVertexArray(self, vao) -> None:
        pass

    def glDrawArrays(self, mode, first, count) -> None:
        self.draw_calls += 1

    def glDeleteProgram(self, program) -> None:
        pass


def _install(monkeypatch, module, recorder: _RecordingGL) -> None:
    monkeypatch.setattr(module, "gl", recorder)
    monkeypatch.setattr(module, "compile_program", lambda *a, **k: _FAKE_PROGRAM)


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


def _frame(
    transition_id: str,
    requested_name: str,
    parameters: dict,
    *,
    duration_ms: int = 1000,
    linear: float = 0.5,
    viewport=(0, 0, 1920, 1080),
    logical_size=(1920.0, 1080.0),
) -> QuickTransitionRenderFrame:
    request = TransitionRequest(
        runtime_generation=3,
        transition_id=transition_id,
        requested_name=requested_name,
        selected_from_random=False,
        duration_ms=duration_ms,
        direction=None,
        parameters=parameters,
        source_image=_image("old"),
        destination_image=_image("new"),
    )
    run = TransitionRun.start(run_id=1, request=request, start_ns=0)
    now_ns = int(run.start_ns + (run.end_ns - run.start_ns) * linear)
    sample = run.sample(now_ns)
    return QuickTransitionRenderFrame(
        run=run,
        sample=sample,
        viewport=viewport,
        logical_size=logical_size,
        matrix_values=_IDENTITY_MATRIX,
        quad_vao=7,
        source_texture_id=8,
        destination_texture_id=9,
    )


def test_diffuse_request_parameters_reach_intended_uniforms(monkeypatch):
    recorder = _RecordingGL()
    _install(monkeypatch, diffuse_module, recorder)
    frame = _frame("diffuse", "Diffuse", {"block_size": 32, "shape_mode": 4})

    diffuse_module.QuickDiffuseRenderer().render(frame)

    assert recorder.used_program == _FAKE_PROGRAM
    assert recorder.draw_calls == 1
    # shape_mode is uploaded as an integer uniform unchanged.
    assert recorder.uniforms["u_shapeMode"] == 4
    # block_size drives the authored grid geometry: ceil(1920/32), ceil(1080/32).
    assert recorder.uniforms["u_grid"] == (60.0, 34.0)
    assert recorder.uniforms["u_progress"] == pytest.approx(
        frame.sample.eased_progress
    )
    assert recorder.uniforms["u_resolution"] == (1920.0, 1080.0)
    assert recorder.uniforms["uOldTex"] == 0
    assert recorder.uniforms["uNewTex"] == 1


def test_ripple_request_parameters_reach_intended_uniforms(monkeypatch):
    recorder = _RecordingGL()
    _install(monkeypatch, ripple_module, recorder)
    frame = _frame("ripple", "Ripple", {"ripple_count": 6, "ripple_seed": 123.5})

    ripple_module.QuickRippleRenderer().render(frame)

    assert recorder.uniforms["u_ripple_count"] == 6
    assert recorder.uniforms["u_ripple_seed"] == pytest.approx(123.5)
    assert recorder.uniforms["u_resolution"] == (1920.0, 1080.0)
    assert recorder.uniforms["u_progress"] == pytest.approx(
        frame.sample.eased_progress
    )


def _crumble_params(**overrides) -> dict:
    params = {
        "seed": 55.0,
        "piece_count": 20,
        "crack_complexity": 1.5,
        "mosaic_mode": True,
        "weight_mode": 2.0,
    }
    params.update(overrides)
    return params


def test_crumble_request_parameters_reach_intended_uniforms(monkeypatch):
    recorder = _RecordingGL()
    _install(monkeypatch, crumble_module, recorder)
    frame = _frame("crumble", "Crumble", _crumble_params())

    crumble_module.QuickCrumbleRenderer().render(frame)

    assert recorder.uniforms["u_seed"] == pytest.approx(55.0)
    assert recorder.uniforms["u_piece_count"] == pytest.approx(20.0)
    assert recorder.uniforms["u_crack_complexity"] == pytest.approx(1.5)
    assert recorder.uniforms["u_weight_mode"] == pytest.approx(2.0)


def test_crumble_mosaic_optional_upload_contract_when_uniform_exists(monkeypatch):
    # C-T7: only the optional uniform-upload contract is tested. When the
    # uniform location exists the renderer uploads mosaic_mode as 1.0/0.0.
    for mosaic, expected in ((True, 1.0), (False, 0.0)):
        recorder = _RecordingGL()
        _install(monkeypatch, crumble_module, recorder)
        frame = _frame(
            "crumble", "Crumble", _crumble_params(mosaic_mode=mosaic)
        )
        crumble_module.QuickCrumbleRenderer().render(frame)
        assert recorder.uniforms["u_mosaic_mode"] == pytest.approx(expected)


def test_crumble_skips_mosaic_upload_when_uniform_absent(monkeypatch):
    # When the shader does not declare u_mosaic_mode (location -1), the renderer
    # must not attempt to upload it.
    recorder = _RecordingGL(absent=frozenset({"u_mosaic_mode"}))
    _install(monkeypatch, crumble_module, recorder)
    frame = _frame("crumble", "Crumble", _crumble_params())

    crumble_module.QuickCrumbleRenderer().render(frame)

    assert "u_mosaic_mode" not in recorder.uniforms


def _particle_params(**overrides) -> dict:
    params = {
        "seed": 77.0,
        "mode": 1,
        "direction": 7,
        "particle_radius": 12.0,
        "overlap": 3.0,
        "trail_length": 0.3,
        "trail_strength": 0.4,
        "swirl_strength": 1.25,
        "swirl_turns": 2.5,
        "use_3d_shading": True,
        "texture_mapping": False,
        "wobble": True,
        "gloss_size": 64.0,
        "light_direction": 3,
        "swirl_order": 2,
    }
    params.update(overrides)
    return params


def test_particle_covers_every_authored_control_uniform(monkeypatch):
    recorder = _RecordingGL()
    _install(monkeypatch, particle_module, recorder)
    frame = _frame("particle", "Particle", _particle_params())

    particle_module.QuickParticleRenderer().render(frame)

    expected = {
        "u_seed": 77.0,
        "u_mode": 1.0,
        "u_direction": 7.0,
        "u_particle_radius": 12.0,
        "u_overlap": 3.0,
        "u_trail_length": 0.3,
        "u_trail_strength": 0.4,
        "u_swirl_strength": 1.25,
        "u_swirl_turns": 2.5,
        "u_use_3d": 1.0,
        "u_texture_map": 0.0,
        "u_wobble": 1.0,
        "u_gloss_size": 64.0,
        "u_light_dir": 3.0,
        "u_swirl_order": 2.0,
    }
    for name, value in expected.items():
        assert recorder.uniforms[name] == pytest.approx(value), name
    # Physical framebuffer resolution semantics: u_resolution is the viewport
    # (physical) size, not the logical item size.
    assert recorder.uniforms["u_resolution"] == (1920.0, 1080.0)


def test_particle_boolean_controls_toggle_their_uniforms(monkeypatch):
    recorder = _RecordingGL()
    _install(monkeypatch, particle_module, recorder)
    frame = _frame(
        "particle",
        "Particle",
        _particle_params(
            use_3d_shading=False, texture_mapping=True, wobble=False
        ),
    )

    particle_module.QuickParticleRenderer().render(frame)

    assert recorder.uniforms["u_use_3d"] == 0.0
    assert recorder.uniforms["u_texture_map"] == 1.0
    assert recorder.uniforms["u_wobble"] == 0.0


def _burn_params(**overrides) -> dict:
    params = {
        "direction": 4,
        "jaggedness": 0.3,
        "glow_intensity": 0.6,
        "glow_color": (0.1, 0.2, 0.3, 1.0),
        "char_width": 0.4,
        "smoke_enabled": True,
        "smoke_density": 0.5,
        "ash_enabled": False,
        "ash_density": 0.2,
        "seed": 88.0,
    }
    params.update(overrides)
    return params


def test_burn_covers_all_authored_uniforms_and_run_clock_time(monkeypatch):
    recorder = _RecordingGL()
    _install(monkeypatch, burn_module, recorder)
    # duration 2000ms at linear 0.5 -> u_time = 0.5 * 2000/1000 = 1.0s.
    frame = _frame(
        "burn", "Burn", _burn_params(), duration_ms=2000, linear=0.5
    )

    burn_module.QuickBurnRenderer().render(frame)

    assert recorder.uniforms["u_direction"] == 4
    assert recorder.uniforms["u_jaggedness"] == pytest.approx(0.3)
    assert recorder.uniforms["u_glow_intensity"] == pytest.approx(0.6)
    assert recorder.uniforms["u_glow_color"] == pytest.approx((0.1, 0.2, 0.3, 1.0))
    assert recorder.uniforms["u_char_width"] == pytest.approx(0.4)
    assert recorder.uniforms["u_smoke_enabled"] == 1
    assert recorder.uniforms["u_smoke_density"] == pytest.approx(0.5)
    assert recorder.uniforms["u_ash_enabled"] == 0
    assert recorder.uniforms["u_ash_density"] == pytest.approx(0.2)
    assert recorder.uniforms["u_seed"] == pytest.approx(88.0)
    # u_time is derived from the immutable run clock (linear_progress), not the
    # eased presentation curve.
    assert recorder.uniforms["u_time"] == pytest.approx(1.0)


def test_burn_boolean_toggles_encode_as_integer_uniforms(monkeypatch):
    recorder = _RecordingGL()
    _install(monkeypatch, burn_module, recorder)
    frame = _frame(
        "burn",
        "Burn",
        _burn_params(smoke_enabled=False, ash_enabled=True),
    )

    burn_module.QuickBurnRenderer().render(frame)

    assert recorder.uniforms["u_smoke_enabled"] == 0
    assert recorder.uniforms["u_ash_enabled"] == 1
