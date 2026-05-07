"""Canonical normalization helpers for visualizer section mappings."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    coerce_visualizer_mode_id,
    get_setting_prefixes,
)
from core.settings.visualizer_settings_contract import (
    migrate_legacy_global_technical_keys,
    migrate_legacy_global_visual_keys,
)

_PREFIX = "widgets.spotify_visualizer"
_TECHNICAL_GLOBAL_KEYS = frozenset(
    {
        "adaptive_sensitivity",
        "agc_strength",
        "audio_block_size",
        "bar_count",
        "dynamic_floor",
        "dynamic_range_enabled",
        "input_gain",
        "kick_lane_gain",
        "manual_floor",
        "sensitivity",
        "transient_clamp",
        "transient_pulse_gain",
    }
)
_RETIRED_AUTHORED_SHARED_VISUAL_KEYS = frozenset(
    {
        "bar_fill_color",
        "bar_border_color",
        "bar_border_opacity",
    }
)
_RETIRED_AUTHORED_TECH_SUFFIXES = frozenset({"energy_boost", "use_raw_energy"})
_RETIRED_AUTHORED_GLOBAL_VISUAL_KEYS = frozenset(
    {
        "ghosting_enabled",
        "ghost_alpha",
        "ghost_decay",
    }
)
_BLOB_SHAPER_KEYS = frozenset(
    {
        "blob_shaper_enabled",
        "blob_shape_base_nodes",
        "blob_shape_reaction_nodes",
        "blob_shape_energy_nodes",
        "blob_shaper_base_strength",
        "blob_shaper_react_strength",
        "blob_shaper_idle_motion",
        "blob_shaper_audio_motion",
        "blob_topology",
        "blob_ring_thickness",
    }
)


def _forward_migrate_alias_keys(
    data: Mapping[str, Any],
    *,
    prefix: str,
) -> Dict[str, Any]:
    """Rewrite retired visualizer aliases to their canonical modern keys.

    This is the forward-only migration seam for persisted/live settings.
    We upgrade the mapping once here and keep leaf/runtime call sites free of
    legacy alias reads.
    """
    migrated = dict(data)

    alias_pairs = (
        ("osc_sensitivity", "osc_line_amplitude"),
    )

    for alias_key, canonical_key in alias_pairs:
        plain_alias_present = alias_key in migrated
        dotted_alias_key = f"{prefix}.{alias_key}"
        dotted_alias_present = dotted_alias_key in migrated
        if not plain_alias_present and not dotted_alias_present:
            continue

        plain_canonical_key = canonical_key
        dotted_canonical_key = f"{prefix}.{canonical_key}"
        alias_value = (
            migrated.get(alias_key)
            if plain_alias_present
            else migrated.get(dotted_alias_key)
        )

        if plain_canonical_key not in migrated and dotted_canonical_key not in migrated:
            if plain_alias_present:
                migrated[plain_canonical_key] = alias_value
            else:
                migrated[dotted_canonical_key] = alias_value

        migrated.pop(alias_key, None)
        migrated.pop(dotted_alias_key, None)

    return migrated


def _lookup_scoped_value(
    data: Mapping[str, Any],
    key: str,
    *,
    prefix: str,
) -> Any:
    if key in data:
        return data.get(key)
    dotted = f"{prefix}.{key}"
    if dotted in data:
        return data.get(dotted)
    return None


def _resolve_per_mode_rainbow_mapping(
    data: Mapping[str, Any],
    normalized: Dict[str, Any],
    *,
    prefix: str,
) -> Dict[str, Any]:
    active_mode = str(normalized.get("mode", "bubble"))
    global_enabled = bool(normalized.get("rainbow_enabled", False))
    global_speed = float(normalized.get("rainbow_speed", 0.5))

    for mode in VISUALIZER_MODE_IDS:
        enabled_value = None
        speed_value = None
        for setting_prefix in get_setting_prefixes(mode):
            enabled_value = _lookup_scoped_value(data, f"{setting_prefix}rainbow_enabled", prefix=prefix)
            if enabled_value is not None:
                break
        for setting_prefix in get_setting_prefixes(mode):
            speed_value = _lookup_scoped_value(data, f"{setting_prefix}rainbow_speed", prefix=prefix)
            if speed_value is not None:
                break

        if enabled_value is None:
            enabled_value = global_enabled if mode == active_mode else False
        if speed_value is None:
            speed_value = global_speed if mode == active_mode else 0.5

        normalized[f"{mode}_rainbow_enabled"] = bool(enabled_value)
        try:
            normalized[f"{mode}_rainbow_speed"] = float(speed_value)
        except (TypeError, ValueError):
            normalized[f"{mode}_rainbow_speed"] = 0.5

    return normalized


def _strip_inactive_blob_shaper_payload(normalized: Dict[str, Any]) -> Dict[str, Any]:
    """Drop Blob Shaper-only payload when shaped Blob is not enabled.

    This keeps canonical snapshots/presets free of shaped-mode baggage so
    non-shaped Blob cannot silently ferry authoring-only keys through
    Move-to-Custom, custom backups, preset repair, or curated payload exports.
    """
    if str(normalized.get("mode", "")).strip().lower() != "blob":
        return normalized
    if bool(normalized.get("blob_shaper_enabled", False)):
        return normalized

    cleaned = dict(normalized)
    for key in _BLOB_SHAPER_KEYS:
        cleaned.pop(key, None)
    return cleaned


def normalize_visualizer_section_mapping(
    data: Mapping[str, Any] | None,
    *,
    prefix: str = _PREFIX,
    apply_preset_overlay: bool = False,
    resolve_preset_indices: bool = True,
) -> Dict[str, Any]:
    """Return a canonical spotify_visualizer section mapping.

    Unknown/obsolete keys are intentionally dropped so reset/import/export and
    repair-style flows all converge on the same persisted schema.
    """
    if not isinstance(data, Mapping):
        return {}

    migrated = _forward_migrate_alias_keys(data, prefix=prefix)
    migrated = migrate_legacy_global_technical_keys(migrated, prefix=prefix)
    migrated = migrate_legacy_global_visual_keys(migrated, prefix=prefix)

    model = SpotifyVisualizerSettings.from_mapping(
        migrated,
        prefix=prefix,
        apply_preset_overlay=apply_preset_overlay,
        resolve_preset_indices=resolve_preset_indices,
    )
    dotted = model.to_dict(prefix=prefix)
    prefix_with_sep = f"{prefix}."
    normalized: Dict[str, Any] = {}
    for key, value in dotted.items():
        if not key.startswith(prefix_with_sep):
            continue
        normalized[key[len(prefix_with_sep):]] = deepcopy(value)
    normalized = _resolve_per_mode_rainbow_mapping(migrated, normalized, prefix=prefix)
    return _strip_inactive_blob_shaper_payload(normalized)


def normalize_visualizer_mode_payload(
    mode: str,
    data: Mapping[str, Any] | None,
    *,
    prefix: str = _PREFIX,
) -> Dict[str, Any]:
    """Return a canonical mode-scoped payload for presets/custom snapshots.

    This keeps shared visual keys (colors/monitor/ghost settings) while
    promoting technical controls to mode-owned keys and dropping legacy shared
    technical duplicates from exported payloads.
    """
    normalized = normalize_visualizer_section_mapping(
        data,
        prefix=prefix,
        apply_preset_overlay=False,
        resolve_preset_indices=False,
    )
    if not normalized:
        return {}

    from core.settings.visualizer_presets import _filter_settings_for_mode

    canonical_mode = coerce_visualizer_mode_id(mode)
    filtered = _filter_settings_for_mode(canonical_mode, normalized)
    for key in _TECHNICAL_GLOBAL_KEYS:
        filtered.pop(key, None)
    for key in _RETIRED_AUTHORED_SHARED_VISUAL_KEYS:
        filtered.pop(key, None)
    for key in _RETIRED_AUTHORED_GLOBAL_VISUAL_KEYS:
        filtered.pop(key, None)
    for retired_suffix in _RETIRED_AUTHORED_TECH_SUFFIXES:
        filtered.pop(retired_suffix, None)
        filtered.pop(f"{canonical_mode}_{retired_suffix}", None)
    filtered["mode"] = canonical_mode
    return filtered
