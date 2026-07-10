"""Standalone GUI for editing canonical Normal and MC default settings.

The tree is generated recursively from the live canonical defaults API, so new
settings appear automatically. Saved changes are stored as compact profile
overrides rather than rewriting the large base defaults literal. Regeneration
runs in fresh Python processes so generated JSON and both SST snapshots see the
new module immediately.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from copy import deepcopy
from pathlib import Path
from pprint import pformat
import subprocess
import sys
import time
from typing import Any, Callable, Iterable, Mapping

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyledItemDelegate,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.settings.defaults import (  # noqa: E402
    MC_PROFILE,
    NORMAL_PROFILE,
    get_base_default_settings,
    merge_default_overrides,
)
from ui.settings_theme import load_theme  # noqa: E402

PROFILE_OVERRIDES_PATH = REPO_ROOT / "core" / "settings" / "default_profile_overrides.py"
SNAPSHOT_REGEN_SCRIPT = REPO_ROOT / "tools" / "regenerate_defaults_snapshot_artifacts.py"
SST_REGEN_SCRIPT = REPO_ROOT / "tools" / "regenerate_sst_defaults.py"
PROFILE_LABELS = {
    NORMAL_PROFILE: "Normal / Screensaver",
    MC_PROFILE: "Media Center / MC",
}

PATH_ROLE = int(Qt.ItemDataRole.UserRole) + 1
VALUE_ROLE = int(Qt.ItemDataRole.UserRole) + 2
TYPE_ROLE = int(Qt.ItemDataRole.UserRole) + 3
_MISSING = object()
_NO_DEFAULT = object()
_PROFILE_MODULE_HEADER = '''"""Profile-specific canonical default overrides.

