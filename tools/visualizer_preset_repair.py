"""Interactive preset repair tool for Spotify visualizer JSON/SST payloads.

This GUI utility lets us select a visualizer mode, pick a curated preset JSON or
an SST snapshot, then prunes irrelevant keys and fills any missing defaults for
that mode. Repairs keep a recoverable backup copy, but backups live under the
repo temp area instead of polluting the curated preset tree itself.

Foundry UI also provides filename-first reindexing and paired preset swapping
with transactional backups. The existing manifest is refreshed on request only
when it already exists; its eventual retirement is tracked in Current_Plan.md.
Batch repair and CLI auditing remain available.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import os
import shutil
import uuid
import sys
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings import visualizer_presets as vp  # noqa: E402
from core.utils.atomic_files import atomic_write_bytes, atomic_write_text  # noqa: E402
from core.settings.models import _normalize_spectrum_linear_notches  # noqa: E402
from core.settings.visualizer_settings_snapshot import (  # noqa: E402
    _TECHNICAL_GLOBAL_KEYS,
    normalize_visualizer_mode_payload,
)
from core.settings.visualizer_settings_contract import LEGACY_GLOBAL_SHARED_VISUAL_KEYS  # noqa: E402
from core.visualizer_preset_manifest import (  # noqa: E402
    get_visualizer_preset_manifest_path,
    write_curated_visualizer_preset_manifest,
    regenerate_repo_shipped_visualizer_preset_artifacts,
) 
from tools.foundry_chrome import (  # noqa: E402
    FoundryTitleBar, FoundryAppearanceDialog, apply_native_backdrop,
    configure_frameless_window, resolve_tool_theme, save_tool_theme_id,
)
from tools.godzip_foundry_theme import render_foundry_stylesheet  # noqa: E402

_DEFAULTS_CACHE: Dict[str, Any] | None = None
_MANDATORY_TECH_SUFFIXES: Tuple[str, ...] = tuple(sorted(_TECHNICAL_GLOBAL_KEYS))

_DEPRECATED_COMPAT_TECH_SUFFIXES: Tuple[str, ...] = (
    "energy_boost",
    "use_raw_energy",
)
_DEPRECATED_AUTHORED_GLOBAL_KEYS: Tuple[str, ...] = (
    "bar_fill_color",
    "bar_border_color",
    "bar_border_opacity",
    "ghosting_enabled",
    "ghost_alpha",
    "ghost_decay",
)
_DEPRECATED_MODE_ALIAS_KEYS: Dict[str, Tuple[str, ...]] = {
    "oscilloscope": ("osc_sensitivity",),
}

_BACKUP_ROOT = ROOT / "temp" / "visualizer_preset_backups"
_UNDO_STATE_PATH = _BACKUP_ROOT / "undo_state.json"


@dataclass
class UndoEntry:
    restore_path: Path
    backup_path: Path
    cleanup_path: Path | None = None
    # One-click undo for multi-file operations, e.g. swapping two presets.
    related: tuple[tuple[Path, Path, Path | None], ...] = ()
    expected_hashes: tuple[str, ...] = ()  # optional for legacy Undo entries


def _load_undo_history() -> list[UndoEntry]:
    try:
        payload = json.loads(_UNDO_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    if not isinstance(payload, list):
        return []

    history: list[UndoEntry] = []
    for item in payload:
        if not isinstance(item, Mapping):
            continue
        restore_raw = item.get("restore_path")
        backup_raw = item.get("backup_path")
        cleanup_raw = item.get("cleanup_path")
        if not isinstance(restore_raw, str) or not isinstance(backup_raw, str):
            continue
        restore_path = Path(restore_raw)
        backup_path = Path(backup_raw)
        cleanup_path = Path(cleanup_raw) if isinstance(cleanup_raw, str) and cleanup_raw.strip() else None
        if not backup_path.exists():
            continue
        related = []
        for row in item.get("related", []):
            if not isinstance(row, Mapping):
                continue
            restore, backup = row.get("restore_path"), row.get("backup_path")
            cleanup = row.get("cleanup_path")
            if isinstance(restore, str) and isinstance(backup, str) and Path(backup).exists():
                related.append((Path(restore), Path(backup), Path(cleanup) if isinstance(cleanup, str) and cleanup else None))
        hashes = item.get("expected_hashes", [])
        hashes = tuple(hashes) if isinstance(hashes, list) and all(isinstance(h, str) for h in hashes) else ()
        history.append(UndoEntry(restore_path=restore_path, backup_path=backup_path,
                                 cleanup_path=cleanup_path, related=tuple(related), expected_hashes=hashes))
    return history


def _save_undo_history(history: Sequence[UndoEntry]) -> None:
    _UNDO_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "restore_path": str(entry.restore_path),
            "backup_path": str(entry.backup_path),
            "cleanup_path": str(entry.cleanup_path) if entry.cleanup_path is not None else "",
            "related": [
                {"restore_path": str(restore), "backup_path": str(backup),
                 "cleanup_path": str(cleanup) if cleanup else ""}
                for restore, backup, cleanup in entry.related
            ],
            "expected_hashes": list(entry.expected_hashes),
        }
        for entry in history
        if entry.backup_path.exists()
    ]
    atomic_write_text(_UNDO_STATE_PATH, json.dumps(payload, indent=2) + "\n")


def _record_undo_entry(entry: UndoEntry, history: list[UndoEntry] | None = None) -> list[UndoEntry]:
    resolved = list(history) if history is not None else _load_undo_history()
    resolved = [existing for existing in resolved if existing.restore_path != entry.restore_path]
    resolved.append(entry)
    _save_undo_history(resolved)
    return resolved


def _pop_undo_entry(history: list[UndoEntry] | None = None) -> tuple[UndoEntry | None, list[UndoEntry]]:
    resolved = list(history) if history is not None else _load_undo_history()
    while resolved:
        entry = resolved.pop()
        if entry.backup_path.exists():
            _save_undo_history(resolved)
            return entry, resolved
    _save_undo_history([])
    return None, []


@dataclass
class ReindexEntry:
    mode: str
    path: Path
    payload: Dict[str, Any]
    current_index: int | None


def _load_visualizer_defaults() -> Dict[str, Any]:
    global _DEFAULTS_CACHE
    if _DEFAULTS_CACHE is None:
        from core.settings.defaults import get_default_settings

        defaults = deepcopy(get_default_settings()["widgets"]["spotify_visualizer"])
        _DEFAULTS_CACHE = defaults
    return deepcopy(_DEFAULTS_CACHE)


def _canonical_mode_defaults(mode: str) -> Dict[str, Any]:
    defaults = _load_visualizer_defaults()
    defaults["mode"] = mode
    return normalize_visualizer_mode_payload(mode, defaults)


def _canonical_spectrum_linear_notches() -> Any:
    """Canonical ``spectrum_notch_positions_linear`` for repair-from-canonical.

    ``_normalize_spectrum_linear_notches`` repairs only from canonical state (no
    hardcoded fallback), so it requires the canonical default explicitly.
    """
    return _load_visualizer_defaults()["spectrum_notch_positions_linear"]


def _canonical_mode_prefix(mode: str) -> str:
    prefixes = vp.MODE_KEY_PREFIXES.get(mode)  # type: ignore[attr-defined]
    preferred = f"{mode}_"
    if prefixes:
        if preferred in prefixes:
            return preferred
        return prefixes[0]
    return f"{mode}_"


def _mode_tech_prefix(mode: str) -> str:
    """Return the canonical per-mode technical key prefix for *mode*."""
    return _canonical_mode_prefix(mode)


def _promote_global_technical_settings(mode: str, sanitized: Dict[str, Any]) -> None:
    """Copy legacy global tech settings (e.g. manual_floor) into per-mode keys."""

    prefix = _mode_tech_prefix(mode)
    for suffix in _MANDATORY_TECH_SUFFIXES:
        global_key = suffix
        mode_key = f"{prefix}{suffix}"
        if global_key in sanitized:
            if mode_key not in sanitized:
                sanitized[mode_key] = sanitized[global_key]
            sanitized.pop(global_key, None)


def _promote_global_visual_settings(mode: str, sanitized: Dict[str, Any]) -> None:
    """Copy legacy shared-authored visual keys into canonical per-mode keys."""

    prefix = _canonical_mode_prefix(mode)
    for suffix in tuple(
        key for key in LEGACY_GLOBAL_SHARED_VISUAL_KEYS
        if key.startswith("bar_")
    ):
        global_key = suffix
        mode_key = f"{prefix}{suffix}"
        if global_key in sanitized:
            if mode_key not in sanitized:
                sanitized[mode_key] = deepcopy(sanitized[global_key])
            sanitized.pop(global_key, None)

    legacy_ghost_map = {
        "ghosting_enabled": f"{prefix}ghosting_enabled",
        "ghost_alpha": f"{prefix}ghost_alpha",
        "ghost_decay": f"{prefix}ghost_decay",
    }
    for global_key, mode_key in legacy_ghost_map.items():
        if global_key in sanitized:
            if mode_key not in sanitized:
                sanitized[mode_key] = sanitized[global_key]
            sanitized.pop(global_key, None)


def _strip_deprecated_curated_keys(mode: str, sanitized: Dict[str, Any]) -> None:
    """Curated authored payloads should not keep deprecated compat keys alive."""
    prefix = _mode_tech_prefix(mode)
    for suffix in _DEPRECATED_COMPAT_TECH_SUFFIXES:
        sanitized.pop(suffix, None)
        sanitized.pop(f"{prefix}{suffix}", None)


def _collect_sections(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    return vp._collect_visualizer_sections(payload)  # type: ignore[attr-defined]


def _promote_legacy_spectrum_lane_scalars(section: Mapping[str, Any]) -> Dict[str, Any]:
    promoted = dict(section)
    if (
        "spectrum_lane_strengths_mirrored" in promoted
        and "spectrum_lane_strengths_linear" in promoted
    ):
        return promoted

    try:
        bass_emphasis = float(promoted.get("spectrum_bass_emphasis", 0.50))
        mid_suppression = float(promoted.get("spectrum_mid_suppression", 0.50))
    except Exception:
        return promoted

    bass = max(0.0, min(1.0, bass_emphasis * 1.6))
    mid = max(0.0, min(1.0, 1.0 - mid_suppression * 0.8))
    low_mid = max(0.0, min(1.0, bass * 0.55 + mid * 0.45))
    vocal = max(0.0, min(1.0, mid * 0.9 + 0.1))
    hi_mid = max(0.0, min(1.0, mid * 0.5 + 0.5))
    promoted.setdefault(
        "spectrum_lane_strengths_mirrored",
        {"Mid": mid, "Vocal": vocal, "Low-Mid": low_mid, "Bass": bass},
    )
    promoted.setdefault(
        "spectrum_lane_strengths_linear",
        {"Bass": bass, "Low-Mid": low_mid, "Vocal": vocal, "Hi-Mid": hi_mid, "Treble": 1.0},
    )
    return promoted


def _validate_payload_mode(mode: str, payload: Mapping[str, Any]) -> None:
    for key in ('mode', 'visualizer_preset_mode'):
        if key in payload and payload[key] != mode:
            raise ValueError(f"Preset {key} {payload[key]!r} does not match selected mode {mode!r}")


def _sanitize_settings(mode: str, payload: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, list[str]]]:
    _validate_payload_mode(mode, payload)
    sections = _collect_sections(payload)
    if not sections:
        raise ValueError("File does not contain any spotify_visualizer settings block")

    sanitized: Dict[str, Any] = {}
    original_filtered: Dict[str, Any] = {}
    migrated_keys: set[str] = set()
    legacy_global_authored: set[str] = set()
    for section in sections:
        section_payload = dict(section)
        original_section = dict(section_payload)
        raw_filtered = vp._filter_settings_for_mode(mode, dict(section_payload))  # type: ignore[attr-defined]
        if mode == "spectrum":
            section_payload = _promote_legacy_spectrum_lane_scalars(section_payload)
        migrated = vp._migrate_preset_settings(mode, section_payload)  # type: ignore[attr-defined]
        filtered = vp._filter_settings_for_mode(mode, migrated)  # type: ignore[attr-defined]
        # Every shared migration owns its output keys. A hand-maintained list
        # here lost newly renamed values (Flicker -> Shimmer became default .3).
        migrated_keys.update(set(filtered) - set(raw_filtered))
        for suffix in _MANDATORY_TECH_SUFFIXES:
            if suffix in original_section and suffix not in filtered:
                filtered[suffix] = deepcopy(original_section[suffix])
                legacy_global_authored.add(suffix)
        original_filtered.update(raw_filtered)
        if mode == "oscilloscope" and "osc_sensitivity" in section:
            if "osc_line_amplitude" in filtered:
                original_filtered["osc_line_amplitude"] = filtered["osc_line_amplitude"]
        if mode == "spectrum" and (
            "spectrum_bass_emphasis" in section or "spectrum_mid_suppression" in section
        ):
            for promoted_key in (
                "spectrum_lane_strengths_mirrored",
                "spectrum_lane_strengths_linear",
            ):
                if promoted_key in filtered:
                    original_filtered[promoted_key] = filtered[promoted_key]
        sanitized.update(filtered)

    authored_keys = set(original_filtered.keys())
    promoted_mode_keys = {
        f"{_mode_tech_prefix(mode)}{suffix}"
        for suffix in _MANDATORY_TECH_SUFFIXES
        if suffix in original_filtered or suffix in legacy_global_authored
    }
    allowed_keys = authored_keys | promoted_mode_keys | migrated_keys | legacy_global_authored | {"mode"}
    sanitized = {key: value for key, value in sanitized.items() if key in allowed_keys}
    if mode == "spectrum" and "spectrum_notch_positions_linear" in sanitized:
        sanitized["spectrum_notch_positions_linear"] = _normalize_spectrum_linear_notches(
            sanitized["spectrum_notch_positions_linear"],
            _canonical_spectrum_linear_notches(),
        )
    sanitized["mode"] = mode
    _promote_global_technical_settings(mode, sanitized)
    _promote_global_visual_settings(mode, sanitized)
    _strip_deprecated_curated_keys(mode, sanitized)
    canonical_defaults = _canonical_mode_defaults(mode)
    prefix = _mode_tech_prefix(mode)
    for suffix in _MANDATORY_TECH_SUFFIXES:
        mode_key = f"{prefix}{suffix}"
        if mode_key in canonical_defaults:
            sanitized.setdefault(mode_key, deepcopy(canonical_defaults[mode_key]))
    # A preset authors every control: a new control is filled at its canonical default (what the preset already
    # resolved to), never left to a silent fallback, and then authored per preset.
    for key in vp.preset_artwork_keys(mode):
        if key not in sanitized and key in canonical_defaults:
            sanitized[key] = deepcopy(canonical_defaults[key])
    orig_keys = set(original_filtered.keys())
    new_keys = set(sanitized.keys())

    added = sorted(new_keys - orig_keys)
    removed = sorted(orig_keys - new_keys)
    changed = sorted(
        key for key in (new_keys & orig_keys) if sanitized.get(key) != original_filtered.get(key)
    )

    stats = {"added": added, "removed": removed, "changed": changed}
    return sanitized, stats


def audit_payload(mode: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Return preset-shape issues that should be repaired or blocked from shipping."""
    sections = list(_collect_sections(payload))
    issues: Dict[str, Any] = {
        "mode": mode,
        "duplicate_prefixed_keys": [],
        "cross_mode_keys": [],
        "has_custom_preset_backup": False,
        "deprecated_authored_keys": [],
        "deprecated_global_keys": [],
        "deprecated_mode_alias_keys": [],
        "legacy_spectrum_linear_notch_family": False,
        "top_level_visualizer_duplication": False,
    }
    prefixes = tuple(vp.MODE_KEY_PREFIXES.get(mode, (_canonical_mode_prefix(mode),)))  # type: ignore[attr-defined]
    other_prefixes: tuple[str, ...] = tuple(
        prefix
        for other_mode, mode_prefixes in vp.MODE_KEY_PREFIXES.items()  # type: ignore[attr-defined]
        if other_mode != mode
        for prefix in mode_prefixes
    )

    snapshot = payload.get("snapshot")
    if isinstance(snapshot, Mapping) and isinstance(snapshot.get("custom_preset_backup"), Mapping):
        issues["has_custom_preset_backup"] = True

    widgets_root = payload.get("widgets")
    snapshot_widgets = snapshot.get("widgets") if isinstance(snapshot, Mapping) else None
    if isinstance(widgets_root, Mapping) and isinstance(snapshot_widgets, Mapping):
        if "spotify_visualizer" in widgets_root and "spotify_visualizer" in snapshot_widgets:
            issues["top_level_visualizer_duplication"] = True

    for section in sections:
        for key in section.keys():
            if not isinstance(key, str):
                continue
            if (
                mode == "spectrum"
                and key == "spectrum_notch_positions_linear"
                and _normalize_spectrum_linear_notches(
                    section.get(key), _canonical_spectrum_linear_notches()
                )
                != section.get(key)
            ):
                issues["legacy_spectrum_linear_notch_family"] = True
            if any(prefix and key.startswith(f"{prefix}{prefix}") for prefix in prefixes):
                issues["duplicate_prefixed_keys"].append(key)
            if any(prefix and key.startswith(prefix) for prefix in other_prefixes):
                issues["cross_mode_keys"].append(key)
            if any(key.endswith(suffix) for suffix in _DEPRECATED_COMPAT_TECH_SUFFIXES):
                issues["deprecated_authored_keys"].append(key)
            if key in _DEPRECATED_AUTHORED_GLOBAL_KEYS:
                issues["deprecated_global_keys"].append(key)
            if key in _DEPRECATED_MODE_ALIAS_KEYS.get(mode, ()):
                issues["deprecated_mode_alias_keys"].append(key)
    issues["duplicate_prefixed_keys"] = sorted(set(issues["duplicate_prefixed_keys"]))
    issues["cross_mode_keys"] = sorted(set(issues["cross_mode_keys"]))
    issues["deprecated_authored_keys"] = sorted(set(issues["deprecated_authored_keys"]))
    issues["deprecated_global_keys"] = sorted(set(issues["deprecated_global_keys"]))
    issues["deprecated_mode_alias_keys"] = sorted(set(issues["deprecated_mode_alias_keys"]))
    issues["problem_count"] = (
        len(issues["duplicate_prefixed_keys"])
        + len(issues["cross_mode_keys"])
        + len(issues["deprecated_authored_keys"])
        + len(issues["deprecated_global_keys"])
        + len(issues["deprecated_mode_alias_keys"])
        + int(bool(issues["legacy_spectrum_linear_notch_family"]))
        + int(bool(issues["has_custom_preset_backup"]))
        + int(bool(issues["top_level_visualizer_duplication"]))
    )
    return issues


