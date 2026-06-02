"""Spectrum mode uniform renderer."""
from __future__ import annotations

from PySide6.QtGui import QColor

from core.logging.logger import get_logger
from core.settings.shadow_tuning import CARD_SHADOW_TUNING
from widgets.spotify_visualizer.renderers.gl_helpers import set1f as _set1f, set1i as _set1i, set_color4 as _set_color4

logger = get_logger(__name__)

_SPECTRUM_MARGIN_X = 8.0
_SPECTRUM_GAP_PX = 2.0
_SPECTRUM_LEFT_INSET_PX = 1.0
_SPECTRUM_RIGHT_INSET_PX = 3.0
_SPECTRUM_BASE_HEIGHT = 80.0


def compute_bar_height_scale(total_height: float) -> float:
    """Mirror the shader's height-scale math for Spectrum bar visibility."""
    try:
        cur_h = max(1.0, float(total_height))
    except Exception:
        cur_h = _SPECTRUM_BASE_HEIGHT
    raw_hs = max(1.0, cur_h / _SPECTRUM_BASE_HEIGHT)
    height_scale = 1.0 + (raw_hs ** 0.5 - 1.0) * 1.0
    return max(1.0, min(1.85, float(height_scale)))


def minimum_value_for_visible_segments(
    total_height: float,
    segment_count: int,
    visible_segments: float,
) -> float:
    """Return the normalized bar value needed to keep N Spectrum segments visible.

    This mirrors the Spectrum shader's `pow(value, 1.15)` plus height-scale
    shaping so runtime idle contracts can target what the user actually sees,
    not just "some small non-zero float" that may still look dead.
    """
    try:
        segments = int(segment_count)
    except Exception:
        segments = 0
    if segments <= 0:
        return 0.0

    target_segments = max(0.0, float(visible_segments))
    if target_segments <= 0.0:
        return 0.0

    # `round()` in the shader flips to N segments once the scaled height clears
    # the midpoint between segment counts.
    required_scaled_height = min(
        0.95,
        max(0.0, (target_segments - 0.5) / float(segments)),
    )
    if required_scaled_height <= 0.0:
        return 0.0

    height_scale = compute_bar_height_scale(total_height)
    curved = required_scaled_height / max(1.0, height_scale)
    if curved <= 0.0:
        return 0.0

    return max(0.0, min(1.0, float(curved) ** (1.0 / 1.15)))


def compute_bar_layout(
    total_width: float,
    count: int,
    *,
    margin_x: float = _SPECTRUM_MARGIN_X,
    gap: float = _SPECTRUM_GAP_PX,
    left_inset: float = _SPECTRUM_LEFT_INSET_PX,
    right_inset: float = _SPECTRUM_RIGHT_INSET_PX,
    card_shrink_right: float = float(CARD_SHADOW_TUNING.get("card_shrink_right", 11)),
) -> dict[str, float] | None:
    """Compute the horizontal Spectrum bar field layout.

    This is the authoritative Spectrum bar-field contract shared by CPU tests
    and the shader. The field intentionally biases one pixel left and keeps a
    slightly larger right guard so the left edge does not show a dead gutter
    while the rightmost bar keeps breathing room from the card edge.
    """
    try:
        bar_count = int(count)
    except Exception:
        return None

    if total_width <= 0.0 or bar_count <= 0:
        return None

    visible_card_width = max(1.0, float(total_width) - float(card_shrink_right))
    inner_width = visible_card_width - float(margin_x) * 2.0
    bar_region_width = inner_width - float(left_inset) - float(right_inset)
    total_gap = float(gap) * float(max(0, bar_count - 1))
    usable_width = bar_region_width - total_gap
    if bar_region_width <= 0.0 or usable_width <= 0.0:
        return None

    bar_width = usable_width / float(bar_count)
    span = bar_width * float(bar_count) + total_gap
    left_px = float(margin_x) + float(left_inset)
    right_padding = max(0.0, float(total_width) - (left_px + span))
    visible_right_padding = max(0.0, visible_card_width - (left_px + span))
    return {
        "bar_width_px": bar_width,
        "span_px": span,
        "left_px": left_px,
        "right_padding_px": right_padding,
        "visible_right_padding_px": visible_right_padding,
        "gap_px": float(gap),
        "bar_region_width_px": bar_region_width,
    }


def get_uniform_names() -> list[str]:
    return [
        "u_bar_count", "u_segments", "u_bar_height_scale", "u_single_piece",
        "u_slanted", "u_border_radius", "u_bars", "u_peaks",
        "u_playing", "u_ghost_alpha",
        "u_fill_color", "u_border_color",
        "u_spectrum_glow_enabled", "u_spectrum_glow_intensity", "u_spectrum_glow_color",
        "u_rainbow_per_bar",
        "u_rainbow_border",
        "u_bars_left", "u_bar_width_px", "u_bar_gap_px", "u_bar_span_px",
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

    total_width = 0.0
    try:
        total_width = float(s._render_rect.width()) if hasattr(s, "_render_rect") else 0.0
    except Exception:
        total_width = 0.0
    if total_width <= 0.0:
        try:
            total_width = float(s.width())
        except Exception:
            total_width = 0.0

    layout = compute_bar_layout(total_width, count)
    if layout is None:
        return False

    _set1f(gl, u, "u_bars_left", float(layout["left_px"]))
    _set1f(gl, u, "u_bar_width_px", float(layout["bar_width_px"]))
    _set1f(gl, u, "u_bar_gap_px", float(layout["gap_px"]))
    _set1f(gl, u, "u_bar_span_px", float(layout["span_px"]))

    # Height scale
    loc = u.get("u_bar_height_scale", -1)
    if loc >= 0:
        cur_h = max(1.0, float(s._render_rect.height()) if hasattr(s, '_render_rect') else 80.0)
        gl.glUniform1f(loc, float(max(1.0, cur_h / _SPECTRUM_BASE_HEIGHT)))

    _set1i(gl, u, "u_single_piece", 1 if s._single_piece else 0)
    _set1i(gl, u, "u_slanted", 1 if getattr(s, '_slanted', False) else 0)
    _set1f(gl, u, "u_border_radius", float(getattr(s, '_border_radius', 0.0)))
    _set1i(gl, u, "u_spectrum_glow_enabled", 1 if getattr(s, '_spectrum_glow_enabled', False) else 0)
    _set1f(gl, u, "u_spectrum_glow_intensity", float(getattr(s, '_spectrum_glow_intensity', 0.55)))

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
            ga = float(s._spectrum_ghost_alpha if s._spectrum_ghosting_enabled else 0.0)
        except Exception:
            ga = 0.0
        gl.glUniform1f(loc, max(0.0, min(1.0, ga)))

    # Fill / border colours
    _set_color4(gl, u, "u_fill_color", QColor(s._fill_color))
    _set_color4(gl, u, "u_border_color", QColor(s._border_color))
    _set_color4(gl, u, "u_spectrum_glow_color", QColor(getattr(s, '_spectrum_glow_color', s._border_color)))

    return True