This small data module is written by ``tools/default_settings_editor.py``.
Normal overrides apply to both builds; MC overrides apply on top for the
``Screensaver_MC`` profile. Stable profile names keep generated SST artifacts
and runtime reset behavior on the same source.
"""
from __future__ import annotations


'''

_SECTION_DESCRIPTIONS = {
    "accessibility": "accessibility and display-protection behavior",
    "display": "image presentation and rendering behavior",
    "input": "interaction and pointer behavior",
    "mc": "Media Center window behavior",
    "queue": "image queue behavior",
    "sources": "local and feed source selection",
    "timing": "screensaver timing and cadence",
    "transitions": "transition selection and rendering",
    "ui": "settings and application interface behavior",
    "widgets": "overlay widget presentation and placement",
    "workers": "background worker availability and capacity",
}


def _profile_payload(overrides: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        NORMAL_PROFILE: deepcopy(dict(overrides.get(NORMAL_PROFILE, {}))),
        MC_PROFILE: deepcopy(dict(overrides.get(MC_PROFILE, {}))),
    }


def render_profile_overrides_module(overrides: Mapping[str, Any]) -> str:
    """Render deterministic importable Python for the small profile overlay."""

    payload = _profile_payload(overrides)
    return (
        _PROFILE_MODULE_HEADER
        + "PROFILE_DEFAULT_OVERRIDES = "
        + pformat(payload, width=100, sort_dicts=True)
        + "\n"
    )


def load_profile_overrides(path: Path = PROFILE_OVERRIDES_PATH) -> dict[str, dict[str, Any]]:
    """Read only the literal override assignment without executing the module."""

    source = path.read_text(encoding="utf-8")
    parsed = ast.parse(source, filename=str(path))
    for node in parsed.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(target, ast.Name) and target.id == "PROFILE_DEFAULT_OVERRIDES" for target in targets):
            continue
        value = ast.literal_eval(node.value)
        if not isinstance(value, Mapping):
            break
        return _profile_payload(value)
    raise ValueError(f"{path} does not define a literal PROFILE_DEFAULT_OVERRIDES mapping")


def deep_difference(base: Mapping[str, Any], target: Mapping[str, Any]) -> dict[str, Any]:
    """Return only target leaves that differ from the inherited mapping."""

    difference: dict[str, Any] = {}
    for key, value in target.items():
        inherited = base.get(key, _MISSING)
        if isinstance(inherited, Mapping) and isinstance(value, Mapping):
            nested = deep_difference(inherited, value)
            if nested:
                difference[key] = nested
        elif inherited is _MISSING or inherited != value:
            difference[key] = deepcopy(value)
    return difference


def build_profile_models(
    base: Mapping[str, Any],
    overrides: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    normal = merge_default_overrides(base, overrides.get(NORMAL_PROFILE, {}))
    mc = merge_default_overrides(normal, overrides.get(MC_PROFILE, {}))
    return {NORMAL_PROFILE: normal, MC_PROFILE: mc}


def build_profile_overrides(
    base: Mapping[str, Any],
    models: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    normal = dict(models[NORMAL_PROFILE])
    mc = dict(models[MC_PROFILE])
    return {
        NORMAL_PROFILE: deep_difference(base, normal),
        MC_PROFILE: deep_difference(normal, mc),
    }


def iter_leaf_settings(
    mapping: Mapping[str, Any],
    prefix: tuple[str, ...] = (),
) -> Iterable[tuple[tuple[str, ...], Any]]:
    """Yield every editable leaf, treating an empty mapping as a value."""

    for key, value in mapping.items():
        path = (*prefix, str(key))
        if isinstance(value, Mapping) and value:
            yield from iter_leaf_settings(value, path)
        else:
            yield path, value


def get_path(mapping: Mapping[str, Any], path: tuple[str, ...], default: Any = _NO_DEFAULT) -> Any:
    current: Any = mapping
    for part in path:
        if not isinstance(current, Mapping) or part not in current:
            if default is _NO_DEFAULT:
                raise KeyError(".".join(path))
            return default
        current = current[part]
    return current


def set_path(mapping: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = mapping
    for part in path[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[path[-1]] = deepcopy(value)


def leaf_paths(mapping: Mapping[str, Any]) -> set[tuple[str, ...]]:
    return {path for path, _value in iter_leaf_settings(mapping)}


def format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)) or value is None:
        return json.dumps(value, ensure_ascii=True, separators=(", ", ": "))
    return str(value)


def value_type_name(value: Any) -> str:
    if value is None:
        return "null / JSON"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "decimal"
    if isinstance(value, str):
        return "text"
    if isinstance(value, list):
        return "list / JSON"
    if isinstance(value, dict):
        return "mapping / JSON"
    return type(value).__name__


def _pretty_name(raw: str) -> str:
    return raw.replace("_", " ").strip().title()


def setting_tooltip(path: tuple[str, ...], value: Any, profile: str) -> str:
    """Generate a useful tooltip for every current and future setting leaf."""

    key = path[-1]
    label = _pretty_name(key)
    owner = _pretty_name(path[-2]) if len(path) > 1 else _pretty_name(path[0])
    section = _SECTION_DESCRIPTIONS.get(path[0], f"{_pretty_name(path[0])} behavior")
    if key == "enabled" or key.startswith("show_") or key.startswith("use_"):
        explanation = f"Controls whether {label.lower()} is enabled for {owner}."
    elif "opacity" in key:
        explanation = f"Sets the default transparency level for {owner}'s {label.lower()}."
    elif key.endswith("color") or "_color_" in key:
        explanation = f"Sets the default colour value used by {owner} for {label.lower()}."
    elif key in {"mode", "type", "shape", "position", "monitor", "direction", "alignment"} or key.endswith("_mode"):
        explanation = f"Selects the default {label.lower()} used by {owner}."
    elif any(token in key for token in ("duration", "interval", "refresh", "timeout", "rate")):
        explanation = f"Sets the default timing or cadence for {owner}'s {label.lower()}."
    elif any(token in key for token in ("width", "height", "size", "radius", "margin", "padding")):
        explanation = f"Sets the default geometry value for {owner}'s {label.lower()}."
    elif any(token in key for token in ("count", "limit", "maximum", "minimum", "max_", "min_")):
        explanation = f"Sets the default capacity or boundary for {owner}'s {label.lower()}."
    elif any(token in key for token in ("path", "folder", "file")):
        explanation = f"Sets the default path used by {owner} for {label.lower()}."
    else:
        explanation = f"Sets {label.lower()} for {owner} within {section}."
    profile_text = PROFILE_LABELS.get(profile, profile)
    return (
        f"{explanation}\n\n"
        f"Key: {'.'.join(path)}\n"
        f"Profile view: {profile_text}\n"
        f"Value type: {value_type_name(value)}\n\n"
        "These defaults affect fresh profiles and Reset to Defaults. Runtime-enforced policy may still supersede a value."
    )


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)


def default_undo_path() -> Path:
    local_root = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    return local_root / "SRPSS" / "DefaultSettingsEditor" / "most_recent_undo.json"


def write_undo_record(source_text: str, path: Path | None = None) -> Path:
    undo_path = path or default_undo_path()
    payload = {
        "schema_version": 1,
        "created_at": time.time(),
        "source_text": source_text,
    }
    atomic_write_text(undo_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return undo_path


def read_undo_record(path: Path | None = None) -> str | None:
    undo_path = path or default_undo_path()
    if not undo_path.exists():
        return None
    try:
        payload = json.loads(undo_path.read_text(encoding="utf-8"))
        source = payload.get("source_text") if isinstance(payload, Mapping) else None
        return source if isinstance(source, str) and "PROFILE_DEFAULT_OVERRIDES" in source else None
    except Exception:
        return None


def regenerate_default_artifacts() -> str:
    """Regenerate JSON plus Normal and MC SST snapshots in fresh processes."""

    output: list[str] = []
    for script in (SNAPSHOT_REGEN_SCRIPT, SST_REGEN_SCRIPT):
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        combined = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        if combined:
            output.append(combined)
        if result.returncode != 0:
            raise RuntimeError(combined or f"{script.name} exited with {result.returncode}")
    return "\n".join(output)


class DefaultsTree(QTreeWidget):
    """Restrict editing to the value column while retaining keyboard editing."""

    def edit(self, index: QModelIndex, trigger, event) -> bool:  # noqa: ANN001
        if index.column() != 1 or not index.data(PATH_ROLE):
            return False
        return super().edit(index, trigger, event)


class DefaultValueDelegate(QStyledItemDelegate):
    validation_failed = Signal(str)

    def createEditor(self, parent, option, index):  # noqa: ANN001, N802
        value = index.data(VALUE_ROLE)
        if isinstance(value, bool):
            editor = QComboBox(parent)
            editor.addItem("true", True)
            editor.addItem("false", False)
            return editor
        if isinstance(value, int):
            editor = QSpinBox(parent)
            editor.setRange(-2_147_483_648, 2_147_483_647)
            return editor
        if isinstance(value, float):
            editor = QDoubleSpinBox(parent)
            editor.setRange(-1_000_000_000.0, 1_000_000_000.0)
            editor.setDecimals(6)
            editor.setSingleStep(0.1)
            return editor
        return QLineEdit(parent)

    def setEditorData(self, editor, index) -> None:  # noqa: ANN001, N802
        value = index.data(VALUE_ROLE)
        if isinstance(editor, QComboBox):
            editor.setCurrentIndex(0 if bool(value) else 1)
        elif isinstance(editor, QSpinBox):
            editor.setValue(int(value))
        elif isinstance(editor, QDoubleSpinBox):
            editor.setValue(float(value))
        elif isinstance(editor, QLineEdit):
            editor.setText(format_value(value))
            editor.selectAll()

    def setModelData(self, editor, model: QAbstractItemModel, index: QModelIndex) -> None:  # noqa: ANN001, N802
        original = index.data(VALUE_ROLE)
        try:
            if isinstance(editor, QComboBox):
                value = bool(editor.currentData())
            elif isinstance(editor, QSpinBox):
                value = int(editor.value())
            elif isinstance(editor, QDoubleSpinBox):
                value = float(editor.value())
            elif isinstance(original, str):
                value = editor.text()
            else:
                value = json.loads(editor.text())
                if isinstance(original, list) and not isinstance(value, list):
                    raise ValueError("Expected a JSON list")
                if isinstance(original, dict) and not isinstance(value, dict):
                    raise ValueError("Expected a JSON object")
            model.setData(index, deepcopy(value), VALUE_ROLE)
            model.setData(index, format_value(value), Qt.ItemDataRole.EditRole)
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self.validation_failed.emit(f"Value was not changed: {exc}")


class DefaultSettingsEditor(QMainWindow):
    def __init__(
        self,
        *,
        overrides_path: Path = PROFILE_OVERRIDES_PATH,
        undo_path: Path | None = None,
        regenerate: Callable[[], str] = regenerate_default_artifacts,
    ) -> None:
        super().__init__()
        self._overrides_path = Path(overrides_path)
        self._undo_path = undo_path or default_undo_path()
        self._regenerate = regenerate
        self._base = get_base_default_settings()
        self._overrides = load_profile_overrides(self._overrides_path)
        self._models = build_profile_models(self._base, self._overrides)
        self._initial_models = deepcopy(self._models)
        self._mc_explicit_paths = leaf_paths(self._overrides.get(MC_PROFILE, {}))
        self._profile = NORMAL_PROFILE
        self._building_tree = False
        self._leaf_items: dict[tuple[str, ...], QTreeWidgetItem] = {}

        self.setWindowTitle("SRPSS Defaults Foundry")
        self.resize(1220, 790)
        self.setMinimumSize(940, 620)
        self._build_ui()
        self._reload_tree()
        self._update_undo_state()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("defaultsFoundryRoot")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("DEFAULTS FOUNDRY")
        title.setObjectName("defaultsFoundryTitle")
        title.setFont(QFont("Jost", 24, QFont.Weight.Black))
        layout.addWidget(title)
        subtitle = QLabel(
            "Edit every canonical fresh-install/reset value. New settings appear automatically; current user profiles are not modified."
        )
        subtitle.setObjectName("defaultsFoundrySubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        profile_label = QLabel("Build Profile")
        controls.addWidget(profile_label)
        self.profile_combo = QComboBox()
        for profile in (NORMAL_PROFILE, MC_PROFILE):
            self.profile_combo.addItem(PROFILE_LABELS[profile], profile)
        self.profile_combo.setMinimumWidth(210)
        self.profile_combo.setToolTip(
            "Normal changes become shared defaults. MC changes are stored only when they differ from the resolved Normal value."
        )
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        controls.addWidget(self.profile_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search dotted keys, labels, values, or types...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_filter)
        controls.addWidget(self.search_edit, stretch=1)
        self.count_label = QLabel()
        controls.addWidget(self.count_label)
        layout.addLayout(controls)

        self.tree = DefaultsTree()
        self.tree.setObjectName("defaultsFoundryTree")
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Setting", "Default Value", "Type", "Layer"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.tree.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        delegate = DefaultValueDelegate(self.tree)
        delegate.validation_failed.connect(self._set_status)
        self.tree.setItemDelegateForColumn(1, delegate)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, stretch=1)

        actions = QHBoxLayout()
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("defaultsFoundryStatus")
        actions.addWidget(self.status_label, stretch=1)
        self.discard_button = QPushButton("Discard Unsaved")
        self.discard_button.clicked.connect(self._discard_unsaved)
        actions.addWidget(self.discard_button)
        self.undo_button = QPushButton("Undo Most Recent and Regenerate")
        self.undo_button.clicked.connect(self._undo_and_regenerate)
        actions.addWidget(self.undo_button)
        self.save_button = QPushButton("Save and Regenerate Defaults")
        self.save_button.setObjectName("defaultsFoundryPrimary")
        self.save_button.clicked.connect(self._save_and_regenerate)
        actions.addWidget(self.save_button)
        layout.addLayout(actions)

        load_theme(self)
        self.setStyleSheet(
            self.styleSheet()
            + """
            QWidget#defaultsFoundryRoot {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(13, 24, 30, 255), stop:0.55 rgba(24, 30, 31, 255), stop:1 rgba(41, 34, 24, 255));
                color: #f4f0e6;
                font-family: 'Jost', 'Segoe UI';
            }
            QLabel#defaultsFoundryTitle { color: #f4c66d; letter-spacing: 2px; }
            QLabel#defaultsFoundrySubtitle { color: #c8d4d1; font-size: 12px; padding-bottom: 4px; }
            QTreeWidget#defaultsFoundryTree {
                background-color: rgba(10, 15, 17, 218);
                alternate-background-color: rgba(31, 38, 38, 205);
                border: 1px solid rgba(225, 193, 127, 150);
                border-radius: 10px;
                color: #edf1ed;
                outline: none;
            }
            QTreeWidget#defaultsFoundryTree::item { min-height: 25px; padding: 2px 5px; }
            QTreeWidget#defaultsFoundryTree::item:selected { background: rgba(60, 108, 103, 210); }
            QHeaderView::section {
                background: rgba(31, 47, 48, 245); color: #f4c66d; border: none;
                border-right: 1px solid rgba(255, 255, 255, 35); padding: 8px; font-weight: 700;
            }
            QPushButton#defaultsFoundryPrimary {
                background: #d59b42; color: #11191a; border-color: #ffd995; font-weight: 800;
            }
            QPushButton#defaultsFoundryPrimary:hover { background: #efb65a; }
            QLabel#defaultsFoundryStatus { color: #9fc9bd; }
            """
        )

    def _on_profile_changed(self) -> None:
        self._profile = str(self.profile_combo.currentData() or NORMAL_PROFILE)
        self._reload_tree()

    def _origin_for(self, path: tuple[str, ...]) -> str:
        if self._profile == NORMAL_PROFILE:
            return "Normal override" if get_path(self._base, path, _MISSING) != get_path(self._models[NORMAL_PROFILE], path) else "Base"
        return "MC override" if get_path(self._models[NORMAL_PROFILE], path, _MISSING) != get_path(self._models[MC_PROFILE], path) else "Inherited"

    def _reload_tree(self) -> None:
        self._building_tree = True
        self.tree.clear()
        self._leaf_items.clear()
        model = self._models[self._profile]

        def _add(parent: QTreeWidgetItem | None, key: str, value: Any, path: tuple[str, ...]) -> None:
            container = self.tree if parent is None else parent
            if isinstance(value, Mapping) and value:
                item = QTreeWidgetItem(container, [_pretty_name(key), "", "section", ""])
                item.setData(0, PATH_ROLE, None)
                item.setForeground(0, QColor("#f4c66d"))
                item.setFont(0, QFont("Jost", 10, QFont.Weight.Bold))
                item.setToolTip(0, _SECTION_DESCRIPTIONS.get(path[0], f"{_pretty_name(key)} settings"))
                for child_key, child_value in value.items():
                    _add(item, str(child_key), child_value, (*path, str(child_key)))
                return

            item = QTreeWidgetItem(
                container,
                [_pretty_name(key), format_value(value), value_type_name(value), self._origin_for(path)],
            )
            item.setData(0, PATH_ROLE, path)
            item.setData(1, PATH_ROLE, path)
            item.setData(1, VALUE_ROLE, deepcopy(value))
            item.setData(1, TYPE_ROLE, value_type_name(value))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            tooltip = setting_tooltip(path, value, self._profile)
            for column in range(4):
                item.setToolTip(column, tooltip)
            if value != get_path(self._initial_models[self._profile], path, _MISSING):
                item.setForeground(1, QColor("#f4c66d"))
            self._leaf_items[path] = item

        for top_key, top_value in model.items():
            _add(None, str(top_key), top_value, (str(top_key),))
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setExpanded(False)
        self._building_tree = False
        self.count_label.setText(f"{len(self._leaf_items)} settings")
        self._apply_filter(self.search_edit.text())
        self._set_status(f"Viewing {PROFILE_LABELS[self._profile]} defaults.")

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._building_tree or column != 1:
            return
        path = item.data(1, PATH_ROLE)
        if not isinstance(path, tuple):
            return
        value = item.data(1, VALUE_ROLE)
        if self._profile == NORMAL_PROFILE:
            old_normal = get_path(self._models[NORMAL_PROFILE], path)
            set_path(self._models[NORMAL_PROFILE], path, value)
            if path not in self._mc_explicit_paths and get_path(self._models[MC_PROFILE], path, _MISSING) == old_normal:
                set_path(self._models[MC_PROFILE], path, value)
        else:
            set_path(self._models[MC_PROFILE], path, value)
            self._mc_explicit_paths.add(path)
        self._building_tree = True
        try:
            item.setText(3, self._origin_for(path))
            initial = get_path(self._initial_models[self._profile], path, _MISSING)
            item.setForeground(1, QColor("#f4c66d") if value != initial else QColor("#edf1ed"))
        finally:
            self._building_tree = False
        self._set_status(f"Unsaved change: {'.'.join(path)}")

    def _apply_filter(self, text: str) -> None:
        needle = text.strip().lower()

        def _visit(item: QTreeWidgetItem) -> bool:
            child_match = False
            for index in range(item.childCount()):
                child_match = _visit(item.child(index)) or child_match
            own = " ".join(item.text(column) for column in range(4)).lower()
            path = item.data(0, PATH_ROLE) or item.data(1, PATH_ROLE)
            if isinstance(path, tuple):
                own += " " + ".".join(path).lower()
            matches = not needle or needle in own or child_match
            item.setHidden(not matches)
            if needle and child_match:
                item.setExpanded(True)
            return matches

        for index in range(self.tree.topLevelItemCount()):
            _visit(self.tree.topLevelItem(index))

    def _set_status(self, message: str) -> None:
        self.status_label.setText(message)

    def _set_actions_enabled(self, enabled: bool) -> None:
        self.save_button.setEnabled(enabled)
        self.undo_button.setEnabled(enabled and read_undo_record(self._undo_path) is not None)
        self.discard_button.setEnabled(enabled)

    def _update_undo_state(self) -> None:
        self.undo_button.setEnabled(read_undo_record(self._undo_path) is not None)

    def _save_and_regenerate(self) -> None:
        source_before = self._overrides_path.read_text(encoding="utf-8")
        undo_before = self._undo_path.read_text(encoding="utf-8") if self._undo_path.exists() else None
        overrides = build_profile_overrides(self._base, self._models)
        source_after = render_profile_overrides_module(overrides)
        self._set_actions_enabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            write_undo_record(source_before, self._undo_path)
            atomic_write_text(self._overrides_path, source_after)
            output = self._regenerate()
        except Exception as exc:
            atomic_write_text(self._overrides_path, source_before)
            rollback_error: Exception | None = None
            try:
                self._regenerate()
            except Exception as rollback_exc:
                rollback_error = rollback_exc
            if undo_before is None:
                self._undo_path.unlink(missing_ok=True)
            else:
                atomic_write_text(self._undo_path, undo_before)
            message = str(exc)
            if rollback_error is not None:
                message += f"\n\nArtifact rollback also failed: {rollback_error}"
            QMessageBox.critical(self, "Defaults Not Saved", message)
            self._set_status(
                "Save failed; profile overrides and the previous undo record were restored."
                if rollback_error is None
                else "Save failed; profile overrides were restored, but generated artifacts need regeneration."
            )
        else:
            self._overrides = overrides
            self._initial_models = deepcopy(self._models)
            self._mc_explicit_paths = leaf_paths(overrides.get(MC_PROFILE, {}))
            self._reload_tree()
            self._set_status(output.splitlines()[-1] if output else "Defaults and generated artifacts saved.")
        finally:
            QApplication.restoreOverrideCursor()
            self._set_actions_enabled(True)
            self._update_undo_state()

    def _undo_and_regenerate(self) -> None:
        restored_source = read_undo_record(self._undo_path)
        if restored_source is None:
            self._update_undo_state()
            return
        current_source = self._overrides_path.read_text(encoding="utf-8")
        self._set_actions_enabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            atomic_write_text(self._overrides_path, restored_source)
            output = self._regenerate()
        except Exception as exc:
            atomic_write_text(self._overrides_path, current_source)
            rollback_error: Exception | None = None
            try:
                self._regenerate()
            except Exception as rollback_exc:
                rollback_error = rollback_exc
            message = str(exc)
            if rollback_error is not None:
                message += f"\n\nArtifact rollback also failed: {rollback_error}"
            QMessageBox.critical(self, "Undo Failed", message)
            self._set_status(
                "Undo failed; current profile overrides and artifacts were restored."
                if rollback_error is None
                else "Undo failed; current profile overrides were restored, but generated artifacts need regeneration."
            )
        else:
            self._undo_path.unlink(missing_ok=True)
            self._overrides = load_profile_overrides(self._overrides_path)
            self._models = build_profile_models(self._base, self._overrides)
            self._initial_models = deepcopy(self._models)
            self._mc_explicit_paths = leaf_paths(self._overrides.get(MC_PROFILE, {}))
            self._reload_tree()
            self._set_status(output.splitlines()[-1] if output else "Most recent save undone and artifacts regenerated.")
        finally:
            QApplication.restoreOverrideCursor()
            self._set_actions_enabled(True)
            self._update_undo_state()

    def _discard_unsaved(self) -> None:
        self._overrides = load_profile_overrides(self._overrides_path)
        self._models = build_profile_models(self._base, self._overrides)
        self._initial_models = deepcopy(self._models)
        self._mc_explicit_paths = leaf_paths(self._overrides.get(MC_PROFILE, {}))
        self._reload_tree()
        self._set_status("Unsaved edits discarded.")

    def smoke_check(self) -> tuple[int, int]:
        leaves = len(self._leaf_items)
        tooltips = sum(1 for item in self._leaf_items.values() if item.toolTip(1).strip())
        if leaves == 0 or tooltips != leaves:
            raise RuntimeError(f"Defaults editor smoke check failed leaves={leaves} tooltips={tooltips}")
        return leaves, tooltips


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Edit and regenerate SRPSS defaults")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Build the offscreen-compatible UI, validate discovery/tooltips, and exit",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    app = QApplication.instance() or QApplication(sys.argv)
    window = DefaultSettingsEditor()
    if args.smoke_test:
        leaves, tooltips = window.smoke_check()
        print(f"[DEFAULTS_EDITOR] leaves={leaves} tooltips={tooltips}")
        window.close()
        return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
