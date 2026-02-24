"""Reddit widget section for widgets tab.

Extracted from widgets_tab.py to reduce monolith size.
Contains UI building, settings loading/saving for Reddit 1 and Reddit 2.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QGroupBox, QCheckBox, QLineEdit,
    QSlider, QFontComboBox, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.logging.logger import get_logger
from ui.styled_popup import ColorSwatchButton

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab

logger = get_logger(__name__)


def _update_reddit_enabled_visibility(tab: WidgetsTab) -> None:
    """Show/hide all Reddit controls based on reddit_enabled checkbox."""
    enabled = getattr(tab, 'reddit_enabled', None) and tab.reddit_enabled.isChecked()
    container = getattr(tab, '_reddit_controls_container', None)
    if container is not None:
        container.setVisible(bool(enabled))


def build_reddit_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build reddit section UI and attach widgets to tab instance.

    Returns the reddit container widget.
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

    reddit_group = QGroupBox("Reddit Widget")
    reddit_layout = QVBoxLayout(reddit_group)

    tab.reddit_enabled = QCheckBox("Enable Reddit Widget")
    tab.reddit_enabled.setToolTip(
        "Shows a small list of posts from a subreddit using Reddit's public JSON feed."
    )
    tab.reddit_enabled.setChecked(tab._default_bool('reddit', 'enabled', True))
    tab.reddit_enabled.stateChanged.connect(tab._save_settings)
    tab.reddit_enabled.stateChanged.connect(tab._update_stack_status)
    reddit_layout.addWidget(tab.reddit_enabled)

    # All controls below are wrapped in a container gated by reddit_enabled
    tab._reddit_controls_container = QWidget()
    _rc_layout = QVBoxLayout(tab._reddit_controls_container)
    _rc_layout.setContentsMargins(0, 0, 0, 0)
    _rc_layout.setSpacing(4)

    reddit_info = QLabel(
        "Links open in your browser and only respond while Ctrl-held or hard-exit "
        "interaction modes are active."
    )
    reddit_info.setWordWrap(True)
    reddit_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
    _rc_layout.addWidget(reddit_info)

    tab.reddit_exit_on_click = QCheckBox("Exit screensaver when Reddit links are opened")
    tab.reddit_exit_on_click.setToolTip(
        "When enabled, clicking a Reddit link will exit the screensaver and open the link in your browser."
    )
    tab.reddit_exit_on_click.setChecked(tab._default_bool('reddit', 'exit_on_click', True))
    tab.reddit_exit_on_click.stateChanged.connect(tab._save_settings)
    _rc_layout.addWidget(tab.reddit_exit_on_click)

    # Subreddit name
    reddit_sub_row = _aligned_row(_rc_layout, "Subreddit:")
    tab.reddit_subreddit = QLineEdit()
    default_subreddit = tab._default_str('reddit', 'subreddit', 'wallpapers')
    tab.reddit_subreddit.setText(default_subreddit)
    tab.reddit_subreddit.setPlaceholderText("e.g. wallpapers")
    tab.reddit_subreddit.setToolTip("Enter the subreddit name (without r/ prefix)")
    tab.reddit_subreddit.textChanged.connect(tab._save_settings)
    reddit_sub_row.addWidget(tab.reddit_subreddit)
    reddit_sub_row.addStretch()

    # Item count
    reddit_items_row = _aligned_row(_rc_layout, "Items:")
    tab.reddit_items = QComboBox()
    tab.reddit_items.addItems(["4", "10", "20"])
    tab.reddit_items.setToolTip("Number of Reddit posts to display in the widget")
    tab.reddit_items.currentTextChanged.connect(tab._save_settings)
    tab.reddit_items.currentTextChanged.connect(tab._update_stack_status)
    tab.reddit_items.setMinimumWidth(80)
    reddit_items_row.addWidget(tab.reddit_items)
    reddit_limit_default = tab._default_int('reddit', 'limit', 10)
    if reddit_limit_default <= 5:
        default_items_text = "4"
    elif reddit_limit_default >= 20:
        default_items_text = "20"
    else:
        default_items_text = "10"
    tab._set_combo_text(tab.reddit_items, default_items_text)
    reddit_items_row.addStretch()
    _rc_layout.addLayout(reddit_items_row)

    # Position
    reddit_pos_row = _aligned_row(_rc_layout, "Position:")
    tab.reddit_position = QComboBox()
    tab.reddit_position.addItems([
        "Top Left", "Top Center", "Top Right",
        "Middle Left", "Center", "Middle Right",
        "Bottom Left", "Bottom Center", "Bottom Right",
    ])
    tab.reddit_position.setToolTip("Screen position for the Reddit widget (9-grid layout)")
    tab.reddit_position.currentTextChanged.connect(tab._save_settings)
    tab.reddit_position.currentTextChanged.connect(tab._update_stack_status)
    tab.reddit_position.setMinimumWidth(150)
    reddit_pos_row.addWidget(tab.reddit_position)
    tab._set_combo_text(tab.reddit_position, tab._default_str('reddit', 'position', 'Bottom Right'))
    tab.reddit_stack_status = QLabel("")
    tab.reddit_stack_status.setMinimumWidth(100)
    reddit_pos_row.addWidget(tab.reddit_stack_status)
    reddit_pos_row.addStretch()
    _rc_layout.addLayout(reddit_pos_row)

    # Display (monitor selection)
    reddit_disp_row = _aligned_row(_rc_layout, "Display:")
    tab.reddit_monitor_combo = QComboBox()
    tab.reddit_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.reddit_monitor_combo.setToolTip("Which monitor(s) to show the Reddit widget on")
    tab.reddit_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.reddit_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    tab.reddit_monitor_combo.setMinimumWidth(120)
    reddit_disp_row.addWidget(tab.reddit_monitor_combo)
    reddit_monitor_default = tab._widget_default('reddit', 'monitor', 'ALL')
    tab._set_combo_text(tab.reddit_monitor_combo, str(reddit_monitor_default))
    reddit_disp_row.addStretch()
    _rc_layout.addLayout(reddit_disp_row)

    # Font family
    reddit_font_family_row = _aligned_row(_rc_layout, "Font:")
    tab.reddit_font_combo = QFontComboBox()
    default_reddit_font = tab._default_str('reddit', 'font_family', 'Segoe UI')
    tab.reddit_font_combo.setCurrentFont(QFont(default_reddit_font))
    tab.reddit_font_combo.setMinimumWidth(220)
    tab.reddit_font_combo.setToolTip("Font family for Reddit post titles")
    tab.reddit_font_combo.currentFontChanged.connect(tab._save_settings)
    reddit_font_family_row.addWidget(tab.reddit_font_combo)
    reddit_font_family_row.addStretch()

    # Font size
    reddit_font_row = _aligned_row(_rc_layout, "Font Size:")
    tab.reddit_font_size = QSpinBox()
    tab.reddit_font_size.setRange(10, 72)
    tab.reddit_font_size.setValue(tab._default_int('reddit', 'font_size', 18))
    tab.reddit_font_size.setAccelerated(True)
    tab.reddit_font_size.setToolTip("Font size for Reddit post titles (10-72px)")
    tab.reddit_font_size.valueChanged.connect(tab._save_settings)
    tab.reddit_font_size.valueChanged.connect(tab._update_stack_status)
    reddit_font_row.addWidget(tab.reddit_font_size)
    reddit_font_px = QLabel("px")
    reddit_font_px.setMinimumWidth(24)
    reddit_font_row.addWidget(reddit_font_px)
    reddit_font_row.addStretch()

    # Margin
    reddit_margin_row = _aligned_row(_rc_layout, "Margin:")
    tab.reddit_margin = QSpinBox()
    tab.reddit_margin.setRange(0, 100)
    tab.reddit_margin.setValue(tab._default_int('reddit', 'margin', 30))
    tab.reddit_margin.setAccelerated(True)
    tab.reddit_margin.valueChanged.connect(tab._save_settings)
    reddit_margin_row.addWidget(tab.reddit_margin)
    reddit_margin_px = QLabel("px")
    reddit_margin_px.setMinimumWidth(24)
    reddit_margin_row.addWidget(reddit_margin_px)
    reddit_margin_row.addStretch()

    # Text color
    reddit_color_row = _aligned_row(_rc_layout, "Text Color:")
    tab.reddit_color_btn = ColorSwatchButton(title="Choose Reddit Text Color")
    tab.reddit_color_btn.set_color(tab._reddit_color)
    tab.reddit_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_reddit_color', c), tab._save_settings())
    )
    reddit_color_row.addWidget(tab.reddit_color_btn)
    reddit_color_row.addStretch()

    # Background frame
    tab.reddit_show_background = QCheckBox("Show Background Frame")
    tab.reddit_show_background.setChecked(tab._default_bool('reddit', 'show_background', True))
    tab.reddit_show_background.stateChanged.connect(tab._save_settings)
    _rc_layout.addWidget(tab.reddit_show_background)

    # Intense shadow
    tab.reddit_intense_shadow = QCheckBox("Intense Shadows")
    tab.reddit_intense_shadow.setChecked(tab._default_bool('reddit', 'intense_shadow', True))
    tab.reddit_intense_shadow.setToolTip(
        "Doubles shadow blur, opacity, and offset for dramatic effect on large displays."
    )
    tab.reddit_intense_shadow.stateChanged.connect(tab._save_settings)
    _rc_layout.addWidget(tab.reddit_intense_shadow)

    tab.reddit_show_separators = QCheckBox("Show separator lines between posts")
    tab.reddit_show_separators.setChecked(tab._default_bool('reddit', 'show_separators', True))
    tab.reddit_show_separators.stateChanged.connect(tab._save_settings)
    _rc_layout.addWidget(tab.reddit_show_separators)

    # Background opacity
    reddit_opacity_row = _aligned_row(_rc_layout, "Background Opacity:")
    tab.reddit_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.reddit_bg_opacity.setMinimum(0)
    tab.reddit_bg_opacity.setMaximum(100)
    reddit_bg_opacity_pct = int(tab._default_float('reddit', 'bg_opacity', 0.6) * 100)
    tab.reddit_bg_opacity.setValue(reddit_bg_opacity_pct)
    tab.reddit_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.reddit_bg_opacity.setTickInterval(10)
    tab.reddit_bg_opacity.valueChanged.connect(tab._save_settings)
    reddit_opacity_row.addWidget(tab.reddit_bg_opacity)
    tab.reddit_bg_opacity_label = QLabel(f"{reddit_bg_opacity_pct}%")
    tab.reddit_bg_opacity.valueChanged.connect(
        lambda v: tab.reddit_bg_opacity_label.setText(f"{v}%")
    )
    tab.reddit_bg_opacity_label.setMinimumWidth(50)
    reddit_opacity_row.addWidget(tab.reddit_bg_opacity_label)

    # Background color
    reddit_bg_color_row = _aligned_row(_rc_layout, "Background Color:")
    tab.reddit_bg_color_btn = ColorSwatchButton(title="Choose Reddit Background Color")
    tab.reddit_bg_color_btn.set_color(tab._reddit_bg_color)
    tab.reddit_bg_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_reddit_bg_color', c), tab._save_settings())
    )
    reddit_bg_color_row.addWidget(tab.reddit_bg_color_btn)
    reddit_bg_color_row.addStretch()

    # Border color
    reddit_border_color_row = _aligned_row(_rc_layout, "Border Color:")
    tab.reddit_border_color_btn = ColorSwatchButton(title="Choose Reddit Border Color")
    tab.reddit_border_color_btn.set_color(tab._reddit_border_color)
    tab.reddit_border_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_reddit_border_color', c), tab._save_settings())
    )
    reddit_border_color_row.addWidget(tab.reddit_border_color_btn)
    reddit_border_color_row.addStretch()

    # Border opacity
    reddit_border_opacity_row = _aligned_row(_rc_layout, "Border Opacity:")
    tab.reddit_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.reddit_border_opacity.setMinimum(0)
    tab.reddit_border_opacity.setMaximum(100)
    reddit_border_opacity_pct = int(tab._default_float('reddit', 'border_opacity', 1.0) * 100)
    tab.reddit_border_opacity.setValue(reddit_border_opacity_pct)
    tab.reddit_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.reddit_border_opacity.setTickInterval(10)
    tab.reddit_border_opacity.valueChanged.connect(tab._save_settings)
    reddit_border_opacity_row.addWidget(tab.reddit_border_opacity)
    tab.reddit_border_opacity_label = QLabel(f"{reddit_border_opacity_pct}%")
    tab.reddit_border_opacity.valueChanged.connect(
        lambda v: tab.reddit_border_opacity_label.setText(f"{v}%")
    )
    tab.reddit_border_opacity_label.setMinimumWidth(50)
    reddit_border_opacity_row.addWidget(tab.reddit_border_opacity_label)

    # Reddit 2
    reddit2_label = QLabel("Reddit 2 (inherits styling from Reddit 1):")
    reddit2_label.setStyleSheet("color: #aaaaaa; font-size: 11px; margin-top: 8px;")
    _rc_layout.addWidget(reddit2_label)

    reddit2_row1 = QHBoxLayout()
    tab.reddit2_enabled = QCheckBox("Enable Reddit 2")
    tab.reddit2_enabled.stateChanged.connect(tab._save_settings)
    tab.reddit2_enabled.stateChanged.connect(tab._update_stack_status)
    reddit2_row1.addWidget(tab.reddit2_enabled)
    reddit2_row1.addSpacing(24)
    reddit2_row1.addWidget(QLabel("Subreddit:"))
    tab.reddit2_subreddit = QLineEdit()
    tab.reddit2_subreddit.setPlaceholderText("e.g. earthporn")
    tab.reddit2_subreddit.textChanged.connect(tab._save_settings)
    tab.reddit2_subreddit.setMaximumWidth(150)
    reddit2_row1.addWidget(tab.reddit2_subreddit)
    reddit2_row1.addWidget(QLabel("Items:"))
    tab.reddit2_items = QComboBox()
    tab.reddit2_items.addItems(["4", "10", "20"])
    tab.reddit2_items.setMaximumWidth(60)
    tab.reddit2_items.currentTextChanged.connect(tab._save_settings)
    tab.reddit2_items.currentTextChanged.connect(tab._update_stack_status)
    reddit2_row1.addWidget(tab.reddit2_items)
    reddit2_row1.addStretch()
    _rc_layout.addLayout(reddit2_row1)

    reddit2_row2 = QHBoxLayout()
    reddit2_row2.addSpacing(24)
    reddit2_row2.addWidget(QLabel("Position:"))
    tab.reddit2_position = QComboBox()
    tab.reddit2_position.addItems([
        "Top Left", "Top Center", "Top Right",
        "Middle Left", "Center", "Middle Right",
        "Bottom Left", "Bottom Center", "Bottom Right",
    ])
    tab.reddit2_position.currentTextChanged.connect(tab._save_settings)
    tab.reddit2_position.currentTextChanged.connect(tab._update_stack_status)
    reddit2_row2.addWidget(tab.reddit2_position)
    tab.reddit2_stack_status = QLabel("")
    tab.reddit2_stack_status.setMinimumWidth(80)
    reddit2_row2.addWidget(tab.reddit2_stack_status)
    reddit2_row2.addWidget(QLabel("Display:"))
    tab.reddit2_monitor_combo = QComboBox()
    tab.reddit2_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.reddit2_monitor_combo.setMaximumWidth(60)
    tab.reddit2_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.reddit2_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    reddit2_row2.addWidget(tab.reddit2_monitor_combo)
    reddit2_row2.addStretch()
    _rc_layout.addLayout(reddit2_row2)

    reddit_layout.addWidget(tab._reddit_controls_container)
    tab.reddit_enabled.stateChanged.connect(lambda: _update_reddit_enabled_visibility(tab))
    _update_reddit_enabled_visibility(tab)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.addWidget(reddit_group)
    return container


def load_reddit_settings(tab: WidgetsTab, widgets: dict) -> None:
    """Load reddit settings from widgets config dict."""
    def _apply_color_to_button(btn_attr: str, color_attr: str) -> None:
        btn = getattr(tab, btn_attr, None)
        color = getattr(tab, color_attr, None)
        if btn is not None and color is not None and hasattr(btn, "set_color"):
            try:
                btn.set_color(color)
            except Exception:
                logger.debug(
                    "[REDDIT_TAB] Failed to sync %s with %s", btn_attr, color_attr, exc_info=True
                )

    reddit_config = widgets.get('reddit', {})
    if not isinstance(reddit_config, dict) or not reddit_config:
        try:
            getter = getattr(tab._settings, 'get_widget_defaults', None)
            if callable(getter):
                section = getter('reddit')
                if isinstance(section, dict) and section:
                    reddit_config = section
        except Exception:
            reddit_config = {}

    tab.reddit_enabled.setChecked(tab._config_bool('reddit', reddit_config, 'enabled', True))
    tab.reddit_exit_on_click.setChecked(tab._config_bool('reddit', reddit_config, 'exit_on_click', True))

    subreddit = tab._config_str('reddit', reddit_config, 'subreddit', 'All')
    tab.reddit_subreddit.setText(subreddit)

    limit_val = tab._config_int('reddit', reddit_config, 'limit', 10)
    if limit_val <= 5:
        items_text = "4"
    elif limit_val >= 20:
        items_text = "20"
    else:
        items_text = "10"
    idx_items = tab.reddit_items.findText(items_text)
    if idx_items >= 0:
        tab.reddit_items.setCurrentIndex(idx_items)

    reddit_pos = tab._config_str('reddit', reddit_config, 'position', 'Bottom Right')
    idx_pos = tab.reddit_position.findText(reddit_pos)
    if idx_pos >= 0:
        tab.reddit_position.setCurrentIndex(idx_pos)

    r_monitor_sel = reddit_config.get('monitor', tab._widget_default('reddit', 'monitor', 'ALL'))
    r_mon_text = str(r_monitor_sel) if isinstance(r_monitor_sel, (int, str)) else 'ALL'
    r_idx = tab.reddit_monitor_combo.findText(r_mon_text)
    if r_idx >= 0:
        tab.reddit_monitor_combo.setCurrentIndex(r_idx)

    tab.reddit_font_combo.setCurrentFont(QFont(tab._config_str('reddit', reddit_config, 'font_family', 'Segoe UI')))
    tab.reddit_font_size.setValue(tab._config_int('reddit', reddit_config, 'font_size', 18))
    tab.reddit_margin.setValue(tab._config_int('reddit', reddit_config, 'margin', 30))

    tab.reddit_show_background.setChecked(tab._config_bool('reddit', reddit_config, 'show_background', True))
    tab.reddit_intense_shadow.setChecked(tab._config_bool('reddit', reddit_config, 'intense_shadow', True))
    tab.reddit_show_separators.setChecked(tab._config_bool('reddit', reddit_config, 'show_separators', True))
    reddit_opacity_pct = int(tab._config_float('reddit', reddit_config, 'bg_opacity', 0.6) * 100)
    tab.reddit_bg_opacity.setValue(reddit_opacity_pct)
    tab.reddit_bg_opacity_label.setText(f"{reddit_opacity_pct}%")

    reddit_border_opacity_pct = int(tab._config_float('reddit', reddit_config, 'border_opacity', 1.0) * 100)
    tab.reddit_border_opacity.setValue(reddit_border_opacity_pct)
    tab.reddit_border_opacity_label.setText(f"{reddit_border_opacity_pct}%")

    reddit_color_data = reddit_config.get('color', tab._widget_default('reddit', 'color', [255, 255, 255, 230]))
    tab._reddit_color = QColor(*reddit_color_data)
    reddit_bg_color_data = reddit_config.get('bg_color', tab._widget_default('reddit', 'bg_color', [35, 35, 35, 255]))
    try:
        tab._reddit_bg_color = QColor(*reddit_bg_color_data)
    except Exception:
        tab._reddit_bg_color = QColor(35, 35, 35, 255)
    reddit_border_color_data = reddit_config.get('border_color', tab._widget_default('reddit', 'border_color', [255, 255, 255, 255]))
    try:
        tab._reddit_border_color = QColor(*reddit_border_color_data)
    except Exception:
        tab._reddit_border_color = QColor(255, 255, 255, 255)
    _apply_color_to_button('reddit_color_btn', '_reddit_color')
    _apply_color_to_button('reddit_bg_color_btn', '_reddit_bg_color')
    _apply_color_to_button('reddit_border_color_btn', '_reddit_border_color')

    # Reddit 2
    reddit2_config = widgets.get('reddit2', {})
    tab.reddit2_enabled.setChecked(tab._config_bool('reddit2', reddit2_config, 'enabled', False))
    tab.reddit2_subreddit.setText(tab._config_str('reddit2', reddit2_config, 'subreddit', ''))
    reddit2_limit = tab._config_int('reddit2', reddit2_config, 'limit', 4)
    if reddit2_limit <= 5:
        reddit2_limit_text = "4"
    elif reddit2_limit >= 20:
        reddit2_limit_text = "20"
    else:
        reddit2_limit_text = "10"
    reddit2_items_idx = tab.reddit2_items.findText(reddit2_limit_text)
    if reddit2_items_idx >= 0:
        tab.reddit2_items.setCurrentIndex(reddit2_items_idx)
    reddit2_pos = tab._config_str('reddit2', reddit2_config, 'position', 'Top Left')
    reddit2_pos_idx = tab.reddit2_position.findText(reddit2_pos)
    if reddit2_pos_idx >= 0:
        tab.reddit2_position.setCurrentIndex(reddit2_pos_idx)
    reddit2_monitor = reddit2_config.get('monitor', tab._widget_default('reddit2', 'monitor', 'ALL'))
    reddit2_mon_text = str(reddit2_monitor) if isinstance(reddit2_monitor, (int, str)) else 'ALL'
    reddit2_mon_idx = tab.reddit2_monitor_combo.findText(reddit2_mon_text)
    if reddit2_mon_idx >= 0:
        tab.reddit2_monitor_combo.setCurrentIndex(reddit2_mon_idx)

    _update_reddit_enabled_visibility(tab)


def save_reddit_settings(tab: WidgetsTab) -> tuple[dict, dict]:
    """Return (reddit_config, reddit2_config) from current UI state."""
    reddit_limit_text = tab.reddit_items.currentText().strip()
    try:
        reddit_limit = int(reddit_limit_text)
    except Exception:
        reddit_limit = 10

    reddit_config = {
        'enabled': tab.reddit_enabled.isChecked(),
        'exit_on_click': tab.reddit_exit_on_click.isChecked(),
        'subreddit': tab.reddit_subreddit.text().strip() or 'wallpapers',
        'limit': reddit_limit,
        'position': tab.reddit_position.currentText(),
        'font_family': tab.reddit_font_combo.currentFont().family(),
        'font_size': tab.reddit_font_size.value(),
        'margin': tab.reddit_margin.value(),
        'show_background': tab.reddit_show_background.isChecked(),
        'intense_shadow': tab.reddit_intense_shadow.isChecked(),
        'show_separators': tab.reddit_show_separators.isChecked(),
        'bg_opacity': tab.reddit_bg_opacity.value() / 100.0,
        'color': [tab._reddit_color.red(), tab._reddit_color.green(),
                  tab._reddit_color.blue(), tab._reddit_color.alpha()],
        'bg_color': [tab._reddit_bg_color.red(), tab._reddit_bg_color.green(),
                     tab._reddit_bg_color.blue(), tab._reddit_bg_color.alpha()],
        'border_color': [tab._reddit_border_color.red(), tab._reddit_border_color.green(),
                         tab._reddit_border_color.blue(), tab._reddit_border_color.alpha()],
        'border_opacity': tab.reddit_border_opacity.value() / 100.0,
    }
    rmon_text = tab.reddit_monitor_combo.currentText()
    reddit_config['monitor'] = rmon_text if rmon_text == 'ALL' else int(rmon_text)

    try:
        reddit2_limit = int(tab.reddit2_items.currentText())
    except Exception:
        reddit2_limit = 4
    reddit2_config = {
        'enabled': tab.reddit2_enabled.isChecked(),
        'subreddit': tab.reddit2_subreddit.text().strip(),
        'limit': reddit2_limit,
        'position': tab.reddit2_position.currentText(),
    }
    r2mon_text = tab.reddit2_monitor_combo.currentText()
    reddit2_config['monitor'] = r2mon_text if r2mon_text == 'ALL' else int(r2mon_text)

    return reddit_config, reddit2_config
