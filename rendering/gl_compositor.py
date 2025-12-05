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

from dataclasses import dataclass, field
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
    cols: int = 0
    rows: int = 0
    direction: Optional[SlideDirection] = None


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
    diffuse_program: int = 0
    blockflip_program: int = 0
    peel_program: int = 0
    claws_program: int = 0
    shuffle_program: int = 0
    crossfade_program: int = 0
    slide_program: int = 0
    wipe_program: int = 0
    blinds_program: int = 0

    # Textures for the current pair of images being blended/transitioned.
    old_tex_id: int = 0
    new_tex_id: int = 0
    # Small per-pixmap texture cache keyed by QPixmap.cacheKey() so
    # shader-backed transitions can reuse GPU textures across frames and
    # transitions instead of re-uploading from CPU memory each time.
    texture_cache: dict[int, int] = field(default_factory=dict)
    texture_lru: list[int] = field(default_factory=list)

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

    # Cached uniform locations for the Diffuse shader program.
    diffuse_u_progress: int = -1
    diffuse_u_resolution: int = -1
    diffuse_u_old_tex: int = -1
    diffuse_u_new_tex: int = -1
    diffuse_u_grid: int = -1
    diffuse_u_shape_mode: int = -1

    # Cached uniform locations for the BlockFlip shader program.
    blockflip_u_progress: int = -1
    blockflip_u_resolution: int = -1
    blockflip_u_old_tex: int = -1
    blockflip_u_new_tex: int = -1
    blockflip_u_grid: int = -1
    blockflip_u_direction: int = -1

    # Cached uniform locations for the Peel shader program.
    peel_u_progress: int = -1
    peel_u_resolution: int = -1
    peel_u_old_tex: int = -1
    peel_u_new_tex: int = -1
    peel_u_direction: int = -1
    peel_u_strips: int = -1

    # Cached uniform locations for the Blinds shader program.
    blinds_u_progress: int = -1
    blinds_u_resolution: int = -1
    blinds_u_old_tex: int = -1
    blinds_u_new_tex: int = -1
    blinds_u_grid: int = -1

    # Cached uniform locations for the Shuffle shader program.
    shuffle_u_progress: int = -1
    shuffle_u_resolution: int = -1
    shuffle_u_old_tex: int = -1
    shuffle_u_new_tex: int = -1
    shuffle_u_grid: int = -1
    shuffle_u_direction: int = -1
    crossfade_u_progress: int = -1
    crossfade_u_resolution: int = -1
    crossfade_u_old_tex: int = -1
    crossfade_u_new_tex: int = -1
    slide_u_progress: int = -1
    slide_u_resolution: int = -1
    slide_u_old_tex: int = -1
    slide_u_new_tex: int = -1
    slide_u_old_rect: int = -1
    slide_u_new_rect: int = -1
    wipe_u_progress: int = -1
    wipe_u_resolution: int = -1
    wipe_u_old_tex: int = -1
    wipe_u_new_tex: int = -1
    wipe_u_mode: int = -1

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
    cols: int = 0
    rows: int = 0


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
    # Optional grid hints for shader-backed Diffuse paths. When non-zero,
    # these represent the logical (cols, rows) block grid used by the shader
    # to mirror the CPU/region-based Diffuse layout.
    cols: int = 0
    rows: int = 0
    # Integer shape mode for GLSL diffuse. 0 = Rectangle, 1 = Membrane,
    # 2 = Circle, 3 = Diamond, 4 = Plus, 5 = Triangle.
    shape_mode: int = 0


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

        # Smoothed Spotify visualiser state pushed from DisplayWidget. When
        # present, bars are rendered as a thin overlay above the current
        # image/transition but below the PERF HUD.
        self._spotify_vis_enabled: bool = False
        self._spotify_vis_rect: Optional[QRect] = None
        self._spotify_vis_bars = None
        self._spotify_vis_bar_count: int = 0
        self._spotify_vis_segments: int = 0
        self._spotify_vis_fill_color: Optional[QColor] = None
        self._spotify_vis_border_color: Optional[QColor] = None
        self._spotify_vis_fade: float = 0.0

    # ------------------------------------------------------------------
    # Public API used by DisplayWidget / transitions
    # ------------------------------------------------------------------

    def set_base_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        """Set the base image when no transition is active."""
        self._base_pixmap = pixmap
        # If no crossfade is active, repaint immediately.
        if self._crossfade is None:
            self.update()

    def set_spotify_visualizer_state(
        self,
        rect: QRect,
        bars,
        bar_count: int,
        segments: int,
        fill_color: QColor,
        border_color: QColor,
        fade: float,
        playing: bool,
        visible: bool,
    ) -> None:
        """Update Spotify bar overlay state pushed from DisplayWidget.

        When ``visible`` is False or the geometry is invalid, the overlay is
        disabled. Otherwise the smoothed bar values are clamped into [0, 1]
        and cached so they can be drawn after the base image/transition but
        before the PERF HUD.
        """

        if not visible:
            self._spotify_vis_enabled = False
            return

        try:
            count = int(bar_count)
        except Exception:
            count = 0
        try:
            segs = int(segments)
        except Exception:
            segs = 0

        if count <= 0 or segs <= 0:
            self._spotify_vis_enabled = False
            return

        try:
            bars_seq = list(bars)
        except Exception:
            self._spotify_vis_enabled = False
            return

        if not bars_seq:
            self._spotify_vis_enabled = False
            return

        if len(bars_seq) > count:
            bars_seq = bars_seq[:count]
        elif len(bars_seq) < count:
            bars_seq = bars_seq + [0.0] * (count - len(bars_seq))

        clamped = []
        for v in bars_seq:
            try:
                f = float(v)
            except Exception:
                f = 0.0
            if f < 0.0:
                f = 0.0
            if f > 1.0:
                f = 1.0
            clamped.append(f)

        if not clamped:
            self._spotify_vis_enabled = False
            return

        self._spotify_vis_enabled = True
        self._spotify_vis_rect = QRect(rect)
        self._spotify_vis_bars = clamped
        self._spotify_vis_bar_count = len(clamped)
        self._spotify_vis_segments = max(1, segs)
        self._spotify_vis_fill_color = QColor(fill_color)
        self._spotify_vis_border_color = QColor(border_color)
        try:
            self._spotify_vis_fade = max(0.0, min(1.0, float(fade)))
        except Exception:
            self._spotify_vis_fade = 1.0

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
        grid_cols: Optional[int] = None,
        grid_rows: Optional[int] = None,
        direction: Optional[SlideDirection] = None,
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
            cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
            rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
            direction=direction,
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

            # Keep BlockFlipState.progress in sync with the animation
            # timeline so both the QPainter and any future GLSL paths see a
            # consistent value.
            try:
                if self._blockflip is not None:
                    p = max(0.0, min(1.0, float(progress)))
                    self._blockflip.progress = p
            except Exception:
                pass

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
        grid_cols: Optional[int] = None,
        grid_rows: Optional[int] = None,
        shape: Optional[str] = None,
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

        # Map the provided shape name (if any) to a small integer used by the
        # GLSL diffuse shader. Rectangle remains the default; additional
        # shapes are reserved for future GLSL work.
        shape_mode = 0
        if shape:
            try:
                key = shape.strip().lower()
            except Exception:
                key = "rectangle"
            if key == "membrane":
                shape_mode = 1
            elif key == "circle":
                shape_mode = 2
            elif key == "diamond":
                shape_mode = 3
            elif key == "plus":
                shape_mode = 4

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
            cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
            rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
            shape_mode=int(shape_mode),
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

            # Keep DiffuseState.progress in sync with the animation timeline so
            # both the QPainter and GLSL paths see a consistent progress value.
            try:
                if self._diffuse is not None:
                    p = max(0.0, min(1.0, float(progress)))
                    self._diffuse.progress = p
            except Exception:
                pass

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
        grid_cols: Optional[int] = None,
        grid_rows: Optional[int] = None,
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
            cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
            rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
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

            # Keep BlindsState.progress in sync with the animation timeline so
            # both the QPainter and any future GLSL paths see a consistent
            # progress value.
            try:
                if self._blinds is not None:
                    p = max(0.0, min(1.0, float(progress)))
                    self._blinds.progress = p
            except Exception:
                pass

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
            # Emit a concise profiling summary for the Ripple shader path so
            # future fidelity-oriented tuning has FPS telemetry without
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
                                "[PERF] [GL COMPOSITOR] Ripple metrics: duration=%.1fms, frames=%d, "
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
                    logger.debug("[GL COMPOSITOR] Ripple metrics logging failed: %s", e, exc_info=True)

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
                logger.debug("[GL COMPOSITOR] Ripple complete update failed (likely after deletion): %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Ripple complete handler failed: %s", e, exc_info=True)

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

            # Compile the Diffuse shader program. On failure we disable shader
            # usage for this session so that all shader-backed transitions fall
            # back to the compositor's QPainter-based paths.
            try:
                dp = self._create_diffuse_program()
                self._gl_pipeline.diffuse_program = dp
                self._gl_pipeline.diffuse_u_progress = gl.glGetUniformLocation(dp, "u_progress")
                self._gl_pipeline.diffuse_u_resolution = gl.glGetUniformLocation(dp, "u_resolution")
                self._gl_pipeline.diffuse_u_old_tex = gl.glGetUniformLocation(dp, "uOldTex")
                self._gl_pipeline.diffuse_u_new_tex = gl.glGetUniformLocation(dp, "uNewTex")
                self._gl_pipeline.diffuse_u_grid = gl.glGetUniformLocation(dp, "u_grid")
                self._gl_pipeline.diffuse_u_shape_mode = gl.glGetUniformLocation(dp, "u_shapeMode")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize diffuse shader program", exc_info=True)
                self._gl_pipeline.diffuse_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the BlockFlip shader program. On failure we disable
            # shader usage for this session so that all shader-backed
            # transitions fall back to the compositor's QPainter-based paths.
            try:
                bfp = self._create_blockflip_program()
                self._gl_pipeline.blockflip_program = bfp
                self._gl_pipeline.blockflip_u_progress = gl.glGetUniformLocation(bfp, "u_progress")
                self._gl_pipeline.blockflip_u_resolution = gl.glGetUniformLocation(bfp, "u_resolution")
                self._gl_pipeline.blockflip_u_old_tex = gl.glGetUniformLocation(bfp, "uOldTex")
                self._gl_pipeline.blockflip_u_new_tex = gl.glGetUniformLocation(bfp, "uNewTex")
                self._gl_pipeline.blockflip_u_grid = gl.glGetUniformLocation(bfp, "u_grid")
                self._gl_pipeline.blockflip_u_direction = gl.glGetUniformLocation(bfp, "u_direction")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize blockflip shader program", exc_info=True)
                self._gl_pipeline.blockflip_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Peel shader program. On failure we disable shader
            # usage for this session so that all shader-backed transitions
            # fall back to the compositor's QPainter-based paths.
            try:
                pp = self._create_peel_program()
                self._gl_pipeline.peel_program = pp
                self._gl_pipeline.peel_u_progress = gl.glGetUniformLocation(pp, "u_progress")
                self._gl_pipeline.peel_u_resolution = gl.glGetUniformLocation(pp, "u_resolution")
                self._gl_pipeline.peel_u_old_tex = gl.glGetUniformLocation(pp, "uOldTex")
                self._gl_pipeline.peel_u_new_tex = gl.glGetUniformLocation(pp, "uNewTex")
                self._gl_pipeline.peel_u_direction = gl.glGetUniformLocation(pp, "u_direction")
                self._gl_pipeline.peel_u_strips = gl.glGetUniformLocation(pp, "u_strips")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize peel shader program", exc_info=True)
                self._gl_pipeline.peel_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            try:
                xp = self._create_crossfade_program()
                self._gl_pipeline.crossfade_program = xp
                self._gl_pipeline.crossfade_u_progress = gl.glGetUniformLocation(xp, "u_progress")
                self._gl_pipeline.crossfade_u_resolution = gl.glGetUniformLocation(xp, "u_resolution")
                self._gl_pipeline.crossfade_u_old_tex = gl.glGetUniformLocation(xp, "uOldTex")
                self._gl_pipeline.crossfade_u_new_tex = gl.glGetUniformLocation(xp, "uNewTex")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize crossfade shader program", exc_info=True)
                self._gl_pipeline.crossfade_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            try:
                slp = self._create_slide_program()
                self._gl_pipeline.slide_program = slp
                self._gl_pipeline.slide_u_progress = gl.glGetUniformLocation(slp, "u_progress")
                self._gl_pipeline.slide_u_resolution = gl.glGetUniformLocation(slp, "u_resolution")
                self._gl_pipeline.slide_u_old_tex = gl.glGetUniformLocation(slp, "uOldTex")
                self._gl_pipeline.slide_u_new_tex = gl.glGetUniformLocation(slp, "uNewTex")
                self._gl_pipeline.slide_u_old_rect = gl.glGetUniformLocation(slp, "u_oldRect")
                self._gl_pipeline.slide_u_new_rect = gl.glGetUniformLocation(slp, "u_newRect")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize slide shader program", exc_info=True)
                self._gl_pipeline.slide_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            try:
                wp2 = self._create_wipe_program()
                self._gl_pipeline.wipe_program = wp2
                self._gl_pipeline.wipe_u_progress = gl.glGetUniformLocation(wp2, "u_progress")
                self._gl_pipeline.wipe_u_resolution = gl.glGetUniformLocation(wp2, "u_resolution")
                self._gl_pipeline.wipe_u_old_tex = gl.glGetUniformLocation(wp2, "uOldTex")
                self._gl_pipeline.wipe_u_new_tex = gl.glGetUniformLocation(wp2, "uNewTex")
                self._gl_pipeline.wipe_u_mode = gl.glGetUniformLocation(wp2, "u_mode")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize wipe shader program", exc_info=True)
                self._gl_pipeline.wipe_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Blinds shader program. On failure we disable shader
            # usage for this session so that all shader-backed transitions fall
            # back to the compositor's QPainter-based paths.
            try:
                bp = self._create_blinds_program()
                self._gl_pipeline.blinds_program = bp
                self._gl_pipeline.blinds_u_progress = gl.glGetUniformLocation(bp, "u_progress")
                self._gl_pipeline.blinds_u_resolution = gl.glGetUniformLocation(bp, "u_resolution")
                self._gl_pipeline.blinds_u_old_tex = gl.glGetUniformLocation(bp, "uOldTex")
                self._gl_pipeline.blinds_u_new_tex = gl.glGetUniformLocation(bp, "uNewTex")
                self._gl_pipeline.blinds_u_grid = gl.glGetUniformLocation(bp, "u_grid")
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize blinds shader program", exc_info=True)
                self._gl_pipeline.blinds_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Shuffle shader program. On failure we disable shader
            # usage for this session so that all shader-backed transitions fall
            # back to the compositor's QPainter-based paths (Group A ￾ Group C
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
                self._gl_pipeline.diffuse_program = 0
                self._gl_pipeline.blockflip_program = 0
                self._gl_pipeline.peel_program = 0
                self._gl_pipeline.shuffle_program = 0
                self._gl_pipeline.claws_program = 0
                self._gl_pipeline.crossfade_program = 0
                self._gl_pipeline.slide_program = 0
                self._gl_pipeline.wipe_program = 0
                self._gl_pipeline.blinds_program = 0
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
            self._gl_pipeline.diffuse_program = 0
            self._gl_pipeline.blockflip_program = 0
            self._gl_pipeline.peel_program = 0
            self._gl_pipeline.shuffle_program = 0
            self._gl_pipeline.claws_program = 0
            self._gl_pipeline.crossfade_program = 0
            self._gl_pipeline.slide_program = 0
            self._gl_pipeline.wipe_program = 0
            self._gl_pipeline.blinds_program = 0
            self._gl_pipeline.quad_vao = 0
            self._gl_pipeline.quad_vbo = 0
            self._gl_pipeline.box_vao = 0
            self._gl_pipeline.box_vbo = 0
            self._gl_pipeline.box_vertex_count = 0
            self._gl_pipeline.initialized = False
            return

        try:
            self._release_transition_textures()

            # Delete any cached textures and clear the cache.
            try:
                cache = getattr(self._gl_pipeline, "texture_cache", None)
                if cache:
                    ids = [int(t) for t in cache.values() if t]
                    if ids:
                        arr = (ctypes.c_uint * len(ids))(*ids)
                        gl.glDeleteTextures(len(ids), arr)
                    cache.clear()
                lru = getattr(self._gl_pipeline, "texture_lru", None)
                if isinstance(lru, list):
                    lru.clear()
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to delete cached textures", exc_info=True)

            try:
                if self._gl_pipeline.basic_program:
                    gl.glDeleteProgram(int(self._gl_pipeline.basic_program))
                if getattr(self._gl_pipeline, "raindrops_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.raindrops_program))
                if getattr(self._gl_pipeline, "warp_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.warp_program))
                if getattr(self._gl_pipeline, "diffuse_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.diffuse_program))
                if getattr(self._gl_pipeline, "blockflip_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.blockflip_program))
                if getattr(self._gl_pipeline, "shuffle_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.shuffle_program))
                if getattr(self._gl_pipeline, "claws_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.claws_program))
                if getattr(self._gl_pipeline, "crossfade_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.crossfade_program))
                if getattr(self._gl_pipeline, "slide_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.slide_program))
                if getattr(self._gl_pipeline, "wipe_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.wipe_program))
                if getattr(self._gl_pipeline, "blinds_program", 0):
                    gl.glDeleteProgram(int(self._gl_pipeline.blinds_program))
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
            self._gl_pipeline.diffuse_program = 0
            self._gl_pipeline.shuffle_program = 0
            self._gl_pipeline.claws_program = 0
            self._gl_pipeline.crossfade_program = 0
            self._gl_pipeline.slide_program = 0
            self._gl_pipeline.wipe_program = 0
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

    def _create_peel_program(self) -> int:
        """Compile and link the shader program used for Peel.

        Peel is implemented as a fullscreen-quad shader that always draws the
        new image as the stable base frame while strips of the old image slide
        and fade away along a configured direction. Each logical strip has a
        small per-strip timing offset so the wave feels organic rather than
        perfectly synchronous.
        """

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
uniform vec2 u_direction;  // peel travel direction
uniform float u_strips;    // logical strip count

float hash1(float n) {
    return fract(sin(n) * 43758.5453123);
}

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    if (t <= 0.0) {
        FragColor = oldColor;
        return;
    }
    if (t >= 1.0) {
        FragColor = newColor;
        return;
    }

    // Normalised peel direction.
    vec2 dir = u_direction;
    if (length(dir) < 1e-3) {
        dir = vec2(1.0, 0.0);
    } else {
        dir = normalize(dir);
    }

    float strips = max(u_strips, 1.0);

    // Choose a 1D coordinate along the strip index. To mirror the CPU
    // compositor we always order strips from left→right (horizontal) or
    // top→bottom (vertical), independent of peel direction.
    bool horizontal = abs(dir.x) >= abs(dir.y);
    float axisCoord = horizontal ? uv.x : uv.y;

    axisCoord = clamp(axisCoord, 0.0, 1.0);
    float stripIndex = floor(axisCoord * strips + 1e-4);

    // Sequential per-strip timing similar to the CPU compositor path: early
    // strips start earlier, later strips start later but all complete by
    // t = 1.0.
    float start = 0.0;
    if (strips > 1.0) {
        float delay_per_strip = 0.7 / (strips - 1.0);
        start = delay_per_strip * stripIndex;
    }

    float local;
    if (t <= start) {
        local = 0.0;
    } else {
        float span = max(1.0 - start, 1e-4);
        local = clamp((t - start) / span, 0.0, 1.0);
    }

    // Local coordinate within this logical strip in [0,1). At the start of
    // the animation each strip occupies its full segment width so the old
    // image completely covers the new image. As the strip peels away, its
    // visible band narrows toward the centre so the effect feels like thin
    // sheets being pulled off.
    float segPos = fract(axisCoord * strips);
    float baseWidth = 0.6;                      // final fraction of segment used
    float width = mix(1.0, baseWidth, local);   // 1.0 → baseWidth over lifetime
    float halfBand = 0.5 * width;
    float bandMin = 0.5 - halfBand;
    float bandMax = 0.5 + halfBand;
    float inBand = step(bandMin, segPos) * step(segPos, bandMax);

    // If this strip has completely peeled away, only the new image remains.
    if (local >= 1.0) {
        FragColor = newColor;
        return;
    }

    // Slide the strip off-screen along the peel direction. We work in the
    // shifted UV space so both the visible band and the sampled old image
    // move together across the screen, mirroring the CPU painter which
    // translates and clips whole rectangles.
    float travel = 1.4;  // slightly more than the viewport diagonal in UV units
    vec2 shifted = uv - dir * local * travel;

    // Recompute the band mask in shifted space so the geometry of the strip
    // itself travels across the frame.
    float maskCoord = horizontal ? shifted.x : shifted.y;
    float maskCoordClamped = clamp(maskCoord, 0.0, 1.0);
    float segPosShifted = fract(maskCoordClamped * strips);
    float inBandShifted = step(bandMin, segPosShifted) * step(segPosShifted, bandMax);

    // Only sample old image where the shifted strip still overlaps it.
    float inside = 0.0;
    if (shifted.x >= 0.0 && shifted.x <= 1.0 && shifted.y >= 0.0 && shifted.y <= 1.0) {
        inside = 1.0;
    }

    vec4 peeledOld = texture(uOldTex, shifted);

    // Piece-wise opacity: start fading as soon as this strip begins to
    // peel, so each band thins out over its entire lifetime rather than
    // staying fully opaque until late in the animation.
    float alpha = inside * inBandShifted * (1.0 - local);

    // Short global tail so, regardless of local timing, we always land on a
    // pure new image by the end of the transition.
    float tail = smoothstep(0.90, 1.0, t);
    alpha *= (1.0 - tail);

    vec4 color = mix(newColor, peeledOld, clamp(alpha, 0.0, 1.0));
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
                logger.debug("[GL SHADER] Failed to link peel program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link peel program: {log!r}")
        finally:
            gl.glDeleteShader(vert)
            gl.glDeleteShader(frag)

        return int(program)

    def _create_wipe_program(self) -> int:
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
uniform int u_mode;   // 0=L2R,1=R2L,2=T2B,3=B2T,4=Diag TL-BR,5=Diag TR-BL

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    if (t <= 0.0) {
        FragColor = oldColor;
        return;
    }
    if (t >= 1.0) {
        FragColor = newColor;
        return;
    }

    // Compute a scalar axis in [0,1] that the wipe front travels along.
    float axis = 0.0;

    if (u_mode == 0) {
        // Left-to-right
        axis = uv.x;
    } else if (u_mode == 1) {
        // Right-to-left
        axis = 1.0 - uv.x;
    } else if (u_mode == 2) {
        // Top-to-bottom
        axis = uv.y;
    } else if (u_mode == 3) {
        // Bottom-to-top
        axis = 1.0 - uv.y;
    } else if (u_mode == 4) {
        // Diagonal TL-BR: project onto (1,1) and normalise back to 0..1.
        float proj = (uv.x + uv.y) * 0.5;
        axis = clamp(proj, 0.0, 1.0);
    } else if (u_mode == 5) {
        // Diagonal TR-BL: project onto (-1,1).
        float proj = ((1.0 - uv.x) + uv.y) * 0.5;
        axis = clamp(proj, 0.0, 1.0);
    }

    float m = step(axis, t);

    vec4 color = mix(oldColor, newColor, m);
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
                logger.debug("[GL SHADER] Failed to link wipe program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link wipe program: {log!r}")
        finally:
            gl.glDeleteShader(vert)
            gl.glDeleteShader(frag)

        return int(program)

    def _create_diffuse_program(self) -> int:
        """Compile and link the shader program used for Diffuse.

        This is a fullscreen-quad shader that reveals the new image in a
        block-based pattern. Each logical block in a grid receives a hashed
        random threshold so blocks fade in over time rather than switching all
        at once. The controller/config passes the grid via ``u_grid``.
        """

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
uniform int u_shapeMode;    // 0=Rectangle, 1=Membrane

float hash1(float n) {
    return fract(sin(n) * 43758.5453123);
}

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Logical block grid in UV space; fall back to a single block when the
    // grid is not configured.
    vec2 grid = max(u_grid, vec2(1.0));
    vec2 cell = clamp(floor(uv * grid), vec2(0.0), grid - vec2(1.0));
    float cols = grid.x;
    float rows = grid.y;
    float cellIndex = cell.y * cols + cell.x;

    // Per-block randomised reveal threshold in [0, 1]. As t increases from
    // 0→1, more blocks cross their threshold and become visible, giving a
    // long-lived mottled phase instead of a late, compressed switch. Clamp
    // the effective threshold so every block has enough time to fully
    // transition before t=1, and slightly bias thresholds towards earlier
    // times so coverage ramps up more smoothly.
    float rnd = hash1(cellIndex * 37.0 + 13.0);
    float width = 0.18;
    float shaped = pow(rnd, 1.35);
    float threshold = min(shaped, 1.0 - width);

    // Small local smoothing window so blocks do not pop on in a single
    // frame. Width controls how quickly each block fades from old→new once
    // its threshold is reached.
    float local = smoothstep(threshold, threshold + width, t);

    // Local UV inside the current block for shape masks.
    vec2 cellOrigin = cell / grid;
    vec2 cellSize = vec2(1.0) / grid;
    vec2 uvLocal = (uv - cellOrigin) / cellSize; // 0..1 inside block

    // Rectangle (0): whole-block transition using the local timing only.
    float rectMix = local;

    // Per-block shape progress: remains 0 until this block's threshold is
    // reached, then ramps from 0→1 over the remaining global timeline. This
    // keeps the membrane evolving inside each cell instead of synchronising
    // purely to the global time.
    float shapeProgress = 0.0;
    if (t > threshold) {
        float span = max(1e-4, 1.0 - threshold);
        shapeProgress = clamp((t - threshold) / span, 0.0, 1.0);
    }

    vec2 centred = uvLocal - vec2(0.5);
    float baseR = length(centred);

    // Subtle per-cell wobble so membranes read as organic/webbed rather than
    // perfect circles, without introducing harsh noise. The wobble only
    // grows as the shapeProgress advances.
    float wobble = (hash1(cellIndex * 91.0 + 7.0) - 0.5) * 0.20;
    float r = baseR * (1.0 + wobble * shapeProgress);

    // Membrane (1): soft radial membrane that grows over time inside each
    // block. The centre reveals first and expands outward, but the maximum
    // radius stays well below the block corners so a feathered web remains
    // visible until the final global tail.
    float memMinR = 0.10;
    float memMaxR = 0.55;
    float memR = mix(memMinR, memMaxR, shapeProgress);
    float memEdge = 0.60;
    float memInner = max(0.0, memR - memEdge * 0.6);
    float memOuter = memR + memEdge * 0.4;
    float membraneMask = 1.0 - smoothstep(memInner, memOuter, r);
    float membraneMix = local * membraneMask;

    float blockMix = rectMix;
    if (u_shapeMode == 1) {
        blockMix = membraneMix;
    }

    // Short global tail so that, regardless of local jitter, we always land
    // on a pure new image by the end of the transition. For Membrane we
    // also fade out and then fully clamp the block-based contribution in
    // the last few percent so no grid structure survives into the final
    // landing frames.
    float tail;
    if (u_shapeMode == 1) {
        float blockFade = 1.0 - smoothstep(0.84, 0.94, t);
        blockMix *= blockFade;
        tail = smoothstep(0.84, 1.0, t);
        if (t > 0.94) {
            // Once the global tail is dominant, cap any remaining block
            // modulation so the final frames are driven purely by the tail
            // and no per-cell pattern is visible.
            blockMix = min(blockMix, tail);
        }
    } else {
        tail = smoothstep(0.96, 1.0, t);
    }

    float mixFactor = clamp(max(blockMix, tail), 0.0, 1.0);

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
                logger.debug("[GL SHADER] Failed to link diffuse program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link diffuse program: {log!r}")
        finally:
            gl.glDeleteShader(vert)
            gl.glDeleteShader(frag)

        return int(program)

    def _create_blockflip_program(self) -> int:
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
uniform vec2 u_direction;   // slide direction, cardinal

float hash1(float n) {
    return fract(sin(n) * 43758.5453123);
}

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    if (t <= 0.0) {
        FragColor = oldColor;
        return;
    }
    if (t >= 1.0) {
        FragColor = newColor;
        return;
    }

    // Logical block grid in UV space.
    vec2 grid = max(u_grid, vec2(1.0));
    vec2 cell = clamp(floor(uv * grid), vec2(0.0), grid - vec2(1.0));
    float cols = grid.x;
    float rows = grid.y;
    float cellIndex = cell.y * cols + cell.x;

    vec2 cellOrigin = cell / grid;
    vec2 cellSize = vec2(1.0) / grid;
    vec2 uvLocal = (uv - cellOrigin) / cellSize; // 0..1 inside block

    // Direction-aware wave based on the *block* row/column, mirroring the
    // legacy BlockPuzzleFlip controller. This determines when each block
    // begins its flip relative to the chosen edge.
    vec2 dir = u_direction;
    if (length(dir) < 1e-3) {
        dir = vec2(1.0, 0.0);
    } else {
        dir = normalize(dir);
    }

    float colIndex = cell.x;
    float rowIndex = cell.y;
    bool horizontal = abs(dir.x) >= abs(dir.y);

    // Base start timing from the leading edge, matching the CPU
    // BlockPuzzleFlip controller.
    float base = 0.0;
    if (horizontal) {
        // LEFT/RIGHT: wave travels across columns.
        if (dir.x > 0.0) {
            // SlideDirection.LEFT semantics: left→right.
            if (cols > 1.0) {
                base = colIndex / (cols - 1.0);
            }
        } else {
            // SlideDirection.RIGHT semantics: right→left.
            if (cols > 1.0) {
                base = (cols - 1.0 - colIndex) / (cols - 1.0);
            }
        }
    } else {
        // UP/DOWN: wave travels across rows.
        if (dir.y > 0.0) {
            // SlideDirection.DOWN: top→bottom.
            if (rows > 1.0) {
                base = rowIndex / (rows - 1.0);
            }
        } else {
            // SlideDirection.UP: bottom→top.
            if (rows > 1.0) {
                base = (rows - 1.0 - rowIndex) / (rows - 1.0);
            }
        }
    }

    // Center bias: blocks nearer the center of the orthogonal axis begin
    // slightly earlier so the wavefront forms a shallow arrow/curve shape
    // rather than a perfectly straight slit.
    float colNorm = (cols > 1.0) ? colIndex / (cols - 1.0) : 0.5;
    float rowNorm = (rows > 1.0) ? rowIndex / (rows - 1.0) : 0.5;
    float ortho = horizontal ? abs(rowNorm - 0.5) : abs(colNorm - 0.5);
    float centerFactor = (0.5 - ortho) * 2.0; // 1 at center, 0 at edges.
    float centerBiasStrength = 0.25;          // tune: fraction of timeline.
    base -= centerFactor * centerBiasStrength;
    base = clamp(base, 0.0, 1.0);

    // Small jitter so neighbouring blocks do not all start at exactly the
    // same moment; scaled by grid density so the wavefront remains coherent.
    float span = max(cols, rows);
    float jitterSpan = span > 0.0 ? 0.18 / span : 0.0;
    if (jitterSpan > 0.0) {
        base += (hash1(cellIndex * 91.0 + 7.0) - 0.5) * jitterSpan;
    }
    base = clamp(base, 0.0, 1.0);

    float start = clamp(base * 0.9, 0.0, 1.0 - 0.25);
    float end = start + 0.25;

    float local = 0.0;
    if (t >= start) {
        float span = max(end - start, 1e-4);
        local = clamp((t - start) / span, 0.0, 1.0);
    }

    // Cosine-based easing for the apparent flip, mirroring the legacy
    // BlockPuzzleFlip controller: eased in [0, 1] drives the width of a
    // hard-edged central band within each block.
    float eased = 0.5 - 0.5 * cos(local * 3.14159265);

    // Width of the revealed band within this block.
    float w = clamp(eased, 0.0, 1.0);
    float half = 0.5 * w;
    float left = 0.5 - half;
    float right = 0.5 + half;

    // Choose local axis according to the flip direction. For horizontal
    // flips use X inside the block; for vertical flips use Y.
    float coord = horizontal ? uvLocal.x : uvLocal.y;

    // Hard-edged band: pixels inside the band are fully new image, outside
    // are fully old image. No spatial feathering.
    float inBand = step(left, coord) * step(coord, right);

    // Late global tail so any remaining stragglers land cleanly on new even
    // if numerical jitter leaves tiny gaps.
    float tail = smoothstep(0.92, 1.0, t);
    float useNew = clamp(max(inBand, tail), 0.0, 1.0);
    float useOld = 1.0 - useNew;

    vec4 color = oldColor * useOld + newColor * useNew;
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
                logger.debug("[GL SHADER] Failed to link blockflip program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link blockflip program: {log!r}")
        finally:
            gl.glDeleteShader(vert)
            gl.glDeleteShader(frag)

        return int(program)

    def _create_blinds_program(self) -> int:
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

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Logical grid in UV space; when u_grid is unset we fall back to a
    // single full-frame cell so the effect still works.
    vec2 grid = max(u_grid, vec2(1.0));
    vec2 cell = clamp(floor(uv * grid), vec2(0.0), grid - vec2(1.0));

    vec2 cellOrigin = cell / grid;
    vec2 cellSize = vec2(1.0) / grid;
    vec2 uvLocal = (uv - cellOrigin) / cellSize; // 0..1 inside cell

    // Blinds are modelled as a horizontal band within each cell that grows
    // symmetrically from the centre outwards. At t=0 the band is collapsed
    // to a thin line; by t=1 it covers the full cell width.
    float w = clamp(t, 0.0, 1.0);
    float half = 0.5 * w;
    float left = 0.5 - half;
    float right = 0.5 + half;

    // Soft edges so the band does not appear as a harsh 1px stripe.
    float feather = 0.08;
    float edgeL = smoothstep(left - feather, left, uvLocal.x);
    float edgeR = 1.0 - smoothstep(right, right + feather, uvLocal.x);
    float bandMask = clamp(edgeL * edgeR, 0.0, 1.0);

    // Late global tail to guarantee we land on a fully revealed frame even
    // if numerical jitter leaves small gaps in the band coverage.
    float tail = smoothstep(0.96, 1.0, t);
    float mixFactor = clamp(max(bandMask, tail), 0.0, 1.0);

    FragColor = mix(oldColor, newColor, mixFactor);
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
                logger.debug("[GL SHADER] Failed to link blinds program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link blinds program: {log!r}")
        finally:
            gl.glDeleteShader(vert)
            gl.glDeleteShader(frag)

        return int(program)

    def _create_crossfade_program(self) -> int:
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
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    FragColor = mix(oldColor, newColor, t);
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
                logger.debug("[GL SHADER] Failed to link crossfade program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link crossfade program: {log!r}")
        finally:
            gl.glDeleteShader(vert)
            gl.glDeleteShader(frag)

        return int(program)

    def _create_slide_program(self) -> int:
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
uniform vec4 u_oldRect; // xy = pos, zw = size, in normalised viewport coords
uniform vec4 u_newRect; // xy = pos, zw = size, in normalised viewport coords

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    // Start from a black background; old and new images layer on top.
    vec4 color = vec4(0.0, 0.0, 0.0, 1.0);

    // OLD image contribution.
    vec2 oldMin = u_oldRect.xy;
    vec2 oldMax = u_oldRect.xy + u_oldRect.zw;
    if (uv.x >= oldMin.x && uv.x <= oldMax.x && uv.y >= oldMin.y && uv.y <= oldMax.y) {
        vec2 span = max(u_oldRect.zw, vec2(1e-5));
        vec2 local = (uv - oldMin) / span;
        color = texture(uOldTex, local);
    }

    // NEW image overlays OLD where they overlap, mirroring the QPainter
    // behaviour where the new pixmap is drawn last.
    vec2 newMin = u_newRect.xy;
    vec2 newMax = u_newRect.xy + u_newRect.zw;
    if (uv.x >= newMin.x && uv.x <= newMax.x && uv.y >= newMin.y && uv.y <= newMax.y) {
        vec2 span = max(u_newRect.zw, vec2(1e-5));
        vec2 local = (uv - newMin) / span;
        vec4 newColor = texture(uNewTex, local);
        color = newColor;
    }

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
                logger.debug("[GL SHADER] Failed to link slide program: %r", log)
                gl.glDeleteProgram(program)
                raise RuntimeError(f"Failed to link slide program: {log!r}")
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

    def _can_use_diffuse_shader(self) -> bool:
        st = self._diffuse
        if st is None:
            return False
        if st.cols <= 0 or st.rows <= 0:
            return False
        return self._can_use_simple_shader(st, getattr(self._gl_pipeline, "diffuse_program", 0))

    def _can_use_blockflip_shader(self) -> bool:
        st = self._blockflip
        if st is None:
            return False
        # BlockFlip GLSL path only activates when grid hints are available; when
        # cols/rows are zero we stay on the QPainter compositor path.
        if getattr(st, "cols", 0) <= 0 or getattr(st, "rows", 0) <= 0:
            return False
        return self._can_use_simple_shader(st, getattr(self._gl_pipeline, "blockflip_program", 0))

    def _can_use_peel_shader(self) -> bool:
        st = self._peel
        if st is None:
            return False
        # Require at least one logical strip; start_peel already clamps this
        # but we keep the guard for safety.
        if getattr(st, "strips", 0) <= 0:
            return False
        return self._can_use_simple_shader(st, getattr(self._gl_pipeline, "peel_program", 0))

    def _can_use_blinds_shader(self) -> bool:
        st = self._blinds
        if st is None:
            return False
        # Blinds GLSL path only activates when grid hints are available; when
        # cols/rows are zero we stay on the QPainter compositor path.
        if getattr(st, "cols", 0) <= 0 or getattr(st, "rows", 0) <= 0:
            return False
        return self._can_use_simple_shader(st, getattr(self._gl_pipeline, "blinds_program", 0))

    def _can_use_crossfade_shader(self) -> bool:
        return self._can_use_simple_shader(self._crossfade, getattr(self._gl_pipeline, "crossfade_program", 0))

    def _can_use_slide_shader(self) -> bool:
        return self._can_use_simple_shader(self._slide, getattr(self._gl_pipeline, "slide_program", 0))

    def _can_use_wipe_shader(self) -> bool:
        return self._can_use_simple_shader(self._wipe, getattr(self._gl_pipeline, "wipe_program", 0))

    def _can_use_shuffle_shader(self) -> bool:
        return self._can_use_simple_shader(self._shuffle, getattr(self._gl_pipeline, "shuffle_program", 0))

    def _can_use_claws_shader(self) -> bool:
        # Shooting Stars / Claw Marks shader path is hard-disabled. The user
        # has elected to remove this effect, and any remaining "Claw Marks"
        # requests are routed through a CPU crossfade instead. Keeping this
        # function returning False ensures the GLSL claws program is never
        # used even if it is still compiled in the pipeline.
        return False

    def warm_shader_textures(self, old_pixmap: Optional[QPixmap], new_pixmap: Optional[QPixmap]) -> None:
        """Best-effort prewarm of shader textures for a pixmap pair.

        This initialises the GLSL pipeline on first use (if not already
        done), then uploads/caches textures for the provided old/new pixmaps
        so shader-backed transitions can reuse them without paying the full
        upload cost on their first frame. Failures are logged at DEBUG and do
        not affect the caller.
        """

        if gl is None or self._gl_disabled_for_session:
            return
        if old_pixmap is None and (new_pixmap is None or new_pixmap.isNull()):
            return

        # Ensure pipeline exists before touching GL resources.
        if self._gl_pipeline is None:
            try:
                self.makeCurrent()
            except Exception:
                return
            try:
                try:
                    self._gl_pipeline = _GLPipelineState()
                    self._use_shaders = False
                    self._gl_disabled_for_session = False
                    self._init_gl_pipeline()
                except Exception:
                    logger.debug("[GL COMPOSITOR] warm_shader_textures failed to init pipeline", exc_info=True)
                    return
            finally:
                try:
                    self.doneCurrent()
                except Exception:
                    pass

        if self._gl_pipeline is None or not self._gl_pipeline.initialized:
            return

        try:
            self.makeCurrent()
        except Exception:
            return

        try:
            try:
                if old_pixmap is not None and not old_pixmap.isNull():
                    self._get_or_create_texture_for_pixmap(old_pixmap)
            except Exception:
                logger.debug("[GL COMPOSITOR] warm_shader_textures failed for old pixmap", exc_info=True)
            try:
                if new_pixmap is not None and not new_pixmap.isNull():
                    self._get_or_create_texture_for_pixmap(new_pixmap)
            except Exception:
                logger.debug("[GL COMPOSITOR] warm_shader_textures failed for new pixmap", exc_info=True)
        finally:
            try:
                self.doneCurrent()
            except Exception:
                pass

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

    def _get_or_create_texture_for_pixmap(self, pixmap: QPixmap) -> int:
        """Return a cached texture id for *pixmap*, uploading if needed.

        Textures are cached per ``QPixmap.cacheKey()`` in the pipeline state so
        shader-backed transitions can reuse GPU textures across frames and
        transitions instead of re-uploading from CPU memory each time. A small
        LRU is used to bound VRAM usage.
        """

        if gl is None or self._gl_pipeline is None or pixmap is None or pixmap.isNull():
            return 0

        key = 0
        try:
            if hasattr(pixmap, "cacheKey"):
                key = int(pixmap.cacheKey())
        except Exception:
            key = 0

        cache = self._gl_pipeline.texture_cache
        lru = self._gl_pipeline.texture_lru

        if key > 0:
            tex_id = cache.get(key, 0)
            if tex_id:
                # Refresh LRU position.
                try:
                    if key in lru:
                        lru.remove(key)
                    lru.append(key)
                except Exception:
                    pass
                return int(tex_id)

        tex_id = self._upload_texture_from_pixmap(pixmap)
        if not tex_id:
            return 0

        if key > 0:
            cache[key] = tex_id
            try:
                lru.append(key)
                max_cached = 12
                while len(lru) > max_cached:
                    evict_key = lru.pop(0)
                    if evict_key == key:
                        continue
                    old_tex = cache.pop(evict_key, 0)
                    if old_tex:
                        try:
                            gl.glDeleteTextures(int(old_tex))
                        except Exception:
                            logger.debug(
                                "[GL SHADER] Failed to delete cached texture %s", old_tex, exc_info=True
                            )
            except Exception:
                pass

        return tex_id

    def _release_transition_textures(self) -> None:
        if self._gl_pipeline is None:
            return
        # Only drop references to the current pair; cached textures remain
        # alive so subsequent transitions can reuse them. Cache lifetime is
        # bounded and cleaned up in _cleanup_gl_pipeline().
        self._gl_pipeline.old_tex_id = 0
        self._gl_pipeline.new_tex_id = 0

    def _prepare_pair_textures(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        if self._gl_pipeline is None:
            return False
        if old_pixmap is None or old_pixmap.isNull() or new_pixmap is None or new_pixmap.isNull():
            return False

        self._release_transition_textures()

        try:
            self._gl_pipeline.old_tex_id = self._get_or_create_texture_for_pixmap(old_pixmap)
            self._gl_pipeline.new_tex_id = self._get_or_create_texture_for_pixmap(new_pixmap)
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

    def _prepare_diffuse_textures(self) -> bool:
        if not self._can_use_diffuse_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._diffuse is None:
            return False
        st = self._diffuse
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_blockflip_textures(self) -> bool:
        if not self._can_use_blockflip_shader():
            return False
        if self._gl_pipeline is None:
            return False
        # Reuse any textures already prepared for this pixmap pair.
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._blockflip is None:
            return False
        st = self._blockflip
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_peel_textures(self) -> bool:
        if not self._can_use_peel_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._peel is None:
            return False
        st = self._peel
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_blinds_textures(self) -> bool:
        if not self._can_use_blinds_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._blinds is None:
            return False
        st = self._blinds
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_crossfade_textures(self) -> bool:
        if not self._can_use_crossfade_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._crossfade is None:
            return False
        st = self._crossfade
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_slide_textures(self) -> bool:
        if not self._can_use_slide_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._slide is None:
            return False
        st = self._slide
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_wipe_textures(self) -> bool:
        if not self._can_use_wipe_shader():
            return False
        if self._gl_pipeline is None:
            return False
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._wipe is None:
            return False
        st = self._wipe
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
        # Guard against off-by-one rounding between Qt's reported size and
        # the underlying framebuffer by slightly over-covering vertically.
        # This prevents a 1px retained strip from the previous frame at the
        # top edge on certain DPI/size combinations.
        try:
            h = max(1, h + 1)
        except Exception:
            h = max(1, h)
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

    def _paint_peel_shader(self, target: QRect) -> None:
        if not self._can_use_peel_shader() or self._gl_pipeline is None or self._peel is None:
            return
        st = self._peel
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_peel_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.peel_program)
        try:
            if self._gl_pipeline.peel_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.peel_u_progress, float(p))

            if self._gl_pipeline.peel_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.peel_u_resolution, float(vp_w), float(vp_h))

            # Map SlideDirection to a cardinal travel vector that matches the
            # CPU compositor semantics: LEFT moves strips left, RIGHT moves
            # them right, DOWN moves them down, UP moves them up.
            dx = 0.0
            dy = 0.0
            try:
                direction = getattr(st, "direction", None)
                if direction == SlideDirection.LEFT:
                    dx, dy = -1.0, 0.0
                elif direction == SlideDirection.RIGHT:
                    dx, dy = 1.0, 0.0
                elif direction == SlideDirection.DOWN:
                    dx, dy = 0.0, 1.0
                elif direction == SlideDirection.UP:
                    dx, dy = 0.0, -1.0
            except Exception:
                dx, dy = -1.0, 0.0

            if self._gl_pipeline.peel_u_direction != -1:
                gl.glUniform2f(self._gl_pipeline.peel_u_direction, float(dx), float(dy))

            if self._gl_pipeline.peel_u_strips != -1:
                try:
                    strips = max(1, int(getattr(st, "strips", 1)))
                except Exception:
                    strips = 1
                gl.glUniform1f(self._gl_pipeline.peel_u_strips, float(strips))

            if self._gl_pipeline.peel_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.peel_u_old_tex, 0)
            if self._gl_pipeline.peel_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.peel_u_new_tex, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
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

    def _paint_blinds_shader(self, target: QRect) -> None:
        if not self._can_use_blinds_shader() or self._gl_pipeline is None or self._blinds is None:
            return
        st = self._blinds
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_blinds_textures():
            return

        vp_w, vp_h = self._get_viewport_size()

        float_cols = float(max(1, int(getattr(st, "cols", 0))))
        float_rows = float(max(1, int(getattr(st, "rows", 0))))
        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.blinds_program)
        try:
            if self._gl_pipeline.blinds_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.blinds_u_progress, float(p))

            if self._gl_pipeline.blinds_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.blinds_u_resolution, float(vp_w), float(vp_h))

            if self._gl_pipeline.blinds_u_grid != -1:
                gl.glUniform2f(self._gl_pipeline.blinds_u_grid, float_cols, float_rows)

            if self._gl_pipeline.blinds_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.blinds_u_old_tex, 0)
            if self._gl_pipeline.blinds_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.blinds_u_new_tex, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_wipe_shader(self, target: QRect) -> None:
        if not self._can_use_wipe_shader() or self._gl_pipeline is None or self._wipe is None:
            return
        st = self._wipe
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_wipe_textures():
            return

        vp_w, vp_h = self._get_viewport_size()

        float_t = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.wipe_program)
        try:
            if self._gl_pipeline.wipe_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.wipe_u_progress, float_t)

            if self._gl_pipeline.wipe_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.wipe_u_resolution, float(vp_w), float(vp_h))

            # Map WipeDirection to a compact integer mode used by the shader.
            mode = 0
            try:
                direction = st.direction
                if direction == WipeDirection.RIGHT_TO_LEFT:
                    mode = 1
                elif direction == WipeDirection.TOP_TO_BOTTOM:
                    mode = 2
                elif direction == WipeDirection.BOTTOM_TO_TOP:
                    mode = 3
                elif direction == WipeDirection.DIAG_TL_BR:
                    mode = 4
                elif direction == WipeDirection.DIAG_TR_BL:
                    mode = 5
            except Exception:
                mode = 0

            if self._gl_pipeline.wipe_u_mode != -1:
                gl.glUniform1i(self._gl_pipeline.wipe_u_mode, int(mode))

            if self._gl_pipeline.wipe_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.wipe_u_old_tex, 0)
            if self._gl_pipeline.wipe_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.wipe_u_new_tex, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_slide_shader(self, target: QRect) -> None:
        if not self._can_use_slide_shader() or self._gl_pipeline is None or self._slide is None:
            return
        st = self._slide
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_slide_textures():
            return

        target_rect = target
        w = max(1, target_rect.width())
        h = max(1, target_rect.height())

        t = max(0.0, min(1.0, float(st.progress)))
        old_pos = QPoint(
            int(st.old_start.x() + (st.old_end.x() - st.old_start.x()) * t),
            int(st.old_start.y() + (st.old_end.y() - st.old_start.y()) * t),
        )
        new_pos = QPoint(
            int(st.new_start.x() + (st.new_end.x() - st.new_start.x()) * t),
            int(st.new_start.y() + (st.new_end.y() - st.new_start.y()) * t),
        )

        inv_w = 1.0 / float(max(1, w))
        inv_h = 1.0 / float(max(1, h))

        old_x = float(old_pos.x()) * inv_w
        old_y = float(old_pos.y()) * inv_h
        new_x = float(new_pos.x()) * inv_w
        new_y = float(new_pos.y()) * inv_h

        vp_w, vp_h = self._get_viewport_size()

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.slide_program)
        try:
            if self._gl_pipeline.slide_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.slide_u_progress, float(t))

            if self._gl_pipeline.slide_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.slide_u_resolution, float(vp_w), float(vp_h))

            if self._gl_pipeline.slide_u_old_rect != -1:
                gl.glUniform4f(self._gl_pipeline.slide_u_old_rect, float(old_x), float(old_y), 1.0, 1.0)
            if self._gl_pipeline.slide_u_new_rect != -1:
                gl.glUniform4f(self._gl_pipeline.slide_u_new_rect, float(new_x), float(new_y), 1.0, 1.0)

            if self._gl_pipeline.slide_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.slide_u_old_tex, 0)
            if self._gl_pipeline.slide_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.slide_u_new_tex, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_crossfade_shader(self, target: QRect) -> None:
        if not self._can_use_crossfade_shader() or self._gl_pipeline is None or self._crossfade is None:
            return
        st = self._crossfade
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_crossfade_textures():
            return

        vp_w, vp_h = self._get_viewport_size()

        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.crossfade_program)
        try:
            if self._gl_pipeline.crossfade_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.crossfade_u_progress, float(p))

            if self._gl_pipeline.crossfade_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.crossfade_u_resolution, float(vp_w), float(vp_h))

            if self._gl_pipeline.crossfade_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.crossfade_u_old_tex, 0)
            if self._gl_pipeline.crossfade_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.crossfade_u_new_tex, 1)

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_diffuse_shader(self, target: QRect) -> None:
        if not self._can_use_diffuse_shader() or self._gl_pipeline is None or self._diffuse is None:
            return
        st = self._diffuse
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_diffuse_textures():
            return

        vp_w, vp_h = self._get_viewport_size()

        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.diffuse_program)
        try:
            if self._gl_pipeline.diffuse_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.diffuse_u_progress, float(p))

            if self._gl_pipeline.diffuse_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.diffuse_u_resolution, float(vp_w), float(vp_h))

            if self._gl_pipeline.diffuse_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.diffuse_u_old_tex, 0)
            if self._gl_pipeline.diffuse_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.diffuse_u_new_tex, 1)

            if self._gl_pipeline.diffuse_u_grid != -1:
                float_cols = float(max(1, int(st.cols)))
                float_rows = float(max(1, int(st.rows)))
                gl.glUniform2f(self._gl_pipeline.diffuse_u_grid, float_cols, float_rows)

            if self._gl_pipeline.diffuse_u_shape_mode != -1:
                gl.glUniform1i(self._gl_pipeline.diffuse_u_shape_mode, int(getattr(st, "shape_mode", 0)))

            gl.glBindVertexArray(self._gl_pipeline.quad_vao)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_blockflip_shader(self, target: QRect) -> None:
        if not self._can_use_blockflip_shader() or self._gl_pipeline is None or self._blockflip is None:
            return
        st = self._blockflip
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_blockflip_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        p = max(0.0, min(1.0, float(st.progress)))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(self._gl_pipeline.blockflip_program)
        try:
            if self._gl_pipeline.blockflip_u_progress != -1:
                gl.glUniform1f(self._gl_pipeline.blockflip_u_progress, float(p))

            if self._gl_pipeline.blockflip_u_resolution != -1:
                gl.glUniform2f(self._gl_pipeline.blockflip_u_resolution, float(vp_w), float(vp_h))

            if self._gl_pipeline.blockflip_u_grid != -1:
                float_cols = float(max(1, int(getattr(st, "cols", 0))))
                float_rows = float(max(1, int(getattr(st, "rows", 0))))
                gl.glUniform2f(self._gl_pipeline.blockflip_u_grid, float_cols, float_rows)

            # Map SlideDirection to a simple cardinal direction vector.
            dx = 1.0
            dy = 0.0
            try:
                direction = getattr(st, "direction", None)
                if direction == SlideDirection.LEFT:
                    dx, dy = 1.0, 0.0
                elif direction == SlideDirection.RIGHT:
                    dx, dy = -1.0, 0.0
                elif direction == SlideDirection.DOWN:
                    dx, dy = 0.0, 1.0
                elif direction == SlideDirection.UP:
                    dx, dy = 0.0, -1.0
            except Exception:
                dx, dy = 1.0, 0.0

            if self._gl_pipeline.blockflip_u_direction != -1:
                gl.glUniform2f(self._gl_pipeline.blockflip_u_direction, float(dx), float(dy))

            if self._gl_pipeline.blockflip_u_old_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.old_tex_id)
                gl.glUniform1i(self._gl_pipeline.blockflip_u_old_tex, 0)
            if self._gl_pipeline.blockflip_u_new_tex != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, self._gl_pipeline.new_tex_id)
                gl.glUniform1i(self._gl_pipeline.blockflip_u_new_tex, 1)

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

        if (
            active_label is None
            and self._blockspin is not None
            and self._blockspin_profile_start_ts is not None
            and self._blockspin_profile_last_ts is not None
            and self._blockspin_profile_frame_count > 0
        ):
            elapsed = self._blockspin_profile_last_ts - self._blockspin_profile_start_ts
            if elapsed > 0.0:
                fps = self._blockspin_profile_frame_count / elapsed
                active_label = "BlockSpin"
                line1 = f"{active_label} t={self._blockspin.progress:.2f}"
                dt_min_ms = self._blockspin_profile_min_dt * 1000.0 if self._blockspin_profile_min_dt > 0.0 else 0.0
                dt_max_ms = self._blockspin_profile_max_dt * 1000.0 if self._blockspin_profile_max_dt > 0.0 else 0.0
                line2 = f"{fps:.1f} fps  dt_min={dt_min_ms:.1f}ms  dt_max={dt_max_ms:.1f}ms"

        if (
            active_label is None
            and self._warp is not None
            and self._warp_profile_start_ts is not None
            and self._warp_profile_last_ts is not None
            and self._warp_profile_frame_count > 0
        ):
            elapsed = self._warp_profile_last_ts - self._warp_profile_start_ts
            if elapsed > 0.0:
                fps = self._warp_profile_frame_count / elapsed
                active_label = "Warp"
                line1 = f"{active_label} t={self._warp.progress:.2f}"
                dt_min_ms = self._warp_profile_min_dt * 1000.0 if self._warp_profile_min_dt > 0.0 else 0.0
                dt_max_ms = self._warp_profile_max_dt * 1000.0 if self._warp_profile_max_dt > 0.0 else 0.0
                line2 = f"{fps:.1f} fps  dt_min={dt_min_ms:.1f}ms  dt_max={dt_max_ms:.1f}ms"

        if (
            active_label is None
            and self._raindrops is not None
            and self._raindrops_profile_start_ts is not None
            and self._raindrops_profile_last_ts is not None
            and self._raindrops_profile_frame_count > 0
        ):
            elapsed = self._raindrops_profile_last_ts - self._raindrops_profile_start_ts
            if elapsed > 0.0:
                fps = self._raindrops_profile_frame_count / elapsed
                active_label = "Ripple"
                line1 = f"{active_label} t={self._raindrops.progress:.2f}"
                dt_min_ms = self._raindrops_profile_min_dt * 1000.0 if self._raindrops_profile_min_dt > 0.0 else 0.0
                dt_max_ms = self._raindrops_profile_max_dt * 1000.0 if self._raindrops_profile_max_dt > 0.0 else 0.0
                line2 = f"{fps:.1f} fps  dt_min={dt_min_ms:.1f}ms  dt_max={dt_max_ms:.1f}ms"

        if (
            active_label is None
            and self._shuffle is not None
            and self._shuffle_profile_start_ts is not None
            and self._shuffle_profile_last_ts is not None
            and self._shuffle_profile_frame_count > 0
        ):
            elapsed = self._shuffle_profile_last_ts - self._shuffle_profile_start_ts
            if elapsed > 0.0:
                fps = self._shuffle_profile_frame_count / elapsed
                active_label = "Shuffle"
                line1 = f"{active_label} t={self._shuffle.progress:.2f}"
                dt_min_ms = self._shuffle_profile_min_dt * 1000.0 if self._shuffle_profile_min_dt > 0.0 else 0.0
                dt_max_ms = self._shuffle_profile_max_dt * 1000.0 if self._shuffle_profile_max_dt > 0.0 else 0.0
                line2 = f"{fps:.1f} fps  dt_min={dt_min_ms:.1f}ms  dt_max={dt_max_ms:.1f}ms"

        if (
            active_label is None
            and self._diffuse is not None
            and self._diffuse_profile_start_ts is not None
            and self._diffuse_profile_last_ts is not None
            and self._diffuse_profile_frame_count > 0
        ):
            elapsed = self._diffuse_profile_last_ts - self._diffuse_profile_start_ts
            if elapsed > 0.0:
                fps = self._diffuse_profile_frame_count / elapsed
                active_label = "Diffuse"
                line1 = f"{active_label} t={self._diffuse.progress:.2f}"
                dt_min_ms = self._diffuse_profile_min_dt * 1000.0 if self._diffuse_profile_min_dt > 0.0 else 0.0
                dt_max_ms = self._diffuse_profile_max_dt * 1000.0 if self._diffuse_profile_max_dt > 0.0 else 0.0
                line2 = f"{fps:.1f} fps  dt_min={dt_min_ms:.1f}ms  dt_max={dt_max_ms:.1f}ms"

        if (
            active_label is None
            and self._blinds is not None
            and self._blinds_profile_start_ts is not None
            and self._blinds_profile_last_ts is not None
            and self._blinds_profile_frame_count > 0
        ):
            elapsed = self._blinds_profile_last_ts - self._blinds_profile_start_ts
            if elapsed > 0.0:
                fps = self._blinds_profile_frame_count / elapsed
                active_label = "Blinds"
                line1 = f"{active_label} t={self._blinds.progress:.2f}"
                dt_min_ms = self._blinds_profile_min_dt * 1000.0 if self._blinds_profile_min_dt > 0.0 else 0.0
                dt_max_ms = self._blinds_profile_max_dt * 1000.0 if self._blinds_profile_max_dt > 0.0 else 0.0
                line2 = f"{fps:.1f} fps  dt_min={dt_min_ms:.1f}ms  dt_max={dt_max_ms:.1f}ms"

        if (
            active_label is None
            and self._peel is not None
            and self._peel_profile_start_ts is not None
            and self._peel_profile_last_ts is not None
            and self._peel_profile_frame_count > 0
        ):
            elapsed = self._peel_profile_last_ts - self._peel_profile_start_ts
            if elapsed > 0.0:
                fps = self._peel_profile_frame_count / elapsed
                active_label = "Peel"
                line1 = f"{active_label} t={self._peel.progress:.2f}"
                dt_min_ms = self._peel_profile_min_dt * 1000.0 if self._peel_profile_min_dt > 0.0 else 0.0
                dt_max_ms = self._peel_profile_max_dt * 1000.0 if self._peel_profile_max_dt > 0.0 else 0.0
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

    def _paint_spotify_visualizer(self, painter: QPainter) -> None:
        if not self._spotify_vis_enabled:
            return

        rect = self._spotify_vis_rect
        bars = self._spotify_vis_bars
        if rect is None or bars is None:
            return

        try:
            fade = float(self._spotify_vis_fade)
        except Exception:
            fade = 0.0
        if fade <= 0.0:
            return

        count = self._spotify_vis_bar_count
        segments = self._spotify_vis_segments
        if count <= 0 or segments <= 0:
            return

        if rect.width() <= 0 or rect.height() <= 0:
            return

        margin_x = 8
        margin_y = 6
        inner = rect.adjusted(margin_x, margin_y, -margin_x, -margin_y)
        if inner.width() <= 0 or inner.height() <= 0:
            return

        gap = 2
        total_gap = gap * (count - 1) if count > 1 else 0
        bar_width = int((inner.width() - total_gap) / max(1, count))
        if bar_width <= 0:
            return
        # Match the QWidget visualiser: slight rightward offset so bars
        # visually line up with the card frame.
        x0 = inner.left() + 3
        bar_x = [x0 + i * (bar_width + gap) for i in range(count)]

        seg_gap = 1
        total_seg_gap = seg_gap * max(0, segments - 1)
        seg_height = int((inner.height() - total_seg_gap) / max(1, segments))
        if seg_height <= 0:
            return
        base_bottom = inner.bottom()
        seg_y = [base_bottom - s * (seg_height + seg_gap) - seg_height + 1 for s in range(segments)]

        fill = QColor(self._spotify_vis_fill_color or QColor(200, 200, 200, 230))
        border = QColor(self._spotify_vis_border_color or QColor(255, 255, 255, 255))

        # Apply the fade factor by scaling alpha on both fill and border so
        # the bar field ramps with the widget card.
        try:
            fade_clamped = max(0.0, min(1.0, fade))
            fill.setAlpha(int(fill.alpha() * fade_clamped))
            border.setAlpha(int(border.alpha() * fade_clamped))
        except Exception:
            pass

        painter.save()
        try:
            painter.setBrush(fill)
            painter.setPen(border)

            max_segments = min(segments, len(seg_y))
            draw_count = min(count, len(bar_x), len(bars))

            for i in range(draw_count):
                x = bar_x[i]
                try:
                    value = float(bars[i])
                except Exception:
                    value = 0.0
                if value <= 0.0:
                    continue
                if value > 1.0:
                    value = 1.0
                active = int(round(value * segments))
                if active <= 0:
                    continue
                if active > max_segments:
                    active = max_segments
                for s in range(active):
                    y = seg_y[s]
                    bar_rect = QRect(x, y, bar_width, seg_height)
                    painter.drawRect(bar_rect)
        finally:
            painter.restore()

    def _render_debug_overlay_image(self) -> Optional[QImage]:
        """Render the PERF HUD into a small offscreen image.

        This keeps glyph rasterisation fully in QPainter's software path so
        the final card can be composited on top of the GL surface without
        relying on GL text rendering state.
        """

        if not is_perf_metrics_enabled():
            return None
        size = self.size()
        if size.width() <= 0 or size.height() <= 0:
            return None

        image = QImage(size.width(), size.height(), QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)

        painter = QPainter(image)
        try:
            self._paint_debug_overlay(painter)
        finally:
            painter.end()

        return image

    def _paint_debug_overlay_gl(self) -> None:
        if not is_perf_metrics_enabled():
            return

        image = self._render_debug_overlay_image()
        if image is None:
            return

        painter = QPainter(self)
        try:
            painter.drawImage(0, 0, image)
        finally:
            painter.end()

    def paintGL(self) -> None:  # type: ignore[override]
        target = self.rect()

        # Prefer the shader path for Block Spins when available. On any failure
        # we log and fall back to the existing QPainter implementation.
        if self._blockspin is not None and self._can_use_blockspin_shader():
            try:
                if self._prepare_blockspin_textures():
                    self._paint_blockspin_shader(target)
                    self._paint_spotify_visualizer_gl()
                    if is_perf_metrics_enabled():
                        self._paint_debug_overlay_gl()
                    return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader blockspin path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug("[GL COMPOSITOR] Shader blockspin path failed; disabling shader pipeline", exc_info=True)
                self._gl_disabled_for_session = True
                self._use_shaders = False

        # BlockFlip shader path: when enabled and the GLSL pipeline is
        # available, draw the flip field in GLSL using the grid and direction
        # hints provided by the controller. On failure we disable shader usage
        # for the session and fall back to the existing QPainter path.
        if self._blockflip is not None and self._can_use_blockflip_shader():
            try:
                self._paint_blockflip_shader(target)
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader blockflip path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader blockflip path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        # Raindrops shader path: when enabled and the GLSL pipeline is
        # available, draw the droplet field entirely in GLSL. On failure we
        # disable shader usage for the session and fall back to the
        # compositor's existing QPainter-based transitions.
        if self._raindrops is not None and self._can_use_raindrops_shader():
            try:
                self._paint_raindrops_shader(target)
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
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
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
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
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
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
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
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

        # Diffuse shader path: when enabled and the GLSL pipeline is
        # available, draw the block-based reveal entirely in GLSL. This path
        # is only active when DiffuseState provides a non-zero grid; legacy
        # region-based Diffuse continues to use the QPainter path below.
        if self._diffuse is not None and self._can_use_diffuse_shader():
            try:
                self._paint_diffuse_shader(target)
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader diffuse path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader diffuse path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        # Peel shader path: when enabled and the GLSL pipeline is available,
        # draw the strip-based peel entirely in GLSL using the direction and
        # strip count provided by the controller. On failure we disable shader
        # usage for the session and fall back to the existing QPainter
        # compositor implementation below.
        if self._peel is not None and self._can_use_peel_shader():
            try:
                self._paint_peel_shader(target)
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader peel path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader peel path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        # Blinds shader path: when enabled and the GLSL pipeline is
        # available, draw the blinds reveal entirely in GLSL using the grid
        # hints provided by the controller. On failure we disable shader
        # usage for the session and fall back to the QPainter compositor
        # implementation below.
        if self._blinds is not None and self._can_use_blinds_shader():
            try:
                self._paint_blinds_shader(target)
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader blinds path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader blinds path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        if self._crossfade is not None and self._can_use_crossfade_shader():
            try:
                self._paint_crossfade_shader(target)
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader crossfade path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader crossfade path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        if self._slide is not None and self._can_use_slide_shader():
            try:
                self._paint_slide_shader(target)
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader slide path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader slide path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        if self._wipe is not None and self._can_use_wipe_shader():
            try:
                self._paint_wipe_shader(target)
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader wipe path failed; disabling shader pipeline",
                    exc_info=True,
                )
                logger.debug(
                    "[GL COMPOSITOR] Shader wipe path failed; disabling shader pipeline",
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
                self._paint_spotify_visualizer(painter)
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
                    self._paint_spotify_visualizer(painter)
                    self._paint_debug_overlay(painter)
                    return
                if t >= 1.0:
                    painter.setOpacity(1.0)
                    painter.drawPixmap(target, st.new_pixmap)
                    self._paint_spotify_visualizer(painter)
                    self._paint_debug_overlay(painter)
                    return

                painter.setOpacity(1.0)
                painter.drawPixmap(target, st.old_pixmap)
                painter.setOpacity(t)
                painter.drawPixmap(target, st.new_pixmap)
                self._paint_spotify_visualizer(painter)
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
                self._paint_spotify_visualizer(painter)
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
                self._paint_debug_overlay(painter)
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
                self._paint_spotify_visualizer(painter)
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
                self._paint_spotify_visualizer(painter)
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
                self._paint_spotify_visualizer(painter)
                self._paint_debug_overlay(painter)
                return

            # No active transition -> draw base pixmap if present.
            if self._base_pixmap is not None and not self._base_pixmap.isNull():
                painter.setOpacity(1.0)
                painter.drawPixmap(target, self._base_pixmap)
            else:
                # As a last resort, fill black.
                painter.fillRect(target, Qt.GlobalColor.black)

            self._paint_spotify_visualizer(painter)
            self._paint_debug_overlay(painter)
        finally:
            painter.end()

    def _paint_spotify_visualizer_gl(self) -> None:
        if not self._spotify_vis_enabled:
            return
        painter = QPainter(self)
        try:
            self._paint_spotify_visualizer(painter)
        finally:
            painter.end()
