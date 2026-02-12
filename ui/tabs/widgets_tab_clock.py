"""Clock widget section for widgets tab.

Extracted from widgets_tab.py to reduce monolith size.
Contains UI building, settings loading/saving for Clock 1/2/3.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QPushButton,
    QSlider, QFontComboBox, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.logging.logger import get_logger

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab

logger = get_logger(__name__)


def _update_clock_enabled_visibility(tab: WidgetsTab) -> None:
    """Show/hide all clock controls based on clock_enabled checkbox."""
    enabled = getattr(tab, 'clock_enabled', None) and tab.clock_enabled.isChecked()
    container = getattr(tab, '_clock_controls_container', None)
    if container is not None:
        container.setVisible(bool(enabled))


def _update_clock_mode_visibility(tab: WidgetsTab) -> None:
    """Show/hide analogue vs digital controls based on clock mode checkbox."""
    is_analog = getattr(tab, 'clock_analog_mode', None) and tab.clock_analog_mode.isChecked()
    analog_container = getattr(tab, '_clock_analog_container', None)
    digital_container = getattr(tab, '_clock_digital_container', None)
    if analog_container is not None:
        analog_container.setVisible(bool(is_analog))
    if digital_container is not None:
        digital_container.setVisible(not bool(is_analog))


def build_clock_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build clock section UI and attach widgets to tab instance.

    Returns the clocks container widget.
    """
    from ui.tabs.widgets_tab import NoWheelSlider

    clock_group = QGroupBox("Clock Widget")
    clock_layout = QVBoxLayout(clock_group)

    # Enable clock
    tab.clock_enabled = QCheckBox("Enable Clock")
    tab.clock_enabled.setChecked(tab._default_bool('clock', 'enabled', True))
    tab.clock_enabled.stateChanged.connect(tab._save_settings)
    tab.clock_enabled.stateChanged.connect(tab._update_stack_status)
    clock_layout.addWidget(tab.clock_enabled)

    # Container for all clock controls gated by enable checkbox
    tab._clock_controls_container = QWidget()
    _clock_ctrl_layout = QVBoxLayout(tab._clock_controls_container)
    _clock_ctrl_layout.setContentsMargins(0, 0, 0, 0)
    _clock_ctrl_layout.setSpacing(4)

    # Time format
    format_row = QHBoxLayout()
    format_row.addWidget(QLabel("Format:"))
    tab.clock_format = QComboBox()
    tab.clock_format.addItems(["12 Hour", "24 Hour"])
    tab.clock_format.currentTextChanged.connect(tab._save_settings)
    default_format = tab._default_str('clock', 'format', '24h').lower()
    format_map = {'12h': "12 Hour", '24h': "24 Hour"}
    tab._set_combo_text(tab.clock_format, format_map.get(default_format, "24 Hour"))
    format_row.addWidget(tab.clock_format)
    format_row.addStretch()
    _clock_ctrl_layout.addLayout(format_row)

    # Show seconds
    tab.clock_seconds = QCheckBox("Show Seconds")
    tab.clock_seconds.setChecked(tab._default_bool('clock', 'show_seconds', True))
    tab.clock_seconds.stateChanged.connect(tab._save_settings)
    tab.clock_seconds.stateChanged.connect(tab._update_stack_status)
    _clock_ctrl_layout.addWidget(tab.clock_seconds)

    # Timezone
    tz_row = QHBoxLayout()
    tz_row.addWidget(QLabel("Timezone:"))
    tab.clock_timezone = QComboBox()
    tab.clock_timezone.setMinimumWidth(200)
    tab._populate_timezones()
    default_timezone = tab._default_str('clock', 'timezone', 'local')
    tab._set_combo_data(tab.clock_timezone, default_timezone)
    tab.clock_timezone.currentTextChanged.connect(tab._save_settings)
    tz_row.addWidget(tab.clock_timezone)

    tab.tz_auto_btn = QPushButton("Auto-Detect")
    tab.tz_auto_btn.clicked.connect(tab._auto_detect_timezone)
    tz_row.addWidget(tab.tz_auto_btn)
    tz_row.addStretch()
    _clock_ctrl_layout.addLayout(tz_row)

    # Show timezone abbreviation
    tab.clock_show_tz = QCheckBox("Show Timezone Abbreviation")
    tab.clock_show_tz.setChecked(tab._default_bool('clock', 'show_timezone', True))
    tab.clock_show_tz.stateChanged.connect(tab._save_settings)
    tab.clock_show_tz.stateChanged.connect(tab._update_stack_status)
    _clock_ctrl_layout.addWidget(tab.clock_show_tz)

    # Analogue mode options
    tab.clock_analog_mode = QCheckBox("Use Analogue Clock")
    default_display_mode = tab._default_str('clock', 'display_mode', 'analog').lower()
    tab.clock_analog_mode.setChecked(default_display_mode == 'analog')
    tab.clock_analog_mode.setToolTip(
        "Render the main clock as an analogue clock face with hour/minute/second hands."
    )
    tab.clock_analog_mode.stateChanged.connect(tab._save_settings)
    tab.clock_analog_mode.stateChanged.connect(tab._update_stack_status)
    _clock_ctrl_layout.addWidget(tab.clock_analog_mode)

    # Analogue-only controls container
    tab._clock_analog_container = QWidget()
    _analog_layout = QVBoxLayout(tab._clock_analog_container)
    _analog_layout.setContentsMargins(0, 0, 0, 0)
    _analog_layout.setSpacing(4)

    tab.clock_analog_shadow = QCheckBox("Analogue Face Shadow")
    tab.clock_analog_shadow.setChecked(tab._default_bool('clock', 'analog_face_shadow', True))
    tab.clock_analog_shadow.setToolTip(
        "Enable a subtle drop shadow under the analogue clock face and hands."
    )
    tab.clock_analog_shadow.stateChanged.connect(tab._save_settings)
    _analog_layout.addWidget(tab.clock_analog_shadow)

    tab.clock_analog_shadow_intense = QCheckBox("Intense Analogue Shadows")
    tab.clock_analog_shadow_intense.setChecked(tab._default_bool('clock', 'analog_shadow_intense', False))
    tab.clock_analog_shadow_intense.setToolTip(
        "Doubles analogue shadow opacity and enlarges the drop shadow by ~50% for dramatic lighting."
    )
    tab.clock_analog_shadow_intense.stateChanged.connect(tab._save_settings)
    _analog_layout.addWidget(tab.clock_analog_shadow_intense)

    tab.clock_show_numerals = QCheckBox("Show Hour Numerals")
    tab.clock_show_numerals.setChecked(tab._default_bool('clock', 'show_numerals', True))
    tab.clock_show_numerals.stateChanged.connect(tab._save_settings)
    _analog_layout.addWidget(tab.clock_show_numerals)

    _clock_ctrl_layout.addWidget(tab._clock_analog_container)

    # Digital-only controls container
    tab._clock_digital_container = QWidget()
    _digital_layout = QVBoxLayout(tab._clock_digital_container)
    _digital_layout.setContentsMargins(0, 0, 0, 0)
    _digital_layout.setSpacing(4)

    tab.clock_digital_shadow_intense = QCheckBox("Intense Digital Shadows")
    tab.clock_digital_shadow_intense.setChecked(tab._default_bool('clock', 'digital_shadow_intense', False))
    tab.clock_digital_shadow_intense.setToolTip(
        "Doubles digital clock shadow blur, opacity, and offset for dramatic effect on large displays."
    )
    tab.clock_digital_shadow_intense.stateChanged.connect(tab._save_settings)
    _digital_layout.addWidget(tab.clock_digital_shadow_intense)

    _clock_ctrl_layout.addWidget(tab._clock_digital_container)

    tab.clock_analog_mode.stateChanged.connect(lambda: _update_clock_mode_visibility(tab))
    _update_clock_mode_visibility(tab)

    # Position
    position_row = QHBoxLayout()
    position_row.addWidget(QLabel("Position:"))
    tab.clock_position = QComboBox()
    tab.clock_position.addItems([
        "Top Left", "Top Center", "Top Right",
        "Middle Left", "Center", "Middle Right",
        "Bottom Left", "Bottom Center", "Bottom Right"
    ])
    tab.clock_position.currentTextChanged.connect(tab._save_settings)
    tab.clock_position.currentTextChanged.connect(tab._update_stack_status)
    position_row.addWidget(tab.clock_position)
    tab._set_combo_text(tab.clock_position, tab._default_str('clock', 'position', 'Top Right'))
    tab.clock_stack_status = QLabel("")
    tab.clock_stack_status.setMinimumWidth(100)
    position_row.addWidget(tab.clock_stack_status)
    position_row.addStretch()
    _clock_ctrl_layout.addLayout(position_row)

    # Display (monitor selection)
    clock_disp_row = QHBoxLayout()
    clock_disp_row.addWidget(QLabel("Display:"))
    tab.clock_monitor_combo = QComboBox()
    tab.clock_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.clock_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.clock_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    clock_disp_row.addWidget(tab.clock_monitor_combo)
    clock_monitor_default = tab._widget_default('clock', 'monitor', 'ALL')
    tab._set_combo_text(tab.clock_monitor_combo, str(clock_monitor_default))
    clock_disp_row.addStretch()
    _clock_ctrl_layout.addLayout(clock_disp_row)

    # Font family
    font_family_row = QHBoxLayout()
    font_family_row.addWidget(QLabel("Font:"))
    tab.clock_font_combo = QFontComboBox()
    default_clock_font = tab._default_str('clock', 'font_family', 'Segoe UI')
    tab.clock_font_combo.setCurrentFont(QFont(default_clock_font))
    tab.clock_font_combo.setMinimumWidth(220)
    tab.clock_font_combo.currentFontChanged.connect(tab._save_settings)
    font_family_row.addWidget(tab.clock_font_combo)
    font_family_row.addStretch()
    _clock_ctrl_layout.addLayout(font_family_row)

    # Font size
    font_row = QHBoxLayout()
    font_row.addWidget(QLabel("Font Size:"))
    tab.clock_font_size = QSpinBox()
    tab.clock_font_size.setRange(12, 144)
    tab.clock_font_size.setValue(tab._default_int('clock', 'font_size', 48))
    tab.clock_font_size.setAccelerated(True)
    tab.clock_font_size.valueChanged.connect(tab._save_settings)
    tab.clock_font_size.valueChanged.connect(tab._update_stack_status)
    font_row.addWidget(tab.clock_font_size)
    font_row.addWidget(QLabel("px"))
    font_row.addStretch()
    _clock_ctrl_layout.addLayout(font_row)

    # Text color
    color_row = QHBoxLayout()
    color_row.addWidget(QLabel("Text Color:"))
    tab.clock_color_btn = QPushButton("Choose Color...")
    tab.clock_color_btn.clicked.connect(tab._choose_clock_color)
    color_row.addWidget(tab.clock_color_btn)
    color_row.addStretch()
    _clock_ctrl_layout.addLayout(color_row)

    # Margin
    margin_row = QHBoxLayout()
    margin_row.addWidget(QLabel("Margin:"))
    tab.clock_margin = QSpinBox()
    tab.clock_margin.setRange(0, 100)
    tab.clock_margin.setValue(tab._default_int('clock', 'margin', 30))
    tab.clock_margin.setAccelerated(True)
    tab.clock_margin.valueChanged.connect(tab._save_settings)
    margin_row.addWidget(tab.clock_margin)
    margin_row.addWidget(QLabel("px"))
    margin_row.addStretch()
    _clock_ctrl_layout.addLayout(margin_row)

    # Background frame
    tab.clock_show_background = QCheckBox("Show Background Frame")
    tab.clock_show_background.setChecked(tab._default_bool('clock', 'show_background', True))
    tab.clock_show_background.stateChanged.connect(tab._save_settings)
    _clock_ctrl_layout.addWidget(tab.clock_show_background)

    # Background opacity
    opacity_row = QHBoxLayout()
    opacity_row.addWidget(QLabel("Background Opacity:"))
    tab.clock_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.clock_bg_opacity.setMinimum(0)
    tab.clock_bg_opacity.setMaximum(100)
    clock_bg_opacity_pct = int(tab._default_float('clock', 'bg_opacity', 0.6) * 100)
    tab.clock_bg_opacity.setValue(clock_bg_opacity_pct)
    tab.clock_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.clock_bg_opacity.setTickInterval(10)
    tab.clock_bg_opacity.valueChanged.connect(tab._save_settings)
    opacity_row.addWidget(tab.clock_bg_opacity)
    tab.clock_opacity_label = QLabel(f"{clock_bg_opacity_pct}%")
    tab.clock_bg_opacity.valueChanged.connect(lambda v: tab.clock_opacity_label.setText(f"{v}%"))
    opacity_row.addWidget(tab.clock_opacity_label)
    _clock_ctrl_layout.addLayout(opacity_row)

    # Background color
    clock_bg_color_row = QHBoxLayout()
    clock_bg_color_row.addWidget(QLabel("Background Color:"))
    tab.clock_bg_color_btn = QPushButton("Choose Color...")
    tab.clock_bg_color_btn.clicked.connect(tab._choose_clock_bg_color)
    clock_bg_color_row.addWidget(tab.clock_bg_color_btn)
    clock_bg_color_row.addStretch()
    _clock_ctrl_layout.addLayout(clock_bg_color_row)

    # Background border color
    clock_border_color_row = QHBoxLayout()
    clock_border_color_row.addWidget(QLabel("Border Color:"))
    tab.clock_border_color_btn = QPushButton("Choose Color...")
    tab.clock_border_color_btn.clicked.connect(tab._choose_clock_border_color)
    clock_border_color_row.addWidget(tab.clock_border_color_btn)
    clock_border_color_row.addStretch()
    _clock_ctrl_layout.addLayout(clock_border_color_row)

    # Background border opacity
    clock_border_opacity_row = QHBoxLayout()
    clock_border_opacity_row.addWidget(QLabel("Border Opacity:"))
    tab.clock_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.clock_border_opacity.setMinimum(0)
    tab.clock_border_opacity.setMaximum(100)
    clock_border_opacity_pct = int(tab._default_float('clock', 'border_opacity', 0.8) * 100)
    tab.clock_border_opacity.setValue(clock_border_opacity_pct)
    tab.clock_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.clock_border_opacity.setTickInterval(10)
    tab.clock_border_opacity.valueChanged.connect(tab._save_settings)
    clock_border_opacity_row.addWidget(tab.clock_border_opacity)
    tab.clock_border_opacity_label = QLabel(f"{clock_border_opacity_pct}%")
    tab.clock_border_opacity.valueChanged.connect(
        lambda v: tab.clock_border_opacity_label.setText(f"{v}%")
    )
    clock_border_opacity_row.addWidget(tab.clock_border_opacity_label)
    _clock_ctrl_layout.addLayout(clock_border_opacity_row)

    extra_label = QLabel("Additional clocks (optional, share style with main clock)")
    extra_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
    _clock_ctrl_layout.addWidget(extra_label)

    clock2_row = QHBoxLayout()
    tab.clock2_enabled = QCheckBox("Enable Clock 2")
    tab.clock2_enabled.stateChanged.connect(tab._save_settings)
    tab.clock2_enabled.stateChanged.connect(tab._update_stack_status)
    clock2_row.addWidget(tab.clock2_enabled)
    clock2_row.addWidget(QLabel("Display:"))
    tab.clock2_monitor_combo = QComboBox()
    tab.clock2_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.clock2_monitor_combo.currentTextChanged.connect(tab._save_settings)
    clock2_row.addWidget(tab.clock2_monitor_combo)
    clock2_row.addWidget(QLabel("Timezone:"))
    tab.clock2_timezone = QComboBox()
    tab.clock2_timezone.setMinimumWidth(160)
    tab._populate_timezones_for_combo(tab.clock2_timezone)
    tab.clock2_timezone.currentTextChanged.connect(tab._save_settings)
    clock2_row.addWidget(tab.clock2_timezone)
    clock2_row.addStretch()
    _clock_ctrl_layout.addLayout(clock2_row)

    clock3_row = QHBoxLayout()
    tab.clock3_enabled = QCheckBox("Enable Clock 3")
    tab.clock3_enabled.stateChanged.connect(tab._save_settings)
    tab.clock3_enabled.stateChanged.connect(tab._update_stack_status)
    clock3_row.addWidget(tab.clock3_enabled)
    clock3_row.addWidget(QLabel("Display:"))
    tab.clock3_monitor_combo = QComboBox()
    tab.clock3_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.clock3_monitor_combo.currentTextChanged.connect(tab._save_settings)
    clock3_row.addWidget(tab.clock3_monitor_combo)
    clock3_row.addWidget(QLabel("Timezone:"))
    tab.clock3_timezone = QComboBox()
    tab.clock3_timezone.setMinimumWidth(160)
    tab._populate_timezones_for_combo(tab.clock3_timezone)
    tab.clock3_timezone.currentTextChanged.connect(tab._save_settings)
    clock3_row.addWidget(tab.clock3_timezone)
    clock3_row.addStretch()
    _clock_ctrl_layout.addLayout(clock3_row)

    clock_layout.addWidget(tab._clock_controls_container)
    tab.clock_enabled.stateChanged.connect(lambda: _update_clock_enabled_visibility(tab))
    _update_clock_enabled_visibility(tab)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 10, 0, 0)
    container_layout.addWidget(clock_group)
    return container


