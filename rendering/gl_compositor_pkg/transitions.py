"""GL Compositor Transition Start Methods - Extracted from gl_compositor.py.

Contains all transition-specific start methods (crossfade, warp, raindrops,
wipe, slide, block_flip, block_spin, diffuse, blinds, crumble, particle).
All functions accept the compositor widget instance as the first parameter.
"""

from __future__ import annotations

from typing import Optional, Callable, TYPE_CHECKING

from PySide6.QtCore import QPoint, QTimer
from PySide6.QtGui import QPixmap

from core.logging.logger import get_logger
from core.animation import AnimationManager
from core.animation.easing import EasingCurve
from transitions.base_transition import WipeDirection, SlideDirection
from rendering.transition_state import (
    SlideState,
    WipeState,
    WarpState,
    BlockFlipState,
    RaindropsState,
    BlockSpinState,
    BlindsState,
    DiffuseState,
    CrumbleState,
    ParticleState,
    BurnState,
)

try:
    from OpenGL import GL as gl  # type: ignore[import]
except ImportError:
    gl = None

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def _start_with_desync(
    widget,
    *,
    duration_ms: int,
    starter: Callable[[int], Optional[str]],
    transition_label: str,
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Spread transition-start overhead without changing perceived pacing."""
    delay_ms, compensated_duration = widget._apply_desync_strategy(duration_ms)
    if delay_ms <= 0:
        if on_started is not None:
            on_started(compensated_duration)
        return starter(compensated_duration)

    scheduled_generation = getattr(widget, "_transition_animation_generation", 0)

    def deferred_start() -> None:
        try:
            if (
                getattr(widget, "_render_shutdown_requested", False)
                or scheduled_generation != getattr(widget, "_transition_animation_generation", 0)
            ):
                logger.debug(
                    "[GL COMPOSITOR] Suppressed stale deferred %s start after compositor lifecycle changed",
                    transition_label,
                )
                return
            if on_started is not None:
                on_started(compensated_duration)
            starter(compensated_duration)
        except Exception:
            logger.debug(
                "[GL COMPOSITOR] Deferred %s start failed after desync delay",
                transition_label,
                exc_info=True,
            )

    QTimer.singleShot(delay_ms, deferred_start)
    return f"{transition_label}:deferred:{id(widget)}"


def start_crossfade(
    widget,
    old_pixmap: Optional[QPixmap],
    new_pixmap: QPixmap,
    *,
    duration_ms: int,
    easing: EasingCurve,
    animation_manager: AnimationManager,
    on_finished: Optional[Callable[[], None]] = None,
    on_started: Optional[Callable[[int], None]] = None,
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

    def _start_crossfade(compensated_duration: int) -> Optional[str]:
        if old_pixmap is None or old_pixmap.isNull():
            widget._handle_no_old_image(new_pixmap, on_finished, "crossfade")
            return None
        return widget._start_crossfade_impl(
            old_pixmap, new_pixmap, compensated_duration, easing, animation_manager, on_finished
        )
    return _start_with_desync(
        widget,
        duration_ms=duration_ms,
        starter=_start_crossfade,
        transition_label="crossfade",
        on_started=on_started,
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
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Begin a warp dissolve between two pixmaps using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for warp dissolve")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "warp"):
            return None

    def _start_warp(compensated_duration: int) -> Optional[str]:
        widget._clear_all_transitions()
        widget._warp = WarpState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0)
        widget._pre_upload_textures(widget._prepare_warp_textures)
        widget._profiler.start("warp")
        return widget._start_transition_animation(
            compensated_duration, easing, animation_manager,
            widget._on_warp_update,
            lambda: widget._on_warp_complete(on_finished),
            transition_label="warp",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_warp, transition_label="warp", on_started=on_started)

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
    on_started: Optional[Callable[[int], None]] = None,
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

    import random as _rng
    def _start_raindrops(compensated_duration: int) -> Optional[str]:
        widget._clear_all_transitions()
        widget._raindrops = RaindropsState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0,
            ripple_count=max(1, min(8, int(ripple_count))),
            ripple_seed=_rng.random() * 1000.0,
        )
        widget._pre_upload_textures(widget._prepare_raindrops_textures)
        widget._profiler.start("raindrops")
        return widget._start_transition_animation(
            compensated_duration, easing, animation_manager,
            widget._on_raindrops_update,
            lambda: widget._on_raindrops_complete(on_finished),
            transition_label="raindrops",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_raindrops, transition_label="raindrops", on_started=on_started)

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
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Begin a wipe between two pixmaps using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for wipe")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "wipe"):
            return None

    def _start_wipe(compensated_duration: int) -> Optional[str]:
        widget._clear_all_transitions()
        widget._wipe = WipeState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, direction=direction, progress=0.0)
        widget._pre_upload_textures(widget._prepare_wipe_textures)
        widget._profiler.start("wipe")
        return widget._start_transition_animation(
            compensated_duration, easing, animation_manager,
            widget._on_wipe_update,
            lambda: widget._on_wipe_complete(on_finished),
            transition_label="wipe",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_wipe, transition_label="wipe", on_started=on_started)

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
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Begin a slide between two pixmaps using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for slide")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "slide"):
            return None

    def _start_slide(compensated_duration: int) -> Optional[str]:
        widget._clear_all_transitions()
        widget._slide = SlideState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap,
            old_start=old_start, old_end=old_end,
            new_start=new_start, new_end=new_end, progress=0.0,
        )
        widget._pre_upload_textures(widget._prepare_slide_textures)
        widget._profiler.start("slide")
        return widget._start_transition_animation(
            compensated_duration, easing, animation_manager,
            widget._on_slide_update,
            lambda: widget._on_slide_complete(on_finished),
            transition_label="slide",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_slide, transition_label="slide", on_started=on_started)

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
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Begin a block puzzle flip using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for block flip")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "block flip"):
            return None

    def _start_blockflip(compensated_duration: int) -> Optional[str]:
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
            compensated_duration, easing, animation_manager,
            _blockflip_profiled_update,
            lambda: widget._on_blockflip_complete(on_finished),
            transition_label="blockflip",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_blockflip, transition_label="blockflip", on_started=on_started)

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
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Begin a 3D block spin using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for block spin")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "block spin"):
            return None

    def _start_blockspin(compensated_duration: int) -> Optional[str]:
        widget._clear_all_transitions()
        widget._blockspin = BlockSpinState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap, direction=direction, progress=0.0,
        )
        widget._pre_upload_textures(widget._prepare_blockspin_textures)
        widget._profiler.start("blockspin")
        return widget._start_transition_animation(
            compensated_duration, easing, animation_manager,
            widget._on_blockspin_update,
            lambda: widget._on_blockspin_complete(on_finished),
            transition_label="blockspin",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_blockspin, transition_label="blockspin", on_started=on_started)

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
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Begin a diffuse reveal using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for diffuse")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "diffuse"):
            return None

    # Map shape name to integer for GLSL shader
    shape_mode = {"membrane": 1, "lines": 2, "diamonds": 3, "amorph": 4, "random": 5}.get(
        (shape or "").strip().lower(), 0
    )

    def _start_diffuse(compensated_duration: int) -> Optional[str]:
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
            compensated_duration, easing, animation_manager,
            _diffuse_profiled_update,
            lambda: widget._on_diffuse_complete(on_finished),
            transition_label="diffuse",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_diffuse, transition_label="diffuse", on_started=on_started)

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
    feather: float = 0.08,
    direction: int = 0,
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Begin a blinds reveal using the compositor."""
    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for blinds")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "blinds"):
            return None

    def _start_blinds(compensated_duration: int) -> Optional[str]:
        widget._clear_all_transitions()
        widget._blinds = BlindsState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap, region=None,
            cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
            rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
            feather=max(0.001, min(0.5, float(feather))),
            direction=int(direction),
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
            compensated_duration, easing, animation_manager,
            _blinds_profiled_update,
            lambda: widget._on_blinds_complete(on_finished),
            transition_label="blinds",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_blinds, transition_label="blinds", on_started=on_started)

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
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Begin a crumble transition using the compositor."""
    import random as _random

    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for crumble")
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "crumble"):
            return None

    def _start_crumble(compensated_duration: int) -> Optional[str]:
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
            compensated_duration, easing, animation_manager,
            _crumble_update,
            lambda: widget._on_crumble_complete(on_finished),
            transition_label="crumble",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_crumble, transition_label="crumble", on_started=on_started)

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
    on_started: Optional[Callable[[int], None]] = None,
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

    def _start_particle(compensated_duration: int) -> Optional[str]:
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
            compensated_duration, easing, animation_manager,
            _particle_update,
            lambda: widget._on_particle_complete(on_finished),
            transition_label="particle",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_particle, transition_label="particle", on_started=on_started)

def start_burn(
    widget,
    old_pixmap: Optional[QPixmap],
    new_pixmap: QPixmap,
    *,
    duration_ms: int,
    easing: EasingCurve,
    animation_manager: AnimationManager,
    on_finished: Optional[Callable[[], None]] = None,
    direction: int = 0,
    jaggedness: float = 0.5,
    glow_intensity: float = 0.7,
    glow_color: tuple = (1.0, 0.55, 0.12, 1.0),
    char_width: float = 0.5,
    smoke_enabled: bool = True,
    smoke_density: float = 0.5,
    ash_enabled: bool = True,
    ash_density: float = 0.5,
    seed: Optional[float] = None,
    on_started: Optional[Callable[[int], None]] = None,
) -> Optional[str]:
    """Begin a burn transition between two pixmaps using the compositor."""
    import random as _rng

    if not new_pixmap or new_pixmap.isNull():
        logger.error("[GL COMPOSITOR] Invalid new pixmap for burn")
        return None

    if (widget._gl_disabled_for_session or gl is None or widget._gl_pipeline is None
            or not widget._gl_pipeline.initialized):
        return None

    if old_pixmap is None or old_pixmap.isNull():
        if widget._handle_no_old_image(new_pixmap, on_finished, "burn"):
            return None

    def _start_burn(compensated_duration: int) -> Optional[str]:
        actual_seed = seed if seed is not None else _rng.random() * 1000.0
        widget._clear_all_transitions()
        widget._burn = BurnState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            progress=0.0,
            direction=max(0, min(5, int(direction))),
            jaggedness=max(0.0, min(1.0, float(jaggedness))),
            glow_intensity=max(0.0, min(1.0, float(glow_intensity))),
            glow_color=tuple(glow_color),
            char_width=max(0.1, min(1.0, float(char_width))),
            smoke_enabled=bool(smoke_enabled),
            smoke_density=max(0.0, min(1.0, float(smoke_density))),
            ash_enabled=bool(ash_enabled),
            ash_density=max(0.0, min(1.0, float(ash_density))),
            seed=float(actual_seed),
        )
        widget._pre_upload_textures(widget._prepare_burn_textures)
        widget._profiler.start("burn")
        return widget._start_transition_animation(
            compensated_duration, easing, animation_manager,
            widget._on_burn_update,
            lambda: widget._on_burn_complete(on_finished),
            transition_label="burn",
        )
    return _start_with_desync(widget, duration_ms=duration_ms, starter=_start_burn, transition_label="burn", on_started=on_started)


# ------------------------------------------------------------------
# Animation callbacks
# ------------------------------------------------------------------