def _build_clean_payload(path: Path, payload: Mapping[str, Any], mode: str, cleaned: Mapping[str, Any]) -> Tuple[Dict[str, Any], list[str]]:
    """Rebuild a lean preset payload containing only sanitized visualizer settings."""

    lean: Dict[str, Any] = {}
    if "starting_view" in payload:
        from core.settings.visualizer_view_orbit import validate_visualizer_starting_view
        lean["starting_view"] = validate_visualizer_starting_view(mode, payload["starting_view"])
    for meta_key in ("name", "description", "preset_index"):
        value = payload.get(meta_key)
        if value is None:
            continue
        if meta_key == "preset_index" and isinstance(value, str):
            try:
                value = int(value)
            except ValueError:
                continue
        lean[meta_key] = value

    if "preset_index" not in lean:
        inferred_index = vp._infer_preset_index_from_name(path.stem)  # type: ignore[attr-defined]
        if inferred_index is not None:
            lean["preset_index"] = inferred_index

    if "name" not in lean or not lean["name"]:
        inferred_name: str | None = None
        idx = lean.get("preset_index")
        if isinstance(idx, int):
            suffix = vp._infer_suffix_from_name(path.stem)  # type: ignore[attr-defined]
            inferred_name = vp._friendly_name_from_suffix(idx, suffix)  # type: ignore[attr-defined]
        if not inferred_name:
            idx_val = int(idx) + 1 if isinstance(idx, int) else None
            inferred_name = f"Preset {idx_val}" if idx_val is not None else f"Preset ({mode})"
        lean["name"] = inferred_name

    lean["mode"] = mode
    # Mark the payload so the loader recognizes it as an override even when the
    # user places it alongside curated presets. This mirrors the manual marker
    # contract in core/settings/visualizer_presets.
    lean["visualizer_preset_override"] = True
    lean["visualizer_preset_mode"] = mode

    sv_block = deepcopy(dict(cleaned))

    # Do not emit custom_preset_backup anymore. The duplicate snapshot caused
    # curated presets to drift because later tooling/user edits only touched the
    # widgets block while this tool kept rewriting the legacy backup payload.
    lean["snapshot"] = {
        "widgets": {"spotify_visualizer": deepcopy(sv_block)}
    }

    widgets_section: Dict[str, Any] = {}
    original_widgets_root = payload.get("widgets")
    if isinstance(original_widgets_root, Mapping):
        for name, cfg in original_widgets_root.items():
            if name == "spotify_visualizer":
                continue
            widgets_section[name] = deepcopy(cfg)
    if widgets_section:
        lean["widgets"] = widgets_section

    updated_paths = ["snapshot.widgets.spotify_visualizer"]
    if widgets_section:
        updated_paths.append("widgets")

    return lean, updated_paths


