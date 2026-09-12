"""Focused render-thread retirement regressions for inline visualizer modes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtQuick import QQuickWindow

from rendering.quick.visualizer import item as item_module
from rendering.quick.visualizer import render_host as render_host_module
from rendering.quick.visualizer import VisualizerRenderItem
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from rendering.quick.visualizer.telemetry import (
    VisualizerRenderHostLifecycleTelemetry,
    VisualizerRenderNodeTelemetry,
)
from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge


def _instrumented_host() -> QuickVisualizerRenderHost:
    """A host with lifecycle telemetry injected directly (opt-in seam for P2).

    P2 proves ownership boundedness by reading the boundary telemetry, so it
    injects the telemetry object rather than depending on the process argv
    admission (``--viz-switch-telemetry`` / ``--abc-drive``).
    """
    return QuickVisualizerRenderHost(
        lifecycle_telemetry=VisualizerRenderHostLifecycleTelemetry()
    )


class _FakeRenderer:
    def __init__(self, *, fail_release: bool = False) -> None:
        self._has_resources = True
        self.fail_release = fail_release
        self.release_count = 0

    @property
    def has_resources(self) -> bool:
        return self._has_resources

    def render(self, _frame) -> None:
        self._has_resources = True

    def release_resources(self) -> None:
        self.release_count += 1
        if self.fail_release:
            raise RuntimeError("release failed")
        self._has_resources = False


def test_inactive_cleanup_requires_context_and_retries_failed_renderer(monkeypatch) -> None:
    host = QuickVisualizerRenderHost()
    failed = _FakeRenderer(fail_release=True)
    active = _FakeRenderer()
    host._implementations = {"sphere": failed, "bubble": active}

    monkeypatch.setattr(
        render_host_module,
        "QOpenGLContext",
        SimpleNamespace(currentContext=staticmethod(lambda: None)),
    )
    with pytest.raises(RuntimeError, match="without a current GL context"):
        host.release_inactive_implementations("bubble")
    assert host.resolved_mode_ids == frozenset({"sphere", "bubble"})
    assert failed.release_count == 0

    monkeypatch.setattr(
        render_host_module,
        "QOpenGLContext",
        SimpleNamespace(currentContext=staticmethod(object)),
    )
    with pytest.raises(RuntimeError, match="inactive cleanup incomplete"):
        host.release_inactive_implementations("bubble")
    assert host.resolved_mode_ids == frozenset({"sphere", "bubble"})
    assert failed.release_count == 1

    failed.fail_release = False
    host.release_inactive_implementations("bubble")
    assert failed.release_count == 2
    assert host.resolved_mode_ids == frozenset({"bubble"})
    assert active.release_count == 0


def _install_host_render_stubs(monkeypatch, host, renderers):
    """Make ``host.render()`` drivable without a real GL context.

    ``renderers`` is a mode_id -> _FakeRenderer map; a mode is resolved once and
    reused, matching production lazy resolution. The shared quad is pre-owned so
    ``_ensure_quad`` short-circuits and we can prove it is never multiplied.
    """
    host._quad_vao = 7
    host._quad_vbo = 7
    monkeypatch.setattr(
        render_host_module,
        "QOpenGLContext",
        SimpleNamespace(currentContext=staticmethod(object)),
    )

    def _resolve(mode_id):
        renderer = renderers.get(mode_id)
        if renderer is None or not renderer.has_resources:
            renderer = _FakeRenderer()
            renderers[mode_id] = renderer
        return renderer

    monkeypatch.setattr(
        render_host_module, "resolve_quick_visualizer_renderer", _resolve
    )
    monkeypatch.setattr(
        render_host_module._InheritedGlState,
        "capture",
        lambda: SimpleNamespace(restore=lambda: None),
    )
    for name in (
        "glEnable",
        "glBlendEquationSeparate",
        "glBlendFuncSeparate",
        "glDisable",
        "glDepthMask",
        "glViewport",
        "glDeleteBuffers",
        "glDeleteVertexArrays",
    ):
        monkeypatch.setattr(render_host_module.gl, name, lambda *_args: None)


def _render_mode(host, mode_id):
    snapshot = SimpleNamespace(logical=SimpleNamespace(mode_id=mode_id))
    return host.render(
        snapshot=snapshot,
        viewport=(0, 0, 100, 100),
        logical_size=(100.0, 100.0),
        matrix_values=(1.0,) * 16,
    )


def test_repeated_mode_switches_keep_one_active_renderer_and_bounded_quad(monkeypatch):
    """P2: >=100 completed switches converge to the one-active-renderer invariant.

    Proves lifecycle boundedness (not the physical perf bug): every switch retires
    the previous inactive renderer, resolved ownership stays == {active}, retired
    renderers lose resources and drop from cache, release/resolve counts grow with
    real boundaries (not rendered frames), and the shared quad is never multiplied.
    """
    host = _instrumented_host()
    renderers: dict[str, _FakeRenderer] = {}
    _install_host_render_stubs(monkeypatch, host, renderers)

    modes = ("spectrum", "oscilloscope", "sine_wave", "bubble", "sphere")
    quad_vao = host._quad_vao
    completed = 0
    previous_mode = None
    previous_renderer = None
    for cycle in range(22):  # 22 * 5 = 110 completed mode changes
        for mode in modes:
            assert _render_mode(host, mode) == mode
            completed += 1

            # 2: after every completed switch, exactly the active mode is resolved.
            assert host.resolved_mode_ids == frozenset({mode})
            # 1 + 3: the previous inactive renderer retired, lost resources, and
            # is no longer cached.
            if previous_mode is not None and previous_mode != mode:
                assert previous_renderer.release_count == 1
                assert previous_renderer.has_resources is False
                assert previous_mode not in host.resolved_mode_ids
            # 5: the shared host quad is not recreated/multiplied by a switch.
            assert host._quad_vao == quad_vao
            assert host._quad_vbo == quad_vao

            previous_mode = mode
            previous_renderer = renderers[mode]

            # Extra same-mode frames must not resolve/release/advance boundaries.
            snap = host.lifecycle_snapshot()
            _render_mode(host, mode)
            _render_mode(host, mode)
            after = host.lifecycle_snapshot()
            assert after.mode_boundary_seq == snap.mode_boundary_seq
            assert after.renderer_resolve_count == snap.renderer_resolve_count

    assert completed == 110
    lifecycle = host.lifecycle_snapshot()
    # 4: release/resolve counts track real boundaries, not rendered frames.
    # 110 switches: first mode of the whole run has no predecessor to retire.
    assert lifecycle.mode_boundary_seq == 110
    assert lifecycle.renderer_resolve_count == 110
    assert lifecycle.inactive_release_successes == 109
    assert lifecycle.inactive_release_failures == 0
    assert lifecycle.resolved_mode_ids == ("sphere",)
    assert lifecycle.quad_vao_owned is True

    # 8: full host release leaves no implementations and no host quad resources.
    host.release_resources()
    assert host.resolved_mode_ids == frozenset()
    assert host._quad_vao == 0 and host._quad_vbo == 0
    assert host.has_resources is False
    final = host.lifecycle_snapshot()
    assert final.full_release_count == 1
    assert final.quad_vao_owned is False and final.quad_vbo_owned is False
    assert final.resolved_mode_ids == ()


def test_repeated_switch_injected_release_failure_is_accounted_then_retried(monkeypatch):
    """P2 item 6: a failed inactive release stays accounted/cached, then a later
    legal render retries it and restores the one-active-renderer invariant."""
    host = _instrumented_host()
    renderers: dict[str, _FakeRenderer] = {}
    _install_host_render_stubs(monkeypatch, host, renderers)

    assert _render_mode(host, "bubble") == "bubble"
    bubble = renderers["bubble"]
    bubble.fail_release = True

    # Switching to spectrum tries to retire bubble; the failed release must raise,
    # keep bubble cached/accounted, and register a lifecycle failure.
    with pytest.raises(RuntimeError, match="inactive cleanup incomplete"):
        _render_mode(host, "spectrum")
    assert "bubble" in host.resolved_mode_ids
    assert bubble.release_count == 1
    failed_snapshot = host.lifecycle_snapshot()
    assert failed_snapshot.inactive_release_failures == 1
    assert failed_snapshot.last_release_error is not None
    # Current ownership is broken while the failed renderer is still retained.
    assert failed_snapshot.last_release_failure is not None
    assert failed_snapshot.release_failure_unresolved is True
    assert ("bubble", True) in failed_snapshot.resolved_has_resources

    # A later legal render (failure cleared) retries and converges to one active.
    bubble.fail_release = False
    assert _render_mode(host, "spectrum") == "spectrum"
    assert host.resolved_mode_ids == frozenset({"spectrum"})
    assert bubble.release_count == 2
    recovered = host.lifecycle_snapshot()
    assert recovered.inactive_release_successes >= 1
    assert recovered.resolved_mode_ids == ("spectrum",)
    # History is preserved (cumulative failure count + last failure text) but the
    # ownership is no longer currently unresolved after the successful retry.
    assert recovered.inactive_release_failures == 1
    assert recovered.last_release_failure is not None
    assert recovered.release_failure_unresolved is False


def test_render_retires_inactive_mode_before_resolving_current_mode(monkeypatch) -> None:
    host = QuickVisualizerRenderHost()
    old = _FakeRenderer()
    current = _FakeRenderer()
    host._implementations = {"sphere": old}
    monkeypatch.setattr(
        render_host_module,
        "QOpenGLContext",
        SimpleNamespace(currentContext=staticmethod(object)),
    )
    monkeypatch.setattr(
        render_host_module,
        "resolve_quick_visualizer_renderer",
        lambda mode_id: current if mode_id == "bubble" else None,
    )
    host._quad_vao = 1
    host._quad_vbo = 1
    monkeypatch.setattr(
        render_host_module._InheritedGlState,
        "capture",
        lambda: SimpleNamespace(restore=lambda: None),
    )
    for name in (
        "glEnable",
        "glBlendEquationSeparate",
        "glBlendFuncSeparate",
        "glDisable",
        "glDepthMask",
        "glViewport",
    ):
        monkeypatch.setattr(render_host_module.gl, name, lambda *_args: None)

    snapshot = SimpleNamespace(logical=SimpleNamespace(mode_id="bubble"))
    assert host.render(
        snapshot=snapshot,
        viewport=(0, 0, 100, 100),
        logical_size=(100.0, 100.0),
        matrix_values=(1.0,) * 16,
    ) == "bubble"
    assert old.release_count == 1
    assert host.resolved_mode_ids == frozenset({"bubble"})


class _Signal:
    def __init__(self):
        self.callbacks = []
    def connect(self, callback, connection):
        from PySide6.QtCore import Qt
        assert connection == Qt.ConnectionType.DirectConnection
        self.callbacks.append(callback)
    def disconnect(self, callback):
        self.callbacks.remove(callback)
    def emit(self):
        for callback in tuple(self.callbacks):
            callback()


class _Window:
    def __init__(self):
        self.beforeRendering = _Signal()
        self.sceneGraphInvalidated = _Signal()
        self.update_count = 0
    def update(self):
        self.update_count += 1


class _Node:
    def __init__(self):
        self.released_modes = []
        self.full_releases = 0
    def release_inactive_implementations(self, mode):
        self.released_modes.append(mode)
    def releaseResources(self):
        self.full_releases += 1


def _owner():
    retirement = item_module._RenderNodeRetirement(VisualizerRenderNodeTelemetry())
    window, node = _Window(), _Node()
    retirement.set_window(window)
    retirement.set_node(node, active_mode_id="sphere")
    return retirement, window, node


def test_clear_rebind_uses_latest_admission_and_disconnects_after_one_event():
    owner, window, node = _owner()
    owner.request_inactive_release(window=window, active_mode_id=None)
    owner.request_inactive_release(window=window, active_mode_id="sphere")
    assert window.update_count == 1
    assert len(window.beforeRendering.callbacks) == 1
    window.beforeRendering.emit()
    assert node.released_modes == ["sphere"]
    assert not window.beforeRendering.callbacks
    assert not window.sceneGraphInvalidated.callbacks
    for _ in range(5):
        owner.set_node(node, active_mode_id=None)
        window.beforeRendering.emit()
    assert window.update_count == 1
    assert node.released_modes == ["sphere"]


def test_switch_to_mode_without_a_first_snapshot_still_requests_cleanup(qt_app):
    from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge
    item = item_module.VisualizerRenderItem()
    owner, window, node = _owner()
    item._retirement = owner
    item._bound_window = window
    bridge = VisualizerSnapshotBridge()
    identity = bridge.begin_activation(runtime_generation=1, engine_generation=2,
                                       activation_id=3, mode_id="spectrum")
    item.bind_render_source(bridge, identity)
    item.bind_render_source(bridge, identity)
    assert window.update_count == 1
    assert bridge.peek() is None
    window.beforeRendering.emit()
    assert node.released_modes == ["spectrum"]
    item._bound_window = None
    item.deleteLater()


def test_detached_node_only_retires_on_its_old_window_context():
    owner, old_window, old_node = _owner()
    owner.request_inactive_release(window=old_window, active_mode_id=None)
    new_window, new_node = _Window(), _Node()
    owner.set_window(None)
    owner.set_window(new_window)
    owner.set_node(new_node, active_mode_id="bubble")
    new_window.beforeRendering.emit()
    assert old_node.full_releases == 0
    old_window.beforeRendering.emit()
    assert old_node.full_releases == 1
    assert old_node.released_modes == []
    assert new_node.full_releases == 0
    assert not old_window.beforeRendering.callbacks
    assert not old_window.sceneGraphInvalidated.callbacks


def test_context_invalidation_completes_pending_event_without_another_frame():
    owner, window, node = _owner()
    owner.request_inactive_release(window=window, active_mode_id=None)
    owner.invalidate()
    window.sceneGraphInvalidated.emit()
    assert node.full_releases == 1
    assert not window.beforeRendering.callbacks
    assert not window.sceneGraphInvalidated.callbacks