def load_clock_settings(tab: WidgetsTab, widgets: dict) -> None:
    """Load clock settings from widgets config dict."""
    clock_config = widgets.get('clock', {})
    tab.clock_enabled.setChecked(tab._config_bool('clock', clock_config, 'enabled', True))

    format_raw = tab._config_str('clock', clock_config, 'format', '24h').lower()
    format_text = "12 Hour" if format_raw == '12h' else "24 Hour"
    index = tab.clock_format.findText(format_text)
    if index >= 0:
        tab.clock_format.setCurrentIndex(index)

    tab.clock_seconds.setChecked(tab._config_bool('clock', clock_config, 'show_seconds', True))

    timezone_str = tab._config_str('clock', clock_config, 'timezone', 'local')
    tz_index = tab.clock_timezone.findData(timezone_str)
    if tz_index >= 0:
        tab.clock_timezone.setCurrentIndex(tz_index)

    tab.clock_show_tz.setChecked(tab._config_bool('clock', clock_config, 'show_timezone', True))

    display_mode = tab._config_str('clock', clock_config, 'display_mode', 'analog').lower()
    tab.clock_analog_mode.setChecked(display_mode == 'analog')
    tab.clock_show_numerals.setChecked(tab._config_bool('clock', clock_config, 'show_numerals', True))
    tab.clock_analog_shadow.setChecked(tab._config_bool('clock', clock_config, 'analog_face_shadow', True))
    tab.clock_analog_shadow_intense.setChecked(
        tab._config_bool('clock', clock_config, 'analog_shadow_intense', False)
    )
    tab.clock_digital_shadow_intense.setChecked(
        tab._config_bool('clock', clock_config, 'digital_shadow_intense', False)
    )

    position = tab._config_str('clock', clock_config, 'position', 'Top Right')
    index = tab.clock_position.findText(position)
    if index >= 0:
        tab.clock_position.setCurrentIndex(index)

    tab.clock_font_combo.setCurrentFont(QFont(tab._config_str('clock', clock_config, 'font_family', 'Segoe UI')))
    tab.clock_font_size.setValue(tab._config_int('clock', clock_config, 'font_size', 48))
    tab.clock_margin.setValue(tab._config_int('clock', clock_config, 'margin', 30))
    tab.clock_show_background.setChecked(tab._config_bool('clock', clock_config, 'show_background', True))
    opacity_pct = int(tab._config_float('clock', clock_config, 'bg_opacity', 0.6) * 100)
    tab.clock_bg_opacity.setValue(opacity_pct)
    tab.clock_opacity_label.setText(f"{opacity_pct}%")

    monitor_sel = clock_config.get('monitor', tab._widget_default('clock', 'monitor', 'ALL'))
    mon_text = str(monitor_sel) if isinstance(monitor_sel, (int, str)) else 'ALL'
    idx = tab.clock_monitor_combo.findText(mon_text)
    if idx >= 0:
        tab.clock_monitor_combo.setCurrentIndex(idx)

    color_data = clock_config.get('color', tab._widget_default('clock', 'color', [255, 255, 255, 230]))
    tab._clock_color = QColor(*color_data)
    bg_color_data = clock_config.get('bg_color', tab._widget_default('clock', 'bg_color', [64, 64, 64, 255]))
    try:
        tab._clock_bg_color = QColor(*bg_color_data)
    except Exception:
        tab._clock_bg_color = QColor(64, 64, 64, 255)
    border_color_data = clock_config.get('border_color', tab._widget_default('clock', 'border_color', [128, 128, 128, 255]))
    try:
        tab._clock_border_color = QColor(*border_color_data)
    except Exception:
        tab._clock_border_color = QColor(128, 128, 128, 255)
    border_opacity_pct = int(clock_config.get('border_opacity', tab._default_float('clock', 'border_opacity', 0.8)) * 100)
    tab.clock_border_opacity.setValue(border_opacity_pct)
    tab.clock_border_opacity_label.setText(f"{border_opacity_pct}%")

    _update_clock_mode_visibility(tab)
    _update_clock_enabled_visibility(tab)

    # Clock 2
    clock2_config = widgets.get('clock2', {})
    tab.clock2_enabled.setChecked(clock2_config.get('enabled', False))
    monitor2 = clock2_config.get('monitor', 'ALL')
    mon2_text = str(monitor2) if isinstance(monitor2, (int, str)) else 'ALL'
    idx2 = tab.clock2_monitor_combo.findText(mon2_text)
    if idx2 >= 0:
        tab.clock2_monitor_combo.setCurrentIndex(idx2)
    timezone2 = clock2_config.get('timezone', 'UTC')
    tz2_index = tab.clock2_timezone.findData(timezone2)
    if tz2_index >= 0:
        tab.clock2_timezone.setCurrentIndex(tz2_index)

    # Clock 3
    clock3_config = widgets.get('clock3', {})
    tab.clock3_enabled.setChecked(clock3_config.get('enabled', False))
    monitor3 = clock3_config.get('monitor', 'ALL')
    mon3_text = str(monitor3) if isinstance(monitor3, (int, str)) else 'ALL'
    idx3 = tab.clock3_monitor_combo.findText(mon3_text)
    if idx3 >= 0:
        tab.clock3_monitor_combo.setCurrentIndex(idx3)
    timezone3 = clock3_config.get('timezone', 'UTC+01:00')
    tz3_index = tab.clock3_timezone.findData(timezone3)
    if tz3_index >= 0:
        tab.clock3_timezone.setCurrentIndex(tz3_index)


