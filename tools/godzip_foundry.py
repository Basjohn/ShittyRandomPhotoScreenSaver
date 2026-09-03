#!/usr/bin/env python3
"""SRPSS GODZIP Foundry — Git-aware manifest ZIP creation, apply and debris review.

Run from the repository:
    python tools/godzip_foundry.py
    python tools/godzip_foundry.py --open C:\\path\\to\\GODZIP_xxx.zip

The companion ``godzip_foundry_core.py`` owns all archive/Git mutation logic.
The UI deliberately never infers deletion from a missing ZIP member.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path, PurePosixPath
import sys
from typing import Any, Iterable


def _early_repo_root() -> Path:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--repo")
    ns, _unknown = parser.parse_known_args()
    if ns.repo:
        return Path(ns.repo).expanduser().resolve()
    script = Path(__file__).resolve()
    candidate = script.parents[1]
    if (candidate / ".git").exists() or (candidate / "core").is_dir():
        return candidate
    return Path.cwd().resolve()


def enable_windows_dpi_awareness() -> str:
    """Mirror Build Foundry's strongest-available per-monitor DPI setup."""
    if sys.platform != "win32":
        return "non-windows"
    try:
        user32 = ctypes.windll.user32
        fn = user32.SetProcessDpiAwarenessContext
        fn.argtypes = [ctypes.c_void_p]
        fn.restype = ctypes.c_bool
        if fn(ctypes.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
            return "per-monitor-v2"
    except (AttributeError, OSError, ValueError):
        pass
    try:
        shcore = ctypes.windll.shcore
        fn = shcore.SetProcessDpiAwareness
        fn.argtypes = [ctypes.c_int]
        fn.restype = ctypes.c_long
        if fn(2) in (0, -2147024891):
            return "per-monitor-v1"
    except (AttributeError, OSError, ValueError):
        pass
    try:
        if ctypes.windll.user32.SetProcessDPIAware():
            return "system-aware"
    except (AttributeError, OSError, ValueError):
        pass
    return "unavailable"


def set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "JaydeVerElst.SRPSS.GodzipFoundry"
        )
    except (AttributeError, OSError, ValueError):
        pass


