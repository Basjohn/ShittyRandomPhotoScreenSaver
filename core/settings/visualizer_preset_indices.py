"""Shared visualizer preset-index resolution helpers.

These helpers are intentionally isolated from ``visualizer_presets.py`` so the
settings model layer can resolve preset indices without importing the full
preset-loading module at import time. That keeps the preset registry available
to runtime callers while letting normalization utilities import the settings
model without triggering cycles.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Dict

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    coerce_visualizer_mode_id,
    get_preset_key,
)


def _get_visualizer_presets_module():
    from core.settings import visualizer_presets as _visualizer_presets

    return _visualizer_presets


def get_custom_preset_index(mode: str) -> int:
    """Return the trailing Custom slot index for *mode*."""
    module = _get_visualizer_presets_module()
    if hasattr(module, "get_custom_preset_index"):
        return module.get_custom_preset_index(mode)
    return 3


def get_missing_preset_fallback_index(mode: str) -> int:
    """Return the first available non-custom preset slot for *mode*."""
    module = _get_visualizer_presets_module()
    if not hasattr(module, "get_presets"):
        return 0
    presets = module.get_presets(mode)
    for idx, preset in enumerate(presets):
        if not getattr(preset, "is_custom", False):
            return idx
    return max(0, get_custom_preset_index(mode))


def get_default_preset_index(mode: str) -> int:
    """Backward-compatible alias for missing-preset fallback resolution."""
    return get_missing_preset_fallback_index(mode)


def resolve_preset_index_from_mapping(
    mode: str,
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> int:
    """Resolve a mode's preset index from a sparse mapping."""
    mode = coerce_visualizer_mode_id(mode)
    fallback = get_missing_preset_fallback_index(mode)
    if not isinstance(data, Mapping):
        return fallback

    key = get_preset_key(mode)
    raw = data.get(key, data.get(f"{prefix}.{key}", fallback))
    try:
        idx = int(raw)
    except (TypeError, ValueError):
        idx = fallback

    custom_idx = get_custom_preset_index(mode)
    return max(0, min(custom_idx, idx))


def resolve_all_preset_indices_from_mapping(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, int]:
    """Resolve every visualizer mode's preset index from a sparse mapping."""
    return {
        get_preset_key(mode): resolve_preset_index_from_mapping(mode, data, prefix=prefix)
        for mode in VISUALIZER_MODE_IDS
    }


def resolve_all_preset_indices_from_getter(
    read_value: Callable[[str, Any], Any],
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, int]:
    """Resolve every visualizer preset index from a prefixed settings getter."""
    return resolve_all_preset_indices_from_mapping(
        {
            f"{prefix}.{get_preset_key(mode)}": read_value(
                f"{prefix}.{get_preset_key(mode)}",
                get_missing_preset_fallback_index(mode),
            )
            for mode in VISUALIZER_MODE_IDS
        },
        prefix=prefix,
    )
