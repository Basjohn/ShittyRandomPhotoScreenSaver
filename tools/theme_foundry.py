#!/usr/bin/env python3
"""SRPSS Theme Foundry — schema-v5 semantic Settings theme editor.

The Foundry edits the exact :class:`SettingsThemeSpec` consumed by Settings. It
never scans Python/QSS literals, never rewrites runtime source files and never
maintains a private compatibility schema.

Authored native modes:
* Off — no native backdrop;
* Acrylic — AccentPolicy state 4 at runtime; backdrop.tint is meaningful;
* Glass — AccentPolicy state 3 at runtime; native tint is ignored and semantic
  Qt RGBA surfaces own visible Glass colour/opacity.

Only complete, strictly validated ``.srtheme`` snapshots are written through
``ui.settings_theme_io``. ``Default Dark.srtheme`` remains the protected mirror
of compiled ``DEFAULT_DARK_SETTINGS_THEME``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


def _early_repo_root() -> Path:
    explicit: str | None = None
    argv = sys.argv[1:]
    for index, arg in enumerate(argv):
        if arg == "--repo" and index + 1 < len(argv):
            explicit = argv[index + 1]
            break
        if arg.startswith("--repo="):
            explicit = arg.split("=", 1)[1]
            break
    if explicit:
        return Path(explicit).expanduser().resolve()
    script = Path(__file__).resolve()
    if len(script.parents) >= 2 and (script.parents[1] / "ui").is_dir():
        return script.parents[1]
    cwd = Path.cwd().resolve()
    if (cwd / "ui").is_dir():
        return cwd
    return script.parents[1]


_BOOTSTRAP_REPO_ROOT = _early_repo_root()
if str(_BOOTSTRAP_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_REPO_ROOT))

from PySide6.QtCore import QRect, Qt, Signal  # noqa: E402
from PySide6.QtGui import QColor, QFont, QIcon, QLinearGradient, QPainter, QPen  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from theme_foundry_model import (  # noqa: E402
    ACRYLIC_TINT_PRESETS,
    BACKDROP_MODE_DESCRIPTIONS,
    BACKDROP_MODE_LABELS,
    ThemeDraft,
    alpha_over,
    color_category,
    friendly_token_label,
    gradient_summary,
    matching_acrylic_preset,
    nearest_composite_relation,
    relations_for,
    rgba_summary,
    semantic_description,
    shadow_summary,
    solve_layer_for_target,
)
from ui.settings_theme_io import (  # noqa: E402
    SETTINGS_THEME_FILE_EXTENSION,
    SettingsThemeFileError,
    load_settings_theme_file,
    save_settings_theme_file,
    settings_theme_from_json,
    settings_theme_to_json,
)
from ui.settings_theme_spec import (  # noqa: E402
    DEFAULT_DARK_SETTINGS_THEME,
    SETTINGS_THEME_SCHEMA_VERSION,
    GradientStop,
    GradientStyle,
    Rgba,
    SettingsThemeSpec,
    ShadowStyle,
)

APP_TITLE = "SRPSS Theme Foundry"
PREFERENCES_VERSION = 3
CANONICAL_DEFAULT_FILENAME = "Default Dark.srtheme"


def _foundry_data_dir() -> Path:
    local = os.environ.get("LOCALAPPDATA")
    base = Path(local) if local else Path.home() / "AppData" / "Local"
    return base / "SRPSS" / "ThemeFoundry"


def _preferences_path() -> Path:
    return _foundry_data_dir() / "preferences.json"


def _load_preferences() -> dict[str, Any]:
    try:
        payload = json.loads(_preferences_path().read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_preferences(payload: dict[str, Any]) -> None:
    path = _preferences_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(f".{path.name}.tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(temp, path)
    except OSError:
        pass


class ColorPreview(QWidget):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, *, clickable: bool = False) -> None:
        super().__init__(parent)
        self._color = Rgba(255, 255, 255, 255)
        self._clickable = clickable
        self.setMinimumWidth(150)
        self.setFixedHeight(78)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.set_clickable(clickable)

    def set_rgba(self, value: Rgba) -> None:
        self._color = value
        self.update()

    def set_clickable(self, clickable: bool) -> None:
        self._clickable = clickable
        self.setCursor(
            Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor
        )

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
        c1 = QColor(55, 55, 55)
        c2 = QColor(90, 90, 90)
        for y in range(0, self.height(), cell):
            for x in range(0, self.width(), cell):
                painter.fillRect(
                    QRect(x, y, cell, cell),
                    c1 if ((x // cell) + (y // cell)) % 2 == 0 else c2,
                )
        painter.fillRect(self.rect(), QColor(*self._color.as_tuple()))
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))


class GradientPreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gradient = GradientStyle(
            stops=(
                GradientStop(0.0, Rgba(0, 0, 0, 255)),
                GradientStop(1.0, Rgba(255, 255, 255, 255)),
            )
        )
        self.setMinimumWidth(220)
        self.setFixedHeight(64)

    def set_gradient(self, value: GradientStyle) -> None:
        self._gradient = value
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, max(1, self.width()), 0)
        for stop in self._gradient.stops:
            gradient.setColorAt(stop.position, QColor(*stop.color.as_tuple()))
        painter.fillRect(self.rect(), gradient)
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))


class ShadowPreview(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(220)
        self.setFixedHeight(100)
        self._sample = QLabel("SHADOW", self)
        self._sample.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sample.setStyleSheet(
            "background:#e9ece8;color:#172023;border:1px solid #ffffff;"
            "border-radius:7px;font-weight:700;padding:8px 18px;"
        )
        self._sample.setFixedSize(132, 48)
        self._effect = QGraphicsDropShadowEffect(self._sample)
        self._sample.setGraphicsEffect(self._effect)

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._sample.move(
            (self.width() - self._sample.width()) // 2,
            (self.height() - self._sample.height()) // 2,
        )

    def set_shadow(self, value: ShadowStyle) -> None:
        self._effect.setBlurRadius(value.blur_radius)
        self._effect.setOffset(value.offset_x, value.offset_y)
        self._effect.setColor(QColor(*value.color.as_tuple()))


class SwatchButton(QPushButton):
    colorRequested = Signal()

    def __init__(self, text: str = "Choose Colour…", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._value = Rgba(255, 255, 255, 255)
        self.clicked.connect(self.colorRequested.emit)
        self.setMinimumHeight(36)
        self._refresh()

    def set_rgba(self, value: Rgba) -> None:
        self._value = value
        self._refresh()

    def _refresh(self) -> None:
        c = self._value
        luminance = 0.299 * c.r + 0.587 * c.g + 0.114 * c.b
        fg = "#000000" if luminance > 150 and c.a > 90 else "#ffffff"
        self.setStyleSheet(
            "QPushButton {"
            f"background-color: rgba({c.r},{c.g},{c.b},{c.a});"
            f"color:{fg};border:1px solid #aaaaaa;border-radius:6px;padding:6px 12px;"
            "}"
        )


class ThemeFoundryWindow(QMainWindow):
    COL_FAV = 0
    COL_TOKEN = 1
    COL_KIND = 2
    COL_STATE = 3
    COL_WORKING = 4
    COL_OPENED = 5
    COL_DEFAULT = 6

    def __init__(self, repo_root: Path, initial_theme: Path | None = None) -> None:
        super().__init__()
        self.repo_root = repo_root.resolve()
        self.default_spec = DEFAULT_DARK_SETTINGS_THEME
        self.opened_spec = self.default_spec
        self.draft = ThemeDraft.from_spec(self.default_spec)
        self.theme_path: Path | None = None
        self.selected_entry: tuple[str, str] | None = None
        self.tree_items: dict[str, QTreeWidgetItem] = {}
        self._updating = False
        self._gradient_stop_index = 0
        self._last_acrylic_tint = (
            self.draft.backdrop_tint
            if self.draft.backdrop_tint.a > 0
            else ACRYLIC_TINT_PRESETS[0].tint
        )

        prefs = _load_preferences()
        raw_favorites = prefs.get("favorites", [])
        self.favorites = {
            str(item) for item in raw_favorites if isinstance(item, str) and item.strip()
        }
        self._prefs = prefs

        self.setWindowTitle(APP_TITLE)
        icon_path = self.repo_root / "images" / "foundries" / "SRPSSTheme.ico"
        if not icon_path.is_file():
            icon_path = self.repo_root / "SRPSS.ico"
        if icon_path.is_file():
            icon = QIcon(str(icon_path))
            self.setWindowIcon(icon)
            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(icon)

        self.resize(1480, 930)
        self.setMinimumSize(1120, 720)
        self._build_ui()
        self._apply_internal_style()
        self._refresh_backdrop_ui()
        self._rebuild_tree()
        self._check_default_mirror()

        if initial_theme is not None:
            self._open_theme_path(initial_theme)
        else:
            self._set_status(
                "Editing compiled Default Dark. Use Save As to create a selectable custom .srtheme."
            )
        self._update_dirty_status()

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("themeFoundryRoot")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 14, 18, 14)
        outer.setSpacing(10)

        title = QLabel("THEME FOUNDRY")
        title.setObjectName("themeFoundryTitle")
        font = QFont(title.font())
        font.setPointSize(max(16, font.pointSize() + 6))
        font.setBold(True)
        title.setFont(font)
        outer.addWidget(title)

        subtitle = QLabel(
            f"Semantic SettingsThemeSpec editor · schema-v{SETTINGS_THEME_SCHEMA_VERSION} .srtheme files · "
            "Off / Acrylic / Glass · no source scanning or Python/QSS rewriting"
        )
        subtitle.setObjectName("themeFoundrySubtitle")
        outer.addWidget(subtitle)

        toolbar = QHBoxLayout()
        self.new_btn = QPushButton("New From Default")
        self.open_btn = QPushButton("Open Theme…")
        self.save_btn = QPushButton("Save")
        self.save_as_btn = QPushButton("Save As…")
        self.validate_btn = QPushButton("Validate Draft")
        self.launch_btn = QPushButton("Launch Settings (--s)")
        self.save_as_btn.setObjectName("themeFoundryPrimary")
        for button in (self.new_btn, self.open_btn, self.save_btn, self.save_as_btn, self.validate_btn):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.launch_btn)
        outer.addLayout(toolbar)

        file_row = QHBoxLayout()
        file_row.addWidget(QLabel("Theme name"))
        self.name_edit = QLineEdit(self.draft.name)
        self.name_edit.setMinimumWidth(260)
        file_row.addWidget(self.name_edit)
        file_row.addSpacing(12)
        self.file_label = QLabel("Compiled Default Dark (no file opened)")
        self.file_label.setObjectName("muted")
        self.file_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        file_row.addWidget(self.file_label, 1)
        outer.addLayout(file_row)

        scope = QLabel(
            "Theme files are complete semantic snapshots. Default Dark remains compiled runtime fallback. "
            "Glass is native untinted state-3 blur plus semantic Qt surface composition; Acrylic uses native tint."
        )
        scope.setWordWrap(True)
        scope.setObjectName("scopeBanner")
        outer.addWidget(scope)
        outer.addWidget(self._build_backdrop_box())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_tree_pane())
        splitter.addWidget(self._build_editor_pane())
        splitter.setSizes([820, 620])
        outer.addWidget(splitter, 1)

        status = QStatusBar(self)
        self.setStatusBar(status)
        self.status_label = QLabel("")
        status.addWidget(self.status_label, 1)

        self.new_btn.clicked.connect(self.new_from_default)
        self.open_btn.clicked.connect(self.open_theme)
        self.save_btn.clicked.connect(self.save_theme)
        self.save_as_btn.clicked.connect(self.save_theme_as)
        self.validate_btn.clicked.connect(self.validate_draft)
        self.launch_btn.clicked.connect(self.launch_settings)
        self.name_edit.textEdited.connect(self._theme_name_changed)

    def _build_backdrop_box(self) -> QGroupBox:
        box = QGroupBox("NATIVE BACKDROP")
        box.setObjectName("backdropBox")
        layout = QGridLayout(box)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(7)

        layout.addWidget(QLabel("Material"), 0, 0)
        self.backdrop_mode = QComboBox()
        for mode in ("off", "acrylic", "glass"):
            self.backdrop_mode.addItem(BACKDROP_MODE_LABELS[mode], mode)
        self.backdrop_mode.setMinimumWidth(220)
        layout.addWidget(self.backdrop_mode, 0, 1)

        self.backdrop_note = QLabel("")
        self.backdrop_note.setWordWrap(True)
        self.backdrop_note.setObjectName("muted")
        layout.addWidget(self.backdrop_note, 0, 2, 1, 3)

        layout.addWidget(QLabel("Acrylic tint preset"), 1, 0)
        self.acrylic_preset = QComboBox()
        for preset in ACRYLIC_TINT_PRESETS:
            self.acrylic_preset.addItem(preset.name, preset.name)
        self.acrylic_preset.addItem("Custom", "Custom")
        self.acrylic_preset.setMinimumWidth(240)
        layout.addWidget(self.acrylic_preset, 1, 1)

        self.backdrop_swatch = SwatchButton("Acrylic Tint…")
        layout.addWidget(self.backdrop_swatch, 1, 2)
        layout.addWidget(QLabel("Native tint alpha"), 1, 3)
        self.backdrop_alpha = QSpinBox()
        self.backdrop_alpha.setRange(1, 255)
        self.backdrop_alpha.setMinimumWidth(88)
        layout.addWidget(self.backdrop_alpha, 1, 4)

        self.backdrop_value_label = QLabel("")
        self.backdrop_value_label.setObjectName("muted")
        layout.addWidget(self.backdrop_value_label, 2, 1, 1, 4)

        self.backdrop_mode.currentIndexChanged.connect(self._backdrop_mode_changed)
        self.acrylic_preset.currentIndexChanged.connect(self._acrylic_preset_changed)
        self.backdrop_swatch.colorRequested.connect(self._choose_backdrop_tint)
        self.backdrop_alpha.valueChanged.connect(self._backdrop_alpha_changed)
        return box

    def _build_tree_pane(self) -> QWidget:
        pane = QWidget()
        pane.setObjectName("themeFoundryPane")
        layout = QVBoxLayout(pane)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        search_row = QHBoxLayout()
        search_row.addWidget(QLabel("Filter"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("titlebar, selected, popup, shadow, gradient…")
        search_row.addWidget(self.search, 1)
        self.category_filter = QComboBox()
        self.category_filter.addItem("All categories")
        search_row.addWidget(self.category_filter)
        self.favorites_only = QCheckBox("★ Favorites")
        search_row.addWidget(self.favorites_only)
        layout.addLayout(search_row)

        self.tree = QTreeWidget()
        self.tree.setObjectName("themeFoundryTree")
        self.tree.setHeaderLabels(
            ["★", "Semantic role", "Kind", "State", "Working", "Opened", "Default Dark"]
        )
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setUniformRowHeights(True)
        header = self.tree.header()
        header.setSectionResizeMode(self.COL_FAV, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TOKEN, QHeaderView.ResizeMode.Stretch)
        for col in (self.COL_KIND, self.COL_STATE, self.COL_WORKING, self.COL_OPENED, self.COL_DEFAULT):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 1)

        self.search.textChanged.connect(self._filter_tree)
        self.category_filter.currentTextChanged.connect(self._filter_tree)
        self.favorites_only.toggled.connect(self._filter_tree)
        self.tree.currentItemChanged.connect(self._tree_selection_changed)
        self.tree.itemClicked.connect(self._tree_item_clicked)
        return pane

    def _build_editor_pane(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        editor = QWidget()
        editor.setObjectName("themeFoundryEditor")
        scroll.setWidget(editor)
        layout = QVBoxLayout(editor)
        layout.setContentsMargins(14, 8, 10, 8)
        layout.setSpacing(10)

        row = QHBoxLayout()
        self.token_title = QLabel("Select a semantic role")
        self.token_title.setObjectName("tokenTitle")
        font = QFont(self.token_title.font())
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        self.token_title.setFont(font)
        row.addWidget(self.token_title, 1)
        self.favorite_btn = QPushButton("☆ Favorite")
        self.favorite_btn.setObjectName("favoriteButton")
        self.favorite_btn.clicked.connect(self._toggle_selected_favorite)
        row.addWidget(self.favorite_btn)
        layout.addLayout(row)

        self.token_official = QLabel("")
        self.token_official.setObjectName("muted")
        self.token_official.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.token_official)
        self.token_description = QLabel("")
        self.token_description.setObjectName("descriptionBox")
        self.token_description.setWordWrap(True)
        layout.addWidget(self.token_description)
        self.state_banner = QLabel("")
        self.state_banner.setObjectName("stateBanner")
        self.state_banner.setWordWrap(True)
        layout.addWidget(self.state_banner)

        self.editor_stack = QStackedWidget()
        self.blank_editor = QLabel("Select a colour, shadow or gradient semantic role from the tree.")
        self.blank_editor.setWordWrap(True)
        self.blank_editor.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.color_editor = self._build_color_editor()
        self.shadow_editor = self._build_shadow_editor()
        self.gradient_editor = self._build_gradient_editor()
        for page in (self.blank_editor, self.color_editor, self.shadow_editor, self.gradient_editor):
            self.editor_stack.addWidget(page)
        layout.addWidget(self.editor_stack)

        heading = QLabel("KNOWN VISUAL / STYLE LAYERS")
        heading.setObjectName("sectionHeading")
        layout.addWidget(heading)
        help_label = QLabel(
            "High-confidence semantic relationships only. Double-click a related role to jump to it. "
            "For simple alpha-over mappings the predicted colour preview can solve backwards."
        )
        help_label.setWordWrap(True)
        help_label.setObjectName("muted")
        layout.addWidget(help_label)
        self.layers_tree = QTreeWidget()
        self.layers_tree.setObjectName("layersTree")
        self.layers_tree.setHeaderLabels(["Relationship", "Other role", "Why it matters"])
        self.layers_tree.setRootIsDecorated(False)
        self.layers_tree.setAlternatingRowColors(True)
        self.layers_tree.setMinimumHeight(150)
        h = self.layers_tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.layers_tree.itemDoubleClicked.connect(self._layer_item_activated)
        layout.addWidget(self.layers_tree)

        row = QHBoxLayout()
        self.reset_opened_btn = QPushButton("Reset Selected to Opened")
        self.reset_default_btn = QPushButton("Reset Selected to Default Dark")
        row.addWidget(self.reset_opened_btn)
        row.addWidget(self.reset_default_btn)
        layout.addLayout(row)
        row = QHBoxLayout()
        self.reset_all_opened_btn = QPushButton("Reset ALL to Opened")
        self.reset_all_default_btn = QPushButton("Reset ALL to Default Dark")
        row.addWidget(self.reset_all_opened_btn)
        row.addWidget(self.reset_all_default_btn)
        layout.addLayout(row)
        self.reset_opened_btn.clicked.connect(self._reset_selected_opened)
        self.reset_default_btn.clicked.connect(self._reset_selected_default)
        self.reset_all_opened_btn.clicked.connect(self._reset_all_opened)
        self.reset_all_default_btn.clicked.connect(self._reset_all_default)
        layout.addStretch(1)
        return scroll

    def _build_color_editor(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        preview_grid = QGridLayout()
        preview_grid.addWidget(self._heading("Isolated role"), 0, 0)
        predicted = self._heading("Predicted visible composite")
        predicted.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        preview_grid.addWidget(predicted, 0, 1)
        self.color_preview = ColorPreview()
        self.composite_preview = ColorPreview(clickable=True)
        self.composite_preview.clicked.connect(self._choose_composite_target)
        preview_grid.addWidget(self.color_preview, 1, 0)
        preview_grid.addWidget(self.composite_preview, 1, 1)
        self.composite_note = QLabel("No mapped compositing neighbour")
        self.composite_note.setObjectName("muted")
        self.composite_note.setWordWrap(True)
        self.composite_note.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        preview_grid.addWidget(self.composite_note, 2, 1)
        preview_grid.setColumnStretch(0, 1)
        preview_grid.setColumnStretch(1, 1)
        layout.addLayout(preview_grid)
        self.color_swatch = SwatchButton()
        self.color_swatch.colorRequested.connect(self._choose_selected_color)
        layout.addWidget(self.color_swatch)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.r_spin = self._channel_spin()
        self.g_spin = self._channel_spin()
        self.b_spin = self._channel_spin()
        form.addRow("Red", self.r_spin)
        form.addRow("Green", self.g_spin)
        form.addRow("Blue", self.b_spin)
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        self.a_slider = QSlider(Qt.Orientation.Horizontal)
        self.a_slider.setRange(0, 255)
        self.a_spin = self._channel_spin()
        self.alpha_pct = QLabel("100.0%")
        self.alpha_pct.setMinimumWidth(60)
        row.addWidget(self.a_slider, 1)
        row.addWidget(self.a_spin)
        row.addWidget(self.alpha_pct)
        form.addRow("Opacity", wrap)
        layout.addLayout(form)
        for spin in (self.r_spin, self.g_spin, self.b_spin):
            spin.valueChanged.connect(self._color_channels_changed)
        self.a_spin.valueChanged.connect(self._color_alpha_spin_changed)
        self.a_slider.valueChanged.connect(self._color_alpha_slider_changed)
        return page

    def _build_shadow_editor(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.shadow_preview = ShadowPreview()
        layout.addWidget(self.shadow_preview)
        self.shadow_swatch = SwatchButton("Shadow Colour…")
        self.shadow_swatch.colorRequested.connect(self._choose_shadow_color)
        layout.addWidget(self.shadow_swatch)
        form = QFormLayout()
        self.shadow_blur = self._double_spin(0.0, 100.0, 0.5, 1)
        self.shadow_x = self._double_spin(-50.0, 50.0, 0.5, 1)
        self.shadow_y = self._double_spin(-50.0, 50.0, 0.5, 1)
        self.shadow_disabled = self._double_spin(0.0, 1.0, 0.05, 2)
        form.addRow("Blur radius", self.shadow_blur)
        form.addRow("Offset X", self.shadow_x)
        form.addRow("Offset Y", self.shadow_y)
        form.addRow("Disabled alpha scale", self.shadow_disabled)
        layout.addLayout(form)
        for spin in (self.shadow_blur, self.shadow_x, self.shadow_y, self.shadow_disabled):
            spin.valueChanged.connect(self._shadow_numbers_changed)
        return page

    def _build_gradient_editor(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self.gradient_preview = GradientPreview()
        layout.addWidget(self.gradient_preview)
        row = QHBoxLayout()
        row.addWidget(QLabel("Stop"))
        self.gradient_stop_combo = QComboBox()
        self.gradient_stop_combo.currentIndexChanged.connect(self._gradient_stop_selected)
        row.addWidget(self.gradient_stop_combo, 1)
        self.gradient_add_btn = QPushButton("Add Stop")
        self.gradient_remove_btn = QPushButton("Remove Stop")
        self.gradient_add_btn.clicked.connect(self._gradient_add_stop)
        self.gradient_remove_btn.clicked.connect(self._gradient_remove_stop)
        row.addWidget(self.gradient_add_btn)
        row.addWidget(self.gradient_remove_btn)
        layout.addLayout(row)
        self.gradient_swatch = SwatchButton("Stop Colour…")
        self.gradient_swatch.colorRequested.connect(self._choose_gradient_stop_color)
        layout.addWidget(self.gradient_swatch)
        form = QFormLayout()
        self.gradient_position = self._double_spin(0.0, 1.0, 0.01, 3)
        self.gradient_position.valueChanged.connect(self._gradient_position_changed)
        form.addRow("Stop position", self.gradient_position)
        layout.addLayout(form)
        return page

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("previewLabel")
        return label

    def _channel_spin(self) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(0, 255)
        spin.setMinimumWidth(88)
        return spin

    def _double_spin(self, low: float, high: float, step: float, decimals: int) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(low, high)
        spin.setSingleStep(step)
        spin.setDecimals(decimals)
        spin.setMinimumWidth(100)
        return spin

    def _apply_internal_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #0d181e; color: #f4f0e6; }
            QWidget { color: #f4f0e6; font-family: 'Jost', 'Segoe UI', sans-serif; }
            QWidget#themeFoundryRoot { background: #111a1e; }
            QWidget#themeFoundryPane, QWidget#themeFoundryEditor, QGroupBox#backdropBox {
                background: rgba(10,15,17,220); border: 1px solid rgba(225,193,127,100); border-radius: 10px;
            }
            QGroupBox#backdropBox { margin-top: 11px; padding: 9px; font-weight: 700; color: #f4c66d; }
            QGroupBox#backdropBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
            QLabel#themeFoundryTitle { color: #f4c66d; letter-spacing: 2px; }
            QLabel#themeFoundrySubtitle { color: #c8d4d1; font-size: 12px; padding-bottom: 3px; }
            QLabel#scopeBanner, QLabel#descriptionBox, QLabel#stateBanner {
                background: rgba(16,25,27,210); border: 1px solid rgba(225,193,127,110);
                border-radius: 8px; padding: 8px; color: #dce5df;
            }
            QLabel#stateBanner { color: #f4c66d; }
            QLabel#muted { color: #9fb2ad; }
            QLabel#previewLabel, QLabel#sectionHeading { color: #f4c66d; font-weight: 700; }
            QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background: #1f2626; color: #f4f0e6; border: 1px solid #8f7950; border-radius: 7px; padding: 5px;
            }
            QTreeWidget#themeFoundryTree, QTreeWidget#layersTree {
                background-color: rgba(10,15,17,218); alternate-background-color: rgba(31,38,38,205);
                border: 1px solid rgba(225,193,127,150); border-radius: 10px; color: #edf1ed; outline: none;
            }
            QTreeWidget::item { min-height: 28px; padding: 2px 5px; }
            QTreeWidget::item:selected { background: rgba(60,108,103,210); }
            QHeaderView::section { background: #1f2f30; color: #f4c66d; border: none; padding: 7px; font-weight: 700; }
            QPushButton { background: #263b3a; color: #f4f0e6; border: 1px solid #8f7950;
                border-radius: 7px; padding: 7px 12px; font-weight: 600; }
            QPushButton:hover { background: #33504d; border-color: #f4c66d; }
            QPushButton:disabled { color: #6f7e7b; border-color: #4f554e; background: #1b2424; }
            QPushButton#themeFoundryPrimary { background: #d59b42; color: #101719; border-color: #f4c66d; }
            QSlider::groove:horizontal { height: 5px; background: #11191b; border: 1px solid #8f7950; }
            QSlider::handle:horizontal { width: 14px; margin: -5px 0; border-radius: 7px; background: #f4c66d; }
            QStatusBar { background: #0a0f11; color: #c8d4d1; }
            """
        )

    def _entry_id(self, kind: str, token: str) -> str:
        return f"{kind}:{token}"

    def _value_for_draft(self, kind: str, token: str) -> Any:
        return {"color": self.draft.colors, "shadow": self.draft.shadows, "gradient": self.draft.gradients}[kind][token]

    def _value_for_spec(self, spec: SettingsThemeSpec, kind: str, token: str) -> Any:
        return {"color": spec.colors, "shadow": spec.shadows, "gradient": spec.gradients}[kind][token]

    def _summary(self, kind: str, value: Any) -> str:
        if kind == "color":
            return rgba_summary(value)
        if kind == "shadow":
            return shadow_summary(value)
        if kind == "gradient":
            return gradient_summary(value)
        return str(value)

    def _state_for(self, kind: str, token: str) -> tuple[str, str]:
        working = self._value_for_draft(kind, token)
        opened = self._value_for_spec(self.opened_spec, kind, token)
        default = self._value_for_spec(self.default_spec, kind, token)
        if working == opened:
            if working == default:
                return "UNCHANGED", "Working value equals opened theme and compiled Default Dark."
            return "OPENED", "Working value equals the opened theme."
        if working == default:
            return "DEFAULT", "Working value differs from opened theme and equals compiled Default Dark."
        return "EDITED", "Working value differs from the opened theme."

    def _rebuild_tree(self, select_entry: tuple[str, str] | None = None) -> None:
        self.tree.clear()
        self.tree_items.clear()
        entries: list[tuple[str, str, str]] = []
        entries += [(color_category(token), "color", token) for token in self.draft.colors]
        entries += [("Shadows", "shadow", token) for token in self.draft.shadows]
        entries += [("Gradients", "gradient", token) for token in self.draft.gradients]
        categories = sorted({category for category, _kind, _token in entries})
        current_filter = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All categories")
        self.category_filter.addItems(categories)
        if current_filter in {"All categories", *categories}:
            self.category_filter.setCurrentText(current_filter)
        self.category_filter.blockSignals(False)
        parents: dict[str, QTreeWidgetItem] = {}
        for category in categories:
            parent = QTreeWidgetItem(["", category])
            f = parent.font(self.COL_TOKEN)
            f.setBold(True)
            parent.setFont(self.COL_TOKEN, f)
            self.tree.addTopLevelItem(parent)
            parents[category] = parent
        for category, kind, token in sorted(entries, key=lambda x: (x[0], friendly_token_label(x[2]).lower())):
            entry_id = self._entry_id(kind, token)
            state, detail = self._state_for(kind, token)
            working = self._value_for_draft(kind, token)
            opened = self._value_for_spec(self.opened_spec, kind, token)
            default = self._value_for_spec(self.default_spec, kind, token)
            item = QTreeWidgetItem([
                "★" if entry_id in self.favorites else "☆",
                friendly_token_label(token), kind.title(), state,
                self._summary(kind, working), self._summary(kind, opened), self._summary(kind, default),
            ])
            item.setData(self.COL_FAV, Qt.ItemDataRole.UserRole, (kind, token))
            item.setToolTip(self.COL_TOKEN, token)
            item.setToolTip(self.COL_STATE, detail)
            parents[category].addChild(item)
            self.tree_items[entry_id] = item
        self.tree.expandAll()
        target = select_entry or self.selected_entry
        if target:
            item = self.tree_items.get(self._entry_id(*target))
            if item is not None:
                self.tree.setCurrentItem(item)
        self._filter_tree()

    def _filter_tree(self, *_args) -> None:
        text = self.search.text().strip().lower()
        category = self.category_filter.currentText()
        favorites_only = self.favorites_only.isChecked()
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            category_name = parent.text(self.COL_TOKEN)
            visible_children = 0
            for j in range(parent.childCount()):
                item = parent.child(j)
                data = item.data(self.COL_FAV, Qt.ItemDataRole.UserRole)
                if not data:
                    continue
                kind, token = str(data[0]), str(data[1])
                entry_id = self._entry_id(kind, token)
                haystack = f"{token} {friendly_token_label(token)} {kind} {category_name}".lower()
                visible = (
                    (category == "All categories" or category == category_name)
                    and (not favorites_only or entry_id in self.favorites)
                    and (not text or text in haystack)
                )
                item.setHidden(not visible)
                visible_children += int(visible)
            parent.setHidden(visible_children == 0)

    def _tree_selection_changed(self, current: QTreeWidgetItem | None, previous: QTreeWidgetItem | None) -> None:
        del previous
        if current is None:
            return
        data = current.data(self.COL_FAV, Qt.ItemDataRole.UserRole)
        if data:
            self.selected_entry = (str(data[0]), str(data[1]))
            self._refresh_editor()

    def _tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        if column != self.COL_FAV:
            return
        data = item.data(self.COL_FAV, Qt.ItemDataRole.UserRole)
        if data:
            self._toggle_favorite(self._entry_id(str(data[0]), str(data[1])))

    def _toggle_favorite(self, entry_id: str) -> None:
        if entry_id in self.favorites:
            self.favorites.remove(entry_id)
        else:
            self.favorites.add(entry_id)
        self._save_prefs()
        self._rebuild_tree(self.selected_entry)

    def _toggle_selected_favorite(self) -> None:
        if self.selected_entry:
            self._toggle_favorite(self._entry_id(*self.selected_entry))

    def _refresh_editor(self) -> None:
        if self.selected_entry is None:
            self.editor_stack.setCurrentWidget(self.blank_editor)
            return
        kind, token = self.selected_entry
        self._updating = True
        try:
            self.token_title.setText(friendly_token_label(token))
            self.token_official.setText(f"Official semantic role: {token}")
            self.token_description.setText(semantic_description(kind, token))
            state, detail = self._state_for(kind, token)
            self.state_banner.setText(f"{state} · {detail}")
            self.favorite_btn.setText("★ Favorite" if self._entry_id(kind, token) in self.favorites else "☆ Favorite")
            if kind == "color":
                self.editor_stack.setCurrentWidget(self.color_editor)
                self._refresh_color_editor(token)
            elif kind == "shadow":
                self.editor_stack.setCurrentWidget(self.shadow_editor)
                self._refresh_shadow_editor(token)
            else:
                self.editor_stack.setCurrentWidget(self.gradient_editor)
                self._refresh_gradient_editor(token)
            self._refresh_layers()
        finally:
            self._updating = False

    def _refresh_color_editor(self, token: str) -> None:
        value = self.draft.colors[token]
        self.color_preview.set_rgba(value)
        self.color_swatch.set_rgba(value)
        self.r_spin.setValue(value.r)
        self.g_spin.setValue(value.g)
        self.b_spin.setValue(value.b)
        self.a_spin.setValue(value.a)
        self.a_slider.setValue(value.a)
        self.alpha_pct.setText(f"{value.a * 100.0 / 255.0:.1f}%")
        relation = nearest_composite_relation(token)
        if relation is None:
            predicted = alpha_over(value, Rgba(24, 30, 31, 255))
            self.composite_preview.set_rgba(predicted)
            self.composite_preview.set_clickable(False)
            self.composite_note.setText("No mapped neighbour; preview uses Foundry's neutral dark reference.")
        else:
            lower = self.draft.colors[relation.lower]
            upper = self.draft.colors[relation.upper]
            predicted = alpha_over(upper, lower)
            self.composite_preview.set_rgba(predicted)
            self.composite_preview.set_clickable(relation.reverse_solve)
            other = relation.upper if token == relation.lower else relation.lower
            self.composite_note.setText(
                f"{relation.explanation}\nComposite with: {friendly_token_label(other)}"
                + ("\nClick preview to solve backwards." if relation.reverse_solve else "")
            )

    def _refresh_shadow_editor(self, token: str) -> None:
        value = self.draft.shadows[token]
        self.shadow_preview.set_shadow(value)
        self.shadow_swatch.set_rgba(value.color)
        self.shadow_blur.setValue(value.blur_radius)
        self.shadow_x.setValue(value.offset_x)
        self.shadow_y.setValue(value.offset_y)
        self.shadow_disabled.setValue(value.disabled_alpha_scale)

    def _refresh_gradient_editor(self, token: str) -> None:
        value = self.draft.gradients[token]
        self.gradient_preview.set_gradient(value)
        self.gradient_stop_combo.blockSignals(True)
        self.gradient_stop_combo.clear()
        for index, stop in enumerate(value.stops):
            self.gradient_stop_combo.addItem(f"Stop {index + 1} · {stop.position:.3f}", index)
        self._gradient_stop_index = min(self._gradient_stop_index, len(value.stops) - 1)
        self.gradient_stop_combo.setCurrentIndex(self._gradient_stop_index)
        self.gradient_stop_combo.blockSignals(False)
        self._refresh_gradient_stop_controls(token)
        self.gradient_remove_btn.setEnabled(len(value.stops) > 2)

    def _refresh_gradient_stop_controls(self, token: str) -> None:
        value = self.draft.gradients[token]
        index = max(0, min(self._gradient_stop_index, len(value.stops) - 1))
        self._gradient_stop_index = index
        stop = value.stops[index]
        self.gradient_swatch.set_rgba(stop.color)
        previous = value.stops[index - 1].position + 0.001 if index > 0 else 0.0
        following = value.stops[index + 1].position - 0.001 if index + 1 < len(value.stops) else 1.0
        self.gradient_position.blockSignals(True)
        self.gradient_position.setRange(previous, following)
        self.gradient_position.setValue(stop.position)
        self.gradient_position.blockSignals(False)

    def _refresh_layers(self) -> None:
        self.layers_tree.clear()
        if self.selected_entry is None or self.selected_entry[0] != "color":
            return
        token = self.selected_entry[1]
        for relation in relations_for(token):
            other = relation.upper if token == relation.lower else relation.lower
            if other not in self.draft.colors:
                continue
            relation_text = (
                "BELOW THIS" if relation.kind == "composite" and token == relation.upper
                else "ABOVE THIS" if relation.kind == "composite"
                else "STATE VARIANT" if relation.kind == "state"
                else relation.kind.upper()
            )
            item = QTreeWidgetItem([relation_text, friendly_token_label(other), relation.explanation])
            item.setData(0, Qt.ItemDataRole.UserRole, other)
            self.layers_tree.addTopLevelItem(item)

    def _layer_item_activated(self, item: QTreeWidgetItem, column: int) -> None:
        del column
        token = item.data(0, Qt.ItemDataRole.UserRole)
        if token:
            target = self.tree_items.get(self._entry_id("color", str(token)))
            if target is not None:
                self.tree.setCurrentItem(target)
                self.tree.scrollToItem(target)

    def _choose_qcolor(self, initial: Rgba, title: str, *, alpha: bool = True) -> Rgba | None:
        options = QColorDialog.ColorDialogOption.DontUseNativeDialog
        if alpha:
            options |= QColorDialog.ColorDialogOption.ShowAlphaChannel
        chosen = QColorDialog.getColor(QColor(*initial.as_tuple()), self, title, options)
        if not chosen.isValid():
            return None
        return Rgba(chosen.red(), chosen.green(), chosen.blue(), chosen.alpha())

    def _choose_selected_color(self) -> None:
        if not self.selected_entry or self.selected_entry[0] != "color":
            return
        token = self.selected_entry[1]
        chosen = self._choose_qcolor(self.draft.colors[token], f"Choose {friendly_token_label(token)}")
        if chosen:
            self._set_color(token, chosen)

    def _choose_composite_target(self) -> None:
        if not self.selected_entry or self.selected_entry[0] != "color":
            return
        token = self.selected_entry[1]
        relation = nearest_composite_relation(token)
        if relation is None or not relation.reverse_solve:
            return
        current = alpha_over(self.draft.colors[relation.upper], self.draft.colors[relation.lower])
        chosen = self._choose_qcolor(Rgba(current.r, current.g, current.b, 255), "Desired Visible Composite", alpha=False)
        if not chosen:
            return
        solved, note = solve_layer_for_target(
            selected_token=token, relation=relation, colors=self.draft.colors,
            target_rgb=(chosen.r, chosen.g, chosen.b),
        )
        if solved is None:
            self._warning("Composite target cannot be solved at this opacity", note)
            return
        self._set_color(token, solved)
        self._set_status(note)

    def _color_channels_changed(self, _value: int) -> None:
        if self._updating or not self.selected_entry or self.selected_entry[0] != "color":
            return
        token = self.selected_entry[1]
        old = self.draft.colors[token]
        self._set_color(token, Rgba(self.r_spin.value(), self.g_spin.value(), self.b_spin.value(), old.a))

    def _color_alpha_spin_changed(self, value: int) -> None:
        if self._updating or not self.selected_entry or self.selected_entry[0] != "color":
            return
        token = self.selected_entry[1]
        old = self.draft.colors[token]
        self._set_color(token, Rgba(old.r, old.g, old.b, int(value)))

    def _color_alpha_slider_changed(self, value: int) -> None:
        if self._updating or not self.selected_entry or self.selected_entry[0] != "color":
            return
        token = self.selected_entry[1]
        old = self.draft.colors[token]
        self._set_color(token, Rgba(old.r, old.g, old.b, int(value)))

    def _set_color(self, token: str, value: Rgba) -> None:
        self.draft.colors[token] = value
        self._after_value_change("color", token)

    def _choose_shadow_color(self) -> None:
        if not self.selected_entry or self.selected_entry[0] != "shadow":
            return
        token = self.selected_entry[1]
        old = self.draft.shadows[token]
        chosen = self._choose_qcolor(old.color, f"Choose {friendly_token_label(token)} Colour")
        if chosen:
            self.draft.shadows[token] = ShadowStyle(old.blur_radius, old.offset_x, old.offset_y, chosen, old.disabled_alpha_scale)
            self._after_value_change("shadow", token)

    def _shadow_numbers_changed(self, _value: float) -> None:
        if self._updating or not self.selected_entry or self.selected_entry[0] != "shadow":
            return
        token = self.selected_entry[1]
        old = self.draft.shadows[token]
        try:
            changed = ShadowStyle(
                blur_radius=self.shadow_blur.value(), offset_x=self.shadow_x.value(), offset_y=self.shadow_y.value(),
                color=old.color, disabled_alpha_scale=self.shadow_disabled.value(),
            )
        except (TypeError, ValueError) as exc:
            self._set_status(f"Invalid shadow value: {exc}")
            return
        self.draft.shadows[token] = changed
        self._after_value_change("shadow", token)

    def _gradient_stop_selected(self, index: int) -> None:
        if index < 0 or not self.selected_entry or self.selected_entry[0] != "gradient":
            return
        self._gradient_stop_index = index
        if not self._updating:
            self._updating = True
            try:
                self._refresh_gradient_stop_controls(self.selected_entry[1])
            finally:
                self._updating = False

    def _choose_gradient_stop_color(self) -> None:
        if not self.selected_entry or self.selected_entry[0] != "gradient":
            return
        token = self.selected_entry[1]
        gradient = self.draft.gradients[token]
        stop = gradient.stops[self._gradient_stop_index]
        chosen = self._choose_qcolor(stop.color, f"Choose {friendly_token_label(token)} Stop Colour")
        if chosen:
            stops = list(gradient.stops)
            stops[self._gradient_stop_index] = GradientStop(stop.position, chosen)
            self.draft.gradients[token] = GradientStyle(stops=tuple(stops))
            self._after_value_change("gradient", token)

    def _gradient_position_changed(self, value: float) -> None:
        if self._updating or not self.selected_entry or self.selected_entry[0] != "gradient":
            return
        token = self.selected_entry[1]
        gradient = self.draft.gradients[token]
        stops = list(gradient.stops)
        stop = stops[self._gradient_stop_index]
        stops[self._gradient_stop_index] = GradientStop(float(value), stop.color)
        try:
            self.draft.gradients[token] = GradientStyle(stops=tuple(stops))
        except (TypeError, ValueError) as exc:
            self._set_status(f"Invalid gradient position: {exc}")
            return
        self._after_value_change("gradient", token)

    def _gradient_add_stop(self) -> None:
        if not self.selected_entry or self.selected_entry[0] != "gradient":
            return
        token = self.selected_entry[1]
        stops = list(self.draft.gradients[token].stops)
        best = max(range(len(stops) - 1), key=lambda i: stops[i + 1].position - stops[i].position)
        left, right = stops[best], stops[best + 1]
        stops.insert(best + 1, GradientStop((left.position + right.position) / 2.0, left.color))
        self.draft.gradients[token] = GradientStyle(stops=tuple(stops))
        self._gradient_stop_index = best + 1
        self._after_value_change("gradient", token)

    def _gradient_remove_stop(self) -> None:
        if not self.selected_entry or self.selected_entry[0] != "gradient":
            return
        token = self.selected_entry[1]
        stops = list(self.draft.gradients[token].stops)
        if len(stops) <= 2:
            return
        del stops[self._gradient_stop_index]
        self._gradient_stop_index = min(self._gradient_stop_index, len(stops) - 1)
        self.draft.gradients[token] = GradientStyle(stops=tuple(stops))
        self._after_value_change("gradient", token)

    # Backdrop ---------------------------------------------------------
    def _refresh_backdrop_ui(self) -> None:
        self._updating = True
        try:
            mode = self.draft.backdrop_mode
            idx = self.backdrop_mode.findData(mode)
            self.backdrop_mode.setCurrentIndex(max(0, idx))
            self.backdrop_note.setText(BACKDROP_MODE_DESCRIPTIONS[mode])
            is_acrylic = mode == "acrylic"
            self.acrylic_preset.setEnabled(is_acrylic)
            self.backdrop_swatch.setEnabled(is_acrylic)
            self.backdrop_alpha.setEnabled(is_acrylic)
            tint = self.draft.backdrop_tint
            self.backdrop_swatch.set_rgba(tint)
            self.backdrop_alpha.setValue(max(1, tint.a))
            preset_name = matching_acrylic_preset(tint) or "Custom"
            pidx = self.acrylic_preset.findData(preset_name)
            self.acrylic_preset.setCurrentIndex(max(0, pidx))
            if is_acrylic:
                self.backdrop_value_label.setText(
                    f"Native Acrylic tint: {rgba_summary(tint)} · alpha {tint.a}/255"
                )
            elif mode == "glass":
                self.backdrop_value_label.setText(
                    f"Stored schema tint: {rgba_summary(tint)} · ignored by native Glass; edit semantic surface roles below."
                )
            else:
                self.backdrop_value_label.setText(
                    f"Stored schema tint: {rgba_summary(tint)} · ignored while backdrop is Off."
                )
        finally:
            self._updating = False

    def _backdrop_mode_changed(self, index: int) -> None:
        if self._updating:
            return
        mode = str(self.backdrop_mode.itemData(index))
        if mode not in BACKDROP_MODE_LABELS:
            return
        old_mode = self.draft.backdrop_mode
        if old_mode == "acrylic" and self.draft.backdrop_tint.a > 0:
            self._last_acrylic_tint = self.draft.backdrop_tint
        self.draft.backdrop_mode = mode
        if mode == "acrylic" and self.draft.backdrop_tint.a == 0:
            self.draft.backdrop_tint = self._last_acrylic_tint
        elif mode == "glass" and old_mode != "glass":
            # Make newly-authored Glass files visibly honest: native Glass does
            # not consume this tint. Keep RGB for reversible authoring but zero
            # alpha rather than pretending it is a native Glass strength.
            t = self.draft.backdrop_tint
            self.draft.backdrop_tint = Rgba(t.r, t.g, t.b, 0)
        self._refresh_backdrop_ui()
        self._update_dirty_status()
        self._set_status(BACKDROP_MODE_DESCRIPTIONS[mode])

    def _acrylic_preset_changed(self, index: int) -> None:
        if self._updating or self.draft.backdrop_mode != "acrylic":
            return
        name = self.acrylic_preset.itemData(index)
        for preset in ACRYLIC_TINT_PRESETS:
            if preset.name == name:
                self.draft.backdrop_tint = preset.tint
                self._last_acrylic_tint = preset.tint
                self._refresh_backdrop_ui()
                self._update_dirty_status()
                self._set_status(preset.description)
                return

    def _choose_backdrop_tint(self) -> None:
        if self.draft.backdrop_mode != "acrylic":
            return
        chosen = self._choose_qcolor(self.draft.backdrop_tint, "Choose Native Acrylic Tint / Strength")
        if chosen is None:
            return
        if chosen.a == 0:
            chosen = Rgba(chosen.r, chosen.g, chosen.b, 1)
            self._set_status("Acrylic requires non-zero native tint alpha; clamped to 1/255.")
        self.draft.backdrop_tint = chosen
        self._last_acrylic_tint = chosen
        self._refresh_backdrop_ui()
        self._update_dirty_status()

    def _backdrop_alpha_changed(self, value: int) -> None:
        if self._updating or self.draft.backdrop_mode != "acrylic":
            return
        tint = self.draft.backdrop_tint
        self.draft.backdrop_tint = Rgba(tint.r, tint.g, tint.b, max(1, int(value)))
        self._last_acrylic_tint = self.draft.backdrop_tint
        self._refresh_backdrop_ui()
        self._update_dirty_status()

    # Common updates ---------------------------------------------------
    def _after_value_change(self, kind: str, token: str) -> None:
        self._updating = True
        try:
            if self.selected_entry == (kind, token):
                if kind == "color":
                    self._refresh_color_editor(token)
                elif kind == "shadow":
                    self._refresh_shadow_editor(token)
                else:
                    self._refresh_gradient_editor(token)
                state, detail = self._state_for(kind, token)
                self.state_banner.setText(f"{state} · {detail}")
            self._refresh_tree_item(kind, token)
            if kind == "color":
                self._refresh_layers()
        finally:
            self._updating = False
        self._update_dirty_status()

    def _refresh_tree_item(self, kind: str, token: str) -> None:
        item = self.tree_items.get(self._entry_id(kind, token))
        if item is None:
            return
        state, detail = self._state_for(kind, token)
        item.setText(self.COL_STATE, state)
        item.setToolTip(self.COL_STATE, detail)
        item.setText(self.COL_WORKING, self._summary(kind, self._value_for_draft(kind, token)))

    def _theme_name_changed(self, text: str) -> None:
        self.draft.name = text
        self._update_dirty_status()

    def _current_spec_or_error(self) -> SettingsThemeSpec | None:
        self.draft.name = self.name_edit.text()
        try:
            spec = self.draft.to_spec()
            encoded = settings_theme_to_json(spec)
            decoded = settings_theme_from_json(encoded)
            if decoded != spec:
                raise ValueError("Strict .srtheme round-trip changed the ThemeSpec")
            return spec
        except (TypeError, ValueError, SettingsThemeFileError) as exc:
            self._error("Invalid theme draft", str(exc))
            return None

    def _is_dirty(self) -> bool:
        try:
            return self.draft.to_spec() != self.opened_spec
        except Exception:
            return True

    def _update_dirty_status(self) -> None:
        dirty = self._is_dirty()
        suffix = " *" if dirty else ""
        path_name = self.theme_path.name if self.theme_path else "Compiled Default Dark"
        self.setWindowTitle(f"{APP_TITLE} — {path_name}{suffix}")
        self.save_btn.setEnabled(dirty or self.theme_path is not None)

    def _reset_selected_opened(self) -> None:
        if self.selected_entry:
            self._set_selected_from_spec(self.opened_spec, *self.selected_entry)

    def _reset_selected_default(self) -> None:
        if self.selected_entry:
            self._set_selected_from_spec(self.default_spec, *self.selected_entry)

    def _set_selected_from_spec(self, spec: SettingsThemeSpec, kind: str, token: str) -> None:
        value = self._value_for_spec(spec, kind, token)
        if kind == "color":
            self.draft.colors[token] = value
        elif kind == "shadow":
            self.draft.shadows[token] = value
        else:
            self.draft.gradients[token] = value
        self._after_value_change(kind, token)

    def _reset_all_opened(self) -> None:
        name = self.draft.name
        self.draft = ThemeDraft.from_spec(self.opened_spec)
        self.draft.name = name
        self._reset_backdrop_helper()
        self._rebuild_tree(self.selected_entry)
        self._update_dirty_status()

    def _reset_all_default(self) -> None:
        name = self.draft.name
        self.draft = ThemeDraft.from_spec(self.default_spec)
        self.draft.name = name
        self._reset_backdrop_helper()
        self._rebuild_tree(self.selected_entry)
        self._update_dirty_status()

    def _reset_backdrop_helper(self) -> None:
        if self.draft.backdrop_tint.a > 0:
            self._last_acrylic_tint = self.draft.backdrop_tint
        self._refresh_backdrop_ui()

    # File lifecycle ---------------------------------------------------
    def new_from_default(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        self.opened_spec = self.default_spec
        self.draft = ThemeDraft.from_spec(self.default_spec)
        self.draft.name = "Untitled Theme"
        self.theme_path = None
        self.name_edit.setText(self.draft.name)
        self.file_label.setText("New unsaved theme based on compiled Default Dark")
        self._reset_backdrop_helper()
        self._rebuild_tree(self.selected_entry)
        self._update_dirty_status()

    def open_theme(self) -> None:
        if not self._confirm_discard_if_dirty():
            return
        directory = self.theme_path.parent if self.theme_path else self.repo_root / "themes"
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open semantic SRPSS Theme", str(directory),
            f"SRPSS Theme (*{SETTINGS_THEME_FILE_EXTENSION});;All Files (*)",
        )
        if path_str:
            self._open_theme_path(Path(path_str))

    def _open_theme_path(self, path: Path) -> None:
        try:
            spec = load_settings_theme_file(path)
        except Exception as exc:
            self._error("Open Theme failed", f"{exc}{self._legacy_theme_note(path)}")
            return
        self.opened_spec = spec
        self.draft = ThemeDraft.from_spec(spec)
        self.theme_path = path
        self.name_edit.setText(spec.name)
        self.file_label.setText(str(path))
        self._reset_backdrop_helper()
        self._rebuild_tree(self.selected_entry)
        self._update_dirty_status()
        self._save_prefs(last_theme=str(path))
        self._set_status(f"Loaded schema-v{spec.schema_version} semantic theme: {path.name}")

    def _legacy_theme_note(self, path: Path) -> str:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ""
        if isinstance(payload, dict) and payload.get("format") != "srpss.settings-theme":
            return (
                "\n\nThis looks like an old source-scanner Theme Foundry file. "
                f"It cannot be safely mapped automatically to semantic schema-v{SETTINGS_THEME_SCHEMA_VERSION} roles."
            )
        return ""

    def save_theme(self) -> None:
        if self.theme_path is None:
            self.save_theme_as()
            return
        spec = self._current_spec_or_error()
        if spec is None:
            return
        if self.theme_path.name.casefold() == CANONICAL_DEFAULT_FILENAME.casefold() and spec != self.default_spec:
            self._warning(
                "Default Dark is protected",
                "Default Dark.srtheme is the canonical mirror of compiled DEFAULT_DARK_SETTINGS_THEME. "
                "Save the edited theme under another filename instead.",
            )
            self.save_theme_as()
            return
        self._write_theme(spec, self.theme_path)

    def save_theme_as(self) -> None:
        spec = self._current_spec_or_error()
        if spec is None:
            return
        themes_dir = self.repo_root / "themes"
        themes_dir.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(ch for ch in spec.name if ch not in '<>:"/\\|?*').strip() or "SRPSS Theme"
        initial = self.theme_path or (themes_dir / f"{safe_name}{SETTINGS_THEME_FILE_EXTENSION}")
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save semantic SRPSS Theme", str(initial),
            f"SRPSS Theme (*{SETTINGS_THEME_FILE_EXTENSION});;All Files (*)",
        )
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix.lower() != SETTINGS_THEME_FILE_EXTENSION:
            path = path.with_suffix(SETTINGS_THEME_FILE_EXTENSION)
        if path.name.casefold() == CANONICAL_DEFAULT_FILENAME.casefold() and spec != self.default_spec:
            self._warning("Default Dark is protected", "Choose another filename; the canonical mirror must remain exact.")
            return
        self._write_theme(spec, path)

    def _write_theme(self, spec: SettingsThemeSpec, path: Path) -> None:
        try:
            save_settings_theme_file(spec, path)
            loaded = load_settings_theme_file(path)
            if loaded != spec:
                raise RuntimeError("Saved theme failed exact strict reload equality")
        except Exception as exc:
            self._error("Save Theme failed", str(exc))
            return
        self.theme_path = path
        self.opened_spec = spec
        self.draft = ThemeDraft.from_spec(spec)
        self.name_edit.setText(spec.name)
        self.file_label.setText(str(path))
        self._reset_backdrop_helper()
        self._rebuild_tree(self.selected_entry)
        self._update_dirty_status()
        self._save_prefs(last_theme=str(path))
        self._set_status(f"Saved and strict-reloaded complete semantic theme: {path.name}")

    def validate_draft(self) -> None:
        spec = self._current_spec_or_error()
        if spec is None:
            return
        material = BACKDROP_MODE_LABELS[spec.backdrop.mode]
        native = (
            f"native tint {rgba_summary(spec.backdrop.tint)}" if spec.backdrop.mode == "acrylic"
            else "native tint ignored; Qt semantic surfaces own Glass appearance" if spec.backdrop.mode == "glass"
            else "native backdrop disabled"
        )
        self._info(
            "Theme draft is valid",
            f"{spec.name}\n\nSchema: {spec.schema_version}\nColours: {len(spec.colors)}\n"
            f"Shadows: {len(spec.shadows)}\nGradients: {len(spec.gradients)}\nBackdrop: {material}\n{native}",
        )

    def _check_default_mirror(self) -> None:
        path = self.repo_root / "themes" / CANONICAL_DEFAULT_FILENAME
        if not path.is_file():
            self._set_status("Canonical Default Dark.srtheme is missing; compiled fallback remains authoritative.")
            return
        try:
            mirror = load_settings_theme_file(path)
        except Exception as exc:
            self._set_status(f"Canonical Default Dark mirror is invalid: {exc}")
            return
        if mirror != self.default_spec:
            self._set_status("WARNING: Default Dark.srtheme does not equal compiled DEFAULT_DARK_SETTINGS_THEME.")

    def _confirm_discard_if_dirty(self) -> bool:
        if not self._is_dirty():
            return True
        answer = QMessageBox.question(
            self, "Discard unsaved Theme Foundry changes?",
            "The working theme has unsaved changes. Discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def closeEvent(self, event) -> None:  # type: ignore[override]
        event.accept() if self._confirm_discard_if_dirty() else event.ignore()

    def launch_settings(self) -> None:
        main_py = self.repo_root / "main.py"
        if not main_py.is_file():
            self._error("Cannot launch Settings", f"main.py not found under:\n{self.repo_root}")
            return
        if self._is_dirty():
            self._warning(
                "Unsaved theme",
                "Settings can only load saved .srtheme files. Save this draft first, then select it from Settings > Themes.",
            )
            return
        try:
            subprocess.Popen([sys.executable, str(main_py), "--s"], cwd=str(self.repo_root))
        except Exception as exc:
            self._error("Cannot launch Settings", str(exc))
            return
        current = self.theme_path.name if self.theme_path else "Default Dark"
        self._set_status(f"Launched Settings with --s · select {current!r} from Themes to test it.")

    def _save_prefs(self, *, last_theme: str | None = None) -> None:
        self._prefs["version"] = PREFERENCES_VERSION
        self._prefs["favorites"] = sorted(self.favorites)
        if last_theme is not None:
            self._prefs["last_theme"] = last_theme
        _save_preferences(self._prefs)

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def _warning(self, title: str, text: str) -> None:
        QMessageBox.warning(self, title, text)

    def _error(self, title: str, text: str) -> None:
        QMessageBox.critical(self, title, text)

    def _info(self, title: str, text: str) -> None:
        QMessageBox.information(self, title, text)


def _find_repo_root(script_path: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    candidate = script_path.resolve().parents[1]
    if (candidate / "ui").is_dir():
        return candidate
    cwd = Path.cwd().resolve()
    if (cwd / "ui").is_dir():
        return cwd
    return candidate


def _validate_file(path: Path) -> int:
    try:
        theme = load_settings_theme_file(path)
    except Exception as exc:
        print(f"INVALID: {path}\n{exc}", file=sys.stderr)
        return 2
    print(
        f"VALID: {path}\nname={theme.name!r} schema={theme.schema_version} "
        f"colors={len(theme.colors)} shadows={len(theme.shadows)} gradients={len(theme.gradients)} "
        f"backdrop={theme.backdrop.mode} tint={theme.backdrop.tint.as_list()}"
    )
    return 0


def _dump_schema() -> int:
    theme = DEFAULT_DARK_SETTINGS_THEME
    print(f"SettingsThemeSpec schema {theme.schema_version}")
    print(f"Backdrop: mode={theme.backdrop.mode} tint={theme.backdrop.tint.as_list()}")
    print("Modes: off, acrylic, glass")
    print("  acrylic: state-4 native tint is meaningful and alpha must be non-zero")
    print("  glass: state-3 native blur is untinted; backdrop.tint is ignored by the native adapter")
    print("\nColours:")
    for token in theme.colors:
        print(f"  {token}")
    print("\nShadows:")
    for token in theme.shadows:
        print(f"  {token}")
    print("\nGradients:")
    for token, gradient in theme.gradients.items():
        print(f"  {token} ({len(gradient.stops)} stops)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SRPSS semantic SettingsThemeSpec/.srtheme authoring tool")
    parser.add_argument("--repo", help="SRPSS repository root (auto-detected under tools/)")
    parser.add_argument("--open", dest="open_theme", help="Open one strict semantic .srtheme on startup")
    parser.add_argument("--validate", metavar="THEME", help="Validate one .srtheme and exit")
    parser.add_argument("--dump-schema", action="store_true", help="List current semantic schema roles and exit")
    args = parser.parse_args(argv)

    repo_root = _find_repo_root(Path(__file__), args.repo)
    if not (repo_root / "ui" / "settings_theme_spec.py").is_file():
        print(
            f"Theme Foundry could not locate SRPSS semantic theme modules under {repo_root}.\n"
            "Place it under tools/theme_foundry.py or pass --repo PATH.",
            file=sys.stderr,
        )
        return 2
    if args.validate:
        return _validate_file(Path(args.validate).expanduser().resolve())
    if args.dump_schema:
        return _dump_schema()

    initial_theme = Path(args.open_theme).expanduser().resolve() if args.open_theme else None
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_TITLE)
    window = ThemeFoundryWindow(repo_root, initial_theme=initial_theme)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
