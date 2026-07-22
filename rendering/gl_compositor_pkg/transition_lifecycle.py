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
    new_payload = None
    new_texture_id = 0
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
                new_payload = getattr(state, "new_upload_payload", None)
            except Exception as e:
                logger.debug("[GL COMPOSITOR] Exception suppressed: %s", e)
            if new_pm is not None:
                manager = getattr(widget, "_texture_manager", None)
                if manager is not None:
                    new_texture_id = int(getattr(manager, "new_tex_id", 0) or 0)
                break

    committed = 0
    if snap_to_new and new_pm is not None:
        assign_base = getattr(widget, "_assign_base_pixmap", None)
        if callable(assign_base):
            committed = int(
                assign_base(
                    new_pm,
                    payload=new_payload,
                    texture_id=new_texture_id or None,
                )
                or 0
            )
        else:
            widget._base_pixmap = new_pm
            widget._base_upload_payload = new_payload
    widget._clear_all_transitions()
    if snap_to_new and new_pm is not None and committed <= 0:
        try:
            from rendering.gl_compositor_pkg.gl_lifecycle import (
                _schedule_deferred_base_texture_warmup,
            )

            _schedule_deferred_base_texture_warmup(widget)
        except Exception:
            logger.debug(
                "[GL COMPOSITOR] Failed to schedule cancelled-base residency warmup",
                exc_info=True,
            )
    requester = getattr(widget, "request_scene_update", None)
    if callable(requester):
        requester(source="transition_cancel")
    else:
        logger.error(
            "[GL COMPOSITOR] Presentation owner unavailable during transition cancellation"
        )
