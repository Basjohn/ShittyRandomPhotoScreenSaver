"""GL Compositor Transition Start Methods - Extracted from gl_compositor.py.

Contains all transition-specific start methods (crossfade, warp, raindrops,
wipe, slide, peel, block_flip, block_spin, diffuse, blinds, crumble, particle).
All functions accept the compositor widget instance as the first parameter.
"""

from __future__ import annotations

from typing import Optional, Callable, TYPE_CHECKING

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPixmap

from core.logging.logger import get_logger
from core.animation import AnimationManager
from core.animation.easing import EasingCurve
from transitions.wipe_transition import WipeDirection
from transitions.slide_transition import SlideDirection
from rendering.transition_state import (
    SlideState,
    WipeState,
    WarpState,
    BlockFlipState,
    RaindropsState,
    BlockSpinState,
    PeelState,
    BlindsState,
    DiffuseState,
    CrumbleState,
    ParticleState,
)

try:
    from OpenGL import GL as gl  # type: ignore[import]
except ImportError:
    gl = None

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def start_crossfade(
    widget,
    old_pixmap: Optional[QPixmap],
    new_pixmap: QPixmap,
    *,
    duration_ms: int,
    easing: EasingCurve,
    animation_manager: AnimationManager,
    on_finished: Optional[Callable[[], None]] = None,
) -> Optional[str]:
    """Begin a crossfade between two pixmaps using the compositor.
    
    OPTIMIZATION: Uses desync strategy to spread transition start overhead.
    Each compositor gets a random delay (0-500ms) with duration compensation
    to maintain visual synchronization across displays.
    """
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for crossfade")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "crossfade"):
            return None

    # Apply desync strategy: random delay with duration compensation
    delay_ms, compensated_duration = widget._apply_desync_strategy(duration_ms)
    
    if delay_ms > 0:
        # Use the exact pixmaps we were asked to transition between; do not mutate the
        # compositor base until the animation actually starts.
        from PySide6.QtCore import QTimer

        def deferred_start():
            if old_pixmap is None or old_pixmap.isNull():
                # If the caller did not provide a previous frame, we cannot animate.
                widget._handle_no_old_image(new_pixmap, on_finished, "crossfade")
                return
            widget._start_crossfade_impl(
                old_pixmap, new_pixmap, compensated_duration, easing, animation_manager, on_finished
            )

        QTimer.singleShot(delay_ms, deferred_start)
        return None  # Animation ID will be set when transition actually starts
    else:
        return widget._start_crossfade_impl(
            old_pixmap, new_pixmap, compensated_duration, easing, animation_manager, on_finished
        )

def start_warp(
    widget,
    old_pixmap: Optional[QPixmap],
    new_pixmap: QPixmap,
    *,
    duration_ms: int,
    easing: EasingCurve,
    animation_manager: AnimationManager,
    on_finished: Optional[Callable[[], None]] = None,
) -> Optional[str]:
    """Begin a warp dissolve between two pixmaps using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for warp dissolve")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "warp"):
            return None

    widget._clear_all_transitions()
    widget._warp = WarpState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0)
    widget._pre_upload_textures(widget._prepare_warp_textures)
    widget._profiler.start("warp")
    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        widget._on_warp_update,
        lambda: widget._on_warp_complete(on_finished),
        transition_label="warp",
    )

def start_raindrops(
    widget,
    old_pixmap: Optional[QPixmap],
    new_pixmap: QPixmap,
    *,
    duration_ms: int,
    easing: EasingCurve,
    animation_manager: AnimationManager,
    on_finished: Optional[Callable[[], None]] = None,
    ripple_count: int = 3,
) -> Optional[str]:
    """Begin a shader-driven raindrops transition. Returns None if shader unavailable."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for raindrops")
        return None

    # Only use this path when the GLSL pipeline and raindrops shader are available
    if (widget._gl_disabled_for_session or gl is None or widget._gl_pipeline is None
            or not widget._gl_pipeline.initialized or not widget._gl_pipeline.raindrops_program):
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "raindrops"):
            return None

    widget._clear_all_transitions()
    widget._raindrops = RaindropsState(
        old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0,
        ripple_count=max(1, min(8, int(ripple_count))),
    )
    widget._pre_upload_textures(widget._prepare_raindrops_textures)
    widget._profiler.start("raindrops")
    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        widget._on_raindrops_update,
        lambda: widget._on_raindrops_complete(on_finished),
        transition_label="raindrops",
    )

# NOTE: start_shuffle_shader() and start_shooting_stars() removed - these transitions are retired.

