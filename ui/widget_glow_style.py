"""Shared Widget Theme resolution for widget interaction glow colour."""

from __future__ import annotations

from typing import Sequence

from ui.widget_theme_active import get_active_widget_theme
from ui.widget_theme_spec import WidgetThemeSpec


def resolve_widget_glow_color(
    override: Sequence[int] | None,
    theme: WidgetThemeSpec | None = None,
) -> tuple[int, int, int, int]:
    """Resolve the persisted glow override against the active Widget Theme."""

    if override is None:
        active_theme = get_active_widget_theme() if theme is None else theme
        if not isinstance(active_theme, WidgetThemeSpec):
            raise TypeError("theme must be a WidgetThemeSpec or None")
        return active_theme.color("card.border").as_tuple()

    if not isinstance(override, (list, tuple)) or len(override) != 4:
        raise ValueError("widget glow colour requires four RGBA channels")
    try:
        channels = tuple(int(channel) for channel in override)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("widget glow colour requires numeric RGBA channels") from exc
    if any(channel < 0 or channel > 255 for channel in channels):
        raise ValueError("widget glow colour channels must be in [0, 255]")
    return channels


__all__ = ["resolve_widget_glow_color"]
