"""Compositor-owned visualizer render layer.

P2-RHI proved that a second independently dirtied texture-backed presentation
surface is materially harmful even when it shares the top-level QRhi. This layer
is the correction: the visualizer stops being a presented surface and becomes a
layer drawn inside the display compositor's existing external GL render pass.

Ownership split
---------------

* the visualizer object remains the **logical** authority. It integrates
  Bubble/Spectrum/waveform/ghost/peak state on its own tick exactly as before,
  and none of that evolution happens here.
* this layer owns **presentation** of that state: it draws the already
  integrated render state into the compositor framebuffer when the compositor
  paints.

Coordinates
-----------

The mode shaders draw a fullscreen quad over the current viewport, so drawing
the visualizer into a sub-rect of the whole-display framebuffer is a viewport
and scissor set to the card rect. The rounded-card stencil mask shader instead
reads ``gl_FragCoord.xy``, which is **window** space rather than viewport space,
so its rect uniform must carry the card's display-space origin explicitly. The
old overlay got that for free because its framebuffer *was* the card; nothing
here may rely on that former accident.
"""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QRect

from core.logging.logger import get_logger

try:  # pragma: no cover - PyOpenGL is required for accelerated presentation
    from OpenGL import GL as gl  # type: ignore[import]
except ImportError:  # pragma: no cover
    gl = None

logger = get_logger(__name__)


class VisualizerRenderState:
    """Latest published visualizer render state for one display.

    This is a *latest-wins handle*, not a queue and not a deep copy. The heavy
    per-mode arrays stay owned by the logical visualizer, and this layer reads
    them at paint time. That is safe because publication and paint both run on
    the GUI thread, so a paint can only ever observe a completed publication,
    never a half-applied one; deep-copying ~100 Hz of mode payload would add
    real cost and a second source of truth for no correctness gain.

    Generation and activation identity travel with the handle so a stale
    engine/display generation can be rejected instead of drawn.
    """

    __slots__ = ("owner", "card_rect", "runtime_generation", "activation_id")

    def __init__(
        self,
        owner: Any,
        card_rect: QRect,
        *,
        runtime_generation: object = None,
        activation_id: object = None,
    ) -> None:
        self.owner = owner
        self.card_rect = QRect(card_rect)
        self.runtime_generation = runtime_generation
        self.activation_id = activation_id


