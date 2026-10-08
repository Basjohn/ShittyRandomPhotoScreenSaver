"""Settle 3D view pose without granting visualizer presets geometry authority.

Turn/tilt remain canonical, mode-specific *live* settings. Curated/Custom
presets may change appearance and response but never select or overwrite a
view pose. A finished gesture makes one settings commit; no per-frame writes.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from core.settings.visualizer_mode_registry import (
    coerce_visualizer_mode_id, get_visualizer_view_pose_keys,
)


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
