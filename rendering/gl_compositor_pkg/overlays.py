"""GL Compositor Overlay Rendering - Extracted from gl_compositor.py.

Contains debug overlay, Spotify visualizer painting, dimming overlay,
and debug image rendering.
All functions accept the compositor widget instance as the first parameter.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

try:
    from OpenGL import GL as gl  # type: ignore[import]
except ImportError:
    gl = None

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QImage

from core.logging.logger import get_logger, is_perf_metrics_enabled

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def paint_debug_overlay(widget, painter: QPainter) -> None:
    """Paint debug overlay showing transition profiling metrics."""
    if not is_perf_metrics_enabled():
        return

    # Map transition states to their profiler names and display labels
    transitions = [
        ("slide", widget._slide, "Slide"),
        ("wipe", widget._wipe, "Wipe"),
        ("peel", widget._peel, "Peel"),
        ("blockspin", widget._blockspin, "BlockSpin"),
        ("warp", widget._warp, "Warp"),
        ("raindrops", widget._raindrops, "Ripple"),
        ("blockflip", widget._blockflip, "BlockFlip"),
        ("diffuse", widget._diffuse, "Diffuse"),
        ("blinds", widget._blinds, "Blinds"),
        ("crumble", widget._crumble, "Crumble"),
        ("particle", widget._particle, "Particle"),
    ]

    active_label = None
    line1 = ""
    line2 = ""

    for name, state, label in transitions:
        if state is None:
            continue
        metrics = widget._profiler.get_metrics(name)
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

def paint_spotify_visualizer(widget, painter: QPainter) -> None:
    if not widget._spotify_vis_enabled:
        return

    rect = widget._spotify_vis_rect
    bars = widget._spotify_vis_bars
    if rect is None or bars is None:
        return

    try:
        fade = float(widget._spotify_vis_fade)
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        fade = 0.0
    if fade <= 0.0:
        return

    count = widget._spotify_vis_bar_count
    segments = widget._spotify_vis_segments
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

    fill = QColor(widget._spotify_vis_fill_color or QColor(200, 200, 200, 230))
    border = QColor(widget._spotify_vis_border_color or QColor(255, 255, 255, 255))

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

def render_debug_overlay_image(widget) -> Optional[QImage]:
    """Render the PERF HUD into a small offscreen image.

    This keeps glyph rasterisation fully in QPainter's software path so
    the final card can be composited on top of the GL surface without
    relying on GL text rendering state.
    """

    if not is_perf_metrics_enabled():
        return None
    size = widget.size()
    if size.width() <= 0 or size.height() <= 0:
        return None

    image = QImage(size.width(), size.height(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    try:
        widget._paint_debug_overlay(painter)
    finally:
        painter.end()

    return image

def paint_dimming_gl(widget) -> None:
    """Paint dimming overlay using native GL blending (faster than QPainter)."""
    if not widget._dimming_enabled or widget._dimming_opacity <= 0.0:
        return
    
    if gl is None:
        # Fallback to QPainter if GL not available
        painter = QPainter(widget)
        try:
            widget._paint_dimming(painter)
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
        gl.glColor4f(0.0, 0.0, 0.0, widget._dimming_opacity)
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
        painter = QPainter(widget)
        try:
            widget._paint_dimming(painter)
        finally:
            painter.end()
