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


class PresentationGeometry:
    """The single authoritative presentation geometry for one visualizer frame.

    Every consumer - card visual, viewport, scissor, shader resolution, shader
    fragment origin, stencil mask and border geometry - derives from this one
    value. The initial single-surface landing had two size authorities (the
    published card rect for the bars, the live QWidget size for the card
    pixmap) and two DPR authorities (the compositor for the viewport, the
    hidden visualizer widget for ``u_dpr``); that produced a shader confined to
    a narrow hard-edged region inside a much larger painted card.

    The live card QWidget stays layout/edit authority, but its momentarily
    stale physical geometry must never redefine presentation geometry behind
    the published state.
    """

    __slots__ = (
        "logical_rect",
        "dpr",
        "framebuffer_origin_px",
        "framebuffer_size_px",
    )

    def __init__(self, logical_rect: QRect, dpr: float, surface_height_px: int) -> None:
        self.logical_rect = QRect(logical_rect)
        self.dpr = max(1e-6, float(dpr))

        x_px = int(round(logical_rect.x() * self.dpr))
        w_px = max(1, int(round(logical_rect.width() * self.dpr)))
        h_px = max(1, int(round(logical_rect.height() * self.dpr)))
        top_px = int(round(logical_rect.y() * self.dpr))
        # Qt widget coordinates are top-left origin; GL viewport/scissor and
        # gl_FragCoord are bottom-left origin.
        y_px = max(0, int(surface_height_px) - top_px - h_px)

        self.framebuffer_origin_px = (x_px, y_px)
        self.framebuffer_size_px = (w_px, h_px)

    @property
    def viewport(self) -> tuple[int, int, int, int]:
        return (*self.framebuffer_origin_px, *self.framebuffer_size_px)

    def local_rect(self) -> QRect:
        """Card-local rect: shaders stay card-sized so authored geometry holds."""
        return QRect(0, 0, self.logical_rect.width(), self.logical_rect.height())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PresentationGeometry):
            return NotImplemented
        return (
            self.logical_rect == other.logical_rect
            and abs(self.dpr - other.dpr) < 1e-9
            and self.framebuffer_origin_px == other.framebuffer_origin_px
            and self.framebuffer_size_px == other.framebuffer_size_px
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"PresentationGeometry(logical={self.logical_rect}, dpr={self.dpr}, "
            f"origin_px={self.framebuffer_origin_px}, size_px={self.framebuffer_size_px})"
        )


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


