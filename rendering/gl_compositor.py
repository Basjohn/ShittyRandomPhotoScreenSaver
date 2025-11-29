"""Single OpenGL compositor widget for DisplayWidget.

This module introduces a single per-display GL compositor that is responsible
for drawing the base image and GL-backed transitions. The intent is to replace
per-transition QOpenGLWidget overlays with a single GL surface that owns the
composition, reducing DWM/stacking complexity and flicker on Windows.

Initial implementation focuses on a GPU-backed Crossfade equivalent. Other
transitions (Slide, Wipe, Block Puzzle Flip, Blinds) can be ported onto this
compositor over time.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Callable
import time
import math
import ctypes

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QPixmap, QRegion, QImage
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger
from core.animation.types import EasingCurve
from core.animation.animator import AnimationManager
from rendering.gl_format import apply_widget_surface_format
from transitions.wipe_transition import WipeDirection, _compute_wipe_region
from transitions.slide_transition import SlideDirection
from core.resources.manager import ResourceManager

try:  # Optional dependency; shaders are disabled if unavailable.
    from OpenGL import GL as gl  # type: ignore[import]
except Exception:  # pragma: no cover - PyOpenGL not required for CPU paths
    gl = None


logger = get_logger(__name__)


@dataclass
class CrossfadeState:
    """State for a compositor-driven crossfade transition."""

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    progress: float = 0.0  # 0..1


@dataclass
class SlideState:
    """State for a compositor-driven slide transition."""

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    old_start: QPoint
    old_end: QPoint
    new_start: QPoint
    new_end: QPoint
    progress: float = 0.0  # 0..1


@dataclass
class WipeState:
    """State for a compositor-driven wipe transition."""

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    direction: WipeDirection
    progress: float = 0.0  # 0..1


@dataclass
class WarpState:
    """State for a compositor-driven warp dissolve transition.

    Warp dissolve is modelled as a band-based distortion of the old image over
    the new one. The compositor always draws the new image fully and overlays
    horizontally sliced bands of the old image that jitter and fade out over
    time according to ``progress``.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    progress: float = 0.0  # 0..1


@dataclass
class BlockFlipState:
    """State for a compositor-driven block puzzle flip transition.

    The detailed per-block progression is managed by the controller; the
    compositor only needs the reveal region to clip the new pixmap.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    region: Optional[QRegion] = None
    progress: float = 0.0  # 0..1


@dataclass
class RaindropsState:
    """State for a shader-driven raindrops transition.

    This models a full-frame droplet field where the compositor draws the
    effect using GLSL; controllers only need to provide the old/new pixmaps
    and timeline progress.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    progress: float = 0.0  # 0..1


@dataclass
class _GLPipelineState:
    """Minimal shader pipeline state for GL-backed transitions.

    Phase 1 scaffolding only – this holds the objects needed to render
    textured quads via GLSL. Later phases will populate these with real
    OpenGL ids and use them from paintGL; for now they are created and
    cleaned up but not yet wired into the rendering path.
    """

    # Raw OpenGL object ids. These remain ``int`` so we do not depend on
    # PyOpenGL types in the public API surface of this module.
    quad_vao: int = 0
    quad_vbo: int = 0
    # Geometry for the BlockSpin 3D slab (box mesh rendered with triangles).
    box_vao: int = 0
    box_vbo: int = 0
    box_vertex_count: int = 0
    basic_program: int = 0
    raindrops_program: int = 0
    warp_program: int = 0
    claws_program: int = 0

    # Textures for the current pair of images being blended/transitioned.
    old_tex_id: int = 0
    new_tex_id: int = 0

    # Cached uniform locations for the basic card-flip program.
    u_angle_loc: int = -1
    u_aspect_loc: int = -1
    u_old_tex_loc: int = -1
    u_new_tex_loc: int = -1

    # Simple flags to indicate whether the pipeline was initialized
    # successfully inside the current GL context.
    initialized: bool = False


@dataclass
class BlockSpinState:
    """State for a compositor-driven block spin transition.

    Block spins share the same logical grid as BlockFlip but approximate a
    3D flip by shrinking tile width over time. The compositor always draws the
    new image as the background and overlays animated tiles from either the old
    or new image depending on local phase.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    rows: int
    cols: int
    progress: float = 0.0  # 0..1


@dataclass
class PeelState:
    """State for a compositor-driven peel transition.

    Peel is modelled as a strip-based effect that peels the old image away in
    a chosen cardinal direction while revealing the new image underneath. The
    compositor draws the new image fully and then overlays shrinking, drifting
    strips of the old image according to ``progress`` and ``strips``.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    direction: SlideDirection
    strips: int
    progress: float = 0.0  # 0..1


@dataclass
class BlindsState:
    """State for a compositor-driven blinds transition.

    Like BlockFlip, the controller owns per-slat progression and provides an
    aggregate reveal region; the compositor only clips the new pixmap.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    region: Optional[QRegion] = None
    progress: float = 0.0  # 0..1


@dataclass
class DiffuseState:
    """State for a compositor-driven diffuse transition.

    The controller owns per-cell progression and provides an aggregate reveal
    region; the compositor only clips the new pixmap.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    region: Optional[QRegion] = None
    progress: float = 0.0  # 0..1


