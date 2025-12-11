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
import math
import ctypes
import time

from PySide6.QtCore import Qt, QPoint, QRect, QTimer
from PySide6.QtGui import QPainter, QPixmap, QRegion, QImage, QColor
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.animation.types import EasingCurve
from core.animation.animator import AnimationManager
from core.animation.frame_interpolator import FrameState
from rendering.gl_format import apply_widget_surface_format
from rendering.gl_profiler import TransitionProfiler
from transitions.wipe_transition import WipeDirection, _compute_wipe_region
from transitions.slide_transition import SlideDirection
from core.resources.manager import ResourceManager

try:  # Optional dependency; shaders are disabled if unavailable.
    # Disable OpenGL_accelerate to avoid Nuitka compilation issues.
    # The accelerate module is optional and not required for functionality.
    # Setting PYOPENGL_PLATFORM before import prevents accelerate from loading.
    import os
    os.environ.setdefault("PYOPENGL_PLATFORM", "nt")  # Windows native
    import OpenGL
    # Disable accelerate module - it causes issues with Nuitka builds
    # and is not required for our use case (we don't do heavy GL array ops)
    OpenGL.ERROR_ON_COPY = True  # Catch accidental array copies
    from OpenGL import GL as gl  # type: ignore[import]
except Exception:  # pragma: no cover - PyOpenGL not required for CPU paths
    gl = None

# Import shader program helpers (lazy to avoid circular imports at module level)
_peel_program_instance = None
_blockflip_program_instance = None
_crossfade_program_instance = None
_blinds_program_instance = None
_diffuse_program_instance = None

def _get_peel_program():
    """Lazy-load the PeelProgram singleton."""
    global _peel_program_instance
    if _peel_program_instance is None:
        from rendering.gl_programs.peel_program import peel_program
        _peel_program_instance = peel_program
    return _peel_program_instance

def _get_blockflip_program():
    """Lazy-load the BlockFlipProgram singleton."""
    global _blockflip_program_instance
    if _blockflip_program_instance is None:
        from rendering.gl_programs.blockflip_program import blockflip_program
        _blockflip_program_instance = blockflip_program
    return _blockflip_program_instance

def _get_crossfade_program():
    """Lazy-load the CrossfadeProgram singleton."""
    global _crossfade_program_instance
    if _crossfade_program_instance is None:
        from rendering.gl_programs.crossfade_program import crossfade_program
        _crossfade_program_instance = crossfade_program
    return _crossfade_program_instance

def _get_blinds_program():
    """Lazy-load the BlindsProgram singleton."""
    global _blinds_program_instance
    if _blinds_program_instance is None:
        from rendering.gl_programs.blinds_program import blinds_program
        _blinds_program_instance = blinds_program
    return _blinds_program_instance

def _get_diffuse_program():
    """Lazy-load the DiffuseProgram singleton."""
    global _diffuse_program_instance
    if _diffuse_program_instance is None:
        from rendering.gl_programs.diffuse_program import diffuse_program
        _diffuse_program_instance = diffuse_program
    return _diffuse_program_instance

_slide_program_instance = None
_wipe_program_instance = None

def _get_slide_program():
    """Lazy-load the SlideProgram singleton."""
    global _slide_program_instance
    if _slide_program_instance is None:
        from rendering.gl_programs.slide_program import slide_program
        _slide_program_instance = slide_program
    return _slide_program_instance

def _get_wipe_program():
    """Lazy-load the WipeProgram singleton."""
    global _wipe_program_instance
    if _wipe_program_instance is None:
        from rendering.gl_programs.wipe_program import wipe_program
        _wipe_program_instance = wipe_program
    return _wipe_program_instance

_warp_program_instance = None
_raindrops_program_instance = None
_crumble_program_instance = None

def _get_crumble_program():
    """Lazy-load the CrumbleProgram singleton."""
    global _crumble_program_instance
    if _crumble_program_instance is None:
        from rendering.gl_programs.crumble_program import crumble_program
        _crumble_program_instance = crumble_program
    return _crumble_program_instance

def _get_warp_program():
    """Lazy-load the WarpProgram singleton."""
    global _warp_program_instance
    if _warp_program_instance is None:
        from rendering.gl_programs.warp_program import warp_program
        _warp_program_instance = warp_program
    return _warp_program_instance

def _get_raindrops_program():
    """Lazy-load the RaindropsProgram singleton."""
    global _raindrops_program_instance
    if _raindrops_program_instance is None:
        from rendering.gl_programs.raindrops_program import raindrops_program
        _raindrops_program_instance = raindrops_program
    return _raindrops_program_instance


def cleanup_global_shader_programs() -> None:
    """Clear all global shader program singleton instances.
    
    Call this on application shutdown to ensure GL resources are released.
    This is safe to call even if programs were never loaded.
    """
    global _peel_program_instance, _blockflip_program_instance, _crossfade_program_instance
    global _blinds_program_instance, _diffuse_program_instance, _slide_program_instance
    global _wipe_program_instance, _warp_program_instance, _raindrops_program_instance
    global _crumble_program_instance
    
    # Clear all program instances - they will be garbage collected
    # and their GL resources released when the context is destroyed
    _peel_program_instance = None
    _blockflip_program_instance = None
    _crossfade_program_instance = None
    _blinds_program_instance = None
    _diffuse_program_instance = None
    _slide_program_instance = None
    _wipe_program_instance = None
    _warp_program_instance = None
    _raindrops_program_instance = None
    _crumble_program_instance = None


logger = get_logger(__name__)


def _blockspin_spin_from_progress(p: float) -> float:
    """Map 0..1 timeline to spin progress with eased endpoints.
    
    PERFORMANCE: Module-level function to avoid per-frame nested function creation.
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


@dataclass
class CrossfadeState:
    """State for a compositor-driven crossfade transition."""

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    progress: float = 0.0  # 0..1


# NOTE: ShuffleShaderState removed - Shuffle transition is retired.


@dataclass
class SlideState:
    """State for a compositor-driven slide transition.
    
    PERFORMANCE: Float coordinates are pre-computed at creation time to avoid
    repeated QPoint.x()/y() calls and float() conversions in the hot render path.
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    old_start: QPoint
    old_end: QPoint
    new_start: QPoint
    new_end: QPoint
    progress: float = 0.0  # 0..1
    
    # Pre-computed float coordinates for hot path (set in __post_init__)
    _old_start_x: float = 0.0
    _old_start_y: float = 0.0
    _old_delta_x: float = 0.0  # old_end.x - old_start.x
    _old_delta_y: float = 0.0  # old_end.y - old_start.y
    _new_start_x: float = 0.0
    _new_start_y: float = 0.0
    _new_delta_x: float = 0.0  # new_end.x - new_start.x
    _new_delta_y: float = 0.0  # new_end.y - new_start.y
    
    def __post_init__(self) -> None:
        """Pre-compute float coordinates to avoid per-frame conversions."""
        self._old_start_x = float(self.old_start.x())
        self._old_start_y = float(self.old_start.y())
        self._old_delta_x = float(self.old_end.x()) - self._old_start_x
        self._old_delta_y = float(self.old_end.y()) - self._old_start_y
        self._new_start_x = float(self.new_start.x())
        self._new_start_y = float(self.new_start.y())
        self._new_delta_x = float(self.new_end.x()) - self._new_start_x
        self._new_delta_y = float(self.new_end.y()) - self._new_start_y


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