def start_wipe(
    widget,
    old_pixmap: Optional[QPixmap],
    new_pixmap: QPixmap,
    *,
    direction: WipeDirection,
    duration_ms: int,
    easing: EasingCurve,
    animation_manager: AnimationManager,
    on_finished: Optional[Callable[[], None]] = None,
) -> Optional[str]:
    """Begin a wipe between two pixmaps using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for wipe")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "wipe"):
            return None

    widget._clear_all_transitions()
    widget._wipe = WipeState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, direction=direction, progress=0.0)
    widget._pre_upload_textures(widget._prepare_wipe_textures)
    widget._profiler.start("wipe")
    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        widget._on_wipe_update,
        lambda: widget._on_wipe_complete(on_finished),
        transition_label="wipe",
    )

def start_slide(
    widget,
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
    """Begin a slide between two pixmaps using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for slide")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "slide"):
            return None

    widget._clear_all_transitions()
    widget._slide = SlideState(
        old_pixmap=old_pixmap, new_pixmap=new_pixmap,
        old_start=old_start, old_end=old_end,
        new_start=new_start, new_end=new_end, progress=0.0,
    )
    widget._pre_upload_textures(widget._prepare_slide_textures)
    widget._profiler.start("slide")
    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        widget._on_slide_update,
        lambda: widget._on_slide_complete(on_finished),
        transition_label="slide",
    )

def start_peel(
    widget,
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
    """Begin a strip-based peel between two pixmaps using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for peel")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "peel"):
            return None

    widget._clear_all_transitions()
    widget._peel = PeelState(
        old_pixmap=old_pixmap, new_pixmap=new_pixmap,
        direction=direction, strips=max(1, int(strips)), progress=0.0,
    )
    widget._pre_upload_textures(widget._prepare_peel_textures)
    widget._profiler.start("peel")
    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        widget._on_peel_update,
        lambda: widget._on_peel_complete(on_finished),
        transition_label="peel",
    )

def start_block_flip(
    widget,
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
    """Begin a block puzzle flip using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for block flip")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "block flip"):
            return None

    widget._clear_all_transitions()
    widget._blockflip = BlockFlipState(
        old_pixmap=old_pixmap, new_pixmap=new_pixmap, region=None,
        cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
        rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
        direction=direction,
    )
    widget._pre_upload_textures(widget._prepare_blockflip_textures)
    widget._profiler.start("blockflip")

    def _blockflip_profiled_update(progress: float, *, _inner=update_callback) -> None:
        widget._profiler.tick("blockflip")
        try:
            if widget._blockflip is not None:
                widget._blockflip.progress = max(0.0, min(1.0, float(progress)))
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        _inner(progress)

    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        _blockflip_profiled_update,
        lambda: widget._on_blockflip_complete(on_finished),
        transition_label="blockflip",
    )

def start_block_spin(
    widget,
    old_pixmap: Optional[QPixmap],
    new_pixmap: QPixmap,
    *,
    duration_ms: int,
    easing: EasingCurve,
    animation_manager: AnimationManager,
    direction: SlideDirection = SlideDirection.LEFT,
    on_finished: Optional[Callable[[], None]] = None,
) -> Optional[str]:
    """Begin a 3D block spin using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for block spin")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "block spin"):
            return None

    widget._clear_all_transitions()
    widget._blockspin = BlockSpinState(
        old_pixmap=old_pixmap, new_pixmap=new_pixmap, direction=direction, progress=0.0,
    )
    widget._pre_upload_textures(widget._prepare_blockspin_textures)
    widget._profiler.start("blockspin")
    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        widget._on_blockspin_update,
        lambda: widget._on_blockspin_complete(on_finished),
        transition_label="blockspin",
    )

def start_diffuse(
    widget,
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
    """Begin a diffuse reveal using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for diffuse")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "diffuse"):
            return None

    # Map shape name to integer for GLSL shader
    shape_mode = {"membrane": 1, "lines": 2, "diamonds": 3, "amorph": 4}.get(
        (shape or "").strip().lower(), 0
    )

    widget._clear_all_transitions()
    widget._diffuse = DiffuseState(
        old_pixmap=old_pixmap, new_pixmap=new_pixmap, region=None,
        cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
        rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
        shape_mode=int(shape_mode),
    )
    widget._pre_upload_textures(widget._prepare_diffuse_textures)
    widget._profiler.start("diffuse")

    def _diffuse_profiled_update(progress: float, *, _inner=update_callback) -> None:
        widget._profiler.tick("diffuse")
        try:
            if widget._diffuse is not None:
                widget._diffuse.progress = max(0.0, min(1.0, float(progress)))
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        _inner(progress)

    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        _diffuse_profiled_update,
        lambda: widget._on_diffuse_complete(on_finished),
        transition_label="diffuse",
    )

