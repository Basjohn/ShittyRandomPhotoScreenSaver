"""Opaque Settings material underlay for platforms without native Glass/Acrylic.

Windows composes every Settings theme over a DWM AccentPolicy backdrop: Acrylic
blurs the desktop and applies the theme's ``backdrop.tint``; Glass blurs it
untinted. The theme's semantic Qt surfaces are authored as translucent layers
*over that blurred material* (``Docs/Architecture/Settings_Theme_Architecture.md``).

Linux has no equivalent composition primitive SRPSS can rely on: a compositor,
if present, shows the raw unblurred desktop through those layers; without one the
layers fall onto black. Either way the authored look is lost and readability
depends on the wallpaper. On such platforms the Settings dialog paints this one
opaque underlay beneath its content instead. It stands in for "the blurred desktop
under the material":

* a neutral matched to the theme's existing light/dark polarity
  (``ui.theme_semantics.settings_theme_is_light``), so light themes stay light and
  dark themes stay dark;
* Acrylic then applies its authored tint at its authored strength, exactly as the
  native material does; Glass stays untinted, as natively.

The theme's semantic surfaces are painted over it unchanged. This is a platform
substitute, never a Windows fallback: Windows always uses the native backdrop.
"""
from __future__ import annotations

from ui.settings_theme_spec import Rgba
from ui.theme_semantics import settings_theme_is_light

# Representative blurred-desktop luminance under each palette polarity.
DARK_MATERIAL_NEUTRAL = Rgba(30, 30, 32, 255)
LIGHT_MATERIAL_NEUTRAL = Rgba(224, 225, 228, 255)


def _mix(base: int, over: int, weight: float) -> int:
    return max(0, min(255, round(base + (over - base) * weight)))


def material_underlay(theme) -> Rgba:
    """Return the opaque underlay standing in for the theme's native material."""

    neutral = LIGHT_MATERIAL_NEUTRAL if settings_theme_is_light(theme) else DARK_MATERIAL_NEUTRAL
    backdrop = theme.backdrop
    if backdrop.mode != "acrylic":
        return neutral
    tint = backdrop.tint
    weight = tint.a / 255.0
    return Rgba(_mix(neutral.r, tint.r, weight), _mix(neutral.g, tint.g, weight), _mix(neutral.b, tint.b, weight), 255)


__all__ = ["DARK_MATERIAL_NEUTRAL", "LIGHT_MATERIAL_NEUTRAL", "material_underlay"]
