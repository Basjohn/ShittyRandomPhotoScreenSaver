"""Media & Spotify Visualizer section for widgets tab.

Extracted from widgets_tab.py to reduce monolith size.
Contains UI building, settings loading/saving for Media (Spotify) widget
and Spotify Beat Visualizer.
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


def build_media_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build media + spotify visualizer section UI.

    Returns the media container widget (includes both groups).
    """
    from ui.tabs.widgets_tab import NoWheelSlider

    # --- Media (Spotify) Widget Group ---
    media_group = QGroupBox("Spotify Widget")
    media_layout = QVBoxLayout(media_group)

    tab.media_enabled = QCheckBox("Enable Spotify Widget")
    tab.media_enabled.setToolTip(
        "Shows current Spotify playback using Windows media controls when available."
    )
    tab.media_enabled.stateChanged.connect(tab._save_settings)
    tab.media_enabled.stateChanged.connect(tab._update_stack_status)
    media_layout.addWidget(tab.media_enabled)

    media_info = QLabel(
        "This widget is display-only and non-interactive. Transport controls will "
        "only be active when explicitly enabled via input settings (hard-exit / Ctrl mode)."
    )
    media_info.setWordWrap(True)
    media_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
    media_layout.addWidget(media_info)

    media_pos_row = QHBoxLayout()
    media_pos_row.addWidget(QLabel("Position:"))
    tab.media_position = QComboBox()
    tab.media_position.addItems([
        "Top Left", "Top Center", "Top Right",
        "Middle Left", "Center", "Middle Right",
        "Bottom Left", "Bottom Center", "Bottom Right",
    ])
    tab.media_position.currentTextChanged.connect(tab._save_settings)
    tab.media_position.currentTextChanged.connect(tab._update_stack_status)
    media_pos_row.addWidget(tab.media_position)
    tab._set_combo_text(tab.media_position, tab._default_str('media', 'position', 'Bottom Left'))
    tab.media_stack_status = QLabel("")
    tab.media_stack_status.setMinimumWidth(100)
    media_pos_row.addWidget(tab.media_stack_status)
    media_pos_row.addStretch()
    media_layout.addLayout(media_pos_row)

    media_disp_row = QHBoxLayout()
    media_disp_row.addWidget(QLabel("Display:"))
    tab.media_monitor_combo = QComboBox()
    tab.media_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.media_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.media_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    media_disp_row.addWidget(tab.media_monitor_combo)
    media_monitor_default = tab._widget_default('media', 'monitor', 'ALL')
    tab._set_combo_text(tab.media_monitor_combo, str(media_monitor_default))
    media_disp_row.addStretch()
    media_layout.addLayout(media_disp_row)

    media_font_family_row = QHBoxLayout()
    media_font_family_row.addWidget(QLabel("Font:"))
    tab.media_font_combo = QFontComboBox()
    default_media_font = tab._default_str('media', 'font_family', 'Segoe UI')
    tab.media_font_combo.setCurrentFont(QFont(default_media_font))
    tab.media_font_combo.setMinimumWidth(220)
    tab.media_font_combo.currentFontChanged.connect(tab._save_settings)
    media_font_family_row.addWidget(tab.media_font_combo)
    media_font_family_row.addStretch()
    media_layout.addLayout(media_font_family_row)

    media_font_row = QHBoxLayout()
    media_font_row.addWidget(QLabel("Font Size:"))
    tab.media_font_size = QSpinBox()
    tab.media_font_size.setRange(10, 72)
    tab.media_font_size.setValue(tab._default_int('media', 'font_size', 20))
    tab.media_font_size.setAccelerated(True)
    tab.media_font_size.valueChanged.connect(tab._save_settings)
    tab.media_font_size.valueChanged.connect(tab._update_stack_status)
    media_font_row.addWidget(tab.media_font_size)
    media_font_row.addWidget(QLabel("px"))
    media_font_row.addStretch()
    media_layout.addLayout(media_font_row)

    media_margin_row = QHBoxLayout()
    media_margin_row.addWidget(QLabel("Margin:"))
    tab.media_margin = QSpinBox()
    tab.media_margin.setRange(0, 100)
    tab.media_margin.setValue(tab._default_int('media', 'margin', 30))
    tab.media_margin.setAccelerated(True)
    tab.media_margin.valueChanged.connect(tab._save_settings)
    media_margin_row.addWidget(tab.media_margin)
    media_margin_row.addWidget(QLabel("px"))
    media_margin_row.addStretch()
    media_layout.addLayout(media_margin_row)

    media_color_row = QHBoxLayout()
    media_color_row.addWidget(QLabel("Text Color:"))
    tab.media_color_btn = QPushButton("Choose Color...")
    tab.media_color_btn.clicked.connect(tab._choose_media_color)
    media_color_row.addWidget(tab.media_color_btn)
    media_color_row.addStretch()
    media_layout.addLayout(media_color_row)

    tab.media_show_background = QCheckBox("Show Background Frame")
    tab.media_show_background.setChecked(tab._default_bool('media', 'show_background', True))
    tab.media_show_background.stateChanged.connect(tab._save_settings)
    media_layout.addWidget(tab.media_show_background)

    tab.media_intense_shadow = QCheckBox("Intense Shadows")
    tab.media_intense_shadow.setChecked(tab._default_bool('media', 'intense_shadow', True))
    tab.media_intense_shadow.setToolTip(
        "Doubles shadow blur, opacity, and offset for dramatic effect on large displays."
    )
    tab.media_intense_shadow.stateChanged.connect(tab._save_settings)
    media_layout.addWidget(tab.media_intense_shadow)

    media_opacity_row = QHBoxLayout()
    media_opacity_row.addWidget(QLabel("Background Opacity:"))
    tab.media_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.media_bg_opacity.setMinimum(0)
    tab.media_bg_opacity.setMaximum(100)
    media_bg_opacity_pct = int(tab._default_float('media', 'bg_opacity', 0.6) * 100)
    tab.media_bg_opacity.setValue(media_bg_opacity_pct)
    tab.media_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.media_bg_opacity.setTickInterval(10)
    tab.media_bg_opacity.valueChanged.connect(tab._save_settings)
    media_opacity_row.addWidget(tab.media_bg_opacity)
    tab.media_bg_opacity_label = QLabel(f"{media_bg_opacity_pct}%")
    tab.media_bg_opacity.valueChanged.connect(
        lambda v: tab.media_bg_opacity_label.setText(f"{v}%")
    )
    media_opacity_row.addWidget(tab.media_bg_opacity_label)
    media_layout.addLayout(media_opacity_row)

    media_bg_color_row = QHBoxLayout()
    media_bg_color_row.addWidget(QLabel("Background Color:"))
    tab.media_bg_color_btn = QPushButton("Choose Color...")
    tab.media_bg_color_btn.clicked.connect(tab._choose_media_bg_color)
    media_bg_color_row.addWidget(tab.media_bg_color_btn)
    media_bg_color_row.addStretch()
    media_layout.addLayout(media_bg_color_row)

    media_border_color_row = QHBoxLayout()
    media_border_color_row.addWidget(QLabel("Border Color:"))
    tab.media_border_color_btn = QPushButton("Choose Color...")
    tab.media_border_color_btn.clicked.connect(tab._choose_media_border_color)
    media_border_color_row.addWidget(tab.media_border_color_btn)
    media_border_color_row.addStretch()
    media_layout.addLayout(media_border_color_row)

    media_border_opacity_row = QHBoxLayout()
    media_border_opacity_row.addWidget(QLabel("Border Opacity:"))
    tab.media_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.media_border_opacity.setMinimum(0)
    tab.media_border_opacity.setMaximum(100)
    media_border_opacity_pct = int(tab._default_float('media', 'border_opacity', 1.0) * 100)
    tab.media_border_opacity.setValue(media_border_opacity_pct)
    tab.media_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.media_border_opacity.setTickInterval(10)
    tab.media_border_opacity.valueChanged.connect(tab._save_settings)
    media_border_opacity_row.addWidget(tab.media_border_opacity)
    tab.media_border_opacity_label = QLabel(f"{media_border_opacity_pct}%")
    tab.media_border_opacity.valueChanged.connect(
        lambda v: tab.media_border_opacity_label.setText(f"{v}%")
    )
    media_border_opacity_row.addWidget(tab.media_border_opacity_label)
    media_layout.addLayout(media_border_opacity_row)

    media_volume_fill_row = QHBoxLayout()
    media_volume_fill_row.addWidget(QLabel("Volume Fill Color:"))
    tab.media_volume_fill_color_btn = QPushButton("Choose Color...")
    tab.media_volume_fill_color_btn.clicked.connect(tab._choose_media_volume_fill_color)
    media_volume_fill_row.addWidget(tab.media_volume_fill_color_btn)
    media_volume_fill_row.addStretch()
    media_layout.addLayout(media_volume_fill_row)

    media_artwork_row = QHBoxLayout()
    media_artwork_row.addWidget(QLabel("Artwork Size:"))
    tab.media_artwork_size = QSpinBox()
    tab.media_artwork_size.setRange(100, 300)
    tab.media_artwork_size.setValue(tab._default_int('media', 'artwork_size', 200))
    tab.media_artwork_size.setAccelerated(True)
    tab.media_artwork_size.valueChanged.connect(tab._save_settings)
    tab.media_artwork_size.valueChanged.connect(tab._update_stack_status)
    media_artwork_row.addWidget(tab.media_artwork_size)
    media_artwork_row.addWidget(QLabel("px"))
    media_artwork_row.addStretch()
    media_layout.addLayout(media_artwork_row)

    tab.media_rounded_artwork = QCheckBox("Rounded Artwork Border")
    tab.media_rounded_artwork.setChecked(
        tab._default_bool('media', 'rounded_artwork_border', True)
    )
    tab.media_rounded_artwork.stateChanged.connect(tab._save_settings)
    media_layout.addWidget(tab.media_rounded_artwork)

    tab.media_show_header_frame = QCheckBox("Header Border Around Logo + Title")
    tab.media_show_header_frame.setChecked(
        tab._default_bool('media', 'show_header_frame', True)
    )
    tab.media_show_header_frame.stateChanged.connect(tab._save_settings)
    media_layout.addWidget(tab.media_show_header_frame)

    tab.media_show_controls = QCheckBox("Show Transport Controls")
    tab.media_show_controls.setChecked(
        tab._default_bool('media', 'show_controls', True)
    )
    tab.media_show_controls.stateChanged.connect(tab._save_settings)
    media_layout.addWidget(tab.media_show_controls)

    tab.media_slab_effect = QCheckBox("Slab Effect - Experimental")
    tab.media_slab_effect.setChecked(
        tab._default_bool('media', 'slab_effect_enabled', True)
    )
    tab.media_slab_effect.setToolTip(
        "Adds a 3D depth effect to the transport controls row with a subtle shadow."
    )
    tab.media_slab_effect.stateChanged.connect(tab._save_settings)
    media_layout.addWidget(tab.media_slab_effect)

    tab.media_spotify_volume_enabled = QCheckBox("Enable Spotify Volume Slider")
    tab.media_spotify_volume_enabled.setToolTip(
        "Show a slim vertical volume slider next to the Spotify card when Core Audio/pycaw is available. "
        "The slider only affects the Spotify session volume and is gated by hard-exit / Ctrl interaction modes."
    )
    tab.media_spotify_volume_enabled.setChecked(
        tab._default_bool('media', 'spotify_volume_enabled', True)
    )
    tab.media_spotify_volume_enabled.stateChanged.connect(tab._save_settings)
    media_layout.addWidget(tab.media_spotify_volume_enabled)

    # --- Spotify Beat Visualizer Group ---
    spotify_vis_group = QGroupBox("Spotify Beat Visualizer")
    spotify_vis_layout = QVBoxLayout(spotify_vis_group)

    spotify_vis_enable_row = QHBoxLayout()
    tab.spotify_vis_enabled = QCheckBox("Enable Spotify Beat Visualizer")
    tab.spotify_vis_enabled.setChecked(tab._default_bool('spotify_visualizer', 'enabled', True))
    tab.spotify_vis_enabled.setToolTip(
        "Shows a thin bar visualizer tied to Spotify playback, positioned just above the Spotify widget."
    )
    tab.spotify_vis_enabled.stateChanged.connect(tab._save_settings)
    spotify_vis_enable_row.addWidget(tab.spotify_vis_enabled)

    tab.spotify_vis_software_enabled = QCheckBox("FORCE Software Visualizer")
    tab.spotify_vis_software_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'software_visualizer_enabled', False)
    )
    tab.spotify_vis_software_enabled.setToolTip(
        "Force the legacy CPU bar visualizer even when the renderer backend is set to Software or when OpenGL is unavailable."
    )
    tab.spotify_vis_software_enabled.stateChanged.connect(tab._save_settings)
    spotify_vis_enable_row.addStretch()
    spotify_vis_enable_row.addWidget(tab.spotify_vis_software_enabled)
    spotify_vis_layout.addLayout(spotify_vis_enable_row)

    spotify_vis_bar_row = QHBoxLayout()
    spotify_vis_bar_row.addWidget(QLabel("Bar Count:"))
    tab.spotify_vis_bar_count = QSpinBox()
    tab.spotify_vis_bar_count.setRange(8, 96)
    tab.spotify_vis_bar_count.setValue(tab._default_int('spotify_visualizer', 'bar_count', 32))
    tab.spotify_vis_bar_count.setAccelerated(True)
    tab.spotify_vis_bar_count.setToolTip("Number of frequency bars to display (8-96)")
    tab.spotify_vis_bar_count.valueChanged.connect(tab._save_settings)
    spotify_vis_bar_row.addWidget(tab.spotify_vis_bar_count)
    spotify_vis_bar_row.addWidget(QLabel("bars"))
    spotify_vis_bar_row.addStretch()
    spotify_vis_layout.addLayout(spotify_vis_bar_row)

    spotify_vis_block_row = QHBoxLayout()
    spotify_vis_block_row.addWidget(QLabel("Audio Block Size:"))
    tab.spotify_vis_block_size = QComboBox()
    tab.spotify_vis_block_size.setMinimumWidth(140)
    tab.spotify_vis_block_size.addItem("Auto (Driver)", 0)
    tab.spotify_vis_block_size.addItem("256 samples", 256)
    tab.spotify_vis_block_size.addItem("512 samples", 512)
    tab.spotify_vis_block_size.addItem("1024 samples", 1024)
    tab.spotify_vis_block_size.currentIndexChanged.connect(tab._save_settings)
    spotify_vis_block_row.addWidget(tab.spotify_vis_block_size)
    default_block = tab._default_int('spotify_visualizer', 'audio_block_size', 512)
    block_idx = tab.spotify_vis_block_size.findData(default_block)
    if block_idx >= 0:
        tab.spotify_vis_block_size.setCurrentIndex(block_idx)
    spotify_vis_block_row.addStretch()
    spotify_vis_layout.addLayout(spotify_vis_block_row)

    spotify_vis_fill_row = QHBoxLayout()
    spotify_vis_fill_row.addWidget(QLabel("Bar Fill Color:"))
    tab.spotify_vis_fill_color_btn = QPushButton("Choose Color...")
    tab.spotify_vis_fill_color_btn.clicked.connect(tab._choose_spotify_vis_fill_color)
    spotify_vis_fill_row.addWidget(tab.spotify_vis_fill_color_btn)
    spotify_vis_fill_row.addStretch()
    spotify_vis_layout.addLayout(spotify_vis_fill_row)

    spotify_vis_border_color_row = QHBoxLayout()
    spotify_vis_border_color_row.addWidget(QLabel("Bar Border Color:"))
    tab.spotify_vis_border_color_btn = QPushButton("Choose Color...")
    tab.spotify_vis_border_color_btn.clicked.connect(tab._choose_spotify_vis_border_color)
    spotify_vis_border_color_row.addWidget(tab.spotify_vis_border_color_btn)
    spotify_vis_border_color_row.addStretch()
    spotify_vis_layout.addLayout(spotify_vis_border_color_row)

    spotify_vis_border_opacity_row = QHBoxLayout()
    spotify_vis_border_opacity_row.addWidget(QLabel("Bar Border Opacity:"))
    tab.spotify_vis_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spotify_vis_border_opacity.setMinimum(0)
    tab.spotify_vis_border_opacity.setMaximum(100)
    spotify_vis_border_opacity_pct = int(
        tab._default_float('spotify_visualizer', 'bar_border_opacity', 0.85) * 100
    )
    tab.spotify_vis_border_opacity.setValue(spotify_vis_border_opacity_pct)
    tab.spotify_vis_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spotify_vis_border_opacity.setTickInterval(5)
    tab.spotify_vis_border_opacity.valueChanged.connect(tab._save_settings)
    spotify_vis_border_opacity_row.addWidget(tab.spotify_vis_border_opacity)
    tab.spotify_vis_border_opacity_label = QLabel(f"{spotify_vis_border_opacity_pct}%")
    tab.spotify_vis_border_opacity.valueChanged.connect(
        lambda v: tab.spotify_vis_border_opacity_label.setText(f"{v}%")
    )
    spotify_vis_border_opacity_row.addWidget(tab.spotify_vis_border_opacity_label)
    spotify_vis_layout.addLayout(spotify_vis_border_opacity_row)

    spotify_vis_sensitivity_row = QHBoxLayout()
    tab.spotify_vis_recommended = QCheckBox("Adaptive")
    tab.spotify_vis_recommended.setChecked(
        tab._default_bool('spotify_visualizer', 'adaptive_sensitivity', True)
    )
    tab.spotify_vis_recommended.setToolTip(
        "When enabled, the visualizer uses the adaptive (v1.4) sensitivity baseline. Disable to adjust manually."
    )
    tab.spotify_vis_recommended.stateChanged.connect(tab._save_settings)
    tab.spotify_vis_recommended.stateChanged.connect(lambda _: tab._update_spotify_vis_sensitivity_enabled_state())
    spotify_vis_sensitivity_row.addWidget(tab.spotify_vis_recommended)
    spotify_vis_sensitivity_row.addStretch()
    spotify_vis_layout.addLayout(spotify_vis_sensitivity_row)

    spotify_vis_sensitivity_slider_row = QHBoxLayout()
    spotify_vis_sensitivity_slider_row.addWidget(QLabel("Sensitivity:"))
    tab.spotify_vis_sensitivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spotify_vis_sensitivity.setMinimum(25)
    tab.spotify_vis_sensitivity.setMaximum(250)
    spotify_sens_slider = int(max(0.25, min(2.5, tab._default_float('spotify_visualizer', 'sensitivity', 1.0))) * 100)
    tab.spotify_vis_sensitivity.setValue(spotify_sens_slider)
    tab.spotify_vis_sensitivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spotify_vis_sensitivity.setTickInterval(25)
    tab.spotify_vis_sensitivity.valueChanged.connect(tab._save_settings)
    spotify_vis_sensitivity_slider_row.addWidget(tab.spotify_vis_sensitivity)
    tab.spotify_vis_sensitivity_label = QLabel(f"{spotify_sens_slider / 100.0:.2f}x")
    tab.spotify_vis_sensitivity.valueChanged.connect(
        lambda v: tab.spotify_vis_sensitivity_label.setText(f"{v / 100.0:.2f}x")
    )
    spotify_vis_sensitivity_slider_row.addWidget(tab.spotify_vis_sensitivity_label)
    spotify_vis_layout.addLayout(spotify_vis_sensitivity_slider_row)

    spotify_vis_floor_row = QHBoxLayout()
    tab.spotify_vis_dynamic_floor = QCheckBox("Dynamic Noise Floor")
    tab.spotify_vis_dynamic_floor.setChecked(
        tab._default_bool('spotify_visualizer', 'dynamic_range_enabled', True)
    )
    tab.spotify_vis_dynamic_floor.setToolTip(
        "Automatically adjust the noise floor based on recent Spotify loopback energy."
    )
    tab.spotify_vis_dynamic_floor.setChecked(True)
    tab.spotify_vis_dynamic_floor.stateChanged.connect(tab._save_settings)
    tab.spotify_vis_dynamic_floor.stateChanged.connect(
        lambda _: tab._update_spotify_vis_floor_enabled_state()
    )
    spotify_vis_floor_row.addWidget(tab.spotify_vis_dynamic_floor)
    spotify_vis_floor_row.addStretch()
    spotify_vis_layout.addLayout(spotify_vis_floor_row)

    spotify_vis_manual_floor_row = QHBoxLayout()
    spotify_vis_manual_floor_row.addWidget(QLabel("Manual Floor:"))
    tab.spotify_vis_manual_floor = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spotify_vis_manual_floor.setMinimum(12)
    tab.spotify_vis_manual_floor.setMaximum(400)
    manual_floor_default = tab._default_float('spotify_visualizer', 'manual_floor', 2.1)
    tab.spotify_vis_manual_floor.setValue(int(max(0.12, min(4.0, manual_floor_default)) * 100))
    tab.spotify_vis_manual_floor.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spotify_vis_manual_floor.setTickInterval(10)
    tab.spotify_vis_manual_floor.valueChanged.connect(tab._save_settings)
    spotify_vis_manual_floor_row.addWidget(tab.spotify_vis_manual_floor)
    tab.spotify_vis_manual_floor_label = QLabel(f"{manual_floor_default:.2f}")
    tab.spotify_vis_manual_floor.valueChanged.connect(
        lambda v: tab.spotify_vis_manual_floor_label.setText(f"{v / 100.0:.2f}")
    )
    spotify_vis_manual_floor_row.addWidget(tab.spotify_vis_manual_floor_label)
    spotify_vis_layout.addLayout(spotify_vis_manual_floor_row)

    # Ghosting controls
    spotify_vis_ghost_enable_row = QHBoxLayout()
    tab.spotify_vis_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.spotify_vis_ghost_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'ghosting_enabled', True)
    )
    tab.spotify_vis_ghost_enabled.setToolTip(
        "When enabled, the visualizer draws trailing ghost bars above the current height."
    )
    tab.spotify_vis_ghost_enabled.stateChanged.connect(tab._save_settings)
    spotify_vis_ghost_enable_row.addWidget(tab.spotify_vis_ghost_enabled)
    spotify_vis_ghost_enable_row.addStretch()
    spotify_vis_layout.addLayout(spotify_vis_ghost_enable_row)

    spotify_vis_ghost_opacity_row = QHBoxLayout()
    spotify_vis_ghost_opacity_row.addWidget(QLabel("Ghost Opacity:"))
    tab.spotify_vis_ghost_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spotify_vis_ghost_opacity.setMinimum(0)
    tab.spotify_vis_ghost_opacity.setMaximum(100)
    ghost_alpha_pct = int(tab._default_float('spotify_visualizer', 'ghost_alpha', 0.4) * 100)
    tab.spotify_vis_ghost_opacity.setValue(ghost_alpha_pct)
    tab.spotify_vis_ghost_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spotify_vis_ghost_opacity.setTickInterval(5)
    tab.spotify_vis_ghost_opacity.valueChanged.connect(tab._save_settings)
    spotify_vis_ghost_opacity_row.addWidget(tab.spotify_vis_ghost_opacity)
    tab.spotify_vis_ghost_opacity_label = QLabel(f"{ghost_alpha_pct}%")
    tab.spotify_vis_ghost_opacity.valueChanged.connect(
        lambda v: tab.spotify_vis_ghost_opacity_label.setText(f"{v}%")
    )
    spotify_vis_ghost_opacity_row.addWidget(tab.spotify_vis_ghost_opacity_label)
    spotify_vis_layout.addLayout(spotify_vis_ghost_opacity_row)

    spotify_vis_ghost_decay_row = QHBoxLayout()
    spotify_vis_ghost_decay_row.addWidget(QLabel("Ghost Decay Speed:"))
    tab.spotify_vis_ghost_decay = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spotify_vis_ghost_decay.setMinimum(10)
    tab.spotify_vis_ghost_decay.setMaximum(100)
    ghost_decay_slider = int(tab._default_float('spotify_visualizer', 'ghost_decay', 0.4) * 100)
    tab.spotify_vis_ghost_decay.setValue(max(10, min(100, ghost_decay_slider)))
    tab.spotify_vis_ghost_decay.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spotify_vis_ghost_decay.setTickInterval(5)
    tab.spotify_vis_ghost_decay.valueChanged.connect(tab._save_settings)
    spotify_vis_ghost_decay_row.addWidget(tab.spotify_vis_ghost_decay)
    tab.spotify_vis_ghost_decay_label = QLabel(f"{tab.spotify_vis_ghost_decay.value() / 100.0:.2f}x")
    tab.spotify_vis_ghost_decay.valueChanged.connect(
        lambda v: tab.spotify_vis_ghost_decay_label.setText(f"{v / 100.0:.2f}x")
    )
    spotify_vis_ghost_decay_row.addWidget(tab.spotify_vis_ghost_decay_label)
    spotify_vis_layout.addLayout(spotify_vis_ghost_decay_row)

    # Container for both groups
    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.addWidget(media_group)
    container_layout.addWidget(spotify_vis_group)
    return container


