"""Centralized QColor ↔ list conversion utilities.

All UI and rendering code should use these functions instead of
inline conversion logic. Consolidates duplicated patterns from
widgets_tab_media.py and rendering/widget_setup.py.
"""
from __future__ import annotations

from typing import Any, List, Optional

from PySide6.QtGui import QColor

from core.logging.logger import get_logger

logger = get_logger(__name__)


def qcolor_to_list(color: Optional[QColor], fallback: Optional[List[int]] = None) -> List[int]:
    """Convert a QColor to an RGBA list [r, g, b, a].

    Args:
        color: QColor to convert (may be None or invalid)
        fallback: Default list if conversion fails. Defaults to [255, 255, 255, 255].

    Returns:
        List of [r, g, b, a] integers.
    """
    if fallback is None:
        fallback = [255, 255, 255, 255]
    if color is None:
        return list(fallback)
    try:
        if not color.isValid():
            return list(fallback)
        return [color.red(), color.green(), color.blue(), color.alpha()]
    except Exception:
        logger.debug("[COLOR_UTILS] qcolor_to_list failed, using fallback %s", fallback, exc_info=True)
        return list(fallback)


def list_to_qcolor(
    color_data: Any,
    fallback: Optional[QColor] = None,
    opacity_override: Optional[float] = None,
) -> Optional[QColor]:
    """Parse a color list [r, g, b] or [r, g, b, a] into a QColor.

    Args:
        color_data: List/tuple of color components.
        fallback: QColor to return if parsing fails (default: None).
        opacity_override: Optional opacity multiplier (0.0-1.0) applied to alpha.

    Returns:
        QColor or fallback if parsing fails.
    """
    try:
        r, g, b = int(color_data[0]), int(color_data[1]), int(color_data[2])
        a = int(color_data[3]) if len(color_data) > 3 else 255
        if opacity_override is not None:
            a = int(max(0.0, min(1.0, opacity_override)) * a)
        return QColor(r, g, b, a)
    except (TypeError, ValueError, IndexError, KeyError):
        logger.debug("[COLOR_UTILS] list_to_qcolor failed for %s", color_data, exc_info=True)
        return fallback
