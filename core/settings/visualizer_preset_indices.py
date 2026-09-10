"""Shared visualizer preset-index resolution helpers.

Missing/invalid persisted selection repairs to the canonical per-mode selection.
The user-authored preset registry owns runtime slot availability; authored file
slot numbers may be sparse and are compacted for the slider. There is no generic
"first preset" product-default authority.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Dict

from core.settings.default_contract import require_canonical_default
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
    return module.get_custom_preset_index(mode)


def get_missing_preset_fallback_index(mode: str) -> int:
    """Resolve missing persisted state from canonical per-mode authority."""
    mode = coerce_visualizer_mode_id(mode)
    key = get_preset_key(mode)
    canonical = int(
        require_canonical_default(f"widgets.spotify_visualizer.{key}")
    )
    custom_idx = get_custom_preset_index(mode)
    if custom_idx <= 0:
        raise RuntimeError(f"visualizer mode {mode!r} has no authored presets")
    # Product defaults select authored content, never the user-owned trailing
    # Custom slot. Runtime positions are compact even when authored file slot
    # numbers are sparse.
    return max(0, min(custom_idx - 1, canonical))


def get_default_preset_index(mode: str) -> int:
    """Compatibility alias for canonical missing-preset repair."""
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
        return fallback

    custom_idx = get_custom_preset_index(mode)
    if idx < 0 or idx > custom_idx:
        return fallback
    return idx


def resolve_all_preset_indices_from_mapping(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, int]:
    return {
        get_preset_key(mode): resolve_preset_index_from_mapping(mode, data, prefix=prefix)
        for mode in VISUALIZER_MODE_IDS
    }


def resolve_all_preset_indices_from_getter(
    read_value: Callable[[str, Any], Any],
    *,
    prefix: str = "widgets.spotify_visualizer",
) -> Dict[str, int]:
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