def load_media_settings(tab: WidgetsTab, widgets: dict) -> None:
    """Load media + spotify visualizer settings from widgets config dict."""
    media_config = widgets.get('media', {})
    tab.media_enabled.setChecked(tab._config_bool('media', media_config, 'enabled', True))

    media_pos = tab._config_str('media', media_config, 'position', 'Bottom Left')
    index = tab.media_position.findText(media_pos)
    if index >= 0:
        tab.media_position.setCurrentIndex(index)

    tab.media_font_combo.setCurrentFont(QFont(tab._config_str('media', media_config, 'font_family', 'Segoe UI')))
    tab.media_font_size.setValue(tab._config_int('media', media_config, 'font_size', 20))
    tab.media_margin.setValue(tab._config_int('media', media_config, 'margin', 30))
    tab.media_show_background.setChecked(tab._config_bool('media', media_config, 'show_background', True))
    tab.media_intense_shadow.setChecked(tab._config_bool('media', media_config, 'intense_shadow', True))
    media_opacity_pct = int(tab._config_float('media', media_config, 'bg_opacity', 0.6) * 100)
    tab.media_bg_opacity.setValue(media_opacity_pct)
    tab.media_bg_opacity_label.setText(f"{media_opacity_pct}%")

    tab._media_artwork_size = tab._config_int('media', media_config, 'artwork_size', 200)
    tab.media_artwork_size.setValue(tab._media_artwork_size)
    tab.media_rounded_artwork.setChecked(tab._config_bool('media', media_config, 'rounded_artwork_border', True))
    tab.media_show_header_frame.setChecked(tab._config_bool('media', media_config, 'show_header_frame', True))
    tab.media_show_controls.setChecked(tab._config_bool('media', media_config, 'show_controls', True))
    tab.media_slab_effect.setChecked(tab._config_bool('media', media_config, 'slab_effect_enabled', False))
    tab.media_spotify_volume_enabled.setChecked(
        tab._config_bool('media', media_config, 'spotify_volume_enabled', True)
    )

    # Colors
    media_color_data = media_config.get('color', tab._widget_default('media', 'color', [255, 255, 255, 230]))
    tab._media_color = QColor(*media_color_data)
    media_bg_color_data = media_config.get('bg_color', tab._widget_default('media', 'bg_color', [35, 35, 35, 255]))
    try:
        tab._media_bg_color = QColor(*media_bg_color_data)
    except Exception:
        tab._media_bg_color = QColor(35, 35, 35, 255)
    media_border_color_data = media_config.get('border_color', tab._widget_default('media', 'border_color', [255, 255, 255, 255]))
    try:
        tab._media_border_color = QColor(*media_border_color_data)
    except Exception:
        tab._media_border_color = QColor(255, 255, 255, 255)
    media_border_opacity_pct = int(tab._config_float('media', media_config, 'border_opacity', 1.0) * 100)
    tab.media_border_opacity.setValue(media_border_opacity_pct)
    tab.media_border_opacity_label.setText(f"{media_border_opacity_pct}%")

    volume_fill_data = media_config.get('spotify_volume_fill_color', tab._widget_default('media', 'spotify_volume_fill_color', [255, 255, 255, 230]))
    try:
        tab._media_volume_fill_color = QColor(*volume_fill_data)
    except Exception:
        tab._media_volume_fill_color = QColor(255, 255, 255, 230)

    m_monitor_sel = media_config.get('monitor', tab._widget_default('media', 'monitor', 'ALL'))
    m_mon_text = str(m_monitor_sel) if isinstance(m_monitor_sel, (int, str)) else 'ALL'
    midx = tab.media_monitor_combo.findText(m_mon_text)
    if midx >= 0:
        tab.media_monitor_combo.setCurrentIndex(midx)

    # Spotify Visualizer
    spotify_vis_config = widgets.get('spotify_visualizer', {})
    tab.spotify_vis_enabled.setChecked(
        tab._config_bool('spotify_visualizer', spotify_vis_config, 'enabled', True)
    )
    tab.spotify_vis_bar_count.setValue(
        tab._config_int('spotify_visualizer', spotify_vis_config, 'bar_count', 32)
    )
    block_size_val = tab._config_int('spotify_visualizer', spotify_vis_config, 'audio_block_size', 0)
    block_idx = tab.spotify_vis_block_size.findData(block_size_val)
    if block_idx < 0:
        block_idx = 0
    tab.spotify_vis_block_size.setCurrentIndex(block_idx)

    tab.spotify_vis_recommended.setChecked(
        tab._config_bool('spotify_visualizer', spotify_vis_config, 'adaptive_sensitivity', True)
    )
    sens_f = tab._config_float('spotify_visualizer', spotify_vis_config, 'sensitivity', 1.0)
    sens_slider = int(max(0.25, min(2.5, sens_f)) * 100)
    tab.spotify_vis_sensitivity.setValue(sens_slider)
    tab.spotify_vis_sensitivity_label.setText(f"{sens_slider / 100.0:.2f}x")
    tab._update_spotify_vis_sensitivity_enabled_state()

    dynamic_floor = tab._config_bool('spotify_visualizer', spotify_vis_config, 'dynamic_range_enabled', True)
    tab.spotify_vis_dynamic_floor.setChecked(dynamic_floor)
    manual_floor_f = tab._config_float('spotify_visualizer', spotify_vis_config, 'manual_floor', 2.1)
    manual_slider = int(max(0.12, min(4.0, manual_floor_f)) * 100)
    tab.spotify_vis_manual_floor.setValue(manual_slider)
    tab.spotify_vis_manual_floor_label.setText(f"{manual_slider / 100.0:.2f}")
    tab._update_spotify_vis_floor_enabled_state()

    tab.spotify_vis_software_enabled.setChecked(
        tab._config_bool('spotify_visualizer', spotify_vis_config, 'software_visualizer_enabled', False)
    )

    fill_color_data = spotify_vis_config.get('bar_fill_color', tab._widget_default('spotify_visualizer', 'bar_fill_color', [0, 255, 128, 230]))
    try:
        tab._spotify_vis_fill_color = QColor(*fill_color_data)
    except Exception:
        tab._spotify_vis_fill_color = QColor(0, 255, 128, 230)

    border_color_data = spotify_vis_config.get('bar_border_color', tab._widget_default('spotify_visualizer', 'bar_border_color', [255, 255, 255, 230]))
    try:
        tab._spotify_vis_border_color = QColor(*border_color_data)
    except Exception:
        tab._spotify_vis_border_color = QColor(255, 255, 255, 230)

    border_opacity_pct = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bar_border_opacity', 0.85) * 100)
    tab.spotify_vis_border_opacity.setValue(border_opacity_pct)
    tab.spotify_vis_border_opacity_label.setText(f"{border_opacity_pct}%")

    # Ghosting
    tab.spotify_vis_ghost_enabled.setChecked(
        tab._config_bool('spotify_visualizer', spotify_vis_config, 'ghosting_enabled', True)
    )
    ghost_alpha_pct = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'ghost_alpha', 0.4) * 100)
    ghost_alpha_pct = max(0, min(100, ghost_alpha_pct))
    tab.spotify_vis_ghost_opacity.setValue(ghost_alpha_pct)
    tab.spotify_vis_ghost_opacity_label.setText(f"{ghost_alpha_pct}%")

    ghost_decay_f = tab._config_float('spotify_visualizer', spotify_vis_config, 'ghost_decay', 0.4)
    ghost_decay_slider = max(10, min(100, int(ghost_decay_f * 100.0)))
    tab.spotify_vis_ghost_decay.setValue(ghost_decay_slider)
    tab.spotify_vis_ghost_decay_label.setText(f"{ghost_decay_slider / 100.0:.2f}x")


