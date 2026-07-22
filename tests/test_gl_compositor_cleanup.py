"""Lifecycle and cleanup tests for GLCompositorWidget.

These tests focus on the GLSL pipeline teardown path to ensure that
`GLCompositorWidget.cleanup()` is safe to call multiple times and behaves
correctly when a GL context is (or is not) available.
"""

from __future__ import annotations

import time

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from rendering.gl_compositor import GLCompositorWidget, gl as _gl
from rendering.gl_compositor_pkg import gl_lifecycle


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


def test_compositor_cleanup_deletes_only_private_program(monkeypatch):
    deleted: list[int] = []

    class _FakeGL:
        @staticmethod
        def glIsProgram(_program_id):
            return True

        @staticmethod
        def glDeleteProgram(program_id):
            deleted.append(int(program_id))

    class _Pipeline:
        basic_program = 11
        warp_program = 22

    class _Manager:
        def cleanup(self):
            return None

    class _Widget:
        def __init__(self):
            self._gl_pipeline = _Pipeline()
            self._texture_manager = _Manager()
            self._geometry_manager = _Manager()
            self._startup_transition_warm_queue = []
            self._startup_transition_resource_warm_queue = []
            self._startup_transition_resource_warm_types = set()
            self._deferred_warmup_context = None
            self._deferred_warmup_surface = None
            self.reset_calls = 0

        def isValid(self):
            return True

        def makeCurrent(self):
            return None

        def doneCurrent(self):
            return None

        def _reset_pipeline_state(self):
            self.reset_calls += 1

    monkeypatch.setattr(gl_lifecycle, "gl", _FakeGL())

    widget = _Widget()
    gl_lifecycle.cleanup_gl_pipeline(widget)

    assert deleted == [11]
    assert widget.reset_calls == 1


def test_hidden_warmup_cleanup_releases_context_before_surface(monkeypatch):
    events: list[str] = []

    class _Context:
        def thread(self):
            return None

        def doneCurrent(self):
            events.append("doneCurrent")

        def deleteLater(self):
            events.append("deleteContext")

    class _Surface:
        def thread(self):
            return None

        def destroy(self):
            events.append("destroySurface")

        def deleteLater(self):
            events.append("deleteSurface")

    widget = type(
        "_Widget",
        (),
        {
            "_deferred_warmup_context": _Context(),
            "_deferred_warmup_surface": _Surface(),
            "_deferred_warmup_generation": 4,
            "_deferred_warmup_owner_thread": object(),
        },
    )()
    monkeypatch.setattr(gl_lifecycle, "QOpenGLContext", _Context)
    monkeypatch.setattr(gl_lifecycle, "QOffscreenSurface", _Surface)

    gl_lifecycle._cleanup_deferred_warmup_resources(widget)

    assert events == [
        "doneCurrent",
        "destroySurface",
        "deleteSurface",
        "deleteContext",
    ]
    assert widget._deferred_warmup_context is None
    assert widget._deferred_warmup_surface is None
    assert widget._deferred_warmup_generation == 0
    assert widget._deferred_warmup_owner_thread is None


def test_affinity_guard_rejects_before_qt_operation(monkeypatch):
    owner = object()
    current = object()
    calls: list[str] = []

    class _ThreadApi:
        @staticmethod
        def currentThread():
            return current

    class _Object:
        def thread(self):
            return owner

        def makeCurrent(self):
            calls.append("makeCurrent")

    monkeypatch.setattr(gl_lifecycle, "QThread", _ThreadApi)

    with pytest.raises(RuntimeError, match="affinity violation"):
        gl_lifecycle.assert_qt_affinity(_Object(), operation="test.makeCurrent")

    assert calls == []


@pytest.mark.qt_no_exception_capture
def test_permanent_quiesce_requests_stop_without_waiting_on_qt(qapp):
    parent = QWidget()
    comp = GLCompositorWidget(parent)
    events: list[str] = []

    class _RetiringManager:
        def pause(self):
            events.append("pause")

        def request_stop(self):
            events.append("request_stop")
            return False

        def stop(self):
            raise AssertionError("Qt quiesce must not synchronously stop/join")

    comp._render_strategy_manager = _RetiringManager()
    try:
        started = time.perf_counter()
        comp.begin_quiesce(
            reason="test_permanent",
            snap_to_new=True,
            permanent=True,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000.0

        assert elapsed_ms < 25.0
        assert events[-1] == "request_stop"
        assert events.count("pause") >= 1
        assert events.count("request_stop") == 1
        assert comp._render_shutdown_requested is True
        assert comp._admission_open is False
        assert comp._render_owner_stopped_ack is False
        assert comp._render_owner_stop_requested_ts > 0.0
    finally:
        comp._render_strategy_manager = None
        comp.cleanup()


@pytest.mark.qt_no_exception_capture
def test_render_owner_ack_racing_request_return_is_not_overwritten(qapp):
    parent = QWidget()
    comp = GLCompositorWidget(parent)

    class _InlineAckManager:
        def request_stop(self):
            comp._render_owner_stop_acknowledged()
            return False

    comp._render_strategy_manager = _InlineAckManager()
    try:
        assert comp._stop_render_strategy() is True
        assert comp._render_owner_stopped_ack is True
        assert comp._render_owner_stop_requested_ts == 0.0
    finally:
        comp._render_strategy_manager = None
        comp.cleanup()

