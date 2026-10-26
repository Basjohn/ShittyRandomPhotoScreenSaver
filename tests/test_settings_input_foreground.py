"""Native input roles must follow semantic colours rather than the OS palette."""
from dataclasses import replace

import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QComboBox, QLineEdit, QSpinBox, QVBoxLayout, QWidget

from ui.settings_theme import _build_settings_root_stylesheet
from ui.settings_theme_spec import DEFAULT_DARK_SETTINGS_THEME, Rgba


@pytest.mark.parametrize("foreground", [Rgba(30, 40, 50), Rgba(230, 240, 250, 220)])
def test_input_roles_follow_current_semantics_across_live_theme_changes(qt_app, foreground):
    root = QWidget()
    layout = QVBoxLayout(root)
    controls = (QLineEdit(), QSpinBox(), QComboBox())
    for control in controls:
        layout.addWidget(control)
    # A component's local surface override must not hide the shared text rule.
    controls[0].setStyleSheet("QLineEdit { background-color: rgba(220, 220, 220, 200); }")
    controls[0].setPlaceholderText("Feed address")
    colors = dict(DEFAULT_DARK_SETTINGS_THEME.colors)
    colors["control.input.text"] = foreground
    colors["control.input.disabled_text"] = Rgba(100, 110, 120, 150)
    try:
        for value in (foreground, Rgba(80, 60, 90, 200), foreground):
            colors["control.input.text"] = value
            root.setStyleSheet(_build_settings_root_stylesheet(replace(DEFAULT_DARK_SETTINGS_THEME, colors=colors)))
            for control in controls:
                control.ensurePolished()
                palette = control.palette()
                assert palette.color(QPalette.ColorRole.Text) == QColor(*value.as_tuple())
                assert palette.color(QPalette.ColorRole.PlaceholderText) == QColor(value.r, value.g, value.b, round(value.a * 0.5))
                control.setEnabled(False)
                assert control.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.PlaceholderText) == QColor(100, 110, 120, 150)
                control.setEnabled(True)
    finally:
        root.deleteLater()
        qt_app.processEvents()
