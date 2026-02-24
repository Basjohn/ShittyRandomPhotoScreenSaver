"""Weather widget section for widgets tab.

Extracted from widgets_tab.py to reduce monolith size.
Contains UI building, settings loading/saving for Weather widget.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QLineEdit,
    QSlider, QFontComboBox, QWidget, QCompleter,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.logging.logger import get_logger
from widgets.timezone_utils import get_local_timezone
from ui.styled_popup import ColorSwatchButton

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab

logger = get_logger(__name__)


def _update_weather_enabled_visibility(tab: WidgetsTab) -> None:
    """Show/hide all weather controls based on weather_enabled checkbox."""
    enabled = getattr(tab, 'weather_enabled', None) and tab.weather_enabled.isChecked()
    container = getattr(tab, '_weather_controls_container', None)
    if container is not None:
        container.setVisible(bool(enabled))


def _update_weather_icon_visibility(tab: WidgetsTab) -> None:
    """Show/hide icon alignment/size controls based on show_icon checkbox."""
    show = getattr(tab, 'weather_show_icon', None) and tab.weather_show_icon.isChecked()
    container = getattr(tab, '_weather_icon_container', None)
    if container is not None:
        container.setVisible(bool(show))


def _sync_weather_swatch(tab: WidgetsTab, btn_attr: str, color_attr: str) -> None:
    btn = getattr(tab, btn_attr, None)
    color = getattr(tab, color_attr, None)
    if btn is None or color is None or not hasattr(btn, "set_color"):
        return
    try:
        btn.set_color(color)
    except Exception:  # pragma: no cover
        logger.debug(
            "[WEATHER_TAB] Failed to sync %s with %s", btn_attr, color_attr, exc_info=True
        )


def _update_weather_bg_visibility(tab: WidgetsTab) -> None:
    """Show/hide background styling controls based on show_background checkbox."""
    show = getattr(tab, 'weather_show_background', None) and tab.weather_show_background.isChecked()
    container = getattr(tab, '_weather_bg_container', None)
    if container is not None:
        container.setVisible(bool(show))


def build_weather_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build weather section UI and attach widgets to tab instance.

    Returns the weather container widget.
    """
    from ui.tabs.widgets_tab import NoWheelSlider

    LABEL_WIDTH = 140

    def _aligned_row(parent: QVBoxLayout, label_text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        label = QLabel(label_text)
        label.setFixedWidth(LABEL_WIDTH)
        row.addWidget(label)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(6)
        row.addLayout(content, 1)
        parent.addLayout(row)
        return content

    weather_group = QGroupBox("Weather Widget")
    weather_layout = QVBoxLayout(weather_group)

    # Enable weather
    tab.weather_enabled = QCheckBox("Enable Weather Widget")
    tab.weather_enabled.setChecked(tab._default_bool('weather', 'enabled', True))
    tab.weather_enabled.stateChanged.connect(tab._save_settings)
    tab.weather_enabled.stateChanged.connect(tab._update_stack_status)
    weather_layout.addWidget(tab.weather_enabled)

    # Container for all weather controls gated by enable checkbox
    tab._weather_controls_container = QWidget()
    _weather_ctrl_layout = QVBoxLayout(tab._weather_controls_container)
    _weather_ctrl_layout.setContentsMargins(0, 0, 0, 0)
    _weather_ctrl_layout.setSpacing(4)

    # Info label
    info_label = QLabel("\u2713 Uses Open-Meteo API (free, no API key required)")
    info_label.setStyleSheet("color: #4CAF50; font-size: 11px;")
    _weather_ctrl_layout.addWidget(info_label)

    # Location with autocomplete
    location_row = _aligned_row(_weather_ctrl_layout, "Location:")
    tab.weather_location = QLineEdit()
    default_city = tab._default_str('weather', 'location', '')
    tab.weather_location.setText(default_city)
    tab.weather_location.setPlaceholderText("City name...")
    tab.weather_location.textChanged.connect(tab._save_settings)

    common_cities = [
        "London", "New York", "Tokyo", "Paris", "Berlin", "Sydney", "Toronto",
        "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
        "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
        "Fort Worth", "Columbus", "Charlotte", "San Francisco", "Indianapolis",
        "Seattle", "Denver", "Washington", "Boston", "El Paso", "Nashville",
        "Detroit", "Portland", "Las Vegas", "Memphis", "Louisville", "Baltimore",
        "Milwaukee", "Albuquerque", "Tucson", "Fresno", "Mesa", "Sacramento",
        "Atlanta", "Kansas City", "Colorado Springs", "Omaha", "Raleigh", "Miami",
        "Long Beach", "Virginia Beach", "Oakland", "Minneapolis", "Tulsa",
        "Arlington", "Tampa", "New Orleans", "Wichita", "Cleveland", "Bakersfield",
        "Munich", "Madrid", "Rome", "Amsterdam", "Barcelona", "Vienna",
        "Hamburg", "Warsaw", "Budapest", "Prague", "Copenhagen", "Stockholm",
        "Brussels", "Dublin", "Lisbon", "Athens", "Helsinki", "Oslo",
        "Shanghai", "Beijing", "Hong Kong", "Singapore", "Seoul", "Bangkok",
        "Mumbai", "Delhi", "Bangalore", "Chennai", "Kolkata", "Hyderabad",
        "Melbourne", "Brisbane", "Perth", "Auckland", "Wellington",
        "Cape Town", "Johannesburg", "Durban", "Cairo", "Lagos", "Nairobi",
        "Buenos Aires", "Rio de Janeiro", "S\u00e3o Paulo", "Lima", "Bogot\u00e1",
        "Santiago", "Mexico City", "Guadalajara", "Monterrey", "Havana",
        "Tel Aviv", "Jerusalem", "Dubai", "Abu Dhabi", "Doha", "Istanbul",
        "Moscow", "St Petersburg", "Kyiv", "Minsk", "Bucharest", "Sofia"
    ]
    completer = QCompleter(sorted(common_cities))
    completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
    tab.weather_location.setCompleter(completer)

    location_row.addWidget(tab.weather_location)
    location_row.addStretch()

    # Position
    weather_pos_row = _aligned_row(_weather_ctrl_layout, "Position:")
    tab.weather_position = QComboBox()
    tab.weather_position.addItems([
        "Top Left", "Top Center", "Top Right",
        "Middle Left", "Center", "Middle Right",
        "Bottom Left", "Bottom Center", "Bottom Right"
    ])
    tab.weather_position.currentTextChanged.connect(tab._save_settings)
    tab.weather_position.currentTextChanged.connect(tab._update_stack_status)
    tab.weather_position.setMinimumWidth(150)
    weather_pos_row.addWidget(tab.weather_position)
    tab._set_combo_text(tab.weather_position, tab._default_str('weather', 'position', 'Top Left'))
    tab.weather_stack_status = QLabel("")
    tab.weather_stack_status.setMinimumWidth(100)
    weather_pos_row.addWidget(tab.weather_stack_status)
    weather_pos_row.addStretch()

    # Display (monitor selection)
    weather_disp_row = _aligned_row(_weather_ctrl_layout, "Display:")
    tab.weather_monitor_combo = QComboBox()
    tab.weather_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.weather_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.weather_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    tab.weather_monitor_combo.setMinimumWidth(120)
    weather_disp_row.addWidget(tab.weather_monitor_combo)
    monitor_default = tab._widget_default('weather', 'monitor', 'ALL')
    tab._set_combo_text(tab.weather_monitor_combo, str(monitor_default))
    weather_disp_row.addStretch()

    # Font family
    weather_font_family_row = _aligned_row(_weather_ctrl_layout, "Font:")
    tab.weather_font_combo = QFontComboBox()
    default_weather_font = tab._default_str('weather', 'font_family', 'Segoe UI')
    tab.weather_font_combo.setCurrentFont(QFont(default_weather_font))
    tab.weather_font_combo.setMinimumWidth(220)
    tab.weather_font_combo.currentFontChanged.connect(tab._save_settings)
    weather_font_family_row.addWidget(tab.weather_font_combo)
    weather_font_family_row.addStretch()

    # Font size
    weather_font_row = _aligned_row(_weather_ctrl_layout, "Font Size:")
    tab.weather_font_size = QSpinBox()
    tab.weather_font_size.setRange(12, 72)
    tab.weather_font_size.setValue(tab._default_int('weather', 'font_size', 24))
    tab.weather_font_size.setAccelerated(True)
    tab.weather_font_size.valueChanged.connect(tab._save_settings)
    tab.weather_font_size.valueChanged.connect(tab._update_stack_status)
    weather_font_row.addWidget(tab.weather_font_size)
    font_px = QLabel("px")
    font_px.setMinimumWidth(24)
    weather_font_row.addWidget(font_px)
    weather_font_row.addStretch()

    # Text color
    weather_color_row = _aligned_row(_weather_ctrl_layout, "Text Color:")
    tab.weather_color_btn = ColorSwatchButton(title="Choose Weather Text Color")
    tab.weather_color_btn.set_color(tab._weather_color)
    tab.weather_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_weather_color', c), tab._save_settings())
    )
    weather_color_row.addWidget(tab.weather_color_btn)
    weather_color_row.addStretch()

    # Show forecast line
    tab.weather_show_forecast = QCheckBox("Show Forecast Line")
    tab.weather_show_forecast.setChecked(tab._default_bool('weather', 'show_forecast', True))
    tab.weather_show_forecast.setToolTip("Display tomorrow's forecast below current weather")
    tab.weather_show_forecast.stateChanged.connect(tab._save_settings)
    tab.weather_show_forecast.stateChanged.connect(tab._update_stack_status)
    _weather_ctrl_layout.addWidget(tab.weather_show_forecast)

    # Show details row
    tab.weather_show_details = QCheckBox("Show Details (Rain/Humidity/Wind)")
    tab.weather_show_details.setChecked(tab._default_bool('weather', 'show_details_row', True))
    tab.weather_show_details.setToolTip("Display weather detail metrics with icons")
    tab.weather_show_details.stateChanged.connect(tab._save_settings)
    _weather_ctrl_layout.addWidget(tab.weather_show_details)

    # Show condition icon
    tab.weather_show_icon = QCheckBox("Show Weather Icon")
    tab.weather_show_icon.setChecked(tab._default_bool('weather', 'show_condition_icon', True))
    tab.weather_show_icon.setToolTip("Display weather condition icon (clear, cloudy, rain, etc.)")
    tab.weather_show_icon.stateChanged.connect(tab._save_settings)
    _weather_ctrl_layout.addWidget(tab.weather_show_icon)

    # Icon sub-controls container (shown only when show_icon is checked)
    tab._weather_icon_container = QWidget()
    _icon_layout = QVBoxLayout(tab._weather_icon_container)
    _icon_layout.setContentsMargins(0, 0, 0, 0)
    _icon_layout.setSpacing(4)

    icon_align_row = _aligned_row(_icon_layout, "Icon Position:")
    tab.weather_icon_alignment = QComboBox()
    tab.weather_icon_alignment.addItems(["LEFT", "RIGHT"])
    tab._set_combo_text(tab.weather_icon_alignment, tab._default_str('weather', 'icon_alignment', 'RIGHT'))
    tab.weather_icon_alignment.currentTextChanged.connect(tab._save_settings)
    tab.weather_icon_alignment.setMinimumWidth(120)
    icon_align_row.addWidget(tab.weather_icon_alignment)
    icon_align_row.addStretch()

    icon_size_row = _aligned_row(_icon_layout, "Icon Size:")
    tab.weather_icon_size = QSpinBox()
    tab.weather_icon_size.setRange(32, 192)
    tab.weather_icon_size.setValue(tab._default_int('weather', 'icon_size', 96))
    tab.weather_icon_size.setSuffix(" px")
    tab.weather_icon_size.valueChanged.connect(tab._save_settings)
    icon_size_row.addWidget(tab.weather_icon_size)
    icon_size_row.addStretch()

    _weather_ctrl_layout.addWidget(tab._weather_icon_container)
    tab.weather_show_icon.stateChanged.connect(lambda: _update_weather_icon_visibility(tab))
    _update_weather_icon_visibility(tab)

    # Intense shadow
    tab.weather_intense_shadow = QCheckBox("Intense Shadows")
    tab.weather_intense_shadow.setChecked(tab._default_bool('weather', 'intense_shadow', True))
    tab.weather_intense_shadow.setToolTip(
        "Doubles shadow blur, opacity, and offset for dramatic effect on large displays."
    )
    tab.weather_intense_shadow.stateChanged.connect(tab._save_settings)
    _weather_ctrl_layout.addWidget(tab.weather_intense_shadow)

    # Background frame
    tab.weather_show_background = QCheckBox("Show Background Frame")
    tab.weather_show_background.setChecked(tab._default_bool('weather', 'show_background', True))
    tab.weather_show_background.stateChanged.connect(tab._save_settings)
    _weather_ctrl_layout.addWidget(tab.weather_show_background)

    # Background sub-controls container (shown only when show_background is checked)
    tab._weather_bg_container = QWidget()
    _bg_layout = QVBoxLayout(tab._weather_bg_container)
    _bg_layout.setContentsMargins(0, 0, 0, 0)
    _bg_layout.setSpacing(4)

    weather_opacity_row = _aligned_row(_bg_layout, "Background Opacity:")
    tab.weather_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.weather_bg_opacity.setMinimum(0)
    tab.weather_bg_opacity.setMaximum(100)
    weather_bg_opacity_pct = int(tab._default_float('weather', 'bg_opacity', 0.6) * 100)
    tab.weather_bg_opacity.setValue(weather_bg_opacity_pct)
    tab.weather_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.weather_bg_opacity.setTickInterval(10)
    tab.weather_bg_opacity.valueChanged.connect(tab._save_settings)
    weather_opacity_row.addWidget(tab.weather_bg_opacity)
    tab.weather_opacity_label = QLabel(f"{weather_bg_opacity_pct}%")
    tab.weather_bg_opacity.valueChanged.connect(lambda v: tab.weather_opacity_label.setText(f"{v}%"))
    tab.weather_opacity_label.setMinimumWidth(50)
    weather_opacity_row.addWidget(tab.weather_opacity_label)

    weather_bg_color_row = _aligned_row(_bg_layout, "Background Color:")
    tab.weather_bg_color_btn = ColorSwatchButton(title="Choose Weather Background Color")
    tab.weather_bg_color_btn.set_color(tab._weather_bg_color)
    tab.weather_bg_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_weather_bg_color', c), tab._save_settings())
    )
    weather_bg_color_row.addWidget(tab.weather_bg_color_btn)
    weather_bg_color_row.addStretch()

    weather_border_color_row = _aligned_row(_bg_layout, "Border Color:")
    tab.weather_border_color_btn = ColorSwatchButton(title="Choose Weather Border Color")
    tab.weather_border_color_btn.set_color(tab._weather_border_color)
    tab.weather_border_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_weather_border_color', c), tab._save_settings())
    )
    weather_border_color_row.addWidget(tab.weather_border_color_btn)
    weather_border_color_row.addStretch()

    weather_border_opacity_row = _aligned_row(_bg_layout, "Border Opacity:")
    tab.weather_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.weather_border_opacity.setMinimum(0)
    tab.weather_border_opacity.setMaximum(100)
    weather_border_opacity_pct = int(tab._default_float('weather', 'border_opacity', 1.0) * 100)
    tab.weather_border_opacity.setValue(weather_border_opacity_pct)
    tab.weather_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.weather_border_opacity.setTickInterval(10)
    tab.weather_border_opacity.valueChanged.connect(tab._save_settings)
    weather_border_opacity_row.addWidget(tab.weather_border_opacity)
    tab.weather_border_opacity_label = QLabel(f"{weather_border_opacity_pct}%")
    tab.weather_border_opacity.valueChanged.connect(
        lambda v: tab.weather_border_opacity_label.setText(f"{v}%")
    )
    tab.weather_border_opacity_label.setMinimumWidth(50)
    weather_border_opacity_row.addWidget(tab.weather_border_opacity_label)

    _weather_ctrl_layout.addWidget(tab._weather_bg_container)
    tab.weather_show_background.stateChanged.connect(lambda: _update_weather_bg_visibility(tab))
    _update_weather_bg_visibility(tab)

    # Margin
    weather_margin_row = _aligned_row(_weather_ctrl_layout, "Margin:")
    tab.weather_margin = QSpinBox()
    tab.weather_margin.setRange(0, 200)
    tab.weather_margin.setValue(tab._default_int('weather', 'margin', 30))
    tab.weather_margin.setSuffix(" px")
    tab.weather_margin.setToolTip("Distance from screen edge in pixels")
    tab.weather_margin.valueChanged.connect(tab._save_settings)
    weather_margin_row.addWidget(tab.weather_margin)
    weather_margin_row.addStretch()

    weather_layout.addWidget(tab._weather_controls_container)
    tab.weather_enabled.stateChanged.connect(lambda: _update_weather_enabled_visibility(tab))
    _update_weather_enabled_visibility(tab)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 10, 0, 0)
    container_layout.addWidget(weather_group)
    return container


