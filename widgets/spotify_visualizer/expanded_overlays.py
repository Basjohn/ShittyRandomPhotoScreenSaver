"""Expanded Visualizer overlays (plan 01 §G, M3b): what the display manager publishes to the scene for them.

The overlays themselves are QML (``ExpandedVisualizerOverlays.qml``), loaded only while the display-wide card is
drawn. This module resolves, at event edges only, the two inputs that are not already on the Visualizer card:

* the options: ``widgets.spotify_visualizer.fullscreen_overlays`` (normalised by its one owner,
  ``core.settings.fullscreen_overlays``) as the QML map the overlays read, plus the active Widget Theme's card text
  colour for an overlay drawn on its own card;
* the active preset's display name: the preset owner's own name (``get_preset_names``), in Title Case by the shared
  SRPSS typography rule (``utils.text_utils.title_case``).

The border colour, width and radius, the card surface, its material and the card shadow are the Visualizer card's
own (the one card-chrome owner, already on the card); the Media source is the model the Visualizer already binds.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def resolve_expanded_overlay_config(section: Mapping[str, Any] | None, *, card_text_color: Any = None) -> dict[str, Any]:
    """The overlays' options as the QML map ``ExpandedVisualizerOverlays.qml`` reads (camelCase).

    ``card_text_color`` is the active Widget Theme's card text colour when the caller already resolved it (Fullscreen
    Edit projects a draft per gesture sample and resolves the theme once per session).
    """

    from core.settings.fullscreen_overlays import normalize_fullscreen_overlays
    from rendering.quick.widgets.surface_material import surface_text_color

    values = normalize_fullscreen_overlays(section.get("fullscreen_overlays") if isinstance(section, Mapping) else None)

    def overlay(name: str) -> dict[str, Any]:
        options = values[name]
        projected = {
            "corner": str(options["corner"]),
            "alwaysShow": bool(options["always_show"]),
            "card": bool(options["card"]),
            "offsetX": float(options["offset_x"]),
            "offsetY": float(options["offset_y"]),
            "scale": float(options["scale"]),
            # The text box's single-axis extents (ems of the overlay's font; 0 = the natural size).
            "textWidth": float(options["text_width"]),
            "textHeight": float(options["text_height"]),
        }
        if "media_controls" in options:
            projected["mediaControls"] = bool(options["media_controls"])
        if "hover_reveal" in options:
            # Show On Hover: the pointer resting where Now Playing is placed fades it back in (QML HoverHandler edges).
            projected["hoverReveal"] = bool(options["hover_reveal"])
        if "artwork_scale" in options:
            projected["artworkScale"] = float(options["artwork_scale"])
            projected["artworkWidth"] = float(options["artwork_width"])
            projected["artworkHeight"] = float(options["artwork_height"])
        return projected

    return {
        "fontFamily": str(values["font_family"]),
        "fontSize": int(values["font_size"]),
        "cardTextColor": surface_text_color() if card_text_color is None else card_text_color,
        "preset": overlay("preset"),
        "nowPlaying": overlay("now_playing"),
        # The Volume OSD's placement over the expanded card (applied by the scene controller to the OSD's geometry).
        "volumeOsd": {"offsetX": float(values["volume_osd"]["offset_x"]),
                      "offsetY": float(values["volume_osd"]["offset_y"]),
                      "scale": float(values["volume_osd"]["scale"])},
    }


def resolve_active_preset_display_name(section: Mapping[str, Any] | None, mode: str | None = None) -> str:
    """The active preset's name for ``mode`` (default: the section's mode) in Title Case; "" when there is none."""

    from core.settings.visualizer_mode_registry import coerce_visualizer_mode_id
    from core.settings.visualizer_presets import get_preset_names, resolve_preset_index_from_mapping
    from utils.text_utils import title_case

    if not isinstance(section, Mapping):
        return ""
    try:
        mode_id = coerce_visualizer_mode_id(str(mode if mode is not None else section.get("mode", "")))
        index = int(resolve_preset_index_from_mapping(mode_id, section))
        names = get_preset_names(mode_id)
    except (KeyError, TypeError, ValueError):
        return ""
    if not 0 <= index < len(names):
        return ""
    return title_case(str(names[index]).strip())


__all__ = ["resolve_active_preset_display_name", "resolve_expanded_overlay_config"]
