"""Media Widget Layout - Extracted from media_widget.py.

Contains controls layout computation and position update logic.
All functions accept the widget instance as the first parameter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QRect, QTimer
from PySide6.QtGui import QFont, QFontMetrics

from core.logging.logger import get_logger
from widgets.base_overlay_widget import OverlayPosition, BaseOverlayWidget
from widgets.media_widget import MediaPosition

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def compute_controls_layout(widget):
    """Compute geometry for the transport controls row."""
    if not widget._show_controls:
        widget._controls_layout_cache = None
        return None

    width = widget.width()
    height = widget.height()
    if width <= 0 or height <= 0:
        widget._controls_layout_cache = None
        return None

    margins = widget.contentsMargins()
    content_left = margins.left()
    content_right = width - margins.right()
    content_width = content_right - content_left
    if content_width <= 60:
        widget._controls_layout_cache = None
        return None

    controls_font_pt = max(8, int((widget._font_size - 2) * 0.9))
    font = QFont(widget._font_family, controls_font_pt, QFont.Weight.Medium)
    fm = QFontMetrics(font)
    row_height = max(widget._controls_row_min_height(), int((fm.height() + 10) * 0.85))

    try:
        header_font_pt = int(widget._header_font_pt) if widget._header_font_pt > 0 else widget._font_size
    except Exception as e:
        logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        header_font_pt = widget._font_size

    cache_key = (
        width,
        height,
        margins.left(),
        margins.top(),
        margins.right(),
        margins.bottom(),
        controls_font_pt,
        header_font_pt,
    )
    cached = widget._controls_layout_cache
    if cached is not None and cached.get("_cache_key") == cache_key:
        return cached

    header_metrics = QFontMetrics(QFont(widget._font_family, header_font_pt, QFont.Weight.Bold))
    header_height = header_metrics.height()

    base_row_top = height - margins.bottom() - row_height - 5  # Shift up 5px for 3D depth effect
    min_row_top = margins.top() + header_height + 6
    row_top = max(min_row_top, base_row_top)
    if row_top + row_height > height - margins.bottom():
        row_top = max(margins.top(), height - margins.bottom() - row_height)
    if row_top < margins.top():
        row_top = margins.top()

    row_rect = QRect(
        int(content_left),
        int(row_top),
        int(content_width),
        int(row_height),
    )

    slot_width = content_width / 3.0
    inner_pad_x = max(5.0, slot_width * 0.07)
    inner_pad_y = max(2.0, row_height * 0.16)
    hit_slop = max(8, int(row_height * 0.28))

    button_rects = {}
    hit_rects = {}
    for index, key in enumerate(("prev", "play", "next")):
        slot_left = content_left + slot_width * index
        rect = QRect(
            int(slot_left + inner_pad_x),
            int(row_top + inner_pad_y),
            int(slot_width - inner_pad_x * 2),
            int(row_height - inner_pad_y * 2),
        )
        button_rects[key] = rect
        hit_rects[key] = rect.adjusted(-hit_slop, -hit_slop, hit_slop, hit_slop)

    layout = {
        "font": font,
        "row_rect": row_rect,
        "button_rects": button_rects,
        "hit_rects": hit_rects,
    }
    layout["_cache_key"] = cache_key
    widget._controls_layout_cache = layout
    return layout

def update_position(widget) -> None:
    """Update widget position using centralized base class logic.
    
    Delegates to BaseOverlayWidget._update_position() which handles:
    - Margin-based positioning for all 9 anchor positions
    - Visual padding offsets (when background is disabled)
    - Pixel shift and stack offset application
    - Bounds clamping to prevent off-screen drift
    
    This ensures consistent margin alignment across all overlay widgets.
    """
    # Guard against positioning before widget has valid size
    if widget.width() <= 0 or widget.height() <= 0:
        QTimer.singleShot(16, widget._update_position)
        return
    
    # Sync MediaPosition to OverlayPosition for base class
    position_map = {
        MediaPosition.TOP_LEFT: OverlayPosition.TOP_LEFT,
        MediaPosition.TOP_CENTER: OverlayPosition.TOP_CENTER,
        MediaPosition.TOP_RIGHT: OverlayPosition.TOP_RIGHT,
        MediaPosition.MIDDLE_LEFT: OverlayPosition.MIDDLE_LEFT,
        MediaPosition.CENTER: OverlayPosition.CENTER,
        MediaPosition.MIDDLE_RIGHT: OverlayPosition.MIDDLE_RIGHT,
        MediaPosition.BOTTOM_LEFT: OverlayPosition.BOTTOM_LEFT,
        MediaPosition.BOTTOM_CENTER: OverlayPosition.BOTTOM_CENTER,
        MediaPosition.BOTTOM_RIGHT: OverlayPosition.BOTTOM_RIGHT,
    }
    
    # Update base class position
    widget._position = position_map.get(widget._media_position, OverlayPosition.BOTTOM_LEFT)
    
    # Delegate to base class for centralized margin/positioning logic
    BaseOverlayWidget._update_position(widget)

    # Keep Spotify-related overlays anchored to the card
    parent = widget.parent()
    if parent is not None:
        if hasattr(parent, "_position_spotify_visualizer"):
            try:
                parent._position_spotify_visualizer()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)
        if hasattr(parent, "_position_spotify_volume"):
            try:
                parent._position_spotify_volume()
            except Exception as e:
                logger.debug("[MEDIA_WIDGET] Exception suppressed: %s", e)

