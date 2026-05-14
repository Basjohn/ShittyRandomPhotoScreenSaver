from __future__ import annotations

from types import SimpleNamespace

import widgets.spotify_visualizer.overlay_render_dispatch as overlay_dispatch
import widgets.spotify_visualizer.renderers as renderer_mod


class _CaptureLogger:
    def __init__(self) -> None:
        self.debug_messages: list[str] = []
        self.warning_messages: list[str] = []

    def debug(self, msg, *args, **kwargs) -> None:
        self.debug_messages.append(msg % args if args else str(msg))

    def warning(self, msg, *args, **kwargs) -> None:
        self.warning_messages.append(msg % args if args else str(msg))


class _FakeGL:
    GL_VERTEX_SHADER = 35633
    GL_COMPILE_STATUS = 35713

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def glCreateShader(self, shader_type):
        self.calls.append(("glCreateShader", shader_type))
        return 99

    def glShaderSource(self, shader, source):
        self.calls.append(("glShaderSource", shader, source))

    def glCompileShader(self, shader):
        self.calls.append(("glCompileShader", shader))

    def glGetShaderiv(self, shader, param):
        self.calls.append(("glGetShaderiv", shader, param))
        return True

    def glDeleteShader(self, shader):
        self.calls.append(("glDeleteShader", shader))


def test_resolve_mode_program_returns_cached_program_without_lazy_compile():
    logger = _CaptureLogger()
    gl = _FakeGL()
    overlay = SimpleNamespace(_gl_programs={"spectrum": 1234})

    program = overlay_dispatch.resolve_mode_program(overlay, gl, "spectrum", logger)

    assert program == 1234
    assert gl.calls == []
    assert not logger.warning_messages


def test_resolve_mode_program_lazily_compiles_missing_mode(monkeypatch):
    logger = _CaptureLogger()
    gl = _FakeGL()

    compiled = {}

    def _compile(mode, fs_source, vs, _gl):
        compiled["args"] = (mode, fs_source, vs)
        overlay._gl_programs[mode] = 4321
        return True

    overlay = SimpleNamespace(_gl_programs={}, _compile_gl_mode_program=_compile)

    monkeypatch.setattr(overlay_dispatch, "SHARED_VERTEX_SHADER", "unused", raising=False)
    monkeypatch.setattr(
        "widgets.spotify_visualizer.shaders.SHARED_VERTEX_SHADER",
        "vertex-source",
        raising=False,
    )
    monkeypatch.setattr(
        "widgets.spotify_visualizer.shaders.load_fragment_shader",
        lambda mode: f"frag:{mode}",
    )

    program = overlay_dispatch.resolve_mode_program(overlay, gl, "bubble", logger)

    assert program == 4321
    assert compiled["args"] == ("bubble", "frag:bubble", 99)
    assert ("glDeleteShader", 99) in gl.calls
    assert not logger.warning_messages


def test_dispatch_mode_uniforms_delegates_to_renderer_registry(monkeypatch):
    calls = {}

    def _fake_upload(mode, gl, uniforms, state):
        calls["args"] = (mode, gl, uniforms, state)
        return True

    monkeypatch.setattr(renderer_mod, "upload_mode_uniforms", _fake_upload)

    fake_gl = object()
    uniforms = {"u_test": 1}
    state = object()

    assert overlay_dispatch.dispatch_mode_uniforms(fake_gl, "sine_wave", uniforms, state) is True
    assert calls["args"] == ("sine_wave", fake_gl, uniforms, state)
