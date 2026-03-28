"""Shared visibility helpers for media-dependent satellite widgets."""
from __future__ import annotations

from typing import Callable


def resolve_anchor_visibility(anchor, *, missing_anchor_visible: bool | None = False) -> bool | None:
    """Resolve anchor visibility with explicit handling for missing anchors.

    ``missing_anchor_visible=None`` means "defer/no decision yet", which is
    useful during startup while an anchor widget exists conceptually but has not
    been wired yet.
    """
    if anchor is None:
        return missing_anchor_visible
    try:
        return bool(anchor.isVisible())
    except Exception:
        return False


def sync_anchor_dependent_visibility(
    widget,
    *,
    anchor,
    enabled: bool,
    has_faded_in: bool,
    start_fade_in: Callable[[], None],
    refresh_visible: Callable[[], None] | None = None,
    missing_anchor_visible: bool | None = False,
) -> bool:
    """Sync a dependent widget against its media anchor's visibility.

    Returns ``True`` when the dependent should remain visible. When
    ``missing_anchor_visible`` is ``None`` the helper intentionally takes no
    visibility action until a real anchor arrives.
    """
    if not enabled:
        try:
            widget.hide()
        except Exception:
            pass
        return False

    anchor_visible = resolve_anchor_visibility(
        anchor,
        missing_anchor_visible=missing_anchor_visible,
    )
    if anchor_visible is None:
        return False
    if not anchor_visible:
        try:
            widget.hide()
        except Exception:
            pass
        return False

    if not has_faded_in:
        start_fade_in()
    else:
        try:
            widget.show()
            widget.raise_()
        except Exception:
            return False

    if callable(refresh_visible):
        refresh_visible()
    return True
