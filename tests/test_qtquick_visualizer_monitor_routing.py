"""Canonical Quick visualizer monitor routing regression (H correction).

The single Quick ``spotify_visualizer`` edge must resolve its admitted monitor
through the canonical descriptor/effective-routing authority, not from the
visualizer's own persisted ``monitor`` directly:

- OUTSIDE CUSTOM the visualizer follows Media's effective monitor route;
- while CUSTOM owns the committed layout the visualizer's OWN persisted monitor
  route is authoritative.

Media and the visualizer's stored monitor deliberately DISAGREE here so a test
cannot accidentally pass under both routing interpretations.
"""
from __future__ import annotations

from engine.display_manager import DisplayManager


# Media routes to monitor 2 (index 1); the visualizer's own stored monitor routes
# to monitor 3 (index 2). The two must never coincide in these bars.
def _widgets(position: str) -> dict:
    return {
        "family_activation": {"media": True, "visualizers": True},
        "media": {"monitor": "2", "position": "Center"},
        "spotify_visualizer": {"monitor": "3", "position": position},
    }


def test_outside_custom_visualizer_follows_media_route():
    # Non-CUSTOM position -> effective route is Media's monitor (2 -> index 1),
    # NOT the visualizer's own stored monitor (3).
    idx = DisplayManager._resolve_visualizer_requested_screen_index(_widgets("Center"))
    assert idx == 1


def test_custom_makes_visualizer_own_monitor_authoritative():
    # CUSTOM position -> the visualizer's OWN stored monitor is authoritative
    # (3 -> index 2), NOT Media's monitor (2).
    idx = DisplayManager._resolve_visualizer_requested_screen_index(_widgets("Custom"))
    assert idx == 2


def test_all_media_route_resolves_first_participant_outside_custom():
    widgets = _widgets("Center")
    widgets["media"]["monitor"] = "ALL"
    # ALL -> first participant sentinel (-1), resolved from Media outside CUSTOM.
    assert DisplayManager._resolve_visualizer_requested_screen_index(widgets) == -1


def test_all_visualizer_route_resolves_first_participant_in_custom():
    widgets = _widgets("Custom")
    widgets["spotify_visualizer"]["monitor"] = "ALL"
    # In CUSTOM the visualizer's own ALL wins even though Media names monitor 2.
    assert DisplayManager._resolve_visualizer_requested_screen_index(widgets) == -1


def test_missing_config_is_first_participant():
    assert DisplayManager._resolve_visualizer_requested_screen_index({}) == -1
    assert DisplayManager._resolve_visualizer_requested_screen_index(None) == -1
