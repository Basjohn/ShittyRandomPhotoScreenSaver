"""GL Compositor Overlay Rendering - Extracted from gl_compositor.py.

Contains debug overlay, Spotify visualizer painting, dimming overlay,
and debug image rendering.
All functions accept the compositor widget instance as the first parameter.
"""

from __future__ import annotations

import time
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QPainter, QColor, QImage

from core.logging.logger import get_logger, is_perf_metrics_enabled

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)
_DEBUG_OVERLAY_REFRESH_INTERVAL_S = 0.12
_DEBUG_OVERLAY_TRANSITIONS: tuple[tuple[str, str, str], ...] = (
    ("slide", "_slide", "Slide"),
    ("wipe", "_wipe", "Wipe"),
    ("blockspin", "_blockspin", "BlockSpin"),
    ("warp", "_warp", "Warp"),
    ("raindrops", "_raindrops", "Ripple"),
    ("blockflip", "_blockflip", "BlockFlip"),
    ("diffuse", "_diffuse", "Diffuse"),
    ("burn", "_burn", "Burn"),
    ("blinds", "_blinds", "Blinds"),
    ("crumble", "_crumble", "Crumble"),
    ("particle", "_particle", "Particle"),
)


def _build_debug_overlay_payload(widget) -> Optional[tuple[str, str]]:
    """Return the PERF HUD lines for the currently active transition."""
    for name, attr, label in _DEBUG_OVERLAY_TRANSITIONS:
        state = getattr(widget, attr, None)
        if state is None:
            continue
        metrics = widget._profiler.get_metrics(name)
        if metrics is None:
            continue
        avg_fps, min_dt_ms, max_dt_ms, _ = metrics
        progress = getattr(state, "progress", 0.0)
        line1 = f"{label} t={progress:.2f}"
        line2 = f"{avg_fps:.1f} fps  dt_min={min_dt_ms:.1f}ms  dt_max={max_dt_ms:.1f}ms"
        return line1, line2
    return None


def _paint_debug_overlay_payload(painter: QPainter, payload: tuple[str, str]) -> None:
    """Paint a previously computed PERF HUD payload."""
    line1, line2 = payload
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


def paint_debug_overlay(widget, painter: QPainter) -> None:
    """Paint debug overlay showing transition profiling metrics."""
    if not is_perf_metrics_enabled():
        return

    payload = _build_debug_overlay_payload(widget)
    if payload is None:
        return

    painter.save()
    try:
        _paint_debug_overlay_payload(painter, payload)
    finally:
        painter.restore()

def paint_visualizer_scene(widget, painter: QPainter) -> bool:
    """Paint the compositor-owned visualizer without a fidelity substitute."""

    layer = getattr(widget, "_spotify_visualizer_layer", None)
    if layer is not None:
        paint_layer = getattr(widget, "paint_spotify_visualizer_layer", None)
        if callable(paint_layer):
            return bool(paint_layer(painter))
    return False

def render_debug_overlay_image(widget) -> Optional[QImage]:
    """Render the PERF HUD into a small offscreen image.

    This keeps glyph rasterisation fully in QPainter's software path so
    the final card can be composited on top of the GL surface without
    relying on GL text rendering state.
    """

    if not is_perf_metrics_enabled():
        widget._debug_overlay_cache_key = None
        widget._debug_overlay_cache_image = None
        return None
    size = widget.size()
    if size.width() <= 0 or size.height() <= 0:
        widget._debug_overlay_cache_key = None
        widget._debug_overlay_cache_image = None
        return None

    now = time.monotonic()
    cached_key = getattr(widget, "_debug_overlay_cache_key", None)
    cached_image = getattr(widget, "_debug_overlay_cache_image", None)
    cached_built_at = float(getattr(widget, "_debug_overlay_cache_built_at", 0.0) or 0.0)
    cached_size = cached_key[:2] if isinstance(cached_key, tuple) and len(cached_key) >= 2 else None
    size_key = (size.width(), size.height())
    if (
        cached_image is not None
        and cached_size == size_key
        and cached_built_at > 0.0
        and (now - cached_built_at) < _DEBUG_OVERLAY_REFRESH_INTERVAL_S
    ):
        return cached_image

    payload = _build_debug_overlay_payload(widget)
    if payload is None:
        widget._debug_overlay_cache_key = None
        widget._debug_overlay_cache_image = None
        widget._debug_overlay_cache_built_at = 0.0
        return None

    cache_key = (size.width(), size.height(), payload)
    if cached_key == cache_key and cached_image is not None:
        return cached_image

    image = QImage(size.width(), size.height(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    try:
        _paint_debug_overlay_payload(painter, payload)
    finally:
        painter.end()

    widget._debug_overlay_cache_key = cache_key
    widget._debug_overlay_cache_image = image
    widget._debug_overlay_cache_built_at = now
    return image
