#!/usr/bin/env python3
"""SRPSS Widget Theme Foundry — lightweight schema-v3 .srwtheme editor.

This tool edits the exact WidgetThemeSpec consumed by retained Qt Quick runtime
surfaces.  It owns no runtime schema, widget geometry, materials, cadence, or
family-local style values.  Optional roles remain sparse and may be removed to
return to the production inheritance chain in ui.widget_visual_roles.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def _early_repo_root() -> Path:
    argv = sys.argv[1:]
    for index, arg in enumerate(argv):
        if arg == "--repo" and index + 1 < len(argv):
            return Path(argv[index + 1]).expanduser().resolve()
        if arg.startswith("--repo="):
            return Path(arg.split("=", 1)[1]).expanduser().resolve()
    script = Path(__file__).resolve()
    if len(script.parents) >= 2 and (script.parents[1] / "ui").is_dir():
        return script.parents[1]
    return Path.cwd().resolve()


REPO_ROOT = _early_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
TOOLS_DIR = REPO_ROOT / "tools"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from PySide6.QtCore import QRect, Qt, Signal  # noqa: E402
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.settings_theme_spec import Rgba  # noqa: E402
from ui.widget_theme_catalog import CANONICAL_DEFAULT_WIDGET_THEME_FILENAME  # noqa: E402
from ui.widget_theme_io import (  # noqa: E402
    WIDGET_THEME_FILE_EXTENSION,
    WidgetThemeFileError,
    discover_widget_theme_files,
    load_widget_theme_file,
    save_widget_theme_file,
    widget_theme_from_json,
    widget_theme_to_json,
)
from ui.widget_theme_spec import (  # noqa: E402
    DEFAULT_DARK_WIDGET_THEME,
    WIDGET_THEME_CORE_COLOR_ROLES,
    WidgetThemeSpec,
)
from ui.widget_visual_roles import WIDGET_VISUAL_ROLE_PARENTS  # noqa: E402
from widget_theme_foundry_model import (  # noqa: E402
    WidgetThemeDraft,
    all_widget_theme_roles,
    default_seed_color,
    friendly_role_label,
    most_used_colors,
    replace_exact_color_matches,
    rgba_summary,
    role_group,
    safe_theme_filename,
    theme_id_for_save_as,
)

APP_TITLE = "SRPSS Widget Theme Foundry"
THEMES_DIR = REPO_ROOT / "themes" / "widgets"


class ColorPreview(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, *, clickable: bool = False) -> None:
        super().__init__(parent)
        self._color = Rgba(255, 255, 255, 255)
        self._clickable = clickable
        self.setMinimumWidth(180)
        self.setFixedHeight(78)
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)

    def set_rgba(self, color: Rgba) -> None:
        self._color = color
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        cell = 10
        a = QColor(50, 50, 50)
        b = QColor(88, 88, 88)
        for y in range(0, self.height(), cell):
            for x in range(0, self.width(), cell):
                painter.fillRect(
                    QRect(x, y, cell, cell),
                    a if ((x // cell) + (y // cell)) % 2 == 0 else b,
                )
        painter.fillRect(self.rect(), QColor(*self._color.as_tuple()))
        painter.setPen(QPen(QColor(255, 255, 255, 160), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))


class SwatchButton(QPushButton):
    colorRequested = Signal()

    def __init__(self, text: str = "Choose Colour…", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._rgba = Rgba(255, 255, 255, 255)
        self.clicked.connect(self.colorRequested.emit)
        self.setMinimumHeight(36)

    def set_rgba(self, color: Rgba) -> None:
        self._rgba = color
        fg = "#101719" if (color.r * 299 + color.g * 587 + color.b * 114) / 1000 > 155 else "#f7f4ea"
        self.setStyleSheet(
            "QPushButton {"
            f"background-color: rgba({color.r},{color.g},{color.b},{color.a}); color:{fg};"
            "border:1px solid rgba(244,198,109,180); border-radius:7px; padding:7px 10px; font-weight:700;"
            "} QPushButton:hover { border-color:#fff0ba; }"
        )


class WidgetThemeFoundryWindow(QMainWindow):
    COL_ROLE = 0
    COL_STATE = 1
    COL_VALUE = 2

    def __init__(self, repo_root: Path, initial_path: Path | None = None) -> None:
        super().__init__()
        self.repo_root = repo_root
        self.themes_dir = repo_root / "themes" / "widgets"
        self.default_spec = DEFAULT_DARK_WIDGET_THEME
        self.opened_spec = self.default_spec
        self.draft = WidgetThemeDraft.from_spec(self.default_spec)
        self.theme_path: Path | None = None
        self.selected_role: str | None = None
        self._spin_guard = False
        self._file_paths: list[Path] = []
        self._most_used_entries: list[tuple[Rgba, tuple[str, ...]]] = []

        self.setWindowTitle(APP_TITLE)
        icon_path = self.repo_root / "images" / "foundries" / "SRPSSTheme.ico"
        if icon_path.is_file():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.resize(1260, 810)
        self.setMinimumSize(980, 650)
        self._apply_style()
        self._build_ui()
        self._refresh_file_list()
        if initial_path is not None:
            self._open_theme_path(initial_path)
        else:
            self._load_spec(self.default_spec, None)

    # ---- UI ---------------------------------------------------------
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("widgetThemeFoundryRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 12, 14, 10)
        outer.setSpacing(10)

        title_row = QHBoxLayout()
        title = QLabel("WIDGET THEME FOUNDRY")
        title.setObjectName("foundryTitle")
        font = QFont(title.font())
        font.setPointSize(max(font.pointSize(), 17))
        font.setBold(True)
        title.setFont(font)
        title_row.addWidget(title)
        title_row.addStretch(1)
        self.schema_label = QLabel("SCHEMA v3 · COLOUR ONLY")
        self.schema_label.setObjectName("scopePill")
        title_row.addWidget(self.schema_label)
        outer.addLayout(title_row)

        subtitle = QLabel(
            "Edit the exact retained Widget Theme palette. Shared semantics first; optional special roles stay sparse and inherited until you override them."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        quick = QHBoxLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.setMinimumWidth(330)
        quick.addWidget(QLabel("Theme"))
        quick.addWidget(self.theme_combo, 1)
        self.open_selected_btn = QPushButton("OPEN SELECTED")
        self.open_selected_btn.clicked.connect(self._open_combo_theme)
        quick.addWidget(self.open_selected_btn)
        self.refresh_files_btn = QPushButton("↻")
        self.refresh_files_btn.setFixedWidth(42)
        self.refresh_files_btn.setToolTip("Refresh themes/widgets")
        self.refresh_files_btn.clicked.connect(self._refresh_file_list)
        quick.addWidget(self.refresh_files_btn)
        self.new_btn = QPushButton("NEW")
        self.new_btn.clicked.connect(self.new_from_default)
        quick.addWidget(self.new_btn)
        self.open_btn = QPushButton("OPEN…")
        self.open_btn.clicked.connect(self.open_theme)
        quick.addWidget(self.open_btn)
        self.save_btn = QPushButton("SAVE")
        self.save_btn.setObjectName("primary")
        self.save_btn.clicked.connect(self.save_theme)
        quick.addWidget(self.save_btn)
        self.save_as_btn = QPushButton("SAVE AS…")
        self.save_as_btn.clicked.connect(self.save_theme_as)
        quick.addWidget(self.save_as_btn)
        outer.addLayout(quick)

        meta = QFrame()
        meta.setObjectName("metaBox")
        meta_l = QGridLayout(meta)
        meta_l.setContentsMargins(10, 8, 10, 8)
        self.name_edit = QLineEdit()
        self.name_edit.textEdited.connect(self._name_changed)
        self.id_label = QLabel()
        self.id_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.link_label = QLabel()
        self.link_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.path_label = QLabel()
        self.path_label.setObjectName("muted")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        meta_l.addWidget(QLabel("Name"), 0, 0)
        meta_l.addWidget(self.name_edit, 0, 1)
        meta_l.addWidget(QLabel("Theme ID"), 0, 2)
        meta_l.addWidget(self.id_label, 0, 3)
        meta_l.addWidget(QLabel("Linked Settings"), 1, 0)
        meta_l.addWidget(self.link_label, 1, 1, 1, 3)
        meta_l.addWidget(QLabel("File"), 2, 0)
        meta_l.addWidget(self.path_label, 2, 1, 1, 3)
        meta_l.setColumnStretch(1, 2)
        meta_l.setColumnStretch(3, 2)
        outer.addWidget(meta)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, 1)

        # Left: role browser.
        left = QFrame()
        left.setObjectName("pane")
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(10, 10, 10, 10)
        filter_row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter roles…")
        self.search_edit.textChanged.connect(self._apply_tree_filter)
        filter_row.addWidget(self.search_edit, 1)
        self.category_combo = QComboBox()
        self.category_combo.addItems([
            "All",
            "Shared Card",
            "Shared Widget",
            "Media",
            "Context Menu",
            "Mail / Reddit / Weather / Clock",
            "Steam",
            "Other",
        ])
        self.category_combo.currentTextChanged.connect(self._apply_tree_filter)
        filter_row.addWidget(self.category_combo)
        left_l.addLayout(filter_row)
        self.tree = QTreeWidget()
        self.tree.setObjectName("roleTree")
        self.tree.setHeaderLabels(["Semantic role", "State", "Working colour"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.itemSelectionChanged.connect(self._selection_changed)
        header = self.tree.header()
        header.setSectionResizeMode(self.COL_ROLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_STATE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_VALUE, QHeaderView.ResizeMode.ResizeToContents)
        left_l.addWidget(self.tree, 1)
        splitter.addWidget(left)

        # Right: selected role + tools.
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right = QWidget()
        right.setObjectName("editor")
        right_scroll.setWidget(right)
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(12, 12, 12, 12)
        right_l.setSpacing(10)

        self.role_title = QLabel("SELECT A ROLE")
        self.role_title.setObjectName("sectionTitle")
        right_l.addWidget(self.role_title)
        self.role_token = QLabel("")
        self.role_token.setObjectName("muted")
        self.role_token.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        right_l.addWidget(self.role_token)
        self.state_banner = QLabel("Select a semantic colour role from the tree.")
        self.state_banner.setObjectName("stateBanner")
        self.state_banner.setWordWrap(True)
        right_l.addWidget(self.state_banner)

        self.preview = ColorPreview(clickable=True)
        self.preview.clicked.connect(self._choose_selected_color)
        right_l.addWidget(self.preview)
        self.swatch = SwatchButton()
        self.swatch.colorRequested.connect(self._choose_selected_color)
        right_l.addWidget(self.swatch)

        channel_grid = QGridLayout()
        self.r_spin = self._channel_spin()
        self.g_spin = self._channel_spin()
        self.b_spin = self._channel_spin()
        self.a_spin = self._channel_spin()
        for index, (label, spin) in enumerate((('R', self.r_spin), ('G', self.g_spin), ('B', self.b_spin), ('A', self.a_spin))):
            channel_grid.addWidget(QLabel(label), 0, index)
            channel_grid.addWidget(spin, 1, index)
            spin.valueChanged.connect(self._spins_changed)
        right_l.addLayout(channel_grid)

        hex_row = QHBoxLayout()
        self.hex_edit = QLineEdit()
        self.hex_edit.setPlaceholderText("#RRGGBB or #RRGGBBAA")
        self.hex_edit.returnPressed.connect(self._apply_hex)
        hex_row.addWidget(self.hex_edit, 1)
        self.hex_apply_btn = QPushButton("APPLY HEX")
        self.hex_apply_btn.clicked.connect(self._apply_hex)
        hex_row.addWidget(self.hex_apply_btn)
        self.copy_btn = QPushButton("COPY RGBA")
        self.copy_btn.clicked.connect(self._copy_rgba)
        hex_row.addWidget(self.copy_btn)
        right_l.addLayout(hex_row)

        role_actions = QHBoxLayout()
        self.bulk_btn = QPushButton("CHANGE ALL EXACT MATCHES…")
        self.bulk_btn.clicked.connect(self._bulk_replace_selected)
        role_actions.addWidget(self.bulk_btn)
        self.remove_override_btn = QPushButton("REMOVE OPTIONAL OVERRIDE")
        self.remove_override_btn.clicked.connect(self._remove_override)
        role_actions.addWidget(self.remove_override_btn)
        right_l.addLayout(role_actions)

        reset_actions = QGridLayout()
        self.reset_opened_btn = QPushButton("RESET ROLE → OPENED")
        self.reset_opened_btn.clicked.connect(self._reset_role_opened)
        self.reset_default_btn = QPushButton("RESET ROLE → DEFAULT")
        self.reset_default_btn.clicked.connect(self._reset_role_default)
        self.reset_all_opened_btn = QPushButton("RESET ALL → OPENED")
        self.reset_all_opened_btn.clicked.connect(self._reset_all_opened)
        self.reset_all_default_btn = QPushButton("RESET ALL → DEFAULT DARK")
        self.reset_all_default_btn.clicked.connect(self._reset_all_default)
        reset_actions.addWidget(self.reset_opened_btn, 0, 0)
        reset_actions.addWidget(self.reset_default_btn, 0, 1)
        reset_actions.addWidget(self.reset_all_opened_btn, 1, 0)
        reset_actions.addWidget(self.reset_all_default_btn, 1, 1)
        right_l.addLayout(reset_actions)

        used_title = QLabel("MOST USED COLOURS")
        used_title.setObjectName("sectionTitle")
        right_l.addWidget(used_title)
        used_note = QLabel("Click a palette swatch to replace every exact RGBA match in this Widget Theme.")
        used_note.setObjectName("muted")
        used_note.setWordWrap(True)
        right_l.addWidget(used_note)
        self.most_used_buttons: list[SwatchButton] = []
        self.most_used_counts: list[QLabel] = []
        for index in range(6):
            row = QHBoxLayout()
            button = SwatchButton("")
            button.colorRequested.connect(lambda index=index: self._replace_most_used(index))
            count = QLabel("")
            count.setObjectName("muted")
            count.setMinimumWidth(64)
            count.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            row.addWidget(button, 1)
            row.addWidget(count)
            right_l.addLayout(row)
            self.most_used_buttons.append(button)
            self.most_used_counts.append(count)

        inheritance_title = QLabel("INHERITANCE")
        inheritance_title.setObjectName("sectionTitle")
        right_l.addWidget(inheritance_title)
        self.inheritance_label = QLabel("")
        self.inheritance_label.setObjectName("infoBox")
        self.inheritance_label.setWordWrap(True)
        right_l.addWidget(self.inheritance_label)
        right_l.addStretch(1)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        status = QStatusBar()
        self.setStatusBar(status)
        self.statusBar().showMessage("Ready")
        self._set_editor_enabled(False)

    def _channel_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 255)
        spin.setMinimumWidth(70)
        return spin

    def _apply_style(self) -> None:
        # Intentionally shares Theme Foundry's visual language and icon family.
        self.setStyleSheet(
            """
            QMainWindow { background:#0d181e; color:#f4f0e6; }
            QWidget { color:#f4f0e6; font-family:'Jost','Segoe UI',sans-serif; font-size:10pt; }
            QWidget#widgetThemeFoundryRoot { background:#111a1e; }
            QFrame#pane, QWidget#editor, QFrame#metaBox {
                background:rgba(10,15,17,220); border:1px solid rgba(225,193,127,100); border-radius:10px;
            }
            QLabel#foundryTitle, QLabel#sectionTitle { color:#f4c66d; font-weight:700; letter-spacing:1px; }
            QLabel#subtitle, QLabel#muted { color:#9fb2ad; }
            QLabel#scopePill { background:#263b3a; color:#f4c66d; border:1px solid #8f7950; border-radius:8px; padding:5px 9px; font-weight:700; }
            QLabel#stateBanner, QLabel#infoBox {
                background:rgba(16,25,27,210); border:1px solid rgba(225,193,127,110); border-radius:8px; padding:8px; color:#dce5df;
            }
            QLabel#stateBanner { color:#f4c66d; }
            QLineEdit, QComboBox, QSpinBox {
                background:#1f2626; color:#f4f0e6; border:1px solid #8f7950; border-radius:7px; padding:5px;
            }
            QTreeWidget#roleTree {
                background-color:rgba(10,15,17,218); alternate-background-color:rgba(31,38,38,205);
                border:1px solid rgba(225,193,127,150); border-radius:10px; color:#edf1ed; outline:none;
            }
            QTreeWidget::item { min-height:27px; padding:2px 5px; }
            QTreeWidget::item:selected { background:rgba(60,108,103,210); }
            QHeaderView::section { background:#1f2f30; color:#f4c66d; border:none; padding:7px; font-weight:700; }
            QPushButton { background:#263b3a; color:#f4f0e6; border:1px solid #8f7950; border-radius:7px; padding:7px 11px; font-weight:600; }
            QPushButton:hover { background:#33504d; border-color:#f4c66d; }
            QPushButton:disabled { color:#6f7e7b; border-color:#4f554e; background:#1b2424; }
            QPushButton#primary { background:#d59b42; color:#101719; border-color:#f4c66d; }
            QStatusBar { background:#0a0f11; color:#c8d4d1; }
            QSplitter::handle { background:#273436; width:2px; }
            """
        )

    # ---- loading / file lifecycle ---------------------------------
    def _refresh_file_list(self) -> None:
        self._file_paths = list(discover_widget_theme_files(self.themes_dir))
        current = self.theme_combo.currentText()
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        self.theme_combo.addItem("Compiled Default Dark", None)
        for path in self._file_paths:
            self.theme_combo.addItem(path.name, str(path))
        if current:
            index = self.theme_combo.findText(current)
            if index >= 0:
                self.theme_combo.setCurrentIndex(index)
        self.theme_combo.blockSignals(False)

    def _open_combo_theme(self) -> None:
        data = self.theme_combo.currentData()
        if data is None:
            if self._confirm_discard_if_dirty():
                self._load_spec(self.default_spec, None)
            return
        if self._confirm_discard_if_dirty():
            self._open_theme_path(Path(str(data)))

    def open_theme(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Widget Theme",
            str(self.themes_dir),
            f"SRPSS Widget Theme (*{WIDGET_THEME_FILE_EXTENSION});;All Files (*)",
        )
        if path_str:
            self._open_theme_path(Path(path_str))

    def _open_theme_path(self, path: Path) -> None:
        try:
            spec = load_widget_theme_file(path)
        except Exception as exc:
            self._error("Open Widget Theme failed", str(exc))
            return
        self._load_spec(spec, path)
        self.statusBar().showMessage(f"Loaded {path.name}", 6000)

    def _load_spec(self, spec: WidgetThemeSpec, path: Path | None) -> None:
        self.opened_spec = spec
        self.draft = WidgetThemeDraft.from_spec(spec)
        self.theme_path = path
        self.name_edit.setText(spec.name)
        self.id_label.setText(spec.theme_id)
        self.link_label.setText(spec.linked_settings_theme_id or "UNLINKED")
        self.path_label.setText(str(path) if path is not None else "Compiled Default Dark")
        self.selected_role = None
        self._rebuild_tree()
        self._refresh_most_used()
        self._set_editor_enabled(False)
        self._update_dirty_status()

    def new_from_default(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        draft = WidgetThemeDraft.from_spec(self.default_spec)
        draft.name = "Untitled Widget Theme"
        draft.theme_id = "widget:untitled"
        draft.linked_settings_theme_id = None
        self.opened_spec = draft.to_spec()
        self.draft = WidgetThemeDraft.from_spec(self.opened_spec)
        self.theme_path = None
        self.name_edit.setText(self.draft.name)
        self.id_label.setText(self.draft.theme_id)
        self.link_label.setText("UNLINKED")
        self.path_label.setText("New unsaved Widget Theme")
        self.selected_role = None
        self._rebuild_tree()
        self._refresh_most_used()
        self._set_editor_enabled(False)
        self._update_dirty_status()

    def save_theme(self) -> None:
        if self.theme_path is None:
            self.save_theme_as()
            return
        spec = self._current_spec_or_error()
        if spec is None:
            return
        if self.theme_path.name.casefold() == CANONICAL_DEFAULT_WIDGET_THEME_FILENAME.casefold() and spec != self.default_spec:
            self._warning("Default Dark is protected", "The canonical Default Dark Widget mirror must exactly equal the compiled fallback. Use Save As instead.")
            return
        self._write_theme(spec, self.theme_path)

    def save_theme_as(self) -> None:
        spec = self._current_spec_or_error()
        if spec is None:
            return
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        initial = self.themes_dir / f"{safe_theme_filename(spec.name)}{WIDGET_THEME_FILE_EXTENSION}"
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Widget Theme As",
            str(initial),
            f"SRPSS Widget Theme (*{WIDGET_THEME_FILE_EXTENSION});;All Files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix.lower() != WIDGET_THEME_FILE_EXTENSION:
            path = path.with_suffix(WIDGET_THEME_FILE_EXTENSION)
        if path.name.casefold() == CANONICAL_DEFAULT_WIDGET_THEME_FILENAME.casefold():
            self._warning("Default Dark is protected", "Choose another filename for an authored Widget Theme.")
            return
        # Save As creates an intentionally unlinked fork. Duplicating link metadata
        # would make Settings<->Widget Keep Synced resolution ambiguous.
        fork = WidgetThemeSpec(
            theme_id=theme_id_for_save_as(path),
            name=spec.name,
            linked_settings_theme_id=None,
            colors=dict(spec.colors),
        )
        self._write_theme(fork, path)
        self.statusBar().showMessage("Saved unlinked Widget Theme fork; original Settings link was not duplicated.", 8000)

    def _current_spec_or_error(self) -> WidgetThemeSpec | None:
        self.draft.name = self.name_edit.text().strip()
        try:
            spec = self.draft.to_spec()
            encoded = widget_theme_to_json(spec)
            decoded = widget_theme_from_json(encoded)
            if decoded != spec:
                raise RuntimeError("Strict .srwtheme round-trip changed the WidgetThemeSpec")
            return spec
        except Exception as exc:
            self._error("Invalid Widget Theme draft", str(exc))
            return None

    def _write_theme(self, spec: WidgetThemeSpec, path: Path) -> None:
        try:
            save_widget_theme_file(spec, path)
            loaded = load_widget_theme_file(path)
            if loaded != spec:
                raise RuntimeError("Saved Widget Theme failed strict reload equality")
        except Exception as exc:
            self._error("Save Widget Theme failed", str(exc))
            return
        self._load_spec(spec, path)
        self._refresh_file_list()
        index = self.theme_combo.findText(path.name)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        self.statusBar().showMessage(f"Saved + strict-reloaded {path.name}", 8000)

    # ---- role browser ----------------------------------------------
    def _role_state(self, role: str) -> tuple[str, str]:
        current_present = role in self.draft.colors
        opened_present = role in self.opened_spec.colors
        default_present = role in self.default_spec.colors
        current = self.draft.colors.get(role)
        opened = self.opened_spec.colors.get(role)
        default = self.default_spec.colors.get(role)
        if role in WIDGET_THEME_CORE_COLOR_ROLES:
            if current == opened:
                return ("CORE", "Required core role; unchanged from opened theme.")
            if current == default:
                return ("DEFAULT", "Required core role currently equals compiled Default Dark.")
            return ("EDITED", "Required core role differs from opened theme.")
        if not current_present:
            resolution = self.draft.resolve_role(role)
            if resolution.kind == "inherited":
                return ("INHERITED", f"Sparse optional role inherits from {resolution.source_role}.")
            return ("LOCAL", f"Sparse optional role ultimately inherits through {resolution.source_role or 'family-local presentation'}.")
        if opened_present and current == opened:
            return ("EXPLICIT", "Optional role is explicitly authored and unchanged from opened theme.")
        if default_present and current == default:
            return ("DEFAULT", "Optional role explicitly equals compiled Default Dark.")
        return ("OVERRIDE", "Optional role is explicitly authored in this theme.")

    def _rebuild_tree(self, select_role: str | None = None) -> None:
        self.tree.clear()
        parents: dict[str, QTreeWidgetItem] = {}
        roles = all_widget_theme_roles()
        for group in dict.fromkeys(role_group(role) for role in roles):
            parent = QTreeWidgetItem([group, "", ""])
            f = parent.font(0)
            f.setBold(True)
            parent.setFont(0, f)
            parent.setData(0, Qt.ItemDataRole.UserRole, None)
            self.tree.addTopLevelItem(parent)
            parents[group] = parent
        selected_item: QTreeWidgetItem | None = None
        for role in roles:
            state, detail = self._role_state(role)
            resolution = self.draft.resolve_role(role)
            value = resolution.color
            summary = rgba_summary(value) if value is not None else "family-local inheritance"
            item = QTreeWidgetItem([friendly_role_label(role), state, summary])
            item.setData(0, Qt.ItemDataRole.UserRole, role)
            item.setToolTip(0, role)
            item.setToolTip(1, detail)
            parents[role_group(role)].addChild(item)
            if role == select_role:
                selected_item = item
        self.tree.expandAll()
        self._apply_tree_filter()
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)

    def _apply_tree_filter(self) -> None:
        needle = self.search_edit.text().strip().casefold()
        category = self.category_combo.currentText()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            group = group_item.text(0)
            group_allowed = category == "All" or category == group
            visible_children = 0
            for j in range(group_item.childCount()):
                item = group_item.child(j)
                role = str(item.data(0, Qt.ItemDataRole.UserRole) or "")
                haystack = f"{role} {item.text(0)} {item.text(1)}".casefold()
                visible = group_allowed and (not needle or needle in haystack)
                item.setHidden(not visible)
                visible_children += int(visible)
            group_item.setHidden(visible_children == 0)

    def _selection_changed(self) -> None:
        item = self.tree.currentItem()
        role = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if not isinstance(role, str) or not role:
            self.selected_role = None
            self._set_editor_enabled(False)
            return
        self.selected_role = role
        self._set_editor_enabled(True)
        self._refresh_editor()

    def _set_editor_enabled(self, enabled: bool) -> None:
        for widget in (
            self.preview, self.swatch, self.r_spin, self.g_spin, self.b_spin, self.a_spin,
            self.hex_edit, self.hex_apply_btn, self.copy_btn, self.bulk_btn,
            self.remove_override_btn, self.reset_opened_btn, self.reset_default_btn,
        ):
            widget.setEnabled(enabled)

    def _refresh_editor(self) -> None:
        role = self.selected_role
        if role is None:
            return
        resolution = self.draft.resolve_role(role)
        color = resolution.color or default_seed_color(role, self.draft)
        state, detail = self._role_state(role)
        self.role_title.setText(friendly_role_label(role).upper())
        self.role_token.setText(role)
        if resolution.color is None:
            source_text = f"No theme-owned colour yet; runtime reaches {resolution.source_role or 'family-local presentation'}"
        elif resolution.kind == "explicit":
            source_text = "Explicitly authored in this theme"
        else:
            source_text = f"Inherited from {resolution.source_role}"
        self.state_banner.setText(f"{state} · {source_text}\n{detail}")
        self.preview.set_rgba(color)
        self.swatch.set_rgba(color)
        self.swatch.setText(rgba_summary(color))
        self._spin_guard = True
        try:
            for spin, value in zip((self.r_spin, self.g_spin, self.b_spin, self.a_spin), color.as_tuple()):
                spin.setValue(value)
            self.hex_edit.setText(f"#{color.r:02X}{color.g:02X}{color.b:02X}{color.a:02X}")
        finally:
            self._spin_guard = False
        self.remove_override_btn.setEnabled(
            role not in WIDGET_THEME_CORE_COLOR_ROLES and role in self.draft.colors
        )
        parent = WIDGET_VISUAL_ROLE_PARENTS.get(role)
        chain = [role]
        seen = {role}
        while parent and parent not in seen:
            chain.append(parent)
            seen.add(parent)
            if parent.startswith("local."):
                break
            parent = WIDGET_VISUAL_ROLE_PARENTS.get(parent)
        chain_text = " → ".join(chain)
        core_note = "Required core role; it cannot be removed." if role in WIDGET_THEME_CORE_COLOR_ROLES else "Optional role; Remove Override restores this inheritance chain."
        self.inheritance_label.setText(f"{core_note}\n\n{chain_text}")

    # ---- edits ------------------------------------------------------
    def _choose_qcolor(self, current: Rgba, title: str) -> Rgba | None:
        initial = QColor(*current.as_tuple())
        chosen = QColorDialog.getColor(
            initial,
            self,
            title,
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if not chosen.isValid():
            return None
        return Rgba(chosen.red(), chosen.green(), chosen.blue(), chosen.alpha())

    def _choose_selected_color(self) -> None:
        role = self.selected_role
        if role is None:
            return
        current = self.draft.resolve_role(role).color or default_seed_color(role, self.draft)
        chosen = self._choose_qcolor(current, f"{friendly_role_label(role)}")
        if chosen is not None and chosen != current:
            self._set_selected_color(chosen)

    def _set_selected_color(self, color: Rgba) -> None:
        role = self.selected_role
        if role is None:
            return
        self.draft.set_role(role, color)
        self._after_edit(role)

    def _spins_changed(self) -> None:
        if self._spin_guard or self.selected_role is None:
            return
        self._set_selected_color(Rgba(self.r_spin.value(), self.g_spin.value(), self.b_spin.value(), self.a_spin.value()))

    def _parse_hex(self, text: str) -> Rgba:
        value = text.strip().lstrip("#")
        if len(value) == 6:
            value += "FF"
        if len(value) != 8 or any(ch not in "0123456789abcdefABCDEF" for ch in value):
            raise ValueError("Use #RRGGBB or #RRGGBBAA")
        return Rgba(*(int(value[index:index + 2], 16) for index in range(0, 8, 2)))

    def _apply_hex(self) -> None:
        try:
            color = self._parse_hex(self.hex_edit.text())
        except ValueError as exc:
            self._warning("Invalid colour", str(exc))
            return
        self._set_selected_color(color)

    def _copy_rgba(self) -> None:
        role = self.selected_role
        if role is None:
            return
        color = self.draft.resolve_role(role).color or default_seed_color(role, self.draft)
        QApplication.clipboard().setText(f"{color.r},{color.g},{color.b},{color.a}")
        self.statusBar().showMessage("RGBA copied to clipboard", 3000)

    def _bulk_replace_selected(self) -> None:
        role = self.selected_role
        if role is None:
            return
        current = self.draft.resolve_role(role).color
        if current is None:
            self._warning("Nothing explicit to bulk-replace", "This role currently resolves only through family-local inheritance. Add an override first.")
            return
        matches = tuple(r for r, c in self.draft.colors.items() if c == current)
        chosen = self._choose_qcolor(current, f"Replace {len(matches)} exact Widget Theme matches")
        if chosen is None or chosen == current:
            return
        replaced = replace_exact_color_matches(self.draft.colors, current, chosen)
        self._rebuild_tree(role)
        self._refresh_most_used()
        self._update_dirty_status()
        self.statusBar().showMessage(f"Changed {len(replaced)} exact semantic colour roles.", 6000)

    def _remove_override(self) -> None:
        role = self.selected_role
        if role is None:
            return
        try:
            changed = self.draft.remove_optional_override(role)
        except ValueError as exc:
            self._warning("Core role", str(exc))
            return
        if changed:
            self._after_edit(role)

    def _reset_role_opened(self) -> None:
        role = self.selected_role
        if role is None:
            return
        if role in self.opened_spec.colors:
            self.draft.set_role(role, self.opened_spec.colors[role])
        elif role not in WIDGET_THEME_CORE_COLOR_ROLES:
            self.draft.colors.pop(role, None)
        self._after_edit(role)

    def _reset_role_default(self) -> None:
        role = self.selected_role
        if role is None:
            return
        if role in self.default_spec.colors:
            self.draft.set_role(role, self.default_spec.colors[role])
        elif role not in WIDGET_THEME_CORE_COLOR_ROLES:
            self.draft.colors.pop(role, None)
        self._after_edit(role)

    def _reset_all_opened(self) -> None:
        name = self.draft.name
        self.draft = WidgetThemeDraft.from_spec(self.opened_spec)
        self.draft.name = name
        self._rebuild_tree(self.selected_role)
        self._refresh_most_used()
        self._update_dirty_status()

    def _reset_all_default(self) -> None:
        name = self.draft.name
        theme_id = self.draft.theme_id
        link = self.draft.linked_settings_theme_id
        self.draft = WidgetThemeDraft.from_spec(self.default_spec)
        self.draft.name = name
        self.draft.theme_id = theme_id
        self.draft.linked_settings_theme_id = link
        self._rebuild_tree(self.selected_role)
        self._refresh_most_used()
        self._update_dirty_status()

    def _after_edit(self, role: str) -> None:
        self._rebuild_tree(role)
        self._refresh_most_used()
        self._update_dirty_status()

    def _refresh_most_used(self) -> None:
        entries = most_used_colors(self.draft.colors, limit=6)
        self._most_used_entries = list(entries)
        for index, (button, count) in enumerate(zip(self.most_used_buttons, self.most_used_counts)):
            if index >= len(entries):
                button.hide()
                count.hide()
                continue
            color, roles = entries[index]
            button.show()
            count.show()
            button.set_rgba(color)
            button.setText(rgba_summary(color))
            count.setText(f"{len(roles)} role{'s' if len(roles) != 1 else ''}")
            button.setToolTip("\n".join(roles))

    def _replace_most_used(self, index: int) -> None:
        if index >= len(self._most_used_entries):
            return
        current, roles = self._most_used_entries[index]
        chosen = self._choose_qcolor(current, f"Replace {len(roles)} exact Widget Theme matches")
        if chosen is None or chosen == current:
            return
        replaced = replace_exact_color_matches(self.draft.colors, current, chosen)
        self._rebuild_tree(self.selected_role)
        self._refresh_most_used()
        self._update_dirty_status()
        self.statusBar().showMessage(f"Changed {len(replaced)} exact semantic colour roles.", 6000)

    # ---- state / safety --------------------------------------------
    def _name_changed(self, text: str) -> None:
        self.draft.name = text
        self._update_dirty_status()

    def _is_dirty(self) -> bool:
        try:
            return self.draft.to_spec() != self.opened_spec
        except Exception:
            return True

    def _update_dirty_status(self) -> None:
        dirty = self._is_dirty()
        path_name = self.theme_path.name if self.theme_path is not None else "Compiled / unsaved"
        self.setWindowTitle(f"{APP_TITLE} — {path_name}{' *' if dirty else ''}")
        self.id_label.setText(self.draft.theme_id)
        self.link_label.setText(self.draft.linked_settings_theme_id or "UNLINKED")

    def _confirm_discard_if_dirty(self) -> bool:
        if not self._is_dirty():
            return True
        answer = QMessageBox.question(
            self,
            "Discard Widget Theme changes?",
            "The current Widget Theme has unsaved changes. Discard them?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Discard

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._confirm_discard_if_dirty():
            event.accept()
        else:
            event.ignore()

    def _warning(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)

    def _error(self, title: str, text: str) -> None:
        QMessageBox.critical(self, title, text)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Edit SRPSS schema-v3 Widget Themes")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("theme", nargs="?", type=Path, help="Optional .srwtheme to open")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(args.repo).expanduser().resolve()
    if not (repo_root / "ui" / "widget_theme_spec.py").is_file():
        print(f"Widget Theme Foundry could not locate SRPSS under {repo_root}", file=sys.stderr)
        return 2

    # Qt 6 is DPI aware by default. PassThrough avoids surprise fractional scale
    # rounding when editing on the same high-DPI desktops used to inspect widgets.
    try:
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass
    app = QApplication(sys.argv)
    icon_path = repo_root / "images" / "foundries" / "SRPSSTheme.ico"
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    initial = Path(args.theme).expanduser().resolve() if args.theme is not None else None
    window = WidgetThemeFoundryWindow(repo_root, initial)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
