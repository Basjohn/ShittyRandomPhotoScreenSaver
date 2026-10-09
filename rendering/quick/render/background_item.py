"""Quick item that synchronizes retained background and transition presentation."""

from __future__ import annotations

import threading
import time
import weakref

from PySide6.QtCore import Property, QRunnable, Signal, Qt
from PySide6.QtGui import QOpenGLContext
from PySide6.QtQuick import QQuickItem, QQuickWindow, QSGNode

from ..image_state import PresentationImage
from ..transitions.state import TransitionRun
from .background_image_node import RetainedBackgroundSceneNode
from .background_node import BackgroundRenderNode, SlideProofState
from .telemetry import RenderNodeTelemetry
from core.performance.frame_trace import FrameTraceEvent, current_frame_trace


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

    def warm_step(self, transition_id: str, parameters) -> bool:
        """Render thread: one warm-up step on the current node; True when there is none."""
        with self._lock:
            node = self._node
        if node is None:
            return True
        return node.warm_step(transition_id, parameters)

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


class _TransitionWarmStepJob:
    """Plain-Python payload for one context-current *idle render job*.

    NoStage executes on the window's render owner without requesting a frame.
    Qt deletes its QRunnable on the render thread. A Python *subclass* of
    QRunnable crosses the Shiboken virtual-override/destruction boundary on
    that thread; the R137-R139 jobs coincided with native aborts and wrong-
    thread QBasicTimer destruction during startup. Instead, Qt owns the
    callable-based runnable created by QRunnable.create(self.run), while this
    payload stays an ordinary Python object containing NO QObject owners.

    In particular, never close over a strong QQuickWindow or GUI reporter. A
    pending runnable can be discarded without run() during scene-graph teardown.
    The display manager serializes displays and owns delayed admissions.
    """

    def __init__(self, window, retirement, request, cancelled, reporter, ticket: int) -> None:
        # The callable-owned payload is intentionally not a QRunnable/QObject.
        # Qt destroys the native runnable on the render thread.
        self._window_ref = weakref.ref(window)
        self._reporter_ref = weakref.ref(reporter)
        self._retirement = retirement  # plain Python render-thread owner
        self._request = request        # detached scalar/dict state
        self._cancelled = cancelled    # threading.Event; no Qt affinity
        self._ticket = ticket

    def run(self) -> None:
        if self._cancelled.is_set():
            return
        window = self._window_ref()
        if window is None:
            return  # the GUI scene has already retired
        done = True  # failed optional preparation must not strand the owner
        try:
            if QOpenGLContext.currentContext() is None:
                raise RuntimeError("idle warm-up job has no Qt-owned OpenGL context")
            window.beginExternalCommands()
            try:
                if not self._cancelled.is_set():
                    done = bool(self._retirement.warm_step(*self._request))
            finally:
                window.endExternalCommands()
        except Exception:
            # Optional preparation may fail closed; the authoritative transition
            # retains its normal render-thread first-use path.
            done = True
        finally:
            # Do not retain the temporary strong GUI wrapper reference while
            # Qt destroys this job on the render thread.
            window = None
        if self._cancelled.is_set():
            return
        reporter = self._reporter_ref()
        if reporter is not None:
            try:
                reporter.finished.emit(self._ticket, done)
            except RuntimeError:
                # The GUI receiver has been destroyed during runtime retirement.
                pass


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
        self._warm_up_cancel: threading.Event | None = None
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
        if run is not None:
            self._cancel_warm_up()   # the run prepares whatever is left itself
        self._transition_run = run
        self.update()

    def schedule_warm_step(self, transition_id: str, parameters, reporter, ticket: int) -> bool:
        """GUI thread: one GL step with NoStage, with no rendering request.

        Only the shared idle-preparation owner may call this. A hidden or
        retiring window must fail closed instead of creating a repaint loop.
        """
        window = self.window()
        if window is None or not window.isExposed() or self._transition_run is not None:
            return False
        self._cancel_warm_up()
        cancelled = threading.Event()
        self._warm_up_cancel = cancelled
        payload = _TransitionWarmStepJob(
            window, self._retirement, (str(transition_id), dict(parameters)),
            cancelled, reporter, int(ticket),
        )
        try:
            # Qt owns and deletes the built-in callable runnable, never a
            # Python subclass with a virtual run() override. The callback's
            # only QObject references are weak; there is no render-thread
            # owner-finalization or QObject timer release path in its payload.
            job = QRunnable.create(payload.run)
            window.scheduleRenderJob(job, QQuickWindow.RenderStage.NoStage)
        except Exception:
            cancelled.set()
            self._warm_up_cancel = None
            return False
        return True

    def _cancel_warm_up(self) -> None:
        token, self._warm_up_cancel = self._warm_up_cancel, None
        if token is not None:
            token.set()

    def cancel_warm_up(self) -> None:
        """GUI owner: invalidate any queued idle render job."""
        self._cancel_warm_up()

    def _bind_window_invalidation(self, window) -> None:
        if window is self._bound_window:
            return
        self._cancel_warm_up()
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
            # One-time node construction may perform context validation before
            # native image admission. Attribute it separately from GL upload.
            trace = self._frame_trace
            if trace is not None:
                trace.record(
                    FrameTraceEvent.RETAINED_NODE_CREATE_BEGIN,
                    screen_index=self._screen_index,
                )
            node = RetainedBackgroundSceneNode(
                window=window,
                telemetry=self._telemetry,
                screen_index=self._screen_index,
                frame_trace=self._frame_trace,
            )
            if trace is not None:
                trace.record(
                    FrameTraceEvent.RETAINED_NODE_CREATE_READY,
                    screen_index=self._screen_index,
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
