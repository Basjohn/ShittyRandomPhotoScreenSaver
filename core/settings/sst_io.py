"""SST (Settings Snapshot Transport) import/export logic.

Extracted from settings_manager.py to reduce monolith size.
All functions take the SettingsManager instance as their first argument.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from core.logging.logger import get_logger
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

if TYPE_CHECKING:
    from core.settings.settings_manager import SettingsManager

logger = get_logger(__name__)

SNAPSHOT_VERSION = 1


def _normalize_widgets_mapping(widgets_map: Mapping[str, Any]) -> Dict[str, Any]:
    widgets_dict: Dict[str, Any] = dict(widgets_map)
    vis_section = widgets_dict.get('spotify_visualizer')
    if isinstance(vis_section, Mapping):
        widgets_dict['spotify_visualizer'] = normalize_visualizer_section_mapping(
            vis_section,
            apply_preset_overlay=False,
        )
    return widgets_dict


def export_to_sst(mgr: "SettingsManager", path: str) -> bool:
    """Export a human-readable SST snapshot of all settings to *path*.

    The snapshot is a JSON document with a simple nested structure that
    mirrors the canonical settings schema documented in Docs/SPEC.md.
    QSettings remains the runtime store; this is purely a convenience
    layer for humans (and tests) to inspect or move configurations
    between machines.
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
                if key == 'transitions':
                    if isinstance(value, Mapping):
                        snapshot['transitions'] = dict(value)
                    else:
                        snapshot['transitions'] = value
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

        app_name = getattr(mgr, "_application", "Screensaver")

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

    current_version = 1
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

    normalized_root = normalize_sst_snapshot(root)

    try:
        with mgr._lock:
            for section_key, section_value in normalized_root.items():
                if section_key == "preset":
                    # Retired global preset marker key.
                    continue
                if section_key == 'widgets':
                    widgets_map: Any = section_value
                    if not isinstance(widgets_map, Mapping):
                        continue
                    widgets_dict: Dict[str, Any] = dict(widgets_map)
                    widgets_dict = _normalize_widgets_mapping(widgets_dict)

                    if merge:
                        existing = mgr._settings.value('widgets', {})
                        if isinstance(existing, Mapping):
                            merged_widgets = dict(existing)
                            for name, cfg in widgets_dict.items():
                                merged_widgets[name] = cfg
                            widgets_dict = _normalize_widgets_mapping(merged_widgets)

                    mgr._settings.setValue('widgets', widgets_dict)
                    continue

                if section_key == 'transitions':
                    transitions_map: Any = section_value
                    if not isinstance(transitions_map, Mapping):
                        continue
                    transitions_dict: Dict[str, Any] = dict(transitions_map)

                    if merge:
                        existing_t = mgr._settings.value('transitions', {})
                        if isinstance(existing_t, Mapping):
                            merged_t = dict(existing_t)
                            merged_t.update(transitions_dict)
                            transitions_dict = merged_t

                    mgr._settings.setValue('transitions', transitions_dict)
                    continue

                if section_key in {'display', 'timing', 'input', 'sources', 'cache'} and not isinstance(section_value, Mapping):
                    logger.warning(
                        "Skipping SST section '%s': expected mapping, got %s",
                        section_key, type(section_value).__name__,
                    )
                    continue

                if isinstance(section_value, Mapping):
                    flat: Mapping[str, Any] = section_value
                    for subkey, subval in flat.items():
                        dotted = f"{section_key}.{subkey}"
                        if dotted in {
                            "display.refresh_sync",
                            "display.refresh_adaptive",
                            "display.render_backend_mode",
                            "display.hw_accel",
                        }:
                            logger.info("Skipping legacy display key from SST import: %s", dotted)
                            continue
                        coerced = mgr._coerce_import_value(dotted, subval)
                        mgr._settings.setValue(dotted, coerced)
                else:
                    coerced = mgr._coerce_import_value(section_key, section_value)
                    mgr._settings.setValue(section_key, coerced)

            mgr._settings.sync()
            mgr._cache.clear()

        mgr.settings_changed.emit('*', None)
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

    normalized_root = normalize_sst_snapshot(root)

    diffs: Dict[str, Any] = {}

    try:
        with mgr._lock:
            for section_key, section_value in normalized_root.items():
                if section_key == "preset":
                    continue
                if section_key == 'widgets':
                    widgets_map: Any = section_value
                    if not isinstance(widgets_map, Mapping):
                        continue
                    new_widgets: Dict[str, Any] = dict(widgets_map)
                    new_widgets = _normalize_widgets_mapping(new_widgets)

                    existing = mgr._settings.value('widgets', {})
                    if isinstance(existing, Mapping):
                        old_widgets = dict(existing)
                    else:
                        old_widgets = {}

                    if merge and isinstance(existing, Mapping):
                        merged_widgets = dict(existing)
                        for name, cfg in new_widgets.items():
                            merged_widgets[name] = cfg
                        new_widgets = _normalize_widgets_mapping(merged_widgets)

                    if old_widgets != new_widgets:
                        diffs['widgets'] = (old_widgets, new_widgets)
                    continue

                if section_key == 'transitions':
                    transitions_map: Any = section_value
                    if not isinstance(transitions_map, Mapping):
                        continue
                    new_transitions: Dict[str, Any] = dict(transitions_map)

                    existing_t = mgr._settings.value('transitions', {})
                    if isinstance(existing_t, Mapping):
                        old_transitions = dict(existing_t)
                    else:
                        old_transitions = {}

                    if merge and isinstance(existing_t, Mapping):
                        merged_t = dict(existing_t)
                        merged_t.update(new_transitions)
                        new_transitions = merged_t

                    if old_transitions != new_transitions:
                        diffs['transitions'] = (old_transitions, new_transitions)
                    continue

                if section_key in {'display', 'timing', 'input', 'sources', 'cache'} and not isinstance(section_value, Mapping):
                    logger.warning(
                        "Skipping SST section '%s' in preview: expected mapping, got %s",
                        section_key, type(section_value).__name__,
                    )
                    continue

                if isinstance(section_value, Mapping):
                    flat: Mapping[str, Any] = section_value
                    for subkey, subval in flat.items():
                        dotted = f"{section_key}.{subkey}"
                        new_val = mgr._coerce_import_value(dotted, subval)
                        old_val = mgr._settings.value(dotted)
                        if old_val != new_val:
                            diffs[dotted] = (old_val, new_val)
                else:
                    new_val = mgr._coerce_import_value(section_key, section_value)
                    old_val = mgr._settings.value(section_key)
                    if old_val != new_val:
                        diffs[section_key] = (old_val, new_val)

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
        if key in {'widgets', 'transitions'}:
            if isinstance(value, Mapping):
                normalized[key] = dict(value)
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
