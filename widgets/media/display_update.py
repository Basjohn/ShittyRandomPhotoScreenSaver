"""Accepted Media state projection for the non-painting Visualizer anchor."""

from __future__ import annotations

from typing import TYPE_CHECKING

from shiboken6 import Shiboken

from core.logging.logger import get_logger
from core.media.media_controller import MediaTrackInfo

if TYPE_CHECKING:
    from widgets.media_widget import MediaWidget

logger = get_logger(__name__)


def _set_anchor_visible(widget: "MediaWidget", visible: bool) -> None:
    parent = widget.parentWidget()
    if visible and (
        bool(getattr(widget, "_custom_layout_shell_active", False))
        or bool(getattr(parent, "_custom_layout_edit_active", False))
    ):
        visible = False
    try:
        if visible:
            widget._update_position()
            widget.show()
        else:
            widget.hide()
    except Exception:
        logger.debug("[MEDIA_WIDGET] Failed to update anchor visibility", exc_info=True)
        return
    widget._notify_spotify_widgets_visibility()


def update_display(widget: "MediaWidget", info: MediaTrackInfo | None) -> None:
    """Publish accepted state and maintain only the Visualizer anchor contract."""

    try:
        if not Shiboken.isValid(widget):
            return
    except Exception:
        return

    widget._last_info = info
    if info is None:
        widget._last_track_identity = None
        _set_anchor_visible(widget, False)
        return

    identity = widget._compute_track_identity(info)
    state_changed = identity != widget._last_track_identity
    widget._last_track_identity = identity
    if state_changed or not widget._has_seen_first_track:
        widget._has_seen_first_track = True
        widget._emit_media_update(info)
    _set_anchor_visible(widget, True)
