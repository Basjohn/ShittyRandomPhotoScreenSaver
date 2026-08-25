"""Geometry for the non-painting Media/Visualizer compatibility anchor."""

from __future__ import annotations

from shiboken6 import Shiboken

from core.logging.logger import get_logger
from core.threading.manager import ThreadManager
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.media_widget import MediaPosition

logger = get_logger(__name__)


def _defer_update_position(widget) -> None:
    def _retry() -> None:
        try:
            if not Shiboken.isValid(widget):
                return
            widget._update_position()
        except RuntimeError:
            return
        except Exception:
            logger.debug("[MEDIA_WIDGET] Deferred anchor positioning failed", exc_info=True)

    _retry._srpss_runtime_generation = getattr(widget, "_runtime_generation", None)
    ThreadManager.single_shot(16, _retry)


def update_position(widget) -> None:
    """Position the retained-card anchor and its Visualizer dependent."""

    if widget.width() <= 0 or widget.height() <= 0:
        _defer_update_position(widget)
        return

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
    widget._position = position_map.get(
        widget._media_position, OverlayPosition.BOTTOM_LEFT
    )
    BaseOverlayWidget._update_position(widget)

    parent = widget.parent()
    position_visualizer = getattr(parent, "_position_spotify_visualizer", None)
    if callable(position_visualizer):
        try:
            position_visualizer()
        except Exception:
            logger.debug("[MEDIA_WIDGET] Visualizer positioning failed", exc_info=True)
