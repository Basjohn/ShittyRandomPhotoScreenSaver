"""P4-RHI-A acceptance bars for the QRhiWidget main compositor surface.

These tests exist to fail on a *superficial* inheritance swap. A naive port
compiles and renders something, but silently breaks one of:

* the OpenGL backend selection (Windows defaults QRhiWidget to Direct3D);
* the ExternalContent pass / beginExternal bracketing contract;
* exception safety, stranding QRhi mid-pass and poisoning later frames;
* borrowed-context ownership (destroying or doneCurrent-ing a Qt-owned context);
* strict, exactly-once GL resource cleanup;
* the QPainter fallback and PERF HUD, which stop drawing entirely if they keep
  targeting the widget instead of the QRhi render target.

Structural bars use AST/runtime inspection rather than substring matching.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QRhiCommandBuffer
from PySide6.QtWidgets import QRhiWidget

from rendering import gl_rhi_surface
from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg import gl_lifecycle, paint, shader_dispatch
from rendering.gl_rhi_surface import (
    BorrowedRhiGLContext,
    ExternalOpenGLRhiWidget,
    ExternalPassState,
    external_gl_render_pass,
    external_gl_section,
)


# ---------------------------------------------------------------------------
# Recording doubles
# ---------------------------------------------------------------------------


class _RecordingCommandBuffer:
    """Records the QRhi call sequence a frame actually issues."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.events: list[str] = []
        self.begin_pass_flags: list[object] = []
        self._fail_on = fail_on

    def _maybe_fail(self, name: str) -> None:
        if self._fail_on == name:
            raise RuntimeError(f"injected {name} failure")

    def beginPass(self, rt, clear_color, ds_clear, resource_updates=None, flags=None):
        self.events.append("beginPass")
        self.begin_pass_flags.append(flags)
        self._maybe_fail("beginPass")

    def endPass(self, resource_updates=None):
        self.events.append("endPass")

    def beginExternal(self):
        self.events.append("beginExternal")
        self._maybe_fail("beginExternal")

    def endExternal(self):
        self.events.append("endExternal")


class _StubRenderTarget:
    def pixelSize(self):
        from PySide6.QtCore import QSize

        return QSize(64, 48)


# ---------------------------------------------------------------------------
# Bar 1: OpenGL backend selection
# ---------------------------------------------------------------------------


class TestOpenGLBackendSelection:
    def test_compositor_is_a_qrhiwidget_not_a_qopenglwidget(self):
        assert issubclass(GLCompositorWidget, QRhiWidget)
        assert issubclass(GLCompositorWidget, ExternalOpenGLRhiWidget)

        from PySide6.QtOpenGLWidgets import QOpenGLWidget

        assert not issubclass(GLCompositorWidget, QOpenGLWidget)

    def test_opengl_api_is_selected_in_the_constructor(self):
        """Direct3D is the Windows default, so selection must precede realization."""
        source = inspect.getsource(ExternalOpenGLRhiWidget.__init__)
        tree = ast.parse(textwrap.dedent(source))

        api_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setApi"
        ]
        assert len(api_calls) == 1, "setApi must be called exactly once, in __init__"

        (arg,) = api_calls[0].args
        assert isinstance(arg, ast.Attribute)
        assert arg.attr == "OpenGL", "compositor must select the OpenGL QRhi backend"

    def test_constructed_compositor_reports_opengl_api(self, qapp):
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        comp = GLCompositorWidget(parent)
        try:
            assert comp.api() == QRhiWidget.Api.OpenGL
        finally:
            comp.setParent(None)
            comp.deleteLater()
            parent.deleteLater()


# ---------------------------------------------------------------------------
# Bars 2 and 3: external pass bracketing and exception safety
# ---------------------------------------------------------------------------


