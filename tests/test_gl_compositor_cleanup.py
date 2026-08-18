"""Lifecycle and cleanup tests for GLCompositorWidget.

These tests focus on the GLSL pipeline teardown path to ensure that
`GLCompositorWidget.cleanup()` is safe to call multiple times and behaves
correctly when a GL context is (or is not) available.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from rendering.gl_compositor import GLCompositorWidget, gl as _gl
from rendering import gl_compositor
from rendering.gl_state_manager import GLContextState


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.mark.qt_no_exception_capture
def test_gl_compositor_cleanup_idempotent_without_context(qapp):
    """cleanup() should be safe and idempotent even without a GL context.

    This covers environments where PyOpenGL or an OpenGL context is not
    available; the method must degrade gracefully and never raise.
    """

    parent = QWidget()
    parent.resize(64, 64)

    comp = GLCompositorWidget(parent)
    comp.setGeometry(parent.rect())
    comp.show()
    parent.show()

    # Call cleanup multiple times without forcing a GL context.
    comp.cleanup()
    comp.cleanup()


def test_cleanup_refuses_gl_teardown_while_adaptive_worker_is_live():
    class _State:
        @staticmethod
        def get_state():
            return GLContextState.READY

    compositor = type(
        "CompositorStub",
        (),
        {
            "_gl_state": _State(),
            "_presentation_reasons": set(),
            "_render_shutdown_requested": False,
            "_gl_lifecycle_generation": 1,
            "_transition_animation_generation": 1,
            "_cancel_current_animation": lambda self: None,
            "_stop_render_strategy": lambda self: False,
        },
    )()

    with pytest.raises(RuntimeError, match="refusing GL/context teardown"):
        GLCompositorWidget.cleanup(compositor)

    assert compositor._render_shutdown_requested is True


@pytest.mark.qt_no_exception_capture
def test_gl_compositor_cleanup_releases_pipeline_when_gl_available(qapp):
    """When GL is available, cleanup() should tear down the shader pipeline.

    The test attempts to initialise the internal GLSL pipeline and then calls
    cleanup(), asserting that the pipeline is marked uninitialised and its
    GL object ids are cleared. All operations must be exception-safe and
    idempotent.
    """

    if _gl is None:
        pytest.skip("PyOpenGL not available; skipping GL-specific cleanup test")

    parent = QWidget()
    parent.resize(64, 64)

    comp = GLCompositorWidget(parent)
    comp.setGeometry(parent.rect())
    comp.show()
    parent.show()

    # Realize the QRhi surface, then borrow its Qt-owned OpenGL context.
    for _ in range(10):
        comp.update()
        qapp.processEvents()
    if not comp._rhi_gl.is_attached() or not comp._rhi_gl.make_current():
        pytest.skip("GL context not available for GLCompositorWidget cleanup test")

    # Attempt to initialise the GLSL pipeline; failures should simply leave
    # the shader path disabled for this session.
    try:
        comp._init_gl_pipeline()  # type: ignore[attr-defined]
    except Exception:
        comp.cleanup()
        comp.cleanup()
        return

    state = getattr(comp, "_gl_pipeline", None)
    if state is None:
        # Pipeline was not created; cleanup must still be safe and idempotent.
        comp.cleanup()
        comp.cleanup()
        return

    # After explicit initialisation, the pipeline should report initialised.
    if not state.initialized:
        # If initialisation was short-circuited (e.g. GL version/driver
        # limitations), we still only require that cleanup is safe.
        comp.cleanup()
        comp.cleanup()
        return

    # Perform cleanup and verify that the pipeline is reset.
    comp.cleanup()

    assert state.initialized is False
    assert state.basic_program == 0
    assert state.quad_vao == 0
    assert state.quad_vbo == 0

    # Second cleanup must be a no-op from the pipeline's perspective.
    comp.cleanup()


@pytest.mark.qt_no_exception_capture
def test_two_live_compositors_have_distinct_program_owners_and_cleanup(qapp):
    """Reproduce the multi-display Settings/Edit teardown ownership shape."""
    if _gl is None:
        pytest.skip("PyOpenGL not available; skipping GL-specific cleanup test")

    parent = QWidget()
    parent.resize(160, 80)
    compositors = [GLCompositorWidget(parent), GLCompositorWidget(parent)]
    for index, comp in enumerate(compositors):
        comp.setGeometry(index * 80, 0, 80, 80)
        comp.show()
    parent.show()
    qapp.processEvents()

    initialized = []
    for comp in compositors:
        for _ in range(10):
            comp.update()
            qapp.processEvents()
        try:
            if not comp._rhi_gl.is_attached() or not comp._rhi_gl.make_current():
                raise RuntimeError("no borrowed QRhi context")
            comp._init_gl_pipeline()  # type: ignore[attr-defined]
        except Exception:
            for candidate in compositors:
                candidate.cleanup()
            pytest.skip("GL context unavailable for multi-compositor cleanup test")
        initialized.append(bool(getattr(comp._gl_pipeline, "initialized", False)))

    if not all(initialized):
        for comp in compositors:
            comp.cleanup()
        pytest.skip("Shader pipeline unavailable for multi-compositor cleanup test")

    assert compositors[0]._program_cache is not compositors[1]._program_cache
    assert compositors[0]._program_cache.has_live_programs()
    assert compositors[1]._program_cache.has_live_programs()

    # This exact sequence previously deleted globally shared IDs through the
    # first context, then raised GL_INVALID_VALUE in the second context.
    compositors[0].cleanup()
    compositors[1].cleanup()

    assert not compositors[0]._program_cache.has_live_programs()
    assert not compositors[1]._program_cache.has_live_programs()


@pytest.mark.qt_no_exception_capture
def test_compositor_perf_query_handles_use_real_owner_context_and_cleanup(
    qapp,
    monkeypatch,
):
    """Exercise production compositor query initialization and strict deletion."""

    if _gl is None:
        pytest.skip("PyOpenGL not available; skipping GL timer-query integration")
    monkeypatch.setattr(gl_compositor, "is_perf_metrics_enabled", lambda: True)
    monkeypatch.setattr(gl_compositor, "is_gpu_timing_enabled", lambda: True)

    parent = QWidget()
    parent.resize(64, 64)
    comp = gl_compositor.GLCompositorWidget(parent)
    comp.setGeometry(parent.rect())
    comp.show()
    parent.show()
    qapp.processEvents()

    try:
        comp.grabFramebuffer()
    except Exception:
        comp.cleanup()
        pytest.skip("GL context unavailable for compositor timer-query test")

    timer_queries = comp._gpu_timer_queries
    if timer_queries is None or not timer_queries.supported:
        comp.cleanup()
        pytest.skip("GL timer queries unavailable on this compositor context")

    assert timer_queries.has_live_queries()
    comp.cleanup()
    assert not timer_queries.has_live_queries()
