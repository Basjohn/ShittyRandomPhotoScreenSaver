"""Quick item that owns the background's image and transition timing; the native core's background layer draws them
(N5.2h: one route per API), or the degraded display where no layer can be made."""

from __future__ import annotations

import weakref

from PySide6.QtQuick import QQuickItem, QSGNode

from ..image_state import PresentationImage
from ..transitions.state import TransitionRun
from core.logging.logger import get_logger

logger = get_logger(__name__)


def _native_background_wanted() -> bool:
    """Whether the process's backend draws the background natively (N5.2h: OpenGL and Vulkan). Read once per item."""
    from .native_background import native_background_wanted

    try:
        return native_background_wanted()
    except Exception:
        return False


class BackgroundRenderItem(QQuickItem):
    """Full-scene background: the image and run owner over the native background layer."""

    def __init__(
        self,
        parent: QQuickItem | None = None,
        *,
        screen_index: int = -1,
    ) -> None:
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self._presentation_image: PresentationImage | None = None
        self._transition_run: TransitionRun | None = None
        self._screen_index = int(screen_index)
        # N5.7a (D7 point 1, D10 point 3), N5.2h: the photo and every run are drawn by the native core's background
        # layer, a composite item in this one, made at the first image. This item keeps owning the image, its identity
        # rule and the timing of every change.
        self._native_layer = None
        self._native_layer_wanted = _native_background_wanted()
        # N5.2h point 5: the degraded display, once the layer cannot be made (no native core on either API).
        self._degraded = False
        # The hitch rows (22 Nov): a GUI-thread warm-up unit (the renderer module's import with its shader text build,
        # then the native layer's own) waits for the next frame the window renders anyway (afterRendering, queued),
        # then runs alone: (transition id, weak reporter, ticket) while one is armed.
        self._gui_warm_pending: tuple[str, weakref.ref, int] | None = None
        self._gui_warm_edge = None
        self.windowChanged.connect(self._cancel_warm_up)

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
        """The native background layer takes the item's image at the edge it is published (N5.7a)."""
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
        if self._native_layer is not None:
            self._native_layer.transition(run)   # N5.2a: the core draws the run on the native background's backend

    def schedule_warm_step(self, transition_id: str, parameters, reporter, ticket: int) -> bool:
        """GUI thread: one warm-up unit, with no rendering request: the renderer module's import and the native
        layer's units on the GUI thread at the next frame rendered anyway. False when nothing is left.

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
        return False

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
        if self._gui_warm_edge is None:
            from rendering.quick.visualizer.native_route import _WindowEdge

            # The one window-edge owner (``_WindowEdge``: a queued, one-shot GUI-thread edge, never a timer).
            self._gui_warm_edge = _WindowEdge("afterRendering", self._run_gui_warm)
        self._gui_warm_pending = (transition_id, weakref.ref(reporter), ticket)
        self._gui_warm_edge.arm(window)

    def _disarm_gui_warm(self) -> None:
        self._gui_warm_pending = None
        if self._gui_warm_edge is not None:
            self._gui_warm_edge.disarm()

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
        done = self._gui_warm_unit(transition_id) is None
        reporter = reporter_ref()
        if reporter is not None:
            try:
                reporter.finished.emit(ticket, done)
            except RuntimeError:
                pass                              # the owner retired meanwhile

    def _cancel_warm_up(self) -> None:
        self._disarm_gui_warm()

    def cancel_warm_up(self) -> None:
        """GUI owner: invalidate any queued idle render job."""
        self._cancel_warm_up()

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
        # The native layer is a child item that draws itself; this item's own node is only the degraded display's.
        if self._degraded:
            return self._degraded_node(old_node)
        return None
