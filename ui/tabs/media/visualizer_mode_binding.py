"""Shared Settings bindings for visualizer mode and preset UI contract."""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_default_visualizer_mode_id,
    iter_visualizer_mode_descriptors,
)
from core.settings.visualizer_presets import (
    resolve_preset_index_from_mapping,
)


def get_visualizer_mode_fallback() -> str:
    return get_default_visualizer_mode_id()


def load_visualizer_mode_selection(tab, spotify_vis_config: Mapping[str, Any] | None) -> None:
    """Load the active visualizer mode into the shared Settings context state.

    V7 mode pills are the presentation; there is no second combo selection
    authority.
    """
    fallback = get_visualizer_mode_fallback()
    if isinstance(spotify_vis_config, Mapping) and hasattr(tab, "_config_str"):
        mode_id = tab._config_str("spotify_visualizer", spotify_vis_config, "mode")
    else:
        mode_id = fallback
    tab._active_visualizer_mode_id = mode_id or fallback


def collect_visualizer_mode_selection(tab) -> str:
    """Return the context-owned active mode using the canonical fallback."""
    getter = getattr(tab, "_get_active_visualizer_mode", None)
    if callable(getter):
        current = getter()
        if current:
            return current
    current = getattr(tab, "_active_visualizer_mode_id", None)
    return current or get_visualizer_mode_fallback()


def load_visualizer_preset_indices(tab, spotify_vis_config: Mapping[str, Any] | None) -> None:
    """Load per-mode preset slider selections from the config mapping."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}
    for descriptor in iter_visualizer_mode_descriptors():
        slider = getattr(tab, descriptor.preset_slider_attr, None)
        if slider is None:
            continue
        slider.set_preset_index(resolve_preset_index_from_mapping(descriptor.mode_id, config))


def collect_visualizer_preset_indices(tab, spotify_vis_config: dict[str, Any]) -> None:
    """Write per-mode preset slider selections into the config mapping.

    Under lazy mode bodies (V5), an absent preset slider means the mode's
    Settings body was never constructed — NOT that its preset setting is missing.
    An unbuilt mode must contribute no replacement preset key: its persisted
    preset index stays authoritative through the save merge. Writing a
    fallback index here would silently reset an unbuilt mode's preset on an
    unrelated save (cf. R-13 cross-mode loss / R-32 lazy-save hydration), so a
    missing slider is skipped rather than defaulted.
    """
    for descriptor in iter_visualizer_mode_descriptors():
        slider = getattr(tab, descriptor.preset_slider_attr, None)
        if slider is None:
            continue
        spotify_vis_config[descriptor.preset_key] = slider.preset_index()


# The page-level shared families (Bar Appearance, Rainbow), stored per owning mode and declared in each mode's spec
# (``visualizer_mode_settings.shared_family_entries``). Every mode is edited in its Studio, which edits these too, so
# the Visualizers page builds no widget for them: this value cache is their only Settings owner.
FAMILY_CACHE_ATTR = "_visualizer_family_lazy_values"


def family_controls(mode_id: str, family: str | None = None) -> tuple:
    """The mode's shared-family spec controls (one family, or both); () for a mode owning none."""
    from core.settings.visualizer_mode_settings import BAR_APPEARANCE_BUCKET, RAINBOW_BUCKET, mode_settings
    spec = mode_settings(mode_id)
    if spec is None:
        return ()
    families = (family,) if family else (BAR_APPEARANCE_BUCKET, RAINBOW_BUCKET)
    return tuple(control for name in families for control in spec.family_controls(name))


def load_visualizer_family_values(tab, spotify_vis_config: Mapping[str, Any] | None) -> None:
    """Hold every owning mode's Bar Appearance and Rainbow values from ``spotify_vis_config`` (canonical defaults
    for missing ones), admitted by their spec controls as the model admits them."""
    from core.settings.visualizer_mode_settings import read_control_value
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}
    cache = getattr(tab, FAMILY_CACHE_ATTR, None)
    if not isinstance(cache, dict):
        cache = {}
        setattr(tab, FAMILY_CACHE_ATTR, cache)
    for mode_id in VISUALIZER_MODE_IDS:
        for control in family_controls(mode_id):
            default = tab._widget_default("spotify_visualizer", control.key)
            cache[control.key] = control.admit(read_control_value(control, config.get, default), default)


def collect_visualizer_family_values(tab, spotify_vis_config: dict[str, Any], current_mode: str) -> None:
    """Write the held family values: every owning mode's Rainbow, and the current mode's Bar Appearance (an
    unselected mode's bar values stay as stored through the save merge). The unprefixed active-mode rainbow
    mirror follows the current mode when it owns Rainbow."""
    from core.settings.visualizer_mode_settings import RAINBOW_BUCKET, BAR_APPEARANCE_BUCKET
    cache = getattr(tab, FAMILY_CACHE_ATTR, None)
    if not isinstance(cache, dict):
        return
    for mode_id in VISUALIZER_MODE_IDS:
        for control in family_controls(mode_id, RAINBOW_BUCKET):
            if control.key in cache:
                spotify_vis_config[control.key] = deepcopy(cache[control.key])
    for control in family_controls(current_mode, BAR_APPEARANCE_BUCKET):
        if control.key in cache:
            spotify_vis_config[control.key] = deepcopy(cache[control.key])
    for control in family_controls(current_mode, RAINBOW_BUCKET):
        suffix = control.key.removeprefix(f"{current_mode}_")
        if suffix in ("rainbow_enabled", "rainbow_speed") and control.key in cache:
            spotify_vis_config[suffix] = deepcopy(cache[control.key])
