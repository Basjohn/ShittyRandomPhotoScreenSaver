"""Interactive preset repair tool for Spotify visualizer JSON/SST payloads.

This GUI utility lets us select a visualizer mode, pick a curated preset JSON or
an SST snapshot, then prunes irrelevant keys and fills any missing defaults for
that mode. Every repair writes a .bak copy next to the file and exposes an Undo
button to revert the most recent change per session.
"""
from __future__ import annotations

import json
import shutil
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Tuple

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


def _load_visualizer_defaults() -> Dict[str, Any]:
    global _DEFAULTS_CACHE
    if _DEFAULTS_CACHE is None:
        from core.settings import default_settings

        defaults = deepcopy(default_settings.DEFAULT_SETTINGS["widgets"]["spotify_visualizer"])
        _DEFAULTS_CACHE = defaults
    return deepcopy(_DEFAULTS_CACHE)


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
    base = vp._filter_settings_for_mode(mode, defaults)  # type: ignore[attr-defined]

    original_filtered: Dict[str, Any] = {}
    for section in sections:
        migrated = vp._migrate_preset_settings(mode, dict(section))  # type: ignore[attr-defined]
        filtered = vp._filter_settings_for_mode(mode, migrated)  # type: ignore[attr-defined]
        original_filtered.update(filtered)
        base.update(filtered)

    sanitized = dict(base)

    orig_keys = set(original_filtered.keys())
    new_keys = set(sanitized.keys())

    added = sorted(new_keys - orig_keys)
    removed = sorted(orig_keys - new_keys)
    changed = sorted(
        key for key in (new_keys & orig_keys) if sanitized.get(key) != original_filtered.get(key)
    )

    stats = {"added": added, "removed": removed, "changed": changed}
    return sanitized, stats


def _apply_cleaned_settings(payload: Dict[str, Any], cleaned: Mapping[str, Any]) -> list[str]:
    updated_paths: list[str] = []

    snapshot = payload.get("snapshot")
    if isinstance(snapshot, dict):
        widgets = snapshot.get("widgets")
        if isinstance(widgets, dict):
            widgets["spotify_visualizer"] = dict(cleaned)
            updated_paths.append("snapshot.widgets.spotify_visualizer")
        custom_backup = snapshot.get("custom_preset_backup")
        if isinstance(custom_backup, dict):
            prefix = "widgets.spotify_visualizer."
            for key in list(custom_backup.keys()):
                if key.startswith(prefix):
                    del custom_backup[key]
            for key, value in cleaned.items():
                custom_backup[f"{prefix}{key}"] = value
            updated_paths.append("snapshot.custom_preset_backup")

    widgets_section = payload.get("widgets")
    if isinstance(widgets_section, dict):
        widgets_section["spotify_visualizer"] = dict(cleaned)
        updated_paths.append("widgets.spotify_visualizer")

    if not updated_paths and isinstance(payload.get("spotify_visualizer"), dict):
        payload["spotify_visualizer"] = dict(cleaned)
        updated_paths.append("spotify_visualizer")

    return updated_paths


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
    updated_paths = _apply_cleaned_settings(payload, cleaned)
    if not updated_paths:
        raise ValueError("Unable to locate spotify_visualizer section to update")

    backup_path = _ensure_backup(path)
    new_text = json.dumps(payload, indent=2, sort_keys=True)
    path.write_text(new_text + "\n", encoding="utf-8")

    stats = {
        "updated_paths": updated_paths,
        "added": stats["added"],
        "removed": stats["removed"],
        "changed": stats["changed"],
    }
    return backup_path, stats


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


def main() -> None:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication.instance() or QApplication(sys.argv)
    window = VisualizerPresetRepairApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
