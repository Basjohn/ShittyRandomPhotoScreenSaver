"""P2-RHI-A acceptance bars for the QRhiWidget Spotify visualizer surface.

The visualizer overlay keeps its sibling position above the QWidget card; only
its presentation backend changed from QOpenGLWidget to the shared
ExternalOpenGLRhiWidget/OpenGL substrate.

These bars exist to fail on the ways that migration silently breaks:

* an opaque render-pass clear would paint a black rectangle over the card;
* a missing depth/stencil target would break the rounded-card stencil mask;
* clearing the "backing buffer" outside the render callback now lands on an
  unspecified framebuffer rather than this surface's target;
* a QRhi replacement stranding the state machine in terminal DESTROYED would
  leave a live overlay permanently unable to reach READY again;
* changing the request stream would confound the whole P2 experiment.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
import textwrap
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QRhiWidget

from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_rhi_surface import (
    OPAQUE_CLEAR_COLOR,
    TRANSPARENT_CLEAR_COLOR,
    ExternalOpenGLRhiWidget,
)
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay


def _overlay_source() -> str:
    return inspect.getsource(SpotifyBarsGLOverlay)


def _method_ast(name: str) -> ast.FunctionDef:
    method = getattr(SpotifyBarsGLOverlay, name)
    return ast.parse(textwrap.dedent(inspect.getsource(method))).body[0]


def _self_calls(node: ast.AST) -> set[str]:
    return {
        n.func.attr
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and isinstance(n.func.value, ast.Name)
        and n.func.value.id == "self"
    }


# ---------------------------------------------------------------------------
# Surface
# ---------------------------------------------------------------------------


class TestSurfaceBackend:
    def test_overlay_uses_the_shared_substrate(self):
        assert issubclass(SpotifyBarsGLOverlay, ExternalOpenGLRhiWidget)
        assert issubclass(SpotifyBarsGLOverlay, QRhiWidget)

        from PySide6.QtOpenGLWidgets import QOpenGLWidget

        assert not issubclass(SpotifyBarsGLOverlay, QOpenGLWidget)

    def test_no_second_rhi_wrapper_was_introduced(self):
        """The substrate is shared with the compositor, not duplicated."""
        source = _overlay_source()
        assert "setApi" not in source, (
            "API selection belongs to the shared substrate constructor"
        )
        assert "beginPass" not in source and "beginExternal" not in source, (
            "render-pass bracketing belongs to the shared substrate"
        )

    def test_overlay_reports_opengl_api(self, qapp):
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        overlay = SpotifyBarsGLOverlay(parent)
        try:
            assert overlay.api() == QRhiWidget.Api.OpenGL
        finally:
            overlay.setParent(None)
            overlay.deleteLater()
            parent.deleteLater()

    def test_overlay_is_hidden_on_construction(self, qapp):
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        overlay = SpotifyBarsGLOverlay(parent)
        try:
            assert overlay.isHidden(), "startup flash protection must survive"
        finally:
            overlay.setParent(None)
            overlay.deleteLater()
            parent.deleteLater()

    def test_overlay_does_not_own_presentation_policy(self):
        """The compositor / global startup owns swap interval and presentation."""
        tree = ast.parse(_overlay_source())
        invoked = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if name:
                    invoked.add(name)
        forbidden = {
            "swapBuffers",
            "wglSwapIntervalEXT",
            "_disable_current_context_swap_interval",
            "setFormat",
            "apply_widget_surface_format",
            "setUpdateBehavior",
        }
        assert not (invoked & forbidden), (
            f"visualizer must not own presentation policy: {invoked & forbidden}"
        )


# ---------------------------------------------------------------------------
# Clear policy
# ---------------------------------------------------------------------------


class TestClearPolicy:
    def test_visualizer_clears_transparent(self):
        assert SpotifyBarsGLOverlay.RHI_CLEAR_COLOR is TRANSPARENT_CLEAR_COLOR
        assert SpotifyBarsGLOverlay.RHI_CLEAR_COLOR.alpha() == 0

    def test_compositor_keeps_its_opaque_clear(self):
        assert GLCompositorWidget.RHI_CLEAR_COLOR is OPAQUE_CLEAR_COLOR
        assert GLCompositorWidget.RHI_CLEAR_COLOR.alpha() == 255

    def test_one_surface_cannot_mutate_the_others_clear_policy(self):
        """Clear policy is per-class, so the two surfaces cannot interfere."""
        assert (
            GLCompositorWidget.RHI_CLEAR_COLOR
            is not SpotifyBarsGLOverlay.RHI_CLEAR_COLOR
        )
        assert "RHI_CLEAR_COLOR" in vars(GLCompositorWidget) or (
            GLCompositorWidget.RHI_CLEAR_COLOR is OPAQUE_CLEAR_COLOR
        )
        assert "RHI_CLEAR_COLOR" in vars(SpotifyBarsGLOverlay)
        # The base default stays opaque for any future surface.
        assert ExternalOpenGLRhiWidget.RHI_CLEAR_COLOR is OPAQUE_CLEAR_COLOR

    def test_render_pass_uses_the_subclass_clear_colour(self):
        source = textwrap.dedent(inspect.getsource(ExternalOpenGLRhiWidget.render))
        tree = ast.parse(source)
        keywords = {
            kw.arg
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            for kw in node.keywords
        }
        assert "clear_color" in keywords, (
            "the pass must clear with the surface's own policy, not a constant"
        )


# ---------------------------------------------------------------------------
# Stencil / depth capability for the rounded-card mask
# ---------------------------------------------------------------------------


class TestStencilCapability:
    def test_overlay_still_uses_the_stencil_mask_path(self):
        source = _overlay_source()
        assert "GL_STENCIL_TEST" in source
        assert "GL_STENCIL_BUFFER_BIT" in source

    def test_qrhi_target_provides_a_depth_stencil_buffer(self, qapp):
        """The mask path needs a real stencil attachment on the QRhi target."""
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        parent.resize(320, 240)
        comp = GLCompositorWidget(parent)
        comp.resize(320, 240)
        comp.show()
        parent.show()
        overlay = SpotifyBarsGLOverlay(parent)
        overlay.setGeometry(10, 10, 160, 90)
        overlay.show()
        try:
            for _ in range(12):
                overlay.update()
                qapp.processEvents()
            if not overlay._rhi_gl.is_attached():
                pytest.skip("no QRhi surface available in this environment")
            assert overlay.depthStencilBuffer() is not None, (
                "rounded-card stencil mask requires a depth/stencil target"
            )
        finally:
            try:
                overlay.cleanup_gl()
            except Exception:
                pass
            parent.close()
            parent.deleteLater()


# ---------------------------------------------------------------------------
# Construction ordering
# ---------------------------------------------------------------------------


class TestConstructionOrdering:
    def test_overlay_joins_the_compositor_top_level_qrhi_after_show(self, qapp):
        """Production creates the overlay lazily, after the window is shown.

        That is only safe because the main compositor already locked the
        top-level window to an OpenGL QRhi before show. This is the exact
        production shape, and it must keep resolving to the SAME top-level QRhi.
        """
        from PySide6.QtWidgets import QWidget

        parent = QWidget()
        parent.resize(320, 240)
        comp = GLCompositorWidget(parent)
        comp.resize(320, 240)
        comp.show()
        parent.show()
        qapp.processEvents()

        overlay = SpotifyBarsGLOverlay(parent)
        overlay.setGeometry(0, 0, 160, 90)
        overlay.show()
        try:
            for _ in range(15):
                comp.update()
                overlay.update()
                qapp.processEvents()

            if not comp._rhi_gl.is_attached():
                pytest.skip("no QRhi surface available in this environment")

            assert overlay._rhi_gl.is_attached(), (
                "overlay created after show must still obtain the top-level QRhi"
            )
            assert overlay._rhi_gl.rhi is comp._rhi_gl.rhi, (
                "both surfaces must share one top-level QRhi backend"
            )
            assert overlay._rhi_gl.context is comp._rhi_gl.context
        finally:
            for widget in (overlay, comp):
                try:
                    widget.cleanup_gl() if widget is overlay else widget.cleanup()
                except Exception:
                    pass
            parent.close()
            parent.deleteLater()

    def test_no_silent_qopenglwidget_fallback_exists(self):
        from PySide6.QtOpenGLWidgets import QOpenGLWidget

        assert QOpenGLWidget not in SpotifyBarsGLOverlay.__mro__

        module_tree = ast.parse(
            pathlib.Path(inspect.getfile(SpotifyBarsGLOverlay)).read_text(
                encoding="utf-8"
            )
        )
        referenced = {
            node.id for node in ast.walk(module_tree) if isinstance(node, ast.Name)
        } | {
            alias.name.split(".")[-1]
            for node in ast.walk(module_tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }
        assert "QOpenGLWidget" not in referenced, (
            "no QOpenGLWidget fallback may remain reachable in the overlay module"
        )


# ---------------------------------------------------------------------------
# Buffer clear ownership
# ---------------------------------------------------------------------------


class TestClearOverlayBuffer:
    def test_clear_overlay_buffer_does_no_raw_gl_target_mutation(self):
        """Outside the render callback this surface's target is not bound."""
        method = _method_ast("clear_overlay_buffer")
        called = _self_calls(method)
        for forbidden in ("makeCurrent", "doneCurrent", "repaint"):
            assert forbidden not in called

        gl_calls = {
            node.func.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "gl"
        }
        assert gl_calls == set(), (
            f"clear_overlay_buffer must not touch raw GL, found {gl_calls}"
        )

    def test_clear_overlay_buffer_still_requests_a_frame(self):
        assert "update" in _self_calls(_method_ast("clear_overlay_buffer"))

    def test_clear_overlay_buffer_still_resets_logical_payload(self):
        source = inspect.getsource(SpotifyBarsGLOverlay.clear_overlay_buffer)
        for field in ("_bars", "_bubble_pos_data", "_waveform", "_peaks", "_fade"):
            assert field in source


