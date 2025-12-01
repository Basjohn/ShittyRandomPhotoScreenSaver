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
from PySide6.QtGui import QPainter, QPixmap, QRegion, QImage, QColor
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger, is_perf_metrics_enabled
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
class ShuffleShaderState:
    """State for a shader-driven Shuffle transition.

    This models a fullscreen Shuffle mask rendered in GLSL. The compositor
    drives the effect on a single quad using a logical block grid and a
    per-block jitter field; controllers provide the old/new pixmaps,
    grid dimensions and edge direction.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    cols: int
    rows: int
    edge: str
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
class ShootingStarsState:
    """State for a shader-driven Shooting Stars (claws) transition.

    This models a field of streak-like "shooting stars" rendered entirely in
    GLSL. The compositor draws the effect using a fullscreen quad shader;
    controllers only provide the old/new pixmaps and timeline progress.
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
    shuffle_program: int = 0

    # Textures for the current pair of images being blended/transitioned.
    old_tex_id: int = 0
    new_tex_id: int = 0

    # Cached uniform locations for the basic card-flip program.
    u_angle_loc: int = -1
    u_aspect_loc: int = -1
    u_old_tex_loc: int = -1
    u_new_tex_loc: int = -1
    u_spec_dir_loc: int = -1
    u_axis_mode_loc: int = -1
    # Per-tile placement for the 3D Block Spins slab when rendering a grid of
    # cards. These are optional and default to a single full-frame slab when
    # unset.
    u_block_rect_loc: int = -1
    u_block_uv_rect_loc: int = -1

    # Cached uniform locations for the Ripple (raindrops) shader program.
    raindrops_u_progress: int = -1
    raindrops_u_resolution: int = -1
    raindrops_u_old_tex: int = -1
    raindrops_u_new_tex: int = -1

    # Cached uniform locations for the Warp Dissolve shader program.
    warp_u_progress: int = -1
    warp_u_resolution: int = -1
    warp_u_old_tex: int = -1
    warp_u_new_tex: int = -1

    # Cached uniform locations for the Shuffle shader program.
    shuffle_u_progress: int = -1
    shuffle_u_resolution: int = -1
    shuffle_u_old_tex: int = -1
    shuffle_u_new_tex: int = -1
    shuffle_u_grid: int = -1
    shuffle_u_direction: int = -1

    # Cached uniform locations for the Shooting Stars (claws) shader program.
    claws_u_progress: int = -1
    claws_u_resolution: int = -1
    claws_u_old_tex: int = -1
    claws_u_new_tex: int = -1
    claws_u_density: int = -1
    claws_u_direction: int = -1
    claws_u_length: int = -1
    claws_u_width: int = -1

    # Simple flags to indicate whether the pipeline was initialized
    # successfully inside the current GL context.
    initialized: bool = False