_DPI_MODE = enable_windows_dpi_awareness()
set_windows_app_id()

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon
    from PySide6.QtWidgets import (
        QAbstractItemView,
        QApplication,
        QCheckBox,
        QComboBox,
        QDialog,
        QDialogButtonBox,
        QFileDialog,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPlainTextEdit,
        QProgressBar,
        QPushButton,
        QSplitter,
        QTabWidget,
        QTreeWidget,
        QTreeWidgetItem,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - user environment contract
    raise SystemExit(
        "GODZIP Foundry requires PySide6. Run it from the same SRPSS environment "
        "that runs the other PySide6 Foundries."
    ) from exc

from godzip_foundry_core import (  # noqa: E402
    ArchiveInspection,
    DebrisItem,
    GodzipError,
    PullInspection,
    RepoFile,
    RUN_DEFAULT_FLAGS,
    RUN_ENTRYPOINTS,
    apply_godzip,
    build_run_command,
    collect_log_files,
    collect_repo_files,
    create_godzip,
    create_logzip,
    discover_repo_root,
    discover_run_flags,
    discover_zip_candidates,
    generate_godzip_diff,
    git_branch,
    git_changes,
    git_commit_all,
    git_dirty,
    git_head,
    git_pull_ff_only,
    git_push_current,
    inspect_godzip,
    inspect_pull,
    launch_run_command,
    move_paths_to_deleteme,
    read_debris_manifest,
    repo_venv_python,
    run_flag_description,
    selective_sync_from_remote,
    suggested_godzip_name,
    suggested_logzip_path,
    validate_repo_relpath,
    write_debris_manifest,
)

APP_TITLE = "SRPSS GODZIP Foundry"
PERSONAL_GODZIP_DROP_DIR = Path(r"Z:\Torrents\Torrentfiles")

# Build Foundry's palette, translated to Qt/QSS.
COLORS = {
    "root": "#0d181e",
    "shell_border": "#ffffff",
    "titlebar": "#0c0c0c",
    "panel": "#10191b",
    "panel_alt": "#1f2626",
    "panel_hover": "#263b3a",
    "border": "#8f7950",
    "text": "#f4f0e6",
    "muted": "#c8d4d1",
    "faint": "#7d918e",
    "amber": "#f4c66d",
    "amber_dark": "#d59b42",
    "amber_hover": "#efb65a",
    "green": "#9fc9bd",
    "red": "#ef7f7f",
    "close_hover": "#e81123",
}

ROLE_PAYLOAD = int(Qt.ItemDataRole.UserRole)
ROLE_PATH = ROLE_PAYLOAD + 1
ROLE_KIND = ROLE_PAYLOAD + 2


def human_size(value: int) -> str:
    size = float(max(0, int(value)))
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def modified_stamp(path: Path) -> str:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return "date unknown"


def _resolved_foundry_icon(repo_root: Path) -> Path | None:
    for path in (
        repo_root / "images" / "foundries" / "SRPSSGodZIP.ico",
        repo_root / "images" / "foundries" / "SRPSSBuild.ico",
        repo_root / "SRPSS.ico",
    ):
        if path.is_file():
            return path.resolve()
    return None


def _inside_repo(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError as exc:
        raise GodzipError(f"Path is outside the repository: {path}") from exc


_LOCAL_STATE_DIR = ".godzip_foundry"
_LOCAL_SETTINGS_FILE = "settings.json"


def _local_settings_path(repo_root: Path) -> Path:
    """Return the repo-bound Foundry settings path. Never use global app data."""
    return repo_root.resolve() / _LOCAL_STATE_DIR / _LOCAL_SETTINGS_FILE


def _load_local_settings(repo_root: Path) -> dict[str, Any]:
    path = _local_settings_path(repo_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_local_setting(repo_root: Path, key: str, value: Any) -> None:
    """Atomically persist a small preference inside the current repository."""
    path = _local_settings_path(repo_root)
    state = _load_local_settings(repo_root)
    state[str(key)] = value
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(state, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


class CheckPathTree(QTreeWidget):
    """Hierarchical path tree where folder checks act only on listed children."""

    def __init__(self, headers: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setColumnCount(len(headers))
        self.setHeaderLabels(headers)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(True)
        self.setSortingEnabled(False)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(headers)):
            self.header().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.itemChanged.connect(self._item_changed)
        self._changing = False
        self._folders: dict[tuple[str, ...], QTreeWidgetItem] = {}

    def clear(self) -> None:  # type: ignore[override]
        self._folders.clear()
        super().clear()

    def add_path(
        self,
        path: str,
        values: list[str],
        *,
        checked: bool,
        payload: Any,
        kind: str = "file",
    ) -> QTreeWidgetItem:
        parts = PurePosixPath(path).parts
        if not parts:
            raise ValueError("empty tree path")
        parent: QTreeWidgetItem | None = None
        for depth, part in enumerate(parts[:-1], start=1):
            key = tuple(parts[:depth])
            folder = self._folders.get(key)
            if folder is None:
                folder = QTreeWidgetItem([part] + [""] * (self.columnCount() - 1))
                folder.setData(0, ROLE_KIND, "folder")
                folder.setFlags(
                    folder.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsAutoTristate
                )
                folder.setCheckState(0, Qt.CheckState.Unchecked)
                font = folder.font(0)
                font.setBold(True)
                folder.setFont(0, font)
                if parent is None:
                    self.addTopLevelItem(folder)
                else:
                    parent.addChild(folder)
                self._folders[key] = folder
            parent = folder
        row = [parts[-1]] + values[1:]
        item = QTreeWidgetItem(row)
        item.setData(0, ROLE_KIND, kind)
        item.setData(0, ROLE_PATH, path)
        item.setData(0, ROLE_PAYLOAD, payload)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        item.setToolTip(0, path)
        if parent is None:
            self.addTopLevelItem(item)
        else:
            parent.addChild(item)
        return item

    def _set_descendants(self, item: QTreeWidgetItem, state: Qt.CheckState) -> None:
        for index in range(item.childCount()):
            child = item.child(index)
            child.setCheckState(0, state)
            if child.childCount():
                self._set_descendants(child, state)

    def _item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._changing or column != 0:
            return
        if item.data(0, ROLE_KIND) != "folder":
            return
        state = item.checkState(0)
        if state == Qt.CheckState.PartiallyChecked:
            return
        self._changing = True
        self.blockSignals(True)
        try:
            self._set_descendants(item, state)
        finally:
            self.blockSignals(False)
            self._changing = False
        self.viewport().update()

    def leaf_items(self) -> list[QTreeWidgetItem]:
        result: list[QTreeWidgetItem] = []

        def visit(item: QTreeWidgetItem) -> None:
            if item.data(0, ROLE_KIND) != "folder":
                result.append(item)
                return
            for i in range(item.childCount()):
                visit(item.child(i))

        for i in range(self.topLevelItemCount()):
            visit(self.topLevelItem(i))
        return result

    def checked_paths(self) -> list[str]:
        return [
            str(item.data(0, ROLE_PATH))
            for item in self.leaf_items()
            if item.checkState(0) == Qt.CheckState.Checked
        ]

    def set_leaf_checks(self, predicate) -> None:
        self.blockSignals(True)
        try:
            for item in self.leaf_items():
                item.setCheckState(
                    0,
                    Qt.CheckState.Checked if predicate(item.data(0, ROLE_PAYLOAD)) else Qt.CheckState.Unchecked,
                )
        finally:
            self.blockSignals(False)
        self.viewport().update()

    def apply_filter(self, text: str) -> None:
        needle = text.strip().casefold()

        def visit(item: QTreeWidgetItem) -> bool:
            if item.data(0, ROLE_KIND) != "folder":
                visible = not needle or needle in str(item.data(0, ROLE_PATH)).casefold()
                item.setHidden(not visible)
                return visible
            any_visible = False
            for i in range(item.childCount()):
                any_visible = visit(item.child(i)) or any_visible
            item.setHidden(not any_visible)
            if needle and any_visible:
                item.setExpanded(True)
            return any_visible

        for i in range(self.topLevelItemCount()):
            visit(self.topLevelItem(i))


class Panel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("panel")


class RelationBanner(QLabel):
    def set_relation(self, relation: str, text: str) -> None:
        relation = relation if relation in {"same", "newer", "older", "diverged", "unknown"} else "unknown"
        self.setProperty("relation", relation)
        self.setText(text)
        self.style().unpolish(self)
        self.style().polish(self)


class CreateTab(QWidget):
    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self.repo_files: list[RepoFile] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        intro = Panel()
        intro_l = QVBoxLayout(intro)
        intro_l.setContentsMargins(14, 12, 14, 12)
        title = QLabel("CREATE GOD ZIP")
        title.setObjectName("sectionTitle")
        intro_l.addWidget(title)
        desc = QLabel(
            "Git-aware archive creation. Ignored files never enter the source universe. "
            "Workflow defaults keep ordinary source + all Docs + direct tests/* files selected, "
            "while themes, images, goldens and nested test payloads stay off unless explicitly selected."
        )
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        intro_l.addWidget(desc)
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter repository paths…")
        self.filter_edit.textChanged.connect(self._filter)
        controls.addWidget(self.filter_edit, 1)
        for label, handler in (
            ("Workflow Defaults", self.select_defaults),
            ("Changed Only", self.select_changed),
            ("All", self.select_all),
            ("None", self.select_none),
            ("Refresh", self.refresh),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            controls.addWidget(button)
        layout.addLayout(controls)

        self.tree = CheckPathTree(["Repository path", "Git", "Size", "Default"])
        self.tree.itemChanged.connect(lambda *_: self._update_summary())
        layout.addWidget(self.tree, 1)

        footer = Panel()
        foot = QVBoxLayout(footer)
        foot.setContentsMargins(14, 12, 14, 12)
        row = QHBoxLayout()
        self.output_edit = QLineEdit()
        local_settings = _load_local_settings(self.repo_root)
        remembered = str(local_settings.get("output_dir", str(self.repo_root.parent)))
        self.output_edit.setText(remembered)
        browse = QPushButton("Output Folder…")
        browse.clicked.connect(self.choose_output)
        row.addWidget(QLabel("Output"))
        row.addWidget(self.output_edit, 1)
        row.addWidget(browse)
        foot.addLayout(row)
        row2 = QHBoxLayout()
        self.name_edit = QLineEdit(suggested_godzip_name(self.repo_root))
        self.include_debris = QCheckBox("Include checked Manual/Imported debris instructions")
        self.include_debris.setChecked(True)
        row2.addWidget(QLabel("Name"))
        row2.addWidget(self.name_edit, 1)
        row2.addWidget(self.include_debris)
        foot.addLayout(row2)
        action = QHBoxLayout()
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        self.create_button = QPushButton("CREATE GOD ZIP")
        self.create_button.setObjectName("primaryButton")
        self.create_button.clicked.connect(self.create_archive)
        action.addWidget(self.summary, 1)
        action.addWidget(self.create_button)
        foot.addLayout(action)
        layout.addWidget(footer)

    def refresh(self) -> None:
        self.window.set_busy(True, "Scanning Git worktree…")
        try:
            self.repo_files = collect_repo_files(self.repo_root)
            self.tree.clear()
            for entry in self.repo_files:
                default_text = "workflow" if entry.default_selected else "off"
                self.tree.add_path(
                    entry.path,
                    [entry.path, entry.status or "—", human_size(entry.size), default_text],
                    checked=entry.default_selected,
                    payload=entry,
                )
            self.tree.expandToDepth(0)
            self.name_edit.setText(suggested_godzip_name(self.repo_root))
            self._update_summary()
            self.window.refresh_repo_header()
            self.window.set_status(f"Repository scan complete — {len(self.repo_files):,} Git-visible files")
        except Exception as exc:
            self.window.show_error("Repository scan failed", exc)
        finally:
            self.window.set_busy(False)

    def _filter(self, text: str) -> None:
        self.tree.apply_filter(text)

    def select_defaults(self) -> None:
        self.tree.set_leaf_checks(lambda payload: bool(payload.default_selected))
        self._update_summary()

    def select_changed(self) -> None:
        self.tree.set_leaf_checks(lambda payload: bool(payload.status))
        self._update_summary()

    def select_all(self) -> None:
        self.tree.set_leaf_checks(lambda _payload: True)
        self._update_summary()

    def select_none(self) -> None:
        self.tree.set_leaf_checks(lambda _payload: False)
        self._update_summary()

    def _update_summary(self) -> None:
        paths = set(self.tree.checked_paths())
        selected = [entry for entry in self.repo_files if entry.path in paths]
        size = sum(entry.size for entry in selected)
        dirty = sum(1 for entry in selected if entry.status)
        debris_count = len(self.window.debris_tab.entries_for_create()) if hasattr(self.window, "debris_tab") else 0
        self.summary.setText(
            f"{len(selected):,} files · {human_size(size)} · {dirty} changed/new"
            + (f" · {debris_count} pending debris" if debris_count else "")
        )
        self.create_button.setEnabled(bool(selected or debris_count))

    def choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "GODZIP output folder", self.output_edit.text())
        if path:
            self.output_edit.setText(path)
            _save_local_setting(self.repo_root, "output_dir", path)

    def create_archive(self) -> None:
        selected = self.tree.checked_paths()
        output_dir = Path(self.output_edit.text().strip() or str(self.repo_root.parent)).expanduser()
        name = self.name_edit.text().strip() or suggested_godzip_name(self.repo_root)
        if not name.lower().endswith(".zip"):
            name += ".zip"
        output = output_dir / name
        debris = self.window.debris_tab.entries_for_create() if self.include_debris.isChecked() else []
        if output.exists():
            answer = QMessageBox.question(
                self,
                "Replace existing archive?",
                f"{output.name} already exists. Replace it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.window.set_busy(True, "Hashing selected files and creating GODZIP…")
        try:
            manifest = create_godzip(self.repo_root, selected, output, debris_entries=debris)
            _save_local_setting(self.repo_root, "output_dir", str(output.parent))
            self.window.set_status(
                f"Created {output.name} — {len(manifest['files'])} files, {len(manifest['debris'])} debris instructions"
            )
            QMessageBox.information(
                self,
                "GODZIP created",
                f"Created:\n{output}\n\n"
                f"HEAD: {manifest['source_head'][:10]}\n"
                f"Dirty worktree: {'yes' if manifest['dirty_worktree'] else 'no'}\n"
                f"Manifest: .godzip/manifest.json\n\n"
                "The archive passed CRC validation before publication.",
            )
            self.name_edit.setText(suggested_godzip_name(self.repo_root))
        except Exception as exc:
            self.window.show_error("GODZIP creation failed", exc)
        finally:
            self.window.set_busy(False)


class ApplyTab(QWidget):
    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self.inspection: ArchiveInspection | None = None
        self.current_zip: Path | None = None
        self._discovery_loaded = False
        self._discovered_zips: list[Path] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        drop = Panel()
        drop.setObjectName("dropPanel")
        d = QHBoxLayout(drop)
        d.setContentsMargins(16, 14, 16, 14)
        left = QVBoxLayout()
        t = QLabel("DROP A GOD ZIP ANYWHERE ON THIS WINDOW")
        t.setObjectName("sectionTitle")
        left.addWidget(t)
        s = QLabel("Explorer drag/drop or Browse. Manifest GODZIPs get SHA-256 validation + Git ancestry proof before mutation.")
        s.setObjectName("muted")
        s.setWordWrap(True)
        left.addWidget(s)
        d.addLayout(left, 1)
        quick = QVBoxLayout()
        quick.setSpacing(6)
        quick_label = QLabel("FOUND ZIPS")
        quick_label.setObjectName("faint")
        quick.addWidget(quick_label)
        quick_row = QHBoxLayout()
        self.found_combo = QComboBox()
        self.found_combo.setMinimumWidth(360)
        self.found_combo.setToolTip(
            "Newest direct ZIPs from repo-adjacent/output locations and the optional personal drop folder."
        )
        self.found_combo.activated.connect(self._load_discovered_index)
        quick_row.addWidget(self.found_combo, 1)
        self.show_all_zips = QCheckBox("Show all ZIPs")
        self.show_all_zips.setToolTip(
            "Off: show only recognized SRPSS/GODZIP archives. On: show every direct ZIP in the quick locations."
        )
        self.show_all_zips.toggled.connect(lambda *_: self.refresh_discovered_zips(force=True))
        quick_row.addWidget(self.show_all_zips)
        refresh_found = QPushButton("↻")
        refresh_found.setToolTip("Refresh discovered ZIPs")
        refresh_found.clicked.connect(lambda: self.refresh_discovered_zips(force=True))
        quick_row.addWidget(refresh_found)
        browse = QPushButton("BROWSE GOD ZIP…")
        browse.setObjectName("primaryButton")
        browse.clicked.connect(self.browse)
        quick_row.addWidget(browse)
        quick.addLayout(quick_row)
        d.addLayout(quick)
        layout.addWidget(drop)

        info = Panel()
        info_l = QVBoxLayout(info)
        info_l.setContentsMargins(14, 12, 14, 12)
        self.archive_label = QLabel("No GODZIP loaded")
        self.archive_label.setObjectName("archiveName")
        self.archive_label.setWordWrap(True)
        info_l.addWidget(self.archive_label)
        chips = QHBoxLayout()
        self.kind_chip = QLabel("—")
        self.kind_chip.setObjectName("chip")
        self.head_chip = QLabel("source HEAD —")
        self.head_chip.setObjectName("chip")
        self.branch_chip = QLabel("branch —")
        self.branch_chip.setObjectName("chip")
        self.dirty_chip = QLabel("worktree —")
        self.dirty_chip.setObjectName("chip")
        for chip in (self.kind_chip, self.head_chip, self.branch_chip, self.dirty_chip):
            chips.addWidget(chip)
        chips.addStretch(1)
        info_l.addLayout(chips)
        self.relation = RelationBanner("Archive age cannot be proven.")
        self.relation.setWordWrap(True)
        info_l.addWidget(self.relation)
        self.warning_label = QLabel("")
        self.warning_label.setObjectName("warningText")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        info_l.addWidget(self.warning_label)
        self.strip_wrapper = QCheckBox("Legacy archive: strip detected common top-level wrapper folder")
        self.strip_wrapper.hide()
        self.strip_wrapper.toggled.connect(self._wrapper_changed)
        info_l.addWidget(self.strip_wrapper)
        layout.addWidget(info)

        tools = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("Filter archive targets…")
        self.filter_edit.textChanged.connect(self.tree_filter)
        tools.addWidget(self.filter_edit, 1)
        for label, handler in (
            ("Changes", self.select_changes),
            ("All", self.select_all),
            ("None", self.select_none),
        ):
            b = QPushButton(label)
            b.clicked.connect(handler)
            tools.addWidget(b)
        layout.addLayout(tools)

        self.tree = CheckPathTree(["Target path", "Local", "Size", "SHA-256"])
        self.tree.itemChanged.connect(lambda *_: self._update_apply_summary())
        layout.addWidget(self.tree, 1)

        bottom = Panel()
        btm = QVBoxLayout(bottom)
        btm.setContentsMargins(14, 12, 14, 12)
        opts = QHBoxLayout()
        self.rollback = QCheckBox("Create rollback snapshot of overwritten files in /deleteme")
        self.rollback.setChecked(True)
        self.include_debris = QCheckBox("Apply checked archive debris moves")
        self.include_debris.setChecked(True)
        self.include_debris.toggled.connect(self._update_apply_summary)
        opts.addWidget(self.rollback)
        opts.addWidget(self.include_debris)
        opts.addStretch(1)
        btm.addLayout(opts)
        self.older_ack = QCheckBox("I understand this archive is PROVEN OLDER than local HEAD")
        self.older_ack.setObjectName("dangerCheck")
        self.older_ack.hide()
        self.older_ack.toggled.connect(self._update_apply_summary)
        btm.addWidget(self.older_ack)
        row = QHBoxLayout()
        self.summary = QLabel("Load a GODZIP to inspect it.")
        self.summary.setObjectName("muted")
        self.apply_button = QPushButton("APPLY SELECTED")
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply_selected)
        row.addWidget(self.summary, 1)
        row.addWidget(self.apply_button)
        btm.addLayout(row)
        layout.addWidget(bottom)

    def _zip_search_dirs(self) -> list[Path]:
        return self.window.zip_search_dirs()

    def ensure_discovery_loaded(self) -> None:
        if not self._discovery_loaded:
            self.refresh_discovered_zips()

    def refresh_discovered_zips(self, *, force: bool = False) -> None:
        if self._discovery_loaded and not force:
            return
        self._discovered_zips = discover_zip_candidates(
            self._zip_search_dirs(),
            limit=40,
            project_only=not self.show_all_zips.isChecked(),
        )
        self.found_combo.blockSignals(True)
        try:
            self.found_combo.clear()
            self.found_combo.addItem("Choose a discovered ZIP…")
            for path in self._discovered_zips:
                try:
                    parent = path.parent
                    if os.name == "nt" and parent == PERSONAL_GODZIP_DROP_DIR:
                        where = "goblin drop"
                    elif parent == self.repo_root.parent:
                        where = "repo-adjacent"
                    else:
                        where = parent.name or str(parent)
                except Exception:
                    where = str(path.parent)
                self.found_combo.addItem(
                    f"{modified_stamp(path)}  —  {path.name}  —  {where}",
                    str(path),
                )
                self.found_combo.setItemData(
                    self.found_combo.count() - 1,
                    str(path),
                    Qt.ItemDataRole.ToolTipRole,
                )
            if not self._discovered_zips:
                self.found_combo.addItem("No ZIPs found in quick locations")
        finally:
            self.found_combo.blockSignals(False)
        self._discovery_loaded = True

    def _load_discovered_index(self, index: int) -> None:
        if index <= 0:
            return
        raw = self.found_combo.itemData(index)
        if raw:
            self.load_zip(Path(str(raw)))

    def browse(self) -> None:
        if self.current_zip is not None:
            start_path = self.current_zip.parent
        elif os.name == "nt" and PERSONAL_GODZIP_DROP_DIR.is_dir():
            start_path = PERSONAL_GODZIP_DROP_DIR
        else:
            candidates = self._zip_search_dirs()
            start_path = next((path for path in candidates if path.is_dir()), self.repo_root.parent)
        path, _ = QFileDialog.getOpenFileName(self, "Open GODZIP", str(start_path), "ZIP archives (*.zip);;All files (*)")
        if path:
            self.load_zip(Path(path))

    def load_zip(self, path: Path, *, preserve_wrapper_choice: bool = False) -> None:
        path = path.expanduser().resolve()
        self.window.set_busy(True, f"Inspecting {path.name}…")
        try:
            strip = self.strip_wrapper.isChecked() if preserve_wrapper_choice else False
            inspection = inspect_godzip(self.repo_root, path, strip_legacy_prefix=strip)
            self.inspection = inspection
            self.current_zip = path
            self._render_inspection()
            self.window.debris_tab.set_archive_entries(inspection, path)
            self.window.tabs.setCurrentWidget(self)
            self.window.set_status(
                f"Inspected {path.name} — {len(inspection.files)} file targets, {len(inspection.debris)} debris instructions"
            )
        except Exception as exc:
            self.window.show_error("GODZIP inspection failed", exc)
        finally:
            self.window.set_busy(False)

    def _wrapper_changed(self, _checked: bool) -> None:
        if self.current_zip is not None and self.inspection is not None and self.inspection.legacy:
            self.load_zip(self.current_zip, preserve_wrapper_choice=True)

    def _render_inspection(self) -> None:
        inspection = self.inspection
        assert inspection is not None
        self.archive_label.setText(str(inspection.zip_path))
        self.kind_chip.setText("LEGACY / UNMANIFESTED" if inspection.legacy else "MANIFEST v1")
        self.head_chip.setText(f"source {inspection.source_head[:10] if inspection.source_head else 'unknown'}")
        self.branch_chip.setText(f"branch {inspection.source_branch or 'unknown'}")
        self.dirty_chip.setText("source DIRTY" if inspection.dirty_worktree else "source clean")
        self.relation.set_relation(inspection.relation, inspection.relation_detail)
        warnings = list(inspection.warnings)
        dirty_count = sum(1 for item in inspection.files if item.local_state == "LOCAL DIRTY")
        if dirty_count:
            warnings.insert(0, f"{dirty_count} selected-capable target(s) have local uncommitted changes. Rollback snapshots are strongly recommended.")
        self.warning_label.setText("\n".join(f"• {warning}" for warning in warnings))
        self.warning_label.setVisible(bool(warnings))
        self.strip_wrapper.blockSignals(True)
        self.strip_wrapper.setVisible(bool(inspection.legacy and inspection.legacy_common_prefix))
        if inspection.legacy and inspection.legacy_common_prefix:
            self.strip_wrapper.setText(
                f"Legacy archive: strip detected wrapper “{inspection.legacy_common_prefix}/”"
            )
        self.strip_wrapper.blockSignals(False)

        self.tree.clear()
        for entry in inspection.files:
            item = self.tree.add_path(
                entry.target_path,
                [entry.target_path, entry.local_state, human_size(entry.size), entry.sha256[:12]],
                checked=entry.default_selected,
                payload=entry,
            )
            if entry.local_state == "LOCAL DIRTY":
                for col in range(self.tree.columnCount()):
                    item.setForeground(col, QColor(COLORS["red"]))
            elif entry.local_state == "NEW":
                item.setForeground(1, QColor(COLORS["green"]))
            elif entry.local_state == "SAME":
                item.setForeground(1, QColor(COLORS["faint"]))
        self.tree.expandToDepth(0)
        self.older_ack.setVisible(inspection.proven_older)
        self.older_ack.setChecked(False)
        self.include_debris.setVisible(bool(inspection.debris))
        self.include_debris.setText(
            f"Apply checked archive debris moves ({len(inspection.debris)}) — review in Debris tab"
        )
        self._update_apply_summary()

    def tree_filter(self, text: str) -> None:
        self.tree.apply_filter(text)

    def select_changes(self) -> None:
        self.tree.set_leaf_checks(lambda payload: payload.local_state != "SAME")
        self._update_apply_summary()

    def select_all(self) -> None:
        self.tree.set_leaf_checks(lambda _payload: True)
        self._update_apply_summary()

    def select_none(self) -> None:
        self.tree.set_leaf_checks(lambda _payload: False)
        self._update_apply_summary()

    def _update_apply_summary(self) -> None:
        inspection = self.inspection
        if inspection is None:
            self.apply_button.setEnabled(False)
            return
        checked = set(self.tree.checked_paths())
        chosen = [entry for entry in inspection.files if entry.target_path in checked]
        changed = [entry for entry in chosen if entry.local_state != "SAME"]
        dirty = sum(1 for entry in chosen if entry.local_state == "LOCAL DIRTY")
        debris = (
            self.window.debris_tab.checked_archive_paths(inspection.zip_path)
            if self.include_debris.isChecked()
            else []
        )
        self.summary.setText(
            f"{len(chosen)} file target(s) · {len(changed)} actual change(s)"
            + (f" · {dirty} LOCAL DIRTY" if dirty else "")
            + (f" · {len(debris)} debris move(s)" if debris else "")
        )
        age_ok = not inspection.proven_older or self.older_ack.isChecked()
        self.apply_button.setEnabled(bool(chosen or debris) and age_ok)

    def apply_selected(self) -> None:
        inspection = self.inspection
        if inspection is None:
            return
        selected = self.tree.checked_paths()
        debris = (
            self.window.debris_tab.checked_archive_paths(inspection.zip_path)
            if self.include_debris.isChecked()
            else []
        )
        dirty = [
            item.target_path
            for item in inspection.files
            if item.target_path in selected and item.local_state == "LOCAL DIRTY"
        ]
        lines = [
            f"Apply {len(selected)} manifest/legacy file target(s) from:\n{inspection.zip_path.name}"
        ]
        if debris:
            lines.append(f"Move {len(debris)} manifest debris path(s) into /deleteme.")
        if dirty:
            lines.append(f"WARNING: {len(dirty)} selected target(s) contain local uncommitted changes.")
        if inspection.proven_older:
            lines.append("WARNING: this archive is PROVEN OLDER than local HEAD.")
        lines.append("Missing archive files are NEVER interpreted as deletions.")
        answer = QMessageBox.warning(
            self,
            "Apply GODZIP?",
            "\n\n".join(lines),
            QMessageBox.StandardButton.Apply | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Apply:
            return
        self.window.set_busy(True, "Validating and transactionally applying GODZIP…")
        try:
            result = apply_godzip(
                self.repo_root,
                inspection,
                selected,
                selected_debris=debris,
                create_rollback_snapshot=self.rollback.isChecked(),
                allow_proven_older=self.older_ack.isChecked(),
            )
            detail = (
                f"Replaced: {result.replaced}\n"
                f"New files: {result.new_files}\n"
                f"Already identical: {result.unchanged_skipped}\n"
                f"Debris moved: {result.debris_moved}"
            )
            if result.backup_dir:
                detail += f"\n\nRollback snapshot:\n{result.backup_dir}"
            if result.debris_dir:
                detail += f"\n\nDebris:\n{result.debris_dir}"
            QMessageBox.information(self, "GODZIP applied", detail)
            self.window.set_status(
                f"Applied {inspection.zip_path.name} — {result.replaced} replaced, {result.new_files} new, {result.debris_moved} debris"
            )
            self.window.refresh_repo_header()
            self.window.create_tab.refresh()
            self.load_zip(inspection.zip_path, preserve_wrapper_choice=True)
        except Exception as exc:
            self.window.show_error("GODZIP apply failed", exc)
        finally:
            self.window.set_busy(False)


class DebrisTab(QWidget):
    SOURCE_MANUAL = "Manual"
    SOURCE_IMPORTED = "Imported"
    SOURCE_ARCHIVE = "Archive"

    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        intro = Panel()
        il = QVBoxLayout(intro)
        il.setContentsMargins(14, 12, 14, 12)
        title = QLabel("DEBRIS — NEVER DELETE BLINDLY")
        title.setObjectName("sectionTitle")
        il.addWidget(title)
        desc = QLabel(
            "Deletion intent is explicit. Checked paths are moved to /deleteme/<operation>/<original path>, "
            "never permanently deleted. Archive debris instructions appear here automatically."
        )
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        il.addWidget(desc)
        layout.addWidget(intro)

        row = QHBoxLayout()
        for label, handler in (
            ("Add Files…", self.add_files),
            ("Add Folder…", self.add_folder),
            ("Load Manifest / GODZIP…", self.load_manifest),
            ("Export Checked Manifest…", self.export_manifest),
            ("Remove Rows", self.remove_selected_rows),
            ("Clear Manual/Imported", self.clear_nonarchive),
        ):
            b = QPushButton(label)
            b.clicked.connect(handler)
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Path", "Source", "Exists", "Reason"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setRootIsDecorated(False)
        self.tree.setUniformRowHeights(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tree.itemChanged.connect(lambda *_: self._changed())
        layout.addWidget(self.tree, 1)

        bottom = Panel()
        bl = QHBoxLayout(bottom)
        bl.setContentsMargins(14, 12, 14, 12)
        self.summary = QLabel("No debris queued.")
        self.summary.setObjectName("muted")
        self.move_button = QPushButton("MOVE CHECKED TO /DELETEME")
        self.move_button.setObjectName("dangerButton")
        self.move_button.clicked.connect(self.move_checked)
        self.move_button.setEnabled(False)
        bl.addWidget(self.summary, 1)
        bl.addWidget(self.move_button)
        layout.addWidget(bottom)

    def _add_entry(
        self,
        path: str,
        *,
        source: str,
        reason: str = "",
        archive_path: Path | None = None,
        checked: bool = True,
    ) -> None:
        rel = validate_repo_relpath(path)
        # Deduplicate same path+source+archive.
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if (
                item.data(0, ROLE_PATH) == rel
                and item.data(0, ROLE_KIND) == source
                and item.data(0, ROLE_PAYLOAD) == (str(archive_path) if archive_path else "")
            ):
                return
        exists = (self.repo_root / Path(*PurePosixPath(rel).parts)).exists()
        item = QTreeWidgetItem([rel, source, "yes" if exists else "missing", reason])
        item.setData(0, ROLE_PATH, rel)
        item.setData(0, ROLE_KIND, source)
        item.setData(0, ROLE_PAYLOAD, str(archive_path) if archive_path else "")
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(0, Qt.CheckState.Checked if checked and exists else Qt.CheckState.Unchecked)
        if not exists:
            item.setForeground(2, QColor(COLORS["faint"]))
        self.tree.addTopLevelItem(item)
        self._changed()

    def set_archive_entries(self, inspection: ArchiveInspection, archive_path: Path) -> None:
        # Remove only archive-sourced rows; manual/imported intent survives inspection changes.
        for i in reversed(range(self.tree.topLevelItemCount())):
            if self.tree.topLevelItem(i).data(0, ROLE_KIND) == self.SOURCE_ARCHIVE:
                self.tree.takeTopLevelItem(i)
        for entry in inspection.debris:
            self._add_entry(
                entry.path,
                source=self.SOURCE_ARCHIVE,
                reason=entry.reason,
                archive_path=archive_path,
                checked=entry.exists,
            )
        self._changed()

    def checked_archive_paths(self, archive_path: Path) -> list[str]:
        key = str(archive_path.resolve())
        result = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if (
                item.data(0, ROLE_KIND) == self.SOURCE_ARCHIVE
                and item.data(0, ROLE_PAYLOAD) == key
                and item.checkState(0) == Qt.CheckState.Checked
            ):
                result.append(str(item.data(0, ROLE_PATH)))
        return result

    def entries_for_create(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.data(0, ROLE_KIND) == self.SOURCE_ARCHIVE:
                continue
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            result.append({"path": str(item.data(0, ROLE_PATH)), "reason": item.text(3)})
        return result

    def _chosen_paths(self) -> list[str]:
        return [
            str(self.tree.topLevelItem(i).data(0, ROLE_PATH))
            for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
        ]

    def _changed(self) -> None:
        checked = self._chosen_paths()
        existing = sum(
            1 for path in checked if (self.repo_root / Path(*PurePosixPath(path).parts)).exists()
        )
        self.summary.setText(
            f"{self.tree.topLevelItemCount()} queued row(s) · {len(checked)} checked · {existing} currently exist"
        )
        self.move_button.setEnabled(existing > 0)
        if hasattr(self.window, "create_tab"):
            self.window.create_tab._update_summary()
        if hasattr(self.window, "apply_tab"):
            self.window.apply_tab._update_apply_summary()

    def add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add repository debris files", str(self.repo_root), "All files (*)")
        for raw in paths:
            try:
                rel = _inside_repo(self.repo_root, Path(raw))
                self._add_entry(rel, source=self.SOURCE_MANUAL)
            except Exception as exc:
                self.window.show_error("Cannot add debris path", exc)

    def add_folder(self) -> None:
        raw = QFileDialog.getExistingDirectory(self, "Add repository debris folder", str(self.repo_root))
        if not raw:
            return
        try:
            rel = _inside_repo(self.repo_root, Path(raw))
            if rel in (".", ""):
                raise GodzipError("The repository root cannot be moved to /deleteme")
            self._add_entry(rel, source=self.SOURCE_MANUAL)
        except Exception as exc:
            self.window.show_error("Cannot add debris folder", exc)

    def load_manifest(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load debris manifest or GODZIP",
            str(self.repo_root.parent),
            "GODZIP / JSON (*.zip *.json);;All files (*)",
        )
        if not path:
            return
        try:
            entries = read_debris_manifest(Path(path))
            for entry in entries:
                self._add_entry(
                    entry["path"],
                    source=self.SOURCE_IMPORTED,
                    reason=entry.get("reason", ""),
                )
            self.window.tabs.setCurrentWidget(self)
            self.window.set_status(f"Loaded {len(entries)} debris instruction(s) from {Path(path).name}")
        except Exception as exc:
            self.window.show_error("Debris manifest load failed", exc)

    def export_manifest(self) -> None:
        checked = self._chosen_paths()
        if not checked:
            QMessageBox.information(self, "Nothing checked", "Check at least one debris path first.")
            return
        default = self.repo_root / "godzip_debris.json"
        path, _ = QFileDialog.getSaveFileName(self, "Export debris manifest", str(default), "JSON (*.json)")
        if not path:
            return
        try:
            reasons = {
                str(self.tree.topLevelItem(i).data(0, ROLE_PATH)): self.tree.topLevelItem(i).text(3)
                for i in range(self.tree.topLevelItemCount())
            }
            write_debris_manifest(Path(path), checked, reasons=reasons)
            self.window.set_status(f"Exported debris manifest: {path}")
        except Exception as exc:
            self.window.show_error("Debris manifest export failed", exc)

    def remove_selected_rows(self) -> None:
        for item in list(self.tree.selectedItems()):
            index = self.tree.indexOfTopLevelItem(item)
            if index >= 0:
                self.tree.takeTopLevelItem(index)
        self._changed()

    def clear_nonarchive(self) -> None:
        for i in reversed(range(self.tree.topLevelItemCount())):
            if self.tree.topLevelItem(i).data(0, ROLE_KIND) != self.SOURCE_ARCHIVE:
                self.tree.takeTopLevelItem(i)
        self._changed()

    def move_checked(self) -> None:
        paths = self._chosen_paths()
        existing = [path for path in paths if (self.repo_root / Path(*PurePosixPath(path).parts)).exists()]
        if not existing:
            return
        answer = QMessageBox.warning(
            self,
            "Move debris?",
            f"Move {len(existing)} checked path(s) to /deleteme?\n\nNothing is permanently deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            root, count = move_paths_to_deleteme(self.repo_root, existing, label="DEBRIS")
            QMessageBox.information(self, "Debris moved", f"Moved {count} path(s) to:\n{root}")
            self.window.set_status(f"Moved {count} debris path(s) to /deleteme")
            # Rebuild existence column without discarding intent rows.
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                rel = str(item.data(0, ROLE_PATH))
                exists = (self.repo_root / Path(*PurePosixPath(rel).parts)).exists()
                item.setText(2, "yes" if exists else "missing")
                if not exists:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
            self._changed()
            self.window.create_tab.refresh()
        except Exception as exc:
            self.window.show_error("Debris move failed", exc)



class ConfirmFileListDialog(QDialog):
    """Prominent final confirmation that exposes every affected path."""

    def __init__(self, title: str, warning: str, lines: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(760, 620)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        banner = QLabel(warning)
        banner.setObjectName("warningText")
        banner.setWordWrap(True)
        layout.addWidget(banner)
        label = QLabel(f"Review all {len(lines)} affected path(s) before continuing:")
        label.setObjectName("muted")
        layout.addWidget(label)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText("\n".join(lines) if lines else "(none)")
        layout.addWidget(text, 1)
        self.ack = QCheckBox("I reviewed the complete file list above")
        self.ack.setObjectName("dangerCheck")
        layout.addWidget(self.ack)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("CONFIRM")
        ok.setEnabled(False)
        self.ack.toggled.connect(ok.setEnabled)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class LogzipTab(QWidget):
    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self._paths: list[Path] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)
        intro = Panel()
        il = QVBoxLayout(intro)
        il.setContentsMargins(14, 12, 14, 12)
        title = QLabel("LOGZIP")
        title.setObjectName("sectionTitle")
        il.addWidget(title)
        desc = QLabel(
            "Bundles direct loose files inside /logs only. Subfolders and existing ZIPs are ignored. "
            "The archive is named from current Git HEAD; repeated bundles receive 2/3/4… suffixes. Sources are left untouched."
        )
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        il.addWidget(desc)
        layout.addWidget(intro)
        controls = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        all_b = QPushButton("All")
        all_b.clicked.connect(lambda: self._set_all(True))
        none_b = QPushButton("None")
        none_b.clicked.connect(lambda: self._set_all(False))
        controls.addWidget(refresh)
        controls.addWidget(all_b)
        controls.addWidget(none_b)
        controls.addStretch(1)
        layout.addLayout(controls)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Loose log file", "Size"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemChanged.connect(lambda *_: self._update())
        layout.addWidget(self.tree, 1)
        footer = Panel()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(14, 12, 14, 12)
        summary_box = QVBoxLayout()
        self.summary = QLabel("Not scanned yet.")
        self.summary.setObjectName("muted")
        self.destination = QLabel("")
        self.destination.setObjectName("faint")
        self.destination.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        summary_box.addWidget(self.summary)
        summary_box.addWidget(self.destination)
        self.button = QPushButton("CREATE LOGZIP")
        self.button.setObjectName("primaryButton")
        self.button.clicked.connect(self.create)
        self.button.setEnabled(False)
        fl.addLayout(summary_box, 1)
        fl.addWidget(self.button)
        layout.addWidget(footer)

    def _output_dir(self) -> Path:
        settings = _load_local_settings(self.repo_root)
        remembered = str(settings.get("output_dir", "")).strip()
        return Path(remembered).expanduser() if remembered else self.repo_root.parent

    def refresh(self) -> None:
        try:
            self._paths = collect_log_files(self.repo_root)
            self.tree.blockSignals(True)
            self.tree.clear()
            for path in self._paths:
                item = QTreeWidgetItem([path.name, human_size(path.stat().st_size)])
                item.setData(0, ROLE_PATH, path.name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                self.tree.addTopLevelItem(item)
            self.tree.blockSignals(False)
            self._update()
            self.window.set_status(f"LOGZIP scan: {len(self._paths)} direct loose /logs file(s)")
        except Exception as exc:
            self.window.show_error("LOGZIP scan failed", exc)

    def _set_all(self, checked: bool) -> None:
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(i).setCheckState(0, Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self._update()

    def _selected(self) -> list[str]:
        return [
            str(self.tree.topLevelItem(i).data(0, ROLE_PATH))
            for i in range(self.tree.topLevelItemCount())
            if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
        ]

    def _update(self) -> None:
        names = self._selected()
        by_name = {p.name: p for p in self._paths}
        size = sum(by_name[name].stat().st_size for name in names if name in by_name)
        self.summary.setText(f"{len(names)} file(s) · {human_size(size)} · HEAD {git_head(self.repo_root)[:10]}")
        try:
            target = suggested_logzip_path(self.repo_root, self._output_dir())
            self.destination.setText(f"Destination: {target}")
        except Exception as exc:
            self.destination.setText(f"Destination unavailable: {exc}")
        self.button.setEnabled(bool(names))

    def create(self) -> None:
        names = self._selected()
        self.window.set_busy(True, "Creating verified LOGZIP…")
        try:
            result = create_logzip(self.repo_root, names, output_dir=self._output_dir())
            self.window.set_status(f"Created {result.zip_path.name} from {len(result.files)} loose log file(s)")
            QMessageBox.information(
                self,
                "LOGZIP created",
                f"Created:\n{result.zip_path}\n\nFiles: {len(result.files)}\nSource logs were not removed.",
            )
            self.refresh()
        except Exception as exc:
            self.window.show_error("LOGZIP creation failed", exc)
        finally:
            self.window.set_busy(False)


class DiffResultDialog(QDialog):
    def __init__(self, parent: QWidget, title: str, text: str, summary: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1120, 820)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        heading = QLabel(summary)
        heading.setObjectName("sectionTitle")
        heading.setWordWrap(True)
        layout.addWidget(heading)
        hint = QLabel(
            "Unified text diff. Paste this directly into ChatGPT/Claude; binary changes are summarized by hash/size."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setPlainText(text)
        layout.addWidget(self.text, 1)
        buttons = QHBoxLayout()
        copy = QPushButton("COPY TO CLIPBOARD")
        copy.setObjectName("primaryButton")
        copy.clicked.connect(self.copy_all)
        close = QPushButton("CLOSE")
        close.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(copy)
        buttons.addWidget(close)
        layout.addLayout(buttons)

    def copy_all(self) -> None:
        QApplication.clipboard().setText(self.text.toPlainText())
        self.text.selectAll()


class DiffTab(QWidget):
    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self.current_zip: Path | None = None
        self._loaded = False
        self._zips: list[Path] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)
        intro = Panel()
        il = QVBoxLayout(intro)
        il.setContentsMargins(14, 12, 14, 12)
        title = QLabel("GODZIP DIFF")
        title.setObjectName("sectionTitle")
        il.addWidget(title)
        desc = QLabel(
            "Compare the current repo against a chosen GODZIP baseline. Archived bytes win for files carried by the ZIP; "
            "manifest source HEAD + current non-ignored Git changes extend the comparison so later committed/new files are visible "
            "without treating every intentional GODZIP omission as an addition."
        )
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        il.addWidget(desc)
        layout.addWidget(intro)

        chooser = Panel()
        cl = QVBoxLayout(chooser)
        cl.setContentsMargins(14, 12, 14, 12)
        row = QHBoxLayout()
        self.combo = QComboBox()
        self.combo.setMinimumWidth(500)
        self.combo.activated.connect(self._choose_index)
        row.addWidget(self.combo, 1)
        self.show_all = QCheckBox("Show all ZIPs")
        self.show_all.setToolTip("Normally only recognized SRPSS/GODZIP archives are listed.")
        self.show_all.toggled.connect(lambda *_: self.refresh(force=True))
        row.addWidget(self.show_all)
        refresh = QPushButton("↻")
        refresh.clicked.connect(lambda: self.refresh(force=True))
        row.addWidget(refresh)
        browse = QPushButton("BROWSE…")
        browse.clicked.connect(self.browse)
        row.addWidget(browse)
        cl.addLayout(row)
        self.selected = QLabel("No baseline selected")
        self.selected.setObjectName("faint")
        self.selected.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        cl.addWidget(self.selected)
        layout.addWidget(chooser)

        scope = Panel()
        sl = QVBoxLayout(scope)
        sl.setContentsMargins(14, 12, 14, 12)
        scope_title = QLabel("WHAT THE DIFF MEANS")
        scope_title.setObjectName("sectionTitle")
        sl.addWidget(scope_title)
        scope_text = QLabel(
            "It is not a GitHub web diff and it does not mutate anything. The chosen GODZIP is the baseline; the current local repo is the target. "
            "Git-ignored untracked files stay out. For a manifested baseline, its dirty archived bytes are preserved exactly."
        )
        scope_text.setObjectName("muted")
        scope_text.setWordWrap(True)
        sl.addWidget(scope_text)
        layout.addWidget(scope)
        layout.addStretch(1)

        footer = Panel()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(14, 12, 14, 12)
        self.summary = QLabel("Choose a GODZIP baseline.")
        self.summary.setObjectName("muted")
        self.button = QPushButton("GENERATE DIFF")
        self.button.setObjectName("primaryButton")
        self.button.setEnabled(False)
        self.button.clicked.connect(self.generate)
        fl.addWidget(self.summary, 1)
        fl.addWidget(self.button)
        layout.addWidget(footer)

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.refresh()

    def refresh(self, *, force: bool = False) -> None:
        if self._loaded and not force:
            return
        self._zips = discover_zip_candidates(
            self.window.zip_search_dirs(),
            limit=40,
            project_only=not self.show_all.isChecked(),
        )
        self.combo.blockSignals(True)
        try:
            self.combo.clear()
            self.combo.addItem("Choose a GODZIP baseline…")
            for path in self._zips:
                self.combo.addItem(f"{modified_stamp(path)}  —  {path.name}", str(path))
                self.combo.setItemData(self.combo.count() - 1, str(path), Qt.ItemDataRole.ToolTipRole)
            if not self._zips:
                self.combo.addItem("No matching ZIPs found")
        finally:
            self.combo.blockSignals(False)
        self._loaded = True

    def _choose_index(self, index: int) -> None:
        if index <= 0:
            return
        raw = self.combo.itemData(index)
        if raw:
            self.set_zip(Path(str(raw)))

    def set_zip(self, path: Path) -> None:
        self.current_zip = path.expanduser().resolve()
        self.selected.setText(f"Baseline: {self.current_zip} · modified {modified_stamp(self.current_zip)}")
        self.summary.setText("Ready to compare against the current local repo.")
        self.button.setEnabled(True)

    def browse(self) -> None:
        start = PERSONAL_GODZIP_DROP_DIR if os.name == "nt" and PERSONAL_GODZIP_DROP_DIR.is_dir() else self.repo_root.parent
        path, _ = QFileDialog.getOpenFileName(self, "Choose GODZIP baseline", str(start), "ZIP archives (*.zip);;All files (*)")
        if path:
            self.set_zip(Path(path))

    def generate(self) -> None:
        if self.current_zip is None:
            return
        self.window.set_busy(True, f"Diffing current repo against {self.current_zip.name}…")
        try:
            result = generate_godzip_diff(self.repo_root, self.current_zip)
            summary = (
                f"{result.changed_files} changed file(s) · {result.added} added · "
                f"{result.modified} modified · {result.deleted} deleted · {result.binary} binary"
            )
            self.summary.setText(summary)
            dialog = DiffResultDialog(self, f"GODZIP DIFF — {self.current_zip.name}", result.text, summary)
            dialog.exec()
            self.window.set_status(f"Generated DIFF against {self.current_zip.name}: {summary}")
        except Exception as exc:
            self.window.show_error("GODZIP DIFF failed", exc)
        finally:
            self.window.set_busy(False)


class PushTab(QWidget):
    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)
        intro = Panel()
        il = QVBoxLayout(intro)
        il.setContentsMargins(14, 12, 14, 12)
        title = QLabel("COMMIT / PUSH")
        title.setObjectName("sectionTitle")
        il.addWidget(title)
        desc = QLabel(
            "Commit stages every Git-visible worktree change shown below (git add -A). COMMIT & PUSH pushes only after a successful commit. "
            "No force-push, merge or rebase path exists here."
        )
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        il.addWidget(desc)
        layout.addWidget(intro)
        row = QHBoxLayout()
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        row.addStretch(1)
        layout.addLayout(row)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Git path", "State", "Index", "Worktree"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, 4):
            self.tree.header().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 1)
        box = Panel()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(14, 12, 14, 12)
        self.summary = QLabel()
        self.summary.setObjectName("muted")
        bl.addWidget(self.summary)
        msgrow = QHBoxLayout()
        self.message = QLineEdit()
        self.message.setPlaceholderText("Commit message…")
        msgrow.addWidget(QLabel("Message"))
        msgrow.addWidget(self.message, 1)
        bl.addLayout(msgrow)
        buttons = QHBoxLayout()
        self.commit_button = QPushButton("COMMIT")
        self.commit_push_button = QPushButton("COMMIT & PUSH")
        self.commit_push_button.setObjectName("primaryButton")
        self.push_button = QPushButton("PUSH EXISTING COMMITS")
        self.commit_button.clicked.connect(lambda: self.commit(push=False))
        self.commit_push_button.clicked.connect(lambda: self.commit(push=True))
        self.push_button.clicked.connect(self.push)
        buttons.addStretch(1)
        buttons.addWidget(self.commit_button)
        buttons.addWidget(self.push_button)
        buttons.addWidget(self.commit_push_button)
        bl.addLayout(buttons)
        layout.addWidget(box)

    def refresh(self) -> None:
        try:
            changes = git_changes(self.repo_root)
            self.tree.clear()
            for change in changes:
                item = QTreeWidgetItem([
                    change.path,
                    change.status,
                    "staged" if change.staged else "—",
                    "new" if change.untracked else ("modified" if change.unstaged else "—"),
                ])
                self.tree.addTopLevelItem(item)
            self.summary.setText(
                f"{len(changes)} current Git change(s) · branch {git_branch(self.repo_root)} · HEAD {git_head(self.repo_root)[:10]}"
            )
            self.commit_button.setEnabled(bool(changes))
            self.commit_push_button.setEnabled(bool(changes))
            self.window.refresh_repo_header()
        except Exception as exc:
            self.window.show_error("Git change scan failed", exc)

    def _confirm_commit(self, push: bool) -> bool:
        changes = git_changes(self.repo_root)
        lines = [f"{item.status:8} {item.path}" for item in changes]
        warning = (
            "This will stage and commit EVERY Git-visible change listed below"
            + (" and then push the resulting commit if commit succeeds." if push else ".")
        )
        return ConfirmFileListDialog("Confirm commit", warning, lines, self).exec() == QDialog.DialogCode.Accepted

    def commit(self, *, push: bool) -> None:
        message = self.message.text().strip()
        if not message:
            QMessageBox.warning(self, "Commit message required", "Enter a commit message first.")
            return
        if not self._confirm_commit(push):
            return
        self.window.set_busy(True, "Committing Git changes…")
        try:
            head = git_commit_all(self.repo_root, message)
            detail = f"Committed {head[:10]}."
            if push:
                self.window.set_status("Commit succeeded; pushing…")
                pushed = git_push_current(self.repo_root)
                detail += "\n\nPush complete."
                if pushed:
                    detail += f"\n{pushed}"
            QMessageBox.information(self, "Git operation complete", detail)
            self.message.clear()
            self.refresh()
            self.window.create_tab.refresh()
        except Exception as exc:
            self.window.show_error("Commit/push failed", exc)
        finally:
            self.window.set_busy(False)

    def push(self) -> None:
        answer = QMessageBox.warning(
            self,
            "Push current branch?",
            f"Push branch {git_branch(self.repo_root)} at HEAD {git_head(self.repo_root)[:10]}?\n\nNo force-push is permitted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.window.set_busy(True, "Pushing current branch…")
        try:
            detail = git_push_current(self.repo_root)
            QMessageBox.information(self, "Push complete", detail or "Push completed successfully.")
            self.window.refresh_repo_header()
        except Exception as exc:
            self.window.show_error("Push failed", exc)
        finally:
            self.window.set_busy(False)


class PullTab(QWidget):
    """Fetch/inspect lazily. Full PULL is strict ff-only; partial is worktree sync."""

    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self.inspection: PullInspection | None = None
        self.loaded_once = False
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)
        intro = Panel()
        il = QVBoxLayout(intro)
        il.setContentsMargins(14, 12, 14, 12)
        title = QLabel("PULL — REVIEW BEFORE MUTATION")
        title.setObjectName("sectionTitle")
        il.addWidget(title)
        desc = QLabel(
            "Nothing is fetched until this tab is opened/refreshed. Full PULL only fast-forwards a CLEAN worktree. "
            "SELECTIVE SYNC copies checked remote file states without advancing HEAD and backs overwritten local files into /deleteme."
        )
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        il.addWidget(desc)
        layout.addWidget(intro)
        row = QHBoxLayout()
        refresh = QPushButton("FETCH / REFRESH")
        refresh.setObjectName("primaryButton")
        refresh.clicked.connect(self.refresh)
        all_b = QPushButton("All")
        none_b = QPushButton("None")
        all_b.clicked.connect(lambda: self.tree.set_leaf_checks(lambda _p: True))
        none_b.clicked.connect(lambda: self.tree.set_leaf_checks(lambda _p: False))
        row.addWidget(refresh)
        row.addWidget(all_b)
        row.addWidget(none_b)
        row.addStretch(1)
        layout.addLayout(row)
        self.banner = RelationBanner()
        self.banner.set_relation("unknown", "Not fetched yet.")
        layout.addWidget(self.banner)
        self.tree = CheckPathTree(["Incoming path", "Remote", "Local"])
        self.tree.itemChanged.connect(lambda *_: self._update())
        layout.addWidget(self.tree, 1)
        footer = Panel()
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(14, 12, 14, 12)
        self.warning = QLabel(
            "FULL PULL will not run on dirty/diverged worktrees. SELECTIVE SYNC intentionally leaves local HEAD unchanged."
        )
        self.warning.setObjectName("warningText")
        self.warning.setWordWrap(True)
        fl.addWidget(self.warning)
        line = QHBoxLayout()
        self.summary = QLabel("No remote inspection yet.")
        self.summary.setObjectName("muted")
        self.sync_button = QPushButton("SELECTIVE SYNC CHECKED")
        self.sync_button.setObjectName("dangerButton")
        self.pull_button = QPushButton("PULL ALL (FF-ONLY)")
        self.pull_button.setObjectName("primaryButton")
        self.sync_button.clicked.connect(self.selective_sync)
        self.pull_button.clicked.connect(self.pull_all)
        line.addWidget(self.summary, 1)
        line.addWidget(self.sync_button)
        line.addWidget(self.pull_button)
        fl.addLayout(line)
        layout.addWidget(footer)
        self.sync_button.setEnabled(False)
        self.pull_button.setEnabled(False)

    def ensure_loaded(self) -> None:
        if not self.loaded_once:
            self.refresh()

    def refresh(self) -> None:
        self.window.set_busy(True, "Fetching remote and inspecting incoming changes…")
        try:
            inspection = inspect_pull(self.repo_root, fetch=True)
            self.inspection = inspection
            self.loaded_once = True
            relation_ui = {
                "same": "same",
                "behind": "newer",
                "ahead": "same",
                "diverged": "older",
            }.get(inspection.relation, "unknown")
            self.banner.set_relation(relation_ui, inspection.relation_detail)
            self.tree.clear()
            for entry in inspection.files:
                local = "LOCAL DIRTY" if entry.local_dirty else "clean"
                self.tree.add_path(
                    entry.path,
                    [entry.path, entry.status, local],
                    checked=True,
                    payload=entry,
                )
            self.tree.expandToDepth(0)
            self._update()
            self.window.set_status(
                f"Remote inspection: {inspection.remote_ref} {inspection.remote_head[:10]} · {len(inspection.files)} incoming path(s)"
            )
        except Exception as exc:
            self.inspection = None
            self.loaded_once = True
            self.banner.set_relation("older", f"PULL inspection failed: {exc}")
            self.tree.clear()
            self._update()
        finally:
            self.window.set_busy(False)

    def _update(self) -> None:
        inspection = self.inspection
        if inspection is None:
            self.summary.setText("No valid remote inspection.")
            self.sync_button.setEnabled(False)
            self.pull_button.setEnabled(False)
            return
        selected = self.tree.checked_paths()
        conflicts = sum(1 for item in inspection.files if item.path in selected and item.local_dirty)
        self.summary.setText(
            f"{len(inspection.files)} incoming · {len(selected)} selected"
            + (f" · {conflicts} overlap local edits" if conflicts else "")
            + (" · WORKTREE DIRTY" if inspection.worktree_dirty else " · worktree clean")
        )
        self.sync_button.setEnabled(bool(selected) and inspection.relation in {"behind", "diverged"})
        self.pull_button.setEnabled(
            inspection.relation == "behind" and not inspection.worktree_dirty and bool(inspection.files)
        )

    def _confirm(self, title: str, warning: str, entries: list) -> bool:
        lines = []
        for item in entries:
            local = " [LOCAL DIRTY]" if item.local_dirty else ""
            lines.append(f"{item.status:6} {item.display_path}{local}")
        return ConfirmFileListDialog(title, warning, lines, self).exec() == QDialog.DialogCode.Accepted

    def pull_all(self) -> None:
        inspection = self.inspection
        if inspection is None:
            return
        if not self._confirm(
            "Confirm full pull",
            "MAJOR WARNING: this will advance local HEAD and replace/delete tracked files exactly as listed. "
            "The operation is strict fast-forward only and requires a clean worktree.",
            inspection.files,
        ):
            return
        self.window.set_busy(True, "Applying reviewed fast-forward pull…")
        try:
            detail = git_pull_ff_only(self.repo_root, inspection)
            QMessageBox.information(self, "Pull complete", detail or "Fast-forward pull completed.")
            self.window.refresh_after_git_mutation()
            self.refresh()
        except Exception as exc:
            self.window.show_error("Pull failed", exc)
        finally:
            self.window.set_busy(False)

    def selective_sync(self) -> None:
        inspection = self.inspection
        if inspection is None:
            return
        selected = self.tree.checked_paths()
        chosen = [item for item in inspection.files if item.path in selected]
        if not self._confirm(
            "Confirm selective remote sync",
            "MAJOR WARNING: this does NOT advance HEAD. Checked remote states are copied into the working tree, "
            "remote deletions/rename sources are removed, and overwritten local files are backed up under /deleteme first.",
            chosen,
        ):
            return
        self.window.set_busy(True, "Synchronizing selected remote file states…")
        try:
            result = selective_sync_from_remote(self.repo_root, inspection, selected)
            detail = f"Written: {result.written}\nRemoved/renamed-away: {result.deleted}\nHEAD unchanged: {git_head(self.repo_root)[:10]}"
            if result.backup_dir:
                detail += f"\n\nRollback backup:\n{result.backup_dir}"
            QMessageBox.information(self, "Selective sync complete", detail)
            self.window.refresh_after_git_mutation()
            self.refresh()
        except Exception as exc:
            self.window.show_error("Selective sync failed", exc)
        finally:
            self.window.set_busy(False)


class RunTab(QWidget):
    """Repo-local SRPSS launcher with remembered diagnostic flag profiles."""

    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self.flag_checks: dict[str, QCheckBox] = {}
        self._flags: tuple[str, ...] = ()
        self._building = False
        self._build_ui()
        self.refresh_flags()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        intro = Panel()
        il = QVBoxLayout(intro)
        il.setContentsMargins(14, 12, 14, 12)
        title = QLabel("RUN SRPSS")
        title.setObjectName("sectionTitle")
        il.addWidget(title)
        desc = QLabel(
            "Launch the repo through its own .venv Python in a separate console. "
            "The normal console closes automatically when SRPSS exits; keep-open is opt-in."
        )
        desc.setWordWrap(True)
        desc.setObjectName("muted")
        il.addWidget(desc)
        layout.addWidget(intro)

        controls = Panel()
        cl = QVBoxLayout(controls)
        cl.setContentsMargins(14, 12, 14, 12)
        row = QHBoxLayout()
        row.addWidget(QLabel("Entrypoint"))
        self.entrypoint_combo = QComboBox()
        self.entrypoint_combo.addItems(list(RUN_ENTRYPOINTS))
        self.entrypoint_combo.currentTextChanged.connect(self._selection_changed)
        row.addWidget(self.entrypoint_combo)
        self.python_label = QLabel()
        self.python_label.setObjectName("faint")
        self.python_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        row.addWidget(self.python_label, 1)
        refresh = QPushButton("Refresh CLI")
        refresh.clicked.connect(self.refresh_flags)
        row.addWidget(refresh)
        cl.addLayout(row)
        layout.addWidget(controls)

        flags_panel = Panel()
        fl = QVBoxLayout(flags_panel)
        fl.setContentsMargins(14, 12, 14, 12)
        heading = QHBoxLayout()
        label = QLabel("RUNTIME / DIAGNOSTIC FLAGS")
        label.setObjectName("sectionTitle")
        heading.addWidget(label)
        heading.addStretch(1)
        for text, handler in (
            ("Diagnostic Default", self.select_default),
            ("All", self.select_all),
            ("None", self.select_none),
        ):
            button = QPushButton(text)
            button.clicked.connect(handler)
            heading.addWidget(button)
        fl.addLayout(heading)
        self.flags_host = QWidget()
        self.flags_grid = QGridLayout(self.flags_host)
        self.flags_grid.setContentsMargins(0, 4, 0, 0)
        self.flags_grid.setHorizontalSpacing(20)
        self.flags_grid.setVerticalSpacing(5)
        fl.addWidget(self.flags_host)
        layout.addWidget(flags_panel)

        command_panel = Panel()
        cp = QVBoxLayout(command_panel)
        cp.setContentsMargins(14, 12, 14, 12)
        cp.addWidget(QLabel("COMMAND PREVIEW"))
        self.command_preview = QLineEdit()
        self.command_preview.setReadOnly(True)
        cp.addWidget(self.command_preview)
        bottom = QHBoxLayout()
        self.keep_console = QCheckBox("Keep console open after SRPSS exits")
        self.keep_console.setToolTip(
            "Off (default): the dedicated console closes naturally with Python. "
            "On: launch through cmd /k so the console remains for inspection."
        )
        self.keep_console.stateChanged.connect(self._selection_changed)
        bottom.addWidget(self.keep_console)
        bottom.addStretch(1)
        self.launch_button = QPushButton("RUN")
        self.launch_button.setObjectName("primaryButton")
        self.launch_button.clicked.connect(self.launch)
        bottom.addWidget(self.launch_button)
        cp.addLayout(bottom)
        self.run_status = QLabel()
        self.run_status.setObjectName("muted")
        cp.addWidget(self.run_status)
        layout.addWidget(command_panel)
        layout.addStretch(1)

    def _clear_flag_widgets(self) -> None:
        while self.flags_grid.count():
            item = self.flags_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.flag_checks.clear()

    def refresh_flags(self) -> None:
        self._building = True
        try:
            self._flags = discover_run_flags(self.repo_root)
            settings = _load_local_settings(self.repo_root)
            remembered_entrypoint = str(settings.get("run_entrypoint", "main.py"))
            if remembered_entrypoint not in RUN_ENTRYPOINTS:
                remembered_entrypoint = "main.py"
            self.entrypoint_combo.setCurrentText(remembered_entrypoint)

            remembered = settings.get("run_flags")
            if isinstance(remembered, list):
                selected = {str(flag) for flag in remembered if str(flag) in self._flags}
            else:
                selected = {flag for flag in RUN_DEFAULT_FLAGS if flag in self._flags}

            self._clear_flag_widgets()
            for index, flag in enumerate(self._flags):
                check = QCheckBox(flag)
                check.setChecked(flag in selected)
                check.setToolTip(run_flag_description(flag))
                check.stateChanged.connect(self._selection_changed)
                self.flag_checks[flag] = check
                row = index // 3
                col = index % 3
                self.flags_grid.addWidget(check, row, col)

            self.keep_console.setChecked(bool(settings.get("run_keep_console_open", False)))
            python_exe = repo_venv_python(self.repo_root)
            self.python_label.setText(str(python_exe))
        except Exception as exc:
            self._flags = ()
            self._clear_flag_widgets()
            self.run_status.setText(str(exc))
        finally:
            self._building = False
        self._update_preview()

    def selected_flags(self) -> list[str]:
        return [flag for flag in self._flags if self.flag_checks.get(flag) and self.flag_checks[flag].isChecked()]

    def select_default(self) -> None:
        wanted = set(RUN_DEFAULT_FLAGS)
        for flag, check in self.flag_checks.items():
            check.setChecked(flag in wanted)
        self._update_preview()

    def select_all(self) -> None:
        for check in self.flag_checks.values():
            check.setChecked(True)
        self._update_preview()

    def select_none(self) -> None:
        for check in self.flag_checks.values():
            check.setChecked(False)
        self._update_preview()

    def _selection_changed(self, *_args) -> None:
        if not self._building:
            self._update_preview()

    def _display_command(self) -> str:
        entrypoint = self.entrypoint_combo.currentText() or "main.py"
        flags = self.selected_flags()
        if os.name == "nt":
            parts = [r".\.venv\Scripts\python.exe", rf".\{entrypoint}", *flags]
        else:
            parts = ["./.venv/bin/python", f"./{entrypoint}", *flags]
        return subprocess.list2cmdline(parts) if os.name == "nt" else " ".join(parts)

    def _update_preview(self) -> None:
        self.command_preview.setText(self._display_command())
        try:
            build_run_command(
                self.repo_root,
                self.entrypoint_combo.currentText() or "main.py",
                self.selected_flags(),
            )
            self.launch_button.setEnabled(True)
            self.run_status.setText(
                "Ready — launches in a dedicated console" +
                (" that stays open after exit." if self.keep_console.isChecked() else " that closes when SRPSS exits.")
            )
        except Exception as exc:
            self.launch_button.setEnabled(False)
            self.run_status.setText(str(exc))

    def launch(self) -> None:
        entrypoint = self.entrypoint_combo.currentText() or "main.py"
        flags = self.selected_flags()
        keep_open = self.keep_console.isChecked()
        try:
            process = launch_run_command(
                self.repo_root,
                entrypoint,
                flags,
                keep_console_open=keep_open,
            )
            _save_local_setting(self.repo_root, "run_entrypoint", entrypoint)
            _save_local_setting(self.repo_root, "run_flags", flags)
            _save_local_setting(self.repo_root, "run_keep_console_open", keep_open)
            self.window.set_status(
                f"Launched {entrypoint} as PID {process.pid} with {len(flags)} flag(s)"
            )
            self.run_status.setText(
                f"Running as PID {process.pid}. "
                + ("Console will remain open after exit." if keep_open else "Console will close automatically when SRPSS exits.")
            )
        except Exception as exc:
            self.window.show_error("RUN launch failed", exc)


class GodzipFoundryWindow(QMainWindow):
    def __init__(self, repo_root: Path, initial_zip: Path | None = None) -> None:
        super().__init__()
        self.repo_root = discover_repo_root(repo_root)
        self.setWindowTitle(APP_TITLE)
        self.setAcceptDrops(True)
        self.setMinimumSize(900, 680)
        self._fit_to_screen()
        self._set_icon()
        self._build_ui()
        self._apply_style()
        self.refresh_repo_header()
        # Populate the default CREATE page before the first native show. Doing the
        # first large tree build after show caused several visible startup repaints.
        self.create_tab.refresh()
        if initial_zip is not None:
            QTimer.singleShot(0, lambda: self.apply_tab.load_zip(initial_zip))

    def _fit_to_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1180, 820)
            return
        avail = screen.availableGeometry()
        width = min(1420, max(980, avail.width() - 100))
        height = min(930, max(720, avail.height() - 100))
        self.resize(width, height)

    def _set_icon(self) -> None:
        self._icon_path = _resolved_foundry_icon(self.repo_root)
        self._native_icon_handles: list[int] = []
        if self._icon_path is None:
            return
        icon = QIcon(str(self._icon_path))
        self.setWindowIcon(icon)
        app = QApplication.instance()
        if app is not None:
            app.setWindowIcon(icon)

    def refresh_native_taskbar_icon(self) -> None:
        """Refresh HWND icons after first show so Windows taskbar does not keep python.exe's icon."""
        if sys.platform != "win32" or self._icon_path is None:
            return
        try:
            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            load_image = user32.LoadImageW
            load_image.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
            load_image.restype = ctypes.c_void_p
            send_message = user32.SendMessageW
            send_message.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_void_p]
            send_message.restype = ctypes.c_ssize_t
            image_icon = 1
            lr_loadfromfile = 0x0010
            wm_seticon = 0x0080
            sizes = (
                (1, int(user32.GetSystemMetrics(11)), int(user32.GetSystemMetrics(12))),  # ICON_BIG
                (0, int(user32.GetSystemMetrics(49)), int(user32.GetSystemMetrics(50))),  # ICON_SMALL
            )
            for kind, width, height in sizes:
                raw_handle = load_image(None, str(self._icon_path), image_icon, width, height, lr_loadfromfile)
                handle = int(raw_handle or 0)
                if not handle:
                    continue
                send_message(ctypes.c_void_p(hwnd), wm_seticon, kind, ctypes.c_void_p(handle))
                self._native_icon_handles.append(handle)
        except (AttributeError, OSError, ValueError):
            return

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if sys.platform == "win32":
            try:
                destroy_icon = ctypes.windll.user32.DestroyIcon
                destroy_icon.argtypes = [ctypes.c_void_p]
                destroy_icon.restype = ctypes.c_bool
                for handle in getattr(self, "_native_icon_handles", []):
                    destroy_icon(ctypes.c_void_p(handle))
            except (AttributeError, OSError, ValueError):
                pass
            self._native_icon_handles = []
        super().closeEvent(event)

    def zip_search_dirs(self) -> list[Path]:
        settings = _load_local_settings(self.repo_root)
        dirs: list[Path] = [self.repo_root.parent]
        remembered_output = str(settings.get("output_dir", "")).strip()
        if remembered_output:
            dirs.append(Path(remembered_output))
        if os.name == "nt":
            dirs.append(PERSONAL_GODZIP_DROP_DIR)
        return dirs

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(10)

        shell = QFrame()
        shell.setObjectName("shell")
        shell_l = QVBoxLayout(shell)
        shell_l.setContentsMargins(1, 1, 1, 1)
        shell_l.setSpacing(0)

        header = QFrame()
        header.setObjectName("foundryHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 14, 18, 14)
        titles = QVBoxLayout()
        title = QLabel("GODZIP FOUNDRY")
        title.setObjectName("appTitle")
        titles.addWidget(title)
        subtitle = QLabel("Manifested repo transfer · ancestry-aware apply · reversible debris")
        subtitle.setObjectName("subtitle")
        titles.addWidget(subtitle)
        hl.addLayout(titles, 1)
        self.branch_badge = QLabel()
        self.branch_badge.setObjectName("chip")
        self.head_badge = QLabel()
        self.head_badge.setObjectName("chip")
        self.dirty_badge = QLabel()
        self.dirty_badge.setObjectName("chip")
        hl.addWidget(self.branch_badge)
        hl.addWidget(self.head_badge)
        hl.addWidget(self.dirty_badge)
        shell_l.addWidget(header)

        body = QWidget()
        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(16, 12, 16, 14)
        body_l.setSpacing(8)
        repo = QLabel(str(self.repo_root))
        repo.setObjectName("repoPath")
        repo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body_l.addWidget(repo)

        self.tabs = QTabWidget()
        self.debris_tab = DebrisTab(self)
        self.create_tab = CreateTab(self)
        self.apply_tab = ApplyTab(self)
        self.diff_tab = DiffTab(self)
        self.logzip_tab = LogzipTab(self)
        self.push_tab = PushTab(self)
        self.pull_tab = PullTab(self)
        self.run_tab = RunTab(self)
        self.tabs.addTab(self.create_tab, "CREATE GOD ZIP")
        self.tabs.addTab(self.apply_tab, "APPLY GOD ZIP")
        self.tabs.addTab(self.diff_tab, "DIFF")
        self.tabs.addTab(self.logzip_tab, "LOGZIP")
        self.tabs.addTab(self.push_tab, "PUSH")
        self.tabs.addTab(self.pull_tab, "PULL")
        self.tabs.addTab(self.debris_tab, "DEBRIS")
        self.tabs.addTab(self.run_tab, "RUN")
        self.tabs.currentChanged.connect(self._tab_changed)
        body_l.addWidget(self.tabs, 1)
        shell_l.addWidget(body, 1)
        outer.addWidget(shell, 1)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")
        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setFixedWidth(150)
        self.busy.hide()
        dpi = QLabel(f"DPI: {_DPI_MODE}")
        dpi.setObjectName("faint")
        status_row.addWidget(self.status_label, 1)
        status_row.addWidget(self.busy)
        status_row.addWidget(dpi)
        outer.addLayout(status_row)

    def _tab_changed(self, _index: int) -> None:
        current = self.tabs.currentWidget()
        if current is self.pull_tab:
            self.pull_tab.ensure_loaded()
        elif current is self.apply_tab:
            self.apply_tab.ensure_discovery_loaded()
        elif current is self.diff_tab:
            self.diff_tab.ensure_loaded()
        elif current is self.push_tab:
            self.push_tab.refresh()
        elif current is self.logzip_tab:
            self.logzip_tab.refresh()

    def refresh_after_git_mutation(self) -> None:
        self.refresh_repo_header()
        self.create_tab.refresh()
        self.push_tab.refresh()

    def refresh_repo_header(self) -> None:
        try:
            branch = git_branch(self.repo_root)
            head = git_head(self.repo_root)[:10]
            dirty = git_dirty(self.repo_root)
            self.branch_badge.setText(branch)
            self.head_badge.setText(head)
            self.dirty_badge.setText("DIRTY" if dirty else "CLEAN")
            self.dirty_badge.setProperty("dirty", dirty)
            self.dirty_badge.style().unpolish(self.dirty_badge)
            self.dirty_badge.style().polish(self.dirty_badge)
        except Exception as exc:
            self.set_status(f"Git header refresh failed: {exc}")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_busy(self, busy: bool, text: str = "") -> None:
        if text:
            self.set_status(text)
        self.busy.setVisible(busy)
        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            if self.isVisible():
                QApplication.processEvents()
        else:
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

    def show_error(self, title: str, exc: Exception) -> None:
        message = str(exc) if str(exc) else exc.__class__.__name__
        self.set_status(f"{title}: {message}")
        QMessageBox.critical(self, title, message)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if any(Path(url.toLocalFile()).suffix.lower() in {".zip", ".json"} for url in urls):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        zip_paths = [path for path in paths if path.suffix.lower() == ".zip"]
        json_paths = [path for path in paths if path.suffix.lower() == ".json"]
        if zip_paths:
            self.tabs.setCurrentWidget(self.apply_tab)
            self.apply_tab.load_zip(zip_paths[0])
            if len(zip_paths) > 1:
                self.set_status(f"Loaded first of {len(zip_paths)} dropped ZIPs: {zip_paths[0].name}")
            event.acceptProposedAction()
            return
        if json_paths:
            try:
                entries = read_debris_manifest(json_paths[0])
                for entry in entries:
                    self.debris_tab._add_entry(
                        entry["path"],
                        source=self.debris_tab.SOURCE_IMPORTED,
                        reason=entry.get("reason", ""),
                    )
                self.tabs.setCurrentWidget(self.debris_tab)
                self.set_status(f"Loaded {len(entries)} debris instruction(s) from dropped JSON")
            except Exception as exc:
                self.show_error("Dropped debris manifest failed", exc)
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _apply_style(self) -> None:
        c = COLORS
        self.setStyleSheet(
            f"""
            QMainWindow, QWidget#root {{ background: {c['root']}; color: {c['text']}; }}
            QWidget {{ color: {c['text']}; font-family: 'Segoe UI'; font-size: 10pt; }}
            QFrame#shell {{ background: {c['panel']}; border: 1px solid {c['shell_border']}; }}
            QFrame#foundryHeader {{ background: {c['titlebar']}; border: none; border-bottom: 1px solid {c['border']}; }}
            QLabel#appTitle {{ color: {c['amber']}; font-size: 19pt; font-weight: 800; letter-spacing: 1px; }}
            QLabel#subtitle, QLabel#muted {{ color: {c['muted']}; }}
            QLabel#faint {{ color: {c['faint']}; }}
            QLabel#repoPath {{ color: {c['faint']}; padding: 1px 2px 5px 2px; }}
            QLabel#sectionTitle {{ color: {c['amber']}; font-size: 12pt; font-weight: 750; }}
            QLabel#archiveName {{ color: {c['text']}; font-size: 11pt; font-weight: 650; }}
            QLabel#status {{ color: {c['muted']}; padding: 2px 4px; }}
            QLabel#warningText {{ color: {c['amber']}; background: #241d12; border: 1px solid {c['amber_dark']}; border-radius: 5px; padding: 7px; }}
            QLabel#chip {{ background: {c['panel_alt']}; border: 1px solid {c['border']}; border-radius: 9px; padding: 4px 9px; color: {c['muted']}; font-weight: 600; }}
            QLabel#chip[dirty="true"] {{ color: {c['amber']}; border-color: {c['amber']}; }}
            QLabel#chip[dirty="false"] {{ color: {c['green']}; }}
            QFrame#panel, QFrame#dropPanel {{ background: {c['panel_alt']}; border: 1px solid {c['border']}; border-radius: 7px; }}
            QFrame#dropPanel {{ background: #132126; border: 1px dashed {c['amber_dark']}; }}
            QTabWidget::pane {{ border: 1px solid {c['border']}; background: {c['panel']}; top: -1px; }}
            QTabBar::tab {{ background: {c['panel_alt']}; color: {c['muted']}; border: 1px solid #46504e; border-bottom: none; padding: 9px 18px; margin-right: 2px; font-weight: 650; }}
            QTabBar::tab:selected {{ background: {c['panel']}; color: {c['amber']}; border-color: {c['border']}; }}
            QTabBar::tab:hover {{ background: {c['panel_hover']}; }}
            QPushButton {{ background: {c['panel_alt']}; color: {c['text']}; border: 1px solid {c['border']}; border-radius: 5px; padding: 7px 12px; font-weight: 600; }}
            QPushButton:hover {{ background: {c['panel_hover']}; border-color: {c['amber']}; }}
            QPushButton:disabled {{ color: #66716f; border-color: #3c4644; background: #151c1d; }}
            QPushButton#primaryButton {{ background: {c['amber_dark']}; color: #101313; border-color: {c['amber']}; font-weight: 800; padding: 9px 16px; }}
            QPushButton#primaryButton:hover {{ background: {c['amber_hover']}; }}
            QPushButton#dangerButton {{ color: {c['red']}; border-color: {c['red']}; font-weight: 750; }}
            QPushButton#dangerButton:hover {{ background: #3a1c1c; }}
            QLineEdit {{ background: #0e1517; color: {c['text']}; border: 1px solid #59625f; border-radius: 5px; padding: 7px 9px; selection-background-color: {c['amber_dark']}; selection-color: #111; }}
            QLineEdit:focus {{ border-color: {c['amber']}; }}
            QTreeWidget {{ background: #0d1517; alternate-background-color: #121d1f; color: {c['text']}; border: 1px solid #4f5956; outline: none; }}
            QTreeWidget::item {{ padding: 4px 3px; }}
            QTreeWidget::item:selected {{ background: #314340; color: white; }}
            QTreeWidget::item:hover {{ background: {c['panel_hover']}; }}
            QHeaderView::section {{ background: {c['titlebar']}; color: {c['amber']}; border: none; border-right: 1px solid #3f4946; border-bottom: 1px solid {c['border']}; padding: 6px; font-weight: 700; }}
            QCheckBox {{ color: {c['muted']}; spacing: 7px; }}
            QCheckBox#dangerCheck {{ color: {c['red']}; font-weight: 700; }}
            QCheckBox::indicator {{ width: 16px; height: 16px; }}
            QProgressBar {{ background: #0e1517; border: 1px solid {c['border']}; border-radius: 4px; text-align: center; }}
            QProgressBar::chunk {{ background: {c['amber_dark']}; }}
            QLabel[relation="same"] {{ color: {c['green']}; background: #15231f; border: 1px solid {c['green']}; border-radius: 5px; padding: 7px; font-weight: 650; }}
            QLabel[relation="newer"] {{ color: {c['green']}; background: #15231f; border: 1px solid {c['green']}; border-radius: 5px; padding: 7px; font-weight: 650; }}
            QLabel[relation="older"] {{ color: {c['red']}; background: #2d1717; border: 1px solid {c['red']}; border-radius: 5px; padding: 7px; font-weight: 800; }}
            QLabel[relation="diverged"] {{ color: {c['amber']}; background: #2a2114; border: 1px solid {c['amber']}; border-radius: 5px; padding: 7px; font-weight: 750; }}
            QLabel[relation="unknown"] {{ color: {c['amber']}; background: #241d12; border: 1px solid {c['amber_dark']}; border-radius: 5px; padding: 7px; }}
            QToolTip {{ color: {c['text']}; background: {c['panel_alt']}; border: 1px solid {c['amber_dark']}; padding: 5px; }}
            """
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SRPSS GODZIP Foundry")
    parser.add_argument("--repo", type=Path, default=_early_repo_root())
    parser.add_argument("--open", dest="initial_zip", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except AttributeError:
        pass
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_TITLE)
    app.setOrganizationName("SRPSS")
    repo_root = discover_repo_root(args.repo)
    icon_path = _resolved_foundry_icon(repo_root)
    if icon_path is not None:
        app.setWindowIcon(QIcon(str(icon_path)))
    window = GodzipFoundryWindow(repo_root, args.initial_zip)
    window.show()
    QTimer.singleShot(0, window.refresh_native_taskbar_icon)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
