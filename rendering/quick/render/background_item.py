"""Quick item that synchronizes retained background and transition presentation."""

from __future__ import annotations

import threading

from PySide6.QtCore import Property, Signal, Qt
from PySide6.QtQuick import QQuickItem, QSGNode

from ..image_state import PresentationImage
from ..transitions.state import TransitionRun
from .background_image_node import RetainedBackgroundSceneNode
from .background_node import BackgroundRenderNode, SlideProofState
from .telemetry import RenderNodeTelemetry
from core.performance.frame_trace import current_frame_trace


class _RenderNodeRetirement:
    """Render-thread invalidation owner for the current background subtree."""

    def __init__(self, telemetry: RenderNodeTelemetry) -> None:
        self._telemetry = telemetry
        self._lock = threading.Lock()
        self._node: RetainedBackgroundSceneNode | BackgroundRenderNode | None = None

    def set_node(
        self,
        node: RetainedBackgroundSceneNode | BackgroundRenderNode | None,
    ) -> None:
        with self._lock:
            self._node = node

    def invalidate(self) -> None:
        """Run from sceneGraphInvalidated on Qt Quick's render owner."""

        self._telemetry.note_scene_graph_invalidated()
        with self._lock:
            node = self._node
            self._node = None
        if isinstance(node, RetainedBackgroundSceneNode):
            node.release_resources()
        elif isinstance(node, BackgroundRenderNode):
            # Compatibility retirement for a pre-CHK21 node surviving a live
            # source reload or test scaffold.
            node.releaseResources()


class BackgroundRenderItem(QQuickItem):
    """Full-scene background with retained steady content and custom transitions."""

    proofProgressChanged = Signal()

    def __init__(
        self,
        parent: QQuickItem | None = None,
        *,
        telemetry: RenderNodeTelemetry | None = None,
        screen_index: int = -1,
    ) -> None:
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self._proof_state = SlideProofState()
        # The colour-band Slide proof is a diagnostic scaffold only. Production
        # must not render it merely because a real image has not arrived yet.
        self._proof_enabled = False
        self._presentation_image: PresentationImage | None = None
        self._transition_run: TransitionRun | None = None
        self._telemetry = telemetry or RenderNodeTelemetry(
            gui_thread_id=threading.get_ident()
        )
        self._screen_index = int(screen_index)
        # Explicit --frame-trace only. Ordinary runtime retains no trace sink and
        # executes no per-frame trace calls. Capture the admitted sink once at
        # item construction rather than resolving global state from render().
        self._frame_trace = current_frame_trace()
        self._retirement = _RenderNodeRetirement(self._telemetry)
        self._bound_window = None
        self.windowChanged.connect(self._bind_window_invalidation)
        self._bind_window_invalidation(self.window())

    def getProofProgress(self) -> float:
        return float(self._proof_state.progress)

    def setProofProgress(self, value: float) -> None:
        state = SlideProofState(progress=value).normalized()
        proof_was_enabled = self._proof_enabled
        self._proof_enabled = True
        if state == self._proof_state:
            if not proof_was_enabled:
                # An explicit call opts the harness into proof rendering even
                # when it requests the default progress value.
                self.update()
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

    @staticmethod
    def _retire_replaced_node(node: QSGNode | None) -> None:
        """Release owned resources before Qt deletes a replaced subtree."""

        if isinstance(node, RetainedBackgroundSceneNode):
            node.release_resources()
        elif isinstance(node, BackgroundRenderNode):
            node.releaseResources()

    def _custom_rendering_required(self) -> bool:
        return bool(
            self._transition_run is not None
            or self._proof_enabled
            or self._telemetry.capture_pixels_enabled
        )

    def updatePaintNode(
        self,
        old_node: QSGNode | None,
        _update_data: QQuickItem.UpdatePaintNodeData,
    ) -> QSGNode | None:
        # Phase-A colour bands were useful as a deterministic migration proof,
        # but allowing the no-image production state to instantiate that node
        # leaked the proof palette onto real displays during startup/recreation.
        # Keep the scaffold available only when a harness explicitly calls
        # setProofProgress(). A real image/transition always remains renderable.
        if (
            self._presentation_image is None
            and self._transition_run is None
            and not self._proof_enabled
        ):
            self._retire_replaced_node(old_node)
            self._retirement.set_node(None)
            return None

        window = self.window()
        custom_required = self._custom_rendering_required()
        if window is None and self._presentation_image is not None and not custom_required:
            raise RuntimeError("retained Quick background image has no window")

        if isinstance(old_node, RetainedBackgroundSceneNode):
            node = old_node
        else:
            self._retire_replaced_node(old_node)
            node = RetainedBackgroundSceneNode(
                window=window,
                telemetry=self._telemetry,
                screen_index=self._screen_index,
                frame_trace=self._frame_trace,
            )

        node.synchronize(
            logical_size=(float(self.width()), float(self.height())),
            device_pixel_ratio=(
                float(window.effectiveDevicePixelRatio()) if window is not None else 1.0
            ),
            state=self._proof_state,
            presentation_image=self._presentation_image,
            transition_run=self._transition_run,
            custom_required=custom_required,
        )
        self._retirement.set_node(node)
        return node