class VisualizerPresentationReadiness:
    """Whether this compositor generation can actually draw the visualizer.

    Startup used to begin the visible fade before the single-surface renderer
    that owns the visualizer's pixels existed: the staged reveal completed, the
    fade animation started, and only about a second later did the visualizer GL
    programs register and the compositor begin presenting. The first drawn frame
    therefore sampled an animation that was already part-way through, which is
    the flash/slam the operator saw.

    This is runtime lifecycle state for one compositor QRhi generation - not a
    timer, not a probe and not a fixed sleep. Every field is a fact the layer
    already knows at the moment it is asked.
    """

    __slots__ = (
        "gl_generation",
        "gl_resources_ready",
        "gl_failed",
        "geometry_committed",
        "card_visual_owned",
        "card_texture_ready",
    )

    def __init__(
        self,
        *,
        gl_generation: int = -1,
        gl_resources_ready: bool = False,
        gl_failed: bool = False,
        geometry_committed: bool = False,
        card_visual_owned: bool = False,
        card_texture_ready: bool = False,
    ) -> None:
        self.gl_generation = int(gl_generation)
        self.gl_resources_ready = bool(gl_resources_ready)
        self.gl_failed = bool(gl_failed)
        self.geometry_committed = bool(geometry_committed)
        self.card_visual_owned = bool(card_visual_owned)
        self.card_texture_ready = bool(card_texture_ready)

    @property
    def is_ready(self) -> bool:
        """True only when every pixel owner needed for fade 0 -> 1 exists."""
        return (
            self.gl_generation > 0
            and self.gl_resources_ready
            and not self.gl_failed
            and self.geometry_committed
            and self.card_visual_owned
            and self.card_texture_ready
        )

    def missing(self) -> tuple[str, ...]:
        """The unmet requirements, for one bounded readiness log."""
        gaps: list[str] = []
        if self.gl_generation <= 0:
            gaps.append("gl_generation")
        if not self.gl_resources_ready:
            gaps.append("gl_resources")
        if self.gl_failed:
            gaps.append("gl_failed")
        if not self.geometry_committed:
            gaps.append("geometry")
        if not self.card_visual_owned:
            gaps.append("card_visual")
        if not self.card_texture_ready:
            gaps.append("card_texture")
        return tuple(gaps)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            "VisualizerPresentationReadiness(ready=%s generation=%d missing=%s)"
            % (self.is_ready, self.gl_generation, ",".join(self.missing()) or "none")
        )


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
        from rendering.gl_compositor_pkg.card_texture import CompositorCardTexture

        self._compositor = compositor
        self._card_texture = CompositorCardTexture()
        # Latest visible presentation state; may be None while hidden.
        self._state: Optional[VisualizerRenderState] = None
        # Persistent GL resource owner for this compositor generation. Retained
        # until a successful compositor-generation cleanup, INDEPENDENTLY of
        # visibility: using the transient presentation state as the destruction
        # owner meant a hidden/cleared visualizer at teardown leaked its GL
        # resources - exactly the card texture that survived to application exit
        # in the installed accounting.
        self._resource_owner: Any = None
        self._failures = 0
        self._last_failure_signature: Optional[str] = None
        # Authoritative presentation geometry committed by the last prepare or
        # render pass, with the compositor GL generation it was committed under.
        # Readiness is per generation, so a QRhi generation replacement cannot
        # leave a stale "ready" answer behind.
        self._committed_geometry: Optional[PresentationGeometry] = None
        self._committed_generation: int = -1
        # One readiness notification per preparation, so the reveal gate is
        # event-driven instead of polled.
        self._prepared_notified = False

    # -- publication ------------------------------------------------------

    def publish(self, state: Optional[VisualizerRenderState]) -> None:
        """Accept the latest render state, replacing any previous one."""
        self._state = state
        if state is not None and state.owner is not None:
            # Establish destruction authority deliberately; it outlives
            # visibility and is released only by a successful cleanup.
            self._resource_owner = state.owner

    def clear(self) -> None:
        """Drop the published state; the layer draws nothing until republished.

        Card visual ownership is handed back, otherwise the card would stop
        painting itself while nothing else painted it either.

        Destruction authority is deliberately NOT dropped here: hiding the
        visualizer must not lose the reference needed to free its GL resources
        at compositor teardown.
        """
        self._release_card_visual()
        self._state = None
        # Readiness must not survive the state it described.
        self._committed_geometry = None
        self._committed_generation = -1
        self._prepared_notified = False

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

        ``dpr`` is the compositor's device pixel ratio and is the ONLY DPR this
        path consumes; the hidden logical visualizer is not consulted.
        """
        if gl is None:
            return False
        state = self._state
        if not self.has_visible_state():
            # Not visible yet: this is the readiness/prewarm pass. It runs on
            # the same compositor render strategy inside the same external GL
            # section - no second timer, no second surface - and draws nothing.
            self.prepare(surface_height_px, dpr)
            return False
        owner = state.owner

        borrowed = getattr(self._compositor, "_rhi_gl", None)
        if not self.ensure_initialized(borrowed.context if borrowed else None):
            return False

        # ONE authoritative geometry for card visual, viewport, scissor, shader
        # resolution, fragment origin, stencil mask and border.
        geometry = PresentationGeometry(state.card_rect, dpr, surface_height_px)
        self._commit_geometry(geometry, borrowed)
        x_px, y_px = geometry.framebuffer_origin_px
        w_px, h_px = geometry.framebuffer_size_px

        # The mask shader reads gl_FragCoord (window space), so it needs the
        # card origin in framebuffer pixels rather than a viewport-local rect.
        owner._compositor_mask_origin_px = (float(x_px), float(y_px))
        owner._presentation_geometry = geometry

        try:
            from widgets.spotify_visualizer.overlay_frame_shell import (
                resolve_bars_fade,
                resolve_frame_fade,
            )

            # ONE fade authority. ``fade`` is the authoritative scene fade
            # progress and owns the authored card pixels; ``bars_fade`` is the
            # authored shader stagger of that same progress, published with it.
            fade = resolve_frame_fade(owner, logger)
            if fade is None:
                return False
            bars_fade = resolve_bars_fade(owner, fade)

            # ONE card-region GL state boundary, established BEFORE both the
            # card texture and the visualizer shader.
            #
            # The card texture is a full-NDC quad, so it covers whatever
            # viewport is active. Drawing it before this boundary meant it
            # covered the WHOLE DISPLAY - the previous compositor owner's
            # viewport was still active - and it was drawn without the layer's
            # intended alpha blending, so its transparent shadow pixels did not
            # composite. Both draws now share this state and this geometry.
            gl.glViewport(x_px, y_px, w_px, h_px)
            # Scissor bounds every write this layer makes - including the
            # stencil clear inside the mask path - to the card rect, so the
            # base image and transition already in the framebuffer are safe.
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(x_px, y_px, w_px, h_px)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            try:
                # Card beneath, bars above; no viewport restore between them.
                self._render_card_visual(geometry, fade)
                owner.paint_layer(geometry.local_rect(), bars_fade)
            finally:
                self._restore_gl_state()
            self._last_failure_signature = None
            return True
        except Exception:
            self._record_failure("render_exception")
            # Exception paths must leave the compositor in the same documented
            # state as success, or the next owner inherits a broken pipeline.
            self._restore_gl_state()
            return False
        finally:
            owner._compositor_mask_origin_px = None
            owner._presentation_geometry = None

    def _restore_gl_state(self) -> None:
        """Return the documented post-layer GL state for the next owner.

        Explicit restoration of exactly what this layer changes - no per-frame
        glGet* interrogation. The stencil path is included because the card mask
        enables stencil test, writes the mask and narrows the colour mask.
        """
        if gl is None:
            return
        try:
            gl.glDisable(gl.GL_SCISSOR_TEST)
            gl.glDisable(gl.GL_STENCIL_TEST)
            gl.glStencilMask(0x00)
            gl.glColorMask(True, True, True, True)
            gl.glDisable(gl.GL_BLEND)
            gl.glUseProgram(0)
            gl.glBindVertexArray(0)
        except Exception:
            logger.debug("[SPOTIFY_VIS][LAYER] GL state restore failed", exc_info=True)

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

    def _card_revision(self, card, geometry: "PresentationGeometry") -> tuple:
        """Identity of the authored card image for the target geometry.

        Derived from the card's OWN canonical pixmap cache key, so the QPixmap
        rebuild and this GL re-upload can never disagree. A second, manually
        parallel definition would eventually let the pixmap invalidate correctly
        while the texture stayed stale.

        Fade is deliberately absent - it is a GL alpha multiplier, so a fade
        animation never re-uploads.
        """
        from widgets.spotify_visualizer.card_paint import (
            painted_frame_shadow_cache_key,
        )

        return painted_frame_shadow_cache_key(
            card,
            logical_size=geometry.logical_rect.size(),
            dpr=geometry.dpr,
        )

    def _render_card_visual(self, geometry: "PresentationGeometry", fade: float) -> None:
        """Draw the card background/border/shadow beneath the shader layer.

        The authored appearance still comes from the card's own QPainter output;
        it is uploaded to a GL texture when its revision changes and drawn as a
        textured quad thereafter. Drawing the cached pixmap through
        QOpenGLPaintDevice/QPainter on every presented frame was pure
        steady-state work for an image that had not changed.
        """
        if not self._ensure_card_visual(geometry):
            return
        try:
            self._card_texture.draw(fade)
        except Exception:
            self._record_failure("card_visual_exception")

    def _ensure_card_visual(self, geometry: "PresentationGeometry") -> bool:
        """Claim card-visual ownership and upload its texture; draw nothing.

        Split out of the draw path so the identical work can run during the
        fade-zero readiness pass. Ownership must be claimed BEFORE the visible
        fade leaves zero, otherwise the card QWidget paints itself at full
        opacity until the compositor takes over - a mid-animation owner handoff.

        Returns True when there is a card texture ready to draw.
        """
        card = self._card_widget()
        if card is None:
            return False
        try:
            # Claim the visual exactly once; the card keeps everything else.
            claim = getattr(card, "set_compositor_owns_card_visual", None)
            if callable(claim):
                claim(True)
            if not self._card_texture_required(card):
                # No background: nothing to occlude, nothing to draw.
                return False

            revision = self._card_revision(card, geometry)
            if self._card_texture.revision != revision:
                from widgets.spotify_visualizer.card_paint import (
                    ensure_painted_frame_shadow_pixmap,
                )

                # Rendered FOR the authoritative presentation size and DPR,
                # never taken from the live QWidget geometry and never rescaled
                # after the fact, which would change border/radius/shadow.
                pixmap = ensure_painted_frame_shadow_pixmap(
                    card,
                    logical_size=geometry.logical_rect.size(),
                    dpr=geometry.dpr,
                )
                if pixmap is None or pixmap.isNull():
                    return False
                if not self._card_texture.ensure_uploaded(pixmap, revision):
                    return False
            return True
        except Exception:
            self._record_failure("card_visual_exception")
            return False

    @staticmethod
    def _card_texture_required(card) -> bool:
        """Whether this card has authored pixels that need a GL texture.

        A card with no background frame legitimately has nothing to upload, so
        readiness must not wait for a texture that will never exist.
        """
        try:
            if not bool(getattr(card, "_show_background", False)):
                return False
            return bool(card.uses_painted_frame_shadow())
        except Exception:
            return False

    # -- readiness / preparation -----------------------------------------

    def _commit_geometry(
        self, geometry: "PresentationGeometry", borrowed
    ) -> None:
        self._committed_geometry = geometry
        try:
            self._committed_generation = int(getattr(borrowed, "generation", -1))
        except Exception:
            self._committed_generation = -1

    def _current_gl_generation(self) -> int:
        borrowed = getattr(self._compositor, "_rhi_gl", None)
        try:
            return int(getattr(borrowed, "generation", -1))
        except Exception:
            return -1

    def prepare(self, surface_height_px: int, dpr: float) -> bool:
        """Establish everything needed to draw the visualizer, at fade zero.

        Runs inside the compositor's external GL section exactly like
        ``render()``, so the borrowed QRhi OpenGL context is current and no raw
        GL is touched from an arbitrary widget callback. It compiles the mode
        programs, creates the shared VAO/VBO/mask, commits the authoritative
        presentation geometry, claims card-visual ownership and uploads the card
        texture - and draws nothing.

        Returns True once this compositor generation is ready to present.
        """
        if gl is None:
            return False
        state = self._state
        if state is None or state.owner is None:
            return False
        rect = state.card_rect
        if rect.width() <= 0 or rect.height() <= 0:
            return False

        borrowed = getattr(self._compositor, "_rhi_gl", None)
        if not self.ensure_initialized(borrowed.context if borrowed else None):
            return False

        geometry = PresentationGeometry(rect, dpr, surface_height_px)
        self._commit_geometry(geometry, borrowed)
        try:
            self._ensure_card_visual(geometry)
        except Exception:
            self._record_failure("prepare_card_exception")
            return False

        ready = self.readiness().is_ready
        if ready and not self._prepared_notified:
            self._prepared_notified = True
            self._notify_prepared(state.owner)
        return ready

    def _notify_prepared(self, owner: Any) -> None:
        """Tell the visualizer, once, that its pixels can now be drawn.

        Deferred onto the GUI event loop rather than called from inside the
        render pass: the reveal path starts an animation and touches widget
        state, which must not run re-entrantly inside a paint. This is one
        queued callback per preparation, not a timer.
        """
        notify = getattr(owner, "notify_presentation_ready", None)
        if not callable(notify):
            return
        try:
            from core.threading.manager import ThreadManager

            ThreadManager.single_shot(0, notify)
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS][LAYER] Failed to dispatch readiness notification",
                exc_info=True,
            )

    def readiness(self) -> VisualizerPresentationReadiness:
        """Report presentation readiness for the CURRENT compositor generation."""
        generation = self._current_gl_generation()
        state = self._state
        owner = state.owner if state is not None else None
        if owner is None:
            owner = self._resource_owner

        gl_ready = False
        gl_failed = False
        if owner is not None:
            probe = getattr(owner, "layer_gl_resources_ready", None)
            if callable(probe):
                try:
                    gl_ready = bool(probe())
                except Exception:
                    gl_ready = False
            failed = getattr(owner, "layer_gl_failed", None)
            if callable(failed):
                try:
                    gl_failed = bool(failed())
                except Exception:
                    gl_failed = False

        geometry_committed = (
            self._committed_geometry is not None
            and generation > 0
            and self._committed_generation == generation
        )

        card = self._card_widget()
        card_visual_owned = False
        card_texture_ready = False
        if card is not None:
            try:
                card_visual_owned = bool(
                    getattr(card, "_compositor_owns_card_visual", False)
                )
            except Exception:
                card_visual_owned = False
            if not self._card_texture_required(card):
                # Nothing authored to upload for this card configuration.
                card_texture_ready = True
            elif geometry_committed and self._committed_geometry is not None:
                try:
                    card_texture_ready = self._card_texture.revision == self._card_revision(
                        card, self._committed_geometry
                    )
                except Exception:
                    card_texture_ready = False

        return VisualizerPresentationReadiness(
            gl_generation=generation,
            gl_resources_ready=gl_ready,
            gl_failed=gl_failed,
            geometry_committed=geometry_committed,
            card_visual_owned=card_visual_owned,
            card_texture_ready=card_texture_ready,
        )

    def is_presentation_ready(self) -> bool:
        return self.readiness().is_ready

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
        """Free everything this compositor generation owns.

        Runs unconditionally on compositor teardown, regardless of whether any
        state is currently published. Card texture ownership must never depend
        on the visualizer being visible at the moment teardown happens.

        Order: release the card QWidget visual, delete the card
        texture/program/VAO/VBO, then the visualizer GL resources through their
        persistent owner. Fail-closed semantics hold - a failed deletion raises
        and retains ownership, and a second cleanup after success is a no-op.
        """
        self._release_card_visual()
        self._state = None
        self._committed_geometry = None
        self._committed_generation = -1
        self._prepared_notified = False

        errors: list[str] = []
        try:
            self._card_texture.cleanup()
        except Exception as exc:
            errors.append("card_texture:%s:%s" % (type(exc).__name__, exc))

        owner = self._resource_owner
        if owner is not None:
            cleanup_gl = getattr(owner, "cleanup_gl", None)
            if callable(cleanup_gl):
                try:
                    cleanup_gl()
                except Exception as exc:
                    errors.append("visualizer_gl:%s:%s" % (type(exc).__name__, exc))
            if not errors:
                self._resource_owner = None

        if errors:
            raise RuntimeError(
                "Visualizer layer cleanup incomplete: " + " | ".join(errors)
            )

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