# ---------------------------------------------------------------------------
# Ownership: no QOpenGLWidget context semantics anywhere
# ---------------------------------------------------------------------------


class TestBorrowedContextOwnership:
    def test_overlay_never_uses_qopenglwidget_context_ownership(self):
        tree = ast.parse(_overlay_source())
        offenders = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr in {"makeCurrent", "doneCurrent", "isValid", "context"}
        }
        assert offenders == set(), f"QOpenGLWidget ownership calls remain: {offenders}"

    def test_gpu_timer_queries_receive_the_borrowed_context(self):
        source = inspect.getsource(SpotifyBarsGLOverlay.gl_initialize)
        assert "self._rhi_gl.context" in source

    def test_deferred_warmup_is_generation_fenced(self):
        method = _method_ast("_warm_next_gl_program")

        attributes = {
            node.attr for node in ast.walk(method) if isinstance(node, ast.Attribute)
        }
        assert "generation" in attributes, "warmup must capture the QRhi generation"
        assert "make_current" in attributes, "warmup must borrow the QRhi context"
        assert "doneCurrent" not in attributes, (
            "the borrowed Qt-owned context must never be released by SRPSS"
        )

        # The captured generation must actually be compared, not just read.
        compared = any(
            isinstance(node, ast.Compare)
            and any(
                isinstance(sub, ast.Attribute) and sub.attr == "generation"
                for sub in ast.walk(node)
            )
            for node in ast.walk(method)
        )
        assert compared, "the captured generation must be re-checked after compiling"

    def test_no_hidden_temporary_qrhi_grab_cycle_remains(self):
        """grabFramebuffer on an unassociated surface can spin a temporary QRhi."""
        source = inspect.getsource(SpotifyBarsGLOverlay.prewarm_context)
        tree = ast.parse(textwrap.dedent(source))
        assert "grabFramebuffer" not in _self_calls(tree)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_resize_does_not_rebuild_immutable_resources(self):
        calls: list[str] = []
        overlay = SimpleNamespace(
            _gl_state=SimpleNamespace(
                is_ready=lambda: True,
                get_state=lambda: None,
                transition=lambda *_a, **_k: calls.append("transition") or True,
            ),
            _gl_programs={"bubble": 7},
            _rhi_gl=SimpleNamespace(generation=1),
        )
        SpotifyBarsGLOverlay.gl_initialize(overlay, False)
        assert calls == [], "a plain resize must not re-enter initialization"

    def test_generation_replacement_reports_surviving_live_resources(self, caplog):
        import logging

        state = SimpleNamespace(
            is_ready=lambda: True,
            get_state=lambda: None,
            transition=lambda *_a, **_k: False,
        )
        overlay = SimpleNamespace(
            _gl_state=state,
            _gl_programs={"bubble": 7},
            _gl_program=7,
            _gl_mask_program=None,
            _gl_vbo=None,
            _gl_vao=None,
            _gpu_timer_queries=None,
            _rhi_gl=SimpleNamespace(generation=2),
        )
        overlay._has_live_gl_resources = (
            lambda: SpotifyBarsGLOverlay._has_live_gl_resources(overlay)
        )
        with caplog.at_level(logging.CRITICAL):
            SpotifyBarsGLOverlay.gl_initialize(overlay, True)

        assert any(
            "generation changed while overlay GL resources" in r.getMessage()
            for r in caplog.records
        ), "unreachable ids must be reported, not silently overwritten"

    def test_a_replaced_generation_can_reach_ready_again(self):
        """DESTROYED is terminal per generation, not for a live overlay object."""
        from rendering.gl_state_manager import GLContextState, GLStateManager

        overlay = SimpleNamespace(_gl_state=GLStateManager("p2-test"))
        overlay._gl_state.transition(GLContextState.INITIALIZING)
        overlay._gl_state.transition(GLContextState.READY)
        overlay._gl_state.transition(GLContextState.DESTROYING)
        overlay._gl_state.transition(GLContextState.DESTROYED)
        assert overlay._gl_state.get_state() == GLContextState.DESTROYED
        assert not overlay._gl_state.transition(GLContextState.INITIALIZING)

        SpotifyBarsGLOverlay._reset_gl_state_for_new_generation(overlay)

        assert overlay._gl_state.get_state() == GLContextState.UNINITIALIZED
        assert overlay._gl_state.transition(GLContextState.INITIALIZING)
        assert overlay._gl_state.transition(GLContextState.READY)

    def test_cleanup_fails_closed_without_an_attached_qrhi(self):
        from rendering.gl_state_manager import GLContextState, GLStateManager

        state = GLStateManager("p2-cleanup")
        state.transition(GLContextState.INITIALIZING)
        state.transition(GLContextState.READY)
        overlay = SimpleNamespace(
            _gl_program_warm_timer=None,
            _gl_program_warm_queue=[],
            _gl_programs={"bubble": 11},
            _gl_uniforms={},
            _gl_program=11,
            _gl_program_rids={},
            _gl_mask_program=None,
            _gl_vbo=None,
            _gl_vao=None,
            _gpu_timer_queries=None,
            _gl_state=state,
            _rhi_gl=SimpleNamespace(
                is_attached=lambda: False, make_current=lambda: False, context=None
            ),
        )
        overlay._has_live_gl_resources = (
            lambda: SpotifyBarsGLOverlay._has_live_gl_resources(overlay)
        )
        with pytest.raises(RuntimeError, match="no QRhi OpenGL context is attached"):
            SpotifyBarsGLOverlay.cleanup_gl(overlay)
        assert overlay._gl_programs == {"bubble": 11}, "ownership must be retained"

    def test_qt_release_reuses_the_same_deletion_owner(self):
        """gl_release() must not become a second deletion implementation."""
        source = inspect.getsource(SpotifyBarsGLOverlay.gl_release)
        assert "cleanup_gl" in source
        tree = ast.parse(textwrap.dedent(source))
        gl_calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "gl"
        }
        assert gl_calls == set(), "release must delegate, not delete directly"

    def test_qt_release_never_raises_into_the_virtual_override(self):
        def _boom():
            raise RuntimeError("deletion failed")

        overlay = SimpleNamespace(cleanup_gl=_boom)
        SpotifyBarsGLOverlay.gl_release(overlay)  # must not raise


