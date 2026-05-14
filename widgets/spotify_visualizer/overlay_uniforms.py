from __future__ import annotations


def _compute_safe_hue_offset(raw: float) -> float:
    """Keep hue offset out of the shader's <= 0.001 dead-zone."""
    return (raw + 0.002) % 1.0 if raw < 0.001 else raw


def _compute_global_rainbow_hue(overlay) -> float:
    raw = (overlay._accumulated_time * overlay._rainbow_speed * 0.1) % 1.0
    return _compute_safe_hue_offset(raw)


def _compute_per_bar_hue(overlay) -> float:
    raw = (overlay._accumulated_time * 0.05) % 1.0
    return _compute_safe_hue_offset(raw)


def upload_common_uniforms(gl, u: dict, overlay, mode: str, width: int, height: int, fade: float, logger) -> None:
    """Upload mode-neutral overlay uniforms before per-mode renderer dispatch."""

    loc = u.get("u_resolution", -1)
    if loc >= 0:
        gl.glUniform2f(loc, float(width), float(height))

    loc = u.get("u_dpr", -1)
    if loc >= 0:
        gl.glUniform1f(loc, overlay._get_dpr())

    loc = u.get("u_fade", -1)
    if loc >= 0:
        gl.glUniform1f(loc, float(max(0.0, min(1.0, fade))))

    loc = u.get("u_time", -1)
    if loc >= 0:
        gl.glUniform1f(loc, float(overlay._accumulated_time))

    loc = u.get("u_border_width", -1)
    if loc >= 0:
        gl.glUniform1f(loc, float(max(0.0, overlay._border_width_px)))

    loc_pb = u.get("u_rainbow_per_bar", -1)
    if loc_pb >= 0:
        gl.glUniform1i(loc_pb, 1 if overlay._rainbow_per_bar else 0)

    loc_rb = u.get("u_rainbow_border", -1)
    if loc_rb >= 0:
        gl.glUniform1i(loc_rb, 1 if overlay._spectrum_rainbow_border else 0)

    loc = u.get("u_rainbow_hue_offset", -1)
    rainbow_logged_mode = getattr(overlay, "_rainbow_logged_mode", None)
    if overlay._rainbow_enabled and rainbow_logged_mode != mode:
        hue_val = (overlay._accumulated_time * overlay._rainbow_speed * 0.1) % 1.0
        logger.info(
            "[SPOTIFY_VIS] Rainbow ACTIVE: enabled=%s per_bar=%s speed=%.2f loc=%d pb_loc=%d mode=%s "
            "accum_time=%.2f hue=%.4f",
            overlay._rainbow_enabled,
            overlay._rainbow_per_bar,
            overlay._rainbow_speed,
            loc,
            loc_pb,
            mode,
            overlay._accumulated_time,
            hue_val,
        )
        overlay._rainbow_logged_mode = mode
    if not overlay._rainbow_enabled:
        overlay._rainbow_logged_mode = None

    if loc >= 0:
        if overlay._rainbow_enabled:
            gl.glUniform1f(loc, float(_compute_global_rainbow_hue(overlay)))
        elif overlay._rainbow_per_bar and mode == "spectrum":
            gl.glUniform1f(loc, float(_compute_per_bar_hue(overlay)))
        else:
            gl.glUniform1f(loc, 0.0)
    elif overlay._rainbow_enabled:
        logger.warning(
            "[SPOTIFY_VIS] Rainbow BROKEN: u_rainbow_hue_offset loc=-1 for mode=%s "
            "(uniform missing or optimized out in shader)",
            mode,
        )