def _apply_cleaned_payload_in_place(payload: Dict[str, Any], cleaned: Mapping[str, Any]) -> list[str]:
    """Patch visualizer payload blocks in place without rebuilding authored metadata."""
    updated_paths: list[str] = []
    cleaned_block = deepcopy(dict(cleaned))

    snapshot = payload.get("snapshot")
    if isinstance(snapshot, dict):
        widgets_section = snapshot.get("widgets")
        if isinstance(widgets_section, dict) and isinstance(widgets_section.get("spotify_visualizer"), Mapping):
            widgets_section["spotify_visualizer"] = deepcopy(cleaned_block)
            updated_paths.append("snapshot.widgets.spotify_visualizer")

        backup_section = snapshot.get("custom_preset_backup")
        if isinstance(backup_section, dict):
            snapshot.pop("custom_preset_backup", None)
            updated_paths.append("snapshot.custom_preset_backup")

    if isinstance(payload.get("spotify_visualizer"), Mapping):
        payload["spotify_visualizer"] = deepcopy(cleaned_block)
        updated_paths.append("spotify_visualizer")

    settings_section = payload.get("settings")
    if isinstance(settings_section, dict):
        dotted_prefix = "widgets.spotify_visualizer."
        dotted_keys = [
            key for key in list(settings_section.keys())
            if isinstance(key, str) and key.startswith(dotted_prefix)
        ]
        if dotted_keys:
            for key in dotted_keys:
                settings_section.pop(key, None)
            for key, value in cleaned_block.items():
                settings_section[f"{dotted_prefix}{key}"] = deepcopy(value)
            updated_paths.append("settings")
        else:
            payload["settings"] = deepcopy(cleaned_block)
            updated_paths.append("settings")

    if any(path != "snapshot.custom_preset_backup" for path in updated_paths):
        # De-duplicate while preserving first-seen order for stable reporting.
        return list(dict.fromkeys(updated_paths))

    # Forward-migrate a legacy backup-only payload into its one live section.
    snapshot_map = payload.get("snapshot")
    if not isinstance(snapshot_map, dict):
        snapshot_map = {}
        payload["snapshot"] = snapshot_map
    widgets_map = snapshot_map.get("widgets")
    if not isinstance(widgets_map, dict):
        widgets_map = {}
        snapshot_map["widgets"] = widgets_map
    widgets_map["spotify_visualizer"] = deepcopy(cleaned_block)
    return [*updated_paths, "snapshot.widgets.spotify_visualizer"]


