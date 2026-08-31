"""Detached H8 resolver for retained runtime visualizer preset cycling."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, Mapping

from core.settings.visualizer_mode_registry import (
    coerce_visualizer_mode_id,
    get_preset_key,
    is_mode_active,
)
from core.settings.visualizer_preset_indices import resolve_preset_index_from_mapping
from core.settings.visualizer_presets import (
    apply_preset_to_config,
    build_normalized_custom_snapshot,
    get_custom_preset_index,
    get_preset_count,
    normalize_visualizer_custom_snapshot_cache,
    restore_visualizer_snapshot,
)
from core.settings.visualizer_settings_snapshot import (
    normalize_visualizer_section_mapping,
)


@dataclass(frozen=True)
class VisualizerRuntimePresetCycleTarget:
    """One detached same-mode target plus its companion Custom-cache state."""

    mode: str
    source_index: int
    target_index: int
    visualizer_config: Dict[str, Any]
    custom_presets: Dict[str, Dict[str, Any]]
    custom_presets_changed: bool


def resolve_next_visualizer_runtime_preset(
    visualizer_config: Mapping[str, Any],
    custom_presets: Mapping[str, Any],
    *,
    mode: str | None = None,
) -> VisualizerRuntimePresetCycleTarget:
    """Resolve exactly one forward preset step without mutating either input.

    A missing per-mode Custom snapshot is seeded from the persisted raw section
    before any curated replacement.  This makes first use deterministic while
    preserving a previously authored Custom snapshot whenever one exists.
    """

    if not isinstance(visualizer_config, Mapping):
        raise TypeError("visualizer_config must be a mapping")
    if not isinstance(custom_presets, Mapping):
        raise TypeError("custom_presets must be a mapping")

    requested = str(mode or visualizer_config.get("mode") or "").strip().lower()
    mode_key = coerce_visualizer_mode_id(requested)
    if mode_key != requested or not is_mode_active(mode_key):
        raise ValueError(f"inactive or invalid visualizer mode: {requested!r}")

    preset_count = get_preset_count(mode_key)
    if preset_count < 2:
        raise ValueError(f"visualizer mode has no cyclable presets: {mode_key}")

    source = deepcopy(dict(visualizer_config))
    source["mode"] = mode_key
    source_index = resolve_preset_index_from_mapping(mode_key, source)
    target_index = (source_index + 1) % preset_count
    custom_index = get_custom_preset_index(mode_key)

    cache = normalize_visualizer_custom_snapshot_cache(custom_presets)
    cached_payload = cache.get(mode_key)
    if source_index == custom_index:
        cache[mode_key] = build_normalized_custom_snapshot(mode_key, source)
    elif not isinstance(cached_payload, Mapping):
        # The raw section is the only persisted pre-mutation authority on a
        # profile that has never materialized this mode's Custom cache.
        cache[mode_key] = build_normalized_custom_snapshot(mode_key, source)

    candidate = deepcopy(source)
    if target_index == custom_index:
        payload = cache.get(mode_key)
        if not isinstance(payload, Mapping):
            raise ValueError(f"visualizer Custom snapshot is unavailable: {mode_key}")
        restore_visualizer_snapshot(mode_key, candidate, payload)
    else:
        applied = apply_preset_to_config(
            mode_key,
            target_index,
            deepcopy(candidate),
        )
        restore_visualizer_snapshot(mode_key, candidate, applied)

    candidate["mode"] = mode_key
    candidate[get_preset_key(mode_key)] = target_index
    candidate = normalize_visualizer_section_mapping(
        candidate,
        apply_preset_overlay=False,
        resolve_preset_indices=False,
    )
    candidate["mode"] = mode_key
    candidate[get_preset_key(mode_key)] = target_index

    return VisualizerRuntimePresetCycleTarget(
        mode=mode_key,
        source_index=source_index,
        target_index=target_index,
        visualizer_config=candidate,
        custom_presets=cache,
        custom_presets_changed=(dict(custom_presets) != cache),
    )


__all__ = [
    "VisualizerRuntimePresetCycleTarget",
    "resolve_next_visualizer_runtime_preset",
]