class TestExternalPassBracketing:
    def test_render_pass_declares_external_content_and_brackets_gl_once(self):
        cb = _RecordingCommandBuffer()
        state = ExternalPassState()

        with external_gl_render_pass(cb, _StubRenderTarget(), state=state):
            pass

        assert cb.events == ["beginPass", "beginExternal", "endExternal", "endPass"]
        assert cb.begin_pass_flags == [
            QRhiCommandBuffer.BeginPassFlag.ExternalContent
        ], "raw GL inside a pass requires the ExternalContent begin-pass flag"
        assert state.passes_begun == 1
        assert state.externals_begun == 1
        assert state.is_balanced()

    def test_body_exception_closes_external_block_and_pass_exactly_once(self):
        cb = _RecordingCommandBuffer()
        state = ExternalPassState()

        with pytest.raises(RuntimeError, match="renderer exploded"):
            with external_gl_render_pass(cb, _StubRenderTarget(), state=state):
                raise RuntimeError("renderer exploded")

        assert cb.events == ["beginPass", "beginExternal", "endExternal", "endPass"]
        assert state.is_balanced(), "QRhi must not be left inside an external block or pass"

    def test_failed_begin_external_still_ends_the_pass(self):
        cb = _RecordingCommandBuffer(fail_on="beginExternal")
        state = ExternalPassState()

        with pytest.raises(RuntimeError):
            with external_gl_render_pass(cb, _StubRenderTarget(), state=state):
                pytest.fail("body must not run when beginExternal fails")

        assert cb.events == ["beginPass", "beginExternal", "endPass"]
        assert "endExternal" not in cb.events, "must not end an external block that never began"
        assert state.is_balanced()

    def test_failed_begin_pass_does_not_end_a_pass_that_never_began(self):
        cb = _RecordingCommandBuffer(fail_on="beginPass")
        state = ExternalPassState()

        with pytest.raises(RuntimeError):
            with external_gl_render_pass(cb, _StubRenderTarget(), state=state):
                pytest.fail("body must not run when beginPass fails")

        assert cb.events == ["beginPass"]
        assert state.is_balanced()

    def test_external_section_outside_a_pass_is_balanced_on_exception(self):
        cb = _RecordingCommandBuffer()
        state = ExternalPassState()

        with pytest.raises(RuntimeError):
            with external_gl_section(cb, state):
                raise RuntimeError("init exploded")

        assert cb.events == ["beginExternal", "endExternal"]
        assert state.is_balanced()

    def test_render_override_never_propagates_into_the_qt_virtual_call(self):
        """A Python exception escaping a Qt virtual override can kill the process."""

        class _Boom(ExternalOpenGLRhiWidget):
            def __init__(self):  # bypass QWidget construction
                self._rhi_gl = BorrowedRhiGLContext()
                self._rhi_pass_state = ExternalPassState()
                self._rhi_render_failures = 0

            def renderTarget(self):
                return _StubRenderTarget()

            def gl_render(self):
                raise RuntimeError("draw failed")

        widget = _Boom()
        cb = _RecordingCommandBuffer()

        ExternalOpenGLRhiWidget.render(widget, cb)

        assert cb.events == ["beginPass", "beginExternal", "endExternal", "endPass"]
        assert widget._rhi_pass_state.is_balanced()
        assert widget._rhi_render_failures == 1

    def test_repeated_render_failures_are_rate_limited(self):
        class _Boom(ExternalOpenGLRhiWidget):
            def __init__(self):
                self._rhi_gl = BorrowedRhiGLContext()
                self._rhi_pass_state = ExternalPassState()
                self._rhi_render_failures = 0

            def renderTarget(self):
                return _StubRenderTarget()

            def gl_render(self):
                raise RuntimeError("draw failed")

        widget = _Boom()
        for _ in range(5):
            ExternalOpenGLRhiWidget.render(widget, _RecordingCommandBuffer())

        # Failures stay counted (never silently swallowed) without one log per frame.
        assert widget._rhi_render_failures == 5
        assert widget._RHI_FAILURE_LOG_INTERVAL > 1


# ---------------------------------------------------------------------------
# Bar 7: presentation stays Qt's
# ---------------------------------------------------------------------------


class TestPresentationOwnership:
    def test_no_application_side_swapbuffers_in_the_compositor_path(self):
        modules = (gl_rhi_surface, gl_lifecycle, paint, shader_dispatch)
        offenders: list[str] = []
        for module in modules:
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in {"swapBuffers", "glFinish"}:
                        offenders.append(f"{module.__name__}:{node.func.attr}")
        # glFinish survives only behind the default-off --diag-pair-warm-finish
        # negative control in gl_compositor.py, never in the render path.
        assert offenders == [], f"Qt owns presentation; found {offenders}"


# ---------------------------------------------------------------------------
# Bars 10 and 11: borrowed context ownership and warmup fencing
# ---------------------------------------------------------------------------