def _ensure_backup(path: Path) -> Path:
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
        target_dir = (_BACKUP_ROOT / relative.parent).resolve()
    except Exception:
        target_dir = _BACKUP_ROOT.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    primary = target_dir / f"{path.name}.bak"
    secondary = target_dir / f"{path.name}.bak1"
    for stale in sorted(target_dir.glob(f"{path.name}.bak*")):
        if stale in (primary, secondary):
            continue
        if stale.name.endswith(".bak"):
            continue
        if stale.name.endswith(".bak1"):
            continue
        stale.unlink(missing_ok=True)
    if secondary.exists():
        secondary.unlink()
    if primary.exists():
        primary.replace(secondary)
    shutil.copy2(path, primary)
    return primary


def _unique_transaction_backup(path: Path, group: str) -> Path:
    """Do not rotate away a backup while it is referenced by Undo."""
    folder = _BACKUP_ROOT / group
    folder.mkdir(parents=True, exist_ok=True)
    backup = folder / f"{uuid.uuid4().hex}.json"
    shutil.copy2(path, backup)
    return backup


def _load_reindex_entry(mode: str, path: Path) -> ReindexEntry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Payload root must be a JSON object")
    _validate_payload_mode(mode, payload)
    # Filenames are operator-authored ordering authority. Embedded metadata is
    # deliberately ignored even when it is a valid but stale integer.
    current_index = vp._infer_preset_index_from_name(path.stem)  # type: ignore[attr-defined]
    return ReindexEntry(
        mode=mode,
        path=path,
        payload=payload,
        current_index=current_index,
    )


def _ordered_reindex_entries(entries: List[ReindexEntry]) -> List[ReindexEntry]:
    """Order by numbered filenames, then markerless files, never JSON metadata."""
    return sorted(entries, key=lambda entry: (
        entry.current_index is None,
        entry.current_index if entry.current_index is not None else 0,
        entry.path.name.casefold(),
    ))


def _indexed_preset_name(original_name: Any, target_index: int) -> str:
    """Update only the Preset N prefix, preserving the human-authored label."""
    if not isinstance(original_name, str) or not original_name.strip():
        return f"Preset {target_index + 1}"
    prefix = re.compile(r"^(\s*Preset\s+)\d+\b", re.IGNORECASE)
    if prefix.match(original_name):
        return prefix.sub(lambda match: match.group(1) + str(target_index + 1),
                          original_name, count=1)
    return f"Preset {target_index + 1} ({original_name})"


def _canonical_reindexed_payload(entry: ReindexEntry, target_index: int) -> Dict[str, Any]:
    payload = deepcopy(entry.payload)
    payload["preset_index"] = target_index
    payload["name"] = _indexed_preset_name(payload.get("name"), target_index)
    return payload


def _canonical_reindexed_path(mode_dir: Path, entry: ReindexEntry, target_index: int) -> Path:
    """Build the target path for a reindexed preset, preserving the original file suffix verbatim.

    Three cases:
    - ``preset_N_some_suffix.json``  → ``preset_M_some_suffix.json`` (suffix preserved verbatim)
    - ``preset_N.json``              → ``preset_M.json``             (no suffix)
    - ``markerless.json``            → ``preset_M_markerless.json``  (stem used as suffix)
    """
    stem = entry.path.stem
    suffix_match = re.match(r"^preset[\s_-]*\d+[\s_-]+(.+)$", stem, flags=re.IGNORECASE)
    if suffix_match:
        file_suffix = suffix_match.group(1)
        filename = f"preset_{target_index + 1}_{file_suffix}.json"
    elif re.match(r"^preset[\s_-]*\d+$", stem, flags=re.IGNORECASE):
        filename = f"preset_{target_index + 1}.json"
    else:
        filename = f"preset_{target_index + 1}_{stem}.json"
    return mode_dir / filename


def reindex_mode_presets(mode: str) -> List[Tuple[Path, Path, Path]]:
    mode_dir = ROOT / "presets" / "visualizer_modes" / mode
    if not mode_dir.exists():
        return []

    entries = [_load_reindex_entry(mode, path) for path in sorted(mode_dir.glob("*.json"))]
    if not entries:
        return []

    ordered = _ordered_reindex_entries(entries)
    plans: List[Tuple[ReindexEntry, Path, Dict[str, Any], str]] = []
    for target_index, entry in enumerate(ordered):
        final_payload = _canonical_reindexed_payload(entry, target_index)
        final_path = _canonical_reindexed_path(mode_dir, entry, target_index)
        final_text = json.dumps(final_payload, indent=2, sort_keys=True) + "\n"
        plans.append((entry, final_path, final_payload, final_text))

    changed_plans = [
        (entry, final_path, final_payload, final_text)
        for entry, final_path, final_payload, final_text in plans
        if final_path != entry.path or entry.path.read_text(encoding="utf-8") != final_text
    ]
    if not changed_plans:
        return []

    # Refuse conflicting targets before making a single change. The previous
    # algorithm could overwrite a file that was not part of changed_plans.
    changing_sources = {entry.path for entry, *_ in changed_plans}
    targets = [final_path for _entry, final_path, *_ in plans]
    if len(targets) != len(set(targets)):
        raise ValueError(f"Ambiguous duplicate preset destinations in {mode_dir}")
    for dest in targets:
        if dest.exists() and dest not in changing_sources and not any(
            entry.path == dest and final_path == dest for entry, final_path, *_ in plans
        ):
            raise ValueError(f"Destination occupied by an unrelated preset: {dest}")

    temp_dir = mode_dir / f".reindex_tmp_{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)

    backups: List[Tuple[Path, Path]] = []
    results: List[Tuple[Path, Path, Path]] = []
    try:
        for index, (entry, final_path, _final_payload, final_text) in enumerate(changed_plans):
            backup = _unique_transaction_backup(entry.path, "reindex")
            backups.append((entry.path, backup))
            staged_path = temp_dir / f"{index:03d}.json"
            staged_path.write_text(final_text, encoding="utf-8")
            results.append((entry.path, final_path, backup))

        for entry, _final_path, _final_payload, _final_text in changed_plans:
            if entry.path.exists():
                entry.path.unlink()

        for index, (_entry, final_path, _final_payload, _final_text) in enumerate(changed_plans):
            staged_path = temp_dir / f"{index:03d}.json"
            os.replace(staged_path, final_path)
    except Exception:
        for _entry, final_path, _payload, _text in changed_plans:
            if final_path.exists():
                final_path.unlink()
        for original, backup in backups:
            shutil.copy2(backup, original)
        raise
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    return results


