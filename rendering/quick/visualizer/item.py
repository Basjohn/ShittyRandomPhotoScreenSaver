"""Sub-rect Quick item synchronizing immutable visualizer state."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt
from PySide6.QtQuick import QQuickItem, QSGNode

from widgets.spotify_visualizer.render_bridge import (
    VisualizerRenderIdentity,
    VisualizerSnapshotBridge,
)
from widgets.spotify_visualizer.render_state import ResolvedVisualizerPresentation

from .node import VisualizerRenderNode
from .telemetry import VisualizerRenderNodeTelemetry


class _RenderNodeRetirement:
    """Direct render-thread invalidation owner for the current node."""

    def __init__(self, telemetry: VisualizerRenderNodeTelemetry) -> None:
        self._telemetry = telemetry
        self._lock = threading.Lock()
        self._node: VisualizerRenderNode | None = None

    def set_node(self, node: VisualizerRenderNode) -> None:
        with self._lock:
            self._node = node

    def invalidate(self) -> None:
        self._telemetry.note_invalidation()
        with self._lock:
            node = self._node
            self._node = None
        if node is not None:
            node.releaseResources()


class VisualizerRenderItem(QQuickItem):
    """Consume one latest immutable snapshot at the Quick sync boundary.

    Clipping is owned by the render node's single local SDF/stencil host. The
    pinned PySide scene-graph clip-node path failed its D3 runtime bar, so no
    second selectable clip implementation remains.
    """

    def __init__(
        self,
        parent: QQuickItem | None = None,
        *,
        telemetry: VisualizerRenderNodeTelemetry | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self._telemetry = telemetry or VisualizerRenderNodeTelemetry()
        self._retirement = _RenderNodeRetirement(self._telemetry)
        self._bridge: VisualizerSnapshotBridge | None = None
        self._identity: VisualizerRenderIdentity | None = None
        self._presentation: ResolvedVisualizerPresentation | None = None
        self._bound_window = None
        self.windowChanged.connect(self._bind_window_invalidation)
        self._bind_window_invalidation(self.window())

    @property
    def telemetry(self) -> VisualizerRenderNodeTelemetry:
        return self._telemetry

    @property
    def render_identity(self) -> VisualizerRenderIdentity | None:
        return self._identity

    @property
    def presentation(self) -> ResolvedVisualizerPresentation | None:
        return self._presentation

    def bind_render_source(
        self,
        bridge: VisualizerSnapshotBridge,
        identity: VisualizerRenderIdentity,
    ) -> None:
        if not isinstance(bridge, VisualizerSnapshotBridge):
            raise TypeError("visualizer item requires a VisualizerSnapshotBridge")
        if not isinstance(identity, VisualizerRenderIdentity):
            raise TypeError("visualizer item requires a VisualizerRenderIdentity")
        if bridge.identity != identity:
            raise ValueError("visualizer bridge is not open for the requested identity")
        self._bridge = bridge
        self._identity = identity
        self.update()

    def clear_render_source(self) -> None:
        if self._bridge is None and self._identity is None:
            return
        self._bridge = None
        self._identity = None
        self.update()

    def set_presentation(
        self,
        presentation: ResolvedVisualizerPresentation | None,
    ) -> None:
        if presentation is not None and not isinstance(
            presentation,
            ResolvedVisualizerPresentation,
        ):
            raise TypeError("visualizer presentation must already be resolved")
        if presentation == self._presentation:
            return
        self._presentation = presentation
        if presentation is not None:
            _x, _y, width, height = presentation.outer_rect
            self.setX(0.0)
            self.setY(0.0)
            self.setWidth(width)
            self.setHeight(height)
        self.update()

    def _bind_window_invalidation(self, window) -> None:
        if window is self._bound_window:
            return
        if self._bound_window is not None:
            try:
                self._bound_window.sceneGraphInvalidated.disconnect(
                    self._retirement.invalidate
                )
            except (RuntimeError, TypeError):
                pass
        self._bound_window = window
        if window is not None:
            window.sceneGraphInvalidated.connect(
                self._retirement.invalidate,
                Qt.ConnectionType.DirectConnection,
            )

    def _create_render_node(self) -> VisualizerRenderNode:
        return VisualizerRenderNode(self._telemetry)

    def updatePaintNode(
        self,
        old_node: QSGNode | None,
        _update_data: QQuickItem.UpdatePaintNodeData,
    ) -> QSGNode:
        node = (
            old_node
            if isinstance(old_node, VisualizerRenderNode)
            else self._create_render_node()
        )
        presentation = self._presentation
        bridge = self._bridge
        identity = self._identity
        snapshot = None
        clear_snapshot = presentation is None or identity is None
        if bridge is not None and identity is not None and presentation is not None:
            snapshot = bridge.take_for_render(
                runtime_generation=identity.runtime_generation,
                engine_generation=identity.engine_generation,
                activation_id=identity.activation_id,
                mode_id=identity.mode_id,
            )
            if snapshot is not None and snapshot.presentation != presentation:
                self._telemetry.note_error(
                    "visualizer snapshot presentation does not match committed item geometry"
                )
                snapshot = None
                clear_snapshot = True

        logical_size = (
            (0.0, 0.0)
            if presentation is None
            else (presentation.outer_rect[2], presentation.outer_rect[3])
        )
        node.synchronize(
            identity=identity,
            snapshot=snapshot,
            logical_size=logical_size,
            device_pixel_ratio=(1.0 if presentation is None else presentation.dpr),
            clear_snapshot=clear_snapshot,
        )
        self._retirement.set_node(node)
        return node


__all__ = ["VisualizerRenderItem"]
