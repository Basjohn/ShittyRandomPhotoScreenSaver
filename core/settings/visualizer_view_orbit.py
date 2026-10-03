"""Detached resolver persisting a finished W/A/S/D view orbit.

Orbiting edits the active mode's view, so it is a user edit like one made in Settings:
on Custom the live section simply takes the new values; on a curated preset the mode
moves to Custom holding what was on screen plus the new view, and that becomes the
mode's Custom snapshot (as Settings does when a control is changed on a preset).
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from core.settings.visualizer_mode_registry import coerce_visualizer_mode_id, get_preset_key
from core.settings.visualizer_presets import (
    build_normalized_custom_snapshot,
    get_custom_preset_index,
    normalize_visualizer_custom_snapshot_cache,
    resolve_visualizer_activation_payload,
)


def resolve_visualizer_view_orbit(
    visualizer_config: Mapping[str, Any],
    custom_presets: Mapping[str, Any],
    *,
    mode: str,
    values: Mapping[str, float],
) -> tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]:
    """The visualizer section and Custom cache to persist, without mutating either input."""
    if not isinstance(visualizer_config, Mapping):
        raise TypeError("visualizer_config must be a mapping")
    if not isinstance(custom_presets, Mapping):
        raise TypeError("custom_presets must be a mapping")
    mode_key = coerce_visualizer_mode_id(str(mode))
    activation = resolve_visualizer_activation_payload(visualizer_config, mode=mode_key)
    config = dict(activation.resolved_config)
    # The orbit never changes which mode is shown (it may finish just after a mode change).
    config["mode"] = str(visualizer_config.get("mode") or mode_key)
    config.update({str(key): float(value) for key, value in values.items()})
    cache = normalize_visualizer_custom_snapshot_cache(custom_presets)
    if not activation.is_custom:
        config[get_preset_key(mode_key)] = get_custom_preset_index(mode_key)
        cache[mode_key] = build_normalized_custom_snapshot(mode_key, config)
    return config, cache