# NOTE: ShootingStarsState removed - Claws/Shooting Stars transition is retired.


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
    crumble_program: int = 0

    # Textures for the current pair of images being blended/transitioned.
    old_tex_id: int = 0
    new_tex_id: int = 0
    # Small per-pixmap texture cache keyed by QPixmap.cacheKey() so
    # shader-backed transitions can reuse GPU textures across frames and
    # transitions instead of re-uploading from CPU memory each time.
    texture_cache: dict[int, int] = field(default_factory=dict)
    texture_lru: list[int] = field(default_factory=list)

    # Double-buffered PBO pool for async texture uploads.
    # Each PBO pair allows one buffer to be filled while the other is used for upload.
    # Format: list of (pbo_id, size, in_use) tuples
    pbo_pool: list = field(default_factory=list)
    # Pending uploads: list of (pbo_id, tex_id, width, height) waiting for next frame
    pbo_pending_uploads: list = field(default_factory=list)

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
    # Legacy fields kept for compatibility; new code uses raindrops_uniforms dict.
    raindrops_u_progress: int = -1
    raindrops_u_resolution: int = -1
    raindrops_u_old_tex: int = -1
    raindrops_u_new_tex: int = -1
    # New: dict of uniform locations from RaindropsProgram.cache_uniforms()
    raindrops_uniforms: dict = field(default_factory=dict)

    # Cached uniform locations for the Warp Dissolve shader program.
    # Legacy fields kept for compatibility; new code uses warp_uniforms dict.
    warp_u_progress: int = -1
    warp_u_resolution: int = -1
    warp_u_old_tex: int = -1
    warp_u_new_tex: int = -1
    # New: dict of uniform locations from WarpProgram.cache_uniforms()
    warp_uniforms: dict = field(default_factory=dict)

    # Cached uniform locations for the Diffuse shader program.
    # Legacy fields kept for compatibility; new code uses diffuse_uniforms dict.
    diffuse_u_progress: int = -1
    diffuse_u_resolution: int = -1
    diffuse_u_old_tex: int = -1
    diffuse_u_new_tex: int = -1
    diffuse_u_grid: int = -1
    diffuse_u_shape_mode: int = -1
    # New: dict of uniform locations from DiffuseProgram.cache_uniforms()
    diffuse_uniforms: dict = field(default_factory=dict)

    # Cached uniform locations for the BlockFlip shader program.
    # Legacy fields kept for compatibility; new code uses blockflip_uniforms dict.
    blockflip_u_progress: int = -1
    blockflip_u_resolution: int = -1
    blockflip_u_old_tex: int = -1
    blockflip_u_new_tex: int = -1
    blockflip_u_grid: int = -1
    blockflip_u_direction: int = -1
    # New: dict of uniform locations from BlockFlipProgram.cache_uniforms()
    blockflip_uniforms: dict = field(default_factory=dict)

    # Cached uniform locations for the Peel shader program.
    # Legacy fields kept for compatibility; new code uses peel_uniforms dict.
    peel_u_progress: int = -1
    peel_u_resolution: int = -1
    peel_u_old_tex: int = -1
    peel_u_new_tex: int = -1
    peel_u_direction: int = -1
    peel_u_strips: int = -1
    # New: dict of uniform locations from PeelProgram.cache_uniforms()
    peel_uniforms: dict = field(default_factory=dict)

    # Cached uniform locations for the Blinds shader program.
    # Legacy fields kept for compatibility; new code uses blinds_uniforms dict.
    blinds_u_progress: int = -1
    blinds_u_resolution: int = -1
    blinds_u_old_tex: int = -1
    blinds_u_new_tex: int = -1
    blinds_u_grid: int = -1
    # New: dict of uniform locations from BlindsProgram.cache_uniforms()
    blinds_uniforms: dict = field(default_factory=dict)

    # Cached uniform locations for the Crumble shader program.
    crumble_uniforms: dict = field(default_factory=dict)

    # Cached uniform locations for the Shuffle shader program.
    shuffle_u_progress: int = -1
    shuffle_u_resolution: int = -1
    shuffle_u_old_tex: int = -1
    shuffle_u_new_tex: int = -1
    shuffle_u_grid: int = -1
    shuffle_u_direction: int = -1
    # Legacy fields kept for compatibility; new code uses crossfade_uniforms dict.
    crossfade_u_progress: int = -1
    crossfade_u_resolution: int = -1
    crossfade_u_old_tex: int = -1
    crossfade_u_new_tex: int = -1
    # New: dict of uniform locations from CrossfadeProgram.cache_uniforms()
    crossfade_uniforms: dict = field(default_factory=dict)
    # Legacy fields kept for compatibility; new code uses slide_uniforms dict.
    slide_u_progress: int = -1
    slide_u_resolution: int = -1
    slide_u_old_tex: int = -1
    slide_u_new_tex: int = -1
    slide_u_old_rect: int = -1
    slide_u_new_rect: int = -1
    # New: dict of uniform locations from SlideProgram.cache_uniforms()
    slide_uniforms: dict = field(default_factory=dict)
    # Legacy fields kept for compatibility; new code uses wipe_uniforms dict.
    wipe_u_progress: int = -1
    wipe_u_resolution: int = -1
    wipe_u_old_tex: int = -1
    wipe_u_new_tex: int = -1
    wipe_u_mode: int = -1
    # New: dict of uniform locations from WipeProgram.cache_uniforms()
    wipe_uniforms: dict = field(default_factory=dict)

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


