"""Lifecycle and cleanup tests for GLCompositorWidget.

These tests focus on the GLSL pipeline teardown path to ensure that
`GLCompositorWidget.cleanup()` is safe to call multiple times and behaves
correctly when a GL context is (or is not) available.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from rendering.gl_compositor import GLCompositorWidget, gl as _gl


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

    try:
        comp.makeCurrent()
    except Exception:
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