class TestBorrowedContextOwnership:
    def test_borrowed_context_has_no_release_or_destroy_api(self):
        """SRPSS may borrow currentness; it must never own the Qt context."""
        api = {name for name in dir(BorrowedRhiGLContext) if not name.startswith("__")}
        for forbidden in ("doneCurrent", "destroy", "deleteLater", "release"):
            assert forbidden not in api

    def test_no_donecurrent_is_issued_against_the_borrowed_context(self):
        source = inspect.getsource(BorrowedRhiGLContext)
        tree = ast.parse(textwrap.dedent(source))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "doneCurrent" not in called
        assert "makeThreadLocalNativeContextCurrent" in called, (
            "the documented QRhi seam is how foreign OpenGL borrows currentness"
        )

    def test_generation_changes_only_on_real_context_replacement(self):
        borrowed = BorrowedRhiGLContext()
        rhi, ctx = object(), object()

        assert borrowed.capture(rhi, ctx) is True
        first = borrowed.generation

        # A render-target resize re-invokes initialize() with the same pairing.
        assert borrowed.capture(rhi, ctx) is False
        assert borrowed.generation == first

        # A QRhi replacement (reparent/screen change) is a new generation.
        assert borrowed.capture(object(), object()) is True
        assert borrowed.generation == first + 1

        assert borrowed.invalidate() is True
        assert borrowed.is_attached() is False

    def test_resize_reinitialize_does_not_rebuild_immutable_resources(self, monkeypatch):
        """Bar 9: same generation must not re-create or leak GL ids."""
        pipeline = SimpleNamespace(initialized=True)
        widget = SimpleNamespace(
            _gl_pipeline=pipeline,
            _rhi_gl=SimpleNamespace(generation=1),
            _gl_state=SimpleNamespace(
                transition=lambda *_a, **_k: pytest.fail(
                    "a resize must not re-enter INITIALIZING"
                )
            ),
        )

        gl_lifecycle.handle_rhi_initialize(widget, generation_changed=False)

        assert pipeline.initialized is True

    def test_hidden_warmup_context_is_retired_when_the_share_group_dies(self, monkeypatch):
        """Bar 11: the SRPSS-owned offscreen context is generation-fenced."""
        destroyed: list[str] = []

        class _Surface:
            def destroy(self):
                destroyed.append("surface")

            def isValid(self):
                return True

        class _Ctx:
            def isValid(self):
                return True

            def doneCurrent(self):
                destroyed.append("doneCurrent")

        monkeypatch.setattr(gl_lifecycle, "QOffscreenSurface", _Surface)
        monkeypatch.setattr(gl_lifecycle, "QOpenGLContext", _Ctx)

        widget = SimpleNamespace(
            _deferred_warmup_context=_Ctx(),
            _deferred_warmup_surface=_Surface(),
            _deferred_warmup_generation=1,
            _rhi_gl=SimpleNamespace(generation=2),
        )

        gl_lifecycle._retire_hidden_shared_warmup_context(widget, reason="test")

        assert widget._deferred_warmup_context is None
        assert widget._deferred_warmup_surface is None
        assert widget._deferred_warmup_generation == 2
        assert "surface" in destroyed, "SRPSS owns the offscreen surface and destroys it"

    def test_cleanup_fails_closed_when_no_qrhi_context_is_attached(self, monkeypatch):
        """Bar 8: live resources plus an unusable context is a hard failure."""
        monkeypatch.setattr(gl_lifecycle, "gl", object())
        pipeline = SimpleNamespace(initialized=True)
        widget = SimpleNamespace(
            _gl_pipeline=pipeline,
            _texture_manager=None,
            _startup_transition_warm_queue=[],
            _startup_transition_resource_warm_queue=[],
            _startup_transition_resource_warm_types=set(),
            _rhi_gl=SimpleNamespace(
                is_attached=lambda: False, make_current=lambda: False
            ),
            _reset_pipeline_state=lambda: pytest.fail(
                "ownership must be retained, not reset, when deletion is impossible"
            ),
        )

        with pytest.raises(RuntimeError, match="no QRhi OpenGL context is attached"):
            gl_lifecycle.cleanup_gl_pipeline(widget)

        assert pipeline.initialized is True


# ---------------------------------------------------------------------------
# Bar 12: fallback and PERF HUD still reach the QRhi target
# ---------------------------------------------------------------------------


