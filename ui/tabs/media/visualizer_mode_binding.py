"""Shared Settings bindings for visualizer mode and preset UI contract."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_default_visualizer_mode_id,
    get_owned_mode_setting_keys,
    iter_visualizer_mode_descriptors,
    mode_has_rainbow_controls,
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


def load_visualizer_rainbow_state(tab, spotify_vis_config: Mapping[str, Any] | None) -> None:
    """Load per-mode rainbow state from config into the active visualizer controls."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}
    global_enabled = tab._config_bool("spotify_visualizer", config, "rainbow_enabled")
    global_speed = int(round(
        tab._config_float("spotify_visualizer", config, "rainbow_speed") * 100.0
    ))

    rainbow_cache = {}
    for mode_id in VISUALIZER_MODE_IDS:
        # Capability metadata only decides whether this mode participates in
        # the shared Rainbow product surface. Persisted values/defaults remain
        # exclusively owned by the canonical Settings defaults/schema.
        rainbow_keys = get_owned_mode_setting_keys(mode_id, "rainbow")
        if not rainbow_keys:
            continue
        enabled_key = rainbow_keys["rainbow_enabled"]
        speed_key = rainbow_keys["rainbow_speed"]
        mode_enabled = config.get(enabled_key, None)
        mode_speed = config.get(speed_key, None)
        enabled = bool(mode_enabled) if mode_enabled is not None else global_enabled
        if mode_speed is None:
            speed = global_speed
        else:
            try:
                speed = int(round(float(mode_speed) * 100.0))
            except (TypeError, ValueError, OverflowError):
                speed = int(round(tab._default_float("spotify_visualizer", speed_key) * 100.0))
        rainbow_cache[mode_id] = (enabled, max(1, min(100, speed)))

    tab._rainbow_per_mode = rainbow_cache
    current_mode = collect_visualizer_mode_selection(tab)
    if not mode_has_rainbow_controls(current_mode):
        # An experimental mode may intentionally have no Rainbow persisted
        # keys. Do not invent defaults or overwrite the shared presentation
        # controls while that mode is selected; visibility owns hiding them.
        if hasattr(tab, "_update_rainbow_visibility"):
            tab._update_rainbow_visibility()
        return

    current_rainbow_keys = get_owned_mode_setting_keys(current_mode, "rainbow")
    current_enabled, current_speed = rainbow_cache.get(
        current_mode,
        (
            tab._default_bool("spotify_visualizer", current_rainbow_keys["rainbow_enabled"]),
            int(round(tab._default_float("spotify_visualizer", current_rainbow_keys["rainbow_speed"]) * 100.0)),
        ),
    )

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
    rainbow_cache = {
        mode_id: value
        for mode_id, value in dict(getattr(tab, "_rainbow_per_mode", {})).items()
        if mode_has_rainbow_controls(mode_id)
    }
    current_mode = collect_visualizer_mode_selection(tab)
    if (
        mode_has_rainbow_controls(current_mode)
        and hasattr(tab, "rainbow_enabled")
        and hasattr(tab, "rainbow_speed_slider")
    ):
        rainbow_cache[current_mode] = (
            tab.rainbow_enabled.isChecked(),
            tab.rainbow_speed_slider.value(),
        )
    tab._rainbow_per_mode = rainbow_cache

    for mode_id in VISUALIZER_MODE_IDS:
        rainbow_keys = get_owned_mode_setting_keys(mode_id, "rainbow")
        if not rainbow_keys:
            continue
        enabled_key = rainbow_keys["rainbow_enabled"]
        speed_key = rainbow_keys["rainbow_speed"]
        default_enabled = tab._default_bool("spotify_visualizer", enabled_key)
        default_speed = int(round(
            tab._default_float("spotify_visualizer", speed_key) * 100.0
        ))
        enabled, speed = rainbow_cache.get(mode_id, (default_enabled, default_speed))
        spotify_vis_config[enabled_key] = enabled
        spotify_vis_config[speed_key] = speed / 100.0
