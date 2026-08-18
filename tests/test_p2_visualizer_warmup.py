"""P2-VIS-WARMUP: every runtime visualizer program is ready before reveal.

GL initialization used to compile only the active visualizer program and leave
the other four to a post-reveal GUI timer queue that linked one program every
140 ms. That produced visible startup hitching - Bubble tick spikes around
49-68 ms in the installed run - and made the first switch to each mode pay a
shader compile inside the visible state.

Hardware acceleration is a required runtime contract and there are exactly five
supported accelerated modes, so all of them are compiled during the hidden
startup stage as one visualizer-GL readiness contract.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay

RUNTIME_MODES = ("bubble", "spectrum", "sine_wave", "oscilloscope", "devcurve")


class _FakeGL:
    """Compiles and links everything successfully."""

    GL_VERTEX_SHADER = "vs"
    GL_FRAGMENT_SHADER = "fs"
    GL_COMPILE_STATUS = "compile"
    GL_LINK_STATUS = "link"
    GL_ARRAY_BUFFER = "array"
    GL_STATIC_DRAW = "static"
    GL_FLOAT = "float"

    def __init__(self):
        self.compiles = 0
        self.links = 0
        self._next = 1

    def _id(self):
        value = self._next
        self._next += 1
        return value

    def glCreateShader(self, kind):
        self.compiles += 1
        return self._id()

    def glShaderSource(self, *a):
        pass

    def glCompileShader(self, *a):
        pass

    def glGetShaderiv(self, shader, pname):
        return 1

    def glGetShaderInfoLog(self, shader):
        return b""

    def glCreateProgram(self):
        self.links += 1
        return self._id()

    def glAttachShader(self, *a):
        pass

    def glLinkProgram(self, *a):
        pass

    def glGetProgramiv(self, program, pname):
        return 1

    def glGetProgramInfoLog(self, program):
        return b""

    def glDeleteShader(self, *a):
        pass

    def glDeleteProgram(self, *a):
        pass

    def glGetUniformLocation(self, program, name):
        return 0

    def glGenVertexArrays(self, n):
        return self._id()

    def glGenBuffers(self, n):
        return self._id()

    def glBindVertexArray(self, *a):
        pass

    def glBindBuffer(self, *a):
        pass

    def glBufferData(self, *a):
        pass

    def glEnableVertexAttribArray(self, *a):
        pass

    def glVertexAttribPointer(self, *a):
        pass


class TestAllRuntimeProgramsCompileWhileHidden:
    def test_pipeline_init_compiles_every_available_mode(self, qapp, monkeypatch):
        from widgets.spotify_visualizer import shaders

        overlay = SpotifyBarsGLOverlay(None)
        available = shaders.load_all_fragment_shaders()
        if not available:
            pytest.skip("no visualizer shader sources available")

        gl = _FakeGL()
        monkeypatch.setattr(
            "widgets.spotify_bars_gl_overlay.gl", gl, raising=False
        )
        import OpenGL.GL as real_gl

        monkeypatch.setattr(real_gl, "glCreateShader", gl.glCreateShader, raising=False)

        # Compile through the real init path with a fake driver.
        import builtins

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "OpenGL":
                class _M:
                    GL = gl
                return _M()
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        try:
            overlay._init_gl_pipeline()
        finally:
            monkeypatch.setattr(builtins, "__import__", real_import)

        compiled = set(overlay._gl_programs.keys())
        expected = set(available.keys())
        assert compiled == expected, (
            f"only {sorted(compiled)} compiled; every runtime mode must be ready "
            f"before reveal, missing {sorted(expected - compiled)}"
        )

    def test_active_mode_is_compiled_first(self):
        """A failing secondary mode must not prevent the visualizer starting."""
        source = inspect.getsource(SpotifyBarsGLOverlay._init_gl_pipeline)
        order = source.index("compile_order = prioritized_visualizer_compile_order")
        loop = source.index("for mode_key in compile_order")
        assert order < loop, "the prioritized order must drive the compile loop"


class TestNoPostRevealWarmQueueRemains:
    def test_deferred_program_warm_machinery_is_gone(self):
        for retired in (
            "_warm_next_gl_program",
            "_schedule_gl_program_warmup_queue",
        ):
            assert not hasattr(SpotifyBarsGLOverlay, retired), (
                f"{retired} is a post-reveal warm queue and must not remain"
            )

    def test_no_warm_timer_state_remains(self, qapp):
        overlay = SpotifyBarsGLOverlay(None)
        for attr in ("_gl_program_warm_timer", "_gl_program_warm_queue"):
            assert not hasattr(overlay, attr), (
                f"{attr} kept the retired 140 ms warm queue alive"
            )

    def test_visualizer_constructs_no_qtimer(self):
        """No presentation or warm timer belongs in the visualizer any more."""
        import widgets.spotify_bars_gl_overlay as module

        tree = ast.parse(inspect.getsource(module))
        constructed = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "QTimer" not in constructed

    def test_init_does_not_schedule_deferred_compilation(self):
        import widgets.spotify_bars_gl_overlay as module

        tree = ast.parse(inspect.getsource(module))
        method = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_init_gl_pipeline"
        )
        called = {
            n.func.attr
            for n in ast.walk(method)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "self"
        }
        for forbidden in ("_schedule_gl_program_warmup_queue", "singleShot", "start"):
            assert forbidden not in called


class TestStartupFailureStaysLoud:
    def test_uncompiled_modes_are_reported_as_an_error(self):
        source = inspect.getsource(SpotifyBarsGLOverlay._init_gl_pipeline)
        assert "logger.error" in source, (
            "a mode that failed to compile must stay loud, not be retried silently"
        )

    def test_total_failure_still_raises(self):
        source = inspect.getsource(SpotifyBarsGLOverlay._init_gl_pipeline)
        assert "No visualizer shader programs compiled successfully" in source

    def test_no_cpu_renderer_substitute_exists(self):
        import widgets.spotify_bars_gl_overlay as module

        tree = ast.parse(inspect.getsource(module))
        constructed = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "QPainter" not in constructed, (
            "visualizer failure must never fall back to a CPU renderer"
        )


class TestModeSwitchingCompilesNothing:
    def test_every_runtime_mode_resolves_without_compiling(self, qapp, monkeypatch):
        """After startup, switching to any mode must find its program ready."""
        from widgets.spotify_visualizer import shaders

        available = shaders.load_all_fragment_shaders()
        if not available:
            pytest.skip("no visualizer shader sources available")

        overlay = SpotifyBarsGLOverlay(None)
        # Simulate the post-startup state: every runtime program already linked.
        overlay._gl_programs = {mode: 100 + i for i, mode in enumerate(available)}
        overlay._gl_uniforms = {mode: {} for mode in available}

        from widgets.spotify_visualizer.overlay_render_dispatch import (
            resolve_render_program_key,
        )

        for mode in available:
            key = resolve_render_program_key(overlay, mode)
            assert key in overlay._gl_programs, (
                f"mode {mode} would have to compile at switch time"
            )