def start_blinds(
    widget,
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
    """Begin a blinds reveal using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for blinds")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "blinds"):
            return None

    widget._clear_all_transitions()
    widget._blinds = BlindsState(
        old_pixmap=old_pixmap, new_pixmap=new_pixmap, region=None,
        cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
        rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
    )
    widget._pre_upload_textures(widget._prepare_blinds_textures)
    widget._profiler.start("blinds")

    def _blinds_profiled_update(progress: float, *, _inner=update_callback) -> None:
        widget._profiler.tick("blinds")
        try:
            if widget._blinds is not None:
                widget._blinds.progress = max(0.0, min(1.0, float(progress)))
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        _inner(progress)

    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        _blinds_profiled_update,
        lambda: widget._on_blinds_complete(on_finished),
        transition_label="blinds",
    )

def start_crumble(
    widget,
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
    weight_mode: float = 0.0,
    seed: Optional[float] = None,
) -> Optional[str]:
    """Begin a crumble transition using the compositor."""
    import random as _random

    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for crumble")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "crumble"):
            return None

    widget._clear_all_transitions()
    actual_seed = seed if seed is not None else _random.random() * 1000.0
    widget._crumble = CrumbleState(
        old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0,
        seed=actual_seed, piece_count=float(max(4, piece_count)),
        crack_complexity=max(0.5, min(2.0, crack_complexity)),
        mosaic_mode=mosaic_mode, weight_mode=max(0.0, min(4.0, float(weight_mode))),
    )
    widget._pre_upload_textures(widget._prepare_crumble_textures)
    widget._profiler.start("crumble")

    def _crumble_update(progress: float) -> None:
        widget._profiler.tick("crumble")
        if widget._crumble is not None:
            widget._crumble.progress = max(0.0, min(1.0, float(progress)))

    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        _crumble_update,
        lambda: widget._on_crumble_complete(on_finished),
        transition_label="crumble",
    )

def start_particle(
    widget,
    old_pixmap: Optional[QPixmap],
    new_pixmap: QPixmap,
    *,
    duration_ms: int,
    easing: EasingCurve,
    animation_manager: AnimationManager,
    on_finished: Optional[Callable[[], None]] = None,
    mode: int = 0,
    direction: int = 0,
    particle_radius: float = 24.0,
    overlap: float = 4.0,
    trail_length: float = 0.15,
    trail_strength: float = 0.6,
    swirl_strength: float = 1.0,
    swirl_turns: float = 2.0,
    use_3d_shading: bool = True,
    texture_mapping: bool = True,
    wobble: bool = False,
    gloss_size: float = 64.0,
    light_direction: int = 0,
    swirl_order: int = 0,
    seed: Optional[float] = None,
) -> Optional[str]:
    """Begin a particle transition using the compositor.
    
    Args:
        mode: 0=Directional, 1=Swirl
        direction: 0-7=directions, 8=random, 9=random placement
        particle_radius: Base particle radius in pixels
        overlap: Overlap in pixels to avoid gaps
        trail_length: Trail length as fraction of particle size
        trail_strength: Trail opacity 0..1
        swirl_strength: Angular component for swirl mode
        swirl_turns: Number of spiral turns
        use_3d_shading: Enable 3D ball shading
        texture_mapping: Map new image onto particles
        seed: Random seed (auto-generated if None)
    """
    import random as _random

    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for particle")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "particle"):
            return None

    widget._clear_all_transitions()
    actual_seed = seed if seed is not None else _random.random() * 1000.0
    widget._particle = ParticleState(
        old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0,
        seed=actual_seed, mode=mode, direction=direction,
        particle_radius=max(8.0, particle_radius),
        overlap=max(0.0, overlap),
        trail_length=max(0.0, min(1.0, trail_length)),
        trail_strength=max(0.0, min(1.0, trail_strength)),
        swirl_strength=max(0.0, swirl_strength),
        swirl_turns=max(0.5, swirl_turns),
        use_3d_shading=use_3d_shading,
        texture_mapping=texture_mapping,
        wobble=wobble,
        gloss_size=max(16.0, min(128.0, gloss_size)),
        light_direction=max(0, min(4, light_direction)),
        swirl_order=max(0, min(2, swirl_order)),
    )
    widget._pre_upload_textures(widget._prepare_particle_textures)
    widget._profiler.start("particle")

    def _particle_update(progress: float) -> None:
        widget._profiler.tick("particle")
        if widget._particle is not None:
            widget._particle.progress = max(0.0, min(1.0, float(progress)))

    return widget._start_transition_animation(
        duration_ms, easing, animation_manager,
        _particle_update,
        lambda: widget._on_particle_complete(on_finished),
        transition_label="particle",
    )

# ------------------------------------------------------------------
# Animation callbacks
# ------------------------------------------------------------------

