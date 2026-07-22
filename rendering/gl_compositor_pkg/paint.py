"""GL Compositor Paint Orchestration - Extracted from gl_compositor.py.

Contains paintGL entry point and _paintGL_impl rendering pipeline.
All functions accept the compositor widget instance as the first parameter.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
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
    paint_visualizer_scene,
)
from rendering.gl_compositor_pkg.shader_dispatch import (
    paint_idle_base_shader,
    paint_qpainter_overlays_gl,
)

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
win_diag_logger = logging.getLogger("win_diag")


@dataclass(frozen=True)
class PaintOutcome:
    path: str
    rendered: bool
    transition_rendered: bool
    terminal_transition_rendered: bool


_NO_PAINT_OUTCOME = PaintOutcome(
    path="not_ready",
    rendered=False,
    transition_rendered=False,
    terminal_transition_rendered=False,
)


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

_TRANSITION_SHADER_BY_NAME = {
    descriptor[0]: descriptor for descriptor in _TRANSITION_SHADER_DESCRIPTORS
}


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


def _resolve_active_transition(widget):
    """Resolve the compositor's singular transition owner without a broad scan.

    ``_current_transition_name`` and the matching state slot are committed by
    the same UI-thread transition-start transaction.  A scan is reserved for
    an already-invalid active frame so normal idle and transition paints stay
    constant-time.
    """

    transition_name = str(
        getattr(widget, "_current_transition_name", "") or ""
    ).strip().lower()
    descriptor = _TRANSITION_SHADER_BY_NAME.get(transition_name)
    if descriptor is not None:
        state = getattr(widget, descriptor[1], None)
        if state is not None:
            return descriptor, state

    frame_state = getattr(widget, "_frame_state", None)
    if frame_state is None:
        return None

    # This is an invariant-recovery path, not ordinary dispatch.  Keeping it
    # loud avoids turning a corrupt owner into a silent base-image paint.
    active = _active_transition_descriptors(widget)
    if not active:
        return None
    names = _active_shader_names(active)
    signature = (transition_name, tuple(names))
    if getattr(widget, "_last_transition_owner_mismatch", None) != signature:
        widget._last_transition_owner_mismatch = signature
        logger.error(
            "[GL PAINT][OWNERSHIP] Transition owner mismatch current=%s active=%s",
            transition_name or "<none>",
            ",".join(names),
        )
    return active[0]


def _active_shader_names(active_descriptors) -> list[str]:
    return [descriptor[0][0] for descriptor in active_descriptors]


def _sync_transition_progress_from_frame_state(
    widget,
    active_transition=None,
) -> float | None:
    """Refresh active shader progress from paint-time interpolation.

    AnimationManager still owns duration/completion.  Paint frames should not
    be limited to the slower QTimer callback cadence when the compositor render
    timer is producing additional high-refresh frames.
    """

    frame_state = getattr(widget, "_frame_state", None)
    if frame_state is None:
        return None
    try:
        progress = float(frame_state.get_interpolated_progress())
    except Exception:
        logger.debug("[GL COMPOSITOR] FrameState interpolation failed", exc_info=True)
        return None
    progress = max(0.0, min(1.0, progress))
    if active_transition is None:
        active_transition = _resolve_active_transition(widget)
    if active_transition is None:
        return progress
    profiler = getattr(widget, "_profiler", None)
    descriptor, state = active_transition
    name, attr, *_ = descriptor
    if not hasattr(state, "progress"):
        return progress
    try:
        state.progress = progress
        if profiler is not None and name:
            profiler.tick(name)
    except Exception:
        logger.debug("[GL COMPOSITOR] Failed to sync %s progress", attr, exc_info=True)
    return progress


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
    perf_enabled = is_perf_metrics_enabled()
    paint_start = time.perf_counter() if perf_enabled else 0.0
    paint_generation = 0
    paint_started = getattr(widget, "_presentation_paint_started", None)
    if callable(paint_started):
        try:
            paint_generation = int(paint_started())
        except Exception:
            logger.debug(
                "[GL COMPOSITOR] Presentation paint-start acknowledgement failed",
                exc_info=True,
            )
    
    _is_transition_active = widget._frame_state is not None and widget._frame_state.started and not widget._frame_state.completed
    frame_budget = None
    if _is_transition_active and perf_enabled:
        try:
            from core.performance.frame_budget import get_frame_budget

            # Frame-budget accounting is diagnostic-only. It must not add
            # locks or global GC state changes to ordinary compositor paints.
            frame_budget = get_frame_budget()
            frame_budget.begin_frame()
            frame_budget.begin_category(frame_budget.CATEGORY_GL_RENDER)
        except Exception as e:
            frame_budget = None
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
    
    paint_outcome = _NO_PAINT_OUTCOME
    try:
        result = paintGL_impl(widget, perf_enabled=perf_enabled)
        if isinstance(result, PaintOutcome):
            paint_outcome = result
    finally:
        paint_elapsed = (
            (time.perf_counter() - paint_start) * 1000.0
            if perf_enabled
            else 0.0
        )
        if perf_enabled:
            try:
                widget._record_paint_metrics(paint_elapsed)
            except Exception:
                logger.debug(
                    "[GL COMPOSITOR] Paint metrics recording failed",
                    exc_info=True,
                )
        
        if frame_budget is not None:
            try:
                frame_budget.end_category(frame_budget.CATEGORY_GL_RENDER)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        
        if perf_enabled and paint_elapsed > 50.0:
            # Phase 8: Include GLStateManager transition history on dt_max spikes
            history = widget._gl_state.get_transition_history(limit=5)
            history_str = ", ".join(f"{h[0].name}→{h[1].name}" for h in history) if history else "none"
            logger.warning(
                "[PERF] [GL COMPOSITOR] Slow paintGL: %.2fms (recent transitions: %s)",
                paint_elapsed, history_str
            )

        paint_completed = getattr(widget, "_presentation_paint_completed", None)
        if callable(paint_completed):
            try:
                paint_completed(
                    paint_generation,
                    terminal_transition_rendered=(
                        paint_outcome.terminal_transition_rendered
                    ),
                )
            except Exception:
                logger.error(
                    "[GL COMPOSITOR] Presentation paint-completion acknowledgement failed",
                    exc_info=True,
                )
                _mark_widget_update_consumed(widget)
        else:
            _mark_widget_update_consumed(widget)

def _record_section_time(
    section_times: dict[str, float],
    previous_time: float,
    name: str,
) -> float:
    now = time.perf_counter()
    section_times[name] = (now - previous_time) * 1000.0
    return now


def paintGL_impl(widget, *, perf_enabled: bool | None = None) -> PaintOutcome:
    """Internal paintGL implementation.
    
    Phase 6 GL Warmup Protection: Gate rendering behind GLStateManager.is_ready()
    to prevent paintGL from firing before initialization is complete.
    """
    # Phase 6: Prevent rendering until GL context is fully ready
    if not widget._gl_state.is_ready():
        widget._last_paint_path = "not_ready"
        return _NO_PAINT_OUTCOME
    
    # Section timing is diagnostic-only. Sample it so --perf does not add
    # avoidable Python allocation/timestamp pressure to every high-refresh
    # paint while paint-duration metrics remain authoritative each frame.
    if perf_enabled is None:
        perf_enabled = is_perf_metrics_enabled()
    section_times = None
    last_section_time = 0.0
    if perf_enabled:
        sample_index = int(
            getattr(widget, "_paint_section_sample_counter", 0) or 0
        )
        widget._paint_section_sample_counter = sample_index + 1
        if sample_index % 60 == 0:
            section_times = {}
            last_section_time = time.perf_counter()
    
    target = widget.rect()
    if section_times is not None:
        last_section_time = _record_section_time(
            section_times, last_section_time, "init"
        )
    active_transition = _resolve_active_transition(widget)
    frame_progress = _sync_transition_progress_from_frame_state(
        widget,
        active_transition,
    )
    if section_times is not None:
        last_section_time = _record_section_time(
            section_times, last_section_time, "progress_sync"
        )

    # Try shader paths in priority order. On failure, fall back to QPainter.
    if section_times is not None:
        last_section_time = _record_section_time(
            section_times, last_section_time, "pre_shader"
        )
    any_transition_active = active_transition is not None

    shader_success = False
    active_name = ""
    if active_transition is not None:
        descriptor, state = active_transition
        active_name, _attr, can_use_name, paint_name, prep_name = descriptor
        can_use_fn = getattr(widget, can_use_name)
        paint_fn = getattr(widget, paint_name)
        prep_fn = getattr(widget, prep_name) if prep_name else None
        shader_success = widget._try_shader_path(
            active_name,
            state,
            can_use_fn,
            paint_fn,
            target,
            prep_fn,
        )

    if section_times is not None:
        last_section_time = _record_section_time(
            section_times,
            last_section_time,
            "shader_render" if shader_success else "shader_attempt",
        )

    idle_shader_success = False
    if not any_transition_active:
        idle_shader_success = paint_idle_base_shader(widget)
        if idle_shader_success:
            paint_qpainter_overlays_gl(widget)
            if section_times is not None:
                last_section_time = _record_section_time(
                    section_times, last_section_time, "idle_gl"
                )

    if not shader_success and not idle_shader_success:
        # A transition shader failure, first-image cache miss, or genuinely
        # unavailable GL context retains the established QPainter safety path.
        if any_transition_active:
            _log_shader_fallback_once(widget, [active_name])
        painter = QPainter(widget)
        try:
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            target = widget.rect()
            widget._transition_renderer.render_base_image(painter, target, widget._base_pixmap)
            widget._paint_dimming(painter)
            paint_visualizer_scene(widget, painter)
            paint_debug_overlay(widget, painter)
        finally:
            painter.end()
            if section_times is not None:
                last_section_time = _record_section_time(
                    section_times, last_section_time, "qpainter_base_only"
                )

    paint_path = (
        "transition_gl"
        if shader_success
        else "idle_gl"
        if idle_shader_success
        else "transition_qpainter_fallback"
        if any_transition_active
        else "idle_qpainter_fallback"
    )
    try:
        widget._last_paint_path = paint_path
    except Exception:
        pass

    # Log section times if any section took >10ms
    if section_times:
        total = sum(section_times.values())
        if total > 10.0:
            sections_str = ", ".join(
                f"{key}={value:.1f}ms"
                for key, value in section_times.items()
                if value > 1.0
            )
            logger.debug("[PERF] [GL PAINT] Section times (total=%.1fms): %s", total, sections_str)

    terminal_rendered = bool(
        shader_success
        and any_transition_active
        and frame_progress is not None
        and frame_progress >= 0.999999
    )
    return PaintOutcome(
        path=paint_path,
        rendered=True,
        transition_rendered=bool(shader_success and any_transition_active),
        terminal_transition_rendered=terminal_rendered,
    )