def reindex_curated_presets(
    *,
    on_result: Callable[[str, Path, Path, Path], None] | None = None,
    on_error: Callable[[str, Exception], None] | None = None,
) -> List[Tuple[str, Path, Path, Path]]:
    processed: List[Tuple[str, Path, Path, Path]] = []
    for mode in vp.MODES:
        try:
            mode_results = reindex_mode_presets(mode)
        except Exception as exc:
            if on_error:
                on_error(mode, exc)
            continue
        for old_path, new_path, backup in mode_results:
            entry = (mode, old_path, new_path, backup)
            processed.append(entry)
            if on_result:
                on_result(*entry)
    if processed:
        _regenerate_shipped_preset_artifacts_if_needed(
            [old_path for _mode, old_path, _new_path, _backup in processed]
        )
    return processed


def _authored_mode_entries(mode: str, mode_dir: Path | None = None) -> list[ReindexEntry]:
    mode_dir = mode_dir or (ROOT / "presets" / "visualizer_modes" / mode)
    if mode not in vp.MODES:
        raise ValueError(f"Unknown visualizer mode: {mode}")
    return _ordered_reindex_entries([_load_reindex_entry(mode, path)
                                     for path in mode_dir.glob("*.json")])


def swap_mode_presets(
    mode: str, first: Path, second: Path, *, mode_dir: Path | None = None,
) -> tuple[tuple[Path, Path, Path], tuple[Path, Path, Path]]:
    """Swap two authored slots without changing any visualizer setting values.

    Stage both replacements, check destination ownership before any mutation,
    retain separate durable backups and roll back the pair on write failure.
    """
    mode_dir = (mode_dir or (ROOT / "presets" / "visualizer_modes" / mode)).resolve()
    entries = _authored_mode_entries(mode, mode_dir)
    by_path = {entry.path.resolve(): entry for entry in entries}
    a, b = by_path.get(Path(first).resolve()), by_path.get(Path(second).resolve())
    if a is None or b is None or a.path == b.path:
        raise ValueError("Choose two different existing presets in the selected mode")
    if a.current_index is None or b.current_index is None or a.current_index == b.current_index:
        raise ValueError("Both presets need distinct numbered filenames. Reindex first if necessary.")
    slots = [(entry.current_index, entry.path) for entry in entries if entry.current_index is not None]
    if len(slots) != len({slot for slot, _ in slots}):
        raise ValueError("Duplicate numbered slots exist in this mode; resolve them before swapping")

    destinations = (
        _canonical_reindexed_path(mode_dir, a, b.current_index),
        _canonical_reindexed_path(mode_dir, b, a.current_index),
    )
    if destinations[0] == destinations[1]:
        raise ValueError("Swap would create duplicate target filenames")
    source_paths = {a.path, b.path}
    for dest in destinations:
        if dest.exists() and dest not in source_paths:
            raise FileExistsError(f"Swap destination already exists: {dest.name}")

    # Unique backups preserve previous undo transactions instead of rotating
    # their backups out from under the persisted Undo history.
    transaction = uuid.uuid4().hex
    backup_dir = _BACKUP_ROOT / "swap" / transaction
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_a, backup_b = backup_dir / "first.json", backup_dir / "second.json"
    shutil.copy2(a.path, backup_a)
    shutil.copy2(b.path, backup_b)
    stage = backup_dir / "stage"
    stage.mkdir()
    staged = [stage / "first.json", stage / "second.json"]
    for target, entry, index in zip(staged, (a, b), (b.current_index, a.current_index)):
        target.write_text(json.dumps(_canonical_reindexed_payload(entry, index), indent=2,
                                     ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        a.path.unlink()
        b.path.unlink()
        os.replace(staged[0], destinations[0])
        os.replace(staged[1], destinations[1])
    except Exception:
        for dest in set(destinations):
            if dest.exists():
                dest.unlink()
        shutil.copy2(backup_a, a.path)
        shutil.copy2(backup_b, b.path)
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    return ((a.path, destinations[0], backup_a),
            (b.path, destinations[1], backup_b))


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _undo_hashes(rows: Iterable[tuple[Path, Path, Path | None]]) -> tuple[str, ...]:
    return tuple(_file_digest(cleanup if cleanup is not None else restore)
                 for restore, _backup, cleanup in rows)


def restore_undo_entry(entry: UndoEntry) -> None:
    """Restore all files in one action, including paired swap replacements."""
    affected = [(entry.restore_path, entry.backup_path, entry.cleanup_path), *entry.related]
    for _restore, backup, _cleanup in affected:
        if not backup.is_file():
            raise FileNotFoundError(f"Missing undo backup: {backup}")
    if entry.expected_hashes:
        if len(entry.expected_hashes) != len(affected) or entry.expected_hashes != _undo_hashes(affected):
            raise RuntimeError("Preset files changed since this operation. Undo refused to protect newer edits.")
    destinations = {cleanup if cleanup is not None else restore for restore,_backup,cleanup in affected}
    for restore,_backup,_cleanup in affected:
        if restore.exists() and restore not in destinations:
            raise RuntimeError(f"Undo refused: original filename is now occupied by a newer file: {restore}")
    # Read every backup and current before-image before touching any file.
    # Restore atomically before removing obsolete destinations; never delete a
    # path which is also another row's restored source (same-suffix swaps).
    restored = {restore: backup.read_bytes() for restore,backup,_cleanup in affected}
    touched = set(restored) | {cleanup for _restore,_backup,cleanup in affected if cleanup is not None}
    before = {path: path.read_bytes() if path.exists() else None for path in touched}
    try:
        for restore,data in restored.items():
            atomic_write_bytes(restore,data)
        for _restore,_backup,cleanup in affected:
            if cleanup is not None and cleanup not in restored:
                cleanup.unlink(missing_ok=True)
    except Exception as failure:
        rollback_errors=[]
        for path,data in before.items():
            try:
                if data is None:path.unlink(missing_ok=True)
                else:atomic_write_bytes(path,data)
            except Exception as rollback_error:
                rollback_errors.append(f'{path}: {rollback_error}')
        if rollback_errors:
            raise RuntimeError('Undo rollback failed; retained backups are required: '+ '; '.join(rollback_errors)) from failure
        raise


def regenerate_existing_visualizer_manifest(*, sync_release: bool = False) -> bool:
    """Rebuild an existing source manifest without creating one after retirement.

    The explicit GUI button only updates the source inventory; existing repair
    workflows may also sync the release mirror when they have changed files.
    """
    root = ROOT / "presets" / "visualizer_modes"
    if not get_visualizer_preset_manifest_path(root).is_file():
        return False
    if sync_release:
        regenerate_repo_shipped_visualizer_preset_artifacts(ROOT)
    else:
        write_curated_visualizer_preset_manifest(root)
    return True


def repair_file(
    path: Path,
    mode: str,
    *,
    sync_shipped_artifacts: bool = True,
) -> Tuple[Path, Dict[str, Any]]:
    try:
        original_bytes = path.read_bytes()
        raw_text = original_bytes.decode("utf-8")
        payload = json.loads(raw_text)
    except Exception as exc:  # pragma: no cover - GUI path
        raise ValueError(f"Failed to read JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Payload root must be a JSON object")

    cleaned, stats = _sanitize_settings(mode, payload)
    if "starting_view" in payload:
        from core.settings.visualizer_view_orbit import validate_visualizer_starting_view
        validate_visualizer_starting_view(mode, payload["starting_view"])
    patched_payload = deepcopy(payload)
    updated_paths = _apply_cleaned_payload_in_place(patched_payload, cleaned)

    new_text = json.dumps(patched_payload, indent=2, sort_keys=True)
    if path.read_bytes() != original_bytes:
        raise RuntimeError(f"Preset changed during repair: {path}")
    backup_path = _ensure_backup(path)
    if path.read_bytes() != original_bytes:
        raise RuntimeError(f"Preset changed while backing up repair: {path}")
    atomic_write_text(path, new_text + "\n")

    stats = {
        "updated_paths": updated_paths,
        "added": stats["added"],
        "removed": stats["removed"],
        "changed": stats["changed"],
    }
    if sync_shipped_artifacts:
        _regenerate_shipped_preset_artifacts_if_needed([path])
    return backup_path, stats


def _discover_preset_files() -> List[Tuple[str, Path]]:
    files: List[Tuple[str, Path]] = []
    root = ROOT / "presets" / "visualizer_modes"
    for mode in vp.MODES:
        mode_dir = root / mode
        if not mode_dir.exists():
            continue
        for path in sorted(mode_dir.glob("*.json")):
            files.append((mode, path))
    return files


def _is_curated_source_path(path: Path) -> bool:
    try:
        path.resolve().relative_to((ROOT / "presets" / "visualizer_modes").resolve())
        return True
    except Exception:
        return False


def _regenerate_shipped_preset_artifacts_if_needed(mutated_paths: Iterable[Path]) -> None:
    if not any(_is_curated_source_path(path) for path in mutated_paths):
        return
    regenerate_existing_visualizer_manifest(sync_release=True)


def repair_all_presets(
    *,
    modes: Iterable[str] | None = None,
    on_result: Callable[[str, Path, Path, Dict[str, Any]], None] | None = None,
    on_error: Callable[[str, Path, Exception], None] | None = None,
) -> List[Tuple[str, Path, Path, Dict[str, Any]]]:
    """Repair every curated preset JSON under presets/visualizer_modes."""

    processed: List[Tuple[str, Path, Path, Dict[str, Any]]] = []
    wanted = set(modes) if modes is not None else None
    for mode, path in _discover_preset_files():
        if wanted is not None and mode not in wanted:
            continue
        try:
            backup, stats = repair_file(path, mode, sync_shipped_artifacts=False)
        except Exception as exc:  # pragma: no cover - batch path logging
            if on_error:
                on_error(mode, path, exc)
            continue
        entry = (mode, path, backup, stats)
        processed.append(entry)
        if on_result:
            on_result(*entry)
    if processed:
        _regenerate_shipped_preset_artifacts_if_needed([path for _mode, path, _backup, _stats in processed])
    return processed


def audit_all_presets() -> List[Tuple[str, Path, Dict[str, Any]]]:
    """Audit every curated preset JSON under presets/visualizer_modes."""
    findings: List[Tuple[str, Path, Dict[str, Any]]] = []
    for mode, path in _discover_preset_files():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            findings.append(
                (
                    mode,
                    path,
                    {
                        "mode": mode,
                        "problem_count": 1,
                        "read_error": str(exc),
                    },
                )
            )
            continue
        if not isinstance(payload, Mapping):
            findings.append(
                (
                    mode,
                    path,
                    {
                        "mode": mode,
                        "problem_count": 1,
                        "read_error": "Payload root must be a JSON object",
                    },
                )
            )
            continue
        report = audit_payload(mode, payload)
        if report.get("problem_count", 0):
            findings.append((mode, path, report))
    return findings


class VisualizerPresetRepairApp(QMainWindow):
    """Foundry-style catalogue tools, without a second preset authority."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SRPSS Visualizer Preset Repair Foundry")
        configure_frameless_window(self)
        self.resize(1040, 760)
        self.setMinimumSize(860, 640)
        self._theme_id = ""
        self._theme = None
        self._history = _load_undo_history()
        root = QWidget(self)
        root.setObjectName("presetRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(0)
        shell = QFrame(root)
        shell.setObjectName("presetShell")
        outer.addWidget(shell, 1)
        layout = QVBoxLayout(shell)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(FoundryTitleBar("VISUALIZER PRESET REPAIR FOUNDRY", self,
                                          settings_callback=self._appearance))
        pane = QWidget(shell)
        pane.setObjectName("presetPane")
        body = QVBoxLayout(pane)
        body.setContentsMargins(22, 17, 22, 18)
        body.setSpacing(13)
        layout.addWidget(pane, 1)

        intro = QLabel("Repair curated JSON, correct filename slot metadata, or swap two presets in one operation.")
        intro.setObjectName("presetMuted")
        intro.setWordWrap(True)
        body.addWidget(intro)

        head = QHBoxLayout()
        head.addWidget(QLabel("VISUALIZER MODE"))
        self.mode_combo = QComboBox(pane)
        for mode in vp.MODES:
            self.mode_combo.addItem(mode.replace("_", " ").title(), mode)
        self.mode_combo.setMinimumWidth(240)
        self.mode_combo.currentIndexChanged.connect(self._refresh_presets)
        head.addWidget(self.mode_combo, 1)
        refresh = QPushButton("Refresh List")
        refresh.clicked.connect(self._refresh_presets)
        head.addWidget(refresh)
        body.addLayout(head)

        swap_group = QFrame(pane)
        swap_group.setObjectName("presetGroup")
        swap_layout = QVBoxLayout(swap_group)
        swap_layout.setContentsMargins(18, 15, 18, 15)
        swap_layout.setSpacing(10)
        section = QLabel("SWAP PRESET POSITIONS")
        section.setObjectName("presetHeading")
        swap_layout.addWidget(section)
        tip = QLabel("Choose two presets from this mode. Their file numbers and JSON indexes are swapped together; appearance settings are preserved.")
        tip.setObjectName("presetMuted")
        tip.setWordWrap(True)
        swap_layout.addWidget(tip)
        swap_row = QHBoxLayout()
        self.swap_first = QComboBox(swap_group)
        self.swap_second = QComboBox(swap_group)
        for cb in (self.swap_first, self.swap_second):
            cb.setMinimumWidth(220)
            cb.currentIndexChanged.connect(self._swap_selection_changed)
            swap_row.addWidget(cb, 1)
        swap_layout.addLayout(swap_row)
        self.swap_hint = QLabel("Select two different numbered presets")
        self.swap_hint.setObjectName("presetMuted")
        self.swap_hint.setWordWrap(True)
        swap_layout.addWidget(self.swap_hint)
        self.swap_btn = QPushButton("Swap Selected Presets")
        self.swap_btn.setObjectName("presetPrimary")
        self.swap_btn.clicked.connect(self._on_swap_clicked)
        swap_layout.addWidget(self.swap_btn)
        body.addWidget(swap_group)

        actions = QFrame(pane)
        actions.setObjectName("presetGroup")
        action_layout = QVBoxLayout(actions)
        action_layout.setContentsMargins(18, 15, 18, 15)
        action_layout.setSpacing(10)
        action_layout.addWidget(QLabel("REPAIR & MAINTENANCE"))
        first_row = QHBoxLayout()
        self.repair_btn = QPushButton("Repair Selected File…")
        self.repair_btn.clicked.connect(self._on_repair_clicked)
        first_row.addWidget(self.repair_btn, 1)
        self.reindex_btn = QPushButton("Reindex by Filename")
        self.reindex_btn.setToolTip("Normalize all modes in filename order. JSON index fields do not control positions.")
        self.reindex_btn.clicked.connect(self._on_reindex_clicked)
        first_row.addWidget(self.reindex_btn, 1)
        action_layout.addLayout(first_row)
        second_row = QHBoxLayout()
        self.repair_all_btn = QPushButton("Repair All")
        self.repair_all_btn.clicked.connect(self._on_repair_all_clicked)
        second_row.addWidget(self.repair_all_btn, 1)
        self.manifest_btn = QPushButton("Regenerate Existing Manifest")
        self.manifest_btn.setToolTip("Refreshes the existing source inventory without touching preset JSON")
        self.manifest_btn.clicked.connect(self._on_manifest_clicked)
        second_row.addWidget(self.manifest_btn, 1)
        action_layout.addLayout(second_row)
        self.undo_btn = QPushButton("Undo Last Change")
        self.undo_btn.clicked.connect(self._on_undo_clicked)
        action_layout.addWidget(self.undo_btn)
        body.addWidget(actions)

        self.status_label = QLabel("Ready. No authored settings will be changed by Swap or Reindex.")
        self.status_label.setObjectName("presetMuted")
        self.status_label.setWordWrap(True)
        body.addWidget(self.status_label)
        self.log = QPlainTextEdit(pane)
        self.log.setObjectName("presetLog")
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Operation history")
        body.addWidget(self.log, 1)
        self._apply_theme()
        self._refresh_presets()
        self._refresh_actions()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._theme is not None:
            from types import SimpleNamespace
            apply_native_backdrop(self, SimpleNamespace(theme=self._theme))

    def _appearance(self) -> None:
        from tools.godzip_foundry_theme import resolve_foundry_theme
        resolution = resolve_foundry_theme(self._theme_id)
        dialog = FoundryAppearanceDialog(self, title="Preset Repair Foundry",
                                         resolution=resolution, apply_theme=self._set_theme)
        dialog.show()
        # A nonmodal dialog must remain Python-owned for its entire native life.
        self._appearance_dialog = dialog

    def _set_theme(self, theme_id: str) -> None:
        self._theme_id = theme_id
        save_tool_theme_id("visualizer_preset_repair", theme_id)
        self._apply_theme()

    def _apply_theme(self) -> None:
        from types import SimpleNamespace
        resolution = resolve_tool_theme("visualizer_preset_repair")
        self._theme_id = resolution.theme_id
        self._theme = resolution.theme
        theme = resolution.theme
        def rgba(role: str) -> str:
            c = theme.color(role)
            return f"rgba({c.r},{c.g},{c.b},{c.a})"
        qss = render_foundry_stylesheet(theme, use_settings_controls=True)
        qss += f"""
            QWidget#presetRoot, QWidget#presetPane {{ background: transparent; }}
            QFrame#presetShell {{ background: {rgba('window.dialog_glass')}; border: 2px solid {rgba('panel.border')}; border-radius: 10px; }}
            QFrame#presetGroup {{ background: {rgba('panel.group.surface')}; border: 1px solid {rgba('panel.border')}; border-radius: 10px; }}
            QLabel#presetMuted {{ color: {rgba('text.secondary')}; }}
            QLabel#presetHeading {{ font-weight: 700; }}
            QPushButton#presetPrimary {{ background: {rgba('control.setup_action.surface')}; color: {rgba('control.setup_action.text')}; border-color: {rgba('control.setup_action.border')}; font-weight: 700; }}
            QPlainTextEdit#presetLog {{ border: 1px solid {rgba('panel.border')}; border-radius: 8px; }}
        """
        self.setStyleSheet(qss)
        if self.isVisible():
            apply_native_backdrop(self, SimpleNamespace(theme=theme))

    def _current_mode(self) -> str:
        value = self.mode_combo.currentData()
        if not isinstance(value, str):
            raise ValueError("Select a visualizer mode")
        return value

    def _refresh_actions(self) -> None:
        self.undo_btn.setEnabled(bool(self._history))
        self.manifest_btn.setEnabled(get_visualizer_preset_manifest_path(
            ROOT / "presets" / "visualizer_modes").is_file())
        self.manifest_btn.setToolTip("The source manifest is absent; no manifest is created" if not self.manifest_btn.isEnabled()
                                     else "Regenerate only the existing source inventory; preset files are untouched")

    def _refresh_presets(self, *_args) -> None:
        mode = self._current_mode()
        try:
            entries = _authored_mode_entries(mode)
        except Exception as exc:
            self._show_error(str(exc))
            entries = []
        previous_first, previous_second = self.swap_first.currentData(), self.swap_second.currentData()
        for cb in (self.swap_first, self.swap_second):
            cb.blockSignals(True)
            cb.clear()
            for entry in entries:
                slot = (entry.current_index + 1) if entry.current_index is not None else "?"
                suffix = re.sub(r"^preset[_-]*\d+[_-]*", "", entry.path.stem, flags=re.IGNORECASE)
                label = suffix.replace("_", " ").replace("-", " ").strip().title() or entry.path.stem
                cb.addItem(f"{slot}  ·  {label}", str(entry.path))
            cb.blockSignals(False)
        if entries:
            idx = self.swap_first.findData(previous_first)
            self.swap_first.setCurrentIndex(idx if idx >= 0 else 0)
            idx = self.swap_second.findData(previous_second)
            self.swap_second.setCurrentIndex(idx if idx >= 0 else (1 if len(entries) > 1 else 0))
        self._swap_selection_changed()
        self._refresh_actions()

    def _swap_selection_changed(self, *_args) -> None:
        p, q = self.swap_first.currentData(), self.swap_second.currentData()
        valid = isinstance(p, str) and isinstance(q, str) and p != q
        self.swap_btn.setEnabled(valid)
        self.swap_hint.setText((f"Swap {Path(p).name} ↔ {Path(q).name}" if valid
                                else "Select two different presets from the same mode"))

    def _on_swap_clicked(self) -> None:
        try:
            mode = self._current_mode()
            p, q = Path(self.swap_first.currentData()), Path(self.swap_second.currentData())
            (a, b) = swap_mode_presets(mode, p, q)
            undo_rows = ((a[0], a[2], a[1]), (b[0], b[2], b[1]))
            self._history = _record_undo_entry(UndoEntry(
                restore_path=a[0], backup_path=a[2], cleanup_path=a[1],
                related=(undo_rows[1],), expected_hashes=_undo_hashes(undo_rows)), self._history)
            _regenerate_shipped_preset_artifacts_if_needed((a[0], b[0]))
            self.status_label.setText(f"Swapped {p.stem} and {q.stem}. Undo restores both files together.")
            self._append_log(f"Swap {a[0].name} → {a[1].name}  |  {b[0].name} → {b[1].name}")
            self._refresh_presets()
            for combo, new_path in ((self.swap_first, a[1]), (self.swap_second, b[1])):
                index = combo.findData(str(new_path))
                if index >= 0:
                    combo.setCurrentIndex(index)
        except Exception as exc:
            self._show_error(str(exc))

    def _on_repair_clicked(self) -> None:
        mode = self._current_mode()
        start_dir = ROOT / "presets" / "visualizer_modes" / mode
        file_path, _ = QFileDialog.getOpenFileName(self, f"Select {mode} preset JSON/SST",
            str(start_dir if start_dir.exists() else ROOT), "JSON/SST Files (*.json *.sst);;All Files (*)")
        if file_path:
            self._repair(Path(file_path), mode)

    def _repair(self, path: Path, mode: str) -> None:
        try:
            backup, stats = repair_file(path, mode, sync_shipped_artifacts=False)
            self._history = _record_undo_entry(UndoEntry(
                path, backup, expected_hashes=(_file_digest(path),)), self._history)
            _regenerate_shipped_preset_artifacts_if_needed((path,))
            self.status_label.setText(f"Repaired {path.name}; backup saved.")
            self._append_log(f"Repair {path.name}: +{len(stats['added'])} / -{len(stats['removed'])} / adjusted {len(stats['changed'])}")
            self._refresh_presets()
        except Exception as exc:
            self._show_error(str(exc))

    def _on_repair_all_clicked(self) -> None:
        if QMessageBox.question(self, "Repair all curated presets",
             "Repair all preset payloads across all visualizer modes? Backups are retained.",
             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
             QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        failed = []
        def done(mode, path, backup, stats):
            self._history = _record_undo_entry(UndoEntry(
                path, backup, expected_hashes=(_file_digest(path),)), self._history)
            self._append_log(f"Repaired {mode}: {path.name}")
        def error(mode, path, exc):
            failed.append((path, exc))
            self._append_log(f"FAILED {mode}: {path.name}: {exc}")
        try:
            results = repair_all_presets(on_result=done, on_error=error)
            self.status_label.setText(f"Repair All: {len(results)} files updated, {len(failed)} failed.")
            self._refresh_presets()
        except Exception as exc:
            self._show_error(str(exc))

    def _on_reindex_clicked(self) -> None:
        # Reindex is a bulk file rename: make the impact explicit in the UI.
        if QMessageBox.question(self, "Reindex by filename",
             "Normalize sequential numbers across all modes in filename order?\n"
             "Existing authored settings are retained. Backups will be created.",
             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
             QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        failed = []
        undo_rows = []
        def done(mode, old, new, backup):
            undo_rows.append((old, backup, new if old != new else None))
            self._append_log(f"Reindexed {mode}: {old.name} → {new.name}")
        def error(mode, exc):
            failed.append((mode, exc))
            self._append_log(f"FAILED {mode}: {exc}")
        try:
            changes = reindex_curated_presets(on_result=done, on_error=error)
            if undo_rows:
                first, *others = undo_rows
                self._history = _record_undo_entry(UndoEntry(
                    restore_path=first[0], backup_path=first[1], cleanup_path=first[2],
                    related=tuple(others), expected_hashes=_undo_hashes(undo_rows)), self._history)
            self.status_label.setText(f"Reindex: {len(changes)} files updated, {len(failed)} modes failed.")
            self._refresh_presets()
        except Exception as exc:
            self._show_error(str(exc))

    def _on_manifest_clicked(self) -> None:
        try:
            if regenerate_existing_visualizer_manifest():
                self.status_label.setText("Existing source manifest regenerated; preset files unchanged.")
                self._append_log("Regenerated the existing manifest from current authored filenames.")
            else:
                self.status_label.setText("No source manifest exists. No action taken.")
        except Exception as exc:
            self._show_error(str(exc))
        self._refresh_actions()

    def _on_undo_clicked(self) -> None:
        if not self._history:
            return
        entry = self._history[-1]
        try:
            restore_undo_entry(entry)
            _regenerate_shipped_preset_artifacts_if_needed(
                [entry.restore_path, *(restore for restore, _backup, _cleanup in entry.related)])
            _item, self._history = _pop_undo_entry(self._history)
            self.status_label.setText("Undo restored all files in the last operation.")
            self._append_log(f"Undo: {entry.restore_path.name} ({1 + len(entry.related)} files)")
            self._refresh_presets()
        except Exception as exc:
            self._show_error(str(exc))

    def _append_log(self, text: str) -> None:
        self.log.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Preset Repair", message)
        self._append_log(f"Error: {message}")
        self.status_label.setText("Error: " + message)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Spotify visualizer preset repair tool")
    parser.add_argument(
        "--repair-all",
        action="store_true",
        help="Repair every preset JSON under presets/visualizer_modes and exit.",
    )
    parser.add_argument(
        "--mode",
        action="append",
        help="With --repair-all: only this mode's presets (repeatable).",
    )
    parser.add_argument(
        "--audit-curated",
        action="store_true",
        help="Audit curated preset JSON files for duplicate prefixes, backup blocks, and stale authored payloads.",
    )
    parser.add_argument(
        "--reindex-curated",
        action="store_true",
        help="Normalize curated preset indices and filenames into sequential preset slots per mode.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.repair_all:
        results: List[Tuple[str, Path, Path, Dict[str, Any]]] = []

        def _cli_result(mode: str, path: Path, backup: Path, stats: Dict[str, Any]) -> None:
            rel = path.relative_to(ROOT)
            print(
                f"Repaired {rel} ({mode}). Backup: {backup.name}. Added {len(stats['added'])}, "
                f"removed {len(stats['removed'])}, changed {len(stats['changed'])}.",
                flush=True,
            )

        def _cli_error(mode: str, path: Path, exc: Exception) -> None:
            rel = path.relative_to(ROOT)
            print(f"Failed to repair {rel} ({mode}): {exc}", file=sys.stderr, flush=True)

        results = repair_all_presets(modes=args.mode, on_result=_cli_result, on_error=_cli_error)
        print(f"Completed batch repair for {len(results)} preset(s).", flush=True)
        return

    if args.audit_curated:
        findings = audit_all_presets()
        if not findings:
            print("Curated preset audit passed with no issues.", flush=True)
            return
        for mode, path, report in findings:
            rel = path.relative_to(ROOT)
            summary: list[str] = []
            if report.get("read_error"):
                summary.append(f"read_error={report['read_error']}")
            if report.get("duplicate_prefixed_keys"):
                summary.append(f"duplicate_prefixed_keys={report['duplicate_prefixed_keys']}")
            if report.get("has_custom_preset_backup"):
                summary.append("has_custom_preset_backup=True")
            if report.get("deprecated_authored_keys"):
                summary.append(f"deprecated_authored_keys={report['deprecated_authored_keys']}")
            if report.get("deprecated_global_keys"):
                summary.append(f"deprecated_global_keys={report['deprecated_global_keys']}")
            if report.get("deprecated_mode_alias_keys"):
                summary.append(f"deprecated_mode_alias_keys={report['deprecated_mode_alias_keys']}")
            if report.get("legacy_spectrum_linear_notch_family"):
                summary.append("legacy_spectrum_linear_notch_family=True")
            if report.get("top_level_visualizer_duplication"):
                summary.append("top_level_visualizer_duplication=True")
            print(f"{rel} ({mode}): {'; '.join(summary)}", flush=True)
        print(f"Curated preset audit found issues in {len(findings)} preset(s).", flush=True)
        raise SystemExit(1)

    if args.reindex_curated:
        def _cli_result(mode: str, old_path: Path, new_path: Path, backup: Path) -> None:
            old_rel = old_path.relative_to(ROOT)
            new_rel = new_path.relative_to(ROOT)
            print(
                f"Reindexed {old_rel} ({mode}) -> {new_rel}. Backup: {backup.name}.",
                flush=True,
            )

        def _cli_error(mode: str, exc: Exception) -> None:
            print(f"Failed to reindex {mode}: {exc}", file=sys.stderr, flush=True)

        results = reindex_curated_presets(on_result=_cli_result, on_error=_cli_error)
        print(f"Completed curated preset reindex for {len(results)} preset(s).", flush=True)
        return

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication.instance() or QApplication(sys.argv)
    window = VisualizerPresetRepairApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