class TestFallbackAndHudTargetTheQRhiSurface:
    def test_compositor_path_never_constructs_qpainter_on_the_widget(self):
        """QPainter(widget) targets the backing store, not the QRhi texture."""
        offenders: list[str] = []
        for module in (paint, shader_dispatch, __import__(
            "rendering.gl_compositor_pkg.overlays", fromlist=["overlays"]
        )):
            tree = ast.parse(inspect.getsource(module))
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                    continue
                if node.func.id != "QPainter":
                    continue
                for arg in node.args:
                    # QPainter(image) is fine; QPainter(widget)/(comp) is not.
                    if isinstance(arg, ast.Name) and arg.id in {"widget", "comp"}:
                        offenders.append(f"{module.__name__}:{node.lineno}")
        assert offenders == [], (
            f"fallback/HUD must paint into the QRhi target, found {offenders}"
        )

    def test_target_painter_is_sized_from_the_render_target_with_dpr(self):
        sig = inspect.signature(gl_rhi_surface.external_gl_painter)
        assert list(sig.parameters) == ["pixel_size", "device_pixel_ratio"], (
            "the paint device must carry physical size and DPR so callers keep "
            "drawing in unchanged logical coordinates"
        )

    def test_overlay_batching_uses_one_target_painter_session(self, monkeypatch):
        events: list[str] = []

        from contextlib import contextmanager

        class _Painter:
            def drawImage(self, x, y, image):
                events.append("draw:image")

        @contextmanager
        def _target_painter():
            events.append("open")
            try:
                yield _Painter()
            finally:
                events.append("close")

        comp = SimpleNamespace(
            _spotify_vis_enabled=True, gl_target_painter=_target_painter
        )
        monkeypatch.setattr(shader_dispatch, "is_perf_metrics_enabled", lambda: True)
        monkeypatch.setattr(
            shader_dispatch, "gl", SimpleNamespace(glUseProgram=lambda _p: None)
        )
        monkeypatch.setattr(
            "rendering.gl_compositor_pkg.overlays.paint_spotify_visualizer",
            lambda _comp, _painter: events.append("draw:spotify"),
        )
        monkeypatch.setattr(
            "rendering.gl_compositor_pkg.overlays.render_debug_overlay_image",
            lambda _comp: object(),
        )

        shader_dispatch.paint_qpainter_overlays_gl(comp)

        assert events == ["open", "draw:spotify", "draw:image", "close"], (
            "the HUD and visualizer must share one painter session on the QRhi target"
        )


# ---------------------------------------------------------------------------
# Bars 4, 5 and 6: unchanged rendering policy
# ---------------------------------------------------------------------------


class TestRenderingPolicyUnchanged:
    def test_transition_dispatch_table_is_unchanged(self):
        names = [d[0] for d in paint._TRANSITION_SHADER_DESCRIPTORS]
        assert names == [
            "blockspin", "blockflip", "raindrops", "warp", "diffuse", "blinds",
            "crumble", "particle", "burn", "crossfade", "slide", "wipe",
        ]

    def test_update_request_ownership_is_unchanged(self):
        """The adaptive-timer handoff still owns update(); render() must not."""
        slot = inspect.getsource(GLCompositorWidget._srpss_apply_timer_update)
        assert ".update()" in slot

        tree = ast.parse(textwrap.dedent(inspect.getsource(ExternalOpenGLRhiWidget)))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        for forbidden in ("update", "repaint", "singleShot", "start", "sleep"):
            assert forbidden not in called, (
                f"the QRhi surface must not schedule {forbidden}"
            )

    def test_global_interval_zero_surface_format_policy_survives(self):
        """Qt derives the top-level NoVSync swapchain from the global format."""
        import main as main_module

        tree = ast.parse(inspect.getsource(main_module))
        sets_default = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setDefaultFormat"
            for node in ast.walk(tree)
        )
        assert sets_default, "global QSurfaceFormat policy must remain in startup"

        from rendering.gl_format import build_surface_format

        fmt, _prefs = build_surface_format(reason="p4-rhi-test")
        assert fmt.swapInterval() == 0

    def test_compositor_no_longer_applies_a_child_surface_format(self):
        """QRhiWidget takes its format from the top level; setFormat is gone."""
        source = inspect.getsource(GLCompositorWidget.__init__)
        tree = ast.parse(textwrap.dedent(source))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "setFormat" not in called
        assert "setUpdateBehavior" not in called

# ---------------------------------------------------------------------------
# Regression: raw WGL calls must never outlive a live drawable
# ---------------------------------------------------------------------------


