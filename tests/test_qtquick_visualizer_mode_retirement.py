"""Focused render-thread retirement regressions for inline visualizer modes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtQuick import QQuickWindow

from rendering.quick.visualizer import item as item_module
from rendering.quick.visualizer import render_host as render_host_module
from rendering.quick.visualizer import VisualizerRenderItem
from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
from rendering.quick.visualizer.telemetry import VisualizerRenderNodeTelemetry
from widgets.spotify_visualizer.render_bridge import VisualizerSnapshotBridge


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
