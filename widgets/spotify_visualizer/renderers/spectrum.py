"""Spectrum mode uniform renderer."""
from __future__ import annotations

from PySide6.QtGui import QColor

from core.logging.logger import get_logger

logger = get_logger(__name__)


def get_uniform_names() -> list[str]:
    return [
        "u_bar_count", "u_segments", "u_bar_height_scale", "u_single_piece",
        "u_slanted", "u_border_radius", "u_bars", "u_peaks",
        "u_playing", "u_ghost_alpha",
        "u_fill_color", "u_border_color",
        "u_rainbow_per_bar",
    ]


def upload_uniforms(gl, u: dict, s) -> bool:
    """Upload spectrum-specific uniforms.  *s* is the overlay instance."""
    try:
        count = int(s._bar_count)
        segments = int(s._segments)
    except Exception:
        return False
    if count <= 0 or segments <= 0:
        return False

    _set1i(gl, u, "u_bar_count", min(count, 64))
    _set1i(gl, u, "u_segments", segments)

    # Height scale
    loc = u.get("u_bar_height_scale", -1)
    if loc >= 0:
        _SPECTRUM_BASE_HEIGHT = 80.0
        cur_h = max(1.0, float(s._render_rect.height()) if hasattr(s, '_render_rect') else 80.0)
        gl.glUniform1f(loc, float(max(1.0, cur_h / _SPECTRUM_BASE_HEIGHT)))

    _set1i(gl, u, "u_single_piece", 1 if s._single_piece else 0)
    _set1i(gl, u, "u_slanted", 1 if getattr(s, '_slanted', False) else 0)
    _set1f(gl, u, "u_border_radius", float(getattr(s, '_border_radius', 0.0)))

    # Bar data
    bars = list(s._bars)
    if not bars:
        return False
    if len(bars) < 64:
        bars = bars + [0.0] * (64 - len(bars))
    else:
        bars = bars[:64]

    if not s._debug_bars_logged:
        try:
            sample = bars[:count] if count > 0 else [0.0]
            logger.debug(
                "[SPOTIFY_VIS] Shader bars snapshot: count=%d, min=%.4f, max=%.4f",
                count, min(sample), max(sample),
            )
        except Exception:
            pass
        s._debug_bars_logged = True

    loc = u.get("u_bars", -1)
    if loc >= 0:
        buf = s._bars_buffer
        buf.fill(0.0)
        for i in range(min(len(bars), 64)):
            buf[i] = float(bars[i]) * 0.55
        gl.glUniform1fv(loc, 64, buf)

    loc = u.get("u_peaks", -1)
    if loc >= 0:
        buf_peaks = s._peaks_buffer
        buf_peaks.fill(0.0)
        peaks = s._peaks
        for i in range(min(len(peaks), 64)):
            buf_peaks[i] = float(peaks[i]) * 0.55
        gl.glUniform1fv(loc, 64, buf_peaks)

    _set1i(gl, u, "u_playing", 1 if s._playing else 0)

    loc = u.get("u_ghost_alpha", -1)
    if loc >= 0:
        try:
            ga = float(s._ghost_alpha if s._ghosting_enabled else 0.0)
        except Exception:
            ga = 0.0
        gl.glUniform1f(loc, max(0.0, min(1.0, ga)))

    # Fill / border colours
    _set_color4(gl, u, "u_fill_color", QColor(s._fill_color))
    _set_color4(gl, u, "u_border_color", QColor(s._border_color))

    return True


# ── helpers ──────────────────────────────────────────────────────────────
def _set1f(gl, u, name, val):
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform1f(loc, float(val))

def _set1i(gl, u, name, val):
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform1i(loc, int(val))

def _set_color4(gl, u, name, qc):
    loc = u.get(name, -1)
    if loc >= 0:
        gl.glUniform4f(loc, float(qc.redF()), float(qc.greenF()),
                        float(qc.blueF()), float(qc.alphaF()))
