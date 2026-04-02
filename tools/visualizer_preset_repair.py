"""Interactive preset repair tool for Spotify visualizer JSON/SST payloads.

This GUI utility lets us select a visualizer mode, pick a curated preset JSON or
an SST snapshot, then prunes irrelevant keys and fills any missing defaults for
that mode. Repairs keep a recoverable backup copy, but backups live under the
repo temp area instead of polluting the curated preset tree itself.

It also exposes a batch "Repair All" action (both via CLI and GUI button) that
walks the curated preset tree, sanitising every JSON file automatically.
"""
from __future__ import annotations

import argparse
import json
import shutil
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
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings import visualizer_presets as vp  # noqa: E402
from core.settings.visualizer_settings_snapshot import (  # noqa: E402
    _TECHNICAL_GLOBAL_KEYS,
    normalize_visualizer_mode_payload,
)
from core.visualizer_preset_manifest import regenerate_repo_shipped_visualizer_preset_artifacts  # noqa: E402

_DEFAULTS_CACHE: Dict[str, Any] | None = None
_MANDATORY_TECH_SUFFIXES: Tuple[str, ...] = tuple(sorted(_TECHNICAL_GLOBAL_KEYS))

_DEPRECATED_COMPAT_TECH_SUFFIXES: Tuple[str, ...] = (
    "energy_boost",
    "use_raw_energy",
)
_DEPRECATED_AUTHORED_GLOBAL_KEYS: Tuple[str, ...] = (
    "ghosting_enabled",
    "ghost_alpha",
    "ghost_decay",
)
_DEPRECATED_MODE_ALIAS_KEYS: Dict[str, Tuple[str, ...]] = {
    "oscilloscope": ("osc_sensitivity",),
}
_DEPRECATED_BLOB_AUTHORED_KEYS: Tuple[str, ...] = (
    "blob_pulse_cap",
    "blob_stage_gain",
    "blob_core_scale",
    "blob_core_floor_bias",
    "blob_stage_bias",
    "blob_stage2_release_ms",
    "blob_stage3_release_ms",
    "blob_stretch_tendency",
    "blob_stretch_inner",
    "blob_stretch_outer",
)

_MODE_TECH_PREFIXES: Dict[str, str] = {
    "spectrum": "spectrum_",
    "bubble": "bubble_",
    "blob": "blob_",
    "sine_wave": "sine_wave_",
    "oscilloscope": "oscilloscope_",
}

_BACKUP_ROOT = ROOT / "temp" / "visualizer_preset_backups"


@dataclass
class ReindexEntry:
    mode: str
    path: Path
    payload: Dict[str, Any]
    current_index: int | None
    suffix: str | None


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


def _required_repair_default_keys_for_mode(mode: str) -> set[str]:
    raw_defaults = _load_visualizer_defaults()
    return {
        key
        for key in _canonical_mode_defaults(mode).keys()
        if key != "mode" and key in raw_defaults
    }


def _canonical_mode_prefix(mode: str) -> str:
    prefixes = vp.MODE_KEY_PREFIXES.get(mode)  # type: ignore[attr-defined]
    if prefixes:
        return prefixes[0]
    return f"{mode}_"


def _ensure_mandatory_per_mode_defaults(
    mode: str,
    sanitized: Dict[str, Any],
    defaults: Mapping[str, Any],
) -> None:
    for key in _required_repair_default_keys_for_mode(mode):
        if key not in sanitized and key in defaults:
            sanitized[key] = deepcopy(defaults[key])


def _promote_global_technical_settings(mode: str, sanitized: Dict[str, Any]) -> None:
    """Copy legacy global tech settings (e.g. manual_floor) into per-mode keys."""

    prefix = _MODE_TECH_PREFIXES.get(mode, _canonical_mode_prefix(mode))
    for suffix in _MANDATORY_TECH_SUFFIXES:
        global_key = suffix
        mode_key = f"{prefix}{suffix}"
        if global_key in sanitized:
            if mode_key not in sanitized:
                sanitized[mode_key] = sanitized[global_key]
            sanitized.pop(global_key, None)


