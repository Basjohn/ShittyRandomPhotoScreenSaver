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
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path, PurePosixPath
import sys
from typing import Any, Callable, Iterable


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
_REPO_IMPORT_ROOT = _SCRIPT_DIR.parent
for _import_root in (_SCRIPT_DIR, _REPO_IMPORT_ROOT):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))

try:
    from PySide6.QtCore import QObject, QPoint, Qt, QTimer, QUrl, Signal
    from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication, QIcon
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
from godzip_foundry_theme import (  # noqa: E402
    FOUNDRY_DEFAULT_THEME_ID,
    FoundryThemeResolution,
    render_foundry_stylesheet,
    resolve_foundry_theme,
    theme_choices,
)

APP_TITLE = "SRPSS GODZIP Foundry"
PERSONAL_GODZIP_DROP_DIR = Path(r"Z:\Torrents\Torrentfiles")

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


class FoundryHeaderFrame(QFrame):
    """Frameless-window drag surface for the Foundry header."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._drag_offset = QPoint()
        self.setObjectName("foundryHeader")

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle is not None:
                try:
                    if handle.startSystemMove():
                        event.accept()
                        return
                except (AttributeError, RuntimeError):
                    pass
            self._drag_offset = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if event.buttons() & Qt.MouseButton.LeftButton and not self._drag_offset.isNull():
            self.window().move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.MouseButton.LeftButton:
            owner = self.window()
            toggle = getattr(owner, "_toggle_maximized", None)
            if callable(toggle):
                toggle()
            else:
                owner.showNormal() if owner.isMaximized() else owner.showMaximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class RelationBanner(QLabel):
    def set_relation(self, relation: str, text: str) -> None:
        relation = relation if relation in {"same", "compatible", "conflict", "future", "diverged", "unknown", "stale", "dirty"} else "unknown"
        self.setProperty("relation", relation)
        self.setText(text)
        self.style().unpolish(self)
        self.style().polish(self)


class _TaskBridge(QObject):
    """Qt signal bridge for one background Foundry operation."""

    succeeded = Signal(object)
    failed = Signal(object)


class FoundryNoticeDialog(QDialog):
    """Non-modal always-on-top Foundry notification."""

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
        *,
        danger: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("foundryPopup")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setMinimumWidth(440)
        self.setMaximumWidth(760)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("foundryPopupPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("popupTitle")
        if danger:
            heading.setProperty("danger", True)
        layout.addWidget(heading)
        body = QLabel(message)
        body.setObjectName("popupMessage")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        outer.addWidget(panel)


class FoundryConfirmDialog(QDialog):
    """Non-modal always-on-top confirmation with callback-friendly signals."""

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
        *,
        confirm_text: str = "CONTINUE",
        danger: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("foundryPopup")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.setMinimumWidth(500)
        self.setMaximumWidth(780)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("foundryPopupPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        heading = QLabel(title)
        heading.setObjectName("popupTitle")
        if danger:
            heading.setProperty("danger", True)
        layout.addWidget(heading)
        body = QLabel(message)
        body.setObjectName("popupMessage")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText(confirm_text)
        if danger:
            ok.setObjectName("dangerButton")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        outer.addWidget(panel)


class FoundrySettingsDialog(QDialog):
    """Tool-local Foundry settings. Product Settings are never mutated."""

    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.setWindowTitle("GODZIP Foundry Settings")
        self.setObjectName("foundryPopup")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
        self.resize(560, 210)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QFrame()
        panel.setObjectName("foundryPopupPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        heading = QLabel("FOUNDRY SETTINGS")
        heading.setObjectName("popupTitle")
        layout.addWidget(heading)
        explainer = QLabel(
            "Foundry themes are a tool-local snapshot. Changing this does not alter SRPSS Settings."
        )
        explainer.setObjectName("popupMessage")
        explainer.setWordWrap(True)
        layout.addWidget(explainer)

        row = QHBoxLayout()
        row.addWidget(QLabel("Theme"))
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumWidth(320)
        for theme_id, name in theme_choices(window.theme_resolution.catalog):
            self.theme_combo.addItem(name, theme_id)
        index = self.theme_combo.findData(window.theme_resolution.theme_id)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        row.addWidget(self.theme_combo, 1)
        layout.addLayout(row)

        close_button = QPushButton("CLOSE")
        close_button.clicked.connect(self.close)
        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(close_button)
        layout.addLayout(footer)
        outer.addWidget(panel)

    def _theme_changed(self, index: int) -> None:
        theme_id = self.theme_combo.itemData(index)
        if theme_id:
            self.window.set_foundry_theme(str(theme_id))


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
            "while app/tool themes, images, goldens and nested test payloads stay off unless explicitly selected."
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
        open_saved = QPushButton("Open Saved Folder")
        open_saved.setToolTip("Open the current GODZIP output folder in the system file manager.")
        open_saved.clicked.connect(self.open_saved_folder)
        row.addWidget(QLabel("Output"))
        row.addWidget(self.output_edit, 1)
        row.addWidget(browse)
        row.addWidget(open_saved)
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
        def apply_result(result: list[RepoFile]) -> None:
            self.repo_files = result
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

        self.window.run_task(
            "Scanning Git worktree…",
            lambda: collect_repo_files(self.repo_root),
            apply_result,
            error_title="Repository scan failed",
        )

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

    def open_saved_folder(self) -> None:
        self.window.open_folder(
            Path(self.output_edit.text().strip() or str(self.repo_root.parent)).expanduser(),
            label="GODZIP output folder",
        )

    def create_archive(self) -> None:
        selected = self.tree.checked_paths()
        output_dir = Path(self.output_edit.text().strip() or str(self.repo_root.parent)).expanduser()
        name = self.name_edit.text().strip() or suggested_godzip_name(self.repo_root)
        if not name.lower().endswith(".zip"):
            name += ".zip"
        output = output_dir / name
        debris = self.window.debris_tab.entries_for_create() if self.include_debris.isChecked() else []

        def start() -> None:
            self._create_archive_now(selected, output, debris)

        if output.exists():
            self.window.confirm(
                "Replace existing archive?",
                f"{output.name} already exists. Replace it?",
                start,
                confirm_text="REPLACE",
                danger=True,
            )
            return
        start()

    def _create_archive_now(self, selected: list[str], output: Path, debris: list[dict[str, str]]) -> None:
        def completed(manifest: dict[str, Any]) -> None:
            _save_local_setting(self.repo_root, "output_dir", str(output.parent))
            self.window.set_status(
                f"Created {output.name} — {len(manifest['files'])} files, {len(manifest['debris'])} debris instructions"
            )
            self.window.notify(
                "GODZIP created",
                f"Created:\n{output}\n\n"
                f"HEAD: {manifest['source_head'][:10]}\n"
                f"Dirty worktree: {'yes' if manifest['dirty_worktree'] else 'no'}\n"
                "Manifest: .godzip/manifest.json\n\n"
                "The archive passed CRC validation before publication.",
            )
            self.name_edit.setText(suggested_godzip_name(self.repo_root))

        self.window.run_task(
            "Hashing selected files and creating GODZIP…",
            lambda: create_godzip(self.repo_root, selected, output, debris_entries=debris),
            completed,
            error_title="GODZIP creation failed",
        )


class ApplyTab(QWidget):
    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self.inspection: ArchiveInspection | None = None
        self.current_zip: Path | None = None
        self._discovery_loaded = False
        self._discovered_zips: list[Path] = []
        self._browser_expanded = False
        self._main_items: dict[str, QTreeWidgetItem] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 0)
        layout.setSpacing(10)

        self.context_panel = Panel()
        context = QHBoxLayout(self.context_panel)
        context.setContentsMargins(12, 10, 12, 10)
        context.setSpacing(12)

        # Compact drag target: the whole window still accepts ZIP drops; this is
        # only the visual affordance and deliberately does not waste vertical space.
        self.drop_panel = QFrame()
        self.drop_panel.setObjectName("dropPanel")
        self.drop_panel.setFixedWidth(124)
        drop_l = QVBoxLayout(self.drop_panel)
        drop_l.setContentsMargins(8, 8, 8, 8)
        drop_l.addStretch(1)
        drop_title = QLabel("DROP")
        drop_title.setObjectName("dropTitle")
        drop_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_l.addWidget(drop_title)
        drop_l.addStretch(1)
        context.addWidget(self.drop_panel)

        archive_box = QVBoxLayout()
        archive_box.setSpacing(6)
        self.archive_label = QLabel("No GODZIP loaded")
        self.archive_label.setObjectName("archiveName")
        self.archive_label.setWordWrap(True)
        archive_box.addWidget(self.archive_label)

        chips = QHBoxLayout()
        chips.setSpacing(5)
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
        archive_box.addLayout(chips)

        state_row = QHBoxLayout()
        state_row.setSpacing(8)
        self.relation = RelationBanner("Archive baseline applicability cannot be proven.")
        self.relation.setWordWrap(True)
        self.relation.hide()
        self.freshness = RelationBanner("Load a GODZIP to compare incoming file timestamps.")
        self.freshness.setWordWrap(True)
        self.freshness.hide()
        state_row.addWidget(self.relation, 1)
        state_row.addWidget(self.freshness, 1)
        archive_box.addLayout(state_row)

        self.warning_label = QLabel("")
        self.warning_label.setObjectName("warningText")
        self.warning_label.setWordWrap(True)
        self.warning_label.hide()
        archive_box.addWidget(self.warning_label)
        self.strip_wrapper = QCheckBox("Legacy archive: strip detected common top-level wrapper folder")
        self.strip_wrapper.hide()
        self.strip_wrapper.toggled.connect(self._wrapper_changed)
        archive_box.addWidget(self.strip_wrapper)
        context.addLayout(archive_box, 1)

        chooser_box = QVBoxLayout()
        chooser_box.setSpacing(6)
        chooser_label = QLabel("GODZIP")
        chooser_label.setObjectName("faint")
        chooser_box.addWidget(chooser_label)
        self.found_combo = QComboBox()
        self.found_combo.setMinimumWidth(280)
        self.found_combo.setToolTip(
            "Newest direct ZIPs from repo-adjacent/output locations and the optional personal drop folder."
        )
        self.found_combo.activated.connect(self._load_discovered_index)
        chooser_box.addWidget(self.found_combo)
        quick_row = QHBoxLayout()
        self.show_all_zips = QCheckBox("All ZIPs")
        self.show_all_zips.setToolTip(
            "Off: recognized SRPSS/GODZIP archives only. On: every direct ZIP in quick locations."
        )
        self.show_all_zips.toggled.connect(lambda *_: self.refresh_discovered_zips(force=True))
        quick_row.addWidget(self.show_all_zips)
        quick_row.addStretch(1)
        refresh_found = QPushButton("↻")
        refresh_found.setObjectName("iconButton")
        refresh_found.setFixedSize(34, 32)
        refresh_found.setToolTip("Refresh discovered ZIPs")
        refresh_found.clicked.connect(lambda: self.refresh_discovered_zips(force=True))
        quick_row.addWidget(refresh_found)
        chooser_box.addLayout(quick_row)
        browse = QPushButton("BROWSE GOD ZIP…")
        browse.setObjectName("primaryButton")
        browse.clicked.connect(self.browse)
        chooser_box.addWidget(browse)
        context.addLayout(chooser_box)

        # Historical name retained only as an internal visibility alias; there is
        # now one compact context dashboard rather than two stacked panels.
        self.info_panel = self.context_panel
        layout.addWidget(self.context_panel)

        self.browser_panel = Panel()
        browser_l = QVBoxLayout(self.browser_panel)
        browser_l.setContentsMargins(10, 0, 10, 10)
        browser_l.setSpacing(8)

        notch = QHBoxLayout()
        notch.addStretch(1)
        self.expand_button = QPushButton("▲")
        self.expand_button.setObjectName("expandButton")
        self.expand_button.setFixedWidth(46)
        self.expand_button.setToolTip("Expand the Apply file browser to use the full tab height")
        self.expand_button.clicked.connect(self.toggle_browser_expanded)
        notch.addWidget(self.expand_button)
        notch.addStretch(1)
        browser_l.addLayout(notch)

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
        browser_l.addLayout(tools)
        legend = QLabel("Orange = timestamp-old · Red = timestamp-old + Git-old · Violet = local dirty")
        legend.setObjectName("faint")
        browser_l.addWidget(legend)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("applySplitter")
        self.tree = CheckPathTree(["Target path", "Local", "Size", "SHA-256"])
        self.tree.setMinimumHeight(260)
        self.tree.itemChanged.connect(lambda *_: self._update_apply_summary())
        self.splitter.addWidget(self.tree)

        self.changes_tree = QTreeWidget()
        self.changes_tree.setObjectName("changesTree")
        self.changes_tree.setHeaderLabels(["CHANGING FILES"])
        self.changes_tree.setRootIsDecorated(False)
        self.changes_tree.setUniformRowHeights(True)
        self.changes_tree.setAlternatingRowColors(True)
        self.changes_tree.setMinimumWidth(180)
        self.changes_tree.setMaximumWidth(360)
        self.changes_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.changes_tree.itemClicked.connect(self._locate_changed_item)
        self.changes_tree.itemActivated.connect(self._locate_changed_item)
        self.splitter.addWidget(self.changes_tree)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([820, 230])
        browser_l.addWidget(self.splitter, 1)
        layout.addWidget(self.browser_panel, 1)

        self.bottom_panel = Panel()
        btm = QVBoxLayout(self.bottom_panel)
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
        self.history_ack = QCheckBox("I reviewed the selected timestamp + commit-history risk")
        self.history_ack.setObjectName("dangerCheck")
        self.history_ack.hide()
        self.history_ack.toggled.connect(self._update_apply_summary)
        btm.addWidget(self.history_ack)
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
        layout.addWidget(self.bottom_panel)

    def toggle_browser_expanded(self) -> None:
        self._browser_expanded = not self._browser_expanded
        for widget in (self.context_panel, self.bottom_panel):
            widget.setVisible(not self._browser_expanded)
        self.expand_button.setText("▼" if self._browser_expanded else "▲")
        self.expand_button.setToolTip(
            "Restore the normal Apply layout"
            if self._browser_expanded
            else "Expand the Apply file browser to use the full tab height"
        )

    def _locate_changed_item(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        path = str(item.data(0, ROLE_PATH) or "")
        target = self._main_items.get(path)
        if target is None:
            return
        parent = target.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.tree.setCurrentItem(target)
        self.tree.scrollToItem(target, QAbstractItemView.ScrollHint.PositionAtCenter)

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

    def load_zip(
        self,
        path: Path,
        *,
        preserve_wrapper_choice: bool = False,
        on_loaded: Callable[[], None] | None = None,
    ) -> None:
        path = path.expanduser().resolve()
        strip = self.strip_wrapper.isChecked() if preserve_wrapper_choice else False

        def completed(inspection: ArchiveInspection) -> None:
            self.inspection = inspection
            self.current_zip = path
            self._render_inspection()
            self.window.debris_tab.set_archive_entries(inspection, path)
            self.window.tabs.setCurrentWidget(self)
            self.window.set_status(
                f"Inspected {path.name} — {len(inspection.files)} file targets, {len(inspection.debris)} debris instructions"
            )
            if on_loaded is not None:
                on_loaded()

        self.window.run_task(
            f"Inspecting {path.name}…",
            lambda: inspect_godzip(self.repo_root, path, strip_legacy_prefix=strip),
            completed,
            error_title="GODZIP inspection failed",
        )

    def _wrapper_changed(self, _checked: bool) -> None:
        if self.current_zip is not None and self.inspection is not None and self.inspection.legacy:
            self.load_zip(self.current_zip, preserve_wrapper_choice=True)

    def _render_inspection(self) -> None:
        inspection = self.inspection
        assert inspection is not None
        self.archive_label.setText(str(inspection.zip_path))
        manifest_version = inspection.manifest.get("version") if inspection.manifest else None
        self.kind_chip.setText("LEGACY / UNMANIFESTED" if inspection.legacy else f"MANIFEST v{manifest_version}")
        self.head_chip.setText(f"baseline {inspection.source_head[:10] if inspection.source_head else 'unknown'}")
        self.branch_chip.setText(f"branch {inspection.source_branch or 'unknown'}")
        self.dirty_chip.setText("archive from DIRTY worktree" if inspection.dirty_worktree else "archive source clean")
        self.relation.set_relation(inspection.relation, inspection.relation_detail)
        self.relation.show()
        self.freshness.show()

        overlap = {path.casefold() for path in inspection.history_overlap_paths}
        changed_entries = [entry for entry in inspection.files if entry.local_state != "SAME"]
        stale_entries = [entry for entry in changed_entries if entry.timestamp_stale]
        dangerous_entries = [
            entry for entry in stale_entries if entry.target_path.casefold() in overlap
        ]
        dirty_entries = [entry for entry in changed_entries if entry.local_dirty]
        current_entries = [entry for entry in changed_entries if not entry.timestamp_stale]
        freshness_text = (
            f"{len(current_entries)} current/newer · {len(stale_entries)} timestamp-old · "
            f"{len(dangerous_entries)} timestamp-old + Git-old · {len(dirty_entries)} local dirty"
        )
        if dangerous_entries:
            self.freshness.set_relation("conflict", freshness_text)
        elif stale_entries:
            self.freshness.set_relation("stale", freshness_text)
        elif dirty_entries:
            self.freshness.set_relation("dirty", freshness_text)
        else:
            self.freshness.set_relation("compatible", freshness_text)

        warnings = list(inspection.warnings)
        dirty_count = len(dirty_entries)
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
        self.changes_tree.clear()
        self._main_items.clear()
        for entry in inspection.files:
            committed_overlap = entry.target_path.casefold() in overlap
            tags = [entry.local_state]
            if entry.timestamp_stale:
                tags.append("TIMESTAMP OLD")
            elif entry.local_state not in {"SAME", "NEW"} and entry.local_mtime_ns:
                tags.append("TIMESTAMP CURRENT/NEWER")
            if committed_overlap:
                tags.append("GIT CHANGED")
            state_text = " · ".join(tags)
            item = self.tree.add_path(
                entry.target_path,
                [entry.target_path, state_text, human_size(entry.size), entry.sha256[:12]],
                checked=entry.default_selected,
                payload=entry,
            )
            self._main_items[entry.target_path] = item

            row_color: QColor | None = None
            if entry.timestamp_stale and committed_overlap:
                row_color = self.window.theme_qcolor("popup.icon.error")
            elif entry.timestamp_stale:
                row_color = self.window.theme_qcolor("popup.icon.warning")
            elif entry.local_dirty:
                row_color = self.window.theme_qcolor("popup.icon.info")
            elif entry.local_state == "NEW":
                row_color = self.window.theme_qcolor("popup.icon.success")
            elif entry.local_state == "SAME":
                row_color = self.window.theme_qcolor("text.tertiary")
            if row_color is not None:
                for col in range(self.tree.columnCount()):
                    item.setForeground(col, row_color)

            if entry.local_state != "SAME":
                changed_item = QTreeWidgetItem([entry.target_path])
                changed_item.setData(0, ROLE_PATH, entry.target_path)
                changed_item.setToolTip(0, state_text)
                if row_color is not None:
                    changed_item.setForeground(0, row_color)
                self.changes_tree.addTopLevelItem(changed_item)

        self.changes_tree.setHeaderLabel(f"CHANGING FILES · {self.changes_tree.topLevelItemCount()}")
        self.tree.expandToDepth(0)
        self.history_ack.blockSignals(True)
        self.history_ack.setChecked(False)
        self.history_ack.hide()
        self.history_ack.blockSignals(False)
        self.include_debris.setVisible(bool(inspection.debris))
        self.include_debris.setText(
            f"Apply checked archive debris moves ({len(inspection.debris)}) — review in Debris tab"
        )
        self.tree_filter(self.filter_edit.text())
        self._update_apply_summary()

    def tree_filter(self, text: str) -> None:
        self.tree.apply_filter(text)
        needle = text.strip().casefold()
        for index in range(self.changes_tree.topLevelItemCount()):
            item = self.changes_tree.topLevelItem(index)
            path = str(item.data(0, ROLE_PATH) or "")
            item.setHidden(bool(needle and needle not in path.casefold()))

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
        stale = sum(1 for entry in changed if entry.timestamp_stale)
        overlap = {path.casefold() for path in inspection.history_overlap_paths}
        danger = sum(1 for entry in changed if entry.timestamp_stale and entry.target_path.casefold() in overlap)
        self.summary.setText(
            f"{len(chosen)} file target(s) · {len(changed)} actual change(s)"
            + (f" · {stale} timestamp-old" if stale else "")
            + (f" · {danger} timestamp+Git risk" if danger else "")
            + (f" · {dirty} LOCAL DIRTY" if dirty else "")
            + (f" · {len(debris)} debris move(s)" if debris else "")
        )
        history_ack_required = inspection.selection_requires_history_ack(checked, debris)
        self.history_ack.blockSignals(True)
        try:
            self.history_ack.setVisible(history_ack_required)
            if history_ack_required:
                if inspection.baseline_relation == "older":
                    overlap = {path.casefold() for path in inspection.history_overlap_paths}
                    stale = {path.casefold() for path in inspection.timestamp_stale_paths}
                    risky_files = {path.casefold() for path in checked} & overlap & stale
                    risky_debris = {path.casefold() for path in debris} & overlap
                    overlap_count = len(risky_files | risky_debris)
                    self.history_ack.setText(
                        f"I reviewed {overlap_count} selected timestamp-stale + Git-overlap/debris risk target(s)"
                    )
                elif inspection.baseline_relation == "newer":
                    self.history_ack.setText("I understand this archive was built on a newer baseline than my local HEAD")
                else:
                    self.history_ack.setText("I reviewed the selected targets against diverged commit history")
            elif self.history_ack.isChecked():
                self.history_ack.setChecked(False)
        finally:
            self.history_ack.blockSignals(False)
        history_ok = not history_ack_required or self.history_ack.isChecked()
        self.apply_button.setEnabled(bool(chosen or debris) and history_ok)

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
        if inspection.selection_requires_history_ack(selected, debris):
            if inspection.baseline_relation == "older":
                overlap = {path.casefold() for path in inspection.history_overlap_paths}
                stale = {path.casefold() for path in inspection.timestamp_stale_paths}
                selected_overlap = (
                    ({path.casefold() for path in selected} & overlap & stale)
                    | ({path.casefold() for path in debris} & overlap)
                )
                lines.append(
                    f"WARNING: {len(selected_overlap)} selected target(s) are timestamp-stale + Git-overlapped, or overlapping debris."
                )
            elif inspection.baseline_relation == "newer":
                lines.append("WARNING: this archive was built on a newer baseline than local HEAD.")
            else:
                lines.append("WARNING: archive baseline and local HEAD have diverged.")
        lines.append("Missing archive files are NEVER interpreted as deletions.")

        self.window.confirm(
            "Apply GODZIP?",
            "\n\n".join(lines),
            lambda: self._apply_selected_now(inspection, selected, debris),
            confirm_text="APPLY",
            danger=True,
        )

    def _apply_selected_now(
        self,
        inspection: ArchiveInspection,
        selected: list[str],
        debris: list[str],
    ) -> None:
        create_rollback = self.rollback.isChecked()
        allow_history_conflict = self.history_ack.isChecked()

        def completed(result: Any) -> None:
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
            self.window.notify("GODZIP applied", detail)
            self.window.set_status(
                f"Applied {inspection.zip_path.name} — {result.replaced} replaced, {result.new_files} new, {result.debris_moved} debris"
            )
            self.window.refresh_repo_header()
            self.load_zip(
                inspection.zip_path,
                preserve_wrapper_choice=True,
                on_loaded=self.window.create_tab.refresh,
            )

        self.window.run_task(
            "Validating and transactionally applying GODZIP…",
            lambda: apply_godzip(
                self.repo_root,
                inspection,
                selected,
                selected_debris=debris,
                create_rollback_snapshot=create_rollback,
                allow_history_conflict=allow_history_conflict,
            ),
            completed,
            error_title="GODZIP apply failed",
        )



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
            item.setForeground(2, self.window.theme_qcolor("text.tertiary"))
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
            self.window.notify("Nothing checked", "Check at least one debris path first.")
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
        self.window.confirm(
            "Move debris?",
            f"Move {len(existing)} checked path(s) to /deleteme?\n\nNothing is permanently deleted.",
            lambda: self._move_checked_now(existing),
            confirm_text="MOVE",
            danger=True,
        )

    def _move_checked_now(self, existing: list[str]) -> None:
        def completed(result: tuple[Path, int]) -> None:
            root, count = result
            self.window.notify("Debris moved", f"Moved {count} path(s) to:\n{root}")
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

        self.window.run_task(
            "Moving checked debris into /deleteme…",
            lambda: move_paths_to_deleteme(self.repo_root, existing, label="DEBRIS"),
            completed,
            error_title="Debris move failed",
        )



class ConfirmFileListDialog(QDialog):
    """Prominent final confirmation that exposes every affected path."""

    def __init__(self, title: str, warning: str, lines: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("foundryPopup")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
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
        open_saved = QPushButton("Open Saved Folder")
        open_saved.setToolTip("Open the remembered GODZIP/LOGZIP output folder in the system file manager.")
        open_saved.clicked.connect(self.open_saved_folder)
        fl.addLayout(summary_box, 1)
        fl.addWidget(open_saved)
        fl.addWidget(self.button)
        layout.addWidget(footer)

    def _output_dir(self) -> Path:
        settings = _load_local_settings(self.repo_root)
        remembered = str(settings.get("output_dir", "")).strip()
        return Path(remembered).expanduser() if remembered else self.repo_root.parent

    def open_saved_folder(self) -> None:
        self.window.open_folder(self._output_dir(), label="LOGZIP output folder")

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
        output_dir = self._output_dir()

        def completed(result: Any) -> None:
            self.window.set_status(f"Created {result.zip_path.name} from {len(result.files)} loose log file(s)")
            self.window.notify(
                "LOGZIP created",
                f"Created:\n{result.zip_path}\n\nFiles: {len(result.files)}\nSource logs were not removed.",
            )
            self.refresh()

        self.window.run_task(
            "Creating verified LOGZIP…",
            lambda: create_logzip(self.repo_root, names, output_dir=output_dir),
            completed,
            error_title="LOGZIP creation failed",
        )


class DiffResultDialog(QDialog):
    def __init__(self, parent: QWidget, title: str, text: str, summary: str) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setObjectName("foundryPopup")
        self.setModal(False)
        self.setWindowModality(Qt.WindowModality.NonModal)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setWindowFlag(Qt.WindowType.Tool, True)
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
        current_zip = self.current_zip
        if current_zip is None:
            return

        def completed(result: Any) -> None:
            summary = (
                f"{result.changed_files} changed file(s) · {result.added} added · "
                f"{result.modified} modified · {result.deleted} deleted · {result.binary} binary"
            )
            self.summary.setText(summary)
            dialog = DiffResultDialog(self, f"GODZIP DIFF — {current_zip.name}", result.text, summary)
            self.window._track_dialog(dialog)
            self.window.set_status(f"Generated DIFF against {current_zip.name}: {summary}")

        self.window.run_task(
            f"Diffing current repo against {current_zip.name}…",
            lambda: generate_godzip_diff(self.repo_root, current_zip),
            completed,
            error_title="GODZIP DIFF failed",
        )


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
        settings = _load_local_settings(self.repo_root)
        self.message = QLineEdit(str(settings.get("git_commit_message", "")))
        self.message.setPlaceholderText("Commit message…")
        self.message.editingFinished.connect(self.persist_message)
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

    def persist_message(self) -> None:
        _save_local_setting(self.repo_root, "git_commit_message", self.message.text())

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

    def commit(self, *, push: bool) -> None:
        message = self.message.text().strip()
        if not message:
            self.window.notify("Commit message required", "Enter a commit message first.", danger=True)
            return
        self.persist_message()
        lines = []
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            lines.append(f"{item.text(1):8} {item.text(0)}")
        warning = (
            "This will stage and commit EVERY Git-visible change listed below"
            + (" and then push the resulting commit if commit succeeds." if push else ".")
        )
        self.window.confirm_file_list(
            "Confirm commit",
            warning,
            lines,
            lambda: self._commit_now(message, push),
        )

    def _commit_now(self, message: str, push: bool) -> None:
        def worker() -> tuple[str, str]:
            head = git_commit_all(self.repo_root, message)
            pushed = git_push_current(self.repo_root) if push else ""
            return head, pushed

        def completed(result: tuple[str, str]) -> None:
            head, pushed = result
            detail = f"Committed {head[:10]}."
            if push:
                detail += "\n\nPush complete."
                if pushed:
                    detail += f"\n{pushed}"
            self.window.notify("Git operation complete", detail)
            self.persist_message()
            self.refresh()
            self.window.create_tab.refresh()

        self.window.run_task(
            "Committing Git changes" + (" and pushing…" if push else "…"),
            worker,
            completed,
            error_title="Commit/push failed",
        )

    def push(self) -> None:
        branch = git_branch(self.repo_root)
        head = git_head(self.repo_root)[:10]
        self.window.confirm(
            "Push current branch?",
            f"Push branch {branch} at HEAD {head}?\n\nNo force-push is permitted.",
            self._push_now,
            confirm_text="PUSH",
            danger=True,
        )

    def _push_now(self) -> None:
        def completed(detail: str) -> None:
            self.window.notify("Push complete", detail or "Push completed successfully.")
            self.window.refresh_repo_header()

        self.window.run_task(
            "Pushing current branch…",
            lambda: git_push_current(self.repo_root),
            completed,
            error_title="Push failed",
        )



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

    def refresh(self, *, on_loaded: Callable[[], None] | None = None) -> None:
        def completed(inspection: PullInspection) -> None:
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
            if on_loaded is not None:
                on_loaded()

        self.window.run_task(
            "Fetching remote and inspecting incoming changes…",
            lambda: inspect_pull(self.repo_root, fetch=True),
            completed,
            error_title="PULL inspection failed",
        )


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

    def _confirmation_lines(self, entries: list) -> list[str]:
        lines: list[str] = []
        for item in entries:
            local = " [LOCAL DIRTY]" if item.local_dirty else ""
            lines.append(f"{item.status:6} {item.display_path}{local}")
        return lines

    def pull_all(self) -> None:
        inspection = self.inspection
        if inspection is None:
            return
        self.window.confirm_file_list(
            "Confirm full pull",
            "MAJOR WARNING: this will advance local HEAD and replace/delete tracked files exactly as listed. "
            "The operation is strict fast-forward only and requires a clean worktree.",
            self._confirmation_lines(inspection.files),
            lambda: self._pull_all_now(inspection),
        )

    def _pull_all_now(self, inspection: PullInspection) -> None:
        def completed(detail: str) -> None:
            self.window.notify("Pull complete", detail or "Fast-forward pull completed.")
            self.window.refresh_repo_header()
            self.refresh(on_loaded=self.window.create_tab.refresh)

        self.window.run_task(
            "Applying reviewed fast-forward pull…",
            lambda: git_pull_ff_only(self.repo_root, inspection),
            completed,
            error_title="Pull failed",
        )

    def selective_sync(self) -> None:
        inspection = self.inspection
        if inspection is None:
            return
        selected = self.tree.checked_paths()
        chosen = [item for item in inspection.files if item.path in selected]
        self.window.confirm_file_list(
            "Confirm selective remote sync",
            "MAJOR WARNING: this does NOT advance HEAD. Checked remote states are copied into the working tree, "
            "remote deletions/rename sources are removed, and overwritten local files are backed up under /deleteme first.",
            self._confirmation_lines(chosen),
            lambda: self._selective_sync_now(inspection, selected),
        )

    def _selective_sync_now(self, inspection: PullInspection, selected: list[str]) -> None:
        def completed(result: Any) -> None:
            detail = (
                f"Written: {result.written}\n"
                f"Removed/renamed-away: {result.deleted}\n"
                f"HEAD unchanged: {git_head(self.repo_root)[:10]}"
            )
            if result.backup_dir:
                detail += f"\n\nRollback backup:\n{result.backup_dir}"
            self.window.notify("Selective sync complete", detail)
            self.window.refresh_repo_header()
            self.refresh(on_loaded=self.window.create_tab.refresh)

        self.window.run_task(
            "Synchronizing selected remote file states…",
            lambda: selective_sync_from_remote(self.repo_root, inspection, selected),
            completed,
            error_title="Selective sync failed",
        )



class RunTab(QWidget):
    """Repo-local SRPSS launcher with remembered diagnostic flag profiles."""

    runWaitFinished = Signal(object)

    def __init__(self, window: "GodzipFoundryWindow") -> None:
        super().__init__(window)
        self.window = window
        self.repo_root = window.repo_root
        self.flag_checks: dict[str, QCheckBox] = {}
        self._flags: tuple[str, ...] = ()
        self._building = False
        self._auto_logzip_process: subprocess.Popen | None = None
        self._auto_logzip_wait_thread: threading.Thread | None = None
        self.runWaitFinished.connect(self._run_wait_finished)
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
        self.keep_console.toggled.connect(self._keep_console_toggled)
        bottom.addWidget(self.keep_console)
        self.auto_logzip = QCheckBox("LogZIP after run automatically")
        self.auto_logzip.setToolTip(
            "After the launched SRPSS Python process has fully exited, bundle all direct loose /logs files "
            "to the remembered GODZIP output folder. Uses process.wait(); no polling or timer. "
            "Mutually exclusive with keeping the console open so session completion stays exact."
        )
        self.auto_logzip.toggled.connect(self._auto_logzip_toggled)
        bottom.addWidget(self.auto_logzip)
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

            auto_logzip = bool(settings.get("run_auto_logzip_after_exit", False))
            self.auto_logzip.setChecked(auto_logzip)
            self.keep_console.setChecked(
                bool(settings.get("run_keep_console_open", False)) and not auto_logzip
            )
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

    def _keep_console_toggled(self, checked: bool) -> None:
        if checked and self.auto_logzip.isChecked():
            self.auto_logzip.setChecked(False)
        self._selection_changed()

    def _auto_logzip_toggled(self, checked: bool) -> None:
        if checked and self.keep_console.isChecked():
            self.keep_console.setChecked(False)
        self._selection_changed()

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
                + (" LOGZIP will be created after SRPSS exits." if self.auto_logzip.isChecked() else "")
            )
        except Exception as exc:
            self.launch_button.setEnabled(False)
            self.run_status.setText(str(exc))

    def launch(self) -> None:
        entrypoint = self.entrypoint_combo.currentText() or "main.py"
        flags = self.selected_flags()
        keep_open = self.keep_console.isChecked()
        auto_logzip = self.auto_logzip.isChecked()
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
            _save_local_setting(self.repo_root, "run_auto_logzip_after_exit", auto_logzip)
            self.window.set_status(
                f"Launched {entrypoint} as PID {process.pid} with {len(flags)} flag(s)"
            )
            self.run_status.setText(
                f"Running as PID {process.pid}. "
                + ("Console will remain open after exit." if keep_open else "Console will close automatically when SRPSS exits.")
                + (" LOGZIP will be created only after the SRPSS process exits." if auto_logzip else "")
            )
            if auto_logzip:
                self._start_auto_logzip_wait(process)
        except Exception as exc:
            self.window.show_error("RUN launch failed", exc)

    def _start_auto_logzip_wait(self, process: subprocess.Popen) -> None:
        """Wait off the UI thread for the actual SRPSS process, without polling."""

        self._auto_logzip_process = process
        self.launch_button.setEnabled(False)
        self.auto_logzip.setEnabled(False)
        self.keep_console.setEnabled(False)

        def wait_for_exit() -> None:
            try:
                payload: object = ("ok", int(process.wait()))
            except Exception as exc:  # pragma: no cover - OS/process failure path
                payload = ("error", str(exc))
            try:
                self.runWaitFinished.emit(payload)
            except RuntimeError:
                # Foundry may have been closed while SRPSS was still running.
                pass

        self._auto_logzip_wait_thread = threading.Thread(
            target=wait_for_exit,
            name="GodzipFoundryRunWait",
            daemon=True,
        )
        self._auto_logzip_wait_thread.start()

    def _run_wait_finished(self, payload: object) -> None:
        self._auto_logzip_process = None
        self._auto_logzip_wait_thread = None
        self.auto_logzip.setEnabled(True)
        self.keep_console.setEnabled(True)

        status, detail = (
            payload
            if isinstance(payload, tuple) and len(payload) == 2
            else ("error", "invalid wait result")
        )
        if status != "ok":
            self._update_preview()
            self.window.show_error("RUN completion watch failed", detail)
            return

        logs = collect_log_files(self.repo_root)
        if not logs:
            message = (
                f"SRPSS exited with code {detail}; Auto-LOGZIP skipped because /logs "
                "has no direct loose files."
            )
            self.window.set_status(message)
            self.run_status.setText(message)
            self.window.logzip_tab.refresh()
            self._update_preview()
            return

        output_dir = self.window.logzip_tab._output_dir()
        self._update_preview()

        def completed(result: Any) -> None:
            message = (
                f"SRPSS exited with code {detail}; created {result.zip_path.name} "
                f"from {len(result.files)} loose log file(s)."
            )
            self.window.set_status(message)
            self.run_status.setText(f"{message}\n{result.zip_path}")
            self.window.logzip_tab.refresh()

        self.window.run_task(
            "SRPSS exited — creating automatic LOGZIP…",
            lambda: create_logzip(self.repo_root, output_dir=output_dir),
            completed,
            error_title="Automatic LOGZIP creation failed",
        )


class CommandTab(QWidget):
    """Repo-root shell launcher; elevation is explicit because it triggers UAC."""

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
        intro_l = QVBoxLayout(intro)
        intro_l.setContentsMargins(16, 14, 16, 14)
        title = QLabel("REPO COMMAND SHELLS")
        title.setObjectName("sectionTitle")
        intro_l.addWidget(title)
        desc = QLabel(
            "Open a terminal directly at the repository root. Administrator mode is opt-in because Windows will show UAC."
        )
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        intro_l.addWidget(desc)
        layout.addWidget(intro)

        panel = Panel()
        panel_l = QVBoxLayout(panel)
        panel_l.setContentsMargins(18, 18, 18, 18)
        panel_l.setSpacing(14)

        path = QLabel(str(self.repo_root))
        path.setObjectName("repoPath")
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        panel_l.addWidget(path)

        local = _load_local_settings(self.repo_root)
        self.admin = QCheckBox("Run terminal as Administrator")
        self.admin.setChecked(bool(local.get("cmd_admin", False)))
        self.admin.toggled.connect(
            lambda checked: _save_local_setting(self.repo_root, "cmd_admin", bool(checked))
        )
        panel_l.addWidget(self.admin)

        shells = QHBoxLayout()
        for label, kind in (
            ("POWERSHELL", "powershell"),
            ("CMD", "cmd"),
            ("BASH", "bash"),
        ):
            button = QPushButton(label)
            button.setObjectName("primaryButton" if kind == "powershell" else "")
            button.setMinimumHeight(44)
            button.clicked.connect(lambda _checked=False, shell=kind: self._launch(shell))
            shells.addWidget(button)
        panel_l.addLayout(shells)

        utility = QHBoxLayout()
        explorer = QPushButton("OPEN REPO IN EXPLORER")
        explorer.clicked.connect(
            lambda: self.window.open_folder(self.repo_root, label="repository")
        )
        copy_path = QPushButton("COPY REPO PATH")
        copy_path.clicked.connect(self._copy_path)
        utility.addWidget(explorer)
        utility.addWidget(copy_path)
        utility.addStretch(1)
        panel_l.addLayout(utility)

        layout.addWidget(panel)
        layout.addStretch(1)

    def _copy_path(self) -> None:
        QApplication.clipboard().setText(str(self.repo_root))
        self.window.set_status("Repository path copied to clipboard")

    def _git_bash(self) -> str | None:
        if os.name != "nt":
            return shutil.which("bash")
        candidates: list[Path] = []
        for root_name in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
            raw = os.environ.get(root_name)
            if not raw:
                continue
            base = Path(raw)
            if root_name == "LocalAppData":
                candidates.append(base / "Programs" / "Git" / "bin" / "bash.exe")
            else:
                candidates.append(base / "Git" / "bin" / "bash.exe")
        for candidate in candidates:
            if candidate.is_file():
                return str(candidate)
        resolved = shutil.which("bash.exe") or shutil.which("bash")
        return str(resolved) if resolved else None

    def _shell_spec(self, shell: str) -> tuple[str, list[str]]:
        root = str(self.repo_root)
        if shell == "powershell":
            executable = shutil.which("powershell.exe") or shutil.which("pwsh.exe") or shutil.which("pwsh")
            if not executable:
                raise GodzipError("PowerShell was not found on PATH")
            escaped = root.replace("'", "''")
            return str(executable), ["-NoExit", "-Command", f"Set-Location -LiteralPath '{escaped}'"]
        if shell == "cmd":
            executable = shutil.which("cmd.exe") or (r"C:\Windows\System32\cmd.exe" if os.name == "nt" else None)
            if not executable:
                raise GodzipError("cmd.exe is only available on Windows")
            return str(executable), ["/K", f'cd /d "{root}"']
        if shell == "bash":
            executable = self._git_bash()
            if not executable:
                raise GodzipError("Git Bash / bash was not found")
            return str(executable), ["-i"]
        raise GodzipError(f"Unknown shell request: {shell}")

    def _launch(self, shell: str) -> None:
        try:
            executable, args = self._shell_spec(shell)
            if self.admin.isChecked():
                if os.name != "nt":
                    raise GodzipError("Administrator launch is currently supported only on Windows")
                params = subprocess.list2cmdline(args)
                result = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "runas",
                    executable,
                    params,
                    str(self.repo_root),
                    1,
                )
                if int(result) <= 32:
                    raise GodzipError(f"Windows elevation launch failed with code {int(result)}")
            else:
                subprocess.Popen(args=[executable, *args], cwd=str(self.repo_root))
            self.window.set_status(
                f"Opened {shell.upper()} at repository root"
                + (" as Administrator" if self.admin.isChecked() else "")
            )
        except Exception as exc:
            self.window.show_error(f"Open {shell.upper()} failed", exc)


class GodzipFoundryWindow(QMainWindow):
    def __init__(self, repo_root: Path, initial_zip: Path | None = None) -> None:
        super().__init__()
        self.repo_root = repo_root.expanduser().resolve()
        local_settings = _load_local_settings(self.repo_root)
        requested_theme = str(local_settings.get("theme_id", FOUNDRY_DEFAULT_THEME_ID))
        self.theme_resolution = resolve_foundry_theme(requested_theme)
        self._floating_dialogs: set[QDialog] = set()
        self._settings_dialog: FoundrySettingsDialog | None = None
        self._task_active = False
        self._task_bridge: _TaskBridge | None = None
        self._task_thread: threading.Thread | None = None
        self._native_backdrop_mode: str | None = None
        self._backdrop_applied = False

        self.setWindowTitle(APP_TITLE)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinMaxButtonsHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.setMinimumSize(900, 680)
        self._fit_to_screen()
        self._set_icon()
        self._build_ui()
        self._apply_style()
        self.refresh_repo_header()
        # Expensive repo/archive inspection now runs off the GUI thread. Avoid
        # scheduling two startup operations against the single mutation lane.
        if initial_zip is not None:
            self.tabs.setCurrentWidget(self.apply_tab)
            QTimer.singleShot(0, lambda: self.apply_tab.load_zip(initial_zip))
        else:
            self.create_tab.refresh()
        QTimer.singleShot(0, self._apply_native_backdrop_theme)

    def open_folder(self, path: Path, *, label: str = "folder") -> None:
        """Open one existing directory through the desktop shell; never spawn a console."""

        target = Path(path).expanduser().resolve()
        if not target.is_dir():
            self.show_error(f"Cannot open {label}", GodzipError(f"Directory does not exist: {target}"))
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
            self.show_error(f"Cannot open {label}", GodzipError(f"Desktop shell refused directory: {target}"))

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
        try:
            self.push_tab.persist_message()
        except Exception:
            pass
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

        header = FoundryHeaderFrame(self)
        header.setMinimumHeight(86)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 16, 10, 15)
        titles = QVBoxLayout()
        title = QLabel("GODZIP FOUNDRY")
        title.setObjectName("appTitle")
        title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        titles.addWidget(title)
        subtitle = QLabel("Manifested repo transfer · ancestry-aware apply · reversible debris")
        subtitle.setObjectName("subtitle")
        subtitle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        titles.addWidget(subtitle)
        hl.addLayout(titles, 1)
        self.branch_badge = QLabel()
        self.branch_badge.setObjectName("chip")
        self.branch_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.head_badge = QLabel()
        self.head_badge.setObjectName("chip")
        self.head_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.dirty_badge = QLabel()
        self.dirty_badge.setObjectName("chip")
        self.dirty_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        hl.addWidget(self.branch_badge)
        hl.addWidget(self.head_badge)
        hl.addWidget(self.dirty_badge)
        settings_button = QPushButton("⚙")
        settings_button.setObjectName("toolTitleSettingsButton")
        settings_button.setFixedSize(38, 34)
        settings_button.setToolTip("Foundry Settings")
        settings_button.clicked.connect(self.open_foundry_settings)
        hl.addWidget(settings_button)
        minimize_button = QPushButton("−")
        minimize_button.setObjectName("toolTitleButton")
        minimize_button.setFixedSize(40, 34)
        minimize_button.clicked.connect(self.showMinimized)
        hl.addWidget(minimize_button)
        self.maximize_button = QPushButton("□")
        self.maximize_button.setObjectName("toolTitleButton")
        self.maximize_button.setFixedSize(40, 34)
        self.maximize_button.clicked.connect(self._toggle_maximized)
        hl.addWidget(self.maximize_button)
        close_button = QPushButton("×")
        close_button.setObjectName("toolTitleCloseButton")
        close_button.setFixedSize(40, 34)
        close_button.clicked.connect(self.close)
        hl.addWidget(close_button)
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
        self.command_tab = CommandTab(self)
        self.tabs.addTab(self.create_tab, "CREATE GOD ZIP")
        self.tabs.addTab(self.apply_tab, "APPLY GOD ZIP")
        self.tabs.addTab(self.diff_tab, "DIFF")
        self.tabs.addTab(self.logzip_tab, "LOGZIP")
        self.tabs.addTab(self.push_tab, "PUSH")
        self.tabs.addTab(self.pull_tab, "PULL")
        self.tabs.addTab(self.debris_tab, "DEBRIS")
        self.tabs.addTab(self.run_tab, "RUN")
        command_index = self.tabs.addTab(self.command_tab, "CMD")
        try:
            self.tabs.tabBar().setTabVisible(command_index, False)
        except AttributeError:
            self.tabs.tabBar().setTabEnabled(command_index, False)
        self.cmd_tab_button = QPushButton("CMD")
        self.cmd_tab_button.setObjectName("cmdTabButton")
        self.cmd_tab_button.setCheckable(True)
        self.cmd_tab_button.setFixedHeight(38)
        self.cmd_tab_button.clicked.connect(lambda: self.tabs.setCurrentWidget(self.command_tab))
        self.tabs.setCornerWidget(self.cmd_tab_button, Qt.Corner.TopRightCorner)
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
        if hasattr(self, "cmd_tab_button"):
            self.cmd_tab_button.setChecked(current is self.command_tab)
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

    def _toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
            self.maximize_button.setText("□")
        else:
            self.showMaximized()
            self.maximize_button.setText("❐")

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

    def theme_qcolor(self, token: str) -> QColor:
        value = self.theme_resolution.theme.color(token)
        return QColor(value.r, value.g, value.b, value.a)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_busy(self, busy: bool, text: str = "") -> None:
        """Expose progress without freezing the GUI or replacing the cursor."""

        if text:
            self.set_status(text)
        self.busy.setVisible(bool(busy))

    def _track_dialog(self, dialog: QDialog) -> None:
        self._floating_dialogs.add(dialog)
        dialog.finished.connect(lambda _code, d=dialog: self._floating_dialogs.discard(d))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def notify(self, title: str, message: str, *, danger: bool = False) -> None:
        self._track_dialog(FoundryNoticeDialog(title, message, self, danger=danger))

    def confirm(
        self,
        title: str,
        message: str,
        on_confirm: Callable[[], None],
        *,
        confirm_text: str = "CONTINUE",
        danger: bool = False,
    ) -> None:
        dialog = FoundryConfirmDialog(
            title,
            message,
            self,
            confirm_text=confirm_text,
            danger=danger,
        )
        dialog.accepted.connect(on_confirm)
        self._track_dialog(dialog)

    def confirm_file_list(
        self,
        title: str,
        warning: str,
        lines: list[str],
        on_confirm: Callable[[], None],
    ) -> None:
        dialog = ConfirmFileListDialog(title, warning, lines, self)
        dialog.accepted.connect(on_confirm)
        self._track_dialog(dialog)

    def show_error(self, title: str, exc: Exception) -> None:
        message = str(exc) if str(exc) else exc.__class__.__name__
        self.set_status(f"{title}: {message}")
        self.notify(title, message, danger=True)

    def run_task(
        self,
        status: str,
        worker: Callable[[], Any],
        on_success: Callable[[Any], None] | None = None,
        *,
        error_title: str = "Operation failed",
    ) -> bool:
        """Run one core operation off the Qt thread; mutations never overlap."""

        if self._task_active:
            self.notify(
                "Operation already running",
                "Finish the current Foundry operation before starting another one.",
            )
            return False

        self._task_active = True
        self.set_busy(True, status)
        bridge = _TaskBridge(self)
        self._task_bridge = bridge

        def finish_success(result: Any) -> None:
            self._task_active = False
            self.set_busy(False)
            self._task_bridge = None
            self._task_thread = None
            if on_success is not None:
                try:
                    on_success(result)
                except Exception as exc:
                    self.show_error(error_title, exc)

        def finish_error(exc: Exception) -> None:
            self._task_active = False
            self.set_busy(False)
            self._task_bridge = None
            self._task_thread = None
            self.show_error(error_title, exc)

        bridge.succeeded.connect(finish_success)
        bridge.failed.connect(finish_error)

        def run() -> None:
            try:
                result = worker()
            except Exception as exc:
                bridge.failed.emit(exc)
            else:
                bridge.succeeded.emit(result)

        thread = threading.Thread(target=run, name="godzip-foundry-worker", daemon=True)
        self._task_thread = thread
        thread.start()
        return True

    def open_foundry_settings(self) -> None:
        dialog = self._settings_dialog
        if dialog is None:
            dialog = FoundrySettingsDialog(self)
            self._settings_dialog = dialog
            dialog.finished.connect(lambda _code: setattr(self, "_settings_dialog", None))
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def set_foundry_theme(self, theme_id: str) -> None:
        resolution = resolve_foundry_theme(theme_id)
        self.theme_resolution = resolution
        _save_local_setting(self.repo_root, "theme_id", resolution.theme_id)
        self._apply_style()
        self._apply_native_backdrop_theme()
        self.set_status(f"Foundry theme: {resolution.theme.name}")
        if resolution.warning:
            self.notify("Theme fallback", resolution.warning)

    def _apply_native_backdrop_theme(self) -> bool:
        """Use the same DWM Acrylic/Glass mechanism as Settings when available."""

        if os.name != "nt":
            return False
        try:
            theme = self.theme_resolution.theme
            backdrop = theme.backdrop
            hwnd = int(self.winId())
            if backdrop.mode == "acrylic":
                from core.windows.dwm_blur import enable_acrylic_blur

                enabled = enable_acrylic_blur(
                    hwnd,
                    tint_r=backdrop.tint.r,
                    tint_g=backdrop.tint.g,
                    tint_b=backdrop.tint.b,
                    tint_alpha=backdrop.tint.a,
                )
            elif backdrop.mode == "glass":
                from core.windows.dwm_blur import enable_glass_blur

                enabled = enable_glass_blur(hwnd)
            else:
                from core.windows.dwm_blur import disable_blur

                disable_blur(hwnd)
                enabled = False
            self._native_backdrop_mode = backdrop.mode
            self._backdrop_applied = backdrop.mode == "off" or bool(enabled)
            return bool(enabled)
        except Exception:
            self._backdrop_applied = False
            return False

    def _set_drop_active(self, active: bool) -> None:
        panel = getattr(getattr(self, "apply_tab", None), "drop_panel", None)
        if panel is None:
            return
        panel.setProperty("dragActive", bool(active))
        panel.style().unpolish(panel)
        panel.style().polish(panel)

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        urls = event.mimeData().urls() if event.mimeData().hasUrls() else []
        if any(Path(url.toLocalFile()).suffix.lower() in {".zip", ".json"} for url in urls):
            self._set_drop_active(True)
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dragLeaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_drop_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # type: ignore[override]
        self._set_drop_active(False)
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
        self.setStyleSheet(render_foundry_stylesheet(self.theme_resolution.theme))


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
