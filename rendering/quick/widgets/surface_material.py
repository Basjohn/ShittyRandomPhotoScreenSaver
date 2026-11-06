"""Card surface material domain and resolution (Docs/Architecture/Card_Surface_Materials.md).

The baseline is the Widget Theme style value ``widgets.global.surface_material``; every
ordinary card and the Context Menu inherit it, and an explicit per-widget
``widgets.<id>.surface_material`` (anything but ``inherit``) beats it. Widget Theme
files stay colour-only. Resolution happens once per style build, never per frame.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from PySide6.QtGui import QColor

NORMAL = "normal"
INHERIT = "inherit"
# Canonical order: the Settings combo lists them so; Normal is the default.
SURFACE_MATERIALS: tuple[str, ...] = ("normal", "acrylic", "glass", "frosted", "mica", "smoked")
SURFACE_MATERIAL_LABELS: dict[str, str] = {
    "normal": "Normal",
    "acrylic": "Acrylic",
    "glass": "Glass",
    "frosted": "Frosted",
    "mica": "Mica",
    "smoked": "Smoked",
}

# Continuous backdrop refresh spacing while a transition runs, per material (seconds of
# render-thread time between refreshes; frames in between reuse the last backdrop). Chosen
# by the measured worst-case staleness inside the cards (one full interval old, p99 of the
# 8-bit difference, six transitions incl. 3D, tools/surface_material_capture.py --cadence):
# at most ~12 levels. Glass (light blur) needs >=120 Hz, so it refreshes on every rendered
# frame (never stale); Acrylic/Frosted/Smoked hold <=12 at 60 Hz; Mica <=9 at 20 Hz.
# Docs/Architecture/Card_Surface_Materials.md section 6.
TRANSITION_REFRESH_INTERVAL_S: dict[str, float] = {
    "glass": 0.0,
    "acrylic": 1.0 / 60.0,
    "frosted": 1.0 / 60.0,
    "smoked": 1.0 / 60.0,
    "mica": 1.0 / 20.0,
}


def normalize_surface_material(value: object, *, allow_inherit: bool = False) -> str | None:
    """The canonical material id for ``value`` (case-insensitive), or None if unknown."""

    text = str(value or "").strip().lower()
    if allow_inherit and text == INHERIT:
        return INHERIT
    return text if text in SURFACE_MATERIALS else None


def resolve_global_surface_material(widgets_config: Mapping[str, object] | None) -> str:
    """The Widget Theme baseline material (Normal when absent or unknown)."""

    values = widgets_config.get("global", {}) if isinstance(widgets_config, Mapping) else {}
    if not isinstance(values, Mapping):
        return NORMAL
    return normalize_surface_material(values.get("surface_material")) or NORMAL


def resolve_surface_material(widgets_config: Mapping[str, object] | None, widget_id: str) -> str:
    """``widget_id``'s material: its own explicit value, else the baseline."""

    if isinstance(widgets_config, Mapping):
        values = widgets_config.get(str(widget_id), {})
        if isinstance(values, Mapping):
            own = normalize_surface_material(values.get("surface_material"), allow_inherit=True)
            if own is not None and own != INHERIT:
                return own
    return resolve_global_surface_material(widgets_config)


def transition_refresh_interval_s(materials) -> float:
    """The backdrop refresh spacing a set of present materials needs (the smallest)."""

    intervals = [TRANSITION_REFRESH_INTERVAL_S[m] for m in materials if m in TRANSITION_REFRESH_INTERVAL_S]
    return min(intervals) if intervals else TRANSITION_REFRESH_INTERVAL_S["acrylic"]


def surface_text_color() -> QColor:
    """The active Widget Theme's card text colour: the legibility layer's reference."""

    from ui.settings_theme_spec import Rgba
    from ui.widget_theme_active import get_active_widget_theme
    from ui.widget_visual_roles import resolve_widget_visual_color

    rgba = resolve_widget_visual_color(get_active_widget_theme(), "card.text",
                                       fallback=Rgba(255, 255, 255, 230)).color.as_tuple()
    return QColor(*rgba)


def with_surface_material(style, widgets_config: Mapping[str, object] | None, widget_id: str):
    """``style`` (a family presentation style with ``card_style``) carrying ``widget_id``'s material."""

    card_style = getattr(style, "card_style", None)
    if card_style is None:
        return style
    material = resolve_surface_material(widgets_config, widget_id)
    if material == NORMAL and card_style.surface_material == NORMAL:
        return style
    updated = replace(card_style, surface_material=material,
                      surface_text_color=surface_text_color() if material != NORMAL
                      else card_style.surface_text_color)
    return replace(style, card_style=updated)


__all__ = [
    "INHERIT", "NORMAL", "SURFACE_MATERIALS", "SURFACE_MATERIAL_LABELS",
    "TRANSITION_REFRESH_INTERVAL_S", "normalize_surface_material", "resolve_global_surface_material",
    "resolve_surface_material", "surface_text_color", "transition_refresh_interval_s",
    "with_surface_material",
]