def _strip_deprecated_curated_keys(mode: str, sanitized: Dict[str, Any]) -> None:
    """Curated authored payloads should not keep deprecated compat keys alive."""
    prefix = _MODE_TECH_PREFIXES.get(mode, _canonical_mode_prefix(mode))
    for suffix in _DEPRECATED_COMPAT_TECH_SUFFIXES:
        sanitized.pop(suffix, None)
        sanitized.pop(f"{prefix}{suffix}", None)
    if mode == "blob":
        for key in _DEPRECATED_BLOB_AUTHORED_KEYS:
            sanitized.pop(key, None)


def _collect_sections(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    sections = list(vp._collect_visualizer_sections(payload))  # type: ignore[attr-defined]
    if not sections and isinstance(payload.get("spotify_visualizer"), Mapping):
        sections.append(payload["spotify_visualizer"])  # type: ignore[arg-type]
    return sections


def _sanitize_settings(mode: str, payload: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, list[str]]]:
    sections = _collect_sections(payload)
    if not sections:
        raise ValueError("File does not contain any spotify_visualizer settings block")

    filtered_defaults = _canonical_mode_defaults(mode)

    base: Dict[str, Any] = {}

    original_filtered: Dict[str, Any] = {}
    for section in sections:
        migrated = vp._migrate_preset_settings(mode, dict(section))  # type: ignore[attr-defined]
        filtered = vp._filter_settings_for_mode(mode, migrated)  # type: ignore[attr-defined]
        original_filtered.update(filtered)
        base.update(filtered)

    sanitized = vp.normalize_visualizer_mode_payload(mode, base)  # type: ignore[attr-defined]
    _promote_global_technical_settings(mode, sanitized)
    _ensure_mandatory_per_mode_defaults(mode, sanitized, filtered_defaults)
    _strip_deprecated_curated_keys(mode, sanitized)

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
        "has_custom_preset_backup": False,
        "deprecated_authored_keys": [],
        "deprecated_global_keys": [],
        "deprecated_mode_alias_keys": [],
        "top_level_visualizer_duplication": False,
    }
    prefixes = tuple(vp.MODE_KEY_PREFIXES.get(mode, (_canonical_mode_prefix(mode),)))  # type: ignore[attr-defined]

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
            if any(prefix and key.startswith(f"{prefix}{prefix}") for prefix in prefixes):
                issues["duplicate_prefixed_keys"].append(key)
            if any(key.endswith(suffix) for suffix in _DEPRECATED_COMPAT_TECH_SUFFIXES):
                issues["deprecated_authored_keys"].append(key)
            if mode == "blob" and key in _DEPRECATED_BLOB_AUTHORED_KEYS:
                issues["deprecated_authored_keys"].append(key)
            if key in _DEPRECATED_AUTHORED_GLOBAL_KEYS:
                issues["deprecated_global_keys"].append(key)
            if key in _DEPRECATED_MODE_ALIAS_KEYS.get(mode, ()):
                issues["deprecated_mode_alias_keys"].append(key)

    issues["duplicate_prefixed_keys"] = sorted(set(issues["duplicate_prefixed_keys"]))
    issues["deprecated_authored_keys"] = sorted(set(issues["deprecated_authored_keys"]))
    issues["deprecated_global_keys"] = sorted(set(issues["deprecated_global_keys"]))
    issues["deprecated_mode_alias_keys"] = sorted(set(issues["deprecated_mode_alias_keys"]))
    issues["problem_count"] = (
        len(issues["duplicate_prefixed_keys"])
        + len(issues["deprecated_authored_keys"])
        + len(issues["deprecated_global_keys"])
        + len(issues["deprecated_mode_alias_keys"])
        + int(bool(issues["has_custom_preset_backup"]))
        + int(bool(issues["top_level_visualizer_duplication"]))
    )
    return issues


def _build_clean_payload(path: Path, payload: Mapping[str, Any], mode: str, cleaned: Mapping[str, Any]) -> Tuple[Dict[str, Any], list[str]]:
    """Rebuild a lean preset payload containing only sanitized visualizer settings."""

    lean: Dict[str, Any] = {}
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


