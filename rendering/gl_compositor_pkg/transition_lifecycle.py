"""GL compositor transition lifecycle helpers."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtGui import QPixmap

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