class GLCompositorWidget(QOpenGLWidget):
    """Single GL compositor that renders the base image and transitions.

    This widget is intended to be created as a single child of DisplayWidget,
    covering its full client area in borderless fullscreen mode. Transitions
    are driven externally (via AnimationManager); the compositor simply
    renders according to the current state.
    """

    def __init__(self, parent) -> None:
        super().__init__(parent)
        prefs = apply_widget_surface_format(self, reason="gl_compositor")
        self._surface_prefs = prefs

        # Avoid system background clears and rely entirely on our paintGL.
        try:
            self.setAutoFillBackground(False)
            self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        except Exception:
            pass
        try:
            self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        except Exception:
            pass

        self._base_pixmap: Optional[QPixmap] = None
        self._crossfade: Optional[CrossfadeState] = None
        self._slide: Optional[SlideState] = None
        self._wipe: Optional[WipeState] = None
        self._warp: Optional[WarpState] = None
        self._blockflip: Optional[BlockFlipState] = None
        self._blockspin: Optional[BlockSpinState] = None
        self._blinds: Optional[BlindsState] = None
        self._diffuse: Optional[DiffuseState] = None
        self._raindrops: Optional[RaindropsState] = None
        self._peel: Optional[PeelState] = None

        # Profiling for compositor-driven slide transitions (Route3 §6.4).
        # Metrics are logged with the "[PERF] [GL COMPOSITOR]" tag so
        # production builds can grep and gate/strip this telemetry if needed.
        self._slide_profile_start_ts: Optional[float] = None
        self._slide_profile_last_ts: Optional[float] = None
        self._slide_profile_frame_count: int = 0
        self._slide_profile_min_dt: float = 0.0
        self._slide_profile_max_dt: float = 0.0
        self._wipe_profile_start_ts: Optional[float] = None
        self._wipe_profile_last_ts: Optional[float] = None
        self._wipe_profile_frame_count: int = 0
        self._wipe_profile_min_dt: float = 0.0
        self._wipe_profile_max_dt: float = 0.0

        # Animation plumbing: compositor does not own AnimationManager, but we
        # keep the current animation id so the caller can cancel if needed.
        self._animation_manager: Optional[AnimationManager] = None
        self._current_anim_id: Optional[str] = None
        # Default easing is QUAD_IN_OUT; callers can override per-transition.
        self._current_easing: EasingCurve = EasingCurve.QUAD_IN_OUT

        # Phase 1 GLSL pipeline scaffolding. The actual OpenGL resource
        # creation is deferred to initializeGL so that a valid context is
        # guaranteed. For now we keep the pipeline disabled; later phases
        # will turn this on for specific transitions.
        self._gl_pipeline: Optional[_GLPipelineState] = None
        self._use_shaders: bool = False
        self._gl_disabled_for_session: bool = False

        # Optional ResourceManager hook so higher-level code can track this
        # compositor as a GUI resource. Individual GL object lifetimes remain
        # owned by GLCompositorWidget; ResourceManager is only aware of the
        # widget itself.
        self._resource_manager: Optional[ResourceManager] = None

    # ------------------------------------------------------------------
    # Public API used by DisplayWidget / transitions
    # ------------------------------------------------------------------

    def set_base_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        """Set the base image when no transition is active."""
        self._base_pixmap = pixmap
        # If no crossfade is active, repaint immediately.
        if self._crossfade is None:
            self.update()

    def start_crossfade(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a crossfade between two pixmaps using the compositor.

        This replaces the old per-transition `_GLFadeWidget`. The caller is
        responsible for ensuring that `animation_manager` lives at least as
        long as the transition.
        """
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for crossfade")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately")
            self._crossfade = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Crossfade and slide are mutually exclusive; clear any active slide.
        self._slide = None
        self._crossfade = CrossfadeState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0)
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_crossfade_update,
            on_complete=lambda: self._on_crossfade_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_warp(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a warp dissolve between two pixmaps using the compositor.

        Warp dissolve is a photo-friendly effect that keeps the new image
        stable while the old image appears as gently jittering horizontal bands
        that drift and fade away over time.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for warp dissolve")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (warp)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._warp = None
            self._blockflip = None
            self._blockspin = None
            self._blinds = None
            self._diffuse = None
            self._peel = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Warp dissolve is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blockspin = None
        self._blinds = None
        self._diffuse = None
        self._peel = None
        self._warp = WarpState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            progress=0.0,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_warp_update,
            on_complete=lambda: self._on_warp_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_raindrops(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a shader-driven raindrops transition between two pixmaps.

        This path is only used when the GLSL pipeline and raindrops shader are
        available; callers are expected to fall back to the existing diffuse
        implementation when this method returns ``None``.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for raindrops")
            return None

        # Only use this path when the GLSL pipeline and raindrops shader are
        # actually available. Callers are expected to fall back to the
        # compositor's diffuse implementation when this returns ``None``.
        if (
            self._gl_disabled_for_session
            or gl is None
            or self._gl_pipeline is None
            or not self._gl_pipeline.initialized
            or not self._gl_pipeline.raindrops_program
        ):
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (raindrops)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._warp = None
            self._blockflip = None
            self._blockspin = None
            self._blinds = None
            self._diffuse = None
            self._raindrops = None
            self._peel = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Raindrops are mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._warp = None
        self._blockflip = None
        self._blockspin = None
        self._blinds = None
        self._diffuse = None
        self._peel = None
        self._raindrops = RaindropsState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            progress=0.0,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_raindrops_update,
            on_complete=lambda: self._on_raindrops_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_wipe(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        direction: WipeDirection,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a wipe between two pixmaps using the compositor.

        The caller is responsible for providing the wipe direction; geometry is
        derived from the widget rect and kept in sync with the CPU Wipe
        transition via the shared `_compute_wipe_region` helper.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for wipe")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (wipe)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Wipe is mutually exclusive with crossfade and slide.
        self._crossfade = None
        self._slide = None
        self._wipe = WipeState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            direction=direction,
            progress=0.0,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        self._wipe_profile_start_ts = time.time()
        self._wipe_profile_last_ts = None
        self._wipe_profile_frame_count = 0
        self._wipe_profile_min_dt = 0.0
        self._wipe_profile_max_dt = 0.0

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_wipe_update,
            on_complete=lambda: self._on_wipe_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_slide(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        old_start: QPoint,
        old_end: QPoint,
        new_start: QPoint,
        new_end: QPoint,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a slide between two pixmaps using the compositor.

        The caller is responsible for providing start/end positions that
        correspond to the desired slide direction and widget geometry.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for slide")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (slide)")
            self._crossfade = None
            self._slide = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Slide and crossfade/wipe are mutually exclusive; clear any active crossfade/wipe.
        self._crossfade = None
        self._wipe = None
        self._slide = SlideState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            old_start=old_start,
            old_end=old_end,
            new_start=new_start,
            new_end=new_end,
            progress=0.0,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Reset slide profiling state for this transition.
        self._slide_profile_start_ts = time.time()
        self._slide_profile_last_ts = None
        self._slide_profile_frame_count = 0
        self._slide_profile_min_dt = 0.0
        self._slide_profile_max_dt = 0.0

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_slide_update,
            on_complete=lambda: self._on_slide_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_peel(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        direction: SlideDirection,
        strips: int,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a strip-based peel between two pixmaps using the compositor.

        Peel is implemented as a directional, strip-driven effect that always
        draws the new image as the base frame and overlays shrinking, drifting
        bands of the old image which "peel" away over time. Geometry is kept
        simple and driven entirely by the compositor; controllers provide only
        direction, strip count and timing.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for peel")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (peel)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._blockflip = None
            self._blinds = None
            self._diffuse = None
            self._peel = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Peel is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blinds = None
        self._diffuse = None
        self._peel = PeelState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            direction=direction,
            strips=max(1, int(strips)),
            progress=0.0,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_peel_update,
            on_complete=lambda: self._on_peel_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_block_flip(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        update_callback: Callable[[float], None],
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a block puzzle flip using the compositor.

        The caller owns per-block timing and progression and must update the
        reveal region via :meth:`set_blockflip_region` from the provided
        ``update_callback``.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for block flip")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (block flip)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._blockflip = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Block flip is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = BlockFlipState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            region=None,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=update_callback,
            on_complete=lambda: self._on_blockflip_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_block_spin(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        rows: int,
        cols: int,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a block spin using the compositor.

        Block spins share the same logical grid as BlockFlip but approximate a
        3D flip by shrinking tile width over time. Geometry is computed inside
        the compositor from the provided row/column counts.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for block spin")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (block spin)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._blockflip = None
            self._blockspin = None
            self._blinds = None
            self._diffuse = None
            self._peel = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Block spin is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blinds = None
        self._diffuse = None
        self._peel = None
        self._blockspin = BlockSpinState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            rows=max(1, int(rows)),
            cols=max(1, int(cols)),
            progress=0.0,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_blockspin_update,
            on_complete=lambda: self._on_blockspin_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_diffuse(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        update_callback: Callable[[float], None],
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a diffuse reveal using the compositor.

        The caller owns per-cell timing/geometry and must update the reveal
        region via :meth:`set_diffuse_region` from the provided
        ``update_callback``.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for diffuse")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (diffuse)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._blockflip = None
            self._blinds = None
            self._diffuse = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Diffuse is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blinds = None
        self._diffuse = DiffuseState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            region=None,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=update_callback,
            on_complete=lambda: self._on_diffuse_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_blinds(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        update_callback: Callable[[float], None],
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a blinds reveal using the compositor.

        The caller owns per-slat timing/geometry and must update the reveal
        region via :meth:`set_blinds_region` from the provided
        ``update_callback``.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for blinds")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (blinds)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._blockflip = None
            self._blinds = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Blinds is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blinds = BlindsState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            region=None,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=update_callback,
            on_complete=lambda: self._on_blinds_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    # ------------------------------------------------------------------
    # Animation callbacks
    # ------------------------------------------------------------------

    def _on_crossfade_update(self, progress: float) -> None:
        if self._crossfade is None:
            return
        # Clamp and store progress
        p = max(0.0, min(1.0, float(progress)))
        self._crossfade.progress = p
        self.update()

    def _on_crossfade_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        # Snap to final state: base pixmap becomes the new image, transition ends.
        if self._crossfade is not None:
            try:
                self._base_pixmap = self._crossfade.new_pixmap
            except Exception:
                pass
        self._crossfade = None
        self._current_anim_id = None
        self.update()
        if on_finished:
            try:
                on_finished()
            except Exception:
                logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)

    def _on_slide_update(self, progress: float) -> None:
        if self._slide is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._slide.progress = p

        # Profiling: track frame timing for compositor-driven slide.
        now = time.time()
        if self._slide_profile_start_ts is None:
            self._slide_profile_start_ts = now
        if self._slide_profile_last_ts is not None:
            dt = now - self._slide_profile_last_ts
            if dt > 0.0:
                if self._slide_profile_min_dt == 0.0 or dt < self._slide_profile_min_dt:
                    self._slide_profile_min_dt = dt
                if dt > self._slide_profile_max_dt:
                    self._slide_profile_max_dt = dt
        self._slide_profile_last_ts = now
        self._slide_profile_frame_count += 1

        self.update()

    def _on_slide_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Handle completion of compositor-driven slide transitions.

        This callback may fire after the underlying QOpenGLWidget has been
        deleted (e.g. during test teardown). All QWidget/QObject calls are
        therefore wrapped defensively to avoid RuntimeError bubbling out of
        the Qt event loop.
        """

        try:
            # Emit a concise profiling summary for slide transitions.
            # The log line is tagged with "[PERF] [GL COMPOSITOR]" for easy
            # discovery/disablement when preparing production builds.
            try:
                if (
                    self._slide_profile_start_ts is not None
                    and self._slide_profile_last_ts is not None
                    and self._slide_profile_frame_count > 0
                ):
                    elapsed = max(0.0, self._slide_profile_last_ts - self._slide_profile_start_ts)
                    if elapsed > 0.0:
                        duration_ms = elapsed * 1000.0
                        avg_fps = self._slide_profile_frame_count / elapsed
                        min_dt_ms = self._slide_profile_min_dt * 1000.0 if self._slide_profile_min_dt > 0.0 else 0.0
                        max_dt_ms = self._slide_profile_max_dt * 1000.0 if self._slide_profile_max_dt > 0.0 else 0.0
                        logger.info(
                            "[PERF] [GL COMPOSITOR] Slide metrics: duration=%.1fms, frames=%d, "
                            "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                            duration_ms,
                            self._slide_profile_frame_count,
                            avg_fps,
                            min_dt_ms,
                            max_dt_ms,
                            self.width(),
                            self.height(),
                        )
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Slide metrics logging failed: %s", e, exc_info=True)

            # Reset profiling state.
            self._slide_profile_start_ts = None
            self._slide_profile_last_ts = None
            self._slide_profile_frame_count = 0
            self._slide_profile_min_dt = 0.0
            self._slide_profile_max_dt = 0.0

            # Snap to final state: base pixmap becomes the new image, transition ends.
            if self._slide is not None:
                try:
                    self._base_pixmap = self._slide.new_pixmap
                except Exception:
                    pass
            self._slide = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Slide complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            # Final safeguard so no exception escapes the Qt event loop.
            logger.debug("[GL COMPOSITOR] Slide complete handler failed: %s", e, exc_info=True)

    def _on_wipe_update(self, progress: float) -> None:
        if self._wipe is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._wipe.progress = p

        now = time.time()
        if self._wipe_profile_start_ts is None:
            self._wipe_profile_start_ts = now
        if self._wipe_profile_last_ts is not None:
            dt = now - self._wipe_profile_last_ts
            if dt > 0.0:
                if self._wipe_profile_min_dt == 0.0 or dt < self._wipe_profile_min_dt:
                    self._wipe_profile_min_dt = dt
                if dt > self._wipe_profile_max_dt:
                    self._wipe_profile_max_dt = dt
        self._wipe_profile_last_ts = now
        self._wipe_profile_frame_count += 1
        self.update()

    def _on_wipe_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Handle completion of compositor-driven wipe transitions."""

        try:
            try:
                if (
                    self._wipe_profile_start_ts is not None
                    and self._wipe_profile_last_ts is not None
                    and self._wipe_profile_frame_count > 0
                ):
                    elapsed = max(0.0, self._wipe_profile_last_ts - self._wipe_profile_start_ts)
                    if elapsed > 0.0:
                        duration_ms = elapsed * 1000.0
                        avg_fps = self._wipe_profile_frame_count / elapsed
                        min_dt_ms = self._wipe_profile_min_dt * 1000.0 if self._wipe_profile_min_dt > 0.0 else 0.0
                        max_dt_ms = self._wipe_profile_max_dt * 1000.0 if self._wipe_profile_max_dt > 0.0 else 0.0
                        logger.info(
                            "[PERF] [GL COMPOSITOR] Wipe metrics: duration=%.1fms, frames=%d, "
                            "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                            duration_ms,
                            self._wipe_profile_frame_count,
                            avg_fps,
                            min_dt_ms,
                            max_dt_ms,
                            self.width(),
                            self.height(),
                        )
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Wipe metrics logging failed: %s", e, exc_info=True)

            self._wipe_profile_start_ts = None
            self._wipe_profile_last_ts = None
            self._wipe_profile_frame_count = 0
            self._wipe_profile_min_dt = 0.0
            self._wipe_profile_max_dt = 0.0

            # Snap to final state: base pixmap becomes the new image, transition ends.
            if self._wipe is not None:
                try:
                    self._base_pixmap = self._wipe.new_pixmap
                except Exception:
                    pass
            self._wipe = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Wipe complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Wipe complete handler failed: %s", e, exc_info=True)

    def _on_blockspin_update(self, progress: float) -> None:
        if self._blockspin is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._blockspin.progress = p
        self.update()

    def _on_warp_update(self, progress: float) -> None:
        """Update handler for compositor-driven warp dissolve transitions."""

        if self._warp is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._warp.progress = p
        self.update()

    def _on_raindrops_update(self, progress: float) -> None:
        """Update handler for shader-driven raindrops transitions."""

        if self._raindrops is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._raindrops.progress = p
        self.update()

    def _on_blockspin_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven block spin transitions."""

        try:
            if self._blockspin is not None:
                try:
                    self._base_pixmap = self._blockspin.new_pixmap
                except Exception:
                    pass
            self._blockspin = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Blockspin complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Blockspin complete handler failed: %s", e, exc_info=True)

    def _on_warp_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven warp dissolve transitions."""

        try:
            if self._warp is not None:
                try:
                    self._base_pixmap = self._warp.new_pixmap
                except Exception:
                    pass
            self._warp = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Warp complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Warp complete handler failed: %s", e, exc_info=True)

    def _on_raindrops_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for shader-driven raindrops transitions."""

        try:
            if self._raindrops is not None:
                try:
                    self._base_pixmap = self._raindrops.new_pixmap
                except Exception:
                    pass
            self._raindrops = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug(
                    "[GL COMPOSITOR] Raindrops complete update failed (likely after deletion): %s",
                    e,
                    exc_info=True,
                )

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Raindrops complete handler failed: %s", e, exc_info=True)

    def _on_peel_update(self, progress: float) -> None:
        """Update handler for compositor-driven peel transitions."""

        if self._peel is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._peel.progress = p
        self.update()

    def _on_peel_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven peel transitions."""

        try:
            if self._peel is not None:
                try:
                    self._base_pixmap = self._peel.new_pixmap
                except Exception:
                    pass
            self._peel = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Peel complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Peel complete handler failed: %s", e, exc_info=True)

    def _on_blockflip_update(self, progress: float) -> None:
        if self._blockflip is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._blockflip.progress = p
        self.update()

    def _on_blockflip_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven block flip transitions."""

        try:
            # Snap to final state: base pixmap becomes the new image, transition ends.
            if self._blockflip is not None:
                try:
                    self._base_pixmap = self._blockflip.new_pixmap
                except Exception:
                    pass
            self._blockflip = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Blockflip complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Blockflip complete handler failed: %s", e, exc_info=True)

    def _on_diffuse_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven diffuse transitions."""

        try:
            if self._diffuse is not None:
                try:
                    self._base_pixmap = self._diffuse.new_pixmap
                except Exception:
                    pass
            self._diffuse = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Diffuse complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Diffuse complete handler failed: %s", e, exc_info=True)

    def _on_blinds_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven blinds transitions."""

        try:
            if self._blinds is not None:
                try:
                    self._base_pixmap = self._blinds.new_pixmap
                except Exception:
                    pass
            self._blinds = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Blinds complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Blinds complete handler failed: %s", e, exc_info=True)

    def set_blockflip_region(self, region: Optional[QRegion]) -> None:
        """Update the reveal region for an in-flight block flip transition."""

        if self._blockflip is None:
            return
        self._blockflip.region = region
        self.update()

    def set_blinds_region(self, region: Optional[QRegion]) -> None:
        """Update the reveal region for an in-flight blinds transition."""

        if self._blinds is None:
            return
        self._blinds.region = region
        self.update()

    def set_diffuse_region(self, region: Optional[QRegion]) -> None:
        """Update the reveal region for an in-flight diffuse transition."""

        if self._diffuse is None:
            return
        self._diffuse.region = region
        self.update()

    def cancel_current_transition(self, snap_to_new: bool = True) -> None:
        """Cancel any active compositor-driven transition.

        If ``snap_to_new`` is True, the compositor's base pixmap is updated to
        the new image of the in-flight transition (if any) before clearing
        state. This is used by transitions that want to avoid visual pops when
        interrupted.
        """

        if self._animation_manager and self._current_anim_id:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to cancel current animation: %s", e, exc_info=True)
        self._current_anim_id = None

        new_pm: Optional[QPixmap] = None
        if self._crossfade is not None:
            try:
                new_pm = self._crossfade.new_pixmap
            except Exception:
                new_pm = None
        elif self._slide is not None:
            try:
                new_pm = self._slide.new_pixmap
            except Exception:
                new_pm = None
        elif self._wipe is not None:
            try:
                new_pm = self._wipe.new_pixmap
            except Exception:
                new_pm = None
        elif self._blockflip is not None:
            try:
                new_pm = self._blockflip.new_pixmap
            except Exception:
                new_pm = None
        elif self._blinds is not None:
            try:
                new_pm = self._blinds.new_pixmap
            except Exception:
                new_pm = None
        elif self._diffuse is not None:
            try:
                new_pm = self._diffuse.new_pixmap
            except Exception:
                new_pm = None

        if new_pm is None and self._raindrops is not None:
            try:
                new_pm = self._raindrops.new_pixmap
            except Exception:
                new_pm = None

        # Peel keeps its own state but participates in snap-to-new when
        # cancelling, so the compositor can finish on the correct frame.
        if new_pm is None and self._peel is not None:
            try:
                new_pm = self._peel.new_pixmap
            except Exception:
                new_pm = None

        if new_pm is None and self._blockspin is not None:
            try:
                new_pm = self._blockspin.new_pixmap
            except Exception:
                new_pm = None

        if new_pm is None and self._warp is not None:
            try:
                new_pm = self._warp.new_pixmap
            except Exception:
                new_pm = None

        if snap_to_new and new_pm is not None:
            self._base_pixmap = new_pm

        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._warp = None
        self._blockflip = None
        self._blockspin = None
        self._blinds = None
        self._diffuse = None
        self._raindrops = None
        self._peel = None

        # Ensure any blockspin textures are freed when a transition is
        # cancelled so we do not leak VRAM across many rotations.
        try:
            self._release_blockspin_textures()
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to release blockspin textures on cancel", exc_info=True)
        self.update()

    # ------------------------------------------------------------------
    # QOpenGLWidget hooks
    # ------------------------------------------------------------------

    def initializeGL(self) -> None:  # type: ignore[override]
        """Initialize GL state for the compositor.

        Sets up logging and prepares the internal pipeline container. In this
        phase the shader program and fullscreen quad geometry are created when
        OpenGL is available, but all drawing still goes through QPainter until
        later phases explicitly enable the shader path.
        """

        try:
            ctx = self.context()
            if ctx is not None:
                fmt = ctx.format()
                logger.info(
                    "[GL COMPOSITOR] Context initialized: version=%s.%s, swap=%s, interval=%s",
                    fmt.majorVersion(),
                    fmt.minorVersion(),
                    fmt.swapBehavior(),
                    fmt.swapInterval(),
                )

            # Prepare an empty pipeline container tied to this context and, if
            # possible, compile the shared card-flip shader program and quad
            # geometry. The pipeline remains disabled for rendering until
            # BlockSpin and other transitions are explicitly ported.
            self._gl_pipeline = _GLPipelineState()
            self._use_shaders = False
            self._gl_disabled_for_session = False
            self._init_gl_pipeline()
        except Exception:
            # If initialization fails at this stage, we simply log and keep
            # using the existing QPainter-only path. Higher levels can decide
            # to disable GL transitions for the session based on this signal
            # in later phases when shader-backed effects are wired.
            logger.debug("[GL COMPOSITOR] initializeGL failed", exc_info=True)

    def _init_gl_pipeline(self) -> None:
        if self._gl_disabled_for_session:
            return
        if gl is None:
            logger.info("[GL COMPOSITOR] PyOpenGL not available; disabling shader pipeline")
            self._gl_disabled_for_session = True
            return
        if self._gl_pipeline is None:
            self._gl_pipeline = _GLPipelineState()
        if self._gl_pipeline.initialized:
            return
        try:
            program = self._create_card_flip_program()
            self._gl_pipeline.basic_program = program
            # Cache uniform locations for the shared card-flip program.
            self._gl_pipeline.u_angle_loc = gl.glGetUniformLocation(program, "u_angle")
            self._gl_pipeline.u_aspect_loc = gl.glGetUniformLocation(program, "u_aspect")
            self._gl_pipeline.u_old_tex_loc = gl.glGetUniformLocation(program, "uOldTex")
            self._gl_pipeline.u_new_tex_loc = gl.glGetUniformLocation(program, "uNewTex")

            # Compile the Raindrops shader program when GL is available. On
            # failure we disable shader usage for this session so that all
            # shader-backed transitions fall back to the compositor's
            # QPainter-based paths (Group A → Group B).
            try:
                self._gl_pipeline.raindrops_program = self._create_raindrops_program()
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize raindrops shader program", exc_info=True)
                self._gl_pipeline.raindrops_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            try:
                self._gl_pipeline.warp_program = self._create_warp_program()
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize warp shader program", exc_info=True)
                self._gl_pipeline.warp_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Fullscreen quad with interleaved position (x, y) and UV (u, v).
            vertices = [
                -1.0,
                -1.0,
                0.0,
                0.0,
                1.0,
                -1.0,
                1.0,
                0.0,
                -1.0,
                1.0,
                0.0,
                1.0,
                1.0,
                1.0,
                1.0,
                1.0,
            ]

            # PyOpenGL_accelerate does not handle array.array directly; use a
            # ctypes float buffer so glBufferData sees a concrete pointer.
            vertex_data = (ctypes.c_float * len(vertices))(*vertices)

            vao = gl.glGenVertexArrays(1)
            vbo = gl.glGenBuffers(1)
            self._gl_pipeline.quad_vao = int(vao)
            self._gl_pipeline.quad_vbo = int(vbo)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._gl_pipeline.quad_vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER,
                ctypes.sizeof(vertex_data),
                vertex_data,
                gl.GL_STATIC_DRAW,
            )

            stride = 4 * 4  # 4 floats per vertex (x, y, u, v)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(0))
            gl.glEnableVertexAttribArray(1)
            gl.glVertexAttribPointer(1, 2, gl.GL_FLOAT, gl.GL_FALSE, stride, ctypes.c_void_p(8))

            gl.glBindVertexArray(0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)

            # Box mesh for 3D Block Spins: a thin rectangular prism with front,
            # back, and side faces. Each vertex stores position (x, y, z),
            # normal (nx, ny, nz) and UV (u, v).
            thickness = 0.05
            box_vertices = [
                # Front face (z = 0, normal +Z)
                -1.0, -1.0,  0.0,   0.0, 0.0, 1.0,   0.0, 0.0,
                 1.0, -1.0,  0.0,   0.0, 0.0, 1.0,   1.0, 0.0,
                 1.0,  1.0,  0.0,   0.0, 0.0, 1.0,   1.0, 1.0,

                -1.0, -1.0,  0.0,   0.0, 0.0, 1.0,   0.0, 0.0,
                 1.0,  1.0,  0.0,   0.0, 0.0, 1.0,   1.0, 1.0,
                -1.0,  1.0,  0.0,   0.0, 0.0, 1.0,   0.0, 1.0,

                # Back face (z = -thickness, normal -Z)
                -1.0, -1.0, -thickness,   0.0, 0.0, -1.0,   0.0, 0.0,
                 1.0, -1.0, -thickness,   0.0, 0.0, -1.0,   1.0, 0.0,
                 1.0,  1.0, -thickness,   0.0, 0.0, -1.0,   1.0, 1.0,

                -1.0, -1.0, -thickness,   0.0, 0.0, -1.0,   0.0, 0.0,
                 1.0,  1.0, -thickness,   0.0, 0.0, -1.0,   1.0, 1.0,
                -1.0,  1.0, -thickness,   0.0, 0.0, -1.0,   0.0, 1.0,

                # Left side (x = -1, normal -X)
                -1.0, -1.0,  0.0,       -1.0, 0.0, 0.0,   0.0, 0.0,
                -1.0, -1.0, -thickness, -1.0, 0.0, 0.0,   1.0, 0.0,
                -1.0,  1.0, -thickness, -1.0, 0.0, 0.0,   1.0, 1.0,

                -1.0, -1.0,  0.0,       -1.0, 0.0, 0.0,   0.0, 0.0,
                -1.0,  1.0, -thickness, -1.0, 0.0, 0.0,   1.0, 1.0,
                -1.0,  1.0,  0.0,       -1.0, 0.0, 0.0,   0.0, 1.0,

                # Right side (x = 1, normal +X)
                 1.0, -1.0,  0.0,        1.0, 0.0, 0.0,   1.0, 0.0,
                 1.0, -1.0, -thickness,  1.0, 0.0, 0.0,   0.0, 0.0,
                 1.0,  1.0, -thickness,  1.0, 0.0, 0.0,   0.0, 1.0,

                 1.0, -1.0,  0.0,        1.0, 0.0, 0.0,   1.0, 0.0,
                 1.0,  1.0, -thickness,  1.0, 0.0, 0.0,   0.0, 1.0,
                 1.0,  1.0,  0.0,        1.0, 0.0, 0.0,   1.0, 1.0,

                # Top face (y = 1, normal +Y)
                -1.0,  1.0,  0.0,       0.0, 1.0, 0.0,   0.0, 0.0,
                 1.0,  1.0,  0.0,       0.0, 1.0, 0.0,   1.0, 0.0,
                 1.0,  1.0, -thickness, 0.0, 1.0, 0.0,   1.0, 1.0,

                -1.0,  1.0,  0.0,       0.0, 1.0, 0.0,   0.0, 0.0,
                 1.0,  1.0, -thickness, 0.0, 1.0, 0.0,   1.0, 1.0,
                -1.0,  1.0, -thickness, 0.0, 1.0, 0.0,   0.0, 1.0,

                # Bottom face (y = -1, normal -Y)
                -1.0, -1.0,  0.0,       0.0, -1.0, 0.0,  0.0, 0.0,
                 1.0, -1.0,  0.0,       0.0, -1.0, 0.0,  1.0, 0.0,
                 1.0, -1.0, -thickness, 0.0, -1.0, 0.0,  1.0, 1.0,

                -1.0, -1.0,  0.0,       0.0, -1.0, 0.0,  0.0, 0.0,
                 1.0, -1.0, -thickness, 0.0, -1.0, 0.0,  1.0, 1.0,
                -1.0, -1.0, -thickness, 0.0, -1.0, 0.0,  0.0, 1.0,
            ]

            box_vertex_data = (ctypes.c_float * len(box_vertices))(*box_vertices)
            box_vao = gl.glGenVertexArrays(1)
            box_vbo = gl.glGenBuffers(1)
            self._gl_pipeline.box_vao = int(box_vao)
            self._gl_pipeline.box_vbo = int(box_vbo)
            self._gl_pipeline.box_vertex_count = len(box_vertices) // 8

            gl.glBindVertexArray(self._gl_pipeline.box_vao)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, self._gl_pipeline.box_vbo)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER,
                ctypes.sizeof(box_vertex_data),
                box_vertex_data,
                gl.GL_STATIC_DRAW,
            )

            stride_box = 8 * 4  # 8 floats per vertex (x, y, z, nx, ny, nz, u, v)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 3, gl.GL_FLOAT, gl.GL_FALSE, stride_box, ctypes.c_void_p(0))
            gl.glEnableVertexAttribArray(1)
            gl.glVertexAttribPointer(1, 3, gl.GL_FLOAT, gl.GL_FALSE, stride_box, ctypes.c_void_p(12))
            gl.glEnableVertexAttribArray(2)
            gl.glVertexAttribPointer(2, 2, gl.GL_FLOAT, gl.GL_FALSE, stride_box, ctypes.c_void_p(24))

            gl.glBindVertexArray(0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)

            self._gl_pipeline.initialized = True
            logger.info("[GL COMPOSITOR] Shader pipeline initialized (card flip)")
        except Exception:
            logger.debug("[GL SHADER] Failed to initialize shader pipeline", exc_info=True)
            self._gl_disabled_for_session = True
            self._use_shaders = False

    def _cleanup_gl_pipeline(self) -> None:
        if gl is None or self._gl_pipeline is None:
            return

        try:
            is_valid = getattr(self, "isValid", None)
            if callable(is_valid) and not is_valid():
                self._release_blockspin_textures()
                self._gl_pipeline.basic_program = 0
                self._gl_pipeline.raindrops_program = 0
                self._gl_pipeline.warp_program = 0
                self._gl_pipeline.claws_program = 0
                self._gl_pipeline.quad_vao = 0
                self._gl_pipeline.quad_vbo = 0
                self._gl_pipeline.box_vao = 0
                self._gl_pipeline.box_vbo = 0
                self._gl_pipeline.box_vertex_count = 0
                self._gl_pipeline.initialized = False
                return
        except Exception:
            pass

        try:
            self.makeCurrent()
        except Exception:
            self._release_blockspin_textures()
            self._gl_pipeline.basic_program = 0
            self._gl_pipeline.raindrops_program = 0
            self._gl_pipeline.warp_program = 0
            self._gl_pipeline.claws_program = 0
            self._gl_pipeline.quad_vao = 0
            self._gl_pipeline.quad_vbo = 0
            self._gl_pipeline.box_vao = 0
            self._gl_pipeline.box_vbo = 0
            self._gl_pipeline.box_vertex_count = 0
            self._gl_pipeline.initialized = False
            return

        try:
            self._release_blockspin_textures()

            try:
                if self._gl_pipeline.basic_program:
                    gl.glDeleteProgram(int(self._gl_pipeline.basic_program))
                if getattr(self._gl_pipeline, "raindrops_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.raindrops_program))
                if getattr(self._gl_pipeline, "warp_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.warp_program))
                if getattr(self._gl_pipeline, "claws_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.claws_program))
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to delete shader program", exc_info=True)

            try:
                if self._gl_pipeline.quad_vbo:
                    buf = (ctypes.c_uint * 1)(int(self._gl_pipeline.quad_vbo))
                    gl.glDeleteBuffers(1, buf)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to delete VBO %s", self._gl_pipeline.quad_vbo, exc_info=True)

            try:
                if self._gl_pipeline.quad_vao:
                    arr = (ctypes.c_uint * 1)(int(self._gl_pipeline.quad_vao))
                    gl.glDeleteVertexArrays(1, arr)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to delete VAO %s", self._gl_pipeline.quad_vao, exc_info=True)

            try:
                if self._gl_pipeline.box_vbo:
                    buf = (ctypes.c_uint * 1)(int(self._gl_pipeline.box_vbo))
                    gl.glDeleteBuffers(1, buf)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to delete VBO %s", self._gl_pipeline.box_vbo, exc_info=True)

            try:
                if self._gl_pipeline.box_vao:
                    arr = (ctypes.c_uint * 1)(int(self._gl_pipeline.box_vao))
                    gl.glDeleteVertexArrays(1, arr)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to delete VAO %s", self._gl_pipeline.box_vao, exc_info=True)

            self._gl_pipeline.basic_program = 0
            self._gl_pipeline.raindrops_program = 0
            self._gl_pipeline.warp_program = 0
            self._gl_pipeline.claws_program = 0
            self._gl_pipeline.quad_vbo = 0
            self._gl_pipeline.quad_vao = 0
            self._gl_pipeline.box_vbo = 0
            self._gl_pipeline.box_vao = 0
            self._gl_pipeline.box_vertex_count = 0
            self._gl_pipeline.initialized = False
        finally:
            try:
                self.doneCurrent()
            except Exception:
                pass

    def cleanup(self) -> None:
        try:
            self._cleanup_gl_pipeline()
        except Exception:
            logger.debug("[GL COMPOSITOR] cleanup() failed", exc_info=True)

    def _create_card_flip_program(self) -> int:
        """Compile and link the basic textured card-flip shader program."""

        if gl is None:
            raise RuntimeError("OpenGL context not available for shader program")

        # 3D card-flip program: the vertex shader treats the image pair as a
        # thin 3D slab (box) in world space. Geometry is provided by the
        # dedicated box mesh VBO/VAO created in _init_gl_pipeline.
        vs_source = """#version 410 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
layout(location = 2) in vec2 aUv;

out vec2 vUv;
out vec3 vNormal;
out vec3 vViewDir;
flat out int vFaceKind;  // 1=front, 2=back, 3=side

uniform float u_angle;
uniform float u_aspect;

void main() {
    vUv = aUv;

    // Classify faces in object space so texture mapping is stable regardless
    // of the current rotation.
    int face = 0;
    if (abs(aNormal.z) > 0.5) {
        face = (aNormal.z > 0.0) ? 1 : 2;
    } else {
        face = 3;
    }
    vFaceKind = face;

    float ca = cos(u_angle);
    float sa = sin(u_angle);

    // Pure spin around Y; no X tilt so the top face does not open up.
    mat3 rotY = mat3(
        ca,  0.0, sa,
        0.0, 1.0, 0.0,
       -sa,  0.0, ca
    );

    vec3 pos = rotY * aPos;
    vec3 normal = normalize(rotY * aNormal);

    // Orthographic-style projection: treat the rotated slab as sitting in
    // clip space so that when it faces the camera it fills the viewport
    // similarly to the old 2D card, without extreme perspective stretching.
    vNormal = normal;
    vViewDir = vec3(0.0, 0.0, 1.0);

    float scale = 1.0;
    // Use -pos.z so the face nearest the camera always wins the depth test:
    // at angle 0 the front (old image) is in front, at angle pi the back
    // (new image) is in front. This avoids sudden flips when the CPU swaps
    // the base pixmap at transition start/end.
    float z_clip = -pos.z * 0.5;  // small but non-zero depth for proper occlusion
    gl_Position = vec4(pos.x * scale, pos.y * scale, z_clip, 1.0);
}
"""

        fs_source = """#version 410 core
in vec2 vUv;
in vec3 vNormal;
in vec3 vViewDir;
flat in int vFaceKind;  // 1=front, 2=back, 3=side
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_angle;
uniform float u_aspect;

void main() {
    // Qt images are stored top-to-bottom, whereas OpenGL's texture
    // coordinates assume (0,0) at the bottom-left. Flip the V coordinate so
    // the sampled image appears upright.
    vec2 uv_front = vec2(vUv.x, 1.0 - vUv.y);
    vec2 uv_back  = vec2(1.0 - vUv.x, 1.0 - vUv.y); // horizontally flipped

    vec3 n = normalize(vNormal);
    vec3 viewDir = normalize(vViewDir);
    vec3 lightDir = normalize(vec3(-0.15, 0.35, 0.9));

    // Normalised spin progress 0..1 from angle 0..pi and a smooth
    // highlight envelope so specular accents fade in near the middle of the
    // spin and disappear at the endpoints. This avoids sudden white bands
    // the instant the transition starts or completes.
    float t = clamp(u_angle / 3.14159265, 0.0, 1.0);
    // Start the highlight a bit earlier but still keep it fully suppressed
    // right at the endpoints.
    float highlightPhase = smoothstep(0.16, 0.30, t) * smoothstep(0.16, 0.30, 1.0 - t);

    vec3 color;

    if (vFaceKind == 3) {
        // Side faces: darker glass core with a narrow, moving specular band
        // along the thickness so the edge reads as glossy without turning
        // into a solid white column. The band position is driven by the
        // global rotation angle so it appears to slide across the edge over
        // the course of the spin.
        vec3 base = vec3(0.06);
        vec3 halfVec = normalize(lightDir + viewDir);
        float ndh = max(dot(n, halfVec), 0.0);

        // Side faces use vUv.x in [0,1] to represent thickness from the
        // front edge to the back edge. Move the highlight band centre from
        // near one side to the other over the spin.
        float bandCenter = mix(0.2, 0.8, t);
        float bandHalfWidth = 0.028;  // ~30% wider band for a slightly thicker line
        float d = abs(vUv.x - bandCenter);
        float bandMask = 1.0 - smoothstep(bandHalfWidth, bandHalfWidth * 1.4, d);

        float spec = pow(ndh, 18.0) * bandMask * highlightPhase;
        // Allow the peak to approach pure white while remaining clamped so
        // it never explodes beyond the side face.
        float edgeSpec = min(1.0, 1.05 * spec);
        color = base + vec3(edgeSpec);
    } else {
        // Front/back faces: map old/new images directly to their respective
        // geometry so the card ends exactly on the new image without
        // mirroring or late flips.
        if (vFaceKind == 1) {
            color = texture(uOldTex, uv_front).rgb;
        } else {
            color = texture(uNewTex, uv_back).rgb;
        }

        // Subtle vertical rim highlight near the long edges so the slab
        // reads as a solid object while keeping the face image essentially
        // unshaded. Gate this with the same highlightPhase so we do not get
        // bright rims on the very first/last frames.
        float xN = vUv.x * 2.0 - 1.0;
        float rim = smoothstep(0.975, 0.995, abs(xN));  // even narrower rim
        if (rim > 0.0 && highlightPhase > 0.0) {
            vec3 halfVec = normalize(lightDir + viewDir);
            float ndh = max(dot(n, halfVec), 0.0);
            float spec = pow(ndh, 18.0) * highlightPhase;
            vec3 rimColor = color + vec3(spec * 0.45);  // dimmer, reduces bleed
            color = mix(color, rimColor, rim);
        }
    }

    FragColor = vec4(color, 1.0);
}
"""

        vert = self._compile_shader(vs_source, gl.GL_VERTEX_SHADER)
        try:
            frag = self._compile_shader(fs_source, gl.GL_FRAGMENT_SHADER)
        except Exception:
            gl.glDeleteShader(vert)
            raise

        try:
            program = gl.glCreateProgram()
            gl.glAttachShader(program, vert)
            gl.glAttachShader(program, frag)
            gl.glLinkProgram(program)
            status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
            if status != gl.GL_TRUE:
                log = gl.glGetProgramInfoLog(program)
                logger.debug("[GL SHADER] Failed to link card-flip program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link card-flip program: {log!r}")
        finally:
            gl.glDeleteShader(vert)
            gl.glDeleteShader(frag)

        return int(program)

    def _create_warp_program(self) -> int:
        """Compile and link the shader program used for Warp Dissolve."""

        if gl is None:
            raise RuntimeError("OpenGL context not available for shader program")

        vs_source = """#version 410 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;

out vec2 vUv;

void main() {
    vUv = aUv;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

        fs_source = """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_resolution;

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 newColor = texture(uNewTex, uv);
    vec4 oldColor = texture(uOldTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Horizontal band-based warp similar to the QPainter implementation.
    float y = uv.y;
    float base = y * 6.28318530718; // 2*pi
    float wave = sin(base + t * 6.0) * cos(base * 1.3);

    // Match CPU amplitude of ~3% of the width, fading as t -> 1.
    float offsetNorm = 0.03 * (1.0 - t);
    vec2 warpedUv = uv;
    warpedUv.x += wave * offsetNorm;
    warpedUv.x = clamp(warpedUv.x, 0.0, 1.0);

    vec4 warpedOld = texture(uOldTex, warpedUv);

    // Old image fades slightly faster than nominal timeline.
    float fade = max(0.0, 1.0 - t * 1.25);

    vec4 color = mix(newColor, warpedOld, fade);

    FragColor = color;
}
"""

        vert = self._compile_shader(vs_source, gl.GL_VERTEX_SHADER)
        try:
            frag = self._compile_shader(fs_source, gl.GL_FRAGMENT_SHADER)
        except Exception:
            gl.glDeleteShader(vert)
            raise

        try:
            program = gl.glCreateProgram()
            gl.glAttachShader(program, vert)
            gl.glAttachShader(program, frag)
            gl.glLinkProgram(program)
            status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
            if status != gl.GL_TRUE:
                log = gl.glGetProgramInfoLog(program)
                logger.debug("[GL SHADER] Failed to link warp program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link warp program: {log!r}")
        finally:
            gl.glDeleteShader(vert)
            gl.glDeleteShader(frag)

        return int(program)

    def _create_raindrops_program(self) -> int:
        """Compile and link the shader program used for Raindrops."""

        if gl is None:
            raise RuntimeError("OpenGL context not available for shader program")

        vs_source = """#version 410 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;

out vec2 vUv;

void main() {
    vUv = aUv;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

        fs_source = """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_resolution;

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Normalised coordinates with aspect compensation so the ripple is
    // circular even on non-square render targets.
    float aspect = u_resolution.x / max(u_resolution.y, 1.0);
    vec2 centered = uv - vec2(0.5, 0.5);
    centered.x *= aspect;
    float r = length(centered);

    float maxR = 0.9;
    float rNorm = clamp(r / maxR, 0.0, 1.0);
    float front = t;

    // Radial wave travelling outwards from the centre. Lower spatial and
    // temporal frequency to avoid judder.
    float wave = 0.0;
    if (rNorm < front + 0.25) {
        float spatialFreq = 18.0;
        float temporalFreq = 4.0;
        float phase = spatialFreq * (rNorm - front) - temporalFreq * t;
        float attenuation = exp(-6.0 * abs(rNorm - front));
        wave = 0.012 * sin(phase) * attenuation;
    }

    vec2 dir = (r > 1e-5) ? (centered / r) : vec2(0.0, 0.0);

    // Displace the sampling position along the radial direction to create
    // a water-like refraction of the old image.
    vec2 rippleUv = uv + dir * wave;
    rippleUv = clamp(rippleUv, vec2(0.0), vec2(1.0));
    vec4 rippleOld = texture(uOldTex, rippleUv);

    vec4 base = mix(oldColor, rippleOld, 0.7);

    // Reveal the NEW image from the centre outward. Points that the wave
    // front has already passed transition to the new image, and a gentle
    // global fade near the end guarantees we finish fully on the new frame.
    float localMix = smoothstep(0.0, 0.15, front - rNorm);
    float globalMix = smoothstep(0.9, 1.0, t);
    float newMix = clamp(max(localMix, globalMix), 0.0, 1.0);

    vec4 mixed = mix(base, newColor, newMix);

    // Subtle highlight on the main ring to read as a bright water crest.
    float ringMask = smoothstep(front - 0.03, front, rNorm) *
                     (1.0 - smoothstep(front, front + 0.03, rNorm));
    mixed.rgb += vec3(0.08) * ringMask;

    FragColor = mixed;
}
"""

        vert = self._compile_shader(vs_source, gl.GL_VERTEX_SHADER)
        try:
            frag = self._compile_shader(fs_source, gl.GL_FRAGMENT_SHADER)
        except Exception:
            gl.glDeleteShader(vert)
            raise

        try:
            program = gl.glCreateProgram()
            gl.glAttachShader(program, vert)
            gl.glAttachShader(program, frag)
            gl.glLinkProgram(program)
            status = gl.glGetProgramiv(program, gl.GL_LINK_STATUS)
            if status != gl.GL_TRUE:
                log = gl.glGetProgramInfoLog(program)
                logger.debug("[GL SHADER] Failed to link raindrops program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link raindrops program: {log!r}")
        finally:
            gl.glDeleteShader(vert)
            gl.glDeleteShader(frag)

        return int(program)

    def _compile_shader(self, source: str, shader_type: int) -> int:
        """Compile a single GLSL shader and return its id."""

        if gl is None:
            raise RuntimeError("OpenGL context not available for shader compilation")

        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        status = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        if status != gl.GL_TRUE:
            log = gl.glGetShaderInfoLog(shader)
            logger.debug("[GL SHADER] Failed to compile shader: %r", log)
            gl.glDeleteShader(shader)
            raise RuntimeError(f"Failed to compile shader: {log!r}")
        return int(shader)

    # ------------------------------------------------------------------
    # Shader helpers for Block Spins
    # ------------------------------------------------------------------

    def _can_use_blockspin_shader(self) -> bool:
        if self._gl_disabled_for_session or gl is None:
            return False
        if self._gl_pipeline is None or not self._gl_pipeline.initialized:
            return False
        if self._blockspin is None:
            return False
        return True

    def _can_use_warp_shader(self) -> bool:
        if self._gl_disabled_for_session or gl is None:
            return False
        if self._gl_pipeline is None or not self._gl_pipeline.initialized:
            return False
        if self._warp is None:
            return False
        if not getattr(self._gl_pipeline, "warp_program", 0):
            return False
        return True

    def _can_use_raindrops_shader(self) -> bool:
        if self._gl_disabled_for_session or gl is None:
            return False
        if self._gl_pipeline is None or not self._gl_pipeline.initialized:
            return False
        if self._raindrops is None:
            return False
        if not self._gl_pipeline.raindrops_program:
            return False
        return True

    def _upload_texture_from_pixmap(self, pixmap: QPixmap) -> int:
        """Upload a QPixmap as a GL texture and return its id.

        Returns 0 on failure. Caller is responsible for deleting the texture
        when no longer needed.
        """

        if gl is None or pixmap is None or pixmap.isNull():
            return 0

        # Use ARGB32 + GL_BGRA so channel ordering matches what the GPU
        # expects; this mirrors common Qt+OpenGL interop patterns and avoids
        # colour-swizzling artefacts.
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
        w = image.width()
        h = image.height()
        if w <= 0 or h <= 0:
            return 0

        try:
            ptr = image.constBits()
            # Support both sip.voidptr (older PySide6) and memoryview.
            if hasattr(ptr, "setsize"):
                ptr.setsize(image.sizeInBytes())
                data = bytes(ptr)
            else:
                data = ptr.tobytes()
        except Exception:
            logger.debug("[GL SHADER] Failed to access image bits for texture upload", exc_info=True)
            return 0

        tex = gl.glGenTextures(1)
        tex_id = int(tex)
        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        try:
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D,
                0,
                gl.GL_RGBA8,
                w,
                h,
                0,
                gl.GL_BGRA,
                gl.GL_UNSIGNED_BYTE,
                data,
            )
        except Exception:
            logger.debug("[GL SHADER] Texture upload failed", exc_info=True)
            try:
                gl.glDeleteTextures(int(tex_id))
            except Exception:
                pass
            return 0
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

        return tex_id

    def _release_blockspin_textures(self) -> None:
        if gl is None or self._gl_pipeline is None:
            return
        for tex_id in (self._gl_pipeline.old_tex_id, self._gl_pipeline.new_tex_id):
            if tex_id:
                try:
                    gl.glDeleteTextures(int(tex_id))
                except Exception:
                    logger.debug("[GL SHADER] Failed to delete texture %s", tex_id, exc_info=True)
        self._gl_pipeline.old_tex_id = 0
        self._gl_pipeline.new_tex_id = 0

    def _prepare_pair_textures(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        if self._gl_pipeline is None:
            return False
        if old_pixmap is None or old_pixmap.isNull() or new_pixmap is None or new_pixmap.isNull():
            return False

        self._release_blockspin_textures()

        try:
            self._gl_pipeline.old_tex_id = self._upload_texture_from_pixmap(old_pixmap)
            self._gl_pipeline.new_tex_id = self._upload_texture_from_pixmap(new_pixmap)
        except Exception:
            logger.debug("[GL SHADER] Failed to upload transition textures", exc_info=True)
            self._release_blockspin_textures()
            self._gl_disabled_for_session = True
            self._use_shaders = False
            return False

        if not self._gl_pipeline.old_tex_id or not self._gl_pipeline.new_tex_id:
            self._release_blockspin_textures()
            return False
        return True

    def _prepare_blockspin_textures(self) -> bool:
        if not self._can_use_blockspin_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._blockspin is None:
            return False
        st = self._blockspin
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _get_viewport_size(self) -> tuple[int, int]:
        """Return the framebuffer viewport size in physical pixels."""

        try:
            dpr = float(self.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        w = max(1, int(round(self.width() * dpr)))
        h = max(1, int(round(self.height() * dpr)))
        return w, h

    def _paint_blockspin_shader(self, target: QRect) -> None:
        if not self._can_use_blockspin_shader() or self._gl_pipeline is None or self._blockspin is None:
            return
        if not self._prepare_blockspin_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        w = max(1, target.width())
        h = max(1, target.height())

        p = max(0.0, min(1.0, float(self._blockspin.progress)))
        # Keep the slab perfectly front-facing for the first few percent of
        # the timeline and perfectly back-facing for the last few percent so
        # there is no visible jump at the moment the transition starts or
        # completes. The actual spin is compressed into the middle of the
        # interval.
        if p <= 0.03:
            spin = 0.0
        elif p >= 0.97:
            spin = 1.0
        else:
            spin = (p - 0.03) / 0.94
        angle = math.pi * spin
        aspect = float(w) / float(h)

        gl.glViewport(0, 0, vp_w, vp_h)
        # Enable depth testing so the front face of the slab properly occludes
        # the back face; this avoids seeing both images blended through each
        # other mid-spin.
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_TRUE)

        # Clear to a dark neutral background so the spinning slab appears over
        # a void rather than the next image, while still avoiding
        # "mostly black" frames in automated tests.
        gl.glClearColor(0.08, 0.08, 0.08, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        # Then draw the rotating slab (box) on top using the card-flip program.
        gl.glUseProgram(self._gl_pipeline.basic_program)
        try:
            if self._gl_pipeline.u_angle_loc != -1:
                gl.glUniform1f(self._gl_pipeline.u_angle_loc, float(angle))
            if self._gl_pipeline.u_aspect_loc != -1:
                gl.glUniform1f(self._gl_pipeline.u_aspect_loc, float(aspect))

            # Bind textures.
            if self._gl_pipeline.u_old_tex_loc != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.u_old_tex_loc, 0)
            if self._gl_pipeline.u_new_tex_loc != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.u_new_tex_loc, 1)

            # Prefer the dedicated box mesh for a true 3D slab; fall back to
            # the fullscreen quad if the box geometry was not created.
            if getattr(self._gl_pipeline, "box_vao", 0) and getattr(self._gl_pipeline, "box_vertex_count", 0) > 0:
                gl.glBindVertexArray(self._gl_pipeline.box_vao)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, int(self._gl_pipeline.box_vertex_count))
                gl.glBindVertexArray(0)
            else:
                gl.glBindVertexArray(self._gl_pipeline.quad_vao)
                gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
                gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)
            gl.glDisable(gl.GL_DEPTH_TEST)

    def _paint_warp_shader(self, target: QRect) -> None:
        if not self._can_use_warp_shader() or self._gl_pipeline is None or self._warp is None:
            return
        st = self._warp
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_pair_textures(st.old_pixmap, st.new_pixmap):
            return

        vp_w, vp_h = self._get_viewport_size()

        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.warp_program)
        try:
            loc_progress = gl.glGetUniformLocation(self._gl_pipeline.warp_program, "u_progress")
            if loc_progress != -1:
                gl.glUniform1f(loc_progress, float(p))

            loc_res = gl.glGetUniformLocation(self._gl_pipeline.warp_program, "u_resolution")
            if loc_res != -1:
                gl.glUniform2f(loc_res, float(vp_w), float(vp_h))

            loc_old = gl.glGetUniformLocation(self._gl_pipeline.warp_program, "uOldTex")
            loc_new = gl.glGetUniformLocation(self._gl_pipeline.warp_program, "uNewTex")

            if loc_old != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(loc_old, 0)
            if loc_new != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(loc_new, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_raindrops_shader(self, target: QRect) -> None:
        if not self._can_use_raindrops_shader() or self._gl_pipeline is None or self._raindrops is None:
            return
        st = self._raindrops
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_pair_textures(st.old_pixmap, st.new_pixmap):
            # Texture upload helper currently uses the shared old/new texture
            # slots; on failure we simply skip the shader path.
            return

        vp_w, vp_h = self._get_viewport_size()

        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.raindrops_program)
        try:
            # Per-frame uniforms. Locations are queried dynamically to keep the
            # pipeline dataclass simple while we iterate on the shader.
            loc_progress = gl.glGetUniformLocation(self._gl_pipeline.raindrops_program, "u_progress")
            if loc_progress != -1:
                gl.glUniform1f(loc_progress, float(p))

            loc_res = gl.glGetUniformLocation(self._gl_pipeline.raindrops_program, "u_resolution")
            if loc_res != -1:
                gl.glUniform2f(loc_res, float(vp_w), float(vp_h))

            loc_old = gl.glGetUniformLocation(self._gl_pipeline.raindrops_program, "uOldTex")
            loc_new = gl.glGetUniformLocation(self._gl_pipeline.raindrops_program, "uNewTex")

            if loc_old != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(loc_old, 0)
            if loc_new != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(loc_new, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def paintGL(self) -> None:  # type: ignore[override]
        target = self.rect()

        # Prefer the shader path for Block Spins when available. On any failure
        # we log and fall back to the existing QPainter implementation.
        if self._blockspin is not None and self._can_use_blockspin_shader():
            try:
                if self._prepare_blockspin_textures():
                    self._paint_blockspin_shader(target)
                    return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader blockspin path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug("[GL COMPOSITOR] Shader blockspin path failed; disabling shader pipeline", exc_info=True)
                self._gl_disabled_for_session = True
                self._use_shaders = False

        # Raindrops shader path: when enabled and the GLSL pipeline is
        # available, draw the droplet field entirely in GLSL. On failure we
        # disable shader usage for the session and fall back to the
        # compositor's existing QPainter-based transitions.
        if self._raindrops is not None and self._can_use_raindrops_shader():
            try:
                self._paint_raindrops_shader(target)
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader raindrops path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader raindrops path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        if self._warp is not None and self._can_use_warp_shader():
            try:
                self._paint_warp_shader(target)
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader warp path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader warp path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            # target recomputed in case geometry changed after shader branch.
            target = self.rect()

            # If a peel transition is active, always draw the new image as the
            # base frame and overlay directional, strip-based remnants of the
            # old image that shrink and drift away over time.
            if self._peel is not None:
                st = self._peel
                w = target.width()
                h = target.height()
                t = max(0.0, min(1.0, st.progress))

                # Draw new image fully as the background.
                if st.new_pixmap and not st.new_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)

                if not st.old_pixmap or st.old_pixmap.isNull():
                    return

                strips = max(1, int(st.strips))
                # Later strips begin peeling slightly after earlier ones so the
                # overall effect feels like sequential sheets of paper rather
                # than a rigid shutter.
                delay_per_strip = 0.7 / max(1, strips - 1) if strips > 1 else 0.0

                for i in range(strips):
                    if st.direction in (SlideDirection.LEFT, SlideDirection.RIGHT):
                        # Vertical strips for horizontal peel.
                        strip_w = max(1, w // strips)
                        x0 = i * strip_w
                        if i == strips - 1:
                            strip_w = max(1, w - x0)
                        base_rect = QRect(x0, 0, strip_w, h)
                    else:
                        # Horizontal strips for vertical peel.
                        strip_h = max(1, h // strips)
                        y0 = i * strip_h
                        if i == strips - 1:
                            strip_h = max(1, h - y0)
                        base_rect = QRect(0, y0, w, strip_h)

                    # Per-strip local progress: 0 = still in place, 1 = fully
                    # peeled off-screen.
                    start = i * delay_per_strip
                    if t <= start:
                        local = 0.0
                    else:
                        local = (t - start) / max(0.0001, 1.0 - start)
                        if local >= 1.0:
                            # This strip has completely peeled away.
                            continue

                    # Compute translation offset for this strip.
                    dx = 0
                    dy = 0
                    if local > 0.0:
                        if st.direction in (SlideDirection.LEFT, SlideDirection.RIGHT):
                            sign = 1 if st.direction == SlideDirection.RIGHT else -1
                            max_offset = w + base_rect.width()
                            dx = int(sign * max_offset * local)
                        else:
                            sign = 1 if st.direction == SlideDirection.DOWN else -1
                            max_offset = h + base_rect.height()
                            dy = int(sign * max_offset * local)

                    # Destination rect of the moving strip on screen.
                    rect = base_rect.translated(dx, dy)
                    if not rect.intersects(target):
                        continue

                    painter.save()
                    painter.setClipRect(rect)
                    painter.setOpacity(1.0)
                    try:
                        # Translate the painter so the strip carries its
                        # original content with it rather than sampling new
                        # columns/rows of the old image.
                        painter.translate(dx, dy)
                        painter.drawPixmap(target, st.old_pixmap)
                    except Exception:
                        painter.restore()
                        continue
                    painter.restore()
                return

            # If a warp dissolve is active, draw the new image fully and then
            # overlay horizontally sliced bands of the old image that jitter
            # and fade out over time.
            if self._warp is not None:
                st = self._warp
                w = target.width()
                h = target.height()
                t = max(0.0, min(1.0, st.progress))

                # Draw new image fully as the stable background.
                if st.new_pixmap and not st.new_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                else:
                    painter.fillRect(target, Qt.GlobalColor.black)

                if not st.old_pixmap or st.old_pixmap.isNull():
                    return

                # Band height and warp amplitude tuned for 1080p–4K. Smaller
                # bands and modest amplitude keep the effect gentle.
                band_h = max(4, h // 80)
                amp = max(4.0, w * 0.03)

                # Old image fades out slightly faster than the nominal
                # timeline so we don't see lingering noise at the end.
                fade = max(0.0, 1.0 - t * 1.25)
                if fade <= 0.0:
                    return

                y = 0
                while y < h:
                    band_height = band_h if y + band_h <= h else h - y
                    band_rect = QRect(0, y, w, band_height)

                    # Pseudo-random but deterministic phase per band.
                    base = (y / float(max(1, h))) * math.pi * 2.0
                    wave = math.sin(base + t * 6.0) * math.cos(base * 1.3)
                    offset_x = int(wave * amp * (1.0 - t))

                    if offset_x != 0:
                        shifted = band_rect.translated(offset_x, 0)
                    else:
                        shifted = band_rect

                    painter.save()
                    painter.setClipRect(band_rect)
                    painter.setOpacity(fade)
                    try:
                        painter.drawPixmap(shifted, st.old_pixmap)
                    except Exception:
                        painter.restore()
                        break
                    painter.restore()

                    y += band_height
                return

            # If a block spin is active and the GLSL path is unavailable, fall
            # back to a simple compositor-side crossfade between the old and
            # new images. This keeps the Group A (shader) failure behaviour
            # visually safe and distinct from the GLSL 3D spin while still
            # exercising the compositor surface.
            if self._blockspin is not None:
                st = self._blockspin
                if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
                    return

                t = max(0.0, min(1.0, st.progress))

                if t <= 0.0:
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.old_pixmap)
                    return
                if t >= 1.0:
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                    return

                painter.setOpacity(1.0)
                painter.drawPixmap(target, st.old_pixmap)
                painter.setOpacity(t)
                painter.drawPixmap(target, st.new_pixmap)
                return

            # If a block flip is active, draw old fully and new clipped to the
            # aggregated reveal region.
            if self._blockflip is not None:
                st = self._blockflip
                # Draw old image fully.
                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.old_pixmap)

                # Clip and draw new image inside the reveal region.
                if st.new_pixmap and not st.new_pixmap.isNull() and st.region is not None and not st.region.isEmpty():
                    painter.save()
                    painter.setClipRegion(st.region)
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                    painter.restore()
                return

            # If a blinds transition is active, draw old fully and new clipped
            # to the blinds reveal region.
            if self._blinds is not None:
                st = self._blinds
                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.old_pixmap)

                if st.new_pixmap and not st.new_pixmap.isNull() and st.region is not None and not st.region.isEmpty():
                    painter.save()
                    painter.setClipRegion(st.region)
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                    painter.restore()
                return

            if self._diffuse is not None:
                st = self._diffuse
                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.old_pixmap)

                if st.new_pixmap and not st.new_pixmap.isNull() and st.region is not None and not st.region.isEmpty():
                    painter.save()
                    painter.setClipRegion(st.region)
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                    painter.restore()
                return

            # If a wipe is active, draw old fully and new clipped to the wipe region.
            if self._wipe is not None:
                st = self._wipe
                w = target.width()
                h = target.height()
                t = max(0.0, min(1.0, st.progress))

                # Draw old image fully.
                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.old_pixmap)

                # Clip and draw new according to wipe direction.
                if st.new_pixmap and not st.new_pixmap.isNull():
                    region = _compute_wipe_region(st.direction, w, h, t)
                    if not region.isEmpty():
                        painter.save()
                        painter.setClipRegion(region)
                        painter.setOpacity(1.0)
                        painter.drawPixmap(target, st.new_pixmap)
                        painter.restore()
                return

            # If a slide is active, draw both images at interpolated positions.
            if self._slide is not None:
                st = self._slide
                w = target.width()
                h = target.height()

                t = max(0.0, min(1.0, st.progress))
                old_pos = QPoint(
                    int(st.old_start.x() + (st.old_end.x() - st.old_start.x()) * t),
                    int(st.old_start.y() + (st.old_end.y() - st.old_start.y()) * t),
                )
                new_pos = QPoint(
                    int(st.new_start.x() + (st.new_end.x() - st.new_start.x()) * t),
                    int(st.new_start.y() + (st.new_end.y() - st.new_start.y()) * t),
                )

                if st.old_pixmap and not st.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    old_rect = QRect(old_pos.x(), old_pos.y(), w, h)
                    painter.drawPixmap(old_rect, st.old_pixmap)
                if st.new_pixmap and not st.new_pixmap.isNull():
                    painter.setOpacity(1.0)
                    new_rect = QRect(new_pos.x(), new_pos.y(), w, h)
                    painter.drawPixmap(new_rect, st.new_pixmap)
                return

            # If a crossfade is active, draw old + new with interpolated opacity.
            if self._crossfade is not None:
                cf = self._crossfade
                if cf.old_pixmap and not cf.old_pixmap.isNull():
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, cf.old_pixmap)
                if cf.new_pixmap and not cf.new_pixmap.isNull():
                    painter.setOpacity(cf.progress)
                    painter.drawPixmap(target, cf.new_pixmap)
                return

            # No active transition -> draw base pixmap if present.
            if self._base_pixmap is not None and not self._base_pixmap.isNull():
                painter.setOpacity(1.0)
                painter.drawPixmap(target, self._base_pixmap)
            else:
                # As a last resort, fill black.
                painter.fillRect(target, Qt.GlobalColor.black)
        finally:
            painter.end()
