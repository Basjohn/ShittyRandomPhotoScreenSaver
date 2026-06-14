"""Helpers for choosing a participating display owner for Spotify widgets.

The visualizer's monitor routing can point at a display that is not currently
participating in the running compositor/display set. In those cases we still
need one visible runtime owner, but we must choose it from the active display
instances rather than freelancing off media ownership or off-screen geometry.
"""
from __future__ import annotations

from typing import Any

from rendering.multi_monitor_coordinator import get_coordinator


def _resolve_display_screen(instance: Any) -> Any | None:
    screen = getattr(instance, "_screen", None)
    if screen is not None:
        return screen
    try:
        screen_getter = getattr(instance, "screen", None)
        if callable(screen_getter):
            return screen_getter()
    except Exception:
        return None
    return None


def display_instance_is_participating(instance: Any) -> bool:
    """Return True when *instance* is a live runtime display participant."""

    if instance is None:
        return False
    if bool(getattr(instance, "_exiting", False)):
        return False
    if getattr(instance, "_widget_manager", None) is None:
        return False
    screen = _resolve_display_screen(instance)
    if screen is None:
        return False
    try:
        geom = screen.geometry()
    except Exception:
        return False
    return bool(geom is not None and geom.isValid() and geom.width() > 0 and geom.height() > 0)


def resolve_visualizer_spawn_display(
    requested_screen_index: int,
    *,
    current_display: Any | None,
) -> Any | None:
    """Return the participating display that should own visualizer spawn.

    Preference order:
    1. the requested display if it is participating
    2. the first participating display in stable screen-index order
    """

    participants: list[Any] = []
    try:
        for instance in get_coordinator().get_all_instances():
            if display_instance_is_participating(instance):
                participants.append(instance)
    except Exception:
        participants = []

    if display_instance_is_participating(current_display) and current_display not in participants:
        participants.append(current_display)

    if not participants:
        return None

    participants.sort(key=lambda instance: int(getattr(instance, "screen_index", 0)))

    for instance in participants:
        if int(getattr(instance, "screen_index", -1)) == int(requested_screen_index):
            return instance

    return participants[0]
