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

from typing import Dict, Optional, Callable

import ctypes
import time

# Import metrics classes from extracted package
from rendering.gl_compositor_pkg.metrics import (
    _GLPipelineState,
    _AnimationRunMetrics,
    _PaintMetrics,
    _RenderTimerMetrics,
)
from rendering.adaptive_timer import (
    AdaptiveRenderStrategyManager,
    AdaptiveTimerConfig,
)

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QPainter, QPixmap, QRegion, QImage, QColor
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.animation.types import EasingCurve
from core.animation.animator import AnimationManager
from core.animation.frame_interpolator import FrameState
from rendering.gl_format import apply_widget_surface_format
from rendering.gl_profiler import TransitionProfiler
from transitions.wipe_transition import WipeDirection
from transitions.slide_transition import SlideDirection
from core.resources.manager import ResourceManager
from rendering.transition_state import (
    CrossfadeState,
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

# Centralized shader program cache - replaces scattered module-level globals
from rendering.gl_programs.program_cache import get_program_cache, cleanup_program_cache, GLProgramCache
from rendering.gl_programs.geometry_manager import GLGeometryManager
from rendering.gl_programs.texture_manager import GLTextureManager
from rendering.gl_transition_renderer import GLTransitionRenderer
from rendering.gl_error_handler import get_gl_error_handler
from rendering.gl_state_manager import GLStateManager, GLContextState


def _get_peel_program():
    """Get the PeelProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.PEEL)

def _get_blockflip_program():
    """Get the BlockFlipProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.BLOCK_FLIP)

def _get_crossfade_program():
    """Get the CrossfadeProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.CROSSFADE)

def _get_blinds_program():
    """Get the BlindsProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.BLINDS)

def _get_diffuse_program():
    """Get the DiffuseProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.DIFFUSE)

def _get_slide_program():
    """Get the SlideProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.SLIDE)

def _get_wipe_program():
    """Get the WipeProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.WIPE)

def _get_crumble_program():
    """Get the CrumbleProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.CRUMBLE)

def _get_particle_program():
    """Get the ParticleProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.PARTICLE)

def _get_warp_program():
    """Get the WarpProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.WARP)

def _get_raindrops_program():
    """Get the RaindropsProgram instance via cache."""
    return get_program_cache().get_program_instance(GLProgramCache.RAINDROPS)


def cleanup_global_shader_programs() -> None:
    """Clear all shader program instances via the centralized cache.
    
    Call this on application shutdown to ensure GL resources are released.
    This is safe to call even if programs were never loaded.
    """
    cleanup_program_cache()


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


# NOTE: State dataclasses (CrossfadeState, SlideState, WipeState, WarpState,
# BlockFlipState, RaindropsState, BlockSpinState, PeelState, BlindsState,
# DiffuseState, CrumbleState) are imported from rendering.transition_state