def save_clock_settings(tab: WidgetsTab) -> tuple[dict, dict, dict]:
    """Return (clock_config, clock2_config, clock3_config) from current UI state."""
    tz_data = tab.clock_timezone.currentData()
    timezone_str = tz_data if tz_data else 'local'

    format_text = ""
    try:
        format_text = (tab.clock_format.currentText() or "").strip().lower()
    except Exception:
        format_text = ""
    clock_format_value = '12h' if format_text.startswith('12') else '24h'

    clock_config = {
        'enabled': tab.clock_enabled.isChecked(),
        'format': clock_format_value,
        'show_seconds': tab.clock_seconds.isChecked(),
        'timezone': timezone_str,
        'show_timezone': tab.clock_show_tz.isChecked(),
        'position': tab.clock_position.currentText(),
        'font_family': tab.clock_font_combo.currentFont().family(),
        'font_size': tab.clock_font_size.value(),
        'margin': tab.clock_margin.value(),
        'show_background': tab.clock_show_background.isChecked(),
        'bg_opacity': tab.clock_bg_opacity.value() / 100.0,
        'bg_color': [tab._clock_bg_color.red(), tab._clock_bg_color.green(),
                    tab._clock_bg_color.blue(), tab._clock_bg_color.alpha()],
        'color': [tab._clock_color.red(), tab._clock_color.green(),
                 tab._clock_color.blue(), tab._clock_color.alpha()],
        'border_color': [tab._clock_border_color.red(), tab._clock_border_color.green(),
                         tab._clock_border_color.blue(), tab._clock_border_color.alpha()],
        'border_opacity': tab.clock_border_opacity.value() / 100.0,
        'display_mode': 'analog' if tab.clock_analog_mode.isChecked() else 'digital',
        'show_numerals': tab.clock_show_numerals.isChecked(),
        'analog_face_shadow': tab.clock_analog_shadow.isChecked(),
        'analog_shadow_intense': tab.clock_analog_shadow_intense.isChecked(),
        'digital_shadow_intense': tab.clock_digital_shadow_intense.isChecked(),
    }
    cmon_text = tab.clock_monitor_combo.currentText()
    clock_config['monitor'] = cmon_text if cmon_text == 'ALL' else int(cmon_text)

    clock2_tz_data = tab.clock2_timezone.currentData()
    clock2_timezone = clock2_tz_data if clock2_tz_data else 'UTC'
    clock2_config = {
        'enabled': tab.clock2_enabled.isChecked(),
        'timezone': clock2_timezone,
    }
    c2mon_text = tab.clock2_monitor_combo.currentText()
    clock2_config['monitor'] = c2mon_text if c2mon_text == 'ALL' else int(c2mon_text)

    clock3_tz_data = tab.clock3_timezone.currentData()
    clock3_timezone = clock3_tz_data if clock3_tz_data else 'UTC+01:00'
    clock3_config = {
        'enabled': tab.clock3_enabled.isChecked(),
        'timezone': clock3_timezone,
    }
    c3mon_text = tab.clock3_monitor_combo.currentText()
    clock3_config['monitor'] = c3mon_text if c3mon_text == 'ALL' else int(c3mon_text)

    return clock_config, clock2_config, clock3_config
