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

    # Preparation attempts allowed before the reveal proceeds without readiness.
    # Roughly two seconds of display-refresh presentation; it exists purely so no
    # unforeseen readiness condition can hide the visualizer permanently.
    _PREPARE_ATTEMPT_BUDGET = 120

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
        # One-shot edit snapshot request. CUSTOM edit needs the visualizer
        # scene as pixels, and the visualizer no longer has a framebuffer of
        # its own to grab.
        self._capture_requested = False
        self._captured_scene_image = None
        # Monotonic identity of the latest useful visualizer scene. It
        # advances on every publication and on clear, so a physical
        # presentation deadline can tell whether painting again would
        # reveal anything the last requested paint did not.
        self._scene_revision = 0
        # Set when the authored card image genuinely could not be produced
        # or uploaded. Readiness stays truthful, but the reveal gate must not
        # wait forever for something that cannot arrive.
        self._card_preparation_failed = False
        # Bounded preparation attempts for this compositor generation. Counted on
        # a real event - each render-pass preparation - not on a clock.
        self._prepare_attempts = 0

    # -- publication ------------------------------------------------------

    def publish(self, state: Optional[VisualizerRenderState]) -> None:
        """Accept the latest render state, replacing any previous one."""
        # Every publication is a new authored scene: fade progress, card
        # identity and mode state all arrive through here.
        self._scene_revision += 1
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
        # Clearing is itself a scene change: the card must stop being drawn.
        self._scene_revision += 1
        # Readiness must not survive the state it described.
        self._committed_geometry = None
        self._committed_generation = -1
        self._prepared_notified = False
        self._capture_requested = False
        self._captured_scene_image = None
        self._card_preparation_failed = False
        self._prepare_attempts = 0

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

    @property
    def scene_revision(self) -> int:
        """Monotonic identity of the latest useful visualizer scene."""
        return self._scene_revision

    def invalidate_scene(self) -> None:
        """Force the next deadline to be eligible.

        For changes that alter the drawn result without a new publication -
        a card style/geometry rebuild, for example.
        """
        self._scene_revision += 1

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
            if self._capture_requested:
                self._capture_requested = False
                self._captured_scene_image = self._capture_scene_image(
                    geometry, owner
                )
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
        from widgets.spotify_visualizer.card_surface import (
            compositor_card_surface_cache_key,
        )

        return compositor_card_surface_cache_key(
            card,
            logical_size=geometry.logical_rect.size(),
            dpr=geometry.dpr,
        )

    def _render_card_visual(self, geometry: "PresentationGeometry", fade: float) -> None:
        """Draw the card background/border beneath the shader layer.

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
                from widgets.spotify_visualizer.card_surface import (
                    ensure_compositor_card_surface_pixmap,
                )

                # Rendered FOR the authoritative presentation size and DPR,
                # never taken from the live QWidget geometry and never rescaled
                # after the fact, which would change border/radius.
                pixmap = ensure_compositor_card_surface_pixmap(
                    card,
                    logical_size=geometry.logical_rect.size(),
                    dpr=geometry.dpr,
                )
                if pixmap is None or pixmap.isNull():
                    self._card_preparation_failed = True
                    return False
                if not self._card_texture.ensure_uploaded(pixmap, revision):
                    self._card_preparation_failed = True
                    return False
            self._card_preparation_failed = False
            return True
        except Exception:
            self._card_preparation_failed = True
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
            return bool(card.uses_compositor_card_surface())
        except Exception:
            return False

    # -- edit snapshot ----------------------------------------------------

    def request_scene_capture(self) -> None:
        """Ask for ONE snapshot of the visualizer scene on the next draw.

        The visualizer is not a presented surface any more, so CUSTOM edit
        cannot grab its framebuffer. This is the compositor-owned replacement:
        a single request, serviced inside the normal render pass where the
        borrowed QRhi OpenGL context is legitimately current.
        """
        self._capture_requested = True

    def take_captured_scene_image(self):
        """Pop the captured scene image, if the request has been serviced."""
        image = self._captured_scene_image
        self._captured_scene_image = None
        return image

    def _capture_scene_image(self, geometry: "PresentationGeometry", owner: Any):
        """Render ONLY the card region into a transparent offscreen target.

        Reading the card rect back out of the compositor framebuffer would
        bake in the base image behind the card and lose alpha entirely, so the
        scene is re-drawn card-local into its own target instead. The result is
        the authored card plus the current shader output at the authoritative
        geometry, with correct alpha and nothing else on the display.

        Drawn at full opacity: the preview represents the card, not whatever
        moment of a fade edit mode happened to be entered on.
        """
        from PySide6.QtGui import QImage

        width_px, height_px = geometry.framebuffer_size_px
        if width_px <= 0 or height_px <= 0:
            return None

        fbo = 0
        texture = 0
        stencil = 0
        previous_fbo = 0
        try:
            previous_fbo = int(gl.glGetIntegerv(gl.GL_FRAMEBUFFER_BINDING))
            fbo = int(gl.glGenFramebuffers(1))
            texture = int(gl.glGenTextures(1))
            stencil = int(gl.glGenRenderbuffers(1))

            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, width_px, height_px,
                0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None,
            )
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, stencil)
            gl.glRenderbufferStorage(
                gl.GL_RENDERBUFFER, gl.GL_DEPTH24_STENCIL8, width_px, height_px
            )
            gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, 0)

            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D, texture, 0,
            )
            gl.glFramebufferRenderbuffer(
                gl.GL_FRAMEBUFFER, gl.GL_DEPTH_STENCIL_ATTACHMENT,
                gl.GL_RENDERBUFFER, stencil,
            )
            if gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) != gl.GL_FRAMEBUFFER_COMPLETE:
                self._record_failure("capture_incomplete_fbo")
                return None

            # Card-local: this target IS the card, so the mask shader's window
            # space origin is (0, 0) rather than the card's display position.
            local_rect = QRect(
                0, 0,
                geometry.logical_rect.width(),
                geometry.logical_rect.height(),
            )
            local_geometry = PresentationGeometry(local_rect, geometry.dpr, height_px)

            gl.glViewport(0, 0, width_px, height_px)
            gl.glEnable(gl.GL_SCISSOR_TEST)
            gl.glScissor(0, 0, width_px, height_px)
            gl.glClearColor(0.0, 0.0, 0.0, 0.0)
            gl.glClearStencil(0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_STENCIL_BUFFER_BIT)
            gl.glEnable(gl.GL_BLEND)
            # Separate alpha blending: compositing onto a transparent target
            # with the display's straight SRC_ALPHA function would leave the
            # captured alpha wrong wherever the card is translucent.
            gl.glBlendFuncSeparate(
                gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA,
                gl.GL_ONE, gl.GL_ONE_MINUS_SRC_ALPHA,
            )

            saved_origin = owner._compositor_mask_origin_px
            saved_geometry = owner._presentation_geometry
            owner._compositor_mask_origin_px = (0.0, 0.0)
            owner._presentation_geometry = local_geometry
            try:
                self._card_texture.draw(1.0)
                owner.paint_layer(local_geometry.local_rect(), 1.0)
            finally:
                owner._compositor_mask_origin_px = saved_origin
                owner._presentation_geometry = saved_geometry

            gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
            raw = gl.glReadPixels(
                0, 0, width_px, height_px, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE
            )
            # GL row 0 is the bottom row; Qt's is the top. Reversing the rows
            # here avoids the deprecated QImage mirror helpers and costs one
            # copy of a card-sized buffer, once, at edit entry.
            stride = width_px * 4
            data = bytes(raw)
            flipped = b"".join(
                data[row * stride:(row + 1) * stride]
                for row in range(height_px - 1, -1, -1)
            )
            image = QImage(
                flipped, width_px, height_px, stride, QImage.Format.Format_RGBA8888
            )
            return image.copy()
        except Exception:
            self._record_failure("capture_exception")
            return None
        finally:
            try:
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, previous_fbo)
                if fbo:
                    gl.glDeleteFramebuffers(1, [fbo])
                if texture:
                    gl.glDeleteTextures(1, [texture])
                if stencil:
                    gl.glDeleteRenderbuffers(1, [stencil])
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS][LAYER] Failed to release capture target",
                    exc_info=True,
                )
            self._restore_gl_state()

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

        self._prepare_attempts += 1

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

    def can_reveal(self) -> bool:
        """Whether the visible fade may begin.

        Normally this is readiness. It also becomes true once preparation has
        genuinely been attempted for this compositor generation and cannot
        complete - a failed GL initialization, or an authored card image that
        cannot be produced or uploaded.

        A readiness gate is allowed to DELAY the reveal. It is not allowed to
        hide the visualizer forever: a permanently invisible visualizer is a
        far worse failure than one that reveals without a perfect card.
        """
        readiness = self.readiness()
        if readiness.is_ready:
            return True
        if readiness.gl_generation <= 0:
            return False
        blocked = readiness.gl_failed or (
            readiness.geometry_committed and self._card_preparation_failed
        )
        if not blocked and self._prepare_attempts >= self._PREPARE_ATTEMPT_BUDGET:
            # Preparation has had a real, bounded number of render-pass attempts
            # for this generation and is still not ready. Whatever it is waiting
            # for is not arriving, and an invisible visualizer is not an
            # acceptable resting state.
            blocked = True
        if not blocked:
            return False
        self._record_failure(
            "reveal_without_readiness:" + ",".join(readiness.missing())
        )
        return True

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
