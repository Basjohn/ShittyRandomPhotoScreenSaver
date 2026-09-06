"""SST (Settings Snapshot Transport) import/export logic.

Extracted from settings_manager.py to reduce monolith size.
All functions take the SettingsManager instance as their first argument.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from core.logging.logger import get_logger
from core.steam.credentials import strip_secret_fields as strip_steam_secret_fields
from core.settings.structured_roots import STRUCTURED_SETTINGS_ROOTS
from core.settings.visualizer_presets import (
    normalize_visualizer_custom_snapshot_cache,
)
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager

logger = get_logger(__name__)

SNAPSHOT_VERSION = 1


# Display backend policy is runtime-owned while SRPSS is OpenGL-only. These
# keys may remain canonical product settings, but SST transport must not override
# the active backend contract. Retired refresh keys are rejected at the same
# boundary rather than being duplicated between import and preview.
_SST_NON_IMPORTABLE_KEYS = frozenset({
    "display.refresh_sync",
    "display.refresh_adaptive",
    "display.render_backend_mode",
    "display.hw_accel",
})


def _deep_overlay_mapping(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
    """Recursively overlay mappings without discarding untouched nested siblings."""

    merged: Dict[str, Any] = deepcopy(dict(base))
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_overlay_mapping(existing, value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _coerce_nested_import_mapping(
    mgr: "SettingsManager",
    prefix: str,
    mapping: Mapping[str, Any],
) -> Dict[str, Any]:
    """Coerce nested imported leaves from canonical schema types where known."""

    result: Dict[str, Any] = {}
    for raw_key, value in mapping.items():
        key = str(raw_key)
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, Mapping):
            result[key] = _coerce_nested_import_mapping(mgr, dotted, value)
        else:
            result[key] = mgr._coerce_import_value(dotted, value)
    return result


def _current_store_state(mgr: "SettingsManager") -> Dict[str, Any]:
    return {
        str(key): deepcopy(mgr._settings.value(key))
        for key in mgr._settings.allKeys()
    }


def _project_import_state(
    mgr: "SettingsManager",
    normalized_root: Mapping[str, Any],
    *,
    merge: bool,
) -> Dict[str, Any]:
    """Project SST import into runtime-store shape without mutating the store.

    Import and preview both use this function so their merge, coercion and
    structured-root semantics cannot drift apart. A replace import begins from
    the canonical profile store projection; omitted product values therefore
    reset to canonical defaults rather than forming a sparse shadow schema.
    """

    if merge:
        state = _current_store_state(mgr)
    else:
        from core.settings.defaults import get_flat_defaults

        state = deepcopy(get_flat_defaults(mgr.get_application_name()))
        # A replace import resets product state to canonical defaults, but the
        # Custom visualizer cache is user-authored state and intentionally has
        # no canonical product default. Omission from an SST therefore preserves
        # the existing cache; an explicit SST section still replaces it below.
        if "visualizer_custom_presets" not in normalized_root:
            existing_state = _current_store_state(mgr)
            existing_cache = existing_state.get("visualizer_custom_presets")
            if isinstance(existing_cache, Mapping):
                state["visualizer_custom_presets"] = (
                    normalize_visualizer_custom_snapshot_cache(existing_cache)
                )

    for section_key, section_value in normalized_root.items():
        section_key = str(section_key)
        if section_key in {"preset", "custom_preset_backup"}:
            continue

        if section_key == "widgets":
            if not isinstance(section_value, Mapping):
                raise TypeError("widgets SST section must be a mapping")
            incoming = _coerce_nested_import_mapping(mgr, "widgets", section_value)
            incoming = _normalize_widgets_mapping(incoming)
            existing = state.get("widgets", {})
            if merge and isinstance(existing, Mapping):
                incoming = _normalize_widgets_mapping(_deep_overlay_mapping(existing, incoming))
            state["widgets"] = incoming
            continue

        if section_key == "transitions":
            if not isinstance(section_value, Mapping):
                raise TypeError("transitions SST section must be a mapping")
            incoming = _coerce_nested_import_mapping(mgr, "transitions", section_value)
            existing = state.get("transitions", {})
            if merge and isinstance(existing, Mapping):
                incoming = _deep_overlay_mapping(existing, incoming)
            state["transitions"] = incoming
            continue

        if section_key == "visualizer_custom_presets":
            if not isinstance(section_value, Mapping):
                raise TypeError("visualizer_custom_presets SST section must be a mapping")
            incoming_cache = normalize_visualizer_custom_snapshot_cache(section_value)
            if merge:
                existing_cache = state.get("visualizer_custom_presets", {})
                if isinstance(existing_cache, Mapping):
                    merged_cache = normalize_visualizer_custom_snapshot_cache(existing_cache)
                    merged_cache.update(incoming_cache)
                    incoming_cache = merged_cache
            state["visualizer_custom_presets"] = incoming_cache
            continue

        if section_key in STRUCTURED_SETTINGS_ROOTS:
            if not isinstance(section_value, Mapping):
                raise TypeError(f"{section_key} SST section must be a mapping")
            normalized, _ = mgr._normalize_structured_mapping_shape(section_value)
            incoming = _coerce_nested_import_mapping(mgr, section_key, normalized)
            existing = state.get(section_key, {})
            if merge and isinstance(existing, Mapping):
                existing_normalized, _ = mgr._normalize_structured_mapping_shape(existing)
                incoming = _deep_overlay_mapping(existing_normalized, incoming)
            state[section_key] = incoming
            continue

        if isinstance(section_value, Mapping):
            for raw_subkey, subval in section_value.items():
                dotted = mgr._canonicalize_key(f"{section_key}.{raw_subkey}")
                if dotted in _SST_NON_IMPORTABLE_KEYS:
                    logger.info("Skipping runtime-owned/retired SST key: %s", dotted)
                    continue
                state[dotted] = mgr._coerce_import_value(dotted, subval)
            continue

        canonical_key = mgr._canonicalize_key(section_key)
        if canonical_key in _SST_NON_IMPORTABLE_KEYS:
            logger.info("Skipping runtime-owned/retired SST key: %s", canonical_key)
            continue
        state[canonical_key] = mgr._coerce_import_value(canonical_key, section_value)

    return state


def _normalize_widgets_mapping(widgets_map: Mapping[str, Any]) -> Dict[str, Any]:
    widgets_dict: Dict[str, Any] = dict(widgets_map)
    vis_section = widgets_dict.get('spotify_visualizer')
    if isinstance(vis_section, Mapping):
        widgets_dict['spotify_visualizer'] = normalize_visualizer_section_mapping(
            vis_section,
            apply_preset_overlay=False,
        )
    return widgets_dict


def _strip_steam_secrets_from_snapshot(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    cleaned, removed = strip_steam_secret_fields(snapshot)
    if removed:
        logger.warning(
            "[SETTINGS][STEAM] Stripped %d Steam credential field(s) from settings snapshot",
            removed,
        )
    return cleaned


def export_to_sst(mgr: "SettingsManager", path: str) -> bool:
    """Export a human-readable SST snapshot of all settings to *path*.

    The snapshot is a JSON document with a simple nested structure that
    mirrors the canonical settings schema. The runtime store is
    ``JsonSettingsStore``; SST is a transport layer for moving settings
    between profiles or machines.
    """
    try:
        with mgr._lock:
            keys = list(mgr._settings.allKeys())
            snapshot: Dict[str, Any] = {}

            for key in keys:
                value = mgr._settings.value(key)

                if key == 'widgets':
                    if isinstance(value, Mapping):
                        snapshot['widgets'] = _normalize_widgets_mapping(value)
                    else:
                        snapshot['widgets'] = value
                    continue
                if key == 'visualizer_custom_presets':
                    if isinstance(value, Mapping):
                        snapshot[key] = normalize_visualizer_custom_snapshot_cache(value)
                    else:
                        snapshot[key] = value
                    continue
                if key in STRUCTURED_SETTINGS_ROOTS:
                    if isinstance(value, Mapping):
                        snapshot[key] = dict(value)
                    else:
                        snapshot[key] = value
                    continue
                if '.' in key:
                    section, subkey = key.split('.', 1)
                    container = snapshot.get(section)
                    if not isinstance(container, dict):
                        container = {}
                        snapshot[section] = container
                    container[subkey] = value
                else:
                    snapshot[key] = value

            snapshot = _strip_steam_secrets_from_snapshot(snapshot)

        app_name = mgr.get_application_name()

        payload: Dict[str, Any] = {
            'settings_version': 2,
            'application': app_name,
            'profile': app_name,
            'snapshot_version': SNAPSHOT_VERSION,
            'metadata': mgr._settings.metadata(),
            'snapshot': snapshot,
        }

        target = Path(path)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
        logger.info("Exported settings snapshot to %s", target)
        return True
    except Exception:
        logger.exception("Failed to export settings snapshot to %s", path)
        return False


def import_from_sst(mgr: "SettingsManager", path: str, merge: bool = True) -> bool:
    """Import settings from an SST snapshot at *path*.

    When *merge* is True (default), existing sections are overlaid with
    values from the snapshot instead of clearing the store first.
    """
    try:
        raw = Path(path).read_text(encoding='utf-8')
        loaded = json.loads(raw)
    except Exception:
        logger.exception("Failed to read settings snapshot from %s", path)
        return False

    sst_version: Any = None
    sst_application: Any = None
    if isinstance(loaded, Mapping):
        sst_version = loaded.get('settings_version')
        sst_application = loaded.get('application')

    current_version = 2
    if isinstance(sst_version, int):
        if sst_version > current_version:
            logger.warning(
                "Importing settings snapshot from newer settings_version=%s (current=%s)",
                sst_version, current_version,
            )
        elif sst_version < current_version:
            logger.info(
                "Importing settings snapshot from older settings_version=%s (current=%s)",
                sst_version, current_version,
            )

    if isinstance(sst_application, str):
        current_app = mgr.get_application_name()
        if current_app and sst_application != current_app:
            logger.info(
                "Importing settings snapshot for application '%s' into '%s'",
                sst_application, current_app,
            )

    root: Any
    if isinstance(loaded, Mapping) and 'snapshot' in loaded:
        root = loaded.get('snapshot', {})
    else:
        root = loaded

    if not isinstance(root, Mapping):
        logger.warning("Settings snapshot root is not a mapping: %r", type(root))
        return False

    stripped_root = _strip_steam_secrets_from_snapshot(root)
    normalized_root = normalize_sst_snapshot(stripped_root)

    try:
        with mgr._lock:
            projected = _project_import_state(mgr, normalized_root, merge=merge)
            mgr._settings.replace_all(projected)
            # Re-run the same canonical missing-value merge used by startup. This
            # is normally a no-op for projected state and remains the final guard
            # against future schema additions.
            mgr._set_defaults()
            mgr._mark_visualizer_schema_current_locked()
            mgr._settings.sync()
            mgr._clear_cache_locked()

        mgr._publish_store_change('*', None, mgr._MISSING)
        logger.info("Imported settings snapshot from %s", path)
        return True
    except Exception:
        logger.exception("Failed to apply settings snapshot from %s", path)
        return False


def preview_import_from_sst(mgr: "SettingsManager", path: str, merge: bool = True) -> Dict[str, Any]:
    """Preview the effect of importing an SST snapshot without mutating settings.

    Returns a mapping of setting keys to ``(old_value, new_value)`` tuples for
    every key that would change if :meth:`import_from_sst` were invoked with
    the same arguments.
    """
    try:
        raw = Path(path).read_text(encoding='utf-8')
        loaded = json.loads(raw)
    except Exception:
        logger.exception("Failed to read settings snapshot for preview from %s", path)
        return {}

    root: Any
    if isinstance(loaded, Mapping) and 'snapshot' in loaded:
        root = loaded.get('snapshot', {})
    else:
        root = loaded

    if not isinstance(root, Mapping):
        logger.warning("Settings snapshot root is not a mapping for preview: %r", type(root))
        return {}

    stripped_root = _strip_steam_secrets_from_snapshot(root)
    normalized_root = normalize_sst_snapshot(stripped_root)

    diffs: Dict[str, Any] = {}

    try:
        with mgr._lock:
            old_state = _current_store_state(mgr)
            new_state = _project_import_state(mgr, normalized_root, merge=merge)

            diffs: Dict[str, Any] = {}
            for key in sorted(set(old_state) | set(new_state)):
                old_value = old_state.get(key)
                new_value = new_state.get(key)
                if old_value != new_value:
                    diffs[key] = (old_value, new_value)
            return diffs
    except Exception:
        logger.exception("Failed to compute settings snapshot preview from %s", path)
        return {}


def normalize_sst_snapshot(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    """Coerce legacy flat SST snapshots into the canonical nested form."""
    normalized: Dict[str, Any] = {}

    def assign(section: str, subkey: str, value: Any) -> None:
        container = normalized.get(section)
        if not isinstance(container, dict):
            container = {}
            normalized[section] = container
        container[subkey] = value

    for key, value in snapshot.items():
        if key in STRUCTURED_SETTINGS_ROOTS:
            if isinstance(value, Mapping):
                normalized[key] = (
                    normalize_visualizer_custom_snapshot_cache(value)
                    if key == 'visualizer_custom_presets'
                    else dict(value)
                )
            else:
                normalized[key] = value
            continue
        if key in {"custom_preset_backup", "preset"}:
            # Legacy global preset payloads are ignored on import.
            continue

        if '.' in key:
            section, subkey = key.split('.', 1)
            assign(section, subkey, value)
        else:
            normalized[key] = value

    return normalized