def save_media_settings(tab: WidgetsTab) -> tuple[dict, dict]:
    """Return (media_config, spotify_vis_config) from current UI state."""
    media_config = {
        'enabled': tab.media_enabled.isChecked(),
        'position': tab.media_position.currentText(),
        'font_family': tab.media_font_combo.currentFont().family(),
        'font_size': tab.media_font_size.value(),
        'margin': tab.media_margin.value(),
        'show_background': tab.media_show_background.isChecked(),
        'intense_shadow': tab.media_intense_shadow.isChecked(),
        'bg_opacity': tab.media_bg_opacity.value() / 100.0,
        'color': [tab._media_color.red(), tab._media_color.green(),
                  tab._media_color.blue(), tab._media_color.alpha()],
        'bg_color': [tab._media_bg_color.red(), tab._media_bg_color.green(),
                     tab._media_bg_color.blue(), tab._media_bg_color.alpha()],
        'border_color': [tab._media_border_color.red(), tab._media_border_color.green(),
                         tab._media_border_color.blue(), tab._media_border_color.alpha()],
        'border_opacity': tab.media_border_opacity.value() / 100.0,
        'spotify_volume_fill_color': [
            tab._media_volume_fill_color.red(),
            tab._media_volume_fill_color.green(),
            tab._media_volume_fill_color.blue(),
            tab._media_volume_fill_color.alpha(),
        ],
        'artwork_size': tab.media_artwork_size.value(),
        'rounded_artwork_border': tab.media_rounded_artwork.isChecked(),
        'show_header_frame': tab.media_show_header_frame.isChecked(),
        'show_controls': tab.media_show_controls.isChecked(),
        'slab_effect_enabled': tab.media_slab_effect.isChecked(),
        'spotify_volume_enabled': tab.media_spotify_volume_enabled.isChecked(),
    }
    mmon_text = tab.media_monitor_combo.currentText()
    media_config['monitor'] = mmon_text if mmon_text == 'ALL' else int(mmon_text)

    spotify_vis_config = {
        'enabled': tab.spotify_vis_enabled.isChecked(),
        'mode': 'spectrum',
        'bar_count': tab.spotify_vis_bar_count.value(),
        'software_visualizer_enabled': tab.spotify_vis_software_enabled.isChecked(),
        'adaptive_sensitivity': tab.spotify_vis_recommended.isChecked(),
        'audio_block_size': int(tab.spotify_vis_block_size.currentData() or 0),
        'sensitivity': max(0.25, min(2.5, tab.spotify_vis_sensitivity.value() / 100.0)),
        'bar_fill_color': [
            tab._spotify_vis_fill_color.red(),
            tab._spotify_vis_fill_color.green(),
            tab._spotify_vis_fill_color.blue(),
            tab._spotify_vis_fill_color.alpha(),
        ],
        'bar_border_color': [
            tab._spotify_vis_border_color.red(),
            tab._spotify_vis_border_color.green(),
            tab._spotify_vis_border_color.blue(),
            tab._spotify_vis_border_color.alpha(),
        ],
        'bar_border_opacity': tab.spotify_vis_border_opacity.value() / 100.0,
        'ghosting_enabled': tab.spotify_vis_ghost_enabled.isChecked(),
        'ghost_alpha': tab.spotify_vis_ghost_opacity.value() / 100.0,
        'ghost_decay': max(0.1, tab.spotify_vis_ghost_decay.value() / 100.0),
        'dynamic_floor': tab.spotify_vis_dynamic_floor.isChecked(),
        'dynamic_range_enabled': tab.spotify_vis_dynamic_floor.isChecked(),
        'manual_floor': max(0.12, min(4.0, tab.spotify_vis_manual_floor.value() / 100.0)),
    }

    tab._update_spotify_vis_sensitivity_enabled_state()
    tab._update_spotify_vis_floor_enabled_state()

    return media_config, spotify_vis_config