def _ensure_backup(path: Path) -> Path:
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
        target_dir = (_BACKUP_ROOT / relative.parent).resolve()
    except Exception:
        target_dir = _BACKUP_ROOT.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    base = target_dir / f"{path.name}.bak"
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = target_dir / f"{path.name}.bak{counter}"
        counter += 1
    shutil.copy2(path, candidate)
    return candidate


def _reindex_preset_name(original_name: str, target_index: int) -> str:
    """Update only the 'Preset N' prefix number; preserve everything else verbatim.

    For names that already start with 'Preset N', only the number is replaced.
    For markerless names (no 'Preset N' prefix), the name is wrapped as
    'Preset N (OriginalName)' so the result is consistent with the canonical
    format while keeping the original descriptive text intact.
    """
    if not original_name:
        return f"Preset {target_index + 1}"
    updated = re.sub(
        r"^[Pp]reset[\s_-]*\d+",
        f"Preset {target_index + 1}",
        original_name,
    )
    if updated != original_name:
        return updated
    return f"Preset {target_index + 1} ({original_name})"


def _cleanup_suffix_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"[_-]+", " ", str(value)).strip()
    cleaned = cleaned.strip("() ")
    return cleaned or None


def _suffix_from_payload_name(name: Any) -> str | None:
    if not isinstance(name, str):
        return None
    candidate = name.strip()
    if not candidate:
        return None
    match = re.match(r"^preset[\s_-]*\d+(?:[\s_-]*\((.+)\)|[\s_-]+(.+))?$", candidate, flags=re.IGNORECASE)
    if match:
        return _cleanup_suffix_text(match.group(1) or match.group(2))
    return _cleanup_suffix_text(candidate)


def _suffix_from_path_stem(path: Path) -> str | None:
    inferred = vp._infer_suffix_from_name(path.stem)  # type: ignore[attr-defined]
    if inferred:
        return _cleanup_suffix_text(inferred)
    stem = re.sub(r"^preset[\s_-]*\d+[\s_-]*", "", path.stem, flags=re.IGNORECASE).strip()
    return _cleanup_suffix_text(stem)


def _slugify_suffix(suffix: str | None) -> str:
    if not suffix:
        return ""
    slug = re.sub(r"[^a-z0-9]+", "_", suffix.lower()).strip("_")
    return slug


def _load_reindex_entry(mode: str, path: Path) -> ReindexEntry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Payload root must be a JSON object")
    current_index = payload.get("preset_index")
    if not isinstance(current_index, int):
        current_index = vp._infer_preset_index_from_name(path.stem)  # type: ignore[attr-defined]
    suffix = _suffix_from_payload_name(payload.get("name")) or _suffix_from_path_stem(path)
    return ReindexEntry(
        mode=mode,
        path=path,
        payload=payload,
        current_index=current_index,
        suffix=suffix,
    )


def _ordered_reindex_entries(entries: List[ReindexEntry]) -> List[ReindexEntry]:
    indexed = sorted(
        [entry for entry in entries if entry.current_index is not None],
        key=lambda entry: (int(entry.current_index), entry.path.name.lower()),
    )
    unindexed = sorted(
        [entry for entry in entries if entry.current_index is None],
        key=lambda entry: entry.path.name.lower(),
    )

    ordered: List[ReindexEntry] = []
    target_index = 0
    while indexed or unindexed:
        if indexed and indexed[0].current_index == target_index:
            ordered.append(indexed.pop(0))
        elif unindexed and (not indexed or int(indexed[0].current_index) > target_index):
            ordered.append(unindexed.pop(0))
        elif indexed:
            ordered.append(indexed.pop(0))
        else:
            ordered.append(unindexed.pop(0))
        target_index += 1
    return ordered


def _canonical_reindexed_payload(entry: ReindexEntry, target_index: int) -> Dict[str, Any]:
    payload = deepcopy(entry.payload)
    payload["preset_index"] = target_index
    original_name = str(entry.payload.get("name") or "").strip()
    payload["name"] = _reindex_preset_name(original_name, target_index)
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

    temp_dir = mode_dir / ".reindex_tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    backups: List[Tuple[Path, Path]] = []
    results: List[Tuple[Path, Path, Path]] = []
    try:
        for index, (entry, final_path, _final_payload, final_text) in enumerate(changed_plans):
            backup = _ensure_backup(entry.path)
            backups.append((entry.path, backup))
            staged_path = temp_dir / f"{index:03d}.json"
            staged_path.write_text(final_text, encoding="utf-8")
            results.append((entry.path, final_path, backup))

        for entry, _final_path, _final_payload, _final_text in changed_plans:
            if entry.path.exists():
                entry.path.unlink()

        for index, (_entry, final_path, _final_payload, _final_text) in enumerate(changed_plans):
            staged_path = temp_dir / f"{index:03d}.json"
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(staged_path), str(final_path))
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