class CompositorVisualizerLayer:
    """Draws the visualizer inside the display compositor's render pass.

    The layer does not own the visualizer's GL handles: those stay with the
    logical visualizer object, which already has one deletion owner per numeric
    handle and strict fail-closed teardown. What changes is *which context* they
    live on - the compositor's borrowed QRhi OpenGL context - and *who drives*
    creation and deletion, which is now the compositor lifecycle.
    """

    # Bounded loud reporting: a failing visualizer must be visible in logs
    # without becoming a per-frame log.
    _FAILURE_LOG_INTERVAL = 300

    def __init__(self, compositor: Any) -> None:
        self._compositor = compositor
        self._state: Optional[VisualizerRenderState] = None
        self._failures = 0
        self._last_failure_signature: Optional[str] = None

    # -- publication ------------------------------------------------------

    def publish(self, state: Optional[VisualizerRenderState]) -> None:
        """Accept the latest render state, replacing any previous one."""
        self._state = state

    def clear(self) -> None:
        """Drop the published state; the layer draws nothing until republished.

        Card visual ownership is handed back, otherwise the card would stop
        painting itself while nothing else painted it either.
        """
        self._release_card_visual()
        self._state = None

    def _release_card_visual(self) -> None:
        card = self._card_widget()
        if card is None:
            return
        release = getattr(card, "set_compositor_owns_card_visual", None)
        if callable(release):
            try:
                release(False)
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS][LAYER] Failed to release card visual", exc_info=True
                )

    @property
    def state(self) -> Optional[VisualizerRenderState]:
        return self._state

    def has_visible_state(self) -> bool:
        """Whether a published state currently wants to be drawn."""
        state = self._state
        if state is None or state.owner is None:
            return False
        try:
            if not bool(getattr(state.owner, "_enabled", False)):
                return False
            if float(getattr(state.owner, "_fade", 0.0)) <= 0.0:
                return False
        except Exception:
            return False
        rect = state.card_rect
        return rect.width() > 0 and rect.height() > 0

    # -- rendering --------------------------------------------------------

    def render(self, surface_height_px: int, dpr: float) -> bool:
        """Draw the visualizer layer into the currently bound framebuffer.

        Must be called inside the compositor's external GL section, after the
        base/transition layers. Returns True when the layer actually drew.
        """
        if gl is None:
            return False
        state = self._state
        if not self.has_visible_state():
            return False
        owner = state.owner

        borrowed = getattr(self._compositor, "_rhi_gl", None)
        if not self.ensure_initialized(borrowed.context if borrowed else None):
            return False

        rect = state.card_rect
        # Card rect in framebuffer pixels. Qt widget coordinates are top-left
        # origin; OpenGL viewport/scissor are bottom-left origin.
        x_px = int(round(rect.x() * dpr))
        w_px = max(1, int(round(rect.width() * dpr)))
        h_px = max(1, int(round(rect.height() * dpr)))
        top_px = int(round(rect.y() * dpr))
        y_px = max(0, int(surface_height_px) - top_px - h_px)

        # The mask shader reads gl_FragCoord (window space), so it needs the
        # card origin in framebuffer pixels rather than a viewport-local rect.
        owner._compositor_mask_origin_px = (float(x_px), float(y_px))

        try:
            from widgets.spotify_visualizer.overlay_frame_shell import (
                resolve_frame_fade,
            )

            fade = resolve_frame_fade(owner, logger)
            if fade is None:
                return False

            # The card visual must be drawn by the compositor, beneath the bars.
            # The card QWidget is a sibling ABOVE this surface, so if it kept
            # painting its own background it would simply cover the bars now
            # that they are drawn here.
            self._render_card_visual(rect)

            gl.glViewport(x_px, y_px, w_px, h_px)
            # Scissor bounds every write this layer makes - including the
            # stencil clear inside the mask path - to the card rect, so the
            # base image and transition already in the framebuffer are safe.
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(x_px, y_px, w_px, h_px)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            try:
                # Card-local rect: the shaders size themselves from this, and it
                # must stay card-sized so authored geometry is unchanged.
                local_rect = QRect(0, 0, rect.width(), rect.height())
                owner.paint_layer(local_rect, fade)
            finally:
                gl.glDisable(gl.GL_SCISSOR_TEST)
                gl.glUseProgram(0)
                gl.glBindVertexArray(0)
            self._last_failure_signature = None
            return True
        except Exception:
            self._record_failure("render_exception")
            return False
        finally:
            owner._compositor_mask_origin_px = None

    # -- lifecycle --------------------------------------------------------

    def ensure_initialized(self, borrowed_context) -> bool:
        """Create visualizer GL resources on the compositor's borrowed context.

        Called from the compositor render path, where the QRhi OpenGL context
        is current. Idempotent, so a render-target resize does not rebuild
        immutable programs/VAO/VBO.
        """
        state = self._state
        if state is None or state.owner is None:
            return False
        initialize = getattr(state.owner, "initialize_layer_gl", None)
        if not callable(initialize):
            return False
        try:
            return bool(initialize(borrowed_context))
        except Exception:
            self._record_failure("initialize_exception")
            return False

    def cleanup(self) -> None:
        """Delete visualizer GL resources through their existing strict owner.

        The visualizer object keeps one deletion owner per numeric handle and
        stays fail-closed; this only drives it from compositor teardown, while
        the borrowed context is still current.
        """
        state = self._state
        owner = state.owner if state is not None else None
        self._release_card_visual()
        self._state = None
        if owner is None:
            return
        cleanup_gl = getattr(owner, "cleanup_gl", None)
        if callable(cleanup_gl):
            cleanup_gl()


    def _card_widget(self):
        """The visualizer card whose visual this layer now owns."""
        state = self._state
        if state is None or state.owner is None:
            return None
        try:
            parent = state.owner.parentWidget()
        except Exception:
            return None
        return getattr(parent, "spotify_visualizer_widget", None) if parent else None

    def _render_card_visual(self, rect: QRect) -> None:
        """Draw the card background/border/shadow beneath the shader layer.

        Reuses the card's own cached pixmap rather than reimplementing the
        authored appearance in GL, so border width, radius, shadow and fade stay
        exactly what the card already produced.
        """
        card = self._card_widget()
        if card is None:
            return
        try:
            # Claim the visual exactly once; the card keeps everything else.
            claim = getattr(card, "set_compositor_owns_card_visual", None)
            if callable(claim):
                claim(True)
            if not bool(getattr(card, "_show_background", False)):
                return  # No background: nothing to occlude, nothing to draw.
            from widgets.spotify_visualizer.card_paint import (
                ensure_painted_frame_shadow_pixmap,
            )

            pixmap = (
                ensure_painted_frame_shadow_pixmap(card)
                if card.uses_painted_frame_shadow()
                else None
            )
            if pixmap is None or pixmap.isNull():
                return
            painter_ctx = getattr(self._compositor, "gl_target_painter", None)
            if not callable(painter_ctx):
                return
            with painter_ctx() as painter:
                if painter is None:
                    return
                painter.drawPixmap(rect.x(), rect.y(), pixmap)
        except Exception:
            self._record_failure("card_visual_exception")

    def _record_failure(self, signature: str) -> None:
        """Report visualizer layer failure loudly but boundedly.

        Deliberately no CPU/QPainter substitute: the authored output is the
        shader renderer, so a failure clears the layer rather than inventing
        cheap bars. Resource ownership is retained for cleanup/recovery.
        """
        self._failures += 1
        if signature != self._last_failure_signature or (
            self._failures % self._FAILURE_LOG_INTERVAL == 0
        ):
            self._last_failure_signature = signature
            logger.error(
                "[SPOTIFY_VIS][LAYER] Visualizer layer render failed "
                "signature=%s failures=%d; layer omitted this frame",
                signature,
                self._failures,
                exc_info=True,
            )
