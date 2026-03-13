"""GL Compositor Paint Orchestration - Extracted from gl_compositor.py.

Contains paintGL entry point and _paintGL_impl rendering pipeline.
All functions accept the compositor widget instance as the first parameter.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

try:
    from OpenGL import GL as gl  # type: ignore[import]
except ImportError:
    gl = None

from PySide6.QtGui import QPainter

from core.logging.logger import get_logger, is_perf_metrics_enabled
from rendering.gl_compositor_pkg.overlays import (
    paint_debug_overlay,
    paint_spotify_visualizer,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


def handle_paintGL(widget) -> None:  # type: ignore[override]
    _paint_start = time.time()
    
    # Phase 4: Disable GC during frame rendering to prevent GC pauses
    gc_controller = None
    _is_transition_active = widget._frame_state is not None and widget._frame_state.started and not widget._frame_state.completed
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
        paintGL_impl(widget, )
    finally:
        paint_elapsed = (time.time() - _paint_start) * 1000.0
        widget._record_paint_metrics(paint_elapsed)
        
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
            history = widget._gl_state.get_transition_history(limit=5)
            history_str = ", ".join(f"{h[0].name}→{h[1].name}" for h in history) if history else "none"
            logger.warning(
                "[PERF] [GL COMPOSITOR] Slow paintGL: %.2fms (recent transitions: %s)",
                paint_elapsed, history_str
            )

def paintGL_impl(widget) -> None:
    """Internal paintGL implementation.
    
    Phase 6 GL Warmup Protection: Gate rendering behind GLStateManager.is_ready()
    to prevent paintGL from firing before initialization is complete.
    """
    # Phase 6: Prevent rendering until GL context is fully ready
    if not widget._gl_state.is_ready():
        return
    
    # Profile paintGL sections to identify bottlenecks
    _section_times = {}
    _last_time = time.perf_counter()
    
    def _mark_section(name: str):
        nonlocal _last_time
        now = time.perf_counter()
        _section_times[name] = (now - _last_time) * 1000.0
        _last_time = now
    
    target = widget.rect()
    _mark_section("init")

    # Try shader paths in priority order. On failure, fall back to QPainter.
    _mark_section("pre_shader")
    shader_paths = [
        ("blockspin", widget._blockspin, widget._can_use_blockspin_shader,
         widget._paint_blockspin_shader, widget._prepare_blockspin_textures),
        ("blockflip", widget._blockflip, widget._can_use_blockflip_shader,
         widget._paint_blockflip_shader, None),
        ("raindrops", widget._raindrops, widget._can_use_raindrops_shader,
         widget._paint_raindrops_shader, None),
        ("warp", widget._warp, widget._can_use_warp_shader,
         widget._paint_warp_shader, None),
        ("diffuse", widget._diffuse, widget._can_use_diffuse_shader,
         widget._paint_diffuse_shader, None),
        ("blinds", widget._blinds, widget._can_use_blinds_shader,
         widget._paint_blinds_shader, None),
        ("crumble", widget._crumble, widget._can_use_crumble_shader,
         widget._paint_crumble_shader, None),
        ("particle", widget._particle, widget._can_use_particle_shader,
         widget._paint_particle_shader, None),
        ("burn", widget._burn, widget._can_use_burn_shader,
         widget._paint_burn_shader, None),
        ("crossfade", widget._crossfade, widget._can_use_crossfade_shader,
         widget._paint_crossfade_shader, None),
        ("slide", widget._slide, widget._can_use_slide_shader,
         widget._paint_slide_shader, None),
        ("wipe", widget._wipe, widget._can_use_wipe_shader,
         widget._paint_wipe_shader, None),
    ]

    # Check if ANY transition state is active (non-None).
    # When idle (between transitions), all states are None — that's normal.
    any_transition_active = any(state is not None for _, state, *_ in shader_paths)

    shader_success = False
    if any_transition_active:
        for name, state, can_use_fn, paint_fn, prep_fn in shader_paths:
            if widget._try_shader_path(name, state, can_use_fn, paint_fn, target, prep_fn):
                shader_success = True
                break

    _mark_section("shader_render" if shader_success else "shader_attempt")

    if not shader_success:
        # Idle or shader failure — render base image via QPainter.
        if any_transition_active:
            logger.error("[GL PAINT] All shader paths failed — rendering base image only")
        painter = QPainter(widget)
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target = widget.rect()
            widget._transition_renderer.render_base_image(painter, target, widget._base_pixmap)
            widget._paint_dimming(painter)
            paint_spotify_visualizer(widget, painter)
            paint_debug_overlay(widget, painter)
        finally:
            painter.end()
            _mark_section("qpainter_base_only")

    # Log section times if any section took >10ms
    if is_perf_metrics_enabled() and _section_times:
        total = sum(_section_times.values())
        if total > 10.0:
            sections_str = ", ".join(f"{k}={v:.1f}ms" for k, v in _section_times.items() if v > 1.0)
            logger.debug("[PERF] [GL PAINT] Section times (total=%.1fms): %s", total, sections_str)

