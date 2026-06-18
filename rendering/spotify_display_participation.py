"""Helpers for choosing a participating display owner for Spotify widgets.

The visualizer's monitor routing can point at a display that is not currently
participating in the running compositor/display set. In those cases we still
need one visible runtime owner, but we must choose it from the active display
instances rather than freelancing off media ownership or off-screen geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging.logger import get_logger
from rendering.multi_monitor_coordinator import get_coordinator

logger = get_logger(__name__)


@dataclass(frozen=True)
class VisualizerSpawnResolution:
    """Resolved owner-selection state for a CUSTOM-routed visualizer."""

    requested_screen_index: int
    chosen_display: Any | None
    requested_display: Any | None
    fallback_display: Any | None

    @property
    def requested_has_runtime_presence(self) -> bool:
        return self.requested_display is not None

    @property
    def requested_is_participating(self) -> bool:
        return display_instance_is_participating(self.requested_display)


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


def _display_instance_has_live_screen(instance: Any) -> bool:
    if instance is None:
        return False
    if bool(getattr(instance, "_exiting", False)):
        return False
    screen = _resolve_display_screen(instance)
    if screen is None:
        return False
    try:
        geom = screen.geometry()
    except Exception:
        return False
    return bool(geom is not None and geom.isValid() and geom.width() > 0 and geom.height() > 0)


def _screen_index_matches(instance: Any, requested_screen_index: int) -> bool:
    try:
        return int(getattr(instance, "screen_index", -1)) == int(requested_screen_index)
    except Exception:
        return False


def display_instance_is_participating(instance: Any) -> bool:
    """Return True when *instance* is a live runtime display participant."""

    if not _display_instance_has_live_screen(instance):
        return False
    if getattr(instance, "_widget_manager", None) is None:
        return False
    return True


def describe_visualizer_spawn_display(
    requested_screen_index: int,
    *,
    current_display: Any | None,
) -> VisualizerSpawnResolution:
    """Describe requested/fallback display ownership for CUSTOM visualizer spawn."""

    participants: list[Any] = []
    requested_instance: Any | None = None
    try:
        for instance in get_coordinator().get_all_instances():
            if display_instance_is_participating(instance):
                participants.append(instance)
            if requested_instance is None and _screen_index_matches(instance, requested_screen_index):
                requested_instance = instance
    except Exception:
        participants = []
        requested_instance = None

    if display_instance_is_participating(current_display) and current_display not in participants:
        participants.append(current_display)
    if requested_instance is None and _screen_index_matches(current_display, requested_screen_index):
        requested_instance = current_display

    if participants:
        participants.sort(key=lambda instance: int(getattr(instance, "screen_index", 0)))

    for instance in participants:
        if _screen_index_matches(instance, requested_screen_index):
            return VisualizerSpawnResolution(
                requested_screen_index=requested_screen_index,
                chosen_display=instance,
                requested_display=instance,
                fallback_display=None,
            )

    fallback_display = participants[0] if participants else None
    if requested_instance is not None:
        return VisualizerSpawnResolution(
            requested_screen_index=requested_screen_index,
            chosen_display=requested_instance,
            requested_display=requested_instance,
            fallback_display=fallback_display,
        )

    return VisualizerSpawnResolution(
        requested_screen_index=requested_screen_index,
        chosen_display=fallback_display,
        requested_display=None,
        fallback_display=fallback_display,
    )


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

    resolution = describe_visualizer_spawn_display(
        requested_screen_index,
        current_display=current_display,
    )
    chosen = resolution.chosen_display
    if chosen is None:
        return None

    if resolution.requested_is_participating:
        return chosen

    requested = resolution.requested_display
    if requested is not None:
        if _display_instance_has_live_screen(requested):
            logger.debug(
                "[SPOTIFY_VIS] Requested CUSTOM monitor %s is live but not ready yet; deferring spawn to that display",
                requested_screen_index,
            )
        else:
            logger.debug(
                "[SPOTIFY_VIS] Requested CUSTOM monitor %s still exists in runtime but is not participating yet; "
                "holding ownership on that display until a cautious recheck decides fallback",
                requested_screen_index,
            )
        return chosen

    logger.warning(
        "[SPOTIFY_VIS][FALLBACK] Requested CUSTOM monitor %s is not participating; "
        "falling back to participating display screen_index=%s",
        requested_screen_index,
        getattr(chosen, "screen_index", "?"),
    )
    return chosen
