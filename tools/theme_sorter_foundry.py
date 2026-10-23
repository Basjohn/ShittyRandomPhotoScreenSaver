#!/usr/bin/env python3
"""Theme Sorter Foundry: authentic SRPSS Settings/Widget theme inspection and pair operations.

Standalone PySide6 tool, does not modify SRPSS theme selection or current Settings.
Run: .venv\\Scripts\\python.exe tools\\theme_sorter_foundry.py
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
    QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ui.settings_theme_io import load_settings_theme_file
from ui.widget_theme_io import load_widget_theme_file
from ui.tabs.shared_styles import NoWheelSlider, render_settings_preview_control_styles
from ui.widgets.styled_combo_box import StyledComboBox
from tools.foundry_chrome import (
    FoundryTitleBar, apply_native_backdrop, configure_frameless_window,
)
from tools.godzip_foundry_theme import render_foundry_stylesheet
from tools.theme_sorter_model import (
    ThemePair, ThemeSorterError, delete_theme_pair, list_theme_pairs, rename_theme_pair,
)


def _qss_rgba(colour) -> str:
    return f"rgba({colour.r},{colour.g},{colour.b},{colour.a})"


class ThemeSorterFoundry(QMainWindow):
    """Actual themed preview, not a synthetic static dark panel."""

    def __init__(self, themes_root: Path) -> None:
        super().__init__()
        self.root = themes_root.resolve()
        self._pairs: tuple[ThemePair, ...] = ()
        self._backdrop_theme = None
        self._backdrop_mode = None
        self.setWindowTitle('SRPSS Theme Sorter Foundry')
        configure_frameless_window(self)
        self.resize(1010, 750)
        self.setMinimumSize(780, 630)

        root = QWidget(self)
        root.setObjectName('sorterRoot')
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(2, 2, 2, 2)
        outer.setSpacing(0)

        shell = QFrame(root)
        shell.setObjectName('sorterShell')
        outer.addWidget(shell, 1)
        main = QVBoxLayout(shell)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self.titlebar = FoundryTitleBar('THEME SORTER FOUNDRY', self)
        main.addWidget(self.titlebar)

        pane = QWidget(shell)
        pane.setObjectName('sorterPane')
        inner = QVBoxLayout(pane)
        inner.setContentsMargins(22, 16, 22, 16)
        inner.setSpacing(12)
        main.addWidget(pane, 1)

        helptext = QLabel('Inspect the actual Settings palette, native background material, and linked Widget theme.')
        helptext.setObjectName('sorterMuted')
        inner.addWidget(helptext)
        catalogue = QLabel(f'Catalogue: {self.root}')
        catalogue.setObjectName('sorterFaint')
        catalogue.setWordWrap(True)
        inner.addWidget(catalogue)

        row = QHBoxLayout()
        self.combo = StyledComboBox(pane)
        self.combo.setMinimumWidth(280)
        self.combo.setObjectName('sorterThemeCombo')
        self.combo.currentIndexChanged.connect(self._selected)
        row.addWidget(self.combo, 1)
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self.refresh)
        row.addWidget(refresh)
        inner.addLayout(row)
        self.pair_info = QLabel('')
        self.pair_info.setObjectName('sorterMuted')
        self.pair_info.setWordWrap(True)
        inner.addWidget(self.pair_info)

        actions = QHBoxLayout()
        self.copy_button = QPushButton('Copy Theme Name')
        self.rename_button = QPushButton('Rename Theme Pair')
        self.delete_button = QPushButton('Delete Theme Combo')
        self.rename_button.setObjectName('sorterPrimary')
        for button in (self.copy_button, self.rename_button, self.delete_button):
            actions.addWidget(button, 1)
        inner.addLayout(actions)
        self.copy_button.clicked.connect(self._copy)
        self.rename_button.clicked.connect(self._rename)
        self.delete_button.clicked.connect(self._delete)

        self.preview_tabs = QTabWidget(pane)
        controls_tab = QWidget(self.preview_tabs)
        controls = QVBoxLayout(controls_tab)
        controls.setContentsMargins(12, 12, 12, 12)
        controls.setSpacing(11)
        controls.addWidget(QLabel('Real Settings controls and visual states'))
        self.sample_group = QFrame(controls_tab)
        self.sample_group.setObjectName('sorterGroup')
        group_layout = QVBoxLayout(self.sample_group)
        group_layout.setContentsMargins(18, 15, 18, 14)
        group_layout.setSpacing(12)
        self.demo_check = QCheckBox('Circle checkbox: enabled')
        self.demo_check.setProperty('circleIndicator', True)
        self.demo_check.setProperty('tightSpacing', True)
        self.demo_check.setChecked(True)
        group_layout.addWidget(self.demo_check)
        self.demo_text = QLineEdit('Editable control with focus and hover')
        group_layout.addWidget(self.demo_text)
        editrow = QHBoxLayout()
        self.demo_combo = StyledComboBox(self.sample_group, size_variant='compact')
        self.demo_combo.addItems(['First choice', 'Second choice', 'Third choice'])
        editrow.addWidget(self.demo_combo, 1)
        self.demo_spin = QDoubleSpinBox(self.sample_group)
        self.demo_spin.setRange(0, 100)
        self.demo_spin.setValue(42)
        self.demo_spin.setSingleStep(1)
        self.demo_spin.setFixedWidth(150)
        self.demo_spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        self.demo_spin.setKeyboardTracking(False)
        editrow.addWidget(self.demo_spin)
        group_layout.addLayout(editrow)
        self.demo_slider = NoWheelSlider(Qt.Orientation.Horizontal, self.sample_group)
        self.demo_slider.setRange(0, 100)
        self.demo_slider.setValue(65)
        self.demo_slider.setMinimumWidth(190)
        group_layout.addWidget(self.demo_slider)
        state_row = QHBoxLayout()
        self.demo_button = QPushButton('Normal / hover / press')
        state_row.addWidget(self.demo_button)
        disabled_button = QPushButton('Disabled')
        disabled_button.setEnabled(False)
        state_row.addWidget(disabled_button)
        group_layout.addLayout(state_row)
        controls.addWidget(self.sample_group)
        controls.addStretch(1)
        self.preview_tabs.addTab(controls_tab, 'Settings controls')

        surfaces_tab = QWidget(self.preview_tabs)
        surfaces = QVBoxLayout(surfaces_tab)
        surfaces.setContentsMargins(12, 12, 12, 12)
        surfaces.setSpacing(11)
        surfaces.addWidget(QLabel('Surfaces, hierarchy and linked Widget card roles'))
        self.sample_surface = QLabel('Panel surface and border; background material remains behind this panel.')
        self.sample_surface.setObjectName('sorterSurface')
        self.sample_surface.setWordWrap(True)
        self.sample_surface.setMinimumHeight(56)
        surfaces.addWidget(self.sample_surface)
        self.sample_widget_card = QLabel('Widget card preview')
        self.sample_widget_card.setObjectName('sorterWidgetCard')
        self.sample_widget_card.setMinimumHeight(105)
        self.sample_widget_card.setAlignment(Qt.AlignmentFlag.AlignCenter)
        surfaces.addWidget(self.sample_widget_card)
        surfaces.addStretch(1)
        self.preview_tabs.addTab(surfaces_tab, 'Surfaces and Widget')
        inner.addWidget(self.preview_tabs, 1)

        self.status = QLabel('')
        self.status.setObjectName('status')
        self.status.setWordWrap(True)
        inner.addWidget(self.status)
        self.refresh()

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self._apply_current_backdrop()

    def _apply_current_backdrop(self) -> None:
        theme = self._backdrop_theme
        if theme is None or not self.isVisible():
            return
        if theme.backdrop.mode == 'glass' and self._backdrop_mode == 'glass':
            # Native Windows Glass is one AccentPolicy; Qt owns the transparency.
            return
        if apply_native_backdrop(self, SimpleNamespace(theme=theme)):
            self._backdrop_mode = theme.backdrop.mode
        elif theme.backdrop.mode == 'off':
            self._backdrop_mode = 'off'

    def _current(self) -> ThemePair | None:
        path = self.combo.currentData()
        return next((p for p in self._pairs if str(p.settings_path) == path), None)

    def refresh(self, select: Path | None = None) -> None:
        previous = str(select) if select else self.combo.currentData()
        try:
            pairs = list_theme_pairs(self.root)
        except (OSError, ValueError) as exc:
            self.status.setText(f'Catalogue error: {exc}')
            return
        self._pairs = pairs
        self.combo.blockSignals(True)
        self.combo.clear()
        for pair in pairs:
            self.combo.addItem(pair.name, str(pair.settings_path))
        if previous:
            index = self.combo.findData(previous)
            if index >= 0:
                self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)
        self._selected()

    def _selected(self, *_unused) -> None:
        pair = self._current()
        for button in (self.copy_button, self.rename_button, self.delete_button):
            button.setEnabled(pair is not None)
        if pair is None:
            self.pair_info.setText('No authored Settings themes available.')
            return
        try:
            theme = load_settings_theme_file(pair.settings_path)
            # Exactly the Settings input/combobox/stepper/slider geometry and
            # theme roles, not the generic Godzip Foundry approximations.
            qss = (render_foundry_stylesheet(theme, use_settings_controls=True)
                   + '\n' + render_settings_preview_control_styles(theme))
            # Transparency belongs to the actual themed surface, not to a
            # permanent opaque preview panel. The compositor is already active
            # underneath; see-through Glass/Acrylic remains visible.
            border = _qss_rgba(theme.color('panel.border'))
            panel = _qss_rgba(theme.color('panel.group.surface'))
            helper = _qss_rgba(theme.color('text.secondary'))
            title_text = _qss_rgba(theme.color('window.titlebar.text'))
            qss += f"""
                QWidget#sorterRoot, QWidget#sorterPane {{ background: transparent; }}
                QFrame#sorterShell {{ background: {_qss_rgba(theme.color('window.dialog_glass'))}; border: 2px solid {border}; border-radius: 10px; }}
                QLabel#sorterMuted {{ color: {helper}; }}
                QLabel#sorterFaint {{ color: {helper}; font-size: 9pt; }}
                QFrame#sorterGroup {{ background: {panel}; border: 1.5px solid {border}; border-radius: 10px; }}
                QLabel#sorterSurface {{ background: {panel}; border: 1.5px solid {border}; border-radius: 9px; padding: 14px; }}
                QPushButton#sorterPrimary {{ background: {_qss_rgba(theme.color('control.setup_action.surface'))}; color: {_qss_rgba(theme.color('control.setup_action.text'))}; border-color: {_qss_rgba(theme.color('control.setup_action.border'))}; }}
                QComboBox#sorterThemeCombo {{ font-weight: 700; }}
            """

            self.setStyleSheet(qss)
            # The actual shared StyledComboBox popup uses the tool's selected
            # theme, not the process-global SRPSS Settings selection.
            for combo in (self.combo, self.demo_combo):
                combo._popup_stylesheet = render_settings_preview_control_styles(theme)
                for state, role in (
                    ('Normal', 'control.mode.text'),
                    ('Hover', 'control.mode.text'),
                    ('Pressed', 'control.mode.text'),
                    ('Disabled', 'text.disabled'),
                ):
                    c = theme.color(role)
                    combo.setProperty(f'previewKnob{state}', f'#{c.r:02x}{c.g:02x}{c.b:02x}')
                combo._knob_overlay._overlay.update()
            self._backdrop_theme = theme
            self._apply_current_backdrop()
            if pair.widget_path:
                widget = load_widget_theme_file(pair.widget_path)
                colors = widget.colors
                self.sample_widget_card.setStyleSheet(
                    'QLabel#sorterWidgetCard {'
                    f'background:{_qss_rgba(colors["card.background"])};'
                    f'color:{_qss_rgba(colors["card.text"])};'
                    f'border:2px solid {_qss_rgba(colors["card.border"])};'
                    'border-radius:9px; padding:14px;}'
                )
                self.sample_widget_card.setText('Actual linked Widget theme card')
            else:
                self.sample_widget_card.setStyleSheet('')
                self.sample_widget_card.setText('No linked Widget theme currently exists')
        except (OSError, ValueError, KeyError) as exc:
            self.status.setText(f'Unable to preview selected theme: {exc}')
            return
        widget_name = pair.widget_path.name if pair.widget_path else 'No linked Widget file (rename creates one)'
        self.pair_info.setText(f'Settings: {pair.settings_path.name}\nWidget: {widget_name}')
        self.status.setText(f'Previewing {pair.name} ({theme.backdrop.mode.upper()} material). Product Settings unchanged.')

    def _copy(self) -> None:
        pair = self._current()
        if pair:
            QApplication.clipboard().setText(pair.name)
            self.status.setText(f'Copied: {pair.name}')

    def _rename(self) -> None:
        pair = self._current()
        if not pair:
            return
        popup = QInputDialog(self)
        popup.setWindowTitle('Rename Theme Pair')
        popup.setLabelText('New name for the linked Settings and Widget themes:')
        popup.setTextValue(pair.name)
        popup.setStyleSheet(self.styleSheet())
        if popup.exec() != QInputDialog.DialogCode.Accepted:
            return
        try:
            updated = rename_theme_pair(self.root, pair.settings_path.name, popup.textValue())
        except (ThemeSorterError, OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Rename refused', str(exc))
            return
        self.refresh(updated.settings_path)
        self.status.setText(f'Renamed Settings and linked Widget themes to {updated.name}.')

    def _delete(self) -> None:
        pair = self._current()
        if not pair:
            return
        counterpart = pair.widget_path.name if pair.widget_path else '(no linked Widget file found)'
        reply = QMessageBox.question(
            self, 'Delete Theme Combo',
            f'Permanently delete these authored theme files?\n\n'
            f'{pair.settings_path.name}\n{counterpart}\n\nThis cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            deleted = delete_theme_pair(self.root, pair.settings_path.name)
        except (ThemeSorterError, OSError, ValueError) as exc:
            QMessageBox.warning(self, 'Delete refused', str(exc))
            return
        self.refresh()
        self.status.setText(f'Deleted {len(deleted)} linked theme file(s).')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=ROOT)
    parser.add_argument('--themes-dir', type=Path)
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    root = args.themes_dir if args.themes_dir is not None else args.repo / 'themes'
    window = ThemeSorterFoundry(root)
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
