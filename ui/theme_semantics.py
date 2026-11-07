"""Shared derived palette semantics; no stored roles or theme-name rules."""
from __future__ import annotations

from ui.settings_theme_spec import Rgba


def _relative_luminance(color: Rgba) -> float:
    channels = [value / 255.0 for value in (color.r, color.g, color.b)]
    linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
              for value in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def relative_luminance(color: Rgba) -> float:
    """WCAG relative luminance of ``color``'s RGB (alpha ignored)."""
    return _relative_luminance(color)


def contrast_ratio(first: Rgba, second: Rgba) -> float:
    """WCAG contrast ratio of two colours' RGB (alpha ignored: composite first, see :func:`composite_over`)."""
    high, low = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def composite_over(top: Rgba, bottom: Rgba) -> Rgba:
    """``top`` source-over an opaque ``bottom``, as the compositor blends a translucent surface; opaque result."""
    weight = top.a / 255.0
    return Rgba(*(round(t * weight + b * (1.0 - weight))
                  for t, b in ((top.r, bottom.r), (top.g, bottom.g), (top.b, bottom.b))), 255)


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
