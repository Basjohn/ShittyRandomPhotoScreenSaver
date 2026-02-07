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

    # --- Visualizer Type Selector ---
    vis_type_row = QHBoxLayout()
    vis_type_row.addWidget(QLabel("Visualizer Type:"))
    tab.spotify_vis_type_combo = QComboBox()
    tab.spotify_vis_type_combo.setMinimumWidth(160)
    tab.spotify_vis_type_combo.addItem("Spectrum", "spectrum")
    tab.spotify_vis_type_combo.addItem("Oscilloscope", "oscilloscope")
    tab.spotify_vis_type_combo.addItem("Starfield", "starfield")
    tab.spotify_vis_type_combo.addItem("Blob", "blob")
    tab.spotify_vis_type_combo.addItem("Helix / DNA", "helix")
    default_mode = tab._default_str('spotify_visualizer', 'mode', 'spectrum')
    mode_idx = tab.spotify_vis_type_combo.findData(default_mode)
    if mode_idx >= 0:
        tab.spotify_vis_type_combo.setCurrentIndex(mode_idx)
    tab.spotify_vis_type_combo.setToolTip(
        "Select the visualization style. Spectrum is the classic segmented bar display."
    )
    tab.spotify_vis_type_combo.currentIndexChanged.connect(tab._save_settings)
    tab.spotify_vis_type_combo.currentIndexChanged.connect(
        lambda _: tab._update_vis_mode_sections()
    )
    vis_type_row.addWidget(tab.spotify_vis_type_combo)
    vis_type_row.addStretch()
    spotify_vis_layout.addLayout(vis_type_row)

    # ==========================================
    # Spectrum-only settings container
    # ==========================================
    tab._spectrum_settings_container = QWidget()
    spectrum_layout = QVBoxLayout(tab._spectrum_settings_container)
    spectrum_layout.setContentsMargins(0, 0, 0, 0)

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
    spectrum_layout.addLayout(spotify_vis_bar_row)

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
    spectrum_layout.addLayout(spotify_vis_block_row)

    spotify_vis_fill_row = QHBoxLayout()
    spotify_vis_fill_row.addWidget(QLabel("Bar Fill Color:"))
    tab.spotify_vis_fill_color_btn = QPushButton("Choose Color...")
    tab.spotify_vis_fill_color_btn.clicked.connect(tab._choose_spotify_vis_fill_color)
    spotify_vis_fill_row.addWidget(tab.spotify_vis_fill_color_btn)
    spotify_vis_fill_row.addStretch()
    spectrum_layout.addLayout(spotify_vis_fill_row)

    spotify_vis_border_color_row = QHBoxLayout()
    spotify_vis_border_color_row.addWidget(QLabel("Bar Border Color:"))
    tab.spotify_vis_border_color_btn = QPushButton("Choose Color...")
    tab.spotify_vis_border_color_btn.clicked.connect(tab._choose_spotify_vis_border_color)
    spotify_vis_border_color_row.addWidget(tab.spotify_vis_border_color_btn)
    spotify_vis_border_color_row.addStretch()
    spectrum_layout.addLayout(spotify_vis_border_color_row)

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
    spectrum_layout.addLayout(spotify_vis_border_opacity_row)

    tab.spotify_vis_recommended = QCheckBox("Adaptive")
    tab.spotify_vis_recommended.setChecked(
        tab._default_bool('spotify_visualizer', 'adaptive_sensitivity', True)
    )
    tab.spotify_vis_recommended.setToolTip(
        "When enabled, the visualizer uses the adaptive (v1.4) sensitivity baseline. Disable to adjust manually."
    )
    tab.spotify_vis_recommended.stateChanged.connect(tab._save_settings)
    tab.spotify_vis_recommended.stateChanged.connect(lambda _: tab._update_spotify_vis_sensitivity_enabled_state())
    spectrum_layout.addWidget(tab.spotify_vis_recommended)

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
    spectrum_layout.addLayout(spotify_vis_sensitivity_slider_row)

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
    spectrum_layout.addWidget(tab.spotify_vis_dynamic_floor)

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
    spectrum_layout.addLayout(spotify_vis_manual_floor_row)

    # Ghosting controls
    tab.spotify_vis_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.spotify_vis_ghost_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'ghosting_enabled', True)
    )
    tab.spotify_vis_ghost_enabled.setToolTip(
        "When enabled, the visualizer draws trailing ghost bars above the current height."
    )
    tab.spotify_vis_ghost_enabled.stateChanged.connect(tab._save_settings)
    spectrum_layout.addWidget(tab.spotify_vis_ghost_enabled)

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
    spectrum_layout.addLayout(spotify_vis_ghost_opacity_row)

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
    spectrum_layout.addLayout(spotify_vis_ghost_decay_row)

    spotify_vis_layout.addWidget(tab._spectrum_settings_container)

    # ==========================================
    # Oscilloscope settings container
    # ==========================================
    tab._osc_settings_container = QWidget()
    osc_layout = QVBoxLayout(tab._osc_settings_container)
    osc_layout.setContentsMargins(0, 0, 0, 0)

    tab.osc_glow_enabled = QCheckBox("Enable Glow")
    tab.osc_glow_enabled.setChecked(tab._default_bool('spotify_visualizer', 'osc_glow_enabled', True))
    tab.osc_glow_enabled.setToolTip("Draw a soft glow halo around the waveform line.")
    tab.osc_glow_enabled.stateChanged.connect(tab._save_settings)
    osc_layout.addWidget(tab.osc_glow_enabled)

    osc_glow_row = QHBoxLayout()
    osc_glow_row.addWidget(QLabel("Glow Intensity:"))
    tab.osc_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_glow_intensity.setMinimum(0)
    tab.osc_glow_intensity.setMaximum(100)
    osc_glow_val = int(tab._default_float('spotify_visualizer', 'osc_glow_intensity', 0.5) * 100)
    tab.osc_glow_intensity.setValue(osc_glow_val)
    tab.osc_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_glow_intensity.setTickInterval(10)
    tab.osc_glow_intensity.valueChanged.connect(tab._save_settings)
    osc_glow_row.addWidget(tab.osc_glow_intensity)
    tab.osc_glow_intensity_label = QLabel(f"{osc_glow_val}%")
    tab.osc_glow_intensity.valueChanged.connect(
        lambda v: tab.osc_glow_intensity_label.setText(f"{v}%")
    )
    osc_glow_row.addWidget(tab.osc_glow_intensity_label)
    osc_layout.addLayout(osc_glow_row)

    tab.osc_reactive_glow = QCheckBox("Reactive Glow (bass-driven)")
    tab.osc_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'osc_reactive_glow', True))
    tab.osc_reactive_glow.setToolTip("Glow intensity pulses with bass energy.")
    tab.osc_reactive_glow.stateChanged.connect(tab._save_settings)
    osc_layout.addWidget(tab.osc_reactive_glow)

    spotify_vis_layout.addWidget(tab._osc_settings_container)

    # ==========================================
    # Starfield settings container
    # ==========================================
    tab._starfield_settings_container = QWidget()
    star_layout = QVBoxLayout(tab._starfield_settings_container)
    star_layout.setContentsMargins(0, 0, 0, 0)

    star_speed_row = QHBoxLayout()
    star_speed_row.addWidget(QLabel("Travel Speed:"))
    tab.star_travel_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.star_travel_speed.setMinimum(0)
    tab.star_travel_speed.setMaximum(100)
    star_speed_val = int(tab._default_float('spotify_visualizer', 'star_travel_speed', 0.5) * 100)
    tab.star_travel_speed.setValue(star_speed_val)
    tab.star_travel_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.star_travel_speed.setTickInterval(10)
    tab.star_travel_speed.valueChanged.connect(tab._save_settings)
    star_speed_row.addWidget(tab.star_travel_speed)
    tab.star_travel_speed_label = QLabel(f"{star_speed_val / 100.0:.2f}")
    tab.star_travel_speed.valueChanged.connect(
        lambda v: tab.star_travel_speed_label.setText(f"{v / 100.0:.2f}")
    )
    star_speed_row.addWidget(tab.star_travel_speed_label)
    star_layout.addLayout(star_speed_row)

    star_react_row = QHBoxLayout()
    star_react_row.addWidget(QLabel("Bass Reactivity:"))
    tab.star_reactivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.star_reactivity.setMinimum(0)
    tab.star_reactivity.setMaximum(200)
    star_react_val = int(tab._default_float('spotify_visualizer', 'star_reactivity', 1.0) * 100)
    tab.star_reactivity.setValue(star_react_val)
    tab.star_reactivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.star_reactivity.setTickInterval(25)
    tab.star_reactivity.valueChanged.connect(tab._save_settings)
    star_react_row.addWidget(tab.star_reactivity)
    tab.star_reactivity_label = QLabel(f"{star_react_val / 100.0:.2f}x")
    tab.star_reactivity.valueChanged.connect(
        lambda v: tab.star_reactivity_label.setText(f"{v / 100.0:.2f}x")
    )
    star_react_row.addWidget(tab.star_reactivity_label)
    star_layout.addLayout(star_react_row)

    spotify_vis_layout.addWidget(tab._starfield_settings_container)

    # ==========================================
    # Blob settings container
    # ==========================================
    tab._blob_settings_container = QWidget()
    blob_layout = QVBoxLayout(tab._blob_settings_container)
    blob_layout.setContentsMargins(0, 0, 0, 0)

    blob_pulse_row = QHBoxLayout()
    blob_pulse_row.addWidget(QLabel("Pulse Intensity:"))
    tab.blob_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_pulse.setMinimum(0)
    tab.blob_pulse.setMaximum(200)
    blob_pulse_val = int(tab._default_float('spotify_visualizer', 'blob_pulse', 1.0) * 100)
    tab.blob_pulse.setValue(blob_pulse_val)
    tab.blob_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_pulse.setTickInterval(25)
    tab.blob_pulse.valueChanged.connect(tab._save_settings)
    blob_pulse_row.addWidget(tab.blob_pulse)
    tab.blob_pulse_label = QLabel(f"{blob_pulse_val / 100.0:.2f}x")
    tab.blob_pulse.valueChanged.connect(
        lambda v: tab.blob_pulse_label.setText(f"{v / 100.0:.2f}x")
    )
    blob_pulse_row.addWidget(tab.blob_pulse_label)
    blob_layout.addLayout(blob_pulse_row)

    spotify_vis_layout.addWidget(tab._blob_settings_container)

    # ==========================================
    # Helix settings container
    # ==========================================
    tab._helix_settings_container = QWidget()
    helix_layout = QVBoxLayout(tab._helix_settings_container)
    helix_layout.setContentsMargins(0, 0, 0, 0)

    helix_turns_row = QHBoxLayout()
    helix_turns_row.addWidget(QLabel("Turns:"))
    tab.helix_turns = QSpinBox()
    tab.helix_turns.setRange(2, 12)
    tab.helix_turns.setValue(tab._default_int('spotify_visualizer', 'helix_turns', 4))
    tab.helix_turns.setToolTip("Number of helix turns visible across the card width.")
    tab.helix_turns.valueChanged.connect(tab._save_settings)
    helix_turns_row.addWidget(tab.helix_turns)
    helix_turns_row.addStretch()
    helix_layout.addLayout(helix_turns_row)

    tab.helix_double = QCheckBox("Double Helix (DNA)")
    tab.helix_double.setChecked(tab._default_bool('spotify_visualizer', 'helix_double', True))
    tab.helix_double.setToolTip("Show a second strand and cross-rungs for a DNA-like appearance.")
    tab.helix_double.stateChanged.connect(tab._save_settings)
    helix_layout.addWidget(tab.helix_double)

    helix_speed_row = QHBoxLayout()
    helix_speed_row.addWidget(QLabel("Rotation Speed:"))
    tab.helix_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.helix_speed.setMinimum(0)
    tab.helix_speed.setMaximum(200)
    helix_speed_val = int(tab._default_float('spotify_visualizer', 'helix_speed', 1.0) * 100)
    tab.helix_speed.setValue(helix_speed_val)
    tab.helix_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.helix_speed.setTickInterval(25)
    tab.helix_speed.valueChanged.connect(tab._save_settings)
    helix_speed_row.addWidget(tab.helix_speed)
    tab.helix_speed_label = QLabel(f"{helix_speed_val / 100.0:.2f}x")
    tab.helix_speed.valueChanged.connect(
        lambda v: tab.helix_speed_label.setText(f"{v / 100.0:.2f}x")
    )
    helix_speed_row.addWidget(tab.helix_speed_label)
    helix_layout.addLayout(helix_speed_row)

    tab.helix_glow_enabled = QCheckBox("Enable Glow")
    tab.helix_glow_enabled.setChecked(tab._default_bool('spotify_visualizer', 'helix_glow_enabled', True))
    tab.helix_glow_enabled.setToolTip("Draw a soft glow halo around the helix strands.")
    tab.helix_glow_enabled.stateChanged.connect(tab._save_settings)
    helix_layout.addWidget(tab.helix_glow_enabled)

    helix_glow_row = QHBoxLayout()
    helix_glow_row.addWidget(QLabel("Glow Intensity:"))
    tab.helix_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.helix_glow_intensity.setMinimum(0)
    tab.helix_glow_intensity.setMaximum(100)
    helix_glow_val = int(tab._default_float('spotify_visualizer', 'helix_glow_intensity', 0.5) * 100)
    tab.helix_glow_intensity.setValue(helix_glow_val)
    tab.helix_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.helix_glow_intensity.setTickInterval(10)
    tab.helix_glow_intensity.valueChanged.connect(tab._save_settings)
    helix_glow_row.addWidget(tab.helix_glow_intensity)
    tab.helix_glow_intensity_label = QLabel(f"{helix_glow_val}%")
    tab.helix_glow_intensity.valueChanged.connect(
        lambda v: tab.helix_glow_intensity_label.setText(f"{v}%")
    )
    helix_glow_row.addWidget(tab.helix_glow_intensity_label)
    helix_layout.addLayout(helix_glow_row)

    helix_growth_row = QHBoxLayout()
    helix_growth_row.addWidget(QLabel("Card Height:"))
    tab.helix_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.helix_growth.setMinimum(100)
    tab.helix_growth.setMaximum(400)
    helix_growth_val = int(tab._default_float('spotify_visualizer', 'helix_growth', 2.0) * 100)
    tab.helix_growth.setValue(helix_growth_val)
    tab.helix_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.helix_growth.setTickInterval(50)
    tab.helix_growth.valueChanged.connect(tab._save_settings)
    helix_growth_row.addWidget(tab.helix_growth)
    tab.helix_growth_label = QLabel(f"{helix_growth_val / 100.0:.1f}x")
    tab.helix_growth.valueChanged.connect(
        lambda v: tab.helix_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    helix_growth_row.addWidget(tab.helix_growth_label)
    helix_layout.addLayout(helix_growth_row)

    spotify_vis_layout.addWidget(tab._helix_settings_container)

    # Add card height growth sliders to starfield and blob containers
    # --- Starfield height growth ---
    star_growth_row = QHBoxLayout()
    star_growth_row.addWidget(QLabel("Card Height:"))
    tab.starfield_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.starfield_growth.setMinimum(100)
    tab.starfield_growth.setMaximum(400)
    star_growth_val = int(tab._default_float('spotify_visualizer', 'starfield_growth', 2.0) * 100)
    tab.starfield_growth.setValue(star_growth_val)
    tab.starfield_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.starfield_growth.setTickInterval(50)
    tab.starfield_growth.valueChanged.connect(tab._save_settings)
    star_growth_row.addWidget(tab.starfield_growth)
    tab.starfield_growth_label = QLabel(f"{star_growth_val / 100.0:.1f}x")
    tab.starfield_growth.valueChanged.connect(
        lambda v: tab.starfield_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    star_growth_row.addWidget(tab.starfield_growth_label)
    star_layout.addLayout(star_growth_row)

    # --- Blob height growth ---
    blob_growth_row = QHBoxLayout()
    blob_growth_row.addWidget(QLabel("Card Height:"))
    tab.blob_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_growth.setMinimum(100)
    tab.blob_growth.setMaximum(400)
    blob_growth_val = int(tab._default_float('spotify_visualizer', 'blob_growth', 2.5) * 100)
    tab.blob_growth.setValue(blob_growth_val)
    tab.blob_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_growth.setTickInterval(50)
    tab.blob_growth.valueChanged.connect(tab._save_settings)
    blob_growth_row.addWidget(tab.blob_growth)
    tab.blob_growth_label = QLabel(f"{blob_growth_val / 100.0:.1f}x")
    tab.blob_growth.valueChanged.connect(
        lambda v: tab.blob_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    blob_growth_row.addWidget(tab.blob_growth_label)
    blob_layout.addLayout(blob_growth_row)

    # Initial visibility
    tab._update_vis_mode_sections()

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

    # Visualizer mode combobox
    saved_mode = tab._config_str('spotify_visualizer', spotify_vis_config, 'mode', 'spectrum')
    mode_idx = tab.spotify_vis_type_combo.findData(saved_mode)
    if mode_idx >= 0:
        tab.spotify_vis_type_combo.setCurrentIndex(mode_idx)

    # Per-mode settings: Oscilloscope
    if hasattr(tab, 'osc_glow_enabled'):
        tab.osc_glow_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'osc_glow_enabled', True)
        )
    if hasattr(tab, 'osc_glow_intensity'):
        osc_glow_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_glow_intensity', 0.5) * 100)
        tab.osc_glow_intensity.setValue(max(0, min(100, osc_glow_val)))
        tab.osc_glow_intensity_label.setText(f"{osc_glow_val}%")
    if hasattr(tab, 'osc_reactive_glow'):
        tab.osc_reactive_glow.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'osc_reactive_glow', True)
        )

    # Per-mode settings: Starfield
    if hasattr(tab, 'star_travel_speed'):
        star_speed_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'star_travel_speed', 0.5) * 100)
        tab.star_travel_speed.setValue(max(0, min(200, star_speed_val)))
        tab.star_travel_speed_label.setText(f"{star_speed_val / 100.0:.2f}x")
    if hasattr(tab, 'star_reactivity'):
        star_react_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'star_reactivity', 1.0) * 100)
        tab.star_reactivity.setValue(max(0, min(200, star_react_val)))
        tab.star_reactivity_label.setText(f"{star_react_val / 100.0:.2f}x")
    if hasattr(tab, 'starfield_growth'):
        star_growth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'starfield_growth', 2.0) * 100)
        tab.starfield_growth.setValue(max(100, min(400, star_growth_val)))
        tab.starfield_growth_label.setText(f"{star_growth_val / 100.0:.1f}x")

    # Per-mode settings: Blob
    if hasattr(tab, 'blob_pulse'):
        blob_pulse_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_pulse', 1.0) * 100)
        tab.blob_pulse.setValue(max(0, min(200, blob_pulse_val)))
        tab.blob_pulse_label.setText(f"{blob_pulse_val / 100.0:.2f}x")
    if hasattr(tab, 'blob_growth'):
        blob_growth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_growth', 2.5) * 100)
        tab.blob_growth.setValue(max(100, min(400, blob_growth_val)))
        tab.blob_growth_label.setText(f"{blob_growth_val / 100.0:.1f}x")

    # Per-mode settings: Helix
    if hasattr(tab, 'helix_turns'):
        tab.helix_turns.setValue(
            tab._config_int('spotify_visualizer', spotify_vis_config, 'helix_turns', 4)
        )
    if hasattr(tab, 'helix_double'):
        tab.helix_double.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'helix_double', True)
        )
    if hasattr(tab, 'helix_speed'):
        helix_speed_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'helix_speed', 1.0) * 100)
        tab.helix_speed.setValue(max(0, min(200, helix_speed_val)))
        tab.helix_speed_label.setText(f"{helix_speed_val / 100.0:.2f}x")
    if hasattr(tab, 'helix_glow_enabled'):
        tab.helix_glow_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'helix_glow_enabled', True)
        )
    if hasattr(tab, 'helix_glow_intensity'):
        helix_glow_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'helix_glow_intensity', 0.5) * 100)
        tab.helix_glow_intensity.setValue(max(0, min(100, helix_glow_val)))
        tab.helix_glow_intensity_label.setText(f"{helix_glow_val}%")
    if hasattr(tab, 'helix_growth'):
        helix_growth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'helix_growth', 2.0) * 100)
        tab.helix_growth.setValue(max(100, min(400, helix_growth_val)))
        tab.helix_growth_label.setText(f"{helix_growth_val / 100.0:.1f}x")

    # Update per-mode section visibility
    tab._update_vis_mode_sections()

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
        'mode': getattr(tab, 'spotify_vis_type_combo', None) and tab.spotify_vis_type_combo.currentData() or 'spectrum',
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
        'osc_glow_enabled': getattr(tab, 'osc_glow_enabled', None) and tab.osc_glow_enabled.isChecked(),
        'osc_glow_intensity': (getattr(tab, 'osc_glow_intensity', None) and tab.osc_glow_intensity.value() or 50) / 100.0,
        'osc_reactive_glow': getattr(tab, 'osc_reactive_glow', None) and tab.osc_reactive_glow.isChecked(),
        'star_travel_speed': (getattr(tab, 'star_travel_speed', None) and tab.star_travel_speed.value() or 50) / 100.0,
        'star_reactivity': (getattr(tab, 'star_reactivity', None) and tab.star_reactivity.value() or 100) / 100.0,
        'blob_pulse': (getattr(tab, 'blob_pulse', None) and tab.blob_pulse.value() or 100) / 100.0,
        'helix_turns': getattr(tab, 'helix_turns', None) and tab.helix_turns.value() or 4,
        'helix_double': getattr(tab, 'helix_double', None) and tab.helix_double.isChecked(),
        'helix_speed': (getattr(tab, 'helix_speed', None) and tab.helix_speed.value() or 100) / 100.0,
        'helix_glow_enabled': getattr(tab, 'helix_glow_enabled', None) and tab.helix_glow_enabled.isChecked(),
        'helix_glow_intensity': (getattr(tab, 'helix_glow_intensity', None) and tab.helix_glow_intensity.value() or 50) / 100.0,
        'starfield_growth': (getattr(tab, 'starfield_growth', None) and tab.starfield_growth.value() or 200) / 100.0,
        'blob_growth': (getattr(tab, 'blob_growth', None) and tab.blob_growth.value() or 250) / 100.0,
        'helix_growth': (getattr(tab, 'helix_growth', None) and tab.helix_growth.value() or 200) / 100.0,
    }

    tab._update_spotify_vis_sensitivity_enabled_state()
    tab._update_spotify_vis_floor_enabled_state()

    return media_config, spotify_vis_config