class TestRawWglCallsRequireALiveDrawable:
    """A borrowed context can stay WGL-current over a destroyed surface.

    SRPSS must not doneCurrent() a Qt-owned context, so after a display is torn
    down the borrowed context can remain WGL-current against a drawable that no
    longer exists. Calling into the driver then access-violates rather than
    returning an error, which takes the whole process down. The present-context
    probe must therefore refuse to run unless the compositor's own borrowed
    context is attached AND currently current.
    """

    def test_probe_skips_when_no_borrowed_context_is_attached(self):
        widget = SimpleNamespace(
            _rhi_gl=SimpleNamespace(is_attached=lambda: False, is_current=lambda: False)
        )
        paint._probe_present_context_once(widget)
        assert widget._p4_present_context_probed is True

    def test_probe_skips_when_the_borrowed_context_is_not_current(self):
        widget = SimpleNamespace(
            _rhi_gl=SimpleNamespace(is_attached=lambda: True, is_current=lambda: False)
        )
        paint._probe_present_context_once(widget)
        assert widget._p4_present_context_probed is True

    def test_probe_skips_on_a_widget_without_the_borrowed_handle(self):
        widget = SimpleNamespace()
        paint._probe_present_context_once(widget)
        assert widget._p4_present_context_probed is True

    def test_probe_gate_precedes_every_native_call(self):
        """The liveness gate must dominate the WGL/Qt context calls."""
        source = inspect.getsource(paint._probe_present_context_once)
        gate = source.index("is_current()")
        for native in ("wglGetCurrentContext", "wglGetProcAddress", "currentContext()"):
            assert gate < source.index(native), (
                f"{native} must not run before the live-drawable gate"
            )

    def test_strict_cleanup_detaches_the_borrowed_handle(self):
        """Nothing may treat the pairing as live once the surface can die."""
        source = inspect.getsource(gl_lifecycle.cleanup_gl_pipeline)
        assert "_rhi_gl.invalidate()" in source

# ---------------------------------------------------------------------------
# Construction ordering: the highest-consequence failure mode of this migration
# ---------------------------------------------------------------------------


class TestCompositorIsCreatedBeforeTheWindow:
    """A QRhiWidget added to an already-created window never renders.

    Qt resolves the top-level backing-store QRhi configuration when the window
    is created. QOpenGLWidget tolerated late construction because it owned its
    own context and FBO; QRhiWidget does not. Getting this wrong produces a
    silent black display rather than an error, so the ordering is a contract.
    """

    def test_setup_creates_the_compositor_before_show(self):
        from rendering import display_setup

        source = inspect.getsource(display_setup)
        tree = ast.parse(source)

        target = None
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            body = ast.dump(node)
            if "_ensure_gl_compositor" in body and "'show'" in body:
                target = node
                break
        assert target is not None, "expected a setup function that shows the display"

        ensure_lines = [
            n.lineno
            for n in ast.walk(target)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "_ensure_gl_compositor"
        ]
        show_lines = [
            n.lineno
            for n in ast.walk(target)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "show"
        ]
        assert ensure_lines and show_lines
        assert min(ensure_lines) < min(show_lines), (
            "the GL compositor must be constructed before the display window is "
            "shown, or its QRhiWidget surface never renders"
        )

    def test_late_construction_is_reported_loudly(self):
        """The remaining lazy path must not fail silently."""
        from rendering import display_gl_init

        source = inspect.getsource(display_gl_init.ensure_gl_compositor)
        tree = ast.parse(textwrap.dedent(source))
        logs_error = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"error", "critical"}
            for node in ast.walk(tree)
        )
        assert logs_error, (
            "constructing the compositor after its window exists must be reported"
        )

    def test_compositor_renders_when_created_before_show(self, qapp):
        """End-to-end: correct ordering actually produces frames."""
        from PySide6.QtWidgets import QWidget

        rendered: list[int] = []
        original = paint.handle_rhi_render

        def counting(widget):
            rendered.append(1)
            return original(widget)

        paint.handle_rhi_render = counting
        parent = QWidget()
        parent.resize(240, 180)
        try:
            comp = GLCompositorWidget(parent)
            comp.resize(240, 180)
            comp.show()
            parent.show()
            for _ in range(12):
                comp.update()
                qapp.processEvents()

            if not comp._rhi_gl.is_attached():
                pytest.skip("no QRhi surface available in this environment")
            assert rendered, "correct construction order must produce rendered frames"
        finally:
            paint.handle_rhi_render = original
            try:
                comp.cleanup()
            except Exception:
                pass
            parent.close()
            parent.deleteLater()
