"""Quick item that synchronizes background presentation into a render node."""

from __future__ import annotations

import threading

from PySide6.QtCore import Property, Signal, Qt
from PySide6.QtQuick import QQuickItem, QSGNode

from ..image_state import PresentationImage
from ..transitions.state import TransitionRun
from .background_node import BackgroundRenderNode, SlideProofState
from .telemetry import RenderNodeTelemetry


class _RenderNodeRetirement:
    """Render-thread invalidation owner for the item's current GL node."""

    def __init__(self, telemetry: RenderNodeTelemetry) -> None:
        self._telemetry = telemetry
        self._lock = threading.Lock()
        self._node: BackgroundRenderNode | None = None

    def set_node(self, node: BackgroundRenderNode) -> None:
        with self._lock:
            self._node = node

    def invalidate(self) -> None:
        """Run from sceneGraphInvalidated with the Quick GL context current."""

        self._telemetry.note_scene_graph_invalidated()
        with self._lock:
            node = self._node
            self._node = None
        if node is not None:
            node.releaseResources()


class BackgroundRenderItem(QQuickItem):
    """Full-scene custom content item backed by one inline QSGRenderNode."""

    proofProgressChanged = Signal()

    def __init__(
        self,
        parent: QQuickItem | None = None,
        *,
        telemetry: RenderNodeTelemetry | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self._proof_state = SlideProofState()
        self._presentation_image: PresentationImage | None = None
        self._transition_run: TransitionRun | None = None
        self._telemetry = telemetry or RenderNodeTelemetry(
            gui_thread_id=threading.get_ident()
        )
        self._retirement = _RenderNodeRetirement(self._telemetry)
        self._bound_window = None
        self.windowChanged.connect(self._bind_window_invalidation)
        self._bind_window_invalidation(self.window())

    def getProofProgress(self) -> float:
        return float(self._proof_state.progress)

    def setProofProgress(self, value: float) -> None:
        state = SlideProofState(progress=value).normalized()
        if state == self._proof_state:
            return
        self._proof_state = state
        self.proofProgressChanged.emit()
        self.update()

    proofProgress = Property(
        float,
        getProofProgress,
        setProofProgress,
        notify=proofProgressChanged,
    )

    @property
    def telemetry(self) -> RenderNodeTelemetry:
        return self._telemetry

    @property
    def presentation_image(self) -> PresentationImage | None:
        return self._presentation_image

    @property
    def transition_run(self) -> TransitionRun | None:
        return self._transition_run

    def set_presentation_image(self, image: PresentationImage | None) -> None:
        """Publish detached image state for the next render-thread sync."""

        if image is not None and not isinstance(image, PresentationImage):
            raise TypeError("Quick presentation requires a PresentationImage")
        current_identity = (
            None
            if self._presentation_image is None
            else self._presentation_image.identity
        )
        next_identity = None if image is None else image.identity
        if current_identity == next_identity:
            if image != self._presentation_image:
                raise ValueError(
                    "presentation image identity was reused for different content"
                )
            return
        self._presentation_image = image
        self.update()

    def set_transition_run(self, run: TransitionRun | None) -> None:
        """Publish one immutable run for render-thread monotonic sampling."""

        if run is not None and not isinstance(run, TransitionRun):
            raise TypeError("Quick transition presentation requires a TransitionRun")
        if run == self._transition_run:
            return
        self._transition_run = run
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

    def updatePaintNode(
        self,
        old_node: QSGNode | None,
        _update_data: QQuickItem.UpdatePaintNodeData,
    ) -> QSGNode:
        node = (
            old_node
            if isinstance(old_node, BackgroundRenderNode)
            else BackgroundRenderNode(self._telemetry)
        )
        window = self.window()
        device_pixel_ratio = (
            float(window.effectiveDevicePixelRatio()) if window is not None else 1.0
        )
        node.synchronize(
            logical_size=(float(self.width()), float(self.height())),
            device_pixel_ratio=device_pixel_ratio,
            state=self._proof_state,
            presentation_image=self._presentation_image,
            transition_run=self._transition_run,
        )
        self._retirement.set_node(node)
        return node