@dataclass
class CrumbleState:
    """State for a compositor-driven crumble transition.

    Crumble creates a rock-like crack pattern across the old image, then the
    pieces fall away with physics-based motion to reveal the new image.
    
    Settings:
    - piece_count: Number of pieces (4-16, default 8)
    - crack_complexity: Crack detail level (0.5-2.0, default 1.0)
    - mosaic_mode: If True, uses glass shatter effect with 3D depth
    """

    old_pixmap: Optional[QPixmap]
    new_pixmap: Optional[QPixmap]
    progress: float = 0.0  # 0..1
    seed: float = 0.0  # Random seed for crack pattern variation
    piece_count: float = 8.0  # Approximate number of pieces (grid density)
    crack_complexity: float = 1.0  # Crack detail level (0.5-2.0)
    mosaic_mode: bool = False  # Glass shatter mode


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
        self._crumble: Optional[CrumbleState] = None
        # NOTE: _shuffle and _shooting_stars removed - these transitions are retired.

        # Centralized profiler for all compositor-driven transitions.
        # Replaces per-transition profiling fields with a single reusable instance.
        self._profiler = TransitionProfiler()

        # FRAME PACING: Single FrameState for all transitions. Decouples animation
        # updates from rendering - animation pushes timestamped samples, paintGL
        # interpolates to actual render time for smooth motion.
        self._frame_state: Optional[FrameState] = None
        
        # RENDER TIMER: Drives repaints at display refresh rate during transitions.
        # This decouples rendering from animation timer jitter - the animation timer
        # updates the FrameState, the render timer triggers repaints, and paintGL
        # interpolates to the actual render time.
        self._render_timer: Optional[QTimer] = None
        self._render_timer_fps: int = 60  # Will be set from display refresh rate

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

        # PERFORMANCE: Cached viewport size to avoid per-frame DPR calculations.
        # Invalidated on resize events.
        self._cached_viewport: Optional[tuple[int, int]] = None
        self._cached_widget_size: Optional[tuple[int, int]] = None

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
        
        # GL-based dimming overlay. Rendered AFTER the wallpaper/transition
        # but BEFORE widgets (which are Qt siblings above the compositor).
        # This ensures proper compositing without Z-order issues.
        self._dimming_enabled: bool = False
        self._dimming_opacity: float = 0.0  # 0.0-1.0

    # ------------------------------------------------------------------
    # Public API used by DisplayWidget / transitions
    # ------------------------------------------------------------------
    
    def set_dimming(self, enabled: bool, opacity: float = 0.3) -> None:
        """Enable or disable GL-based dimming overlay.
        
        Args:
            enabled: True to show dimming, False to hide
            opacity: Dimming opacity 0.0-1.0 (default 0.3 = 30%)
        """
        self._dimming_enabled = enabled
        self._dimming_opacity = max(0.0, min(1.0, opacity))
        self.update()
        logger.debug("GL dimming: enabled=%s, opacity=%.0f%%", enabled, self._dimming_opacity * 100)

    def _get_render_progress(self, fallback: float = 0.0) -> float:
        """Get interpolated progress for rendering.
        
        Uses FrameState to interpolate to actual render time, masking timer jitter.
        Falls back to the provided value if no frame state is active.
        """
        if self._frame_state is not None:
            return self._frame_state.get_interpolated_progress()
        return fallback

    def _start_frame_pacing(self, duration_sec: float) -> FrameState:
        """Create and return a new FrameState for a transition.
        
        Called at the start of any transition to enable decoupled rendering.
        Also starts the render timer to drive repaints at display refresh rate.
        """
        self._frame_state = FrameState(duration=duration_sec)
        self._start_render_timer()
        return self._frame_state

    def _stop_frame_pacing(self) -> None:
        """Clear the frame state when a transition completes."""
        self._stop_render_timer()
        if self._frame_state is not None:
            self._frame_state.mark_complete()
        self._frame_state = None
    
    def _start_render_timer(self) -> None:
        """Start the render timer to drive repaints during transitions.
        
        Uses adaptive rate selection based on display refresh rate:
        - 60Hz or below: target full refresh rate
        - 61-120Hz: target half refresh rate (e.g., 120Hz → 60Hz)
        - Above 120Hz: target third refresh rate (e.g., 165Hz → 55Hz)
        
        This ensures we target achievable frame rates rather than impossible ones.
        The interpolation system smooths the visual result regardless of actual FPS.
        """
        if self._render_timer is not None:
            return  # Already running
        
        # Get refresh rate from parent DisplayWidget's stored screen reference
        # (more reliable than self.screen() which may return wrong screen for child widgets)
        display_hz = 60
        try:
            screen = None
            parent = self.parent()
            # First try parent's stored _screen reference (set by DisplayWidget.show_on_screen)
            if parent is not None and hasattr(parent, "_screen"):
                screen = parent._screen
            # Fallback to parent.screen() if _screen not available
            if screen is None and parent is not None:
                screen = parent.screen()
            # Fallback to self.screen()
            if screen is None:
                screen = self.screen()
            # Final fallback to primary screen
            if screen is None:
                from PySide6.QtGui import QGuiApplication
                screen = QGuiApplication.primaryScreen()
            if screen is not None:
                display_hz = int(screen.refreshRate())
                if display_hz <= 0:
                    display_hz = 60
        except Exception:
            pass
        
        # Adaptive rate selection - target achievable FPS
        if display_hz <= 60:
            target_fps = display_hz  # Full rate for 60Hz and below
        elif display_hz <= 120:
            target_fps = display_hz // 2  # Half rate for 61-120Hz (e.g., 120→60, 90→45)
        else:
            target_fps = display_hz // 3  # Third rate for >120Hz (e.g., 165→55, 144→48)
        
        # Ensure minimum of 30 FPS
        target_fps = max(30, target_fps)
        
        self._render_timer_fps = target_fps
        interval_ms = max(1, 1000 // target_fps)
        
        self._render_timer = QTimer(self)
        self._render_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._render_timer.timeout.connect(self._on_render_tick)
        self._render_timer.start(interval_ms)
        
        logger.debug("[GL COMPOSITOR] Render timer started: display=%dHz, target=%dHz (interval=%dms)", 
                    display_hz, target_fps, interval_ms)
    
    def _stop_render_timer(self) -> None:
        """Stop the render timer."""
        if self._render_timer is not None:
            self._render_timer.stop()
            self._render_timer.deleteLater()
            self._render_timer = None
            logger.debug("[GL COMPOSITOR] Render timer stopped")
    
    def _on_render_tick(self) -> None:
        """Called by render timer to trigger a repaint.
        
        The actual progress interpolation happens in paintGL using the FrameState.
        """
        if self._frame_state is not None and self._frame_state.started and not self._frame_state.completed:
            self.update()

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

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_crossfade_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_crossfade_update,
            on_complete=lambda: self._on_crossfade_complete(on_finished),
            frame_state=frame_state,
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

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_warp_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        self._profiler.start("warp")

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_warp_update,
            on_complete=lambda: self._on_warp_complete(on_finished),
            frame_state=frame_state,
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

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_raindrops_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        self._profiler.start("raindrops")

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_raindrops_update,
            on_complete=lambda: self._on_raindrops_complete(on_finished),
            frame_state=frame_state,
        )
        self._current_anim_id = anim_id
        return anim_id

    # NOTE: start_shuffle_shader() and start_shooting_stars() removed - these transitions are retired.

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

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_wipe_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        self._profiler.start("wipe")

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_wipe_update,
            on_complete=lambda: self._on_wipe_complete(on_finished),
            frame_state=frame_state,
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
        
        duration_sec = max(0.001, duration_ms / 1000.0)
        
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

        # TRANSITION READINESS: Pre-upload textures BEFORE animation starts.
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_slide_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        # Start profiling for this transition.
        self._profiler.start("slide")

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        # FRAME PACING: Create FrameState and pass to animation
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_slide_update,
            on_complete=lambda: self._on_slide_complete(on_finished),
            frame_state=frame_state,
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

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_peel_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        self._profiler.start("peel")

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_peel_update,
            on_complete=lambda: self._on_peel_complete(on_finished),
            frame_state=frame_state,
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

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_blockflip_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        self._profiler.start("blockflip")

        def _blockflip_profiled_update(progress: float, *, _inner=update_callback) -> None:
            self._profiler.tick("blockflip")
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
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=_blockflip_profiled_update,
            on_complete=lambda: self._on_blockflip_complete(on_finished),
            frame_state=frame_state,
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

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_blockspin_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        self._profiler.start("blockspin")

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        duration_sec = max(0.001, duration_ms / 1000.0)
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=self._on_blockspin_update,
            on_complete=lambda: self._on_blockspin_complete(on_finished),
            frame_state=frame_state,
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

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_diffuse_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        self._profiler.start("diffuse")

        def _diffuse_profiled_update(progress: float, *, _inner=update_callback) -> None:
            self._profiler.tick("diffuse")
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
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=_diffuse_profiled_update,
            on_complete=lambda: self._on_diffuse_complete(on_finished),
            frame_state=frame_state,
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

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_blinds_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        self._profiler.start("blinds")

        def _blinds_profiled_update(progress: float, *, _inner=update_callback) -> None:
            self._profiler.tick("blinds")
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
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=_blinds_profiled_update,
            on_complete=lambda: self._on_blinds_complete(on_finished),
            frame_state=frame_state,
        )
        self._current_anim_id = anim_id
        return anim_id

    def start_crumble(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
        *,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]] = None,
        piece_count: int = 8,
        crack_complexity: float = 1.0,
        mosaic_mode: bool = False,
        seed: Optional[float] = None,
    ) -> Optional[str]:
        """Begin a crumble transition using the compositor.

        The crumble effect creates a rock-like crack pattern across the old
        image, then the pieces fall away to reveal the new image.
        
        Args:
            piece_count: Number of pieces (4-16)
            crack_complexity: Crack detail level (0.5-2.0)
            mosaic_mode: If True, uses glass shatter effect with 3D depth
        """
        import random as _random

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for crumble")
            return None

        # If there is no old image, simply set the base pixmap and repaint.
        if old_pixmap is None or old_pixmap.isNull():
            logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (crumble)")
            self._crossfade = None
            self._slide = None
            self._wipe = None
            self._crumble = None
            self._base_pixmap = new_pixmap
            self.update()
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
            return None

        # Crumble is mutually exclusive with other transitions.
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._blockflip = None
        self._blockspin = None
        self._blinds = None
        self._diffuse = None
        self._raindrops = None
        self._peel = None

        # Generate random seed if not provided
        actual_seed = seed if seed is not None else _random.random() * 1000.0

        self._crumble = CrumbleState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            progress=0.0,
            seed=actual_seed,
            piece_count=float(max(4, piece_count)),
            crack_complexity=max(0.5, min(2.0, crack_complexity)),
            mosaic_mode=mosaic_mode,
        )
        self._animation_manager = animation_manager
        self._current_easing = easing

        # PERFORMANCE: Pre-upload textures BEFORE animation starts
        if self._gl_pipeline is not None and self._use_shaders:
            try:
                self.makeCurrent()
                self._prepare_crumble_textures()
                self.doneCurrent()
            except Exception:
                logger.debug("[GL COMPOSITOR] Pre-upload textures failed", exc_info=True)

        # Cancel any previous animation on this compositor.
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception:
                pass
            self._current_anim_id = None

        self._profiler.start("crumble")

        def _crumble_update(progress: float) -> None:
            self._profiler.tick("crumble")
            if self._crumble is not None:
                p = max(0.0, min(1.0, float(progress)))
                self._crumble.progress = p

        duration_sec = max(0.001, duration_ms / 1000.0)
        frame_state = self._start_frame_pacing(duration_sec)
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=_crumble_update,
            on_complete=lambda: self._on_crumble_complete(on_finished),
            frame_state=frame_state,
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
        # NOTE: Do NOT call self.update() here - the render timer drives repaints
        # at the display refresh rate. Calling update() here would double the FPS.

    def _on_crossfade_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        # Stop frame pacing
        self._stop_frame_pacing()
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
        self._profiler.tick("slide")
        # NOTE: Do NOT call self.update() here - the render timer drives repaints
        # at the display refresh rate. Calling update() here would double the FPS.

    def _on_slide_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Handle completion of compositor-driven slide transitions."""
        try:
            # Complete profiling and emit metrics.
            self._profiler.complete("slide", viewport_size=(self.width(), self.height()))
            
            # Stop frame pacing
            self._stop_frame_pacing()

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
        self._profiler.tick("wipe")
        # NOTE: Do NOT call self.update() here - the render timer drives repaints

    def _on_wipe_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Handle completion of compositor-driven wipe transitions."""
        try:
            self._profiler.complete("wipe", viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()

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
                logger.debug("[GL COMPOSITOR] Wipe complete update failed: %s", e, exc_info=True)

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
        self._profiler.tick("blockspin")
        # NOTE: Do NOT call self.update() here - the render timer drives repaints

    def _on_warp_update(self, progress: float) -> None:
        """Update handler for compositor-driven warp dissolve transitions."""
        if self._warp is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._warp.progress = p
        self._profiler.tick("warp")
        # NOTE: Do NOT call self.update() here - the render timer drives repaints

    def _on_raindrops_update(self, progress: float) -> None:
        """Update handler for shader-driven raindrops transitions."""
        if self._raindrops is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._raindrops.progress = p
        self._profiler.tick("raindrops")
        # NOTE: Do NOT call self.update() here - the render timer drives repaints

    # NOTE: _on_shooting_stars_update() and _on_shuffle_update() removed - these transitions are retired.

    def _on_blockspin_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven block spin transitions."""
        try:
            self._profiler.complete("blockspin", viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()

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
                logger.debug("[GL COMPOSITOR] BlockSpin complete update failed: %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] BlockSpin complete handler failed: %s", e, exc_info=True)

    def _on_warp_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven warp dissolve transitions."""
        try:
            self._profiler.complete("warp", viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()

            try:
                self._release_transition_textures()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to release warp textures: %s", e, exc_info=True)

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
                logger.debug("[GL COMPOSITOR] Warp complete update failed: %s", e, exc_info=True)

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
            self._profiler.complete("raindrops", viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()

            try:
                self._release_transition_textures()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Failed to release raindrops textures: %s", e, exc_info=True)

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
                logger.debug("[GL COMPOSITOR] Raindrops complete update failed: %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Raindrops complete handler failed: %s", e, exc_info=True)

    # NOTE: _on_shuffle_complete() and _on_shooting_stars_complete() removed - these transitions are retired.

    def _on_peel_update(self, progress: float) -> None:
        """Update handler for compositor-driven peel transitions."""
        if self._peel is None:
            return
        p = max(0.0, min(1.0, float(progress)))
        self._peel.progress = p
        self._profiler.tick("peel")
        # NOTE: Do NOT call self.update() here - the render timer drives repaints

    def _on_peel_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven peel transitions."""
        try:
            self._profiler.complete("peel", viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()

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
                logger.debug("[GL COMPOSITOR] Peel complete update failed: %s", e, exc_info=True)

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
        self._profiler.tick("blockflip")
        # NOTE: Do NOT call self.update() here - the render timer drives repaints

    def _on_blockflip_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven block flip transitions."""
        try:
            self._profiler.complete("blockflip", viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()

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
                logger.debug("[GL COMPOSITOR] BlockFlip complete update failed: %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] BlockFlip complete handler failed: %s", e, exc_info=True)

    def _on_diffuse_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven diffuse transitions."""
        try:
            self._profiler.complete("diffuse", viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()

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
                logger.debug("[GL COMPOSITOR] Diffuse complete update failed: %s", e, exc_info=True)

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
            self._profiler.complete("blinds", viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()

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
                logger.debug("[GL COMPOSITOR] Blinds complete update failed: %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Blinds complete handler failed: %s", e, exc_info=True)

    def _on_crumble_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        """Completion handler for compositor-driven crumble transitions."""
        try:
            self._profiler.complete("crumble", viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()

            if self._crumble is not None:
                try:
                    self._base_pixmap = self._crumble.new_pixmap
                except Exception:
                    pass
            self._crumble = None
            self._current_anim_id = None

            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Crumble complete update failed: %s", e, exc_info=True)

            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Crumble complete handler failed: %s", e, exc_info=True)

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

        if new_pm is None and self._crumble is not None:
            try:
                new_pm = self._crumble.new_pixmap
            except Exception:
                new_pm = None

        # NOTE: _shooting_stars and _shuffle snap-to-new removed - these transitions are retired.

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
        self._crumble = None

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
        
        _pipeline_start = time.time()
        try:
            _shader_start = time.time()
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

            # Compile the Ripple (raindrops) shader program using the helper module.
            # On failure we disable shader usage for this session so that all
            # shader-backed transitions fall back to QPainter-based paths.
            try:
                raindrops_helper = _get_raindrops_program()
                rp = raindrops_helper.create_program()
                self._gl_pipeline.raindrops_program = rp
                self._gl_pipeline.raindrops_uniforms = raindrops_helper.cache_uniforms(rp)
                # Also populate legacy fields for any code still using them
                self._gl_pipeline.raindrops_u_progress = self._gl_pipeline.raindrops_uniforms.get("u_progress", -1)
                self._gl_pipeline.raindrops_u_resolution = self._gl_pipeline.raindrops_uniforms.get("u_resolution", -1)
                self._gl_pipeline.raindrops_u_old_tex = self._gl_pipeline.raindrops_uniforms.get("uOldTex", -1)
                self._gl_pipeline.raindrops_u_new_tex = self._gl_pipeline.raindrops_uniforms.get("uNewTex", -1)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize raindrops shader program", exc_info=True)
                self._gl_pipeline.raindrops_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Warp shader program using the helper module.
            try:
                warp_helper = _get_warp_program()
                wp = warp_helper.create_program()
                self._gl_pipeline.warp_program = wp
                self._gl_pipeline.warp_uniforms = warp_helper.cache_uniforms(wp)
                # Also populate legacy fields for any code still using them
                self._gl_pipeline.warp_u_progress = self._gl_pipeline.warp_uniforms.get("u_progress", -1)
                self._gl_pipeline.warp_u_resolution = self._gl_pipeline.warp_uniforms.get("u_resolution", -1)
                self._gl_pipeline.warp_u_old_tex = self._gl_pipeline.warp_uniforms.get("uOldTex", -1)
                self._gl_pipeline.warp_u_new_tex = self._gl_pipeline.warp_uniforms.get("uNewTex", -1)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize warp shader program", exc_info=True)
                self._gl_pipeline.warp_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Diffuse shader program using the helper module.
            # On failure we disable shader usage for this session so that all
            # shader-backed transitions fall back to QPainter-based paths.
            try:
                diffuse_helper = _get_diffuse_program()
                dp = diffuse_helper.create_program()
                self._gl_pipeline.diffuse_program = dp
                self._gl_pipeline.diffuse_uniforms = diffuse_helper.cache_uniforms(dp)
                # Also populate legacy fields for any code still using them
                self._gl_pipeline.diffuse_u_progress = self._gl_pipeline.diffuse_uniforms.get("u_progress", -1)
                self._gl_pipeline.diffuse_u_resolution = self._gl_pipeline.diffuse_uniforms.get("u_resolution", -1)
                self._gl_pipeline.diffuse_u_old_tex = self._gl_pipeline.diffuse_uniforms.get("uOldTex", -1)
                self._gl_pipeline.diffuse_u_new_tex = self._gl_pipeline.diffuse_uniforms.get("uNewTex", -1)
                self._gl_pipeline.diffuse_u_grid = self._gl_pipeline.diffuse_uniforms.get("u_grid", -1)
                self._gl_pipeline.diffuse_u_shape_mode = self._gl_pipeline.diffuse_uniforms.get("u_shapeMode", -1)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize diffuse shader program", exc_info=True)
                self._gl_pipeline.diffuse_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the BlockFlip shader program using the helper module.
            # On failure we disable shader usage for this session so that all
            # shader-backed transitions fall back to QPainter-based paths.
            try:
                blockflip_helper = _get_blockflip_program()
                bfp = blockflip_helper.create_program()
                self._gl_pipeline.blockflip_program = bfp
                self._gl_pipeline.blockflip_uniforms = blockflip_helper.cache_uniforms(bfp)
                # Also populate legacy fields for any code still using them
                self._gl_pipeline.blockflip_u_progress = self._gl_pipeline.blockflip_uniforms.get("u_progress", -1)
                self._gl_pipeline.blockflip_u_resolution = self._gl_pipeline.blockflip_uniforms.get("u_resolution", -1)
                self._gl_pipeline.blockflip_u_old_tex = self._gl_pipeline.blockflip_uniforms.get("uOldTex", -1)
                self._gl_pipeline.blockflip_u_new_tex = self._gl_pipeline.blockflip_uniforms.get("uNewTex", -1)
                self._gl_pipeline.blockflip_u_grid = self._gl_pipeline.blockflip_uniforms.get("u_grid", -1)
                self._gl_pipeline.blockflip_u_direction = self._gl_pipeline.blockflip_uniforms.get("u_direction", -1)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize blockflip shader program", exc_info=True)
                self._gl_pipeline.blockflip_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Peel shader program using the helper module.
            # On failure we disable shader usage for this session so that all
            # shader-backed transitions fall back to QPainter-based paths.
            try:
                peel_helper = _get_peel_program()
                pp = peel_helper.create_program()
                self._gl_pipeline.peel_program = pp
                self._gl_pipeline.peel_uniforms = peel_helper.cache_uniforms(pp)
                # Also populate legacy fields for any code still using them
                self._gl_pipeline.peel_u_progress = self._gl_pipeline.peel_uniforms.get("u_progress", -1)
                self._gl_pipeline.peel_u_resolution = self._gl_pipeline.peel_uniforms.get("u_resolution", -1)
                self._gl_pipeline.peel_u_old_tex = self._gl_pipeline.peel_uniforms.get("uOldTex", -1)
                self._gl_pipeline.peel_u_new_tex = self._gl_pipeline.peel_uniforms.get("uNewTex", -1)
                self._gl_pipeline.peel_u_direction = self._gl_pipeline.peel_uniforms.get("u_direction", -1)
                self._gl_pipeline.peel_u_strips = self._gl_pipeline.peel_uniforms.get("u_strips", -1)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize peel shader program", exc_info=True)
                self._gl_pipeline.peel_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Crossfade shader program using the helper module.
            try:
                crossfade_helper = _get_crossfade_program()
                xp = crossfade_helper.create_program()
                self._gl_pipeline.crossfade_program = xp
                self._gl_pipeline.crossfade_uniforms = crossfade_helper.cache_uniforms(xp)
                # Also populate legacy fields for any code still using them
                self._gl_pipeline.crossfade_u_progress = self._gl_pipeline.crossfade_uniforms.get("u_progress", -1)
                self._gl_pipeline.crossfade_u_resolution = self._gl_pipeline.crossfade_uniforms.get("u_resolution", -1)
                self._gl_pipeline.crossfade_u_old_tex = self._gl_pipeline.crossfade_uniforms.get("uOldTex", -1)
                self._gl_pipeline.crossfade_u_new_tex = self._gl_pipeline.crossfade_uniforms.get("uNewTex", -1)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize crossfade shader program", exc_info=True)
                self._gl_pipeline.crossfade_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Slide shader program using the helper module.
            try:
                slide_helper = _get_slide_program()
                slp = slide_helper.create_program()
                self._gl_pipeline.slide_program = slp
                self._gl_pipeline.slide_uniforms = slide_helper.cache_uniforms(slp)
                # Also populate legacy fields for any code still using them
                self._gl_pipeline.slide_u_progress = self._gl_pipeline.slide_uniforms.get("u_progress", -1)
                self._gl_pipeline.slide_u_resolution = self._gl_pipeline.slide_uniforms.get("u_resolution", -1)
                self._gl_pipeline.slide_u_old_tex = self._gl_pipeline.slide_uniforms.get("uOldTex", -1)
                self._gl_pipeline.slide_u_new_tex = self._gl_pipeline.slide_uniforms.get("uNewTex", -1)
                self._gl_pipeline.slide_u_old_rect = self._gl_pipeline.slide_uniforms.get("u_oldRect", -1)
                self._gl_pipeline.slide_u_new_rect = self._gl_pipeline.slide_uniforms.get("u_newRect", -1)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize slide shader program", exc_info=True)
                self._gl_pipeline.slide_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Wipe shader program using the helper module.
            try:
                wipe_helper = _get_wipe_program()
                wp2 = wipe_helper.create_program()
                self._gl_pipeline.wipe_program = wp2
                self._gl_pipeline.wipe_uniforms = wipe_helper.cache_uniforms(wp2)
                # Also populate legacy fields for any code still using them
                self._gl_pipeline.wipe_u_progress = self._gl_pipeline.wipe_uniforms.get("u_progress", -1)
                self._gl_pipeline.wipe_u_resolution = self._gl_pipeline.wipe_uniforms.get("u_resolution", -1)
                self._gl_pipeline.wipe_u_old_tex = self._gl_pipeline.wipe_uniforms.get("uOldTex", -1)
                self._gl_pipeline.wipe_u_new_tex = self._gl_pipeline.wipe_uniforms.get("uNewTex", -1)
                self._gl_pipeline.wipe_u_mode = self._gl_pipeline.wipe_uniforms.get("u_mode", -1)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize wipe shader program", exc_info=True)
                self._gl_pipeline.wipe_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Compile the Blinds shader program using the helper module.
            # On failure we disable shader usage for this session so that all
            # shader-backed transitions fall back to QPainter-based paths.
            try:
                blinds_helper = _get_blinds_program()
                bp = blinds_helper.create_program()
                self._gl_pipeline.blinds_program = bp
                self._gl_pipeline.blinds_uniforms = blinds_helper.cache_uniforms(bp)
                # Also populate legacy fields for any code still using them
                self._gl_pipeline.blinds_u_progress = self._gl_pipeline.blinds_uniforms.get("u_progress", -1)
                self._gl_pipeline.blinds_u_resolution = self._gl_pipeline.blinds_uniforms.get("u_resolution", -1)
                self._gl_pipeline.blinds_u_old_tex = self._gl_pipeline.blinds_uniforms.get("uOldTex", -1)
                self._gl_pipeline.blinds_u_new_tex = self._gl_pipeline.blinds_uniforms.get("uNewTex", -1)
                self._gl_pipeline.blinds_u_grid = self._gl_pipeline.blinds_uniforms.get("u_grid", -1)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize blinds shader program", exc_info=True)
                self._gl_pipeline.blinds_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # Initialize Crumble shader program
            try:
                crumble_helper = _get_crumble_program()
                cp = crumble_helper.create_program()
                self._gl_pipeline.crumble_program = cp
                self._gl_pipeline.crumble_uniforms = crumble_helper.cache_uniforms(cp)
            except Exception:
                logger.debug("[GL SHADER] Failed to initialize crumble shader program", exc_info=True)
                self._gl_pipeline.crumble_program = 0
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return

            # NOTE: Shuffle and Claws shader initialization removed - these transitions are retired.

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
            _pipeline_elapsed = (time.time() - _pipeline_start) * 1000.0
            if _pipeline_elapsed > 50.0 and is_perf_metrics_enabled():
                logger.warning("[PERF] [GL COMPOSITOR] Shader pipeline init took %.2fms", _pipeline_elapsed)
            else:
                logger.info("[GL COMPOSITOR] Shader pipeline initialized (%.1fms)", _pipeline_elapsed)
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

            # Clean up PBO pool
            try:
                self._cleanup_pbo_pool()
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup PBO pool", exc_info=True)

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

    # NOTE: _create_peel_program() has been moved to rendering/gl_programs/peel_program.py
    # The PeelProgram helper is now responsible for shader compilation and rendering.

    # NOTE: _create_wipe_program() has been moved to rendering/gl_programs/wipe_program.py
    # The WipeProgram helper is now responsible for shader compilation and rendering.

    # NOTE: _create_diffuse_program() has been moved to rendering/gl_programs/diffuse_program.py
    # The DiffuseProgram helper is now responsible for shader compilation and rendering.

    # NOTE: _create_blockflip_program() has been moved to rendering/gl_programs/blockflip_program.py
    # The BlockFlipProgram helper is now responsible for shader compilation and rendering.

    # NOTE: _create_blinds_program() has been moved to rendering/gl_programs/blinds_program.py
    # The BlindsProgram helper is now responsible for shader compilation and rendering.

    # NOTE: _create_crossfade_program() has been moved to rendering/gl_programs/crossfade_program.py
    # The CrossfadeProgram helper is now responsible for shader compilation and rendering.

    # NOTE: _create_slide_program() has been moved to rendering/gl_programs/slide_program.py
    # The SlideProgram helper is now responsible for shader compilation and rendering.

    # NOTE: _create_shuffle_program() REMOVED - Shuffle transition was retired (dead code)

    # NOTE: _create_warp_program() has been moved to rendering/gl_programs/warp_program.py
    # The WarpProgram helper is now responsible for shader compilation and rendering.

    # NOTE: _create_raindrops_program() has been moved to rendering/gl_programs/raindrops_program.py
    # The RaindropsProgram helper is now responsible for shader compilation and rendering.

    # NOTE: _create_claws_program() REMOVED - Claws/Shooting Stars transition was retired (dead code)

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

    def _can_use_crumble_shader(self) -> bool:
        return self._can_use_simple_shader(self._crumble, getattr(self._gl_pipeline, "crumble_program", 0))

    def _can_use_crossfade_shader(self) -> bool:
        return self._can_use_simple_shader(self._crossfade, getattr(self._gl_pipeline, "crossfade_program", 0))

    def _can_use_slide_shader(self) -> bool:
        return self._can_use_simple_shader(self._slide, getattr(self._gl_pipeline, "slide_program", 0))

    def _can_use_wipe_shader(self) -> bool:
        return self._can_use_simple_shader(self._wipe, getattr(self._gl_pipeline, "wipe_program", 0))

    # NOTE: _can_use_shuffle_shader() and _can_use_claws_shader() removed - these transitions are retired.

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

    def _get_or_create_pbo(self, required_size: int) -> int:
        """Get a PBO from the pool or create a new one.
        
        Returns PBO id or 0 on failure.
        """
        if gl is None or self._gl_pipeline is None:
            return 0
        
        # Look for an available PBO of sufficient size
        for i, (pbo_id, size, in_use) in enumerate(self._gl_pipeline.pbo_pool):
            if not in_use and size >= required_size:
                self._gl_pipeline.pbo_pool[i] = (pbo_id, size, True)
                return pbo_id
        
        # Create a new PBO
        try:
            pbo = gl.glGenBuffers(1)
            pbo_id = int(pbo)
            if pbo_id > 0:
                gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
                # Use GL_STREAM_DRAW for streaming uploads
                gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, required_size, None, gl.GL_STREAM_DRAW)
                gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
                self._gl_pipeline.pbo_pool.append((pbo_id, required_size, True))
                return pbo_id
        except Exception:
            pass
        return 0

    def _release_pbo(self, pbo_id: int) -> None:
        """Mark a PBO as available in the pool."""
        if self._gl_pipeline is None:
            return
        for i, (pid, size, in_use) in enumerate(self._gl_pipeline.pbo_pool):
            if pid == pbo_id:
                self._gl_pipeline.pbo_pool[i] = (pid, size, False)
                return

    def _cleanup_pbo_pool(self) -> None:
        """Delete all PBOs in the pool."""
        if gl is None or self._gl_pipeline is None:
            return
        for pbo_id, _, _ in self._gl_pipeline.pbo_pool:
            try:
                gl.glDeleteBuffers(1, [pbo_id])
            except Exception:
                pass
        self._gl_pipeline.pbo_pool.clear()
        self._gl_pipeline.pbo_pending_uploads.clear()

    def _upload_texture_from_pixmap(self, pixmap: QPixmap) -> int:
        """Upload a QPixmap as a GL texture and return its id.

        Returns 0 on failure. Caller is responsible for deleting the texture
        when no longer needed.
        
        Uses double-buffered PBOs for async DMA transfer:
        1. Map PBO to get CPU-accessible pointer
        2. Copy image data to mapped buffer (fast memcpy)
        3. Unmap PBO (triggers async DMA to GPU)
        4. Upload from PBO to texture (GPU-side, non-blocking)
        """
        _upload_start = time.time()

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

        # NOTE: No texture scaling - upload at native resolution.
        # Modern GPUs (RTX 4090, etc.) handle 4K textures with PBOs efficiently.
        # The PBO async DMA transfer below handles the upload without blocking.

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

        data_size = len(data)
        tex = gl.glGenTextures(1)
        tex_id = int(tex)
        
        # Try double-buffered PBO upload for better performance
        use_pbo = False
        pbo_id = 0
        
        try:
            if hasattr(gl, 'GL_PIXEL_UNPACK_BUFFER') and data_size > 0 and self._gl_pipeline is not None:
                pbo_id = self._get_or_create_pbo(data_size)
                if pbo_id > 0:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, pbo_id)
                    
                    # Use glMapBuffer to get a CPU-accessible pointer
                    # GL_WRITE_ONLY allows the driver to optimize for streaming
                    try:
                        # Orphan the buffer first to avoid sync stalls
                        gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, data_size, None, gl.GL_STREAM_DRAW)
                        
                        # Map the buffer for writing
                        mapped_ptr = gl.glMapBuffer(gl.GL_PIXEL_UNPACK_BUFFER, gl.GL_WRITE_ONLY)
                        if mapped_ptr:
                            # Copy data to mapped buffer using ctypes memmove
                            ctypes.memmove(mapped_ptr, data, data_size)
                            gl.glUnmapBuffer(gl.GL_PIXEL_UNPACK_BUFFER)
                            use_pbo = True
                        else:
                            # Fallback: use glBufferSubData if mapping fails
                            gl.glBufferSubData(gl.GL_PIXEL_UNPACK_BUFFER, 0, data_size, data)
                            use_pbo = True
                    except Exception:
                        # glMapBuffer not available, use glBufferData
                        gl.glBufferData(gl.GL_PIXEL_UNPACK_BUFFER, data_size, data, gl.GL_STREAM_DRAW)
                        use_pbo = True
        except Exception:
            # PBO not available or failed - fall back to direct upload
            use_pbo = False
            if pbo_id > 0:
                try:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
                    self._release_pbo(pbo_id)
                except Exception:
                    pass
                pbo_id = 0

        gl.glBindTexture(gl.GL_TEXTURE_2D, tex_id)
        try:
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
            gl.glPixelStorei(gl.GL_UNPACK_ALIGNMENT, 1)
            
            if use_pbo:
                # Upload from PBO (async DMA transfer)
                # The actual data transfer happens asynchronously on the GPU
                gl.glTexImage2D(
                    gl.GL_TEXTURE_2D,
                    0,
                    gl.GL_RGBA8,
                    w,
                    h,
                    0,
                    gl.GL_BGRA,
                    gl.GL_UNSIGNED_BYTE,
                    None,  # Data comes from bound PBO
                )
            else:
                # Direct upload (synchronous)
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
            if pbo_id > 0:
                try:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
                    self._release_pbo(pbo_id)
                except Exception:
                    pass
            return 0
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            # Unbind and release PBO back to pool
            if pbo_id > 0:
                try:
                    gl.glBindBuffer(gl.GL_PIXEL_UNPACK_BUFFER, 0)
                    self._release_pbo(pbo_id)
                except Exception:
                    pass

        # Log slow texture uploads
        _upload_elapsed = (time.time() - _upload_start) * 1000.0
        if _upload_elapsed > 20.0 and is_perf_metrics_enabled():
            logger.warning("[PERF] [GL COMPOSITOR] Slow texture upload: %.2fms (%dx%d, pbo=%s)", _upload_elapsed, w, h, use_pbo)

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
        # PERFORMANCE: Early exit if textures already prepared (same pattern as slide/wipe)
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
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
        # PERFORMANCE: Early exit if textures already prepared
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._peel is None:
            return False
        st = self._peel
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_blinds_textures(self) -> bool:
        if not self._can_use_blinds_shader():
            return False
        if self._gl_pipeline is None:
            return False
        # PERFORMANCE: Early exit if textures already prepared
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._blinds is None:
            return False
        st = self._blinds
        return self._prepare_pair_textures(st.old_pixmap, st.new_pixmap)

    def _prepare_crumble_textures(self) -> bool:
        if not self._can_use_crumble_shader():
            return False
        if self._gl_pipeline is None:
            return False
        # PERFORMANCE: Early exit if textures already prepared
        if self._gl_pipeline.old_tex_id and self._gl_pipeline.new_tex_id:
            return True
        if self._crumble is None:
            return False
        st = self._crumble
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

    # NOTE: _prepare_shuffle_textures() removed - Shuffle transition is retired.

    def _get_viewport_size(self) -> tuple[int, int]:
        """Return the framebuffer viewport size in physical pixels.
        
        PERFORMANCE OPTIMIZED: Caches the result and only recalculates when
        widget size changes. This eliminates per-frame DPR lookups and float
        conversions in the hot render path.
        """
        current_size = (self.width(), self.height())
        
        # Return cached value if widget size hasn't changed
        if self._cached_viewport is not None and self._cached_widget_size == current_size:
            return self._cached_viewport
        
        # Recalculate viewport size
        try:
            dpr = float(self.devicePixelRatioF())
        except Exception:
            dpr = 1.0
        w = max(1, int(round(current_size[0] * dpr)))
        h = max(1, int(round(current_size[1] * dpr)))
        # Guard against off-by-one rounding between Qt's reported size and
        # the underlying framebuffer by slightly over-covering vertically.
        # This prevents a 1px retained strip from the previous frame at the
        # top edge on certain DPI/size combinations.
        h = max(1, h + 1)
        
        # Cache the result
        self._cached_viewport = (w, h)
        self._cached_widget_size = current_size
        return self._cached_viewport

    def _paint_blockspin_shader(self, target: QRect) -> None:
        """Render 3D Block Spin transition.
        
        PERFORMANCE OPTIMIZED: Uses module-level easing function and avoids
        per-frame list comprehensions.
        """
        if not self._can_use_blockspin_shader() or self._gl_pipeline is None or self._blockspin is None:
            return
        if not self._prepare_blockspin_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        w = max(1, target.width())
        h = max(1, target.height())

        st = self._blockspin
        base_p = st.progress  # Already 0..1 float, no conversion needed

        aspect = w / h  # Python 3 division is float by default

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

            # Single full-frame slab. Direction is applied as a sign on the
            # spin so LEFT/RIGHT and UP/DOWN produce mirrored rotations while
            # still ending on the same final orientation.
            spin = _blockspin_spin_from_progress(base_p)
            angle = math.pi * spin * spin_dir
            
            # PERFORMANCE: Inlined _draw_slab to avoid per-frame nested function
            # and list comprehensions. Values are already floats.
            if self._gl_pipeline.u_angle_loc != -1:
                gl.glUniform1f(self._gl_pipeline.u_angle_loc, angle)
            if self._gl_pipeline.u_block_rect_loc != -1:
                gl.glUniform4f(self._gl_pipeline.u_block_rect_loc, -1.0, -1.0, 1.0, 1.0)
            if self._gl_pipeline.u_block_uv_rect_loc != -1:
                gl.glUniform4f(self._gl_pipeline.u_block_uv_rect_loc, 0.0, 0.0, 1.0, 1.0)

            # Prefer the dedicated box mesh for a true 3D slab; fall back to
            # the fullscreen quad if the box geometry was not created.
            box_vao = getattr(self._gl_pipeline, "box_vao", 0)
            box_count = getattr(self._gl_pipeline, "box_vertex_count", 0)
            if box_vao and box_count > 0:
                gl.glBindVertexArray(box_vao)
                gl.glDrawArrays(gl.GL_TRIANGLES, 0, box_count)
                gl.glBindVertexArray(0)
            else:
                gl.glBindVertexArray(self._gl_pipeline.quad_vao)
                gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
                gl.glBindVertexArray(0)
        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _paint_peel_shader(self, target: QRect) -> None:
        """Render Peel transition using the PeelProgram helper."""
        if not self._can_use_peel_shader() or self._gl_pipeline is None or self._peel is None:
            return
        st = self._peel
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_peel_textures():
            return

        vp_w, vp_h = self._get_viewport_size()

        # Delegate rendering to the PeelProgram helper
        peel_helper = _get_peel_program()
        peel_helper.render(
            program=self._gl_pipeline.peel_program,
            uniforms=self._gl_pipeline.peel_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
        )

    # NOTE: _paint_claws_shader() REMOVED - Claws/Shooting Stars transition was retired (dead code)

    def _paint_crumble_shader(self, target: QRect) -> None:
        """Render Crumble transition using the CrumbleProgram helper."""
        if not self._can_use_crumble_shader() or self._gl_pipeline is None or self._crumble is None:
            return
        st = self._crumble
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_crumble_textures():
            return
        # Track paint timing and approximate GPU duration around the shader
        # draw call. This is only used when PERF metrics are enabled and
        # adds negligible overhead compared to the actual GL work.
        self._profiler.tick_paint("crumble")

        start_gpu = time.perf_counter()
        vp_w, vp_h = self._get_viewport_size()
        crumble_helper = _get_crumble_program()
        crumble_helper.render(
            program=self._gl_pipeline.crumble_program,
            uniforms=self._gl_pipeline.crumble_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
        )
        try:
            gpu_ms = max(0.0, float((time.perf_counter() - start_gpu) * 1000.0))
            self._profiler.tick_gpu("crumble", gpu_ms)
        except Exception:
            # GPU timing is best-effort only; never affect rendering.
            pass

    def _paint_blinds_shader(self, target: QRect) -> None:
        """Render Blinds transition using the BlindsProgram helper."""
        if not self._can_use_blinds_shader() or self._gl_pipeline is None or self._blinds is None:
            return
        st = self._blinds
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_blinds_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        blinds_helper = _get_blinds_program()
        blinds_helper.render(
            program=self._gl_pipeline.blinds_program,
            uniforms=self._gl_pipeline.blinds_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
        )

    def _paint_wipe_shader(self, target: QRect) -> None:
        """Render Wipe transition using the WipeProgram helper."""
        if not self._can_use_wipe_shader() or self._gl_pipeline is None or self._wipe is None:
            return
        st = self._wipe
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_wipe_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        wipe_helper = _get_wipe_program()
        wipe_helper.render(
            program=self._gl_pipeline.wipe_program,
            uniforms=self._gl_pipeline.wipe_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
        )

    def _paint_slide_shader(self, target: QRect) -> None:
        """Render Slide transition using the SlideProgram helper.
        
        PERFORMANCE OPTIMIZED: Uses pre-computed float coordinates from SlideState
        to avoid per-frame QPoint.x()/y() calls and float() conversions.
        """
        if not self._can_use_slide_shader() or self._gl_pipeline is None or self._slide is None:
            return
        st = self._slide
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_slide_textures():
            return
        # Track actual paint timing (after all early-exit checks)
        self._profiler.tick_paint("slide")

        # PERFORMANCE: Use pre-computed float coordinates from SlideState
        # This eliminates 8x float() conversions and 8x QPoint method calls per frame
        w = max(1, target.width())
        h = max(1, target.height())
        inv_w = 1.0 / w
        inv_h = 1.0 / h

        # FRAME PACING: Use interpolated progress from compositor's FrameState
        # Fall back to state progress if frame pacing not active
        t = self._get_render_progress(fallback=st.progress)
        
        # Use pre-computed deltas for interpolation
        old_x = (st._old_start_x + st._old_delta_x * t) * inv_w
        old_y = (st._old_start_y + st._old_delta_y * t) * inv_h
        new_x = (st._new_start_x + st._new_delta_x * t) * inv_w
        new_y = (st._new_start_y + st._new_delta_y * t) * inv_h

        start_gpu = time.perf_counter()
        vp_w, vp_h = self._get_viewport_size()
        slide_helper = _get_slide_program()
        slide_helper.render(
            program=self._gl_pipeline.slide_program,
            uniforms=self._gl_pipeline.slide_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
            old_rect=(old_x, old_y, 1.0, 1.0),
            new_rect=(new_x, new_y, 1.0, 1.0),
        )
        try:
            gpu_ms = max(0.0, float((time.perf_counter() - start_gpu) * 1000.0))
            self._profiler.tick_gpu("slide", gpu_ms)
        except Exception:
            pass

    def _paint_crossfade_shader(self, target: QRect) -> None:
        """Render Crossfade transition using the CrossfadeProgram helper."""
        if not self._can_use_crossfade_shader() or self._gl_pipeline is None or self._crossfade is None:
            return
        st = self._crossfade
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_crossfade_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        crossfade_helper = _get_crossfade_program()
        crossfade_helper.render(
            program=self._gl_pipeline.crossfade_program,
            uniforms=self._gl_pipeline.crossfade_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
        )

    def _paint_diffuse_shader(self, target: QRect) -> None:
        """Render Diffuse transition using the DiffuseProgram helper."""
        if not self._can_use_diffuse_shader() or self._gl_pipeline is None or self._diffuse is None:
            return
        st = self._diffuse
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_diffuse_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        diffuse_helper = _get_diffuse_program()
        diffuse_helper.render(
            program=self._gl_pipeline.diffuse_program,
            uniforms=self._gl_pipeline.diffuse_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
        )

    def _paint_blockflip_shader(self, target: QRect) -> None:
        """Render BlockFlip transition using the BlockFlipProgram helper."""
        if not self._can_use_blockflip_shader() or self._gl_pipeline is None or self._blockflip is None:
            return
        st = self._blockflip
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_blockflip_textures():
            return

        vp_w, vp_h = self._get_viewport_size()

        # Delegate rendering to the BlockFlipProgram helper
        blockflip_helper = _get_blockflip_program()
        blockflip_helper.render(
            program=self._gl_pipeline.blockflip_program,
            uniforms=self._gl_pipeline.blockflip_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
        )

    # NOTE: _paint_shuffle_shader() removed - Shuffle transition is retired.

    def _paint_warp_shader(self, target: QRect) -> None:
        """Render Warp Dissolve transition using the WarpProgram helper."""
        if not self._can_use_warp_shader() or self._gl_pipeline is None or self._warp is None:
            return
        st = self._warp
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_warp_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        warp_helper = _get_warp_program()
        warp_helper.render(
            program=self._gl_pipeline.warp_program,
            uniforms=self._gl_pipeline.warp_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
        )

    def _paint_raindrops_shader(self, target: QRect) -> None:
        """Render Raindrops transition using the RaindropsProgram helper."""
        if not self._can_use_raindrops_shader() or self._gl_pipeline is None or self._raindrops is None:
            return
        st = self._raindrops
        if not st.old_pixmap or st.old_pixmap.isNull() or not st.new_pixmap or st.new_pixmap.isNull():
            return
        if not self._prepare_raindrops_textures():
            return

        vp_w, vp_h = self._get_viewport_size()
        raindrops_helper = _get_raindrops_program()
        raindrops_helper.render(
            program=self._gl_pipeline.raindrops_program,
            uniforms=self._gl_pipeline.raindrops_uniforms,
            viewport=(vp_w, vp_h),
            old_tex=self._gl_pipeline.old_tex_id,
            new_tex=self._gl_pipeline.new_tex_id,
            state=st,
            quad_vao=self._gl_pipeline.quad_vao,
        )

    def _paint_debug_overlay(self, painter: QPainter) -> None:
        """Paint debug overlay showing transition profiling metrics."""
        if not is_perf_metrics_enabled():
            return

        # Map transition states to their profiler names and display labels
        transitions = [
            ("slide", self._slide, "Slide"),
            ("wipe", self._wipe, "Wipe"),
            ("peel", self._peel, "Peel"),
            ("blockspin", self._blockspin, "BlockSpin"),
            ("warp", self._warp, "Warp"),
            ("raindrops", self._raindrops, "Ripple"),
            ("blockflip", self._blockflip, "BlockFlip"),
            ("diffuse", self._diffuse, "Diffuse"),
            ("blinds", self._blinds, "Blinds"),
        ]

        active_label = None
        line1 = ""
        line2 = ""

        for name, state, label in transitions:
            if state is None:
                continue
            metrics = self._profiler.get_metrics(name)
            if metrics is None:
                continue
            avg_fps, min_dt_ms, max_dt_ms, _ = metrics
            progress = getattr(state, "progress", 0.0)
            active_label = label
            line1 = f"{label} t={progress:.2f}"
            line2 = f"{avg_fps:.1f} fps  dt_min={min_dt_ms:.1f}ms  dt_max={max_dt_ms:.1f}ms"
            break

        if not active_label:
            return

        painter.save()
        try:
            text = f"{line1}\n{line2}" if line2 else line1
            fm = painter.fontMetrics()
            lines = text.split("\n")
            max_width = max(fm.horizontalAdvance(s) for s in lines)
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
        _paint_start = time.time()
        try:
            self._paintGL_impl()
        finally:
            # Log slow paintGL calls - this ALWAYS runs regardless of which path was taken
            _paint_elapsed = (time.time() - _paint_start) * 1000.0
            if _paint_elapsed > 50.0 and is_perf_metrics_enabled():
                logger.warning("[PERF] [GL COMPOSITOR] Slow paintGL: %.2fms", _paint_elapsed)

    def _paintGL_impl(self) -> None:
        """Internal paintGL implementation."""
        target = self.rect()

        # Prefer the shader path for Block Spins when available. On any failure
        # we log and fall back to the existing QPainter implementation.
        if self._blockspin is not None and self._can_use_blockspin_shader():
            try:
                if self._prepare_blockspin_textures():
                    self._paint_blockspin_shader(target)
                    self._paint_dimming_gl()
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
                self._paint_dimming_gl()
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
                self._paint_dimming_gl()
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

        # NOTE: Shuffle and Shooting Stars shader paths removed - these transitions are retired.

        if self._warp is not None and self._can_use_warp_shader():
            try:
                self._paint_warp_shader(target)
                self._paint_dimming_gl()
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
                self._paint_dimming_gl()
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
                self._paint_dimming_gl()
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
                self._paint_dimming_gl()
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

        if self._crumble is not None and self._can_use_crumble_shader():
            try:
                self._paint_crumble_shader(target)
                self._paint_dimming_gl()
                self._paint_spotify_visualizer_gl()
                if is_perf_metrics_enabled():
                    self._paint_debug_overlay_gl()
                return
            except Exception:
                logger.debug(
                    "[GL SHADER] Shader crumble path failed; disabling shader pipeline",
                    exc_info=True,
                )
                self._gl_disabled_for_session = True
                self._use_shaders = False

        if self._crossfade is not None and self._can_use_crossfade_shader():
            try:
                self._paint_crossfade_shader(target)
                self._paint_dimming_gl()
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
                self._paint_dimming_gl()
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
                self._paint_dimming_gl()
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
                self._paint_dimming(painter)
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
                self._paint_dimming(painter)
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

            self._paint_dimming(painter)
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
    
    def _paint_dimming(self, painter: QPainter) -> None:
        """Paint the dimming overlay if enabled."""
        if not self._dimming_enabled or self._dimming_opacity <= 0.0:
            return
        
        try:
            painter.save()
            painter.setOpacity(self._dimming_opacity)
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
            painter.restore()
        except Exception:
            pass
    
    def _paint_dimming_gl(self) -> None:
        """Paint dimming overlay in GL context (for shader paths)."""
        if not self._dimming_enabled or self._dimming_opacity <= 0.0:
            return
        
        painter = QPainter(self)
        try:
            self._paint_dimming(painter)
        finally:
            painter.end()
