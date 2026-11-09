"""Neutral blurred-desktop stand-in on platforms without native composition.

The shared theme.window_surface() applies the material tint once above this
opaque neutral. Windows always uses its native untinted blur and never this
explicit platform substitute.
"""
from __future__ import annotations

from ui.settings_theme_spec import Rgba  # noqa: F401  (re-exported type of the underlay)
from ui.theme_semantics import settings_theme_is_light

# Representative blurred-desktop luminance under each palette polarity.
DARK_MATERIAL_NEUTRAL = Rgba(30, 30, 32, 255)
LIGHT_MATERIAL_NEUTRAL = Rgba(224, 225, 228, 255)


def material_underlay(theme) -> Rgba:
    """Return the neutral blurred-desktop base; window_surface applies tint once."""

    return LIGHT_MATERIAL_NEUTRAL if settings_theme_is_light(theme) else DARK_MATERIAL_NEUTRAL



__all__ = ["DARK_MATERIAL_NEUTRAL", "LIGHT_MATERIAL_NEUTRAL", "material_underlay"]
