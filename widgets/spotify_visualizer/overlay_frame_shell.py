from __future__ import annotations


def clear_overlay_backbuffer(gl, logger) -> None:
    try:
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.0, 0.0, 0.0, 0.0)
        gl.glClear(gl.GL_COLOR_BUFFER_BIT)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)


def resolve_frame_fade(overlay, logger):
    if not overlay._enabled:
        return None
    try:
        fade = float(overlay._fade)
    except Exception as e:
        logger.debug("[SPOTIFY_VIS] Exception suppressed: %s", e)
        fade = 0.0
    if fade <= 0.0:
        return None
    return fade


def render_overlay_frame(overlay, rect, fade: float, render_fn) -> None:
    stencil_active = overlay._begin_painted_card_stencil_clip(rect)
    try:
        render_fn(rect, fade)
    finally:
        overlay._end_painted_card_stencil_clip(stencil_active)
