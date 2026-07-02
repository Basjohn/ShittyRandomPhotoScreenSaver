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
from rendering.adaptive_timer import _mark_widget_update_consumed
from rendering.gl_compositor_pkg.overlays import (
    paint_debug_overlay,
    paint_spotify_visualizer,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


_TRANSITION_SHADER_DESCRIPTORS = (
    ("blockspin", "_blockspin", "_can_use_blockspin_shader", "_paint_blockspin_shader", "_prepare_blockspin_textures"),
    ("blockflip", "_blockflip", "_can_use_blockflip_shader", "_paint_blockflip_shader", None),
    ("raindrops", "_raindrops", "_can_use_raindrops_shader", "_paint_raindrops_shader", None),
    ("warp", "_warp", "_can_use_warp_shader", "_paint_warp_shader", None),
    ("diffuse", "_diffuse", "_can_use_diffuse_shader", "_paint_diffuse_shader", None),
    ("blinds", "_blinds", "_can_use_blinds_shader", "_paint_blinds_shader", None),
    ("crumble", "_crumble", "_can_use_crumble_shader", "_paint_crumble_shader", None),
    ("particle", "_particle", "_can_use_particle_shader", "_paint_particle_shader", None),
    ("burn", "_burn", "_can_use_burn_shader", "_paint_burn_shader", None),
    ("crossfade", "_crossfade", "_can_use_crossfade_shader", "_paint_crossfade_shader", None),
    ("slide", "_slide", "_can_use_slide_shader", "_paint_slide_shader", None),
    ("wipe", "_wipe", "_can_use_wipe_shader", "_paint_wipe_shader", None),
)


def _active_transition_descriptors(widget) -> list[tuple]:
    """Return active transition descriptors without binding every paint method.

    Normal compositor ownership keeps exactly one transition state active.  The
    list shape is retained so fallback diagnostics can still report impossible
    multi-active states without reintroducing broad per-frame dispatch work.
    """
    active = []
    for descriptor in _TRANSITION_SHADER_DESCRIPTORS:
        state = getattr(widget, descriptor[1], None)
        if state is not None:
            active.append((descriptor, state))
    return active


def _active_shader_names(active_descriptors) -> list[str]:
    return [descriptor[0][0] for descriptor in active_descriptors]


def _sync_transition_progress_from_frame_state(widget) -> None:
    """Refresh active shader progress from paint-time interpolation.

    AnimationManager still owns duration/completion.  Paint frames should not
    be limited to the slower QTimer callback cadence when the compositor render
    timer is producing additional high-refresh frames.
    """

    frame_state = getattr(widget, "_frame_state", None)
    if frame_state is None:
        return
    try:
        progress = float(frame_state.get_interpolated_progress())
    except Exception:
        logger.debug("[GL COMPOSITOR] FrameState interpolation failed", exc_info=True)
        return
    progress = max(0.0, min(1.0, progress))
    active_descriptors = _active_transition_descriptors(widget)
    if not active_descriptors:
        return
    profiler = getattr(widget, "_profiler", None)
    for descriptor, state in active_descriptors:
        name, attr, *_ = descriptor
        if not hasattr(state, "progress"):
            continue
        try:
            state.progress = progress
            if profiler is not None and name:
                profiler.tick(name)
        except Exception:
            logger.debug("[GL COMPOSITOR] Failed to sync %s progress", attr, exc_info=True)


def _log_shader_fallback_once(widget, active_names: list[str]) -> None:
    """Emit one loud fallback record per repeated shader-failure signature."""
    last_failure = getattr(widget, "_last_shader_path_failure", "") or "<none>"
    signature = (
        tuple(active_names),
        last_failure,
        bool(getattr(widget, "_gl_disabled_for_session", False)),
        bool(getattr(widget, "_use_shaders", False)),
        getattr(widget, "_current_transition_name", None),
    )
    previous = getattr(widget, "_last_shader_fallback_signature", None)
    if previous == signature:
        try:
            widget._shader_fallback_suppressed_count = int(getattr(widget, "_shader_fallback_suppressed_count", 0)) + 1
        except Exception:
            pass
        return

    suppressed = int(getattr(widget, "_shader_fallback_suppressed_count", 0) or 0)
    try:
        widget._last_shader_fallback_signature = signature
        widget._shader_fallback_suppressed_count = 0
    except Exception:
        pass

    logger.error(
        "[GL PAINT][FALLBACK] All active shader paths failed; rendering base image only "
        "active=%s current=%s disabled=%s use_shaders=%s last_failure=%s suppressed_previous=%d",
        ",".join(active_names) if active_names else "<none>",
        getattr(widget, "_current_transition_name", None),
        bool(getattr(widget, "_gl_disabled_for_session", False)),
        bool(getattr(widget, "_use_shaders", False)),
        last_failure,
        suppressed,
    )


def handle_paintGL(widget) -> None:  # type: ignore[override]
    _paint_start = time.time()
    _mark_widget_update_consumed(widget)
    
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
    
    # Section timing is diagnostic-only. Sample it so --perf does not add
    # avoidable Python allocation/timestamp pressure to every high-refresh
    # paint while paint-duration metrics remain authoritative each frame.
    _sample_index = int(getattr(widget, "_paint_section_sample_counter", 0) or 0)
    try:
        widget._paint_section_sample_counter = _sample_index + 1
    except Exception:
        pass
    _collect_sections = is_perf_metrics_enabled() and (_sample_index % 60 == 0)
    _section_times = {} if _collect_sections else None
    _last_time = time.perf_counter() if _collect_sections else 0.0
    
    def _mark_section(name: str):
        nonlocal _last_time
        if _section_times is None:
            return
        now = time.perf_counter()
        _section_times[name] = (now - _last_time) * 1000.0
        _last_time = now
    
    target = widget.rect()
    _mark_section("init")
    _sync_transition_progress_from_frame_state(widget)
    _mark_section("progress_sync")

    # Try shader paths in priority order. On failure, fall back to QPainter.
    _mark_section("pre_shader")
    # Check if ANY transition state is active (non-None).
    # When idle (between transitions), all states are None — that's normal.
    active_descriptors = _active_transition_descriptors(widget)
    active_names = _active_shader_names(active_descriptors)
    any_transition_active = bool(active_names)

    shader_success = False
    if any_transition_active:
        for descriptor, state in active_descriptors:
            name, _attr, can_use_name, paint_name, prep_name = descriptor
            can_use_fn = getattr(widget, can_use_name)
            paint_fn = getattr(widget, paint_name)
            prep_fn = getattr(widget, prep_name) if prep_name else None
            if widget._try_shader_path(name, state, can_use_fn, paint_fn, target, prep_fn):
                shader_success = True
                break

    _mark_section("shader_render" if shader_success else "shader_attempt")

    if not shader_success:
        # Idle or shader failure — render base image via QPainter.
        if any_transition_active:
            _log_shader_fallback_once(widget, active_names)
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
    if _section_times:
        total = sum(_section_times.values())
        if total > 10.0:
            sections_str = ", ".join(f"{k}={v:.1f}ms" for k, v in _section_times.items() if v > 1.0)
            logger.debug("[PERF] [GL PAINT] Section times (total=%.1fms): %s", total, sections_str)