def load_weather_settings(tab: WidgetsTab, widgets: dict) -> None:
    """Load weather settings from widgets config dict."""
    weather_config = widgets.get('weather', {})

    # Auto-derive location from timezone if still default
    try:
        raw_loc = str(weather_config.get('location', 'New York') or 'New York')
        if raw_loc == 'New York':
            tz = get_local_timezone()
            derived_city = None
            if isinstance(tz, str) and '/' in tz:
                candidate = tz.split('/')[-1].strip().replace('_', ' ')
                if candidate and candidate.lower() not in {"local", "utc"}:
                    derived_city = candidate
            if derived_city:
                weather_config['location'] = derived_city
                widgets['weather'] = weather_config
                tab._settings.set('widgets', widgets)
                tab._settings.save()
    except Exception:
        logger.debug("Failed to auto-derive weather location from timezone", exc_info=True)

    tab.weather_enabled.setChecked(tab._config_bool('weather', weather_config, 'enabled', True))
    tab.weather_location.setText(tab._config_str('weather', weather_config, 'location', ''))

    weather_pos = tab._config_str('weather', weather_config, 'position', 'Top Left')
    index = tab.weather_position.findText(weather_pos)
    if index >= 0:
        tab.weather_position.setCurrentIndex(index)

    tab.weather_font_combo.setCurrentFont(QFont(tab._config_str('weather', weather_config, 'font_family', 'Segoe UI')))
    tab.weather_font_size.setValue(tab._config_int('weather', weather_config, 'font_size', 24))
    tab.weather_show_forecast.setChecked(tab._config_bool('weather', weather_config, 'show_forecast', True))
    tab.weather_show_details.setChecked(tab._config_bool('weather', weather_config, 'show_details_row', True))
    tab.weather_show_icon.setChecked(tab._config_bool('weather', weather_config, 'show_condition_icon', True))
    tab._set_combo_text(tab.weather_icon_alignment, tab._config_str('weather', weather_config, 'icon_alignment', 'RIGHT'))
    tab.weather_icon_size.setValue(tab._config_int('weather', weather_config, 'icon_size', 96))
    tab.weather_intense_shadow.setChecked(
        tab._config_bool('weather', weather_config, 'intense_shadow', True)
    )
    tab.weather_show_background.setChecked(tab._config_bool('weather', weather_config, 'show_background', True))
    weather_opacity_pct = int(tab._config_float('weather', weather_config, 'bg_opacity', 0.6) * 100)
    tab.weather_bg_opacity.setValue(weather_opacity_pct)
    tab.weather_opacity_label.setText(f"{weather_opacity_pct}%")

    weather_color_data = weather_config.get('color', tab._widget_default('weather', 'color', [255, 255, 255, 230]))
    tab._weather_color = QColor(*weather_color_data)
    weather_bg_color_data = weather_config.get('bg_color', tab._widget_default('weather', 'bg_color', [35, 35, 35, 255]))
    try:
        tab._weather_bg_color = QColor(*weather_bg_color_data)
    except Exception:
        tab._weather_bg_color = QColor(35, 35, 35, 255)
    weather_border_color_data = weather_config.get('border_color', tab._widget_default('weather', 'border_color', [255, 255, 255, 255]))
    try:
        tab._weather_border_color = QColor(*weather_border_color_data)
    except Exception:
        tab._weather_border_color = QColor(255, 255, 255, 255)
    _sync_weather_swatch(tab, 'weather_color_btn', '_weather_color')
    _sync_weather_swatch(tab, 'weather_bg_color_btn', '_weather_bg_color')
    _sync_weather_swatch(tab, 'weather_border_color_btn', '_weather_border_color')
    weather_border_opacity_pct = int(tab._config_float('weather', weather_config, 'border_opacity', 1.0) * 100)
    tab.weather_border_opacity.setValue(weather_border_opacity_pct)
    tab.weather_border_opacity_label.setText(f"{weather_border_opacity_pct}%")

    wmon_sel = weather_config.get('monitor', tab._widget_default('weather', 'monitor', 'ALL'))
    wmon_text = str(wmon_sel) if isinstance(wmon_sel, (int, str)) else 'ALL'
    wmon_idx = tab.weather_monitor_combo.findText(wmon_text)
    if wmon_idx >= 0:
        tab.weather_monitor_combo.setCurrentIndex(wmon_idx)

    _update_weather_icon_visibility(tab)
    _update_weather_bg_visibility(tab)
    _update_weather_enabled_visibility(tab)


