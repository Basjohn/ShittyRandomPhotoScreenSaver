from __future__ import annotations

import math
import time


_SPECTRUM_PRESENTATION_EPSILON = 1e-4
_SPECTRUM_DECAY_TAU_SECONDS = 0.045
_SPECTRUM_MAX_FRAME_GAP_SECONDS = 0.25
_SPECTRUM_PRESENTATION_ATTRS = (
    "_spectrum_presentation_seen_set_state_total",
    "_spectrum_presentation_target_bars",
    "_spectrum_presentation_bars",
    "_spectrum_presentation_last_ts",
    "_spectrum_presentation_identity",
)


def _reset_spectrum_presentation(overlay) -> None:
    """Drop presentation-only Spectrum state at visibility/ownership boundaries."""

    for attr in _SPECTRUM_PRESENTATION_ATTRS:
        try:
            delattr(overlay, attr)
        except AttributeError:
            pass


def _normalise_bars(values) -> list[float]:
    try:
        source = list(values)
    except Exception:
        return []

    result: list[float] = []
    for value in source:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        if not math.isfinite(number):
            number = 0.0
        result.append(max(0.0, min(1.0, number)))
    return result


def advance_spectrum_presentation(overlay, *, now_ts: float | None = None) -> bool:
    """Apply zero-latency-attack, presentation-only Spectrum decay smoothing.

    The latest source bars remain authoritative targets. Rising values snap to
    the newest target immediately; only falling values interpolate on the
    overlay paint cadence. The function returns True while another local paint
    is required to finish convergence.
    """

    if (
        not bool(getattr(overlay, "_enabled", False))
        or str(getattr(overlay, "_vis_mode", "") or "").lower() != "spectrum"
    ):
        _reset_spectrum_presentation(overlay)
        return False

    incoming = _normalise_bars(getattr(overlay, "_bars", []))
    if not incoming:
        _reset_spectrum_presentation(overlay)
        return False

    if now_ts is None:
        now_ts = time.monotonic()
    try:
        now = float(now_ts)
    except (TypeError, ValueError):
        now = time.monotonic()

    try:
        source_serial = int(getattr(overlay, "_perf_set_state_total", 0) or 0)
    except (TypeError, ValueError):
        source_serial = 0

    identity = (
        "spectrum",
        getattr(overlay, "_engine_generation", None),
        getattr(overlay, "_activation_id", None),
        int(getattr(overlay, "_bar_count", len(incoming)) or len(incoming)),
        float(getattr(overlay, "_last_reset_ts", 0.0) or 0.0),
    )
    previous_identity = getattr(overlay, "_spectrum_presentation_identity", None)
    identity_changed = previous_identity != identity
    seen_serial = getattr(
        overlay,
        "_spectrum_presentation_seen_set_state_total",
        None,
    )
    source_updated = seen_serial != source_serial

    target = getattr(overlay, "_spectrum_presentation_target_bars", None)
    if source_updated or identity_changed or not isinstance(target, list):
        target = list(incoming)
        overlay._spectrum_presentation_target_bars = target
        overlay._spectrum_presentation_seen_set_state_total = source_serial

    presented = getattr(overlay, "_spectrum_presentation_bars", None)
    last_ts = float(getattr(overlay, "_spectrum_presentation_last_ts", 0.0) or 0.0)
    frame_gap = now - last_ts if last_ts > 0.0 else 0.0
    must_snap = (
        identity_changed
        or not isinstance(presented, list)
        or len(presented) != len(target)
        or last_ts <= 0.0
        or frame_gap <= 0.0
        or frame_gap > _SPECTRUM_MAX_FRAME_GAP_SECONDS
    )

    active = False
    if must_snap:
        presented = list(target)
    else:
        dt = max(1e-4, min(0.05, frame_gap))
        decay_alpha = 1.0 - math.exp(-dt / _SPECTRUM_DECAY_TAU_SECONDS)
        next_bars: list[float] = []
        for current, destination in zip(presented, target):
            current_value = float(current)
            target_value = float(destination)
            if target_value >= current_value:
                # Never smooth attack: a newly authoritative rise is visible on
                # this paint rather than one or more presentation frames later.
                next_value = target_value
            else:
                next_value = current_value + (
                    target_value - current_value
                ) * decay_alpha
                if abs(next_value - target_value) <= _SPECTRUM_PRESENTATION_EPSILON:
                    next_value = target_value
                else:
                    active = True
            next_bars.append(next_value)
        presented = next_bars

    overlay._spectrum_presentation_identity = identity
    overlay._spectrum_presentation_bars = list(presented)
    overlay._spectrum_presentation_last_ts = now
    overlay._bars = list(presented)
    return active


def clear_overlay_backbuffer(gl, logger) -> None:
    try:
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)


def resolve_frame_fade(overlay, logger):
    if not overlay._enabled:
        _reset_spectrum_presentation(overlay)
        return None
    try:
        fade = float(overlay._fade)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        fade = 0.0
    if fade <= 0.0:
        _reset_spectrum_presentation(overlay)
        return None
    return fade


def render_overlay_frame(overlay, rect, fade: float, render_fn) -> None:
    spectrum_decay_active = advance_spectrum_presentation(overlay)
    stencil_active = overlay._begin_painted_card_stencil_clip(rect)
    try:
        render_fn(rect, fade)
    finally:
        overlay._end_painted_card_stencil_clip(stencil_active)

    if spectrum_decay_active:
        request_update = getattr(overlay, "_request_frame_update", None)
        if callable(request_update):
            request_update()
        else:
            update = getattr(overlay, "update", None)
            if callable(update):
                update()
