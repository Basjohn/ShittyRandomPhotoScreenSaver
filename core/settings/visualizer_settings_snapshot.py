"""Canonical normalization helpers for visualizer section mappings."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from core.logging.logger import get_logger
from core.settings.default_contract import require_canonical_default
from core.settings.models import SpotifyVisualizerSettings
from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    coerce_visualizer_mode_id,
    get_setting_prefixes,
    get_owned_mode_setting_keys,
    mode_has_rainbow_controls,
    migrate_legacy_enabled_modes_to_activation,
)
from core.settings.visualizer_retired_modes import strip_retired_visualizer_settings
from core.settings.visualizer_settings_contract import (
    migrate_legacy_global_visual_keys,
    migrate_legacy_sphere_finish_keys,
    migrate_legacy_sphere_control_keys,
    strip_legacy_global_technical_keys,
)

_PREFIX = "widgets.spotify_visualizer"
logger = get_logger(__name__)
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

_RETIRED_GROWTH_KEYS = frozenset(
    {
        "spectrum_growth",
        "osc_growth",
        "sine_wave_growth",
        "bubble_growth",
        "devcurve_growth",
    }
)
_RETIRED_AUTHORED_GLOBAL_VISUAL_KEYS = frozenset(
    {
        "ghosting_enabled",
        "ghost_alpha",
        "ghost_decay",
    }
)

def migrate_legacy_visualizer_mode_activation_schema(
    data: Mapping[str, Any],
    *,
    prefix: str = _PREFIX,
) -> Dict[str, Any]:
    """Forward-migrate retired ``enabled_modes`` into ``mode_activation``.

    This is the *only* compatibility reader for the retired persisted list. It
    removes the legacy key immediately. When old state is actually relied upon
    to construct current activation, emit a warning so field/test feedback tells
    us whether the temporary seam can be retired safely.
    """

    migrated = dict(data)
    legacy_plain = "enabled_modes"
    legacy_dotted = f"{prefix}.enabled_modes"
    current_plain = "mode_activation"
    current_dotted = f"{prefix}.mode_activation"
    legacy_present = legacy_plain in migrated or legacy_dotted in migrated
    if not legacy_present:
        return migrated

    current_present = current_plain in migrated or current_dotted in migrated
    if not current_present:
        legacy_value = (
            migrated.get(legacy_plain)
            if legacy_plain in migrated
            else migrated.get(legacy_dotted)
        )
        activation = migrate_legacy_enabled_modes_to_activation(legacy_value)
        if legacy_plain in migrated:
            migrated[current_plain] = activation
        else:
            migrated[current_dotted] = activation
        logger.warning(
            "[VIS_MODE_ACTIVATION][LEGACY] Retired enabled_modes was relied on; "
            "migrated immediately to mode_activation and removed old key"
        )
    else:
        logger.info(
            "[VIS_MODE_ACTIVATION][LEGACY] Dropping redundant enabled_modes because "
            "current mode_activation is already present"
        )

    migrated.pop(legacy_plain, None)
    migrated.pop(legacy_dotted, None)
    return migrated

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
    active_mode = str(normalized["mode"])
    global_enabled = bool(normalized["rainbow_enabled"])
    global_speed = float(normalized["rainbow_speed"])

    for mode in VISUALIZER_MODE_IDS:
        rainbow_keys = get_owned_mode_setting_keys(mode, "rainbow")
        if not rainbow_keys:
            continue
        enabled_key = rainbow_keys["rainbow_enabled"]
        speed_key = rainbow_keys["rainbow_speed"]
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

        enabled_default = require_canonical_default(f"{prefix}.{enabled_key}")
        speed_default = require_canonical_default(f"{prefix}.{speed_key}")
        if enabled_value is None:
            # A legacy shared Rainbow value belonged to the then-active mode;
            # inactive modes inherit their own canonical baseline instead of a
            # hard-coded secondary default.
            enabled_value = global_enabled if mode == active_mode else enabled_default
        if speed_value is None:
            speed_value = global_speed if mode == active_mode else speed_default

        normalized[enabled_key] = bool(enabled_value)
        try:
            normalized[speed_key] = float(speed_value)
        except (TypeError, ValueError):
            normalized[speed_key] = float(speed_default)

    return normalized


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

    migrated = migrate_legacy_visualizer_mode_activation_schema(data, prefix=prefix)
    migrated = migrate_legacy_sphere_finish_keys(migrated, prefix=prefix)
    migrated = migrate_legacy_sphere_control_keys(migrated, prefix=prefix)
    migrated = strip_retired_visualizer_settings(migrated, prefix=prefix)
    # Per-mode card-height growth was pre-Quick geometry state. The current
    # retained geometry contract is viewport/aspect driven; strip shipped
    # growth leaves once here instead of teaching every consumer about them.
    migrated = dict(migrated)
    for retired_key in _RETIRED_GROWTH_KEYS:
        migrated.pop(retired_key, None)
        migrated.pop(f"{prefix}.{retired_key}", None)
    migrated = _forward_migrate_alias_keys(migrated, prefix=prefix)
    migrated = strip_legacy_global_technical_keys(migrated, prefix=prefix)
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
    return strip_retired_visualizer_settings(normalized, prefix=prefix)


def normalize_visualizer_mode_payload(
    mode: str,
    data: Mapping[str, Any] | None,
    *,
    prefix: str = _PREFIX,
) -> Dict[str, Any]:
    """Return a canonical mode-scoped payload for presets/custom snapshots.

    This keeps only mode-owned authored visual and technical controls. Widget
    admission, routing, and outer geometry stay in the live section and are not
    preset/Custom payload state.
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
