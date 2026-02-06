"""Imgur widget section for widgets tab.

Extracted from widgets_tab.py to reduce monolith size.
Contains UI building, settings loading/saving for Imgur widget.
Gated behind SRPSS_ENABLE_DEV environment variable.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QLineEdit, QPushButton,
    QSlider, QFontComboBox, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab

logger = get_logger(__name__)


def build_imgur_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build imgur section UI and attach widgets to tab instance.

    Returns the imgur container widget.
    """
    from ui.tabs.widgets_tab import NoWheelSlider

    imgur_group = QGroupBox("Imgur Widget")
    imgur_layout = QVBoxLayout(imgur_group)

    tab.imgur_enabled = QCheckBox("Enable Imgur Widget")
    tab.imgur_enabled.setToolTip("Shows a grid of images from Imgur tags.")
    tab.imgur_enabled.setChecked(tab._default_bool('imgur', 'enabled', False))
    tab.imgur_enabled.stateChanged.connect(tab._save_settings)
    imgur_layout.addWidget(tab.imgur_enabled)

    imgur_info = QLabel(
        "Displays curated images from Imgur. Click images to open in browser."
    )
    imgur_info.setWordWrap(True)
    imgur_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
    imgur_layout.addWidget(imgur_info)

    # Tag selection
    imgur_tag_row = QHBoxLayout()
    imgur_tag_row.addWidget(QLabel("Tag:"))
    tab.imgur_tag = QComboBox()
    tab.imgur_tag.addItems([
        "most_viral", "memes", "aww", "dog", "cats", "funny",
        "earthporn", "architecture", "wallpapers", "gifs", "pics", "custom"
    ])
    tab.imgur_tag.setToolTip("Select Imgur tag or choose 'custom' to enter your own")
    tab.imgur_tag.currentTextChanged.connect(tab._save_settings)
    tab.imgur_tag.currentTextChanged.connect(tab._on_imgur_tag_changed)
    imgur_tag_row.addWidget(tab.imgur_tag)
    tab._set_combo_text(tab.imgur_tag, tab._default_str('imgur', 'tag', 'most_viral'))

    imgur_tag_row.addWidget(QLabel("Custom:"))
    tab.imgur_custom_tag = QLineEdit()
    tab.imgur_custom_tag.setPlaceholderText("e.g. nature")
    tab.imgur_custom_tag.setMaximumWidth(120)
    tab.imgur_custom_tag.textChanged.connect(tab._save_settings)
    imgur_tag_row.addWidget(tab.imgur_custom_tag)
    imgur_tag_row.addStretch()
    imgur_layout.addLayout(imgur_tag_row)

    # Grid dimensions
    imgur_grid_row = QHBoxLayout()
    imgur_grid_row.addWidget(QLabel("Grid Rows:"))
    tab.imgur_grid_rows = QSpinBox()
    tab.imgur_grid_rows.setRange(1, 6)
    tab.imgur_grid_rows.setValue(tab._default_int('imgur', 'grid_rows', 2))
    tab.imgur_grid_rows.setToolTip("Number of rows in the image grid (1-6)")
    tab.imgur_grid_rows.valueChanged.connect(tab._save_settings)
    tab.imgur_grid_rows.valueChanged.connect(tab._update_imgur_grid_total)
    imgur_grid_row.addWidget(tab.imgur_grid_rows)

    imgur_grid_row.addWidget(QLabel("Columns:"))
    tab.imgur_grid_cols = QSpinBox()
    tab.imgur_grid_cols.setRange(1, 8)
    tab.imgur_grid_cols.setValue(tab._default_int('imgur', 'grid_columns', 4))
    tab.imgur_grid_cols.setToolTip("Number of columns in the image grid (1-8)")
    tab.imgur_grid_cols.valueChanged.connect(tab._save_settings)
    tab.imgur_grid_cols.valueChanged.connect(tab._update_imgur_grid_total)
    imgur_grid_row.addWidget(tab.imgur_grid_cols)

    tab.imgur_grid_total = QLabel("= 8 images")
    imgur_grid_row.addWidget(tab.imgur_grid_total)
    imgur_grid_row.addStretch()
    imgur_layout.addLayout(imgur_grid_row)

    # Position
    imgur_pos_row = QHBoxLayout()
    imgur_pos_row.addWidget(QLabel("Position:"))
    tab.imgur_position = QComboBox()
    tab.imgur_position.addItems([
        "Top Left", "Top Center", "Top Right",
        "Middle Left", "Center", "Middle Right",
        "Bottom Left", "Bottom Center", "Bottom Right",
    ])
    tab.imgur_position.setToolTip("Screen position for the Imgur widget")
    tab.imgur_position.currentTextChanged.connect(tab._save_settings)
    imgur_pos_row.addWidget(tab.imgur_position)
    tab._set_combo_text(tab.imgur_position, tab._default_str('imgur', 'position', 'Top Right'))
    imgur_pos_row.addStretch()
    imgur_layout.addLayout(imgur_pos_row)

    # Display (monitor selection)
    imgur_disp_row = QHBoxLayout()
    imgur_disp_row.addWidget(QLabel("Display:"))
    tab.imgur_monitor_combo = QComboBox()
    tab.imgur_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.imgur_monitor_combo.setToolTip("Which monitor(s) to show the Imgur widget on")
    tab.imgur_monitor_combo.currentTextChanged.connect(tab._save_settings)
    imgur_disp_row.addWidget(tab.imgur_monitor_combo)
    imgur_monitor_default = tab._widget_default('imgur', 'monitor', 2)
    tab._set_combo_text(tab.imgur_monitor_combo, str(imgur_monitor_default))
    imgur_disp_row.addStretch()
    imgur_layout.addLayout(imgur_disp_row)

    # Update interval
    imgur_interval_row = QHBoxLayout()
    imgur_interval_row.addWidget(QLabel("Update Interval:"))
    tab.imgur_interval = QSpinBox()
    tab.imgur_interval.setRange(5, 60)
    tab.imgur_interval.setSuffix(" min")
    tab.imgur_interval.setValue(tab._default_int('imgur', 'update_interval', 600) // 60)
    tab.imgur_interval.setToolTip("How often to refresh images from Imgur (5-60 minutes)")
    tab.imgur_interval.valueChanged.connect(tab._save_settings)
    imgur_interval_row.addWidget(tab.imgur_interval)
    imgur_interval_row.addStretch()
    imgur_layout.addLayout(imgur_interval_row)

    # Show header
    tab.imgur_show_header = QCheckBox("Show Header")
    tab.imgur_show_header.setToolTip("Show Imgur logo and tag name in header")
    tab.imgur_show_header.setChecked(tab._default_bool('imgur', 'show_header', True))
    tab.imgur_show_header.stateChanged.connect(tab._save_settings)
    imgur_layout.addWidget(tab.imgur_show_header)

    # Font family
    imgur_font_family_row = QHBoxLayout()
    imgur_font_family_row.addWidget(QLabel("Font:"))
    tab.imgur_font_combo = QFontComboBox()
    default_imgur_font = tab._default_str('imgur', 'font_family', 'Segoe UI')
    tab.imgur_font_combo.setCurrentFont(QFont(default_imgur_font))
    tab.imgur_font_combo.setMinimumWidth(220)
    tab.imgur_font_combo.setToolTip("Font family for Imgur widget text")
    tab.imgur_font_combo.currentFontChanged.connect(tab._save_settings)
    imgur_font_family_row.addWidget(tab.imgur_font_combo)
    imgur_font_family_row.addStretch()
    imgur_layout.addLayout(imgur_font_family_row)

    # Font size
    imgur_font_row = QHBoxLayout()
    imgur_font_row.addWidget(QLabel("Font Size:"))
    tab.imgur_font_size = QSpinBox()
    tab.imgur_font_size.setRange(8, 48)
    tab.imgur_font_size.setValue(tab._default_int('imgur', 'font_size', 11))
    tab.imgur_font_size.setAccelerated(True)
    tab.imgur_font_size.setToolTip("Font size for Imgur widget text (8-48px)")
    tab.imgur_font_size.valueChanged.connect(tab._save_settings)
    imgur_font_row.addWidget(tab.imgur_font_size)
    imgur_font_row.addWidget(QLabel("px"))
    imgur_font_row.addStretch()
    imgur_layout.addLayout(imgur_font_row)

    # Margin
    imgur_margin_row = QHBoxLayout()
    imgur_margin_row.addWidget(QLabel("Margin:"))
    tab.imgur_margin = QSpinBox()
    tab.imgur_margin.setRange(0, 100)
    tab.imgur_margin.setValue(tab._default_int('imgur', 'margin', 30))
    tab.imgur_margin.setAccelerated(True)
    tab.imgur_margin.valueChanged.connect(tab._save_settings)
    imgur_margin_row.addWidget(tab.imgur_margin)
    imgur_margin_row.addWidget(QLabel("px"))
    imgur_margin_row.addStretch()
    imgur_layout.addLayout(imgur_margin_row)

    # Text color
    imgur_color_row = QHBoxLayout()
    imgur_color_row.addWidget(QLabel("Text Color:"))
    tab.imgur_color_btn = QPushButton("Choose Color...")
    tab.imgur_color_btn.clicked.connect(tab._choose_imgur_color)
    imgur_color_row.addWidget(tab.imgur_color_btn)
    imgur_color_row.addStretch()
    imgur_layout.addLayout(imgur_color_row)

    # Background frame
    tab.imgur_show_background = QCheckBox("Show Background Frame")
    tab.imgur_show_background.setToolTip("Show a semi-transparent background behind the widget")
    tab.imgur_show_background.setChecked(tab._default_bool('imgur', 'show_background', True))
    tab.imgur_show_background.stateChanged.connect(tab._save_settings)
    imgur_layout.addWidget(tab.imgur_show_background)

    # Intense shadow
    tab.imgur_intense_shadow = QCheckBox("Intense Shadow")
    tab.imgur_intense_shadow.setToolTip("Use a more pronounced drop shadow effect")
    tab.imgur_intense_shadow.setChecked(tab._default_bool('imgur', 'intense_shadow', True))
    tab.imgur_intense_shadow.stateChanged.connect(tab._save_settings)
    imgur_layout.addWidget(tab.imgur_intense_shadow)

    # Background opacity
    imgur_opacity_row = QHBoxLayout()
    imgur_opacity_row.addWidget(QLabel("Background Opacity:"))
    tab.imgur_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.imgur_bg_opacity.setMinimum(0)
    tab.imgur_bg_opacity.setMaximum(100)
    imgur_bg_opacity_pct = int(tab._default_float('imgur', 'bg_opacity', 0.6) * 100)
    tab.imgur_bg_opacity.setValue(imgur_bg_opacity_pct)
    tab.imgur_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.imgur_bg_opacity.setTickInterval(10)
    tab.imgur_bg_opacity.valueChanged.connect(tab._save_settings)
    imgur_opacity_row.addWidget(tab.imgur_bg_opacity)
    tab.imgur_bg_opacity_label = QLabel(f"{imgur_bg_opacity_pct}%")
    tab.imgur_bg_opacity.valueChanged.connect(
        lambda v: tab.imgur_bg_opacity_label.setText(f"{v}%")
    )
    imgur_opacity_row.addWidget(tab.imgur_bg_opacity_label)
    imgur_layout.addLayout(imgur_opacity_row)

    # Background color
    imgur_bg_color_row = QHBoxLayout()
    imgur_bg_color_row.addWidget(QLabel("Background Color:"))
    tab.imgur_bg_color_btn = QPushButton("Choose Color...")
    tab.imgur_bg_color_btn.clicked.connect(tab._choose_imgur_bg_color)
    imgur_bg_color_row.addWidget(tab.imgur_bg_color_btn)
    imgur_bg_color_row.addStretch()
    imgur_layout.addLayout(imgur_bg_color_row)

    # Border color
    imgur_border_color_row = QHBoxLayout()
    imgur_border_color_row.addWidget(QLabel("Border Color:"))
    tab.imgur_border_color_btn = QPushButton("Choose Color...")
    tab.imgur_border_color_btn.clicked.connect(tab._choose_imgur_border_color)
    imgur_border_color_row.addWidget(tab.imgur_border_color_btn)
    imgur_border_color_row.addStretch()
    imgur_layout.addLayout(imgur_border_color_row)

    # Border opacity
    imgur_border_opacity_row = QHBoxLayout()
    imgur_border_opacity_row.addWidget(QLabel("Border Opacity:"))
    tab.imgur_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.imgur_border_opacity.setMinimum(0)
    tab.imgur_border_opacity.setMaximum(100)
    imgur_border_opacity_pct = int(tab._default_float('imgur', 'border_opacity', 1.0) * 100)
    tab.imgur_border_opacity.setValue(imgur_border_opacity_pct)
    tab.imgur_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.imgur_border_opacity.setTickInterval(10)
    tab.imgur_border_opacity.valueChanged.connect(tab._save_settings)
    imgur_border_opacity_row.addWidget(tab.imgur_border_opacity)
    tab.imgur_border_opacity_label = QLabel(f"{imgur_border_opacity_pct}%")
    tab.imgur_border_opacity.valueChanged.connect(
        lambda v: tab.imgur_border_opacity_label.setText(f"{v}%")
    )
    imgur_border_opacity_row.addWidget(tab.imgur_border_opacity_label)
    imgur_layout.addLayout(imgur_border_opacity_row)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.addWidget(imgur_group)
    return container


def load_imgur_settings(tab: WidgetsTab, widgets: dict) -> None:
    """Load imgur settings from widgets config dict."""
    if not hasattr(tab, 'imgur_enabled'):
        return

    imgur_config = widgets.get('imgur', {})
    tab.imgur_enabled.setChecked(tab._config_bool('imgur', imgur_config, 'enabled', False))
    imgur_tag = tab._config_str('imgur', imgur_config, 'tag', 'most_viral')
    imgur_tag_idx = tab.imgur_tag.findText(imgur_tag)
    if imgur_tag_idx >= 0:
        tab.imgur_tag.setCurrentIndex(imgur_tag_idx)
    tab.imgur_custom_tag.setText(tab._config_str('imgur', imgur_config, 'custom_tag', ''))
    tab.imgur_grid_rows.setValue(tab._config_int('imgur', imgur_config, 'grid_rows', 2))
    tab.imgur_grid_cols.setValue(tab._config_int('imgur', imgur_config, 'grid_columns', 4))
    imgur_pos = tab._config_str('imgur', imgur_config, 'position', 'Top Right')
    imgur_pos_idx = tab.imgur_position.findText(imgur_pos)
    if imgur_pos_idx >= 0:
        tab.imgur_position.setCurrentIndex(imgur_pos_idx)
    imgur_monitor = imgur_config.get('monitor', tab._widget_default('imgur', 'monitor', 2))
    imgur_mon_text = str(imgur_monitor) if isinstance(imgur_monitor, (int, str)) else '2'
    imgur_mon_idx = tab.imgur_monitor_combo.findText(imgur_mon_text)
    if imgur_mon_idx >= 0:
        tab.imgur_monitor_combo.setCurrentIndex(imgur_mon_idx)
    imgur_interval = tab._config_int('imgur', imgur_config, 'update_interval', 600) // 60
    tab.imgur_interval.setValue(max(5, min(60, imgur_interval)))
    tab.imgur_show_header.setChecked(tab._config_bool('imgur', imgur_config, 'show_header', True))

    tab.imgur_font_combo.setCurrentFont(QFont(tab._config_str('imgur', imgur_config, 'font_family', 'Segoe UI')))
    tab.imgur_font_size.setValue(tab._config_int('imgur', imgur_config, 'font_size', 11))
    tab.imgur_margin.setValue(tab._config_int('imgur', imgur_config, 'margin', 30))
    tab.imgur_show_background.setChecked(tab._config_bool('imgur', imgur_config, 'show_background', True))
    tab.imgur_intense_shadow.setChecked(tab._config_bool('imgur', imgur_config, 'intense_shadow', True))

    imgur_opacity_pct = int(tab._config_float('imgur', imgur_config, 'bg_opacity', 0.6) * 100)
    tab.imgur_bg_opacity.setValue(imgur_opacity_pct)
    tab.imgur_bg_opacity_label.setText(f"{imgur_opacity_pct}%")

    imgur_border_opacity_pct = int(tab._config_float('imgur', imgur_config, 'border_opacity', 1.0) * 100)
    tab.imgur_border_opacity.setValue(imgur_border_opacity_pct)
    tab.imgur_border_opacity_label.setText(f"{imgur_border_opacity_pct}%")

    imgur_color_data = imgur_config.get('color', tab._widget_default('imgur', 'color', [255, 255, 255, 230]))
    tab._imgur_color = QColor(*imgur_color_data)
    imgur_bg_color_data = imgur_config.get('bg_color', tab._widget_default('imgur', 'bg_color', [35, 35, 35, 255]))
    try:
        tab._imgur_bg_color = QColor(*imgur_bg_color_data)
    except Exception:
        logger.debug("[WIDGETS_TAB] Exception suppressed: invalid imgur bg color", exc_info=True)
    imgur_border_color_data = imgur_config.get('border_color', tab._widget_default('imgur', 'border_color', [255, 255, 255, 255]))
    try:
        tab._imgur_border_color = QColor(*imgur_border_color_data)
    except Exception:
        logger.debug("[WIDGETS_TAB] Exception suppressed: invalid imgur border color", exc_info=True)

    tab._on_imgur_tag_changed(imgur_tag)
    tab._update_imgur_grid_total()


def save_imgur_settings(tab: WidgetsTab) -> dict | None:
    """Return imgur config dict from current UI state, or None if not available."""
    if not hasattr(tab, 'imgur_enabled'):
        return None

    imgur_config = {
        'enabled': tab.imgur_enabled.isChecked(),
        'tag': tab.imgur_tag.currentText(),
        'custom_tag': tab.imgur_custom_tag.text().strip(),
        'grid_rows': tab.imgur_grid_rows.value(),
        'grid_columns': tab.imgur_grid_cols.value(),
        'position': tab.imgur_position.currentText(),
        'update_interval': tab.imgur_interval.value() * 60,
        'show_header': tab.imgur_show_header.isChecked(),
        'font_family': tab.imgur_font_combo.currentFont().family(),
        'font_size': tab.imgur_font_size.value(),
        'margin': tab.imgur_margin.value(),
        'color': [tab._imgur_color.red(), tab._imgur_color.green(),
                  tab._imgur_color.blue(), tab._imgur_color.alpha()],
        'show_background': tab.imgur_show_background.isChecked(),
        'intense_shadow': tab.imgur_intense_shadow.isChecked(),
        'bg_opacity': tab.imgur_bg_opacity.value() / 100.0,
        'bg_color': [tab._imgur_bg_color.red(), tab._imgur_bg_color.green(),
                     tab._imgur_bg_color.blue(), tab._imgur_bg_color.alpha()],
        'border_color': [tab._imgur_border_color.red(), tab._imgur_border_color.green(),
                         tab._imgur_border_color.blue(), tab._imgur_border_color.alpha()],
        'border_opacity': tab.imgur_border_opacity.value() / 100.0,
    }
    imgur_mon_text = tab.imgur_monitor_combo.currentText()
    imgur_config['monitor'] = imgur_mon_text if imgur_mon_text == 'ALL' else int(imgur_mon_text)
    return imgur_config