# NOTE: Metrics dataclasses (_GLPipelineState, _AnimationRunMetrics, 
# _PaintMetrics, _RenderTimerMetrics) are imported from rendering.gl_compositor.metrics


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
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        try:
            self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)

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
        self._particle: Optional[ParticleState] = None
        # NOTE: _shuffle and _shooting_stars removed - these transitions are retired.

        # Centralized profiler for all compositor-driven transitions.
        # Replaces per-transition profiling fields with a single reusable instance.
        self._profiler = TransitionProfiler()

        # FRAME PACING: Single FrameState for all transitions. Decouples animation
        # updates from rendering - animation pushes timestamped samples, paintGL
        # interpolates to actual render time for smooth motion.
        self._frame_state: Optional[FrameState] = None
        
        # TIMER-BASED RENDERING: Pure timer strategy capped at display refresh rate.
        # VSync is completely disabled - we use timer for maximum performance.
        self._render_timer_fps: int = 60  # Will be set from display refresh rate
        self._render_timer_metrics: Optional[_RenderTimerMetrics] = None
        
        # Render strategy manager for timer-based rendering (primary method)
        # Using adaptive timer for optimal performance
        self._render_strategy_manager: Optional[AdaptiveRenderStrategyManager] = None
        self._paint_metrics: Optional[_PaintMetrics] = None
        self._paint_slow_threshold_ms: float = 24.0
        self._paint_warning_last_ts: float = 0.0

        # Animation plumbing: compositor does not own AnimationManager, but we
        # keep the current animation id so the caller can cancel if needed.
        self._animation_manager: Optional[AnimationManager] = None
        self._current_anim_id: Optional[str] = None
        # Default easing is QUAD_IN_OUT; callers can override per-transition.
        self._current_easing: EasingCurve = EasingCurve.QUAD_IN_OUT
        self._current_anim_metrics: Optional[_AnimationRunMetrics] = None
        self._anim_dt_spike_threshold_ms: float = 72.0
        self._current_transition_name: Optional[str] = None

        # Phase 1 GLSL pipeline scaffolding. The actual OpenGL resource
        # creation is deferred to initializeGL so that a valid context is
        # guaranteed. For now we keep the pipeline disabled; later phases
        # will turn this on for specific transitions.
        self._gl_pipeline: Optional[_GLPipelineState] = None
        self._use_shaders: bool = False
        self._gl_disabled_for_session: bool = False
        
        # Per-compositor geometry manager - VAOs are NOT shared between GL contexts
        # so each display's compositor needs its own geometry
        self._geometry_manager: Optional[GLGeometryManager] = None
        
        # Centralized error handler for session-level fallback policy
        self._error_handler = get_gl_error_handler()
        
        # Centralized GL state manager for robust state tracking
        self._gl_state = GLStateManager(f"compositor_{id(self)}")
        
        # Per-compositor texture manager - textures are NOT shared between GL contexts
        # so each display's compositor needs its own texture manager
        self._texture_manager: Optional[GLTextureManager] = None
        
        # Transition rendering delegated to centralized renderer
        self._transition_renderer = GLTransitionRenderer(
            compositor=self,
            get_pipeline=lambda: self._gl_pipeline,
            get_texture_manager=lambda: self._texture_manager,
            get_profiler=lambda: self._profiler,
            get_viewport_size=self._get_viewport_size,
            get_render_progress=lambda fallback: self._get_render_progress(fallback=fallback),
        )
        
        # DESYNC STRATEGY: Random delay (0-500ms) to spread transition start overhead
        # Each compositor gets a different delay to avoid simultaneous GPU uploads
        import random
        self._desync_delay_ms: int = random.randint(0, 500)  # Atomic int, no lock needed
        # Set program getters after init
        self._transition_renderer.set_program_getters({
            "peel": _get_peel_program,
            "blockflip": _get_blockflip_program,
            "crossfade": _get_crossfade_program,
            "blinds": _get_blinds_program,
            "diffuse": _get_diffuse_program,
            "slide": _get_slide_program,
            "wipe": _get_wipe_program,
            "warp": _get_warp_program,
            "raindrops": _get_raindrops_program,
            "crumble": _get_crumble_program,
            "particle": _get_particle_program,
        })

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
        self._spotify_vis_bar_count: int = 10
        self._spotify_vis_segments: int = 5
        self._spotify_vis_fill_color: Optional[QColor] = None
        self._spotify_vis_border_color: Optional[QColor] = None
        self._spotify_vis_fade: float = 0.0
        
        # GL-based dimming overlay. Rendered AFTER the wallpaper/transition
        # but BEFORE widgets (which are Qt siblings above the compositor).
        # This ensures proper compositing without Z-order issues.
        self._dimming_enabled: bool = False
        self._dimming_opacity: float = 0.0  # 0.0-1.0

        # Mapping of transition controller class names to shader program keys.
        self._transition_program_map: Dict[str, str] = {
            "GLCompositorCrossfadeTransition": GLProgramCache.CROSSFADE,
            "GLCompositorSlideTransition": GLProgramCache.SLIDE,
            "GLCompositorWipeTransition": GLProgramCache.WIPE,
            "GLCompositorBlockFlipTransition": GLProgramCache.BLOCK_FLIP,
            "GLCompositorBlindsTransition": GLProgramCache.BLINDS,
            "GLCompositorDiffuseTransition": GLProgramCache.DIFFUSE,
            "GLCompositorPeelTransition": GLProgramCache.PEEL,
            "GLCompositorBlockSpinTransition": GLProgramCache.WARP,  # Uses warp helpers for card flip
            "GLCompositorRainDropsTransition": GLProgramCache.RAINDROPS,
            "GLCompositorWarpTransition": GLProgramCache.WARP,
            "GLCompositorCrumbleTransition": GLProgramCache.CRUMBLE,
            "GLCompositorParticleTransition": GLProgramCache.PARTICLE,
        }

    # ------------------------------------------------------------------
    # Public API used by DisplayWidget / transitions
    # ------------------------------------------------------------------
    
    def set_dimming(self, enabled: bool, opacity: float = 0.3) -> None:
        """Enable or disable GL-based dimming overlay.
        
        Args:
            enabled: True to show dimming, False to hide
            opacity: Dimming opacity 0.0-1.0 (default 0.3 = 30%)
        """
        old_enabled = getattr(self, "_dimming_enabled", False)
        old_opacity = getattr(self, "_dimming_opacity", 0.0)
        self._dimming_enabled = enabled
        self._dimming_opacity = max(0.0, min(1.0, opacity))
        
        # Log if dimming state actually changed (helps debug brightness flicker)
        if old_enabled != enabled or abs(old_opacity - self._dimming_opacity) > 0.01:
            logger.info(
                "[DIMMING] GL dimming changed: enabled=%s→%s, opacity=%.0f%%→%.0f%%",
                old_enabled, enabled, old_opacity * 100, self._dimming_opacity * 100
            )
        self.update()

    def _get_render_progress(self, fallback: float = 0.0) -> float:
        """Get interpolated progress for rendering.
        
        Uses FrameState to interpolate to actual render time, masking timer jitter.
        Falls back to the provided value if no frame state is active.
        """
        if self._frame_state is not None:
            return self._frame_state.get_interpolated_progress()
        return fallback

    def get_current_animation_info(self) -> Optional[dict]:
        """Return current animation info for instrumentation during shutdown."""
        if self._current_anim_id is None:
            return None
        return {
            "anim_id": self._current_anim_id,
            "transition": self._current_transition_name,
            "has_frame_state": self._frame_state is not None,
        }

    def describe_state(self) -> dict:
        """Return a lightweight snapshot of compositor runtime state."""
        frame_state = None
        if self._frame_state is not None:
            try:
                frame_state = self._frame_state.describe()
            except Exception as exc:
                logger.debug("[GL COMPOSITOR] FrameState describe failed: %s", exc)
        strategy_state = None
        if self._render_strategy_manager is not None:
            try:
                strategy_state = self._render_strategy_manager.describe_state()
            except Exception as exc:
                logger.debug("[GL COMPOSITOR] Strategy describe failed: %s", exc)
        return {
            "current_transition": self._current_transition_name,
            "has_frame_state": self._frame_state is not None,
            "frame_state": frame_state,
            "render_strategy": strategy_state,
        }

    def stop_rendering(self, reason: str = "unspecified") -> None:
        """Stop timers/animations driving this compositor."""
        if is_perf_metrics_enabled():
            try:
                logger.info("[PERF][GL COMPOSITOR] stop_rendering reason=%s state=%s", reason, self.describe_state())
            except Exception as exc:
                logger.debug("[GL COMPOSITOR] describe_state logging failed: %s", exc)
        try:
            self._stop_frame_pacing()
        except Exception as exc:
            logger.debug("[GL COMPOSITOR] stop_frame_pacing failed: %s", exc)
        self._stop_render_strategy()

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
        self._pause_render_timer()  # Pause (don't stop) for quick resume
        if self._frame_state is not None:
            self._frame_state.mark_complete()
        self._frame_state = None
    
    def _apply_desync_strategy(self, base_duration_ms: int) -> tuple[int, int]:
        """Apply desync strategy to spread transition start overhead.
        
        OPTIMIZATION: Each compositor gets a random delay (0-500ms) to avoid
        simultaneous GPU uploads and transition starts. Duration is compensated
        so all displays complete at the same visual state.
        
        Args:
            base_duration_ms: Original transition duration
            
        Returns:
            (delay_ms, compensated_duration_ms) tuple
            
        Example:
            Display 0: delay=0ms, duration=5000ms → completes at T+5000ms
            Display 1: delay=300ms, duration=5300ms → completes at T+5600ms (same visual state)
        """
        delay_ms = self._desync_delay_ms
        # Compensate duration: add delay so transition completes at same visual state
        compensated_duration_ms = base_duration_ms + delay_ms
        
        if delay_ms > 0 and is_perf_metrics_enabled():
            logger.debug(
                "[PERF] [DESYNC] Applying desync: delay=%dms, duration=%dms→%dms",
                delay_ms, base_duration_ms, compensated_duration_ms
            )
        
        return delay_ms, compensated_duration_ms

    def _get_display_refresh_rate(self) -> int:
        """Get the display refresh rate for this compositor's screen.
        
        Returns:
            Display refresh rate in Hz (defaults to 60 if detection fails)
        """
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
        return display_hz
    
    def _calculate_target_fps(self, display_hz: int) -> int:
        """Mirror DisplayWidget's adaptive ladder."""

        parent = self.parent()
        from rendering.display_widget import DisplayWidget  # local import to avoid cycle
        if isinstance(parent, DisplayWidget):
            target = getattr(parent, "_target_fps", 60)
            if target > 0:
                return target

        if display_hz <= 0:
            display_hz = 60
        if display_hz <= 60:
            target = display_hz
        elif display_hz <= 120:
            target = max(30, display_hz // 2)
        else:
            target = max(30, display_hz // 3)

        if is_perf_metrics_enabled():
            logger.debug(
                "[PERF] [GL COMPOSITOR] Target FPS fallback ladder -> %d (display=%dHz)",
                target,
                display_hz,
            )
        return target

    def _reset_render_timer_metrics(self, target_fps: int) -> None:
        """Initialize or clear render timer metrics based on PERF flag."""

        if is_perf_metrics_enabled():
            interval = max(1, int(round(1000.0 / max(1, target_fps))))
            self._render_timer_metrics = _RenderTimerMetrics(
                target_fps=target_fps,
                interval_ms=interval,
            )
        else:
            self._render_timer_metrics = None

    def _start_render_strategy(self) -> None:
        """Start the render strategy to drive repaints during transitions.

        Uses adaptive timer for optimal performance with state management.
        VSync is completely disabled for maximum performance.
        """
        # Check if already running
        if self._render_strategy_manager is not None:
            if self._render_strategy_manager.is_running():
                # Already running - just resume
                self._render_strategy_manager.resume()
                logger.debug("[GL COMPOSITOR] Render strategy resumed")
                return
        
        display_hz = self._get_display_refresh_rate()
        target_fps = self._calculate_target_fps(display_hz)
        self._render_timer_fps = target_fps
        self._reset_render_timer_metrics(target_fps)
        
        # Start adaptive timer-based rendering
        self._start_adaptive_timer_render(target_fps, display_hz)

    def _start_adaptive_timer_render(self, target_fps: int, display_hz: int) -> None:
        """Start adaptive timer-based rendering (primary method).
        
        This is the ONLY rendering method - VSync is completely disabled.
        Timer uses adaptive state machine for optimal performance.
        """
        if self._render_strategy_manager is None:
            self._render_strategy_manager = AdaptiveRenderStrategyManager(self)
        
        interval_ms = max(1.0, 1000.0 / target_fps)
        config = AdaptiveTimerConfig(
            target_fps=target_fps,
            idle_timeout_sec=5.0,  # Go idle after 5s of no transitions
            max_deep_sleep_sec=60.0,
            min_frame_time_ms=interval_ms,
        )
        self._render_strategy_manager.configure(config)
        
        success = self._render_strategy_manager.start()
        
        logger.info(
            "[GL COMPOSITOR] Adaptive timer render started: display=%dHz, target=%dHz, interval=%.2fms, success=%s",
            display_hz, target_fps, interval_ms, success
        )
    
    def _pause_render_strategy(self) -> None:
        """Pause render strategy after transition ends (enter low-power mode)."""
        if self._render_strategy_manager is not None:
            self._render_strategy_manager.pause()
            logger.debug("[GL COMPOSITOR] Render strategy paused")
    
    def _stop_render_strategy(self) -> None:
        """Stop the render strategy."""
        if self._render_strategy_manager is not None:
            self._render_strategy_manager.stop()
        
        self._finalize_render_timer_metrics()
        logger.debug("[GL COMPOSITOR] Render strategy stopped")
    
    def _start_render_timer(self) -> None:
        """Start the render timer to drive repaints during transitions.
        
        This is now a wrapper around _start_render_strategy() for backward compatibility.
        """
        self._start_render_strategy()
    
    def _pause_render_timer(self) -> None:
        """Pause the render timer (enter low-power mode between transitions).
        
        This keeps the timer thread alive for quick resume.
        """
        self._pause_render_strategy()
    
    def _stop_render_timer(self) -> None:
        """Stop the render timer.
        
        This is now a wrapper around _stop_render_strategy() for backward compatibility.
        """
        self._stop_render_strategy()
    
    def _on_render_tick(self) -> None:
        """Called by render strategy to trigger a repaint.
        
        Note: This is now primarily called by the RenderStrategyManager's internal
        timer or VSync thread. The actual progress interpolation happens in paintGL
        using the FrameState.
        """
        self._record_render_timer_tick()
        if self._frame_state is not None and self._frame_state.started and not self._frame_state.completed:
            self.update()

    def set_base_pixmap(self, pixmap: Optional[QPixmap]) -> None:
        """Set the base image when no transition is active.
        
        OPTIMIZATION: Pre-upload texture to GPU now, not at transition start.
        This spreads the upload cost across idle time instead of blocking transitions.
        """
        self._base_pixmap = pixmap
        
        # Pre-upload texture to GPU cache for future transitions
        # This happens during idle time, not during transition start
        if pixmap is not None and not pixmap.isNull():
            try:
                from rendering.gl_programs.texture_manager import get_texture_manager
                tex_mgr = get_texture_manager()
                if tex_mgr.is_initialized():
                    # Cache the texture - will be reused when transition starts
                    tex_mgr.get_or_create_texture(pixmap)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Texture pre-upload failed: %s", e)
        
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
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            count = 0
        try:
            segs = int(segments)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            segs = 0

        if count <= 0 or segs <= 0:
            self._spotify_vis_enabled = False
            return

        try:
            bars_seq = list(bars)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
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
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
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
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            self._spotify_vis_fade = 1.0

    def _clear_all_transitions(self) -> None:
        """Clear all transition states."""
        self._cancel_current_animation()
        try:
            self._stop_frame_pacing()
        except Exception:
            logger.debug("[GL COMPOSITOR] Frame pacing stop failed during clear", exc_info=True)
        try:
            self._release_transition_textures()
        except Exception:
            logger.debug("[GL COMPOSITOR] Texture release failed during clear", exc_info=True)
        self._finalize_paint_metrics(outcome="cleared")
        self._crossfade = None
        self._slide = None
        self._wipe = None
        self._warp = None
        self._blockflip = None
        self._blockspin = None
        self._blinds = None
        self._diffuse = None
        self._peel = None
        self._raindrops = None
        self._crumble = None
        self._particle = None
        self._current_transition_name = None
        self._finalize_animation_metrics(outcome="cleared")

    def _handle_no_old_image(self, new_pixmap: QPixmap, on_finished: Optional[Callable[[], None]], name: str) -> bool:
        """Handle case where there's no old image - show new image immediately. Returns True if handled."""
        if new_pixmap is None or new_pixmap.isNull():
            return False
        logger.debug("[GL COMPOSITOR] No old image; showing new image immediately (%s)", name)
        self._clear_all_transitions()
        self._base_pixmap = new_pixmap
        self.update()
        if on_finished:
            try:
                on_finished()
            except Exception:
                logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        return True

    def _pre_upload_textures(self, prep_fn: Callable[[], bool]) -> None:
        """Pre-upload textures before animation starts.
        
        PERFORMANCE FIX: Defer texture upload to first paintGL call instead of
        blocking the main thread here. This eliminates 120-690ms paint gaps.
        The prep_fn will be called during the first paintGL when GL context is active.
        """
        # DISABLED: This was blocking the main thread for 120-690ms
        # Textures are now uploaded lazily during first paintGL call
        pass

    def _cancel_current_animation(self) -> None:
        """Cancel any previous animation on this compositor."""
        if self._current_anim_id and self._animation_manager:
            try:
                self._animation_manager.cancel_animation(self._current_anim_id)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            self._current_anim_id = None
            self._finalize_animation_metrics(outcome="cancelled")
            self._finalize_paint_metrics(outcome="cancelled")

    def _start_transition_animation(
        self,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        update_callback: Callable[[float], None],
        on_complete: Callable[[], None],
        transition_label: Optional[str] = None,
    ) -> str:
        """Start a transition animation and return the animation ID.
        
        OPTIMIZATION: Defer non-critical initialization to reduce transition start overhead.
        Metrics and render strategy start are deferred to first frame update.
        """
        self._animation_manager = animation_manager
        self._current_easing = easing
        self._cancel_current_animation()
        duration_sec = max(0.001, duration_ms / 1000.0)
        
        # Create frame state but defer render strategy start
        self._frame_state = FrameState(duration=duration_sec)
        
        # Defer metrics initialization - will be initialized on first frame update
        # Use list to allow mutation in closure (avoid dict overhead on every frame)
        initialized = [False]
        profiled_callback = [None]
        
        # Wrap callback to initialize metrics on first call (lazy init)
        def lazy_init_callback(progress: float) -> None:
            if not initialized[0]:
                initialized[0] = True
                # Initialize metrics FIRST before starting timer
                # to avoid race where timer triggers callback before we're ready
                self._begin_paint_metrics(transition_label or "transition")
                metrics = self._begin_animation_metrics(
                    transition_label or "transition",
                    duration_ms,
                    animation_manager,
                )
                # Wrap the original callback with metrics
                profiled_callback[0] = self._wrap_animation_update(update_callback, metrics)
                # Start render strategy AFTER callback is ready
                self._start_render_timer()
                # Call it for this first frame
                profiled_callback[0](progress)
            else:
                # Use cached profiled callback (direct list access, no dict lookup)
                # Safety check in case initialization failed
                if profiled_callback[0] is not None:
                    profiled_callback[0](progress)
                else:
                    # Fallback to original callback if profiled not ready
                    update_callback(progress)
        
        anim_id = animation_manager.animate_custom(
            duration=duration_sec,
            easing=easing,
            update_callback=lazy_init_callback,
            on_complete=on_complete,
            frame_state=self._frame_state,
        )
        self._current_anim_id = anim_id
        return anim_id

    def _begin_animation_metrics(
        self,
        transition_label: str,
        duration_ms: int,
        animation_manager: AnimationManager,
    ) -> Optional[_AnimationRunMetrics]:
        """Start tracking per-frame dt metrics for the active animation."""
        if not is_perf_metrics_enabled():
            self._current_anim_metrics = None
            return None
        target_fps = getattr(animation_manager, "fps", 60)
        metrics = _AnimationRunMetrics(
            name=transition_label,
            duration_ms=int(duration_ms),
            target_fps=int(target_fps or 60),
            dt_spike_threshold_ms=self._anim_dt_spike_threshold_ms,
        )
        self._current_anim_metrics = metrics
        return metrics

    def _wrap_animation_update(
        self,
        update_callback: Callable[[float], None],
        metrics: Optional[_AnimationRunMetrics],
    ) -> Callable[[float], None]:
        """Wrap the animation update callback to record timing metrics."""
        if metrics is None:
            return update_callback

        def _instrumented(progress: float, *, _inner=update_callback) -> None:
            dt = metrics.record_tick(progress)
            if dt is not None and metrics.should_log_spike(dt):
                self._log_animation_spike(metrics, dt)
            _inner(progress)

        return _instrumented

    def _log_animation_spike(
        self,
        metrics: _AnimationRunMetrics,
        dt_seconds: float,
    ) -> None:
        """Log a dt spike with transition context."""
        if not is_perf_metrics_enabled():
            return
        dt_ms = dt_seconds * 1000.0
        logger.warning(
            "[PERF] [GL ANIM] Tick dt spike %.2fms (name=%s frame=%d progress=%.2f target_fps=%d)",
            dt_ms,
            metrics.name,
            metrics.frame_count,
            metrics.last_progress,
            metrics.target_fps,
        )

    def _finalize_animation_metrics(self, outcome: str) -> None:
        """Emit summary metrics for the last animation run."""
        metrics = self._current_anim_metrics
        self._current_anim_metrics = None
        if metrics is None or not is_perf_metrics_enabled():
            return

        elapsed_s = metrics.elapsed_seconds()
        duration_ms = elapsed_s * 1000.0
        avg_fps = (metrics.frame_count / elapsed_s) if elapsed_s > 0 else 0.0
        min_dt_ms = metrics.min_dt * 1000.0 if metrics.min_dt > 0.0 else 0.0
        max_dt_ms = metrics.max_dt * 1000.0 if metrics.max_dt > 0.0 else 0.0

        logger.info(
            "[PERF] [GL ANIM] %s metrics: duration=%.1fms, frames=%d, avg_fps=%.1f, "
            "dt_min=%.2fms, dt_max=%.2fms, spikes=%d, target_fps=%d, outcome=%s",
            metrics.name.capitalize(),
            duration_ms,
            metrics.frame_count,
            avg_fps,
            min_dt_ms,
            max_dt_ms,
            metrics.dt_spike_count,
            metrics.target_fps,
            outcome,
        )

    def _begin_paint_metrics(self, label: str) -> None:
        """Start tracking paintGL cadence for the current transition."""
        if not is_perf_metrics_enabled():
            self._paint_metrics = None
            return
        self._paint_metrics = _PaintMetrics(
            label=label,
            slow_threshold_ms=self._paint_slow_threshold_ms,
        )

    def _record_paint_metrics(self, paint_duration_ms: float) -> None:
        """Record a paintGL duration and optionally log warnings."""
        if not is_perf_metrics_enabled():
            return
        metrics = self._paint_metrics
        if metrics is None:
            return
        dt_seconds = metrics.record(paint_duration_ms)
        now = time.time()
        if paint_duration_ms > self._paint_slow_threshold_ms:
            if now - self._paint_warning_last_ts > 0.5:
                logger.warning(
                    "[PERF] [GL PAINT] Slow paintGL %.2fms (transition=%s)",
                    paint_duration_ms,
                    metrics.label,
                )
                self._paint_warning_last_ts = now
        if dt_seconds is not None and dt_seconds * 1000.0 > 120.0:
            if now - self._paint_warning_last_ts > 0.5:
                logger.warning(
                    "[PERF] [GL PAINT] Paint gap %.2fms (transition=%s)",
                    dt_seconds * 1000.0,
                    metrics.label,
                )
                self._paint_warning_last_ts = now

    def _finalize_paint_metrics(self, outcome: str = "stopped") -> None:
        """Emit summary metrics for paintGL cadence."""
        metrics = self._paint_metrics
        self._paint_metrics = None
        if metrics is None or not is_perf_metrics_enabled():
            return
        elapsed_s = metrics.elapsed_seconds()
        avg_fps = (metrics.frame_count / elapsed_s) if elapsed_s > 0 else 0.0
        min_dt_ms = metrics.min_dt * 1000.0 if metrics.min_dt > 0.0 else 0.0
        max_dt_ms = metrics.max_dt * 1000.0 if metrics.max_dt > 0.0 else 0.0
        logger.info(
            "[PERF] [GL PAINT] %s metrics: frames=%d, avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
            "dur_min=%.2fms, dur_max=%.2fms, slow_frames=%d, outcome=%s",
            metrics.label.capitalize(),
            metrics.frame_count,
            avg_fps,
            min_dt_ms,
            max_dt_ms,
            metrics.min_duration_ms,
            metrics.max_duration_ms,
            metrics.slow_count,
            outcome,
        )

    def _record_render_timer_tick(self) -> None:
        """Record render timer cadence telemetry."""
        metrics = self._render_timer_metrics
        if metrics is None or not is_perf_metrics_enabled():
            return
        dt = metrics.record_tick()
        if dt is None:
            return
        if metrics.should_log_stall(dt):
            self._log_render_timer_stall(dt, metrics)

    def _log_render_timer_stall(self, dt_seconds: float, metrics: _RenderTimerMetrics) -> None:
        """Emit a warning when render timer stalls exceed thresholds."""
        if not is_perf_metrics_enabled():
            return
        anim_label = self._current_anim_metrics.name if self._current_anim_metrics else "idle"
        logger.warning(
            "[PERF] [GL RENDER] Render timer stall %.2fms (target=%dHz interval=%dms frames=%d anim=%s)",
            dt_seconds * 1000.0,
            metrics.target_fps,
            metrics.interval_ms,
            metrics.frame_count,
            anim_label,
        )

    def _finalize_render_timer_metrics(self, outcome: str = "stopped") -> None:
        """Summarize render timer cadence when it stops."""
        metrics = self._render_timer_metrics
        self._render_timer_metrics = None
        if metrics is None or not is_perf_metrics_enabled():
            return
        elapsed_s = metrics.elapsed_seconds()
        avg_fps = (metrics.frame_count / elapsed_s) if elapsed_s > 0 else 0.0
        min_dt_ms = metrics.min_dt * 1000.0 if metrics.min_dt > 0.0 else 0.0
        max_dt_ms = metrics.max_dt * 1000.0 if metrics.max_dt > 0.0 else 0.0
        logger.info(
            "[PERF] [GL RENDER] Timer metrics: frames=%d, avg_fps=%.1f, dt_min=%.2fms, dt_max=%.2fms, "
            "stalls=%d, target=%dHz, outcome=%s",
            metrics.frame_count,
            avg_fps,
            min_dt_ms,
            max_dt_ms,
            metrics.stall_count,
            metrics.target_fps,
            outcome,
        )

    def _complete_transition(
        self,
        name: str,
        state_attr: str,
        on_finished: Optional[Callable[[], None]],
        release_textures: bool = False,
    ) -> None:
        """Generic transition completion handler."""
        try:
            self._profiler.complete(name, viewport_size=(self.width(), self.height()))
            self._stop_frame_pacing()
            self._finalize_animation_metrics(outcome="complete")
            if release_textures:
                try:
                    self._release_transition_textures()
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Failed to release %s textures: %s", name, e, exc_info=True)
            state = getattr(self, state_attr, None)
            if state is not None:
                try:
                    self._base_pixmap = state.new_pixmap
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            setattr(self, state_attr, None)
            self._current_anim_id = None
            try:
                self.update()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] %s complete update failed: %s", name.capitalize(), e, exc_info=True)
            if on_finished:
                try:
                    on_finished()
                except Exception:
                    logger.debug("[GL COMPOSITOR] on_finished callback failed", exc_info=True)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] %s complete handler failed: %s", name.capitalize(), e, exc_info=True)

    def _ensure_gl_pipeline_ready(self) -> bool:
        """Ensure the GLSL pipeline is initialised and ready for use."""
        if gl is None or self._gl_disabled_for_session:
            return False
        if self._gl_pipeline is not None and self._gl_pipeline.initialized:
            return True

        try:
            self.makeCurrent()
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            return False

        try:
            if self._gl_pipeline is None:
                self._gl_pipeline = _GLPipelineState()
                self._use_shaders = False
                self._gl_disabled_for_session = False
            self._init_gl_pipeline()
            return self._gl_pipeline is not None and self._gl_pipeline.initialized
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to initialise GL pipeline", exc_info=True)
            return False
        finally:
            try:
                self.doneCurrent()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)

    def _with_temp_state(self, attr_name: str, state, prep_fn: Callable[[], bool]) -> bool:
        """Assign a temporary state, invoke prep_fn, then restore the original state."""
        original = getattr(self, attr_name, None)
        setattr(self, attr_name, state)
        try:
            return prep_fn()
        finally:
            setattr(self, attr_name, original)

    def _estimate_grid_dimensions(self, reference_pixmap: QPixmap, min_cols: int = 4) -> tuple[int, int]:
        """Estimate reasonable grid dimensions for warmup based on widget size/aspect."""
        width = max(1, self.width())
        height = max(1, self.height())
        if width <= 1 or height <= 1:
            width = max(width, reference_pixmap.width())
            height = max(height, reference_pixmap.height())

        cols = max(min_cols, int(round(width / 320.0)))
        rows = max(2, int(round(cols * (height / float(max(1, width))))))
        return cols, rows

    def _warm_transition_state(
        self,
        transition_name: str,
        old_pixmap: Optional[QPixmap],
        new_pixmap: QPixmap,
    ) -> bool:
        """Prime transition-specific state so heavy prep work is done before first run."""
        warm_old = old_pixmap or new_pixmap
        if warm_old is None or warm_old.isNull() or new_pixmap.isNull():
            return False

        warmers: Dict[str, Callable[[QPixmap, QPixmap], bool]] = {
            "GLCompositorBlockFlipTransition": self._warm_blockflip_state,
            "GLCompositorBlockSpinTransition": self._warm_blockspin_state,
            "GLCompositorBlindsTransition": self._warm_blinds_state,
            "GLCompositorDiffuseTransition": self._warm_diffuse_state,
            "GLCompositorPeelTransition": self._warm_peel_state,
            "GLCompositorWarpTransition": self._warm_warp_state,
            "GLCompositorRainDropsTransition": self._warm_raindrops_state,
            "GLCompositorCrumbleTransition": self._warm_crumble_state,
            "GLCompositorParticleTransition": self._warm_particle_state,
        }

        warmer = warmers.get(transition_name)
        if warmer is None or gl is None or self._gl_disabled_for_session:
            return True

        try:
            self.makeCurrent()
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            return False

        try:
            self._ensure_texture_manager()
            return warmer(warm_old, new_pixmap)
        except Exception:
            logger.debug(
                "[GL COMPOSITOR] Transition state warmup failed for %s",
                transition_name,
                exc_info=True,
            )
            return False
        finally:
            try:
                self.doneCurrent()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)

    def _warm_blockflip_state(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        cols, rows = self._estimate_grid_dimensions(new_pixmap, min_cols=6)
        state = BlockFlipState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            cols=cols,
            rows=rows,
            region=None,
            direction=SlideDirection.LEFT,
        )
        return self._with_temp_state("_blockflip", state, self._prepare_blockflip_textures)

    def _warm_blockspin_state(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        state = BlockSpinState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            direction=SlideDirection.LEFT,
        )
        return self._with_temp_state("_blockspin", state, self._prepare_blockspin_textures)

    def _warm_blinds_state(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        cols, rows = self._estimate_grid_dimensions(new_pixmap, min_cols=8)
        state = BlindsState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            cols=cols,
            rows=rows,
        )
        return self._with_temp_state("_blinds", state, self._prepare_blinds_textures)

    def _warm_diffuse_state(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        cols, rows = self._estimate_grid_dimensions(new_pixmap, min_cols=8)
        state = DiffuseState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            cols=cols,
            rows=rows,
            shape_mode=0,
        )
        return self._with_temp_state("_diffuse", state, self._prepare_diffuse_textures)

    def _warm_peel_state(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        state = PeelState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            direction=SlideDirection.LEFT,
            strips=8,
        )
        return self._with_temp_state("_peel", state, self._prepare_peel_textures)

    def _warm_warp_state(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        state = WarpState(old_pixmap=old_pixmap, new_pixmap=new_pixmap)
        return self._with_temp_state("_warp", state, self._prepare_warp_textures)

    def _warm_raindrops_state(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        state = RaindropsState(old_pixmap=old_pixmap, new_pixmap=new_pixmap)
        return self._with_temp_state("_raindrops", state, self._prepare_raindrops_textures)

    def _warm_crumble_state(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        state = CrumbleState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
            seed=0.0,
            piece_count=8.0,
            crack_complexity=1.0,
            mosaic_mode=False,
            weight_mode=0.0,
        )
        return self._with_temp_state("_crumble", state, self._prepare_crumble_textures)

    def _warm_particle_state(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        state = ParticleState(
            old_pixmap=old_pixmap,
            new_pixmap=new_pixmap,
        )
        return self._with_temp_state("_particle", state, self._prepare_particle_textures)

    def _ensure_texture_manager(self) -> GLTextureManager:
        if self._texture_manager is None:
            self._texture_manager = GLTextureManager()
        return self._texture_manager

    def _warm_pixmap_textures(
        self,
        old_pixmap: Optional[QPixmap],
        new_pixmap: Optional[QPixmap],
    ) -> bool:
        """Upload/cache the provided pixmaps so textures are ready when needed."""
        if gl is None or self._gl_disabled_for_session:
            return False

        if (old_pixmap is None or old_pixmap.isNull()) and (new_pixmap is None or new_pixmap.isNull()):
            return False

        try:
            self.makeCurrent()
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            return False

        try:
            manager = self._ensure_texture_manager()
            if not manager.is_initialized() and not manager.initialize():
                return False

            success = True

            if old_pixmap is not None and not old_pixmap.isNull():
                success = bool(manager.get_or_create_texture(old_pixmap)) and success
            if new_pixmap is not None and not new_pixmap.isNull():
                success = bool(manager.get_or_create_texture(new_pixmap)) and success
            return success
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to warm pixmap textures", exc_info=True)
            return False
        finally:
            try:
                self.doneCurrent()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)

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
        
        OPTIMIZATION: Uses desync strategy to spread transition start overhead.
        Each compositor gets a random delay (0-500ms) with duration compensation
        to maintain visual synchronization across displays.
        """
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for crossfade")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "crossfade"):
                return None

        # Apply desync strategy: random delay with duration compensation
        delay_ms, compensated_duration = self._apply_desync_strategy(duration_ms)
        
        if delay_ms > 0:
            # Use the exact pixmaps we were asked to transition between; do not mutate the
            # compositor base until the animation actually starts.
            from PySide6.QtCore import QTimer

            def deferred_start():
                if old_pixmap is None or old_pixmap.isNull():
                    # If the caller did not provide a previous frame, we cannot animate.
                    self._handle_no_old_image(new_pixmap, on_finished, "crossfade")
                    return
                self._start_crossfade_impl(
                    old_pixmap, new_pixmap, compensated_duration, easing, animation_manager, on_finished
                )

            QTimer.singleShot(delay_ms, deferred_start)
            return None  # Animation ID will be set when transition actually starts
        else:
            return self._start_crossfade_impl(
                old_pixmap, new_pixmap, compensated_duration, easing, animation_manager, on_finished
            )
    
    def _start_crossfade_impl(
        self,
        old_pixmap: QPixmap,
        new_pixmap: QPixmap,
        duration_ms: int,
        easing: EasingCurve,
        animation_manager: AnimationManager,
        on_finished: Optional[Callable[[], None]],
    ) -> Optional[str]:
        """Internal implementation of crossfade start after desync delay."""
        self._clear_all_transitions()
        self._crossfade = CrossfadeState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0)
        self._pre_upload_textures(self._prepare_crossfade_textures)
        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            self._on_crossfade_update,
            lambda: self._on_crossfade_complete(on_finished),
        )

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
        """Begin a warp dissolve between two pixmaps using the compositor."""
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for warp dissolve")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "warp"):
                return None

        self._clear_all_transitions()
        self._warp = WarpState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0)
        self._pre_upload_textures(self._prepare_warp_textures)
        self._profiler.start("warp")
        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            self._on_warp_update,
            lambda: self._on_warp_complete(on_finished),
            transition_label="warp",
        )

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
        """Begin a shader-driven raindrops transition. Returns None if shader unavailable."""
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for raindrops")
            return None

        # Only use this path when the GLSL pipeline and raindrops shader are available
        if (self._gl_disabled_for_session or gl is None or self._gl_pipeline is None
                or not self._gl_pipeline.initialized or not self._gl_pipeline.raindrops_program):
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "raindrops"):
                return None

        self._clear_all_transitions()
        self._raindrops = RaindropsState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0)
        self._pre_upload_textures(self._prepare_raindrops_textures)
        self._profiler.start("raindrops")
        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            self._on_raindrops_update,
            lambda: self._on_raindrops_complete(on_finished),
            transition_label="raindrops",
        )

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
        """Begin a wipe between two pixmaps using the compositor."""
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for wipe")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "wipe"):
                return None

        self._clear_all_transitions()
        self._wipe = WipeState(old_pixmap=old_pixmap, new_pixmap=new_pixmap, direction=direction, progress=0.0)
        self._pre_upload_textures(self._prepare_wipe_textures)
        self._profiler.start("wipe")
        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            self._on_wipe_update,
            lambda: self._on_wipe_complete(on_finished),
            transition_label="wipe",
        )

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
        """Begin a slide between two pixmaps using the compositor."""
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for slide")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "slide"):
                return None

        self._clear_all_transitions()
        self._slide = SlideState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap,
            old_start=old_start, old_end=old_end,
            new_start=new_start, new_end=new_end, progress=0.0,
        )
        self._pre_upload_textures(self._prepare_slide_textures)
        self._profiler.start("slide")
        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            self._on_slide_update,
            lambda: self._on_slide_complete(on_finished),
            transition_label="slide",
        )

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
        """Begin a strip-based peel between two pixmaps using the compositor."""
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for peel")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "peel"):
                return None

        self._clear_all_transitions()
        self._peel = PeelState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap,
            direction=direction, strips=max(1, int(strips)), progress=0.0,
        )
        self._pre_upload_textures(self._prepare_peel_textures)
        self._profiler.start("peel")
        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            self._on_peel_update,
            lambda: self._on_peel_complete(on_finished),
            transition_label="peel",
        )

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
        """Begin a block puzzle flip using the compositor."""
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for block flip")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "block flip"):
                return None

        self._clear_all_transitions()
        self._blockflip = BlockFlipState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap, region=None,
            cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
            rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
            direction=direction,
        )
        self._pre_upload_textures(self._prepare_blockflip_textures)
        self._profiler.start("blockflip")

        def _blockflip_profiled_update(progress: float, *, _inner=update_callback) -> None:
            self._profiler.tick("blockflip")
            try:
                if self._blockflip is not None:
                    self._blockflip.progress = max(0.0, min(1.0, float(progress)))
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            _inner(progress)

        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            _blockflip_profiled_update,
            lambda: self._on_blockflip_complete(on_finished),
            transition_label="blockflip",
        )

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
        """Begin a 3D block spin using the compositor."""
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for block spin")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "block spin"):
                return None

        self._clear_all_transitions()
        self._blockspin = BlockSpinState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap, direction=direction, progress=0.0,
        )
        self._pre_upload_textures(self._prepare_blockspin_textures)
        self._profiler.start("blockspin")
        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            self._on_blockspin_update,
            lambda: self._on_blockspin_complete(on_finished),
            transition_label="blockspin",
        )

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
        """Begin a diffuse reveal using the compositor."""
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for diffuse")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "diffuse"):
                return None

        # Map shape name to integer for GLSL shader
        shape_mode = {"membrane": 1, "circle": 2, "diamond": 3, "plus": 4}.get(
            (shape or "").strip().lower(), 0
        )

        self._clear_all_transitions()
        self._diffuse = DiffuseState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap, region=None,
            cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
            rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
            shape_mode=int(shape_mode),
        )
        self._pre_upload_textures(self._prepare_diffuse_textures)
        self._profiler.start("diffuse")

        def _diffuse_profiled_update(progress: float, *, _inner=update_callback) -> None:
            self._profiler.tick("diffuse")
            try:
                if self._diffuse is not None:
                    self._diffuse.progress = max(0.0, min(1.0, float(progress)))
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            _inner(progress)

        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            _diffuse_profiled_update,
            lambda: self._on_diffuse_complete(on_finished),
            transition_label="diffuse",
        )

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
        """Begin a blinds reveal using the compositor."""
        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for blinds")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "blinds"):
                return None

        self._clear_all_transitions()
        self._blinds = BlindsState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap, region=None,
            cols=int(grid_cols) if grid_cols is not None and grid_cols > 0 else 0,
            rows=int(grid_rows) if grid_rows is not None and grid_rows > 0 else 0,
        )
        self._pre_upload_textures(self._prepare_blinds_textures)
        self._profiler.start("blinds")

        def _blinds_profiled_update(progress: float, *, _inner=update_callback) -> None:
            self._profiler.tick("blinds")
            try:
                if self._blinds is not None:
                    self._blinds.progress = max(0.0, min(1.0, float(progress)))
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            _inner(progress)

        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            _blinds_profiled_update,
            lambda: self._on_blinds_complete(on_finished),
            transition_label="blinds",
        )

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
        weight_mode: float = 0.0,
        seed: Optional[float] = None,
    ) -> Optional[str]:
        """Begin a crumble transition using the compositor."""
        import random as _random

        if not new_pixmap or new_pixmap.isNull():
            logger.error("[GL COMPOSITOR] Invalid new pixmap for crumble")
            return None

        if old_pixmap is None or old_pixmap.isNull():
            if self._handle_no_old_image(new_pixmap, on_finished, "crumble"):
                return None

        self._clear_all_transitions()
        actual_seed = seed if seed is not None else _random.random() * 1000.0
        self._crumble = CrumbleState(
            old_pixmap=old_pixmap, new_pixmap=new_pixmap, progress=0.0,
            seed=actual_seed, piece_count=float(max(4, piece_count)),
            crack_complexity=max(0.5, min(2.0, crack_complexity)),
            mosaic_mode=mosaic_mode, weight_mode=max(0.0, min(4.0, float(weight_mode))),
        )
        self._pre_upload_textures(self._prepare_crumble_textures)
        self._profiler.start("crumble")

        def _crumble_update(progress: float) -> None:
            self._profiler.tick("crumble")
            if self._crumble is not None:
                self._crumble.progress = max(0.0, min(1.0, float(progress)))

        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            _crumble_update,
            lambda: self._on_crumble_complete(on_finished),
            transition_label="crumble",
        )

    def start_particle(
        self,
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
            if self._handle_no_old_image(new_pixmap, on_finished, "particle"):
                return None

        self._clear_all_transitions()
        actual_seed = seed if seed is not None else _random.random() * 1000.0
        self._particle = ParticleState(
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
        self._pre_upload_textures(self._prepare_particle_textures)
        self._profiler.start("particle")

        def _particle_update(progress: float) -> None:
            self._profiler.tick("particle")
            if self._particle is not None:
                self._particle.progress = max(0.0, min(1.0, float(progress)))

        return self._start_transition_animation(
            duration_ms, easing, animation_manager,
            _particle_update,
            lambda: self._on_particle_complete(on_finished),
            transition_label="particle",
        )

    # ------------------------------------------------------------------
    # Animation callbacks
    # ------------------------------------------------------------------

    def _update_transition_progress(self, state_attr: str, profiler_name: str, progress: float) -> None:
        """Generic progress update for transitions."""
        state = getattr(self, state_attr, None)
        if state is None:
            return
        state.progress = max(0.0, min(1.0, float(progress)))
        if profiler_name:
            self._profiler.tick(profiler_name)

    def _on_crossfade_update(self, progress: float) -> None:
        self._update_transition_progress("_crossfade", "", progress)

    def _on_crossfade_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("crossfade", "_crossfade", on_finished)

    def _on_slide_update(self, progress: float) -> None:
        self._update_transition_progress("_slide", "slide", progress)

    def _on_slide_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("slide", "_slide", on_finished)

    def _on_wipe_update(self, progress: float) -> None:
        self._update_transition_progress("_wipe", "wipe", progress)

    def _on_wipe_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("wipe", "_wipe", on_finished)

    def _on_blockspin_update(self, progress: float) -> None:
        self._update_transition_progress("_blockspin", "blockspin", progress)

    def _on_warp_update(self, progress: float) -> None:
        self._update_transition_progress("_warp", "warp", progress)

    def _on_raindrops_update(self, progress: float) -> None:
        self._update_transition_progress("_raindrops", "raindrops", progress)

    def _on_blockspin_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("blockspin", "_blockspin", on_finished)

    def _on_warp_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("warp", "_warp", on_finished, release_textures=True)

    def _on_raindrops_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("raindrops", "_raindrops", on_finished, release_textures=True)

    def _on_peel_update(self, progress: float) -> None:
        self._update_transition_progress("_peel", "peel", progress)

    def _on_peel_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("peel", "_peel", on_finished)

    def _on_blockflip_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("blockflip", "_blockflip", on_finished)

    def _on_diffuse_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("diffuse", "_diffuse", on_finished)

    def _on_blinds_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("blinds", "_blinds", on_finished)

    def _on_crumble_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("crumble", "_crumble", on_finished)

    def _on_particle_complete(self, on_finished: Optional[Callable[[], None]]) -> None:
        self._complete_transition("particle", "_particle", on_finished)

    def _set_transition_region(self, state_attr: str, region: Optional[QRegion]) -> None:
        """Generic region setter for region-based transitions."""
        state = getattr(self, state_attr, None)
        if state is None:
            return
        state.region = region
        self.update()

    def set_blockflip_region(self, region: Optional[QRegion]) -> None:
        self._set_transition_region("_blockflip", region)

    def set_blinds_region(self, region: Optional[QRegion]) -> None:
        self._set_transition_region("_blinds", region)

    def set_diffuse_region(self, region: Optional[QRegion]) -> None:
        self._set_transition_region("_diffuse", region)

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
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None
        elif self._slide is not None:
            try:
                new_pm = self._slide.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None
        elif self._wipe is not None:
            try:
                new_pm = self._wipe.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None
        elif self._blockflip is not None:
            try:
                new_pm = self._blockflip.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None
        elif self._blinds is not None:
            try:
                new_pm = self._blinds.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None
        elif self._diffuse is not None:
            try:
                new_pm = self._diffuse.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None

        if new_pm is None and self._raindrops is not None:
            try:
                new_pm = self._raindrops.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None

        # Peel keeps its own state but participates in snap-to-new when
        # cancelling, so the compositor can finish on the correct frame.
        if new_pm is None and self._peel is not None:
            try:
                new_pm = self._peel.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None

        if new_pm is None and self._blockspin is not None:
            try:
                new_pm = self._blockspin.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None

        if new_pm is None and self._warp is not None:
            try:
                new_pm = self._warp.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
                new_pm = None

        if new_pm is None and self._crumble is not None:
            try:
                new_pm = self._crumble.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
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
        # Transition to INITIALIZING state
        if not self._gl_state.transition(GLContextState.INITIALIZING):
            logger.warning("[GL COMPOSITOR] Failed to transition to INITIALIZING state")
            return

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
                            except Exception as e:
                                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
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

                    # Record GL info in centralized error handler for session-level tracking
                    self._error_handler.record_gl_info(vendor or "", renderer or "", version_str or "")
                    
                    # Check if error handler detected software GL and demoted capability
                    if self._error_handler.is_software_gl:
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
            
            # Transition to READY state on success
            if self._gl_pipeline and self._gl_pipeline.initialized:
                self._gl_state.transition(GLContextState.READY)
            else:
                self._gl_state.transition(GLContextState.ERROR, "Pipeline initialization failed")
        except Exception as e:
            # If initialization fails at this stage, we simply log and keep
            # using the existing QPainter-only path. Higher levels can decide
            # to disable GL transitions for the session based on this signal
            # in later phases when shader-backed effects are wired.
            logger.debug("[GL COMPOSITOR] initializeGL failed", exc_info=True)
            self._gl_state.transition(GLContextState.ERROR, str(e))

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

            # Compile all shader programs via centralized cache
            cache = get_program_cache()
            programs_to_compile = [
                (GLProgramCache.RAINDROPS, "raindrops_program", "raindrops_uniforms"),
                (GLProgramCache.WARP, "warp_program", "warp_uniforms"),
                (GLProgramCache.DIFFUSE, "diffuse_program", "diffuse_uniforms"),
                (GLProgramCache.BLOCK_FLIP, "blockflip_program", "blockflip_uniforms"),
                (GLProgramCache.PEEL, "peel_program", "peel_uniforms"),
                (GLProgramCache.CROSSFADE, "crossfade_program", "crossfade_uniforms"),
                (GLProgramCache.SLIDE, "slide_program", "slide_uniforms"),
                (GLProgramCache.WIPE, "wipe_program", "wipe_uniforms"),
                (GLProgramCache.BLINDS, "blinds_program", "blinds_uniforms"),
                (GLProgramCache.CRUMBLE, "crumble_program", "crumble_uniforms"),
                (GLProgramCache.PARTICLE, "particle_program", "particle_uniforms"),
            ]
            
            for program_name, program_attr, uniforms_attr in programs_to_compile:
                program_id = cache.get_program(program_name)
                if program_id is None:
                    logger.debug("[GL SHADER] Failed to compile %s shader", program_name)
                    self._gl_disabled_for_session = True
                    self._use_shaders = False
                    return
                setattr(self._gl_pipeline, program_attr, program_id)
                setattr(self._gl_pipeline, uniforms_attr, cache.get_uniforms(program_name))

            # NOTE: Shuffle and Claws shader initialization removed - these transitions are retired.

            # Initialize geometry - each compositor needs its own VAOs since
            # OpenGL VAOs are NOT shared between GL contexts (each display has its own context)
            if self._geometry_manager is None:
                self._geometry_manager = GLGeometryManager()
            if not self._geometry_manager.initialize():
                logger.warning("[GL COMPOSITOR] Failed to initialize geometry manager")
                self._gl_disabled_for_session = True
                self._use_shaders = False
                return
            
            # Copy geometry IDs to pipeline state for backward compatibility
            self._gl_pipeline.quad_vao = self._geometry_manager.quad_vao
            self._gl_pipeline.quad_vbo = self._geometry_manager.quad_vbo
            self._gl_pipeline.box_vao = self._geometry_manager.box_vao
            self._gl_pipeline.box_vbo = self._geometry_manager.box_vbo
            self._gl_pipeline.box_vertex_count = self._geometry_manager.box_vertex_count
            
            # Initialize texture manager - each compositor needs its own textures since
            # OpenGL textures are NOT shared between GL contexts
            if self._texture_manager is None:
                self._texture_manager = GLTextureManager()

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

    def _reset_pipeline_state(self) -> None:
        """Reset all pipeline state to zero/uninitialized."""
        if self._gl_pipeline is None:
            return
        self._release_transition_textures()
        program_attrs = [
            "basic_program", "raindrops_program", "warp_program", "diffuse_program",
            "blockflip_program", "peel_program", "crossfade_program", "slide_program",
            "wipe_program", "blinds_program", "crumble_program", "particle_program",
        ]
        for attr in program_attrs:
            setattr(self._gl_pipeline, attr, 0)
        self._gl_pipeline.quad_vao = 0
        self._gl_pipeline.quad_vbo = 0
        self._gl_pipeline.box_vao = 0
        self._gl_pipeline.box_vbo = 0
        self._gl_pipeline.box_vertex_count = 0
        self._gl_pipeline.initialized = False

    def _cleanup_gl_pipeline(self) -> None:
        if gl is None or self._gl_pipeline is None:
            return

        try:
            is_valid = getattr(self, "isValid", None)
            if callable(is_valid) and not is_valid():
                self._reset_pipeline_state()
                return
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)

        try:
            self.makeCurrent()
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            self._reset_pipeline_state()
            return

        try:
            # Clean up textures via texture manager
            try:
                if self._texture_manager is not None:
                    self._texture_manager.cleanup()
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to cleanup texture manager", exc_info=True)

            # Delete shader programs
            program_attrs = [
                "basic_program", "raindrops_program", "warp_program", "diffuse_program",
                "blockflip_program", "peel_program", "crossfade_program", "slide_program",
                "wipe_program", "blinds_program", "crumble_program",
            ]
            try:
                for attr in program_attrs:
                    prog_id = getattr(self._gl_pipeline, attr, 0)
                    if prog_id:
                        gl.glDeleteProgram(int(prog_id))
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to delete shader program", exc_info=True)

            # Delete geometry buffers
            try:
                for vbo_attr in ["quad_vbo", "box_vbo"]:
                    vbo_id = getattr(self._gl_pipeline, vbo_attr, 0)
                    if vbo_id:
                        buf = (ctypes.c_uint * 1)(int(vbo_id))
                        gl.glDeleteBuffers(1, buf)
                for vao_attr in ["quad_vao", "box_vao"]:
                    vao_id = getattr(self._gl_pipeline, vao_attr, 0)
                    if vao_id:
                        arr = (ctypes.c_uint * 1)(int(vao_id))
                        gl.glDeleteVertexArrays(1, arr)
            except Exception:
                logger.debug("[GL COMPOSITOR] Failed to delete geometry buffers", exc_info=True)

            self._reset_pipeline_state()
        finally:
            try:
                self.doneCurrent()
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)

    def cleanup(self) -> None:
        """Clean up GL resources and transition to DESTROYED state."""
        # Stop render strategy first to prevent timer callbacks during cleanup
        self._stop_render_strategy()
        
        # Transition to DESTROYING state
        self._gl_state.transition(GLContextState.DESTROYING)
        try:
            self._cleanup_gl_pipeline()
        except Exception:
            logger.debug("[GL COMPOSITOR] cleanup() failed", exc_info=True)
        finally:
            # Transition to DESTROYED state
            self._gl_state.transition(GLContextState.DESTROYED)
    
    def is_gl_ready(self) -> bool:
        """Check if GL context is ready for rendering.
        
        Uses the centralized GLStateManager for robust state checking.
        """
        return self._gl_state.is_ready()
    
    def get_gl_state(self) -> GLContextState:
        """Get current GL context state."""
        return self._gl_state.get_state()
    
    def get_gl_error_info(self) -> tuple:
        """Get GL error information if in error state."""
        return self._gl_state.get_error_info()

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
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
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

    def _can_use_grid_shader(self, state, program_attr: str) -> bool:
        """Check if a grid-based shader (diffuse, blockflip, blinds) can be used."""
        if state is None:
            return False
        if getattr(state, "cols", 0) <= 0 or getattr(state, "rows", 0) <= 0:
            return False
        return self._can_use_simple_shader(state, getattr(self._gl_pipeline, program_attr, 0))

    def _can_use_diffuse_shader(self) -> bool:
        return self._can_use_grid_shader(self._diffuse, "diffuse_program")

    def _can_use_blockflip_shader(self) -> bool:
        return self._can_use_grid_shader(self._blockflip, "blockflip_program")

    def _can_use_peel_shader(self) -> bool:
        st = self._peel
        if st is None or getattr(st, "strips", 0) <= 0:
            return False
        return self._can_use_simple_shader(st, getattr(self._gl_pipeline, "peel_program", 0))

    def _can_use_blinds_shader(self) -> bool:
        return self._can_use_grid_shader(self._blinds, "blinds_program")

    def _can_use_crumble_shader(self) -> bool:
        return self._can_use_simple_shader(self._crumble, getattr(self._gl_pipeline, "crumble_program", 0))

    def _can_use_particle_shader(self) -> bool:
        return self._can_use_simple_shader(self._particle, getattr(self._gl_pipeline, "particle_program", 0))

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

        if not self._ensure_gl_pipeline_ready():
            return

        self._warm_pixmap_textures(old_pixmap, new_pixmap)

    def warm_transition_resources(
        self,
        transition_name: str,
        old_pixmap: Optional[QPixmap],
        new_pixmap: Optional[QPixmap],
    ) -> bool:
        """Warm shader program + textures for a specific transition type."""
        if new_pixmap is None or new_pixmap.isNull():
            return False

        warm_old = old_pixmap
        if warm_old is None or warm_old.isNull():
            warm_old = new_pixmap

        if not self._ensure_gl_pipeline_ready():
            return False

        program_key = self._transition_program_map.get(transition_name)
        if program_key:
            try:
                cache = get_program_cache()
                if not cache.is_compiled(program_key):
                    cache.get_program(program_key)
            except Exception:
                logger.debug(
                    "[GL COMPOSITOR] Failed to precompile shader program for %s",
                    transition_name,
                    exc_info=True,
                )

        textures_ready = self._warm_pixmap_textures(warm_old, new_pixmap)
        state_ready = textures_ready and self._warm_transition_state(transition_name, warm_old, new_pixmap)
        if not state_ready:
            logger.debug("[GL COMPOSITOR] Transition warmup incomplete for %s", transition_name)
        return state_ready

    # NOTE: PBO and texture upload methods moved to GLTextureManager
    # See rendering/gl_programs/texture_manager.py

    def _release_transition_textures(self) -> None:
        """Release current transition texture references via texture manager."""
        if self._texture_manager is not None:
            self._texture_manager.release_transition_textures()

    def _prepare_pair_textures(self, old_pixmap: QPixmap, new_pixmap: QPixmap) -> bool:
        """Prepare texture pair via texture manager."""
        if self._gl_pipeline is None:
            return False
        try:
            result = self._texture_manager.prepare_transition_textures(old_pixmap, new_pixmap)
            if not result:
                self._gl_disabled_for_session = True
                self._use_shaders = False
            return result
        except Exception:
            logger.debug("[GL SHADER] Failed to upload transition textures", exc_info=True)
            self._release_transition_textures()
            self._gl_disabled_for_session = True
            self._use_shaders = False
            return False

    def _prepare_transition_textures(self, can_use_fn, state) -> bool:
        """Generic texture preparation for any transition type."""
        if not can_use_fn():
            return False
        if self._gl_pipeline is None:
            return False
        if self._texture_manager is None:
            return False
        if self._texture_manager.has_transition_textures():
            return True
        if state is None:
            return False
        return self._prepare_pair_textures(state.old_pixmap, state.new_pixmap)

    def _prepare_blockspin_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_blockspin_shader, self._blockspin)

    def _prepare_warp_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_warp_shader, self._warp)

    def _prepare_raindrops_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_raindrops_shader, self._raindrops)

    def _prepare_diffuse_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_diffuse_shader, self._diffuse)

    def _prepare_blockflip_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_blockflip_shader, self._blockflip)

    def _prepare_peel_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_peel_shader, self._peel)

    def _prepare_blinds_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_blinds_shader, self._blinds)

    def _prepare_crumble_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_crumble_shader, self._crumble)

    def _prepare_particle_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_particle_shader, self._particle)

    def _prepare_crossfade_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_crossfade_shader, self._crossfade)

    def _prepare_slide_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_slide_shader, self._slide)

    def _prepare_wipe_textures(self) -> bool:
        return self._prepare_transition_textures(self._can_use_wipe_shader, self._wipe)

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
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
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
        """Render BlockSpin transition - delegates to GLTransitionRenderer."""
        if gl is None:
            return
        if not self._can_use_blockspin_shader() or self._gl_pipeline is None or self._blockspin is None:
            return
        if not self._blockspin.old_pixmap or self._blockspin.old_pixmap.isNull() or not self._blockspin.new_pixmap or self._blockspin.new_pixmap.isNull():
            return
        if not self._prepare_blockspin_textures():
            return
        self._transition_renderer.render_blockspin_shader(target, self._blockspin)

    def _paint_peel_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_peel_shader, self._peel, self._prepare_peel_textures,
            "peel_program", "peel_uniforms", "peel"
        )

    def _paint_crumble_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_crumble_shader, self._crumble, self._prepare_crumble_textures,
            "crumble_program", "crumble_uniforms", "crumble"
        )

    def _paint_particle_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_particle_shader, self._particle, self._prepare_particle_textures,
            "particle_program", "particle_uniforms", "particle"
        )

    def _render_simple_shader(
        self, can_use_fn, state, prep_fn, program_attr: str, uniforms_attr: str, helper_name: str
    ) -> None:
        """Generic shader render - delegates to GLTransitionRenderer."""
        self._transition_renderer.render_simple_shader(
            can_use_fn, state, prep_fn, program_attr, uniforms_attr, helper_name
        )

    def _paint_blinds_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_blinds_shader, self._blinds, self._prepare_blinds_textures,
            "blinds_program", "blinds_uniforms", "blinds"
        )

    def _paint_wipe_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_wipe_shader, self._wipe, self._prepare_wipe_textures,
            "wipe_program", "wipe_uniforms", "wipe"
        )

    def _paint_slide_shader(self, target: QRect) -> None:
        """Render Slide transition - delegates to GLTransitionRenderer."""
        if not self._can_use_slide_shader() or self._gl_pipeline is None or self._slide is None:
            return
        if not self._slide.old_pixmap or self._slide.old_pixmap.isNull() or not self._slide.new_pixmap or self._slide.new_pixmap.isNull():
            return
        if not self._prepare_slide_textures():
            return
        self._transition_renderer.render_slide_shader(target, self._slide)

    def _paint_crossfade_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_crossfade_shader, self._crossfade, self._prepare_crossfade_textures,
            "crossfade_program", "crossfade_uniforms", "crossfade"
        )

    def _paint_diffuse_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_diffuse_shader, self._diffuse, self._prepare_diffuse_textures,
            "diffuse_program", "diffuse_uniforms", "diffuse"
        )

    def _paint_blockflip_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_blockflip_shader, self._blockflip, self._prepare_blockflip_textures,
            "blockflip_program", "blockflip_uniforms", "blockflip"
        )

    def _paint_warp_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_warp_shader, self._warp, self._prepare_warp_textures,
            "warp_program", "warp_uniforms", "warp"
        )

    def _paint_raindrops_shader(self, target: QRect) -> None:
        self._render_simple_shader(
            self._can_use_raindrops_shader, self._raindrops, self._prepare_raindrops_textures,
            "raindrops_program", "raindrops_uniforms", "raindrops"
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
            ("crumble", self._crumble, "Crumble"),
            ("particle", self._particle, "Particle"),
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
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
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
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)

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
                except Exception as e:
                    logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
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

        # BUG FIX: Unbind shader before using QPainter
        gl.glUseProgram(0)

        painter = QPainter(self)
        try:
            painter.drawImage(0, 0, image)
        finally:
            painter.end()

    def paintGL(self) -> None:  # type: ignore[override]
        _paint_start = time.time()
        
        # Phase 4: Disable GC during frame rendering to prevent GC pauses
        gc_controller = None
        _is_transition_active = self._frame_state is not None and self._frame_state.started and not self._frame_state.completed
        try:
            from core.performance.frame_budget import get_gc_controller, get_frame_budget
            gc_controller = get_gc_controller()
            gc_controller.disable_gc()
            
            # Track frame budget - only during active transitions to avoid false positives
            # from idle time between transitions (5+ second gaps are expected)
            frame_budget = get_frame_budget()
            if _is_transition_active:
                frame_budget.begin_frame()
                frame_budget.begin_category(frame_budget.CATEGORY_GL_RENDER)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)  # Non-critical - continue without frame budget
        
        try:
            self._paintGL_impl()
        finally:
            paint_elapsed = (time.time() - _paint_start) * 1000.0
            self._record_paint_metrics(paint_elapsed)
            
            # End frame budget tracking and re-enable GC
            try:
                if gc_controller:
                    gc_controller.enable_gc()
                    # Only end frame budget if we started it (during active transition)
                    if _is_transition_active:
                        frame_budget = get_frame_budget()
                        frame_budget.end_category(frame_budget.CATEGORY_GL_RENDER)
                        remaining = frame_budget.get_frame_remaining()
                        if remaining > 5.0:  # 5ms+ remaining
                            gc_controller.run_idle_gc(remaining)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            
            if paint_elapsed > 50.0 and is_perf_metrics_enabled():
                # Phase 8: Include GLStateManager transition history on dt_max spikes
                history = self._gl_state.get_transition_history(limit=5)
                history_str = ", ".join(f"{h[0].name}→{h[1].name}" for h in history) if history else "none"
                logger.warning(
                    "[PERF] [GL COMPOSITOR] Slow paintGL: %.2fms (recent transitions: %s)",
                    paint_elapsed, history_str
                )

    def _try_shader_path(self, name: str, state, can_use_fn, paint_fn, target, prep_fn=None) -> bool:
        """Try to render a transition via shader path. Returns True if successful."""
        if state is None or not can_use_fn():
            return False
        try:
            if prep_fn is not None and not prep_fn():
                return False
            paint_fn(target)
            self._paint_dimming_gl()
            self._paint_spotify_visualizer_gl()
            if is_perf_metrics_enabled():
                self._paint_debug_overlay_gl()
            return True
        except Exception:
            logger.debug("[GL SHADER] Shader %s path failed; disabling shader pipeline", name, exc_info=True)
            self._gl_disabled_for_session = True
            self._use_shaders = False
            return False

    def _paintGL_impl(self) -> None:
        """Internal paintGL implementation.
        
        Phase 6 GL Warmup Protection: Gate rendering behind GLStateManager.is_ready()
        to prevent paintGL from firing before initialization is complete.
        """
        # Phase 6: Prevent rendering until GL context is fully ready
        if not self._gl_state.is_ready():
            return
        
        # Profile paintGL sections to identify bottlenecks
        _section_times = {}
        _last_time = time.perf_counter()
        
        def _mark_section(name: str):
            nonlocal _last_time
            now = time.perf_counter()
            _section_times[name] = (now - _last_time) * 1000.0
            _last_time = now
        
        target = self.rect()
        _mark_section("init")

        # Try shader paths in priority order. On failure, fall back to QPainter.
        _mark_section("pre_shader")
        shader_paths = [
            ("blockspin", self._blockspin, self._can_use_blockspin_shader,
             self._paint_blockspin_shader, self._prepare_blockspin_textures),
            ("blockflip", self._blockflip, self._can_use_blockflip_shader,
             self._paint_blockflip_shader, None),
            ("raindrops", self._raindrops, self._can_use_raindrops_shader,
             self._paint_raindrops_shader, None),
            ("warp", self._warp, self._can_use_warp_shader,
             self._paint_warp_shader, None),
            ("diffuse", self._diffuse, self._can_use_diffuse_shader,
             self._paint_diffuse_shader, None),
            ("peel", self._peel, self._can_use_peel_shader,
             self._paint_peel_shader, None),
            ("blinds", self._blinds, self._can_use_blinds_shader,
             self._paint_blinds_shader, None),
            ("crumble", self._crumble, self._can_use_crumble_shader,
             self._paint_crumble_shader, None),
            ("particle", self._particle, self._can_use_particle_shader,
             self._paint_particle_shader, None),
            ("crossfade", self._crossfade, self._can_use_crossfade_shader,
             self._paint_crossfade_shader, None),
            ("slide", self._slide, self._can_use_slide_shader,
             self._paint_slide_shader, None),
            ("wipe", self._wipe, self._can_use_wipe_shader,
             self._paint_wipe_shader, None),
        ]

        shader_success = False
        for name, state, can_use_fn, paint_fn, prep_fn in shader_paths:
            if self._try_shader_path(name, state, can_use_fn, paint_fn, target, prep_fn):
                shader_success = True
                break

        # If all shader paths failed or are inactive, fall back to QPainter
        if not shader_success:
            _mark_section("shader_attempt")
        else:
            _mark_section("shader_render")
            # Log section times if any section took >10ms
            if is_perf_metrics_enabled() and _section_times:
                total = sum(_section_times.values())
                if total > 10.0:
                    sections_str = ", ".join(f"{k}={v:.1f}ms" for k, v in _section_times.items() if v > 1.0)
                    logger.debug("[PERF] [GL PAINT] Section times (total=%.1fms): %s", total, sections_str)
            return

        # QPainter fallback path (Group B) - delegates to GLTransitionRenderer
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target = self.rect()
            
            # Try each transition type in priority order
            if self._peel is not None:
                self._transition_renderer.render_peel_fallback(painter, target, self._peel)
                return
            
            if self._warp is not None:
                self._transition_renderer.render_warp_fallback(painter, target, self._warp)
                self._paint_spotify_visualizer(painter)
                self._paint_debug_overlay(painter)
                return
            
            if self._blockspin is not None:
                self._transition_renderer.render_blockspin_fallback(painter, target, self._blockspin)
                self._paint_spotify_visualizer(painter)
                return
            
            # Region-based transitions (blockflip, blinds, diffuse)
            for st, paint_vis in [(self._blockflip, True), (self._blinds, False), (self._diffuse, False)]:
                if st is not None:
                    self._transition_renderer.render_region_fallback(painter, target, st)
                    if paint_vis:
                        self._paint_spotify_visualizer(painter)
                    self._paint_debug_overlay(painter)
                    return
            
            if self._wipe is not None:
                self._transition_renderer.render_wipe_fallback(painter, target, self._wipe)
                self._paint_spotify_visualizer(painter)
                self._paint_debug_overlay(painter)
                return
            
            if self._slide is not None:
                self._transition_renderer.render_slide_fallback(painter, target, self._slide)
                self._paint_dimming(painter)
                self._paint_spotify_visualizer(painter)
                self._paint_debug_overlay(painter)
                return
            
            if self._crossfade is not None:
                self._transition_renderer.render_crossfade_fallback(painter, target, self._crossfade)
                self._paint_dimming(painter)
                self._paint_spotify_visualizer(painter)
                self._paint_debug_overlay(painter)
                return
            
            # No active transition -> draw base pixmap
            self._transition_renderer.render_base_image(painter, target, self._base_pixmap)
            self._paint_dimming(painter)
            self._paint_spotify_visualizer(painter)
            self._paint_debug_overlay(painter)
        finally:
            painter.end()
            _mark_section("qpainter_fallback")
            
        # Log section times if any section took >10ms
        if is_perf_metrics_enabled() and _section_times:
            total = sum(_section_times.values())
            if total > 10.0:
                sections_str = ", ".join(f"{k}={v:.1f}ms" for k, v in _section_times.items() if v > 1.0)
                logger.debug("[PERF] [GL PAINT] Section times (total=%.1fms): %s", total, sections_str)

    def _paint_spotify_visualizer_gl(self) -> None:
        if not self._spotify_vis_enabled:
            return
        painter = QPainter(self)
        try:
            self._paint_spotify_visualizer(painter)
        finally:
            painter.end()
    
    def _paint_dimming(self, painter: QPainter) -> None:
        """Paint the dimming overlay if enabled (QPainter fallback path)."""
        if not self._dimming_enabled or self._dimming_opacity <= 0.0:
            return
        
        try:
            painter.save()
            painter.setOpacity(self._dimming_opacity)
            painter.fillRect(self.rect(), Qt.GlobalColor.black)
            painter.restore()
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
    
    def _paint_dimming_gl(self) -> None:
        """Paint dimming overlay using native GL blending (faster than QPainter)."""
        if not self._dimming_enabled or self._dimming_opacity <= 0.0:
            return
        
        if gl is None:
            # Fallback to QPainter if GL not available
            painter = QPainter(self)
            try:
                self._paint_dimming(painter)
            finally:
                painter.end()
            return
        
        try:
            # BUG FIX: Unbind shader before drawing dimming overlay
            gl.glUseProgram(0)
            
            # Use native GL blending for dimming - much faster than QPainter
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            
            # Draw a black quad with the dimming opacity
            gl.glColor4f(0.0, 0.0, 0.0, self._dimming_opacity)
            gl.glBegin(gl.GL_QUADS)
            gl.glVertex2f(-1.0, -1.0)
            gl.glVertex2f(1.0, -1.0)
            gl.glVertex2f(1.0, 1.0)
            gl.glVertex2f(-1.0, 1.0)
            gl.glEnd()
            
            # Reset color to white for subsequent draws
            gl.glColor4f(1.0, 1.0, 1.0, 1.0)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] GL dimming failed, falling back to QPainter: %s", e)
            # Fallback to QPainter
            painter = QPainter(self)
            try:
                self._paint_dimming(painter)
            finally:
                painter.end()
