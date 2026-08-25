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


def resolve_bars_fade(overlay, scene_fade: float) -> float:
    """Return the shader fade published alongside ``scene_fade``.

    The authored stagger is resolved once, by the logical owner, and travels
    with the state. Re-deriving it here would silently apply the startup
    stagger to a mode crossfade as well, which is not the authored behaviour.
    """
    value = getattr(overlay, "_bars_fade", None)
    if value is None:
        return float(scene_fade)
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return float(scene_fade)


def render_overlay_frame(overlay, rect, fade: float, render_fn) -> None:
    stencil_active = overlay._begin_compositor_card_stencil_clip(rect)
    try:
        render_fn(rect, fade)
    finally:
        overlay._end_compositor_card_stencil_clip(stencil_active)
