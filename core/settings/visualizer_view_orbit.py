"""Settle 3D view pose without granting visualizer presets geometry authority.

Orbit and optional internal pan/scale remain canonical, mode-specific live settings.
Framed curated presets may supply a validated starting view on explicit activation. Only this
live-view owner applies/persists poses; ordinary reloads preserve user adjustments.
A finished gesture makes one settings commit; no per-frame writes.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping
import math

from core.settings.visualizer_mode_registry import (
    coerce_visualizer_mode_id, get_visualizer_view_pose_keys, get_visualizer_mode_descriptor,
)


def validate_visualizer_starting_view(mode: str, values: Mapping[str, Any]) -> Dict[str, float]:
    """Validate optional preset metadata using the live owner's exact pose schema.

    Legacy pose leaves inside artwork remain inert. This complete metadata record
    is opt-in for framed modes only; malformed records fail loudly at preset input.
    Composition admission remains with the existing presentation/configure path.
    """
    from core.settings.visualizer_mode_settings import require_mode_settings
    if not get_visualizer_mode_descriptor(mode).scene_transform_settings:
        raise ValueError(f"{mode} does not support a framed starting view")
    keys = get_visualizer_view_pose_keys(mode)
    if not isinstance(values, Mapping) or set(values) != set(keys):
        raise ValueError(f"{mode} starting_view requires exactly {keys}")
    spec = require_mode_settings(mode)
    result = {}
    for key in keys:
        raw = values[key]
        if type(raw) not in (int, float):
            raise ValueError(f"{key} starting view must be a finite number")
        try:
            value = float(raw)
        except OverflowError:
            raise ValueError(f"{key} starting view must be a finite number") from None
        if not math.isfinite(value):
            raise ValueError(f"{key} starting view must be a finite number")
        if spec.control(key).admit(value, value) != value:
            raise ValueError(f"{key} starting view is outside its canonical range")
        result[key] = value
    return result


def resolve_visualizer_view_orbit(
    visualizer_config: Mapping[str, Any],
    custom_presets: Mapping[str, Any],
    *,
    mode: str,
    values: Mapping[str, float],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Update only the requested mode's persisted view keys, leave all presets intact."""
    if not isinstance(visualizer_config, Mapping):
        raise TypeError("visualizer_config must be a mapping")
    if not isinstance(custom_presets, Mapping):
        raise TypeError("custom_presets must be a mapping")
    mode_key = coerce_visualizer_mode_id(str(mode))
    admitted = frozenset(get_visualizer_view_pose_keys(mode_key))
    if not admitted or set(values) != admitted:
        raise ValueError(f"Unexpected view pose keys for {mode_key}: {set(values) ^ admitted}")
    section = dict(visualizer_config)
    for key in admitted:
        section[key] = float(values[key])
    # Custom cache is a separate authority, passed back unchanged. Never
    # normalize/rebuild it simply because someone moved the camera.
    return section, dict(custom_presets)


def starting_camera_pose(mode: str, preset_index: int) -> Dict[str, float]:
    """Read one curated preset's authored starting view, or canonical camera home.

    Custom has no immutable starting pose and resets to mode defaults. Nothing is
    written to the curated preset nor to the Custom snapshot by this lookup.
    """
    from core.settings.default_contract import require_canonical_default
    from core.settings.visualizer_presets import get_custom_preset_index, get_presets
    keys = get_visualizer_view_pose_keys(mode)
    values = None
    presets = get_presets(mode)
    if 0 <= preset_index < len(presets) and preset_index != get_custom_preset_index(mode):
        values = presets[preset_index].starting_view
    if values is None:
        values = {key: require_canonical_default(f"widgets.spotify_visualizer.{key}") for key in keys}
    return validate_visualizer_starting_view(mode, values)