def repair_file(path: Path, mode: str) -> Tuple[Path, Dict[str, Any]]:
    try:
        raw_text = path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except Exception as exc:  # pragma: no cover - GUI path
        raise ValueError(f"Failed to read JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Payload root must be a JSON object")

    cleaned, stats = _sanitize_settings(mode, payload)
    lean_payload, updated_paths = _build_clean_payload(path, payload, mode, cleaned)

    backup_path = _ensure_backup(path)
    new_text = json.dumps(lean_payload, indent=2, sort_keys=True)
    path.write_text(new_text + "\n", encoding="utf-8")

    stats = {
        "updated_paths": updated_paths,
        "added": stats["added"],
        "removed": stats["removed"],
        "changed": stats["changed"],
    }
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
    regenerate_repo_shipped_visualizer_preset_artifacts(ROOT)


def repair_all_presets(
    *,
    on_result: Callable[[str, Path, Path, Dict[str, Any]], None] | None = None,
    on_error: Callable[[str, Path, Exception], None] | None = None,
) -> List[Tuple[str, Path, Path, Dict[str, Any]]]:
    """Repair every curated preset JSON under presets/visualizer_modes."""

    processed: List[Tuple[str, Path, Path, Dict[str, Any]]] = []
    for mode, path in _discover_preset_files():
        try:
            backup, stats = repair_file(path, mode)
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


class VisualizerPresetRepairApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Visualizer Preset Repair")
        self.resize(720, 460)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("Select a visualizer mode:"))

        self.mode_list = QListWidget()
        for mode in vp.MODES:
            QListWidgetItem(mode, self.mode_list)
        self.mode_list.setCurrentRow(0)
        main_layout.addWidget(self.mode_list)

        btn_row = QHBoxLayout()
        self.repair_btn = QPushButton("Select File and Repair…")
        self.repair_btn.clicked.connect(self._on_repair_clicked)
        btn_row.addWidget(self.repair_btn)

        self.undo_btn = QPushButton("Undo Last Repair")
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._on_undo_clicked)
        btn_row.addWidget(self.undo_btn)

        self.repair_all_btn = QPushButton("Repair All Presets Found")
        self.repair_all_btn.clicked.connect(self._on_repair_all_clicked)
        btn_row.addWidget(self.repair_all_btn)

        self.reindex_btn = QPushButton("Reindex Curated Presets")
        self.reindex_btn.clicked.connect(self._on_reindex_clicked)
        btn_row.addWidget(self.reindex_btn)
        main_layout.addLayout(btn_row)

        self.status_label = QLabel("Ready.")
        main_layout.addWidget(self.status_label)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        main_layout.addWidget(self.log, stretch=1)

        self._history: list[Tuple[Path, Path]] = []

    def _current_mode(self) -> str:
        item = self.mode_list.currentItem()
        if not item:
            raise ValueError("Select a visualizer mode first")
        return item.text()

    def _on_repair_clicked(self) -> None:
        try:
            mode = self._current_mode()
        except ValueError as exc:
            self._show_error(str(exc))
            return

        start_dir = ROOT / "presets" / "visualizer_modes" / mode
        if not start_dir.exists():
            start_dir = ROOT

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {mode} preset JSON/SST",
            str(start_dir),
            "JSON/SST Files (*.json *.sst);;All Files (*)",
        )
        if not file_path:
            return

        self._repair(Path(file_path), mode)

    def _repair(self, path: Path, mode: str) -> None:
        try:
            backup, stats = repair_file(path, mode)
        except Exception as exc:
            self._show_error(str(exc))
            return

        self._history.append((path, backup))
        self.undo_btn.setEnabled(True)

        msg = (
            f"Repaired {path.name} ({mode}). Updated {', '.join(stats['updated_paths'])}.\n"
            f"Added {len(stats['added'])}, removed {len(stats['removed'])}, changed {len(stats['changed'])}."
        )
        self._append_log(msg)
        self.status_label.setText(f"Saved changes to {path.name} (backup: {backup.name}).")

    def _on_repair_all_clicked(self) -> None:
        files = _discover_preset_files()
        if not files:
            self._append_log("No preset JSON files found under presets/visualizer_modes.")
            self.status_label.setText("No preset files found.")
            return

        self.repair_all_btn.setEnabled(False)
        repaired = 0
        failed = 0

        def _handle_result(mode: str, path: Path, backup: Path, stats: Dict[str, Any]) -> None:
            nonlocal repaired
            repaired += 1
            self._history.append((path, backup))
            rel = path.relative_to(ROOT)
            msg = (
                f"Repaired {rel} ({mode}). Updated {', '.join(stats['updated_paths'])}. "
                f"Added {len(stats['added'])}, removed {len(stats['removed'])}, changed {len(stats['changed'])}."
            )
            self._append_log(msg)

        def _handle_error(mode: str, path: Path, exc: Exception) -> None:
            nonlocal failed
            failed += 1
            rel = path.relative_to(ROOT)
            self._append_log(f"Failed to repair {rel} ({mode}): {exc}")

        try:
            repair_all_presets(on_result=_handle_result, on_error=_handle_error)
        finally:
            self.repair_all_btn.setEnabled(True)

        if self._history:
            self.undo_btn.setEnabled(True)

        summary = f"Batch repair complete: {repaired} updated"
        if failed:
            summary += f", {failed} failed"
        summary += "."
        self.status_label.setText(summary)

    def _on_reindex_clicked(self) -> None:
        self.reindex_btn.setEnabled(False)
        updated = 0
        failed = 0

        def _handle_result(mode: str, old_path: Path, new_path: Path, backup: Path) -> None:
            nonlocal updated
            updated += 1
            self._history.append((old_path, backup))
            old_rel = old_path.relative_to(ROOT)
            new_rel = new_path.relative_to(ROOT)
            self._append_log(
                f"Reindexed {old_rel} ({mode}) -> {new_rel}. Backup: {backup.name}."
            )

        def _handle_error(mode: str, exc: Exception) -> None:
            nonlocal failed
            failed += 1
            self._append_log(f"Failed to reindex {mode}: {exc}")

        try:
            reindex_curated_presets(on_result=_handle_result, on_error=_handle_error)
        finally:
            self.reindex_btn.setEnabled(True)

        if self._history:
            self.undo_btn.setEnabled(True)

        summary = f"Curated preset reindex complete: {updated} updated"
        if failed:
            summary += f", {failed} failed"
        summary += "."
        self.status_label.setText(summary)

    def _on_undo_clicked(self) -> None:
        if not self._history:
            return
        path, backup = self._history.pop()
        try:
            shutil.copy2(backup, path)
        except Exception as exc:
            self._show_error(f"Failed to restore backup: {exc}")
            return

        self._append_log(f"Restored {path.name} from {backup.name}.")
        self.status_label.setText(f"Undo complete for {path.name}.")
        if not self._history:
            self.undo_btn.setEnabled(False)

    def _append_log(self, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log.appendPlainText(f"[{timestamp}] {text}")

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Preset Repair", message)
        self._append_log(f"Error: {message}")
        self.status_label.setText("Error")


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Spotify visualizer preset repair tool")
    parser.add_argument(
        "--repair-all",
        action="store_true",
        help="Repair every preset JSON under presets/visualizer_modes and exit.",
    )
    parser.add_argument(
        "--audit-curated",
        action="store_true",
        help="Audit curated preset JSON files for duplicate prefixes, backup blocks, and stale authored payloads.",
    )
    parser.add_argument(
        "--reindex-curated",
        action="store_true",
        help="Normalize curated preset indices, names, and filenames into sequential preset slots per mode.",
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

        results = repair_all_presets(on_result=_cli_result, on_error=_cli_error)
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
