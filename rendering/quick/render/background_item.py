"""Quick item that synchronizes retained background and transition presentation."""

from __future__ import annotations

import threading
import time
import weakref

from PySide6.QtCore import Property, QObject, QRunnable, Signal, Qt
from PySide6.QtGui import QOpenGLContext
from PySide6.QtQuick import QQuickItem, QQuickWindow, QSGNode

from ..image_state import PresentationImage
from ..transitions.state import TransitionRun
from .background_image_node import RetainedBackgroundSceneNode
from .background_node import BackgroundRenderNode, SlideProofState
from .telemetry import RenderNodeTelemetry
from core.logging.logger import get_logger
from core.performance.frame_trace import FrameTraceEvent, current_frame_trace
from rendering.transition_registry import background_family_available_on_backend

logger = get_logger(__name__)


def _native_background_wanted() -> bool:
    """Whether the process's backend draws the background natively (N5.7a: Vulkan). Read once per item; a process whose
    backend owner never ran (a test, a tool) reads OpenGL."""
    from .native_background import native_background_wanted

    try:
        return native_background_wanted()
    except Exception:
        return False


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


class _FrameEdgeReceiver(QObject):
    """GUI-thread receiver of one queued window signal (a plain method: no @Slot with a result, the QML slot crash)."""

    def __init__(self, fire) -> None:
        super().__init__()
        self._fire = fire

    def fired(self) -> None:
        self._fire()


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
        # D10 point 2: the background family's renderers are Python OpenGL; on
        # a backend without them (the Vulkan rehearsal) no background node is
        # ever created. Read once: the process's backend never changes.
        self._renderers_on_backend = background_family_available_on_backend()
        # N5.7a (D7 point 1, D10 point 3): on the native background's backend (the Vulkan rehearsal) the photo is drawn
        # by the native core's background layer, a composite item in this one, made at the first image. This item keeps
        # owning the image, its identity rule and the timing of every change; on OpenGL nothing native is made.
        self._native_layer = None
        self._native_layer_wanted = (not self._renderers_on_backend) and _native_background_wanted()
        # N5.2h point 5: the degraded display, once the layer cannot be made (no native core on either API).
        self._degraded = False
        self._warm_up_cancel: threading.Event | None = None
        # The hitch rows (22 Nov): a GUI-thread warm-up unit (the renderer module's import with its shader text build,
        # then the native layer's own) waits for the next frame the window renders anyway (afterRendering, queued),
        # then runs alone: (transition id, weak reporter, ticket) while one is armed.
        self._gui_warm_pending: tuple[str, weakref.ref, int] | None = None
        self._gui_warm_window = None
        self._gui_warm_receiver = None
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
        self._present_native(image)

    @property
    def native_layer(self):
        """The native background layer (N5.7a) on its backend, once made; None elsewhere."""
        return self._native_layer

    def _present_native(self, image: PresentationImage | None) -> None:
        """The native background layer takes the item's image at the same edge the Python presenter does (N5.7a)."""
        if not self._native_layer_wanted:
            return
        if self._native_layer is None:
            if image is None:
                return
            from .native_background import attach_native_background

            try:
                self._native_layer = attach_native_background(self)
            except Exception:
                # N5.2h point 5: no layer, so the degraded display (Qt's own image node, hard cuts); the process's
                # reason is logged once by the backend owner, a layer that failed with a core loaded here.
                self._native_layer_wanted = False
                self._degraded = True
                self.update()
                from rendering.quick.bootstrap import native_core

                if native_core() is not None:
                    logger.error("[BACKGROUND][NATIVE] The native background layer could not be made", exc_info=True)
                return
            if self._native_layer is None:
                self._native_layer_wanted = False
                self._degraded = True
                self.update()
                return
            self.widthChanged.connect(self._native_geometry_changed)
            self.heightChanged.connect(self._native_geometry_changed)
            self._native_layer.on_failure(self._native_layer_failed)
        elif self._degraded and image is not None and self._native_layer.drawing:
            # The layer draws again and has been opaque over the degraded photo since: the degraded node goes under it
            # with nothing visible changing (a new photo is drawn by the layer).
            self._degraded = False
        self._native_layer.present(image)

    def _native_layer_failed(self) -> None:
        """N5.2h (lead decision): a layer that fails after it was made (the core's verdict, or a step that raised) fades
        out over the degraded display, shown under it from this edge on, so the display fades to the photo and never
        stays faded out. The layer logs the failure once; it fades back in over the photo if it draws again."""
        if not self._degraded:
            self._degraded = True
            self.update()

    def _native_geometry_changed(self) -> None:
        if self._native_layer is not None:
            self._native_layer.geometry_changed()

    def close_native_layer(self) -> None:
        """The native background layer goes with the display generation, before its scene root (idempotent)."""
        layer, self._native_layer = self._native_layer, None
        self._native_layer_wanted = False
        if layer is not None:
            layer.close()

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
        if self._native_layer is not None:
            self._native_layer.transition(run)   # N5.2a: the core draws the run on the native background's backend

    def schedule_warm_step(self, transition_id: str, parameters, reporter, ticket: int) -> bool:
        """GUI thread: one warm-up unit, with no rendering request: the renderer module's import and the native
        layer's units on the GUI thread at the next frame rendered anyway, else one GL step with NoStage.

        Only the shared idle-preparation owner may call this. A hidden or
        retiring window must fail closed instead of creating a repaint loop.
        """
        window = self.window()
        if window is None or not window.isExposed() or self._transition_run is not None:
            return False
        if self._gui_warm_unit(str(transition_id)) is not None:
            # One GUI-thread unit first (the module's import before any GL step resolves the renderer on the render
            # thread), at the next frame rendered anyway: no frame is asked for.
            self._cancel_warm_up()
            self._arm_gui_warm(window, str(transition_id), reporter, int(ticket))
            return True
        if not self._renderers_on_backend:
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

    def _gui_warm_unit(self, transition_id: str):
        """The next GUI-thread warm-up unit for ``transition_id`` (None: none left): the renderer module's (its
        shared modules, its import, its shader text pieces: ``next_quick_transition_warm_unit``), then, on the native
        background, the layer's own units."""
        from rendering.quick.transitions import implementation_registry

        unit = implementation_registry.next_quick_transition_warm_unit(transition_id)
        if unit is not None:
            return unit
        layer = self._native_layer
        return layer.next_warm_unit(transition_id) if layer is not None else None

    def _arm_gui_warm(self, window, transition_id: str, reporter, ticket: int) -> None:
        if self._gui_warm_receiver is None:
            self._gui_warm_receiver = _FrameEdgeReceiver(self._run_gui_warm)
        self._gui_warm_pending = (transition_id, weakref.ref(reporter), ticket)
        window.afterRendering.connect(self._gui_warm_receiver.fired, Qt.ConnectionType.QueuedConnection)
        self._gui_warm_window = window

    def _disarm_gui_warm(self) -> None:
        self._gui_warm_pending = None
        window, self._gui_warm_window = self._gui_warm_window, None
        if window is not None:
            try:
                window.afterRendering.disconnect(self._gui_warm_receiver.fired)
            except (RuntimeError, TypeError):
                pass                              # the window went first

    def _run_gui_warm(self) -> None:
        """GUI thread, a frame just rendered: one unit, then the owner is told whether this display has more."""
        pending = self._gui_warm_pending
        self._disarm_gui_warm()
        if pending is None or self._transition_run is not None:
            return                                # cancelled, or a run prepares whatever is left itself
        transition_id, reporter_ref, ticket = pending
        unit = self._gui_warm_unit(transition_id)
        if unit is not None:
            try:
                unit()
            except Exception:
                logger.debug("[TRANSITION] A warm-up unit failed for %s", transition_id, exc_info=True)
        done = self._gui_warm_unit(transition_id) is None and not self._renderers_on_backend
        reporter = reporter_ref()
        if reporter is not None:
            try:
                reporter.finished.emit(ticket, done)
            except RuntimeError:
                pass                              # the owner retired meanwhile

    def _cancel_warm_up(self) -> None:
        self._disarm_gui_warm()
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

    @property
    def degraded(self) -> bool:
        """Whether this item shows the degraded display (N5.2h point 5)."""
        return self._degraded

    def _degraded_node(self, old_node: QSGNode | None) -> QSGNode | None:
        """The degraded display's node: the current photo through Qt's own image node (a run draws nothing; the run's
        destination arrives as the next image, a hard cut)."""
        from .degraded_background import DegradedBackgroundNode

        window = self.window()
        if self._presentation_image is None or window is None:
            return None
        node = old_node if isinstance(old_node, DegradedBackgroundNode) else DegradedBackgroundNode(window)
        node.synchronize(self._presentation_image, (float(self.width()), float(self.height())))
        return node

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
        if self._degraded and not self._renderers_on_backend:
            return self._degraded_node(old_node)
        if (
            self._presentation_image is None
            and self._transition_run is None
            and not self._proof_enabled
        ) or not self._renderers_on_backend:
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
