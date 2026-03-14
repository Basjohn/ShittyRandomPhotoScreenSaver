"""Interactive preset repair tool for Spotify visualizer JSON/SST payloads.

This GUI utility lets us select a visualizer mode, pick a curated preset JSON or
an SST snapshot, then prunes irrelevant keys and fills any missing defaults for
that mode. Every repair writes a .bak copy next to the file and exposes an Undo
button to revert the most recent change per session.

It also exposes a batch "Repair All" action (both via CLI and GUI button) that
walks the curated preset tree, sanitising every JSON file automatically.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

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

_DEFAULTS_CACHE: Dict[str, Any] | None = None
_MANDATORY_TECH_SUFFIXES: Tuple[str, ...] = (
    "manual_floor",
    "dynamic_floor",
    "adaptive_sensitivity",
    "sensitivity",
    "audio_block_size",
    "dynamic_range_enabled",
    "bar_count",
)

_MANDATORY_MODE_VISUAL_SUFFIXES: Dict[str, Tuple[str, ...]] = {
    "oscilloscope": (
        "glow_enabled",
        "glow_intensity",
        "glow_reactivity",
        "glow_size",
        "glow_color",
        "reactive_glow",
        "line_color",
    ),
    "sine_wave": (
        "glow_enabled",
        "glow_intensity",
        "glow_reactivity",
        "glow_size",
        "glow_color",
        "reactive_glow",
        "line_color",
    ),
}

_MANDATORY_SPECTRUM_SHAPING: Dict[str, Any] = {
    "spectrum_bass_emphasis": 0.5,
    "spectrum_vocal_position": 0.4,
    "spectrum_mid_suppression": 0.5,
    "spectrum_wave_amplitude": 0.5,
    "spectrum_profile_floor": 0.12,
    "spectrum_mirrored": True,
    "spectrum_shape_nodes": [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]],
}


def _load_visualizer_defaults() -> Dict[str, Any]:
    global _DEFAULTS_CACHE
    if _DEFAULTS_CACHE is None:
        from core.settings import default_settings

        defaults = deepcopy(default_settings.DEFAULT_SETTINGS["widgets"]["spotify_visualizer"])
        _DEFAULTS_CACHE = defaults
    return deepcopy(_DEFAULTS_CACHE)


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
    prefix = _canonical_mode_prefix(mode)
    for suffix in _MANDATORY_TECH_SUFFIXES:
        key = f"{prefix}{suffix}"
        if key not in sanitized and key in defaults:
            sanitized[key] = defaults[key]

    for suffix in _MANDATORY_MODE_VISUAL_SUFFIXES.get(mode, ()): 
        key = f"{prefix}{suffix}"
        if key not in sanitized and key in defaults:
            sanitized[key] = defaults[key]


def _collect_sections(payload: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    sections = list(vp._collect_visualizer_sections(payload))  # type: ignore[attr-defined]
    if not sections and isinstance(payload.get("spotify_visualizer"), Mapping):
        sections.append(payload["spotify_visualizer"])  # type: ignore[arg-type]
    return sections


def _sanitize_settings(mode: str, payload: Mapping[str, Any]) -> Tuple[Dict[str, Any], Dict[str, list[str]]]:
    sections = _collect_sections(payload)
    if not sections:
        raise ValueError("File does not contain any spotify_visualizer settings block")

    defaults = _load_visualizer_defaults()
    defaults["mode"] = mode
    filtered_defaults = vp._filter_settings_for_mode(mode, defaults)  # type: ignore[attr-defined]

    base: Dict[str, Any] = {}

    original_filtered: Dict[str, Any] = {}
    for section in sections:
        migrated = vp._migrate_preset_settings(mode, dict(section))  # type: ignore[attr-defined]
        filtered = vp._filter_settings_for_mode(mode, migrated)  # type: ignore[attr-defined]
        original_filtered.update(filtered)
        base.update(filtered)

    sanitized = dict(base)
    _ensure_mandatory_per_mode_defaults(mode, sanitized, filtered_defaults)
    if mode == "spectrum":
        for _sk, _sv in _MANDATORY_SPECTRUM_SHAPING.items():
            if _sk not in sanitized:
                sanitized[_sk] = _sv

    orig_keys = set(original_filtered.keys())
    new_keys = set(sanitized.keys())

    added = sorted(new_keys - orig_keys)
    removed = sorted(orig_keys - new_keys)
    changed = sorted(
        key for key in (new_keys & orig_keys) if sanitized.get(key) != original_filtered.get(key)
    )

    stats = {"added": added, "removed": removed, "changed": changed}
    return sanitized, stats


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

    custom_backup = {
        f"widgets.spotify_visualizer.{key}": deepcopy(value)
        for key, value in sv_block.items()
    }
    lean["snapshot"] = {
        "widgets": {"spotify_visualizer": deepcopy(sv_block)},
        "custom_preset_backup": custom_backup,
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

    updated_paths = ["snapshot.widgets.spotify_visualizer", "snapshot.custom_preset_backup"]
    if widgets_section:
        updated_paths.append("widgets")

    return lean, updated_paths


def _ensure_backup(path: Path) -> Path:
    base = path.with_suffix(path.suffix + ".bak")
    candidate = base
    counter = 1
    while candidate.exists():
        candidate = path.with_suffix(f"{path.suffix}.bak{counter}")
        counter += 1
    shutil.copy2(path, candidate)
    return candidate


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
    return processed


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

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication.instance() or QApplication(sys.argv)
    window = VisualizerPresetRepairApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
