"""Shared derived palette semantics; no stored roles or theme-name rules."""
from __future__ import annotations

from ui.settings_theme_spec import Rgba


def _relative_luminance(color: Rgba) -> float:
    channels = [value / 255.0 for value in (color.r, color.g, color.b)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def uses_dark_text_on_light_surface(foreground: Rgba, surface: Rgba) -> bool:
    """The existing light-palette hierarchy, independent of backdrop/material alpha.

    Alpha remains authored composition data. This identifies the palette's text
    polarity; it does not repair, recolour or make its surfaces more opaque.
    """
    return _relative_luminance(foreground) <= 0.18 and _relative_luminance(surface) >= 0.55


def settings_theme_is_light(theme) -> bool:
    return uses_dark_text_on_light_surface(theme.color("text.primary"), theme.color("panel.group.surface"))


def widget_theme_is_light(theme) -> bool:
    return uses_dark_text_on_light_surface(theme.color("card.text"), theme.color("card.background"))
