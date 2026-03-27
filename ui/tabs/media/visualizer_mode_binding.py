"""Shared WidgetsTab bindings for visualizer mode and preset UI contract."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_default_visualizer_mode_id,
    iter_visualizer_mode_descriptors,
)
from core.settings.visualizer_presets import (
    get_missing_preset_fallback_index,
    resolve_preset_index_from_mapping,
)


def populate_visualizer_mode_combo(combo) -> None:
    """Populate the visualizer mode combo from the shared mode registry."""
    for descriptor in iter_visualizer_mode_descriptors():
        combo.addItem(descriptor.display_name, descriptor.mode_id)


def get_visualizer_mode_fallback() -> str:
    return get_default_visualizer_mode_id()


def resolve_visualizer_mode_build_default(tab) -> str:
    """Resolve the mode used when the combo is first constructed."""
    fallback = get_visualizer_mode_fallback()
    if not hasattr(tab, "_default_str"):
        return fallback
    mode_id = tab._default_str("spotify_visualizer", "mode", fallback)
    return mode_id if isinstance(mode_id, str) and mode_id else fallback


def initialize_visualizer_mode_combo(tab) -> None:
    """Populate the visualizer mode combo and apply the canonical build default."""
    combo = tab.vis_mode_combo
    populate_visualizer_mode_combo(combo)
    mode_idx = combo.findData(resolve_visualizer_mode_build_default(tab))
    if mode_idx >= 0:
        combo.setCurrentIndex(mode_idx)


def load_visualizer_mode_selection(tab, spotify_vis_config: Mapping[str, Any] | None) -> None:
    """Load the active visualizer mode from the config mapping into the combo."""
    fallback = get_visualizer_mode_fallback()
    if isinstance(spotify_vis_config, Mapping) and hasattr(tab, "_config_str"):
        mode_id = tab._config_str("spotify_visualizer", spotify_vis_config, "mode", fallback)
    else:
        mode_id = fallback
    mode_idx = tab.vis_mode_combo.findData(mode_id)
    if mode_idx < 0:
        mode_idx = tab.vis_mode_combo.findData(fallback)
    if mode_idx >= 0:
        tab.vis_mode_combo.setCurrentIndex(mode_idx)


def collect_visualizer_mode_selection(tab) -> str:
    """Return the active visualizer mode from the combo using the shared fallback."""
    if not hasattr(tab, "vis_mode_combo"):
        return get_visualizer_mode_fallback()
    current = tab.vis_mode_combo.currentData()
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
    """Write per-mode preset slider selections into the config mapping."""
    for descriptor in iter_visualizer_mode_descriptors():
        slider = getattr(tab, descriptor.preset_slider_attr, None)
        spotify_vis_config[descriptor.preset_key] = (
            slider.preset_index()
            if slider is not None
            else get_missing_preset_fallback_index(descriptor.mode_id)
        )


def load_visualizer_rainbow_state(tab, spotify_vis_config: Mapping[str, Any] | None) -> None:
    """Load per-mode rainbow state from config into the active visualizer controls."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}
    global_enabled = False
    global_speed = 50
    if hasattr(tab, "_config_bool"):
        global_enabled = tab._config_bool("spotify_visualizer", config, "rainbow_enabled", False)
    if hasattr(tab, "_config_float"):
        global_speed = int(tab._config_float("spotify_visualizer", config, "rainbow_speed", 0.5) * 100)

    rainbow_cache = {}
    for mode_id in VISUALIZER_MODE_IDS:
        mode_enabled = config.get(f"{mode_id}_rainbow_enabled", None)
        mode_speed = config.get(f"{mode_id}_rainbow_speed", None)
        enabled = bool(mode_enabled) if mode_enabled is not None else global_enabled
        speed = int(float(mode_speed) * 100) if mode_speed is not None else global_speed
        rainbow_cache[mode_id] = (enabled, max(1, min(100, speed)))

    tab._rainbow_per_mode = rainbow_cache
    current_mode = collect_visualizer_mode_selection(tab)
    current_enabled, current_speed = rainbow_cache.get(current_mode, (False, 50))

    if hasattr(tab, "rainbow_enabled"):
        tab.rainbow_enabled.setChecked(current_enabled)
    if hasattr(tab, "rainbow_speed_slider"):
        tab.rainbow_speed_slider.setValue(current_speed)
    if hasattr(tab, "rainbow_speed_label"):
        tab.rainbow_speed_label.setText(f"{current_speed / 100.0:.2f}")
    if hasattr(tab, "_update_rainbow_visibility"):
        tab._update_rainbow_visibility()


def collect_visualizer_rainbow_state(tab, spotify_vis_config: dict[str, Any]) -> None:
    """Write per-mode rainbow state from the active controls into the config mapping."""
    rainbow_cache = dict(getattr(tab, "_rainbow_per_mode", {}))
    current_mode = collect_visualizer_mode_selection(tab)
    if hasattr(tab, "rainbow_enabled") and hasattr(tab, "rainbow_speed_slider"):
        rainbow_cache[current_mode] = (
            tab.rainbow_enabled.isChecked(),
            tab.rainbow_speed_slider.value(),
        )
    tab._rainbow_per_mode = rainbow_cache

    for mode_id in VISUALIZER_MODE_IDS:
        enabled, speed = rainbow_cache.get(mode_id, (False, 50))
        spotify_vis_config[f"{mode_id}_rainbow_enabled"] = enabled
        spotify_vis_config[f"{mode_id}_rainbow_speed"] = speed / 100.0