@dataclass
class BlockSpinState:
    """State for a compositor-driven block spin transition.

    GLSL-backed Block Spins render a single thin 3D slab that flips the old
    image to the new one over a black void, with edge-only specular highlights.
    The grid-based variant has been removed; direction + progress fully define
    the animation.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    direction: SlideDirection = SlideDirection.LEFT
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
        self._shuffle: Optional[ShuffleShaderState] = None
        self._raindrops: Optional[RaindropsState] = None
        self._peel: Optional[PeelState] = None
        self._shooting_stars: Optional[ShootingStarsState] = None

        # Profiling for compositor-driven slide transitions.
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
        # Lightweight profiling for shader-backed Warp and Raindrops (Ripple)
        # transitions. These follow the same pattern as slide/wipe so that
        # future tuning can rely on comparable `[PERF] [GL COMPOSITOR]`
        # summaries without affecting visual behaviour.
        self._warp_profile_start_ts: Optional[float] = None
        self._warp_profile_last_ts: Optional[float] = None
        self._warp_profile_frame_count: int = 0
        self._warp_profile_min_dt: float = 0.0
        self._warp_profile_max_dt: float = 0.0
        self._raindrops_profile_start_ts: Optional[float] = None
        self._raindrops_profile_last_ts: Optional[float] = None
        self._raindrops_profile_frame_count: int = 0
        self._raindrops_profile_min_dt: float = 0.0
        self._raindrops_profile_max_dt: float = 0.0
        self._shuffle_profile_start_ts: Optional[float] = None
        self._shuffle_profile_last_ts: Optional[float] = None
        self._shuffle_profile_frame_count: int = 0
        self._shuffle_profile_min_dt: float = 0.0
        self._shuffle_profile_max_dt: float = 0.0
        self._blockspin_profile_start_ts: Optional[float] = None
        self._blockspin_profile_last_ts: Optional[float] = None
        self._blockspin_profile_frame_count: int = 0
        self._blockspin_profile_min_dt: float = 0.0
        self._blockspin_profile_max_dt: float = 0.0
        self._shooting_profile_start_ts: Optional[float] = None
        self._shooting_profile_last_ts: Optional[float] = None
        self._shooting_profile_frame_count: int = 0
        self._shooting_profile_min_dt: float = 0.0
        self._shooting_profile_max_dt: float = 0.0
        # Lightweight profiling for additional compositor-driven transitions
        # (Peel, BlockFlip, Diffuse, Blinds) so their GPU cost can be
        # compared against the core Slide/Wipe/Warp metrics.
        self._peel_profile_start_ts: Optional[float] = None
        self._peel_profile_last_ts: Optional[float] = None
        self._peel_profile_frame_count: int = 0
        self._peel_profile_min_dt: float = 0.0
        self._peel_profile_max_dt: float = 0.0
        self._blockflip_profile_start_ts: Optional[float] = None
        self._blockflip_profile_last_ts: Optional[float] = None
        self._blockflip_profile_frame_count: int = 0
        self._blockflip_profile_min_dt: float = 0.0
        self._blockflip_profile_max_dt: float = 0.0
        self._diffuse_profile_start_ts: Optional[float] = None
        self._diffuse_profile_last_ts: Optional[float] = None
        self._diffuse_profile_frame_count: int = 0
        self._diffuse_profile_min_dt: float = 0.0
        self._diffuse_profile_max_dt: float = 0.0
        self._blinds_profile_start_ts: Optional[float] = None
        self._blinds_profile_last_ts: Optional[float] = None
        self._blinds_profile_frame_count: int = 0
        self._blinds_profile_min_dt: float = 0.0
        self._blinds_profile_max_dt: float = 0.0

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

    def start_shuffle_shader(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        cols: int,
        rows: int,
        edge: str,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a shader-driven Shuffle transition between two pixmaps.

        This path is only used when the GLSL pipeline and Shuffle shader are
        available; callers are expected to fall back to the existing
        compositor-based Shuffle (diffuse/QRegion) implementation or further
        down to Group C CPU transitions when this method returns ``None``.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for shuffle")
            return None

        logger.debug("[GL SHADER] Shuffle shader path disabled; using diffuse/QRegion fallback")
        return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (shuffle shader)")
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
            self._shuffle = None
            self._shooting_stars = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Shuffle shader is mutually exclusive with other transitions.
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
        self._shuffle = None
        self._shooting_stars = None
        self._shuffle = ShuffleShaderState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            cols=max(1, int(cols)),
            rows=max(1, int(rows)),
            edge=edge or "L2R",
            progress=0.0,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # Reset per-transition profiling state.
        self._shuffle_profile_start_ts = None
        self._shuffle_profile_last_ts = None
        self._shuffle_profile_frame_count = 0
        self._shuffle_profile_min_dt = 0.0
        self._shuffle_profile_max_dt = 0.0

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
            update_callback=self._on_shuffle_update,
            on_complete=lambda: self._on_shuffle_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_shooting_stars(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a shader-driven Shooting Stars (claws) transition.

        This path is only used when the GLSL pipeline and claws shader are
        available; callers are expected to fall back to the existing
        compositor-based Claw Marks implementation when this returns ``None``.
        """

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for shooting stars")
            return None

        # The user has elected to fully retire the Shooting Stars / Claw Marks
        # effect. The GLSL claws path is therefore hard-disabled and callers
        # are expected to fall back to a compositor/crossfade implementation
        # when this method returns ``None``.
        logger.debug("[GL SHADER] Shooting Stars shader path disabled; using safe fallback")
        return None

        # Only use this path when the GLSL pipeline and claws shader are
        # actually available. Callers are expected to fall back to the
        # compositor's diffuse implementation when this returns ``None``.
        if (
            self._gl_disabled_for_session
            or gl is None
            or self._gl_pipeline is None
            or not self._gl_pipeline.initialized
            or not getattr(self._gl_pipeline, "claws_program", 0)
        ):
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (shooting stars)")
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
            self._shooting_stars = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Shooting Stars is mutually exclusive with other transitions.
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
        self._shooting_stars = None
        self._shooting_stars = ShootingStarsState(
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
            update_callback=self._on_shooting_stars_update,
            on_complete=lambda: self._on_shooting_stars_complete(on_finished),
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

        # Reset peel profiling state for this transition.
        self._peel_profile_start_ts = None
        self._peel_profile_last_ts = None
        self._peel_profile_frame_count = 0
        self._peel_profile_min_dt = 0.0
        self._peel_profile_max_dt = 0.0

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

        # Reset BlockFlip profiling state and wrap the caller's
        # update_callback so we can track frame timing without changing the
        # visual effect.
        self._blockflip_profile_start_ts = None
        self._blockflip_profile_last_ts = None
        self._blockflip_profile_frame_count = 0
        self._blockflip_profile_min_dt = 0.0
        self._blockflip_profile_max_dt = 0.0

        def _blockflip_profiled_update(progress: float, *, _inner=update_callback) -> None:
            if is_perf_metrics_enabled():
                now = time.time()
                if self._blockflip_profile_start_ts is None:
                    self._blockflip_profile_start_ts = now
                if self._blockflip_profile_last_ts is not None:
                    dt = now - self._blockflip_profile_last_ts
                    if dt > 0.0:
                        if self._blockflip_profile_min_dt == 0.0 or dt < self._blockflip_profile_min_dt:
                            self._blockflip_profile_min_dt = dt
                        if dt > self._blockflip_profile_max_dt:
                            self._blockflip_profile_max_dt = dt
                self._blockflip_profile_last_ts = now
                self._blockflip_profile_frame_count += 1
            _inner(progress)

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=_blockflip_profiled_update,
            on_complete=lambda: self._on_blockflip_complete(on_finished),
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_block_spin(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        direction: SlideDirection = SlideDirection.LEFT,
        on_finished: Optional[Callable[[], None]] = None,
    ) -> Optional[str]:
        """Begin a 3D block spin using the compositor.

        The GLSL path renders a single thin 3D slab that flips from the old
        image to the new one over a black void. Legacy grid parameters have
        been removed; direction and progress fully define the animation.
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
            direction=direction,
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

        # Reset Diffuse profiling state and wrap the caller's update
        # callback for timing.
        self._diffuse_profile_start_ts = None
        self._diffuse_profile_last_ts = None
        self._diffuse_profile_frame_count = 0
        self._diffuse_profile_min_dt = 0.0
        self._diffuse_profile_max_dt = 0.0

        def _diffuse_profiled_update(progress: float, *, _inner=update_callback) -> None:
            if is_perf_metrics_enabled():
                now = time.time()
                if self._diffuse_profile_start_ts is None:
                    self._diffuse_profile_start_ts = now
                if self._diffuse_profile_last_ts is not None:
                    dt = now - self._diffuse_profile_last_ts
                    if dt > 0.0:
                        if self._diffuse_profile_min_dt == 0.0 or dt < self._diffuse_profile_min_dt:
                            self._diffuse_profile_min_dt = dt
                        if dt > self._diffuse_profile_max_dt:
                            self._diffuse_profile_max_dt = dt
                self._diffuse_profile_last_ts = now
                self._diffuse_profile_frame_count += 1
            _inner(progress)

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=_diffuse_profiled_update,
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

        # Reset Blinds profiling state and wrap the caller's update callback
        # for timing.
        self._blinds_profile_start_ts = None
        self._blinds_profile_last_ts = None
        self._blinds_profile_frame_count = 0
        self._blinds_profile_min_dt = 0.0
        self._blinds_profile_max_dt = 0.0

        def _blinds_profiled_update(progress: float, *, _inner=update_callback) -> None:
            if is_perf_metrics_enabled():
                now = time.time()
                if self._blinds_profile_start_ts is None:
                    self._blinds_profile_start_ts = now
                if self._blinds_profile_last_ts is not None:
                    dt = now - self._blinds_profile_last_ts
                    if dt > 0.0:
                        if self._blinds_profile_min_dt == 0.0 or dt < self._blinds_profile_min_dt:
                            self._blinds_profile_min_dt = dt
                        if dt > self._blinds_profile_max_dt:
                            self._blinds_profile_max_dt = dt
                self._blinds_profile_last_ts = now
                self._blinds_profile_frame_count += 1
            _inner(progress)

        duration_sec = max(0.001, duration_ms / 1000.0)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=_blinds_profiled_update,
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

        # Profiling: track frame timing for compositor-driven slide when
        # PERF metrics are enabled. Disabled builds skip timing work
        # entirely while still running the visual transition.
        if is_perf_metrics_enabled():
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
            if is_perf_metrics_enabled():
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

        if is_perf_metrics_enabled():
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
            if is_perf_metrics_enabled():
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
        if is_perf_metrics_enabled():
            now = time.time()
            if self._blockspin_profile_start_ts is None:
                self._blockspin_profile_start_ts = now
            if self._blockspin_profile_last_ts is not None:
                dt = now - self._blockspin_profile_last_ts
                if dt > 0.0:
                    if self._blockspin_profile_min_dt == 0.0 or dt < self._blockspin_profile_min_dt:
                        self._blockspin_profile_min_dt = dt
                    if dt > self._blockspin_profile_max_dt:
                        self._blockspin_profile_max_dt = dt
            self._blockspin_profile_last_ts = now
            self._blockspin_profile_frame_count += 1
        self.update()

    def _on_warp_update(self, progress: float) -> None:
        """Update handler for compositor-driven warp dissolve transitions."""

        if self._warp is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._warp.progress = p
        # Profiling: track frame timing for warp dissolve.
        if is_perf_metrics_enabled():
            now = time.time()
            if self._warp_profile_start_ts is None:
                self._warp_profile_start_ts = now
            if self._warp_profile_last_ts is not None:
                dt = now - self._warp_profile_last_ts
                if dt > 0.0:
                    if self._warp_profile_min_dt == 0.0 or dt < self._warp_profile_min_dt:
                        self._warp_profile_min_dt = dt
                    if dt > self._warp_profile_max_dt:
                        self._warp_profile_max_dt = dt
            self._warp_profile_last_ts = now
            self._warp_profile_frame_count += 1
        self.update()

    def _on_raindrops_update(self, progress: float) -> None:
        """Update handler for shader-driven raindrops transitions."""

        if self._raindrops is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._raindrops.progress = p
        # Profiling: track frame timing for the Ripple/Raindrops shader path.
        if is_perf_metrics_enabled():
            now = time.time()
            if self._raindrops_profile_start_ts is None:
                self._raindrops_profile_start_ts = now
            if self._raindrops_profile_last_ts is not None:
                dt = now - self._raindrops_profile_last_ts
                if dt > 0.0:
                    if self._raindrops_profile_min_dt == 0.0 or dt < self._raindrops_profile_min_dt:
                        self._raindrops_profile_min_dt = dt
                    if dt > self._raindrops_profile_max_dt:
                        self._raindrops_profile_max_dt = dt
            self._raindrops_profile_last_ts = now
            self._raindrops_profile_frame_count += 1
        self.update()

    def _on_shooting_stars_update(self, progress: float) -> None:
        """Update handler for shader-driven Shooting Stars transitions."""

        if self._shooting_stars is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._shooting_stars.progress = p
        if is_perf_metrics_enabled():
            now = time.time()
            if self._shooting_profile_start_ts is None:
                self._shooting_profile_start_ts = now
            if self._shooting_profile_last_ts is not None:
                dt = now - self._shooting_profile_last_ts
                if dt > 0.0:
                    if self._shooting_profile_min_dt == 0.0 or dt < self._shooting_profile_min_dt:
                        self._shooting_profile_min_dt = dt
                    if dt > self._shooting_profile_max_dt:
                        self._shooting_profile_max_dt = dt
            self._shooting_profile_last_ts = now
            self._shooting_profile_frame_count += 1
        self.update()

    def _on_shuffle_update(self, progress: float) -> None:
        """Update handler for shader-driven Shuffle transitions."""

        if self._shuffle is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._shuffle.progress = p
        # Profiling: track frame timing for the Shuffle shader path.
        if is_perf_metrics_enabled():
            now = time.time()
            if self._shuffle_profile_start_ts is None:
                self._shuffle_profile_start_ts = now
            if self._shuffle_profile_last_ts is not None:
                dt = now - self._shuffle_profile_last_ts
                if dt > 0.0:
                    if self._shuffle_profile_min_dt == 0.0 or dt < self._shuffle_profile_min_dt:
                        self._shuffle_profile_min_dt = dt
                    if dt > self._shuffle_profile_max_dt:
                        self._shuffle_profile_max_dt = dt
            self._shuffle_profile_last_ts = now
            self._shuffle_profile_frame_count += 1
        self.update()

    def _on_blockspin_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven block spin transitions."""

        try:
            if is_perf_metrics_enabled():
                try:
                    if (
                        self._blockspin_profile_start_ts is not None
                        and self._blockspin_profile_last_ts is not None
                        and self._blockspin_profile_frame_count > 0
                    ):
                        elapsed = max(0.0, self._blockspin_profile_last_ts - self._blockspin_profile_start_ts)
                        if elapsed > 0.0:
                            duration_ms = elapsed * 1000.0
                            avg_fps = self._blockspin_profile_frame_count / elapsed
                            min_dt_ms = (
                                self._blockspin_profile_min_dt * 1000.0
                                if self._blockspin_profile_min_dt > 0.0
                                else 0.0
                            )
                            max_dt_ms = (
                                self._blockspin_profile_max_dt * 1000.0
                                if self._blockspin_profile_max_dt > 0.0
                                else 0.0
                            )
                            logger.info(
                                "[PERF] [GL COMPOSITOR] BlockSpin metrics: duration=%.1fms, frames=%d, "
                                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                                duration_ms,
                                self._blockspin_profile_frame_count,
                                avg_fps,
                                min_dt_ms,
                                max_dt_ms,
                                self.width(),
                                self.height(),
                            )
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] BlockSpin metrics logging failed: %s", e, exc_info=True)

            self._blockspin_profile_start_ts = None
            self._blockspin_profile_last_ts = None
            self._blockspin_profile_frame_count = 0
            self._blockspin_profile_min_dt = 0.0
            self._blockspin_profile_max_dt = 0.0

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
            # Emit a concise profiling summary for warp dissolve, mirroring
            # the existing Slide/Wipe `[PERF] [GL COMPOSITOR]` metrics.
            if is_perf_metrics_enabled():
                try:
                    if (
                        self._warp_profile_start_ts is not None
                        and self._warp_profile_last_ts is not None
                        and self._warp_profile_frame_count > 0
                    ):
                        elapsed = max(0.0, self._warp_profile_last_ts - self._warp_profile_start_ts)
                        if elapsed > 0.0:
                            duration_ms = elapsed * 1000.0
                            avg_fps = self._warp_profile_frame_count / elapsed
                            min_dt_ms = (
                                self._warp_profile_min_dt * 1000.0
                                if self._warp_profile_min_dt > 0.0
                                else 0.0
                            )
                            max_dt_ms = (
                                self._warp_profile_max_dt * 1000.0
                                if self._warp_profile_max_dt > 0.0
                                else 0.0
                            )
                            logger.info(
                                "[PERF] [GL COMPOSITOR] Warp metrics: duration=%.1fms, frames=%d, "
                                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                                duration_ms,
                                self._warp_profile_frame_count,
                                avg_fps,
                                min_dt_ms,
                                max_dt_ms,
                                self.width(),
                                self.height(),
                            )
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Warp metrics logging failed: %s", e, exc_info=True)

            # Reset profiling state.
            self._warp_profile_start_ts = None
            self._warp_profile_last_ts = None
            self._warp_profile_frame_count = 0
            self._warp_profile_min_dt = 0.0
            self._warp_profile_max_dt = 0.0

            try:
                self._release_transition_textures()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to release transition textures on warp complete: %s", e, exc_info=True)

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
            # Emit a concise profiling summary for the Ripple/Raindrops shader
            # path so future fidelity-oriented tuning has FPS telemetry without
            # altering the effect itself.
            if is_perf_metrics_enabled():
                try:
                    if (
                        self._raindrops_profile_start_ts is not None
                        and self._raindrops_profile_last_ts is not None
                        and self._raindrops_profile_frame_count > 0
                    ):
                        elapsed = max(0.0, self._raindrops_profile_last_ts - self._raindrops_profile_start_ts)
                        if elapsed > 0.0:
                            duration_ms = elapsed * 1000.0
                            avg_fps = self._raindrops_profile_frame_count / elapsed
                            min_dt_ms = (
                                self._raindrops_profile_min_dt * 1000.0
                                if self._raindrops_profile_min_dt > 0.0
                                else 0.0
                            )
                            max_dt_ms = (
                                self._raindrops_profile_max_dt * 1000.0
                                if self._raindrops_profile_max_dt > 0.0
                                else 0.0
                            )
                            logger.info(
                                "[PERF] [GL COMPOSITOR] Raindrops metrics: duration=%.1fms, frames=%d, "
                                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                                duration_ms,
                                self._raindrops_profile_frame_count,
                                avg_fps,
                                min_dt_ms,
                                max_dt_ms,
                                self.width(),
                                self.height(),
                            )
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Raindrops metrics logging failed: %s", e, exc_info=True)

            # Reset profiling state.
            self._raindrops_profile_start_ts = None
            self._raindrops_profile_last_ts = None
            self._raindrops_profile_frame_count = 0
            self._raindrops_profile_min_dt = 0.0
            self._raindrops_profile_max_dt = 0.0

            try:
                self._release_transition_textures()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to release transition textures on raindrops complete: %s", e, exc_info=True)

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

    def _on_shuffle_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for shader-driven Shuffle transitions."""

        try:
            # Emit a concise profiling summary for the Shuffle shader so future
            # tuning has telemetry without altering visuals.
            if is_perf_metrics_enabled():
                try:
                    if (
                        self._shuffle_profile_start_ts is not None
                        and self._shuffle_profile_last_ts is not None
                        and self._shuffle_profile_frame_count > 0
                    ):
                        elapsed = max(0.0, self._shuffle_profile_last_ts - self._shuffle_profile_start_ts)
                        if elapsed > 0.0:
                            duration_ms = elapsed * 1000.0
                            avg_fps = self._shuffle_profile_frame_count / elapsed
                            min_dt_ms = (
                                self._shuffle_profile_min_dt * 1000.0
                                if self._shuffle_profile_min_dt > 0.0
                                else 0.0
                            )
                            max_dt_ms = (
                                self._shuffle_profile_max_dt * 1000.0
                                if self._shuffle_profile_max_dt > 0.0
                                else 0.0
                            )
                            logger.info(
                                "[PERF] [GL COMPOSITOR] Shuffle metrics: duration=%.1fms, frames=%d, "
                                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                                duration_ms,
                                self._shuffle_profile_frame_count,
                                avg_fps,
                                min_dt_ms,
                                max_dt_ms,
                                self.width(),
                                self.height(),
                            )
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Shuffle metrics logging failed: %s", e, exc_info=True)

            # Reset profiling state.
            self._shuffle_profile_start_ts = None
            self._shuffle_profile_last_ts = None
            self._shuffle_profile_frame_count = 0
            self._shuffle_profile_min_dt = 0.0
            self._shuffle_profile_max_dt = 0.0

            try:
                self._release_transition_textures()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to release transition textures on shuffle complete: %s", e, exc_info=True)

            if self._shuffle is not None:
                try:
                    self._base_pixmap = self._shuffle.new_pixmap
                except Exception:
                    pass
            self._shuffle = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug(
                    "[GL COMPOSITOR] Shuffle complete update failed (likely after deletion): %s",
                    e,
                    exc_info=True,
                )

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Shuffle complete handler failed: %s", e, exc_info=True)

    def _on_shooting_stars_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for shader-driven Shooting Stars transitions."""

        try:
            if is_perf_metrics_enabled():
                try:
                    if (
                        self._shooting_profile_start_ts is not None
                        and self._shooting_profile_last_ts is not None
                        and self._shooting_profile_frame_count > 0
                    ):
                        elapsed = max(0.0, self._shooting_profile_last_ts - self._shooting_profile_start_ts)
                        if elapsed > 0.0:
                            duration_ms = elapsed * 1000.0
                            avg_fps = self._shooting_profile_frame_count / elapsed
                            min_dt_ms = (
                                self._shooting_profile_min_dt * 1000.0
                                if self._shooting_profile_min_dt > 0.0
                                else 0.0
                            )
                            max_dt_ms = (
                                self._shooting_profile_max_dt * 1000.0
                                if self._shooting_profile_max_dt > 0.0
                                else 0.0
                            )
                            logger.info(
                                "[PERF] [GL COMPOSITOR] ShootingStars metrics: duration=%.1fms, frames=%d, "
                                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                                duration_ms,
                                self._shooting_profile_frame_count,
                                avg_fps,
                                min_dt_ms,
                                max_dt_ms,
                                self.width(),
                                self.height(),
                            )
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] ShootingStars metrics logging failed: %s", e, exc_info=True)

            self._shooting_profile_start_ts = None
            self._shooting_profile_last_ts = None
            self._shooting_profile_frame_count = 0
            self._shooting_profile_min_dt = 0.0
            self._shooting_profile_max_dt = 0.0

            if self._shooting_stars is not None:
                try:
                    self._base_pixmap = self._shooting_stars.new_pixmap
                except Exception:
                    pass
            self._shooting_stars = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug(
                    "[GL COMPOSITOR] Shooting Stars complete update failed (likely after deletion): %s",
                    e,
                    exc_info=True,
                )

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Shooting Stars complete handler failed: %s", e, exc_info=True)

    def _on_peel_update(self, progress: float) -> None:
        """Update handler for compositor-driven peel transitions."""

        if self._peel is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._peel.progress = p
        if is_perf_metrics_enabled():
            now = time.time()
            if self._peel_profile_start_ts is None:
                self._peel_profile_start_ts = now
            if self._peel_profile_last_ts is not None:
                dt = now - self._peel_profile_last_ts
                if dt > 0.0:
                    if self._peel_profile_min_dt == 0.0 or dt < self._peel_profile_min_dt:
                        self._peel_profile_min_dt = dt
                    if dt > self._peel_profile_max_dt:
                        self._peel_profile_max_dt = dt
            self._peel_profile_last_ts = now
            self._peel_profile_frame_count += 1
        self.update()

    def _on_peel_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven peel transitions."""

        try:
            if is_perf_metrics_enabled():
                try:
                    if (
                        self._peel_profile_start_ts is not None
                        and self._peel_profile_last_ts is not None
                        and self._peel_profile_frame_count > 0
                    ):
                        elapsed = max(0.0, self._peel_profile_last_ts - self._peel_profile_start_ts)
                        if elapsed > 0.0:
                            duration_ms = elapsed * 1000.0
                            avg_fps = self._peel_profile_frame_count / elapsed
                            min_dt_ms = (
                                self._peel_profile_min_dt * 1000.0
                                if self._peel_profile_min_dt > 0.0
                                else 0.0
                            )
                            max_dt_ms = (
                                self._peel_profile_max_dt * 1000.0
                                if self._peel_profile_max_dt > 0.0
                                else 0.0
                            )
                            logger.info(
                                "[PERF] [GL COMPOSITOR] Peel metrics: duration=%.1fms, frames=%d, "
                                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                                duration_ms,
                                self._peel_profile_frame_count,
                                avg_fps,
                                min_dt_ms,
                                max_dt_ms,
                                self.width(),
                                self.height(),
                            )
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Peel metrics logging failed: %s", e, exc_info=True)

            self._peel_profile_start_ts = None
            self._peel_profile_last_ts = None
            self._peel_profile_frame_count = 0
            self._peel_profile_min_dt = 0.0
            self._peel_profile_max_dt = 0.0

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
            if is_perf_metrics_enabled():
                try:
                    if (
                        self._blockflip_profile_start_ts is not None
                        and self._blockflip_profile_last_ts is not None
                        and self._blockflip_profile_frame_count > 0
                    ):
                        elapsed = max(0.0, self._blockflip_profile_last_ts - self._blockflip_profile_start_ts)
                        if elapsed > 0.0:
                            duration_ms = elapsed * 1000.0
                            avg_fps = self._blockflip_profile_frame_count / elapsed
                            min_dt_ms = (
                                self._blockflip_profile_min_dt * 1000.0
                                if self._blockflip_profile_min_dt > 0.0
                                else 0.0
                            )
                            max_dt_ms = (
                                self._blockflip_profile_max_dt * 1000.0
                                if self._blockflip_profile_max_dt > 0.0
                                else 0.0
                            )
                            logger.info(
                                "[PERF] [GL COMPOSITOR] BlockFlip metrics: duration=%.1fms, frames=%d, "
                                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                                duration_ms,
                                self._blockflip_profile_frame_count,
                                avg_fps,
                                min_dt_ms,
                                max_dt_ms,
                                self.width(),
                                self.height(),
                            )
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] BlockFlip metrics logging failed: %s", e, exc_info=True)

            self._blockflip_profile_start_ts = None
            self._blockflip_profile_last_ts = None
            self._blockflip_profile_frame_count = 0
            self._blockflip_profile_min_dt = 0.0
            self._blockflip_profile_max_dt = 0.0

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
            if is_perf_metrics_enabled():
                try:
                    if (
                        self._diffuse_profile_start_ts is not None
                        and self._diffuse_profile_last_ts is not None
                        and self._diffuse_profile_frame_count > 0
                    ):
                        elapsed = max(0.0, self._diffuse_profile_last_ts - self._diffuse_profile_start_ts)
                        if elapsed > 0.0:
                            duration_ms = elapsed * 1000.0
                            avg_fps = self._diffuse_profile_frame_count / elapsed
                            min_dt_ms = (
                                self._diffuse_profile_min_dt * 1000.0
                                if self._diffuse_profile_min_dt > 0.0
                                else 0.0
                            )
                            max_dt_ms = (
                                self._diffuse_profile_max_dt * 1000.0
                                if self._diffuse_profile_max_dt > 0.0
                                else 0.0
                            )
                            logger.info(
                                "[PERF] [GL COMPOSITOR] Diffuse metrics: duration=%.1fms, frames=%d, "
                                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                                duration_ms,
                                self._diffuse_profile_frame_count,
                                avg_fps,
                                min_dt_ms,
                                max_dt_ms,
                                self.width(),
                                self.height(),
                            )
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Diffuse metrics logging failed: %s", e, exc_info=True)

            self._diffuse_profile_start_ts = None
            self._diffuse_profile_last_ts = None
            self._diffuse_profile_frame_count = 0
            self._diffuse_profile_min_dt = 0.0
            self._diffuse_profile_max_dt = 0.0

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
            if is_perf_metrics_enabled():
                try:
                    if (
                        self._blinds_profile_start_ts is not None
                        and self._blinds_profile_last_ts is not None
                        and self._blinds_profile_frame_count > 0
                    ):
                        elapsed = max(0.0, self._blinds_profile_last_ts - self._blinds_profile_start_ts)
                        if elapsed > 0.0:
                            duration_ms = elapsed * 1000.0
                            avg_fps = self._blinds_profile_frame_count / elapsed
                            min_dt_ms = (
                                self._blinds_profile_min_dt * 1000.0
                                if self._blinds_profile_min_dt > 0.0
                                else 0.0
                            )
                            max_dt_ms = (
                                self._blinds_profile_max_dt * 1000.0
                                if self._blinds_profile_max_dt > 0.0
                                else 0.0
                            )
                            logger.info(
                                "[PERF] [GL COMPOSITOR] Blinds metrics: duration=%.1fms, frames=%d, "
                                "avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, size=%dx%d",
                                duration_ms,
                                self._blinds_profile_frame_count,
                                avg_fps,
                                min_dt_ms,
                                max_dt_ms,
                                self.width(),
                                self.height(),
                            )
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Blinds metrics logging failed: %s", e, exc_info=True)

            self._blinds_profile_start_ts = None
            self._blinds_profile_last_ts = None
            self._blinds_profile_frame_count = 0
            self._blinds_profile_min_dt = 0.0
            self._blinds_profile_max_dt = 0.0

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

        if new_pm is None and self._shooting_stars is not None:
            try:
                new_pm = self._shooting_stars.new_pixmap
            except Exception:
                new_pm = None

        if new_pm is None and self._shuffle is not None:
            try:
                new_pm = self._shuffle.new_pixmap
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

        # Ensure any transition textures are freed when a transition is
        # cancelled so we do not leak VRAM across many rotations.
        try:
            self._release_transition_textures()
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

            # Log adapter information and detect obvious software GL drivers so
            # shader-backed paths can be disabled proactively. QPainter-based
            # compositor transitions remain available as the safe fallback.
            if gl is not None:
                try:
                    vendor_bytes = gl.glGetString(gl.GL_VENDOR)
                    renderer_bytes = gl.glGetString(gl.GL_RENDERER)
                    version_bytes = gl.glGetString(gl.GL_VERSION)

                    def _decode_gl_string(val: object) -> str:
                        if isinstance(val, (bytes, bytearray)):
                            try:
                                return val.decode("ascii", "ignore")
                            except Exception:
                                return ""
                        return str(val) if val is not None else ""

                    vendor = _decode_gl_string(vendor_bytes)
                    renderer = _decode_gl_string(renderer_bytes)
                    version_str = _decode_gl_string(version_bytes)
                    logger.info(
                        "[GL COMPOSITOR] OpenGL adapter: vendor=%s, renderer=%s, version=%s",
                        vendor or "?",
                        renderer or "?",
                        version_str or "?",
                    )

                    combo = f"{vendor} {renderer}".lower()
                    software_markers = (
                        "gdi generic",
                        "microsoft basic render driver",
                        "software rasterizer",
                        "llvmpipe",
                    )
                    if any(m in combo for m in software_markers):
                        logger.warning(
                            "[GL COMPOSITOR] Software OpenGL implementation detected; "
                            "disabling shader pipeline for this session"
                        )
                        self._gl_disabled_for_session = True
                        self._use_shaders = False
                except Exception:
                    logger.debug("[GL COMPOSITOR] Failed to query OpenGL adapter strings", exc_info=True)

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
            self._gl_pipeline.u_block_rect_loc = gl.glGetUniformLocation(program, "u_blockRect")
            self._gl_pipeline.u_block_uv_rect_loc = gl.glGetUniformLocation(program, "u_blockUvRect")
            self._gl_pipeline.u_spec_dir_loc = gl.glGetUniformLocation(program, "u_specDir")
            self._gl_pipeline.u_axis_mode_loc = gl.glGetUniformLocation(program, "u_axisMode")

            # Compile the Ripple (raindrops) shader program when GL is
            # available. On failure we disable shader usage for this session so
            # that all shader-backed transitions fall back to the compositor's
            # QPainter-based paths (Group A → Group B).
            try:
                rp = self._create_raindrops_program()
                self._gl_pipeline.raindrops_program = rp
                self._gl_pipeline.raindrops_u_progress = gl.glGetUniformLocation(rp, "u_progress")
                self._gl_pipeline.raindrops_u_resolution = gl.glGetUniformLocation(rp, "u_resolution")
                self._gl_pipeline.raindrops_u_old_tex = gl.glGetUniformLocation(rp, "uOldTex")
                self._gl_pipeline.raindrops_u_new_tex = gl.glGetUniformLocation(rp, "uNewTex")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize raindrops shader program", exc_info=True)
                self._gl_pipeline.raindrops_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            try:
                wp = self._create_warp_program()
                self._gl_pipeline.warp_program = wp
                self._gl_pipeline.warp_u_progress = gl.glGetUniformLocation(wp, "u_progress")
                self._gl_pipeline.warp_u_resolution = gl.glGetUniformLocation(wp, "u_resolution")
                self._gl_pipeline.warp_u_old_tex = gl.glGetUniformLocation(wp, "uOldTex")
                self._gl_pipeline.warp_u_new_tex = gl.glGetUniformLocation(wp, "uNewTex")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize warp shader program", exc_info=True)
                self._gl_pipeline.warp_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Shuffle shader program. On failure we disable shader
            # usage for this session so that all shader-backed transitions fall
            # back to the compositor's QPainter-based paths (Group A  Group C
            # downgrade via existing CPU transitions rather than a CPU Shuffle
            # variant).
            try:
                sp = self._create_shuffle_program()
                self._gl_pipeline.shuffle_program = sp
                self._gl_pipeline.shuffle_u_progress = gl.glGetUniformLocation(sp, "u_progress")
                self._gl_pipeline.shuffle_u_resolution = gl.glGetUniformLocation(sp, "u_resolution")
                self._gl_pipeline.shuffle_u_old_tex = gl.glGetUniformLocation(sp, "uOldTex")
                self._gl_pipeline.shuffle_u_new_tex = gl.glGetUniformLocation(sp, "uNewTex")
                self._gl_pipeline.shuffle_u_grid = gl.glGetUniformLocation(sp, "u_grid")
                self._gl_pipeline.shuffle_u_direction = gl.glGetUniformLocation(sp, "u_direction")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize shuffle shader program", exc_info=True)
                self._gl_pipeline.shuffle_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Shooting Stars (claws) shader program. On failure we
            # disable shader usage for this session so that all shader-backed
            # transitions fall back to the compositor's QPainter-based paths
            # (Group A → Group B).
            try:
                cp = self._create_claws_program()
                self._gl_pipeline.claws_program = cp
                self._gl_pipeline.claws_u_progress = gl.glGetUniformLocation(cp, "u_progress")
                self._gl_pipeline.claws_u_resolution = gl.glGetUniformLocation(cp, "u_resolution")
                self._gl_pipeline.claws_u_old_tex = gl.glGetUniformLocation(cp, "uOldTex")
                self._gl_pipeline.claws_u_new_tex = gl.glGetUniformLocation(cp, "uNewTex")
                self._gl_pipeline.claws_u_density = gl.glGetUniformLocation(cp, "u_density")
                self._gl_pipeline.claws_u_direction = gl.glGetUniformLocation(cp, "u_direction")
                self._gl_pipeline.claws_u_length = gl.glGetUniformLocation(cp, "u_length")
                self._gl_pipeline.claws_u_width = gl.glGetUniformLocation(cp, "u_width")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize claws/shooting-stars shader program", exc_info=True)
                self._gl_pipeline.claws_program = 0
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
                self._release_transition_textures()
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
            self._release_transition_textures()
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
            self._release_transition_textures()

            try:
                if self._gl_pipeline.basic_program:
                    gl.glDeleteProgram(int(self._gl_pipeline.basic_program))
                if getattr(self._gl_pipeline, "raindrops_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.raindrops_program))
                if getattr(self._gl_pipeline, "warp_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.warp_program))
                if getattr(self._gl_pipeline, "shuffle_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.shuffle_program))
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
            self._gl_pipeline.shuffle_program = 0
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
out float vEdgeX;
flat out int vFaceKind;  // 1=front, 2=back, 3=side

uniform float u_angle;
uniform float u_aspect;
uniform vec4 u_blockRect;   // xy = clip min, zw = clip max
uniform vec4 u_blockUvRect; // xy = uv min,  zw = uv max
uniform float u_specDir;    // -1 or +1, matches fragment shader
uniform int u_axisMode;

void main() {
    // Preserve the local X coordinate as a thickness parameter for side
    // faces while remapping UVs into the per-tile rectangle.
    float edgeCoord = aUv.x;
    vEdgeX = edgeCoord;

    // Remap local UVs into the per-tile UV rectangle so that a grid of slabs
    // each samples its own portion of the image pair.
    vUv = mix(u_blockUvRect.xy, u_blockUvRect.zw, aUv);

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

    mat3 rotX = mat3(
        1.0, 0.0, 0.0,
        0.0,  ca, -sa,
        0.0,  sa,  ca
    );

    vec3 pos;
    vec3 normal;
    if (u_axisMode == 1) {
        pos = rotX * aPos;
        normal = normalize(rotX * aNormal);
    } else {
        pos = rotY * aPos;
        normal = normalize(rotY * aNormal);
    }

    // Orthographic-style projection: treat the rotated slab as sitting in
    // clip space so that when it faces the camera it fills the viewport
    // similarly to the old 2D card, without extreme perspective stretching.
    vNormal = normal;
    vViewDir = vec3(0.0, 0.0, 1.0);

    // Use -pos.z so the face nearest the camera always wins the depth test:
    // at angle 0 the front (old image) is in front, at angle pi the back
    // (new image) is in front. This avoids sudden flips when the CPU swaps
    // the base pixmap at transition start/end.
    float z_clip = -pos.z * 0.5;  // small but non-zero depth for proper occlusion

    // Map the rotated slab into the caller-supplied block rect in clip space.
    // When rendering a single full-frame slab the rect covers the entire
    // viewport (-1..1 in both axes); in grid mode each tile uses a smaller
    // rect.
    float nx = pos.x * 0.5 + 0.5;
    float ny = pos.y * 0.5 + 0.5;
    float x_clip = mix(u_blockRect.x, u_blockRect.z, nx);
    float y_clip = mix(u_blockRect.y, u_blockRect.w, ny);

    // Add axis mode uniform for BlockSpin
    // uniform int u_axisMode;  // 0 = Y, 1 = X
    gl_Position = vec4(x_clip, y_clip, z_clip, 1.0);
}
"""

        fs_source = """#version 410 core
in vec2 vUv;
in vec3 vNormal;
in vec3 vViewDir;
in float vEdgeX;
flat in int vFaceKind;  // 1=front, 2=back, 3=side
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_angle;
uniform float u_aspect;
uniform float u_specDir;  // -1 or +1, controls highlight travel direction
uniform int u_axisMode;   // 0 = Y-axis spin, 1 = X-axis spin

void main() {
    // Qt images are stored top-to-bottom, whereas OpenGL's texture
    // coordinates assume (0,0) at the bottom-left. Flip the V coordinate so
    // the sampled image appears upright.
    vec2 uv_front = vec2(vUv.x, 1.0 - vUv.y);

    // For horizontal (Y-axis) spins we mirror the back face horizontally so
    // that when the card flips left/right the new image appears with the
    // same orientation as a plain 2D draw. For vertical (X-axis) spins the
    // geometric rotation inverts the slab in Y, so we sample with the raw
    // UVs to keep the new image upright.
    vec2 uv_back;
    if (u_axisMode == 0) {
        uv_back = vec2(1.0 - vUv.x, 1.0 - vUv.y);  // horizontal spin
    } else {
        uv_back = vec2(vUv.x, vUv.y);              // vertical spin
    }

    vec3 n = normalize(vNormal);
    vec3 viewDir = normalize(vViewDir);
    vec3 lightDir = normalize(vec3(-0.15, 0.35, 0.9));

    // Normalised spin progress 0..1 from angle 0..pi and an edge-biased
    // highlight envelope so specular accents are strongest near the start
    // and end of the spin (slab faces most flush) and softest around the
    // midpoint. A complementary mid-spin phase is used for the white rim
    // outline so it appears when the slab is most edge-on. Use the absolute
    // angle so LEFT/RIGHT and UP/DOWN directions share the same envelope.
    float t = clamp(abs(u_angle) / 3.14159265, 0.0, 1.0);
    float edgeFactor = abs(t - 0.5) * 2.0;  // 0 at mid-spin, 1 at edges
    float highlightPhase = edgeFactor * edgeFactor;
    float midPhase = (1.0 - edgeFactor);
    midPhase = midPhase * midPhase;

    vec3 color;

    if (vFaceKind == 3) {
        // Side faces: darker glass core with a moving specular band across
        // the slab thickness, plus a very thin white outline along the rim
        // when the slab is most edge-on.
        vec3 base = vec3(0.0);
        vec3 halfVec = normalize(lightDir + viewDir);
        float ndh = max(dot(n, halfVec), 0.0);

        // Side faces use the original local X coordinate in [0,1] to
        // represent slab thickness from one edge to the other, independent
        // of any grid tiling. Move the highlight band centre from one edge
        // to the opposite edge over the spin, clamped far enough inside the
        // edges so the thicker band never leaves the face.
        float edgeT = (u_specDir < 0.0) ? (1.0 - t) : t;
        float bandHalfWidth = 0.09;  // thicker band for a more readable sheen
        float bandCenter = mix(bandHalfWidth, 1.0 - bandHalfWidth, edgeT);
        float d = abs(vEdgeX - bandCenter);
        float bandMask = 1.0 - smoothstep(bandHalfWidth, bandHalfWidth * 1.6, d);

        // Stronger, brighter specular so the edge sheen is clearly visible
        // and approaches white at its apex without blowing out the face.
        float spec = pow(ndh, 6.0) * bandMask * highlightPhase;
        float edgeSpec = clamp(4.0 * spec, 0.0, 1.0);
        color = mix(base, vec3(1.0), edgeSpec);

        // Thin white outline hugging the side-face rim. This uses both the
        // preserved local thickness coordinate (vEdgeX) and the tile UV's
        // vertical coordinate so the border tracks the outer rectangle of
        // the slab. It is only active around mid-spin so it never appears
        // on the very first/last frames.
        float xEdge = min(vEdgeX, 1.0 - vEdgeX);
        float yEdge = min(vUv.y, 1.0 - vUv.y);
        float edgeDist = min(xEdge, yEdge);
        float outlineMask = 1.0 - smoothstep(0.02, 0.08, edgeDist);
        float outlinePhase = outlineMask * midPhase;
        if (outlinePhase > 0.0) {
            float outlineStrength = clamp(1.2 * outlinePhase, 0.0, 1.0);
            color = mix(color, vec3(1.0), outlineStrength);
        }
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
        float rim = 0.0;
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

    def _create_shuffle_program(self) -> int:
        """Compile and link the shader program used for Shuffle mask."""

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
uniform vec2 u_grid;        // (cols, rows)
uniform vec2 u_direction;   // slide direction, cardinal (e.g. (1,0), (-1,0), (0,1), (0,-1))

float hash1(float n) {
    return fract(sin(n) * 43758.5453123);
}

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Logical block grid in UV space.
    vec2 grid = max(u_grid, vec2(1.0));
    vec2 cell = clamp(floor(uv * grid), vec2(0.0), grid - vec2(1.0));
    float cols = grid.x;
    float rows = grid.y;
    float cellIndex = cell.y * cols + cell.x;

    // Per-block jitter: staggered start so blocks do not all move in
    // perfect lock-step. We mirror the diffuse-based Shuffle semantics by
    // varying only the start time per block and letting the wavefront run
    // across the screen, rather than also randomising the span.
    float rnd = hash1(cellIndex * 37.0 + 13.0);
    float start = rnd * 0.7;
    float local = (t - start) / max(1.0 - start, 1e-3);
    local = clamp(local, 0.0, 1.0);

    // Local UV within the block.
    vec2 cellOrigin = cell / grid;
    vec2 cellSize = vec2(1.0) / grid;
    vec2 uvLocal = (uv - cellOrigin) / cellSize; // 0..1 inside block

    // Direction-aware axis so that the reveal always starts at axis = 0
    // regardless of the global direction.
    vec2 dir = u_direction;
    if (length(dir) < 1e-3) {
        dir = vec2(1.0, 0.0);
    } else {
        dir = normalize(dir);
    }

    float axis;
    if (abs(dir.x) > abs(dir.y)) {
        // Horizontal motion
        axis = uvLocal.x;
        if (dir.x < 0.0) {
            axis = 1.0 - axis;
        }
    } else {
        // Vertical motion
        axis = uvLocal.y;
        if (dir.y < 0.0) {
            axis = 1.0 - axis;
        }
    }

    // Soft front so the edge of each block reads as a moving band rather than
    // a hard 1px line.
    float front = local;
    float feather = 0.18;
    float blockMask = smoothstep(front - feather, front, axis);

    // Late global tail: only in the final few percent do we force any
    // remaining straggler blocks fully onto the new image, avoiding an
    // early, harsh swap while still guaranteeing a clean landing.
    float globalTail = smoothstep(0.96, 1.0, t);
    float mixFactor = clamp(max(blockMask, globalTail), 0.0, 1.0);

    vec4 color = mix(oldColor, newColor, mixFactor);
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
                logger.debug("[GL SHADER] Failed to link shuffle program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link shuffle program: {log!r}")
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

    // Normalised, aspect-corrected coordinates around the image centre.
    float aspect = u_resolution.x / max(u_resolution.y, 1.0);
    vec2 centered = uv - vec2(0.5, 0.5);
    centered.x *= aspect;

    float r = length(centered);
    float maxR = length(vec2(0.5 * aspect, 0.5));
    float rNorm = clamp(r / maxR, 0.0, 1.0);

    // Angle in polar space.
    float theta = atan(centered.y, centered.x);

    // Strong vortex: peak twist at t=0.5 and near the centre. Allow up to
    // ~1.65 turns at the core so the motion clearly reads as a whirlpool.
    float swirlPhase = sin(t * 3.14159265);          // 0 at 0/1, 1 at 0.5
    float swirlStrength = 3.3 * 3.14159265;          // ~10% stronger than 1.5
    float radialFalloff = (1.0 - rNorm);
    radialFalloff *= radialFalloff;                  // bias towards centre
    // Suppress twist in a thin border near the outer edge to avoid visible
    // bending of the very top/left edges on wide aspect ratios.
    float edgeMask = 1.0 - smoothstep(0.94, 1.0, rNorm);
    radialFalloff *= edgeMask;
    float swirl = swirlPhase * swirlStrength * radialFalloff;

    // Shared swirl field that gradually unwinds as we approach the end of the
    // transition so the new image relaxes back to its original orientation.
    float unwhirl = smoothstep(0.6, 1.0, t);
    float sharedSwirl = swirl * (1.0 - 0.75 * unwhirl);

    // OLD image - fully participates in the vortex.
    float thetaOld = theta + sharedSwirl;
    float rOld = r * (1.0 - 0.45 * t * (1.0 - rNorm));
    vec2 dirOld = vec2(cos(thetaOld), sin(thetaOld));
    dirOld.x /= aspect;
    vec2 uvOld = vec2(0.5, 0.5) + dirOld * rOld;
    uvOld = clamp(uvOld, vec2(0.0), vec2(1.0));
    vec4 warpedOld = texture(uOldTex, uvOld);

    // NEW image - equally twisted into the same vortex, then gently unwound as
    // we approach t=1 so the final frame is stable. Retain a mild zoom-in
    // early on but guarantee that we land exactly on the original framing
    // once the unwhirl phase has completed.
    float thetaNew = theta + sharedSwirl;
    float zoomPhase = 0.85 + 0.25 * t;
    float zoom = mix(zoomPhase, 1.0, unwhirl);
    float rNew = r * zoom;
    vec2 dirNew = vec2(cos(thetaNew), sin(thetaNew));
    dirNew.x /= aspect;
    vec2 uvNew = vec2(0.5, 0.5) + dirNew * rNew;
    uvNew = clamp(uvNew, vec2(0.0), vec2(1.0));
    vec4 warpedNew = texture(uNewTex, uvNew);

    // Mixing: fade into a shared vortex, then unwhirl to the final frame.
    //  - Centre reveals first once the vortex has formed
    //  - Outer ring follows a bit later
    //  - Global tail guarantees a clean landing on the new image
    // Slightly earlier phases (~10%) so the dissolve feels a bit snappier.
    float centrePhase = smoothstep(0.16, 0.41, t) * (1.0 - rNorm);
    float ringPhase = smoothstep(0.27, 0.63, t) * smoothstep(0.15, 1.0, rNorm);
    float tailPhase = smoothstep(0.72, 0.94, t);
    float mixFactor = clamp(max(max(centrePhase, ringPhase), tailPhase), 0.0, 1.0);

    vec4 color = mix(warpedOld, warpedNew, mixFactor);

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

    // Use the true maximum radius from the centre to the furthest corner so
    // the ripple cleanly reaches the image corners without leaving a thin
    // untransitioned band.
    float maxR = length(vec2(0.5 * aspect, 0.5));
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
    float localMix = smoothstep(-0.04, 0.18, front - rNorm);
    float globalMix = smoothstep(0.78, 0.95, t);
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

    def _create_claws_program(self) -> int:
        """Compile and link the shader program used for Shooting Stars (claws)."""

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
uniform float u_density;
uniform vec2 u_direction;
uniform float u_length;
uniform float u_width;

float hash1(float n) {
    return fract(sin(n) * 43758.5453123);
}

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    vec2 dir = u_direction;
    if (length(dir) < 1e-3) {
        dir = normalize(vec2(0.8, -1.0));
    } else {
        dir = normalize(dir);
    }
    vec2 perpDir = vec2(-dir.y, dir.x);

    vec2 p = uv - vec2(0.5, 0.5);
    float along = dot(p, dir) + 0.5;
    float across = dot(p, perpDir) + 0.5;

    float density = max(u_density, 1.0);
    float stripeIndex = floor(across * density);
    float stripeLocal = fract(across * density) - 0.5;

    float rnd = hash1(stripeIndex * 37.0 + 13.0);
    float start = rnd * 0.7;
    float span = 0.25 + rnd * 0.25;
    float localT = (t - start) / max(span, 1e-3);

    float streakMask = 0.0;
    if (localT > 0.0 && localT < 1.0) {
        float head = localT * (1.1 + rnd * 0.3);
        float halfLen = u_length;
        float distAlong = along - head;
        float core = 1.0 - smoothstep(halfLen, halfLen * 1.6, abs(distAlong));

        float halfWidth = u_width;
        float distAcross = stripeLocal;
        float widthMask = 1.0 - smoothstep(halfWidth, halfWidth * 1.6, abs(distAcross));

        streakMask = clamp(core * widthMask, 0.0, 1.0);
    }

    float globalMix = smoothstep(0.75, 1.0, t);
    float baseMix = max(globalMix, t);
    vec4 base = mix(oldColor, newColor, baseMix);

    if (streakMask > 0.0) {
        float starMix = clamp(0.6 + 0.4 * t, 0.0, 1.0);
        vec4 streakCol = mix(base, newColor, starMix);
        streakCol.rgb += vec3(0.35) * streakMask;
        base = mix(base, streakCol, streakMask);
    }

    FragColor = base;
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
                logger.debug("[GL SHADER] Failed to link claws program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link claws program: {log!r}")
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

    def _can_use_simple_shader(self, state: object, program_id: int) -> bool:
        """Shared capability check for simple fullscreen quad shaders.

        Used by Ripple (raindrops), Warp Dissolve and Shooting Stars, which
        all draw a single quad over the full compositor surface.
        """

        if self._gl_disabled_for_session or gl is None:
            return False
        if self._gl_pipeline is None or not self._gl_pipeline.initialized:
            return False
        if state is None:
            return False
        if not program_id:
            return False
        return True

    def _can_use_warp_shader(self) -> bool:
        return self._can_use_simple_shader(self._warp, getattr(self._gl_pipeline, "warp_program", 0))

    def _can_use_raindrops_shader(self) -> bool:
        return self._can_use_simple_shader(self._raindrops, self._gl_pipeline.raindrops_program)

    def _can_use_shuffle_shader(self) -> bool:
        return self._can_use_simple_shader(self._shuffle, getattr(self._gl_pipeline, "shuffle_program", 0))

    def _can_use_claws_shader(self) -> bool:
        # Shooting Stars / Claw Marks shader path is hard-disabled. The user
        # has elected to remove this effect, and any remaining "Claw Marks"
        # requests are routed through a CPU crossfade instead. Keeping this
        # function returning False ensures the GLSL claws program is never
        # used even if it is still compiled in the pipeline.
        return False

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

    def _release_transition_textures(self) -> None:
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

        self._release_transition_textures()

        try:
            self._gl_pipeline.old_tex_id = self._upload_texture_from_pixmap(old_pixmap)
            self._gl_pipeline.new_tex_id = self._upload_texture_from_pixmap(new_pixmap)
        except Exception:
            logger.debug("[GL SHADER] Failed to upload transition textures", exc_info=True)
            self._release_transition_textures()
            self._gl_disabled_for_session = True
            self._use_shaders = False
            return False

        if not self._gl_pipeline.old_tex_id or not self._gl_pipeline.new_tex_id:
            self._release_transition_textures()
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

    def _prepare_warp_textures(self) -> bool:
        if not self._can_use_warp_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._warp is None:
            return False
        st = self._warp
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_raindrops_textures(self) -> bool:
        if not self._can_use_raindrops_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._raindrops is None:
            return False
        st = self._raindrops
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_shuffle_textures(self) -> bool:
        if not self._can_use_shuffle_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._shuffle is None:
            return False
        st = self._shuffle
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

        st = self._blockspin
        base_p = max(0.0, min(1.0, float(st.progress)))

        def _spin_from_progress(p: float) -> float:
            """Map 0..1 timeline to spin progress with eased endpoints.

            The curve lingers slightly near 0/1 and crosses 0.5 more quickly
            so slabs spend less time edge-on and more time close to face-on.
            """

            if p <= 0.03:
                return 0.0
            if p >= 0.97:
                return 1.0

            t = (p - 0.03) / 0.94
            # Smoothstep-style easing: 0..1 -> 0..1 with low slope at the
            # endpoints and higher slope around the midpoint.
            return t * t * (3.0 - 2.0 * t)

        aspect = float(w) / float(h)

        gl.glViewport(0, 0, vp_w, vp_h)
        # Enable depth testing so the front face of the slab properly occludes
        # the back face; this avoids seeing both images blended through each
        # other mid-spin.
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthMask(gl.GL_TRUE)

        # Clear to a mathematically black background so the spinning slab and
        # its rim/sheens stand out crisply against the void.
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)

        # Then draw the rotating slab (box) on top using the card-flip program.
        gl.glUseProgram(self._gl_pipeline.basic_program)
        try:
            if self._gl_pipeline.u_aspect_loc != -1:
                gl.glUniform1f(self._gl_pipeline.u_aspect_loc, float(aspect))

            axis_mode = 0
            if st.direction in (SlideDirection.UP, SlideDirection.DOWN):
                axis_mode = 1
            if self._gl_pipeline.u_axis_mode_loc != -1:
                gl.glUniform1i(self._gl_pipeline.u_axis_mode_loc, int(axis_mode))

            # Specular line travel direction: by default move from left edge
            # to right edge over the course of the spin; flip for RIGHT/DOWN
            # directions so the line traverses in the opposite sense.
            spin_dir = 1.0
            if st.direction in (SlideDirection.RIGHT, SlideDirection.DOWN):
                spin_dir = -1.0
            if self._gl_pipeline.u_spec_dir_loc != -1:
                gl.glUniform1f(self._gl_pipeline.u_spec_dir_loc, float(spin_dir))

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
            use_box = getattr(self._gl_pipeline, "box_vao", 0) and getattr(self._gl_pipeline, "box_vertex_count", 0) > 0

            # Configure a helper to issue a single slab draw with caller-supplied
            # angle and placement.
            def _draw_slab(angle_rad: float, block_rect: tuple[float, float, float, float], uv_rect: tuple[float, float, float, float]) -> None:
                if self._gl_pipeline.u_angle_loc != -1:
                    gl.glUniform1f(self._gl_pipeline.u_angle_loc, float(angle_rad))
                if self._gl_pipeline.u_block_rect_loc != -1:
                    gl.glUniform4f(self._gl_pipeline.u_block_rect_loc, *[float(v) for v in block_rect])
                if self._gl_pipeline.u_block_uv_rect_loc != -1:
                    gl.glUniform4f(self._gl_pipeline.u_block_uv_rect_loc, *[float(v) for v in uv_rect])

                if use_box:
                    gl.glBindVertexArray(self._gl_pipeline.box_vao)
                    gl.glDrawArrays(gl.GL_TRIANGLES, 0, int(self._gl_pipeline.box_vertex_count))
                    gl.glBindVertexArray(0)
                else:
                    gl.glBindVertexArray(self._gl_pipeline.quad_vao)
                    gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
                    gl.glBindVertexArray(0)

            # Single full-frame slab. Direction is applied as a sign on the
            # spin so LEFT/RIGHT and UP/DOWN produce mirrored rotations while
            # still ending on the same final orientation.
            spin = _spin_from_progress(base_p)
            angle = math.pi * spin * spin_dir
            full_rect = (-1.0, -1.0, 1.0, 1.0)
            full_uv = (0.0, 0.0, 1.0, 1.0)
            _draw_slab(angle, full_rect, full_uv)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_claws_shader(self, target: QRect) -> None:
        if not self._can_use_claws_shader() or self._gl_pipeline is None or self._shooting_stars is None:
            return
        st = self._shooting_stars
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_pair_textures(st.old_pixmap, st.new_pixmap):
            return

        vp_w, vp_h = self._get_viewport_size()
        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.claws_program)
        try:
            if self._gl_pipeline.claws_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.claws_u_progress, float(p))

            if self._gl_pipeline.claws_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.claws_u_resolution, float(vp_w), float(vp_h))

            stripe_count = float(max(10.0, min(32.0, vp_w / 96.0)))
            if self._gl_pipeline.claws_u_density != -1:
                gl.glUniform1f(self._gl_pipeline.claws_u_density, stripe_count)

            if self._gl_pipeline.claws_u_direction != -1:
                gl.glUniform2f(self._gl_pipeline.claws_u_direction, 0.9, -0.45)

            if self._gl_pipeline.claws_u_length != -1:
                gl.glUniform1f(self._gl_pipeline.claws_u_length, 0.35)

            if self._gl_pipeline.claws_u_width != -1:
                width = 0.18 / max(stripe_count, 1.0)
                gl.glUniform1f(self._gl_pipeline.claws_u_width, float(width))

            if self._gl_pipeline.claws_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.claws_u_old_tex, 0)
            if self._gl_pipeline.claws_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.claws_u_new_tex, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_shuffle_shader(self, target: QRect) -> None:
        if not self._can_use_shuffle_shader() or self._gl_pipeline is None or self._shuffle is None:
            return
        st = self._shuffle
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_shuffle_textures():
            return

        vp_w, vp_h = self._get_viewport_size()

        float_cols = float(max(1, int(st.cols)))
        float_rows = float(max(1, int(st.rows)))
        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.shuffle_program)
        try:
            if self._gl_pipeline.shuffle_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.shuffle_u_progress, float(p))

            if self._gl_pipeline.shuffle_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.shuffle_u_resolution, float(vp_w), float(vp_h))

            if self._gl_pipeline.shuffle_u_grid != -1:
                gl.glUniform2f(self._gl_pipeline.shuffle_u_grid, float_cols, float_rows)

            # Map encoded edge string to a simple cardinal direction vector.
            dx = 1.0
            dy = 0.0
            edge = st.edge or "L2R"
            if edge == "L2R":
                dx = 1.0
                dy = 0.0
            elif edge == "R2L":
                dx = -1.0
                dy = 0.0
            elif edge == "T2B":
                dx = 0.0
                dy = 1.0
            elif edge == "B2T":
                dx = 0.0
                dy = -1.0
            if self._gl_pipeline.shuffle_u_direction != -1:
                gl.glUniform2f(self._gl_pipeline.shuffle_u_direction, float(dx), float(dy))

            if self._gl_pipeline.shuffle_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.shuffle_u_old_tex, 0)
            if self._gl_pipeline.shuffle_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.shuffle_u_new_tex, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)
            gl.glDisable(gl.GL_DEPTH_TEST)
            gl.glDisable(gl.GL_DEPTH_TEST)

    def _paint_warp_shader(self, target: QRect) -> None:
        if not self._can_use_warp_shader() or self._gl_pipeline is None or self._warp is None:
            return
        st = self._warp
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_warp_textures():
            return

        vp_w, vp_h = self._get_viewport_size()

        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.warp_program)
        try:
            if self._gl_pipeline.warp_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.warp_u_progress, float(p))

            if self._gl_pipeline.warp_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.warp_u_resolution, float(vp_w), float(vp_h))

            if self._gl_pipeline.warp_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.warp_u_old_tex, 0)
            if self._gl_pipeline.warp_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.warp_u_new_tex, 1)

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
        if not self._prepare_raindrops_textures():
            # Texture upload helper currently uses the shared old/new texture
            # slots; on failure we simply skip the shader path.
            return

        vp_w, vp_h = self._get_viewport_size()

        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.raindrops_program)
        try:
            # Per-frame uniforms now use cached locations from _GLPipelineState.
            if self._gl_pipeline.raindrops_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.raindrops_u_progress, float(p))

            if self._gl_pipeline.raindrops_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.raindrops_u_resolution, float(vp_w), float(vp_h))

            if self._gl_pipeline.raindrops_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.raindrops_u_old_tex, 0)
            if self._gl_pipeline.raindrops_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.raindrops_u_new_tex, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_debug_overlay(self, painter: QPainter) -> None:
        if not is_perf_metrics_enabled():
            return

        active_label = None
        line1 = ""
        line2 = ""

        if (
            self._slide is not None
            and self._slide_profile_start_ts is not None
            and self._slide_profile_last_ts is not None
            and self._slide_profile_frame_count > 0
        ):
            elapsed = self._slide_profile_last_ts - self._slide_profile_start_ts
            if elapsed > 0.0:
                fps = self._slide_profile_frame_count / elapsed
                active_label = "Slide"
                line1 = f"{active_label} t={self._slide.progress:.2f}"
                dt_min_ms = self._slide_profile_min_dt * 1000.0 if self._slide_profile_min_dt > 0.0 else 0.0
                dt_max_ms = self._slide_profile_max_dt * 1000.0 if self._slide_profile_max_dt > 0.0 else 0.0
                line2 = f"{fps:.1f} fps  dt_min={dt_min_ms:.1f}ms  dt_max={dt_max_ms:.1f}ms"

        if (
            active_label is None
            and self._wipe is not None
            and self._wipe_profile_start_ts is not None
            and self._wipe_profile_last_ts is not None
            and self._wipe_profile_frame_count > 0
        ):
            elapsed = self._wipe_profile_last_ts - self._wipe_profile_start_ts
            if elapsed > 0.0:
                fps = self._wipe_profile_frame_count / elapsed
                active_label = "Wipe"
                line1 = f"{active_label} t={self._wipe.progress:.2f}"
                dt_min_ms = self._wipe_profile_min_dt * 1000.0 if self._wipe_profile_min_dt > 0.0 else 0.0
                dt_max_ms = self._wipe_profile_max_dt * 1000.0 if self._wipe_profile_max_dt > 0.0 else 0.0
                line2 = f"{fps:.1f} fps  dt_min={dt_min_ms:.1f}ms  dt_max={dt_max_ms:.1f}ms"

        if not active_label:
            return

        painter.save()
        try:
            text = line1 if not line2 else line1 + "\n" + line2
            fm = painter.fontMetrics()
            lines = text.split("\n")
            max_width = 0
            for s in lines:
                w = fm.horizontalAdvance(s)
                if w > max_width:
                    max_width = w
            line_height = fm.height()
            margin = 6
            rect_height = line_height * len(lines) + margin * 2
            rect_width = max_width + margin * 2
            rect = QRect(margin, margin, rect_width, rect_height)
            painter.fillRect(rect, QColor(0, 0, 0, 160))
            painter.setPen(Qt.GlobalColor.white)
            y = margin + fm.ascent()
            for s in lines:
                painter.drawText(margin + 4, y, s)
                y += line_height
        finally:
            painter.restore()

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

        # Shuffle shader path: when enabled and the GLSL pipeline is
        # available, draw the Shuffle mask entirely in GLSL. On failure we
        # disable shader usage for the session and fall back to the
        # compositor's existing QPainter-based transitions for this run.
        if self._shuffle is not None and self._can_use_shuffle_shader():
            try:
                self._paint_shuffle_shader(target)
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader shuffle path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader shuffle path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        # Shooting Stars (claws) shader path: when enabled and the GLSL
        # pipeline is available, draw the streak field entirely in GLSL. On
        # failure we disable shader usage for the session and fall back to the
        # compositor's existing QPainter-based transitions.
        if self._shooting_stars is not None and self._can_use_claws_shader():
            try:
                self._paint_claws_shader(target)
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader shooting-stars path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader shooting-stars path failed; disabling shader pipeline",
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

                    # Opacity falloff: keep strips opaque in the early part of
                    # their lifetime, then fade them out as they drift away so
                    # they do not "snap" off-screen.
                    float_alpha = 1.0
                    if local > 0.5:
                        float_alpha = 1.0 - min(1.0, (local - 0.5) / 0.5)
                    if float_alpha <= 0.0:
                        continue

                    painter.save()
                    painter.setClipRect(rect)
                    painter.setOpacity(float_alpha)
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
                self._paint_debug_overlay(painter)
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
                    self._paint_debug_overlay(painter)
                    return
                if t >= 1.0:
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                    self._paint_debug_overlay(painter)
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
                self._paint_debug_overlay(painter)
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
                self._paint_debug_overlay(painter)
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
                self._paint_debug_overlay(painter)
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
                self._paint_debug_overlay(painter)
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
                self._paint_debug_overlay(painter)
                return

            # No active transition -> draw base pixmap if present.
            if self._base_pixmap is not None and not self._base_pixmap.isNull():
                painter.setOpacity(1.0)
                painter.drawPixmap(target, self._base_pixmap)
            else:
                # As a last resort, fill black.
                painter.fillRect(target, Qt.GlobalColor.black)

            self._paint_debug_overlay(painter)
        finally:
            painter.end()