def save_weather_settings(tab: WidgetsTab) -> dict:
    """Return weather config dict from current UI state."""
    weather_config = {
        'enabled': tab.weather_enabled.isChecked(),
        'location': tab.weather_location.text(),
        'position': tab.weather_position.currentText(),
        'font_family': tab.weather_font_combo.currentFont().family(),
        'font_size': tab.weather_font_size.value(),
        'margin': tab.weather_margin.value(),
        'show_forecast': tab.weather_show_forecast.isChecked(),
        'show_details_row': tab.weather_show_details.isChecked(),
        'show_condition_icon': tab.weather_show_icon.isChecked(),
        'icon_alignment': tab.weather_icon_alignment.currentText(),
        'icon_size': tab.weather_icon_size.value(),
        'intense_shadow': tab.weather_intense_shadow.isChecked(),
        'show_background': tab.weather_show_background.isChecked(),
        'bg_opacity': tab.weather_bg_opacity.value() / 100.0,
        'color': [tab._weather_color.red(), tab._weather_color.green(),
                 tab._weather_color.blue(), tab._weather_color.alpha()],
        'bg_color': [tab._weather_bg_color.red(), tab._weather_bg_color.green(),
                    tab._weather_bg_color.blue(), tab._weather_bg_color.alpha()],
        'border_color': [tab._weather_border_color.red(), tab._weather_border_color.green(),
                         tab._weather_border_color.blue(), tab._weather_border_color.alpha()],
        'border_opacity': tab.weather_border_opacity.value() / 100.0,
    }
    wmon_text = tab.weather_monitor_combo.currentText()
    weather_config['monitor'] = wmon_text if wmon_text == 'ALL' else int(wmon_text)
    return weather_config