# ---------------------------------------------------------------------------
# Presentation contract: the request stream must be untouched
# ---------------------------------------------------------------------------


class TestPresentationContractUnchanged:
    def test_set_state_still_requests_exactly_one_update_per_publication(self):
        set_state = _method_ast("set_state")
        assert "_request_frame_update" in _self_calls(set_state)
        assert "update" not in _self_calls(set_state), (
            "set_state must route through the single request owner"
        )

        request = _method_ast("_request_frame_update")
        assert "update" in _self_calls(request)

    def test_no_admission_or_pacing_mechanism_was_introduced(self):
        request = _method_ast("_request_frame_update")
        source = inspect.getsource(SpotifyBarsGLOverlay._request_frame_update)
        for forbidden in (
            "_update_pending",
            "_owner_target_fps",
            "singleShot",
            "QTimer",
            "elapsed",
            "monotonic",
        ):
            assert forbidden not in source, (
                f"P2-RHI-A must not change the request stream ({forbidden})"
            )
        assert "start" not in _self_calls(request)

    def test_render_callback_does_not_schedule_repaints(self):
        called = _self_calls(_method_ast("gl_render"))
        for forbidden in ("update", "repaint", "singleShot"):
            assert forbidden not in called

    def test_render_callback_does_not_own_logical_state_evolution(self):
        """gl_render consumes already-integrated state; it never simulates."""
        source = inspect.getsource(SpotifyBarsGLOverlay.gl_render)
        for forbidden in ("_integrate", "_advance", "_simulate", "_smooth_"):
            assert forbidden not in source
