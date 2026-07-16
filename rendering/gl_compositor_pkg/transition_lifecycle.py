"""GL Compositor Transition Lifecycle - Extracted from gl_compositor.py.

Contains transition cancellation and Spotify visualizer state management.
All functions accept the compositor widget instance as the first parameter.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPixmap

from core.logging.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


def cancel_current_transition(widget, snap_to_new: bool = True) -> None:
    """Cancel any active compositor-driven transition.

    If ``snap_to_new`` is True, the compositor's base pixmap is updated to
    the new image of the in-flight transition (if any) before clearing
    state. This is used by transitions that want to avoid visual pops when
    interrupted.
    """

    if widget._animation_manager and widget._current_anim_id:
        try:
            widget._animation_manager.cancel_animation(widget._current_anim_id)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Failed to cancel current animation: %s", e, exc_info=True)
    widget._current_anim_id = None

    new_pm: Optional[QPixmap] = None
    if snap_to_new:
        for attr_name in (
            "_crossfade",
            "_slide",
            "_wipe",
            "_warp",
            "_blockflip",
            "_blockspin",
            "_blinds",
            "_diffuse",
            "_raindrops",
            "_crumble",
            "_particle",
            "_burn",
        ):
            state = getattr(widget, attr_name, None)
            if state is None:
                continue
            try:
                new_pm = state.new_pixmap
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            if new_pm is not None:
                break

    widget._clear_all_transitions()
    if snap_to_new and new_pm is not None:
        widget._base_pixmap = new_pm
    widget.update()

# ------------------------------------------------------------------
# QOpenGLWidget hooks
# ------------------------------------------------------------------

def set_spotify_visualizer_state(
    widget,
    rect: QRect,
    bars,
    bar_count: int,
    segments: int,
    fill_color: QColor,
    border_color: QColor,
    fade: float,
    playing: bool,
    visible: bool,
) -> None:
    """Update Spotify bar overlay state pushed from DisplayWidget.

    When ``visible`` is False or the geometry is invalid, the overlay is
    disabled. Otherwise the smoothed bar values are clamped into [0, 1]
    and cached so they can be drawn after the base image/transition but
    before the PERF HUD.
    """

    if not visible:
        widget._spotify_vis_enabled = False
        return

    try:
        count = int(bar_count)
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        count = 0
    try:
        segs = int(segments)
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        segs = 0

    if count <= 0 or segs <= 0:
        widget._spotify_vis_enabled = False
        return

    try:
        bars_seq = list(bars)
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        widget._spotify_vis_enabled = False
        return

    if not bars_seq:
        widget._spotify_vis_enabled = False
        return

    if len(bars_seq) > count:
        bars_seq = bars_seq[:count]
    elif len(bars_seq) < count:
        bars_seq = bars_seq + [0.0] * (count - len(bars_seq))

    clamped = []
    for v in bars_seq:
        try:
            f = float(v)
        except Exception as e:
            logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            f = 0.0
        if f < 0.0:
            f = 0.0
        if f > 1.0:
            f = 1.0
        clamped.append(f)

    if not clamped:
        widget._spotify_vis_enabled = False
        return

    widget._spotify_vis_enabled = True
    widget._spotify_vis_rect = QRect(rect)
    widget._spotify_vis_bars = clamped
    widget._spotify_vis_bar_count = len(clamped)
    widget._spotify_vis_segments = max(1, segs)
    widget._spotify_vis_fill_color = QColor(fill_color)
    widget._spotify_vis_border_color = QColor(border_color)
    try:
        widget._spotify_vis_fade = max(0.0, min(1.0, float(fade)))
    except Exception as e:
        logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
        widget._spotify_vis_fade = 1.0

