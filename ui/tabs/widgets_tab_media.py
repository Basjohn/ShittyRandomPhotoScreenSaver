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


def _update_media_enabled_visibility(tab) -> None:
    """Show/hide all media controls based on media_enabled checkbox."""
    enabled = getattr(tab, 'media_enabled', None) and tab.media_enabled.isChecked()
    container = getattr(tab, '_media_controls_container', None)
    if container is not None:
        container.setVisible(bool(enabled))


def _update_spotify_vis_enabled_visibility(tab) -> None:
    """Show/hide all visualizer controls based on spotify_vis_enabled checkbox."""
    enabled = getattr(tab, 'spotify_vis_enabled', None) and tab.spotify_vis_enabled.isChecked()
    container = getattr(tab, '_spotify_vis_controls_container', None)
    if container is not None:
        container.setVisible(bool(enabled))


def _update_ghost_visibility(tab) -> None:
    """Show/hide ghost opacity/decay sliders based on ghost_enabled checkbox."""
    show = getattr(tab, 'spotify_vis_ghost_enabled', None) and tab.spotify_vis_ghost_enabled.isChecked()
    container = getattr(tab, '_ghost_sub_container', None)
    if container is not None:
        container.setVisible(bool(show))


def _update_media_bg_visibility(tab) -> None:
    """Show/hide media background styling controls based on show_background checkbox."""
    show = getattr(tab, 'media_show_background', None) and tab.media_show_background.isChecked()
    container = getattr(tab, '_media_bg_container', None)
    if container is not None:
        container.setVisible(bool(show))


def _qcolor_to_list(qc, fallback: list) -> list:
    """Convert a QColor to an RGBA list, or return fallback."""
    if qc is None:
        return list(fallback)
    try:
        return [qc.red(), qc.green(), qc.blue(), qc.alpha()]
    except Exception:
        return list(fallback)


def _update_osc_multi_line_visibility(tab) -> None:
    """Show/hide multi-line sub-controls based on checkbox and line count."""
    enabled = getattr(tab, 'osc_multi_line', None) and tab.osc_multi_line.isChecked()
    container = getattr(tab, '_osc_multi_container', None)
    if container is not None:
        container.setVisible(bool(enabled))
    # Line 3 controls only visible when count == 3
    line_count = getattr(tab, 'osc_line_count', None)
    show_l3 = enabled and line_count is not None and line_count.value() >= 3
    for w in (getattr(tab, '_osc_line3_label', None), getattr(tab, '_osc_l3_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l3))


def _update_sine_multi_line_visibility(tab) -> None:
    """Show/hide sine wave multi-line sub-controls based on checkbox and line count."""
    enabled = getattr(tab, 'sine_multi_line', None) and tab.sine_multi_line.isChecked()
    container = getattr(tab, '_sine_multi_container', None)
    if container is not None:
        container.setVisible(bool(enabled))
    # Line 3 controls only visible when count == 3
    line_count = getattr(tab, 'sine_line_count_slider', None)
    show_l3 = enabled and line_count is not None and line_count.value() >= 3
    for w in (getattr(tab, '_sine_line3_label', None), getattr(tab, '_sine_l3_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l3))


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

    # Container for all media controls gated by enable checkbox
    tab._media_controls_container = QWidget()
    _media_ctrl_layout = QVBoxLayout(tab._media_controls_container)
    _media_ctrl_layout.setContentsMargins(0, 0, 0, 0)
    _media_ctrl_layout.setSpacing(4)

    media_info = QLabel(
        "This widget is display-only and non-interactive. Transport controls will "
        "only be active when explicitly enabled via input settings (hard-exit / Ctrl mode)."
    )
    media_info.setWordWrap(True)
    media_info.setStyleSheet("color: #aaaaaa; font-size: 11px;")
    _media_ctrl_layout.addWidget(media_info)

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
    _media_ctrl_layout.addLayout(media_pos_row)

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
    _media_ctrl_layout.addLayout(media_disp_row)

    media_font_family_row = QHBoxLayout()
    media_font_family_row.addWidget(QLabel("Font:"))
    tab.media_font_combo = QFontComboBox()
    default_media_font = tab._default_str('media', 'font_family', 'Segoe UI')
    tab.media_font_combo.setCurrentFont(QFont(default_media_font))
    tab.media_font_combo.setMinimumWidth(220)
    tab.media_font_combo.currentFontChanged.connect(tab._save_settings)
    media_font_family_row.addWidget(tab.media_font_combo)
    media_font_family_row.addStretch()
    _media_ctrl_layout.addLayout(media_font_family_row)

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
    _media_ctrl_layout.addLayout(media_font_row)

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
    _media_ctrl_layout.addLayout(media_margin_row)

    media_color_row = QHBoxLayout()
    media_color_row.addWidget(QLabel("Text Color:"))
    tab.media_color_btn = QPushButton("Choose Color...")
    tab.media_color_btn.clicked.connect(tab._choose_media_color)
    media_color_row.addWidget(tab.media_color_btn)
    media_color_row.addStretch()
    _media_ctrl_layout.addLayout(media_color_row)

    tab.media_show_background = QCheckBox("Show Background Frame")
    tab.media_show_background.setChecked(tab._default_bool('media', 'show_background', True))
    tab.media_show_background.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_show_background)

    # Background sub-controls container (shown only when show_background is checked)
    tab._media_bg_container = QWidget()
    _mbg_layout = QVBoxLayout(tab._media_bg_container)
    _mbg_layout.setContentsMargins(0, 0, 0, 0)
    _mbg_layout.setSpacing(4)

    tab.media_intense_shadow = QCheckBox("Intense Shadows")
    tab.media_intense_shadow.setChecked(tab._default_bool('media', 'intense_shadow', True))
    tab.media_intense_shadow.setToolTip(
        "Doubles shadow blur, opacity, and offset for dramatic effect on large displays."
    )
    tab.media_intense_shadow.stateChanged.connect(tab._save_settings)
    _mbg_layout.addWidget(tab.media_intense_shadow)

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
    _mbg_layout.addLayout(media_opacity_row)

    media_bg_color_row = QHBoxLayout()
    media_bg_color_row.addWidget(QLabel("Background Color:"))
    tab.media_bg_color_btn = QPushButton("Choose Color...")
    tab.media_bg_color_btn.clicked.connect(tab._choose_media_bg_color)
    media_bg_color_row.addWidget(tab.media_bg_color_btn)
    media_bg_color_row.addStretch()
    _mbg_layout.addLayout(media_bg_color_row)

    media_border_color_row = QHBoxLayout()
    media_border_color_row.addWidget(QLabel("Border Color:"))
    tab.media_border_color_btn = QPushButton("Choose Color...")
    tab.media_border_color_btn.clicked.connect(tab._choose_media_border_color)
    media_border_color_row.addWidget(tab.media_border_color_btn)
    media_border_color_row.addStretch()
    _mbg_layout.addLayout(media_border_color_row)

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
    _mbg_layout.addLayout(media_border_opacity_row)

    _media_ctrl_layout.addWidget(tab._media_bg_container)
    tab.media_show_background.stateChanged.connect(lambda: _update_media_bg_visibility(tab))
    _update_media_bg_visibility(tab)

    media_volume_fill_row = QHBoxLayout()
    media_volume_fill_row.addWidget(QLabel("Volume Fill Color:"))
    tab.media_volume_fill_color_btn = QPushButton("Choose Color...")
    tab.media_volume_fill_color_btn.clicked.connect(tab._choose_media_volume_fill_color)
    media_volume_fill_row.addWidget(tab.media_volume_fill_color_btn)
    media_volume_fill_row.addStretch()
    _media_ctrl_layout.addLayout(media_volume_fill_row)

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
    _media_ctrl_layout.addLayout(media_artwork_row)

    tab.media_rounded_artwork = QCheckBox("Rounded Artwork Border")
    tab.media_rounded_artwork.setChecked(
        tab._default_bool('media', 'rounded_artwork_border', True)
    )
    tab.media_rounded_artwork.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_rounded_artwork)

    tab.media_show_header_frame = QCheckBox("Header Border Around Logo + Title")
    tab.media_show_header_frame.setChecked(
        tab._default_bool('media', 'show_header_frame', True)
    )
    tab.media_show_header_frame.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_show_header_frame)

    tab.media_show_controls = QCheckBox("Show Transport Controls")
    tab.media_show_controls.setChecked(
        tab._default_bool('media', 'show_controls', True)
    )
    tab.media_show_controls.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_show_controls)

    tab.media_spotify_volume_enabled = QCheckBox("Enable Spotify Volume Slider")
    tab.media_spotify_volume_enabled.setToolTip(
        "Show a slim vertical volume slider next to the Spotify card when Core Audio/pycaw is available. "
        "The slider only affects the Spotify session volume and is gated by hard-exit / Ctrl interaction modes."
    )
    tab.media_spotify_volume_enabled.setChecked(
        tab._default_bool('media', 'spotify_volume_enabled', True)
    )
    tab.media_spotify_volume_enabled.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_spotify_volume_enabled)

    tab.media_mute_button_enabled = QCheckBox("Enable System Mute Button")
    tab.media_mute_button_enabled.setToolTip(
        "Show a small mute toggle button near the media card. "
        "Single-click toggles system-wide mute on/off (requires pycaw/Core Audio)."
    )
    tab.media_mute_button_enabled.setChecked(
        tab._default_bool('media', 'mute_button_enabled', False)
    )
    tab.media_mute_button_enabled.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_mute_button_enabled)

    media_layout.addWidget(tab._media_controls_container)
    tab.media_enabled.stateChanged.connect(lambda: _update_media_enabled_visibility(tab))
    _update_media_enabled_visibility(tab)

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

    # Container for all visualizer controls gated by enable checkbox
    tab._spotify_vis_controls_container = QWidget()
    _svctl = QVBoxLayout(tab._spotify_vis_controls_container)
    _svctl.setContentsMargins(0, 0, 0, 0)
    _svctl.setSpacing(4)

    # --- Visualizer Type Selector ---
    vis_type_row = QHBoxLayout()
    vis_type_row.addWidget(QLabel("Visualizer Type:"))
    tab.spotify_vis_type_combo = QComboBox()
    tab.spotify_vis_type_combo.setMinimumWidth(160)
    import os as _os
    _dev_features = _os.getenv('SRPSS_ENABLE_DEV', 'false').lower() == 'true'
    tab.spotify_vis_type_combo.addItem("Spectrum", "spectrum")
    tab.spotify_vis_type_combo.addItem("Oscilloscope", "oscilloscope")
    if _dev_features:
        tab.spotify_vis_type_combo.addItem("Starfield", "starfield")
    tab.spotify_vis_type_combo.addItem("Blob", "blob")
    tab.spotify_vis_type_combo.addItem("Sine Waves", "sine_wave")

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
    _svctl.addLayout(vis_type_row)

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

    tab._ghost_sub_container = QWidget()
    _ghost_layout = QVBoxLayout(tab._ghost_sub_container)
    _ghost_layout.setContentsMargins(0, 0, 0, 0)
    _ghost_layout.setSpacing(4)

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
    _ghost_layout.addLayout(spotify_vis_ghost_opacity_row)

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
    _ghost_layout.addLayout(spotify_vis_ghost_decay_row)

    spectrum_layout.addWidget(tab._ghost_sub_container)
    tab.spotify_vis_ghost_enabled.stateChanged.connect(lambda: _update_ghost_visibility(tab))
    _update_ghost_visibility(tab)

    # Single Piece Mode (solid bars, no segment gaps)
    tab.spectrum_single_piece = QCheckBox("Single Piece Mode")
    tab.spectrum_single_piece.setChecked(
        tab._default_bool('spotify_visualizer', 'spectrum_single_piece', False)
    )
    tab.spectrum_single_piece.setToolTip(
        "Render solid continuous bars instead of segmented blocks. "
        "Produces a clean pillar look while keeping all other bar behaviour."
    )
    tab.spectrum_single_piece.stateChanged.connect(tab._save_settings)
    spectrum_layout.addWidget(tab.spectrum_single_piece)

    # Curved Bar Profile (shifts peak shape outward for a curved look)
    tab.spectrum_curved_profile = QCheckBox("Curved Bar Profile")
    tab.spectrum_curved_profile.setChecked(
        tab._default_bool('spotify_visualizer', 'spectrum_curved_profile', False)
    )
    tab.spectrum_curved_profile.setToolTip(
        "Shifts the mirrored peak bars outward so each ridge curves "
        "(left highest, middle slightly lower, right slightly lower) "
        "while preserving total energy and reactivity."
    )
    tab.spectrum_curved_profile.stateChanged.connect(tab._save_settings)
    spectrum_layout.addWidget(tab.spectrum_curved_profile)

    # Spectrum card height growth slider (1.0 .. 3.0)
    spectrum_growth_row = QHBoxLayout()
    spectrum_growth_row.addWidget(QLabel("Card Height:"))
    tab.spectrum_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_growth.setMinimum(100)
    tab.spectrum_growth.setMaximum(400)
    spectrum_growth_val = int(tab._default_float('spotify_visualizer', 'spectrum_growth', 1.0) * 100)
    tab.spectrum_growth.setValue(max(100, min(400, spectrum_growth_val)))
    tab.spectrum_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_growth.setTickInterval(50)
    tab.spectrum_growth.setToolTip("Height multiplier for the spectrum card. 100% = current default height.")
    tab.spectrum_growth.valueChanged.connect(tab._save_settings)
    spectrum_growth_row.addWidget(tab.spectrum_growth)
    tab.spectrum_growth_label = QLabel(f"{spectrum_growth_val / 100.0:.1f}x")
    tab.spectrum_growth.valueChanged.connect(
        lambda v: tab.spectrum_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    spectrum_growth_row.addWidget(tab.spectrum_growth_label)
    spectrum_layout.addLayout(spectrum_growth_row)

    _svctl.addWidget(tab._spectrum_settings_container)

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

    # Sensitivity slider (0.5x .. 10.0x, default 3.0x)
    osc_sens_row = QHBoxLayout()
    osc_sens_row.addWidget(QLabel("Sensitivity:"))
    tab.osc_sensitivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_sensitivity.setMinimum(5)
    tab.osc_sensitivity.setMaximum(100)
    osc_sens_val = int(tab._default_float('spotify_visualizer', 'osc_sensitivity', 3.0) * 10)
    tab.osc_sensitivity.setValue(max(5, min(100, osc_sens_val)))
    tab.osc_sensitivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_sensitivity.setTickInterval(10)
    tab.osc_sensitivity.valueChanged.connect(tab._save_settings)
    osc_sens_row.addWidget(tab.osc_sensitivity)
    tab.osc_sensitivity_label = QLabel(f"{osc_sens_val / 10.0:.1f}x")
    tab.osc_sensitivity.valueChanged.connect(
        lambda v: tab.osc_sensitivity_label.setText(f"{v / 10.0:.1f}x")
    )
    osc_sens_row.addWidget(tab.osc_sensitivity_label)
    osc_layout.addLayout(osc_sens_row)

    # Smoothing slider (0% = jagged, 100% = smooth curves)
    osc_smooth_row = QHBoxLayout()
    osc_smooth_row.addWidget(QLabel("Smoothing:"))
    tab.osc_smoothing = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_smoothing.setMinimum(0)
    tab.osc_smoothing.setMaximum(100)
    osc_smooth_val = int(tab._default_float('spotify_visualizer', 'osc_smoothing', 0.7) * 100)
    tab.osc_smoothing.setValue(max(0, min(100, osc_smooth_val)))
    tab.osc_smoothing.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_smoothing.setTickInterval(10)
    tab.osc_smoothing.valueChanged.connect(tab._save_settings)
    osc_smooth_row.addWidget(tab.osc_smoothing)
    tab.osc_smoothing_label = QLabel(f"{osc_smooth_val}%")
    tab.osc_smoothing.valueChanged.connect(
        lambda v: tab.osc_smoothing_label.setText(f"{v}%")
    )
    osc_smooth_row.addWidget(tab.osc_smoothing_label)
    osc_layout.addLayout(osc_smooth_row)

    # Speed slider (10% = slow waveform changes, 100% = real-time)
    osc_speed_row = QHBoxLayout()
    osc_speed_row.addWidget(QLabel("Speed:"))
    tab.osc_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_speed.setMinimum(1)
    tab.osc_speed.setMaximum(100)
    osc_speed_val = int(tab._default_float('spotify_visualizer', 'osc_speed', 1.0) * 100)
    tab.osc_speed.setValue(max(1, min(100, osc_speed_val)))
    tab.osc_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_speed.setTickInterval(10)
    tab.osc_speed.setToolTip("Controls how quickly the waveform updates. 100% = real-time, lower = smoother/slower transitions.")
    tab.osc_speed.valueChanged.connect(tab._save_settings)
    osc_speed_row.addWidget(tab.osc_speed)
    tab.osc_speed_label = QLabel(f"{osc_speed_val}%")
    tab.osc_speed.valueChanged.connect(
        lambda v: tab.osc_speed_label.setText(f"{v}%")
    )
    osc_speed_row.addWidget(tab.osc_speed_label)
    osc_layout.addLayout(osc_speed_row)

    tab.osc_line_dim = QCheckBox("Dim Lines 2/3 Glow")
    tab.osc_line_dim.setChecked(tab._default_bool('spotify_visualizer', 'osc_line_dim', False))
    tab.osc_line_dim.setToolTip("When enabled, lines 2 and 3 have slightly reduced glow to let the primary line stand out.")
    tab.osc_line_dim.stateChanged.connect(tab._save_settings)
    osc_layout.addWidget(tab.osc_line_dim)

    # Line Offset Bias slider (0..100, maps to 0.0..1.0, multi-line only)
    osc_lob_row = QHBoxLayout()
    osc_lob_row.addWidget(QLabel("Line Offset Bias:"))
    tab.osc_line_offset_bias = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_line_offset_bias.setMinimum(0)
    tab.osc_line_offset_bias.setMaximum(100)
    osc_lob_val = int(tab._default_float('spotify_visualizer', 'osc_line_offset_bias', 0.0) * 100)
    tab.osc_line_offset_bias.setValue(osc_lob_val)
    tab.osc_line_offset_bias.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_line_offset_bias.setTickInterval(10)
    tab.osc_line_offset_bias.setToolTip(
        "Increases base vertical spread between lines and per-band energy reliance "
        "(bass/mid/treble). Multi-line mode only. 0% = energy-only spacing, "
        "100% = maximum spread with strong per-band separation."
    )
    tab.osc_line_offset_bias.valueChanged.connect(tab._save_settings)
    osc_lob_row.addWidget(tab.osc_line_offset_bias)
    tab.osc_line_offset_bias_label = QLabel(f"{osc_lob_val}%")
    tab.osc_line_offset_bias.valueChanged.connect(
        lambda v: tab.osc_line_offset_bias_label.setText(f"{v}%")
    )
    osc_lob_row.addWidget(tab.osc_line_offset_bias_label)
    osc_layout.addLayout(osc_lob_row)

    osc_vshift_row = QHBoxLayout()
    osc_vshift_row.addWidget(QLabel("Vertical Shift:"))
    tab.osc_vertical_shift = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_vertical_shift.setMinimum(-50)
    tab.osc_vertical_shift.setMaximum(200)
    osc_vshift_val = int(tab._default_int('spotify_visualizer', 'osc_vertical_shift', 0))
    tab.osc_vertical_shift.setValue(max(-50, min(200, osc_vshift_val)))
    tab.osc_vertical_shift.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_vertical_shift.setTickInterval(25)
    tab.osc_vertical_shift.setToolTip(
        "Controls vertical spread between lines. 0 = all aligned, "
        "100 = default spread, 200 = max spread, negative = lines cross. Multi-line only."
    )
    tab.osc_vertical_shift.valueChanged.connect(tab._save_settings)
    osc_vshift_row.addWidget(tab.osc_vertical_shift)
    tab.osc_vertical_shift_label = QLabel(f"{osc_vshift_val}")
    tab.osc_vertical_shift.valueChanged.connect(
        lambda v: tab.osc_vertical_shift_label.setText(f"{v}")
    )
    osc_vshift_row.addWidget(tab.osc_vertical_shift_label)
    osc_layout.addLayout(osc_vshift_row)

    # Line colour picker (separate from glow)
    osc_line_color_row = QHBoxLayout()
    osc_line_color_row.addWidget(QLabel("Line Color:"))
    tab.osc_line_color_btn = QPushButton("Choose Color...")
    tab.osc_line_color_btn.clicked.connect(tab._choose_osc_line_color)
    osc_line_color_row.addWidget(tab.osc_line_color_btn)
    osc_line_color_row.addStretch()
    osc_layout.addLayout(osc_line_color_row)

    # Glow colour picker
    osc_glow_color_row = QHBoxLayout()
    osc_glow_color_row.addWidget(QLabel("Glow Color:"))
    tab.osc_glow_color_btn = QPushButton("Choose Color...")
    tab.osc_glow_color_btn.clicked.connect(tab._choose_osc_glow_color)
    osc_glow_color_row.addWidget(tab.osc_glow_color_btn)
    osc_glow_color_row.addStretch()
    osc_layout.addLayout(osc_glow_color_row)

    # Multi-line mode
    tab.osc_multi_line = QCheckBox("Multi-Line Mode (up to 3 lines)")
    tab.osc_multi_line.setChecked(tab._default_int('spotify_visualizer', 'osc_line_count', 1) > 1)
    tab.osc_multi_line.setToolTip("Enable additional waveform lines with different oscillation distributions.")
    tab.osc_multi_line.stateChanged.connect(tab._save_settings)
    tab.osc_multi_line.stateChanged.connect(lambda: _update_osc_multi_line_visibility(tab))
    osc_layout.addWidget(tab.osc_multi_line)

    # Multi-line sub-container (shown only when multi-line enabled)
    tab._osc_multi_container = QWidget()
    ml_layout = QVBoxLayout(tab._osc_multi_container)
    ml_layout.setContentsMargins(16, 0, 0, 0)

    # Line count spinner
    osc_line_count_row = QHBoxLayout()
    osc_line_count_row.addWidget(QLabel("Line Count:"))
    tab.osc_line_count = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_line_count.setMinimum(2)
    tab.osc_line_count.setMaximum(3)
    tab.osc_line_count.setValue(max(2, tab._default_int('spotify_visualizer', 'osc_line_count', 1)))
    tab.osc_line_count.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_line_count.setTickInterval(1)
    tab.osc_line_count.valueChanged.connect(tab._save_settings)
    tab.osc_line_count.valueChanged.connect(lambda: _update_osc_multi_line_visibility(tab))
    osc_line_count_row.addWidget(tab.osc_line_count)
    tab.osc_line_count_label = QLabel(str(max(2, tab._default_int('spotify_visualizer', 'osc_line_count', 1))))
    tab.osc_line_count.valueChanged.connect(
        lambda v: tab.osc_line_count_label.setText(str(v))
    )
    osc_line_count_row.addWidget(tab.osc_line_count_label)
    ml_layout.addLayout(osc_line_count_row)

    # Line 2 colours
    ml_layout.addWidget(QLabel("Line 2:"))
    osc_l2_row = QHBoxLayout()
    tab.osc_line2_color_btn = QPushButton("Line Color...")
    tab.osc_line2_color_btn.clicked.connect(tab._choose_osc_line2_color)
    osc_l2_row.addWidget(tab.osc_line2_color_btn)
    tab.osc_line2_glow_btn = QPushButton("Glow Color...")
    tab.osc_line2_glow_btn.clicked.connect(tab._choose_osc_line2_glow_color)
    osc_l2_row.addWidget(tab.osc_line2_glow_btn)
    osc_l2_row.addStretch()
    ml_layout.addLayout(osc_l2_row)

    # Line 3 colours (only visible when line_count == 3)
    tab._osc_line3_label = QLabel("Line 3:")
    ml_layout.addWidget(tab._osc_line3_label)
    tab._osc_l3_row_widget = QWidget()
    osc_l3_row = QHBoxLayout(tab._osc_l3_row_widget)
    osc_l3_row.setContentsMargins(0, 0, 0, 0)
    tab.osc_line3_color_btn = QPushButton("Line Color...")
    tab.osc_line3_color_btn.clicked.connect(tab._choose_osc_line3_color)
    osc_l3_row.addWidget(tab.osc_line3_color_btn)
    tab.osc_line3_glow_btn = QPushButton("Glow Color...")
    tab.osc_line3_glow_btn.clicked.connect(tab._choose_osc_line3_glow_color)
    osc_l3_row.addWidget(tab.osc_line3_glow_btn)
    osc_l3_row.addStretch()
    ml_layout.addWidget(tab._osc_l3_row_widget)

    osc_layout.addWidget(tab._osc_multi_container)
    _update_osc_multi_line_visibility(tab)

    # Oscilloscope card height growth slider (1.0 .. 3.0)
    osc_growth_row = QHBoxLayout()
    osc_growth_row.addWidget(QLabel("Card Height:"))
    tab.osc_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_growth.setMinimum(100)
    tab.osc_growth.setMaximum(400)
    osc_growth_val = int(tab._default_float('spotify_visualizer', 'osc_growth', 1.0) * 100)
    tab.osc_growth.setValue(max(100, min(400, osc_growth_val)))
    tab.osc_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_growth.setTickInterval(50)
    tab.osc_growth.setToolTip("Height multiplier for the oscilloscope card.")
    tab.osc_growth.valueChanged.connect(tab._save_settings)
    osc_growth_row.addWidget(tab.osc_growth)
    tab.osc_growth_label = QLabel(f"{osc_growth_val / 100.0:.1f}x")
    tab.osc_growth.valueChanged.connect(
        lambda v: tab.osc_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    osc_growth_row.addWidget(tab.osc_growth_label)
    osc_layout.addLayout(osc_growth_row)

    _svctl.addWidget(tab._osc_settings_container)

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

    # Nebula tint colour pickers
    nebula_tint_row = QHBoxLayout()
    nebula_tint_row.addWidget(QLabel("Nebula Tint 1:"))
    tab.nebula_tint1_btn = QPushButton("Choose Color...")
    tab.nebula_tint1_btn.clicked.connect(tab._choose_nebula_tint1)
    nebula_tint_row.addWidget(tab.nebula_tint1_btn)
    nebula_tint_row.addWidget(QLabel("Tint 2:"))
    tab.nebula_tint2_btn = QPushButton("Choose Color...")
    tab.nebula_tint2_btn.clicked.connect(tab._choose_nebula_tint2)
    nebula_tint_row.addWidget(tab.nebula_tint2_btn)
    nebula_tint_row.addStretch()
    star_layout.addLayout(nebula_tint_row)

    # Nebula colour cycle speed
    nebula_speed_row = QHBoxLayout()
    nebula_speed_row.addWidget(QLabel("Nebula Cycle:"))
    tab.nebula_cycle_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.nebula_cycle_speed.setMinimum(0)
    tab.nebula_cycle_speed.setMaximum(100)
    nebula_spd_val = int(tab._default_float('spotify_visualizer', 'nebula_cycle_speed', 0.3) * 100)
    tab.nebula_cycle_speed.setValue(nebula_spd_val)
    tab.nebula_cycle_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.nebula_cycle_speed.setTickInterval(10)
    tab.nebula_cycle_speed.setToolTip("Speed at which nebula colours cycle between Tint 1 and Tint 2. 0 = static.")
    tab.nebula_cycle_speed.valueChanged.connect(tab._save_settings)
    nebula_speed_row.addWidget(tab.nebula_cycle_speed)
    tab.nebula_cycle_speed_label = QLabel(f"{nebula_spd_val}%")
    tab.nebula_cycle_speed.valueChanged.connect(
        lambda v: tab.nebula_cycle_speed_label.setText(f"{v}%")
    )
    nebula_speed_row.addWidget(tab.nebula_cycle_speed_label)
    star_layout.addLayout(nebula_speed_row)

    _svctl.addWidget(tab._starfield_settings_container)

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

    tab.blob_reactive_glow = QCheckBox("Reactive Glow")
    tab.blob_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'blob_reactive_glow', True))
    tab.blob_reactive_glow.setToolTip("Outer glow pulses with audio energy.")
    tab.blob_reactive_glow.stateChanged.connect(tab._save_settings)
    blob_layout.addWidget(tab.blob_reactive_glow)

    # Blob colour pickers
    blob_fill_color_row = QHBoxLayout()
    blob_fill_color_row.addWidget(QLabel("Fill Color:"))
    tab.blob_fill_color_btn = QPushButton("Choose Color...")
    tab.blob_fill_color_btn.clicked.connect(tab._choose_blob_fill_color)
    blob_fill_color_row.addWidget(tab.blob_fill_color_btn)
    blob_fill_color_row.addStretch()
    blob_layout.addLayout(blob_fill_color_row)

    blob_edge_color_row = QHBoxLayout()
    blob_edge_color_row.addWidget(QLabel("Edge Color:"))
    tab.blob_edge_color_btn = QPushButton("Choose Color...")
    tab.blob_edge_color_btn.clicked.connect(tab._choose_blob_edge_color)
    blob_edge_color_row.addWidget(tab.blob_edge_color_btn)
    blob_edge_color_row.addStretch()
    blob_layout.addLayout(blob_edge_color_row)

    blob_glow_color_row = QHBoxLayout()
    blob_glow_color_row.addWidget(QLabel("Glow Color:"))
    tab.blob_glow_color_btn = QPushButton("Choose Color...")
    tab.blob_glow_color_btn.clicked.connect(tab._choose_blob_glow_color)
    blob_glow_color_row.addWidget(tab.blob_glow_color_btn)
    blob_glow_color_row.addStretch()
    blob_layout.addLayout(blob_glow_color_row)

    blob_outline_color_row = QHBoxLayout()
    blob_outline_color_row.addWidget(QLabel("Outline Color:"))
    tab.blob_outline_color_btn = QPushButton("Choose Color...")
    tab.blob_outline_color_btn.clicked.connect(tab._choose_blob_outline_color)
    blob_outline_color_row.addWidget(tab.blob_outline_color_btn)
    blob_outline_color_row.addStretch()
    blob_layout.addLayout(blob_outline_color_row)

    # Blob card width slider (0.3 .. 1.0)
    blob_width_row = QHBoxLayout()
    blob_width_row.addWidget(QLabel("Card Width:"))
    tab.blob_width = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_width.setMinimum(30)
    tab.blob_width.setMaximum(100)
    blob_width_val = int(tab._default_float('spotify_visualizer', 'blob_width', 1.0) * 100)
    tab.blob_width.setValue(blob_width_val)
    tab.blob_width.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_width.setTickInterval(10)
    tab.blob_width.valueChanged.connect(tab._save_settings)
    blob_width_row.addWidget(tab.blob_width)
    tab.blob_width_label = QLabel(f"{blob_width_val}%")
    tab.blob_width.valueChanged.connect(
        lambda v: tab.blob_width_label.setText(f"{v}%")
    )
    blob_width_row.addWidget(tab.blob_width_label)
    blob_layout.addLayout(blob_width_row)

    # Blob size slider (0.3 .. 2.0)
    blob_size_row = QHBoxLayout()
    blob_size_row.addWidget(QLabel("Blob Size:"))
    tab.blob_size = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_size.setMinimum(30)
    tab.blob_size.setMaximum(200)
    blob_size_val = int(tab._default_float('spotify_visualizer', 'blob_size', 1.0) * 100)
    tab.blob_size.setValue(blob_size_val)
    tab.blob_size.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_size.setTickInterval(20)
    tab.blob_size.setToolTip("Scale of the blob relative to the card. 100% = default.")
    tab.blob_size.valueChanged.connect(tab._save_settings)
    blob_size_row.addWidget(tab.blob_size)
    tab.blob_size_label = QLabel(f"{blob_size_val}%")
    tab.blob_size.valueChanged.connect(
        lambda v: tab.blob_size_label.setText(f"{v}%")
    )
    blob_size_row.addWidget(tab.blob_size_label)
    blob_layout.addLayout(blob_size_row)

    # Blob glow intensity slider (0 .. 100)
    blob_gi_row = QHBoxLayout()
    blob_gi_row.addWidget(QLabel("Glow Intensity:"))
    tab.blob_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_glow_intensity.setMinimum(0)
    tab.blob_glow_intensity.setMaximum(100)
    blob_gi_val = int(tab._default_float('spotify_visualizer', 'blob_glow_intensity', 0.5) * 100)
    tab.blob_glow_intensity.setValue(blob_gi_val)
    tab.blob_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_glow_intensity.setTickInterval(10)
    tab.blob_glow_intensity.setToolTip("Controls the size and brightness of the glow around the blob.")
    tab.blob_glow_intensity.valueChanged.connect(tab._save_settings)
    blob_gi_row.addWidget(tab.blob_glow_intensity)
    tab.blob_glow_intensity_label = QLabel(f"{blob_gi_val}%")
    tab.blob_glow_intensity.valueChanged.connect(
        lambda v: tab.blob_glow_intensity_label.setText(f"{v}%")
    )
    blob_gi_row.addWidget(tab.blob_glow_intensity_label)
    blob_layout.addLayout(blob_gi_row)

    # Reactive Deformation slider (0..300, default 100 = 1.0x)
    blob_rd_row = QHBoxLayout()
    blob_rd_row.addWidget(QLabel("Reactive Deformation:"))
    tab.blob_reactive_deformation = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_reactive_deformation.setMinimum(0)
    tab.blob_reactive_deformation.setMaximum(300)
    blob_rd_val = int(tab._default_float('spotify_visualizer', 'blob_reactive_deformation', 1.0) * 100)
    tab.blob_reactive_deformation.setValue(blob_rd_val)
    tab.blob_reactive_deformation.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_reactive_deformation.setTickInterval(50)
    tab.blob_reactive_deformation.setToolTip(
        "Scales overall outward energy-driven growth. "
        "0% = no deformation, 100% = default, 300% = extreme."
    )
    tab.blob_reactive_deformation.valueChanged.connect(tab._save_settings)
    blob_rd_row.addWidget(tab.blob_reactive_deformation)
    tab.blob_reactive_deformation_label = QLabel(f"{blob_rd_val}%")
    tab.blob_reactive_deformation.valueChanged.connect(
        lambda v: tab.blob_reactive_deformation_label.setText(f"{v}%")
    )
    blob_rd_row.addWidget(tab.blob_reactive_deformation_label)
    blob_layout.addLayout(blob_rd_row)

    # Constant Wobble Energy slider (0..200, default 100 = 1.0x)
    blob_cw_row = QHBoxLayout()
    blob_cw_row.addWidget(QLabel("Constant Wobble:"))
    tab.blob_constant_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_constant_wobble.setMinimum(0)
    tab.blob_constant_wobble.setMaximum(200)
    blob_cw_val = int(tab._default_float('spotify_visualizer', 'blob_constant_wobble', 1.0) * 100)
    tab.blob_constant_wobble.setValue(blob_cw_val)
    tab.blob_constant_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_constant_wobble.setTickInterval(25)
    tab.blob_constant_wobble.setToolTip(
        "Base wobble amplitude present even during silence. "
        "0% = flat, 100% = default organic motion, 200% = exaggerated."
    )
    tab.blob_constant_wobble.valueChanged.connect(tab._save_settings)
    blob_cw_row.addWidget(tab.blob_constant_wobble)
    tab.blob_constant_wobble_label = QLabel(f"{blob_cw_val}%")
    tab.blob_constant_wobble.valueChanged.connect(
        lambda v: tab.blob_constant_wobble_label.setText(f"{v}%")
    )
    blob_cw_row.addWidget(tab.blob_constant_wobble_label)
    blob_layout.addLayout(blob_cw_row)

    # Reactive Wobble Energy slider (0..200, default 100 = 1.0x)
    blob_rw_row = QHBoxLayout()
    blob_rw_row.addWidget(QLabel("Reactive Wobble:"))
    tab.blob_reactive_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_reactive_wobble.setMinimum(0)
    tab.blob_reactive_wobble.setMaximum(200)
    blob_rw_val = int(tab._default_float('spotify_visualizer', 'blob_reactive_wobble', 1.0) * 100)
    tab.blob_reactive_wobble.setValue(blob_rw_val)
    tab.blob_reactive_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_reactive_wobble.setTickInterval(25)
    tab.blob_reactive_wobble.setToolTip(
        "Energy-driven wobble amplitude (mostly vocals/mid). "
        "0% = no audio reaction, 100% = default, 200% = exaggerated."
    )
    tab.blob_reactive_wobble.valueChanged.connect(tab._save_settings)
    blob_rw_row.addWidget(tab.blob_reactive_wobble)
    tab.blob_reactive_wobble_label = QLabel(f"{blob_rw_val}%")
    tab.blob_reactive_wobble.valueChanged.connect(
        lambda v: tab.blob_reactive_wobble_label.setText(f"{v}%")
    )
    blob_rw_row.addWidget(tab.blob_reactive_wobble_label)
    blob_layout.addLayout(blob_rw_row)

    # Stretch Tendency slider (0..100, default 0 = 0.0)
    blob_st_row = QHBoxLayout()
    blob_st_row.addWidget(QLabel("Stretch Tendency:"))
    tab.blob_stretch_tendency = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stretch_tendency.setMinimum(0)
    tab.blob_stretch_tendency.setMaximum(100)
    blob_st_val = int(tab._default_float('spotify_visualizer', 'blob_stretch_tendency', 0.0) * 100)
    tab.blob_stretch_tendency.setValue(max(0, min(100, blob_st_val)))
    tab.blob_stretch_tendency.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stretch_tendency.setTickInterval(10)
    tab.blob_stretch_tendency.setToolTip(
        "Bias deformation toward horizontal stretching rather than uniform growth. "
        "0% = uniform (default), 100% = fully horizontal stretch."
    )
    tab.blob_stretch_tendency.valueChanged.connect(tab._save_settings)
    blob_st_row.addWidget(tab.blob_stretch_tendency)
    tab.blob_stretch_tendency_label = QLabel(f"{blob_st_val}%")
    tab.blob_stretch_tendency.valueChanged.connect(
        lambda v: tab.blob_stretch_tendency_label.setText(f"{v}%")
    )
    blob_st_row.addWidget(tab.blob_stretch_tendency_label)
    blob_layout.addLayout(blob_st_row)

    _svctl.addWidget(tab._blob_settings_container)

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

    helix_glow_color_row = QHBoxLayout()
    helix_glow_color_row.addWidget(QLabel("Glow Color:"))
    tab.helix_glow_color_btn = QPushButton("Choose Color...")
    tab.helix_glow_color_btn.clicked.connect(tab._choose_helix_glow_color)
    helix_glow_color_row.addWidget(tab.helix_glow_color_btn)
    helix_glow_color_row.addStretch()
    helix_layout.addLayout(helix_glow_color_row)

    tab.helix_reactive_glow = QCheckBox("Reactive Glow")
    tab.helix_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'helix_reactive_glow', True))
    tab.helix_reactive_glow.setToolTip("Glow intensity pulses with audio energy.")
    tab.helix_reactive_glow.stateChanged.connect(tab._save_settings)
    helix_layout.addWidget(tab.helix_reactive_glow)

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

    _svctl.addWidget(tab._helix_settings_container)

    # ==========================================
    # Sine Wave settings container
    # ==========================================
    tab._sine_wave_settings_container = QWidget()
    sine_layout = QVBoxLayout(tab._sine_wave_settings_container)
    sine_layout.setContentsMargins(0, 0, 0, 0)

    # Glow
    tab.sine_glow_enabled = QCheckBox("Enable Glow")
    tab.sine_glow_enabled.setChecked(tab._default_bool('spotify_visualizer', 'sine_glow_enabled', True))
    tab.sine_glow_enabled.stateChanged.connect(tab._save_settings)
    sine_layout.addWidget(tab.sine_glow_enabled)

    # Glow intensity
    sine_glow_row = QHBoxLayout()
    sine_glow_row.addWidget(QLabel("Glow Intensity:"))
    tab.sine_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_glow_intensity.setMinimum(0)
    tab.sine_glow_intensity.setMaximum(100)
    sine_glow_val = int(tab._default_float('spotify_visualizer', 'sine_glow_intensity', 0.5) * 100)
    tab.sine_glow_intensity.setValue(sine_glow_val)
    tab.sine_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_glow_intensity.setTickInterval(10)
    tab.sine_glow_intensity.valueChanged.connect(tab._save_settings)
    sine_glow_row.addWidget(tab.sine_glow_intensity)
    tab.sine_glow_intensity_label = QLabel(f"{sine_glow_val}%")
    tab.sine_glow_intensity.valueChanged.connect(
        lambda v: tab.sine_glow_intensity_label.setText(f"{v}%")
    )
    sine_glow_row.addWidget(tab.sine_glow_intensity_label)
    sine_layout.addLayout(sine_glow_row)

    # Glow colour
    sine_glow_color_row = QHBoxLayout()
    sine_glow_color_row.addWidget(QLabel("Glow Color:"))
    tab.sine_glow_color_btn = QPushButton("Choose Color...")
    tab.sine_glow_color_btn.clicked.connect(tab._choose_sine_glow_color)
    sine_glow_color_row.addWidget(tab.sine_glow_color_btn)
    sine_glow_color_row.addStretch()
    sine_layout.addLayout(sine_glow_color_row)

    # Line colour
    sine_line_color_row = QHBoxLayout()
    sine_line_color_row.addWidget(QLabel("Line Color:"))
    tab.sine_line_color_btn = QPushButton("Choose Color...")
    tab.sine_line_color_btn.clicked.connect(tab._choose_sine_line_color)
    sine_line_color_row.addWidget(tab.sine_line_color_btn)
    sine_line_color_row.addStretch()
    sine_layout.addLayout(sine_line_color_row)

    # Reactive glow
    tab.sine_reactive_glow = QCheckBox("Reactive Glow (energy-driven)")
    tab.sine_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'sine_reactive_glow', True))
    tab.sine_reactive_glow.stateChanged.connect(tab._save_settings)
    sine_layout.addWidget(tab.sine_reactive_glow)

    # Sensitivity
    sine_sens_row = QHBoxLayout()
    sine_sens_row.addWidget(QLabel("Sensitivity:"))
    tab.sine_sensitivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_sensitivity.setMinimum(10)
    tab.sine_sensitivity.setMaximum(500)
    sine_sens_val = int(tab._default_float('spotify_visualizer', 'sine_sensitivity', 1.0) * 100)
    tab.sine_sensitivity.setValue(max(10, min(500, sine_sens_val)))
    tab.sine_sensitivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_sensitivity.setTickInterval(50)
    tab.sine_sensitivity.setToolTip("How much audio energy affects sine wave amplitude.")
    tab.sine_sensitivity.valueChanged.connect(tab._save_settings)
    sine_sens_row.addWidget(tab.sine_sensitivity)
    tab.sine_sensitivity_label = QLabel(f"{sine_sens_val / 100.0:.2f}x")
    tab.sine_sensitivity.valueChanged.connect(
        lambda v: tab.sine_sensitivity_label.setText(f"{v / 100.0:.2f}x")
    )
    sine_sens_row.addWidget(tab.sine_sensitivity_label)
    sine_layout.addLayout(sine_sens_row)

    # Speed
    sine_speed_row = QHBoxLayout()
    sine_speed_row.addWidget(QLabel("Speed:"))
    tab.sine_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_speed.setMinimum(10)
    tab.sine_speed.setMaximum(100)
    sine_speed_val = int(tab._default_float('spotify_visualizer', 'sine_speed', 1.0) * 100)
    tab.sine_speed.setValue(max(10, min(100, sine_speed_val)))
    tab.sine_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_speed.setTickInterval(10)
    tab.sine_speed.setToolTip("Wave animation speed multiplier.")
    tab.sine_speed.valueChanged.connect(tab._save_settings)
    sine_speed_row.addWidget(tab.sine_speed)
    tab.sine_speed_label = QLabel(f"{sine_speed_val / 100.0:.2f}x")
    tab.sine_speed.valueChanged.connect(
        lambda v: tab.sine_speed_label.setText(f"{v / 100.0:.2f}x")
    )
    sine_speed_row.addWidget(tab.sine_speed_label)
    sine_layout.addLayout(sine_speed_row)

    # Travel direction
    sine_travel_row = QHBoxLayout()
    sine_travel_row.addWidget(QLabel("Travel:"))
    tab.sine_travel = QComboBox()
    tab.sine_travel.addItems(["None", "Scroll Left", "Scroll Right"])
    default_sine_travel = tab._default_int('spotify_visualizer', 'sine_wave_travel', 0)
    tab.sine_travel.setCurrentIndex(max(0, min(2, default_sine_travel)))
    tab.sine_travel.setToolTip("Direction the sine wave scrolls.")
    tab.sine_travel.currentIndexChanged.connect(tab._save_settings)
    sine_travel_row.addWidget(tab.sine_travel)
    sine_travel_row.addStretch()
    sine_layout.addLayout(sine_travel_row)

    # Wave Effect (positional wave-like undulation)
    sine_wave_fx_row = QHBoxLayout()
    sine_wave_fx_row.addWidget(QLabel("Wave Effect:"))
    tab.sine_wave_effect = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_wave_effect.setMinimum(0)
    tab.sine_wave_effect.setMaximum(100)
    sine_wave_fx_val = int(tab._default_float('spotify_visualizer', 'sine_wave_effect',
                           tab._default_float('spotify_visualizer', 'sine_wobble_amount', 0.0)) * 100)
    tab.sine_wave_effect.setValue(max(0, min(100, sine_wave_fx_val)))
    tab.sine_wave_effect.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_wave_effect.setTickInterval(10)
    tab.sine_wave_effect.setToolTip("Adds a wave-like positional undulation along the sine lines. Higher = more movement.")
    tab.sine_wave_effect.valueChanged.connect(tab._save_settings)
    sine_wave_fx_row.addWidget(tab.sine_wave_effect)
    tab.sine_wave_effect_label = QLabel(f"{sine_wave_fx_val}%")
    tab.sine_wave_effect.valueChanged.connect(
        lambda v: tab.sine_wave_effect_label.setText(f"{v}%")
    )
    sine_wave_fx_row.addWidget(tab.sine_wave_effect_label)
    sine_layout.addLayout(sine_wave_fx_row)

    # Micro Wobble (energy-reactive micro distortions)
    sine_mw_row = QHBoxLayout()
    sine_mw_row.addWidget(QLabel("Micro Wobble:"))
    tab.sine_micro_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_micro_wobble.setMinimum(0)
    tab.sine_micro_wobble.setMaximum(100)
    sine_mw_val = int(tab._default_float('spotify_visualizer', 'sine_micro_wobble', 0.0) * 100)
    tab.sine_micro_wobble.setValue(max(0, min(100, sine_mw_val)))
    tab.sine_micro_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_micro_wobble.setTickInterval(10)
    tab.sine_micro_wobble.setToolTip("Energy-reactive micro distortions along the line. Small dents/bumps that react to audio without changing core shape. Higher = sharper.")
    tab.sine_micro_wobble.valueChanged.connect(tab._save_settings)
    sine_mw_row.addWidget(tab.sine_micro_wobble)
    tab.sine_micro_wobble_label = QLabel(f"{sine_mw_val}%")
    tab.sine_micro_wobble.valueChanged.connect(
        lambda v: tab.sine_micro_wobble_label.setText(f"{v}%")
    )
    sine_mw_row.addWidget(tab.sine_micro_wobble_label)
    sine_layout.addLayout(sine_mw_row)

    # Vertical Shift (slider -50 to 200, 0 = aligned)
    sine_vshift_row = QHBoxLayout()
    sine_vshift_row.addWidget(QLabel("Vertical Shift:"))
    tab.sine_vertical_shift = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_vertical_shift.setMinimum(-50)
    tab.sine_vertical_shift.setMaximum(200)
    sine_vshift_val = int(tab._default_int('spotify_visualizer', 'sine_vertical_shift', 0))
    tab.sine_vertical_shift.setValue(max(-50, min(200, sine_vshift_val)))
    tab.sine_vertical_shift.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_vertical_shift.setTickInterval(25)
    tab.sine_vertical_shift.setToolTip("Controls vertical spread between lines. 0 = all aligned, 100 = default spread, 200 = max spread, negative = lines cross. Multi-line only.")
    tab.sine_vertical_shift.valueChanged.connect(tab._save_settings)
    sine_vshift_row.addWidget(tab.sine_vertical_shift)
    tab.sine_vertical_shift_label = QLabel(f"{sine_vshift_val}")
    tab.sine_vertical_shift.valueChanged.connect(
        lambda v: tab.sine_vertical_shift_label.setText(f"{v}")
    )
    sine_vshift_row.addWidget(tab.sine_vertical_shift_label)
    sine_layout.addLayout(sine_vshift_row)

    # Multi-line
    tab.sine_multi_line = QCheckBox("Multi-Line Mode (up to 3 lines)")
    tab.sine_multi_line.setChecked(
        tab._default_int('spotify_visualizer', 'sine_line_count', 1) > 1
    )
    tab.sine_multi_line.setToolTip("Enable additional sine waves with different frequency distributions.")
    tab.sine_multi_line.stateChanged.connect(tab._save_settings)
    tab.sine_multi_line.stateChanged.connect(lambda: _update_sine_multi_line_visibility(tab))
    sine_layout.addWidget(tab.sine_multi_line)

    # Multi-line sub-container (shown only when multi-line enabled)
    tab._sine_multi_container = QWidget()
    sine_ml_layout = QVBoxLayout(tab._sine_multi_container)
    sine_ml_layout.setContentsMargins(16, 0, 0, 0)

    # Line count slider
    sine_lc_row = QHBoxLayout()
    sine_lc_row.addWidget(QLabel("Line Count:"))
    tab.sine_line_count_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_line_count_slider.setMinimum(2)
    tab.sine_line_count_slider.setMaximum(3)
    tab.sine_line_count_slider.setValue(max(2, tab._default_int('spotify_visualizer', 'sine_line_count', 2)))
    tab.sine_line_count_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_line_count_slider.setTickInterval(1)
    tab.sine_line_count_slider.valueChanged.connect(tab._save_settings)
    tab.sine_line_count_slider.valueChanged.connect(lambda: _update_sine_multi_line_visibility(tab))
    sine_lc_row.addWidget(tab.sine_line_count_slider)
    tab.sine_line_count_label = QLabel(str(max(2, tab._default_int('spotify_visualizer', 'sine_line_count', 2))))
    tab.sine_line_count_slider.valueChanged.connect(
        lambda v: tab.sine_line_count_label.setText(str(v))
    )
    sine_lc_row.addWidget(tab.sine_line_count_label)
    sine_ml_layout.addLayout(sine_lc_row)

    # Line 2 colours + travel
    sine_ml_layout.addWidget(QLabel("Line 2:"))
    sine_l2_row = QHBoxLayout()
    tab.sine_line2_color_btn = QPushButton("Line Color...")
    tab.sine_line2_color_btn.clicked.connect(tab._choose_sine_line2_color)
    sine_l2_row.addWidget(tab.sine_line2_color_btn)
    tab.sine_line2_glow_btn = QPushButton("Glow Color...")
    tab.sine_line2_glow_btn.clicked.connect(tab._choose_sine_line2_glow_color)
    sine_l2_row.addWidget(tab.sine_line2_glow_btn)
    sine_l2_row.addWidget(QLabel("Travel:"))
    tab.sine_travel_line2 = QComboBox()
    tab.sine_travel_line2.addItems(["None", "Left", "Right"])
    tab.sine_travel_line2.setCurrentIndex(max(0, min(2, tab._default_int('spotify_visualizer', 'sine_travel_line2', 0))))
    tab.sine_travel_line2.currentIndexChanged.connect(tab._save_settings)
    sine_l2_row.addWidget(tab.sine_travel_line2)
    sine_l2_row.addStretch()
    sine_ml_layout.addLayout(sine_l2_row)

    # Line 3 colours (only visible when line_count == 3)
    tab._sine_line3_label = QLabel("Line 3:")
    sine_ml_layout.addWidget(tab._sine_line3_label)
    tab._sine_l3_row_widget = QWidget()
    sine_l3_row = QHBoxLayout(tab._sine_l3_row_widget)
    sine_l3_row.setContentsMargins(0, 0, 0, 0)
    tab.sine_line3_color_btn = QPushButton("Line Color...")
    tab.sine_line3_color_btn.clicked.connect(tab._choose_sine_line3_color)
    sine_l3_row.addWidget(tab.sine_line3_color_btn)
    tab.sine_line3_glow_btn = QPushButton("Glow Color...")
    tab.sine_line3_glow_btn.clicked.connect(tab._choose_sine_line3_glow_color)
    sine_l3_row.addWidget(tab.sine_line3_glow_btn)
    sine_l3_row.addWidget(QLabel("Travel:"))
    tab.sine_travel_line3 = QComboBox()
    tab.sine_travel_line3.addItems(["None", "Left", "Right"])
    tab.sine_travel_line3.setCurrentIndex(max(0, min(2, tab._default_int('spotify_visualizer', 'sine_travel_line3', 0))))
    tab.sine_travel_line3.currentIndexChanged.connect(tab._save_settings)
    sine_l3_row.addWidget(tab.sine_travel_line3)
    sine_l3_row.addStretch()
    sine_ml_layout.addWidget(tab._sine_l3_row_widget)

    sine_layout.addWidget(tab._sine_multi_container)
    _update_sine_multi_line_visibility(tab)

    # Line Offset Bias
    sine_lob_row = QHBoxLayout()
    sine_lob_row.addWidget(QLabel("Line Offset Bias:"))
    tab.sine_line_offset_bias = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_line_offset_bias.setMinimum(0)
    tab.sine_line_offset_bias.setMaximum(100)
    sine_lob_val = int(tab._default_float('spotify_visualizer', 'sine_line_offset_bias', 0.0) * 100)
    tab.sine_line_offset_bias.setValue(max(0, min(100, sine_lob_val)))
    tab.sine_line_offset_bias.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_line_offset_bias.setTickInterval(10)
    tab.sine_line_offset_bias.setToolTip("Vertical spread between lines in multi-line mode.")
    tab.sine_line_offset_bias.valueChanged.connect(tab._save_settings)
    sine_lob_row.addWidget(tab.sine_line_offset_bias)
    tab.sine_line_offset_bias_label = QLabel(f"{sine_lob_val}%")
    tab.sine_line_offset_bias.valueChanged.connect(
        lambda v: tab.sine_line_offset_bias_label.setText(f"{v}%")
    )
    sine_lob_row.addWidget(tab.sine_line_offset_bias_label)
    sine_layout.addLayout(sine_lob_row)

    # Widget Card Adaptation (vertical stretch control)
    sine_adapt_row = QHBoxLayout()
    sine_adapt_row.addWidget(QLabel("Card Adaptation:"))
    tab.sine_card_adaptation = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_card_adaptation.setMinimum(3)
    tab.sine_card_adaptation.setMaximum(100)
    sine_adapt_val = int(tab._default_float('spotify_visualizer', 'sine_card_adaptation', 0.3) * 100)
    tab.sine_card_adaptation.setValue(max(3, min(100, sine_adapt_val)))
    tab.sine_card_adaptation.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_card_adaptation.setTickInterval(10)
    tab.sine_card_adaptation.setToolTip("How much of the card height the sine wave uses. Lower = less vertical stretch.")
    tab.sine_card_adaptation.valueChanged.connect(tab._save_settings)
    sine_adapt_row.addWidget(tab.sine_card_adaptation)
    tab.sine_card_adaptation_label = QLabel(f"{sine_adapt_val}%")
    tab.sine_card_adaptation.valueChanged.connect(
        lambda v: tab.sine_card_adaptation_label.setText(f"{v}%")
    )
    sine_adapt_row.addWidget(tab.sine_card_adaptation_label)
    sine_layout.addLayout(sine_adapt_row)

    # Card Height
    sine_growth_row = QHBoxLayout()
    sine_growth_row.addWidget(QLabel("Card Height:"))
    tab.sine_wave_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.sine_wave_growth.setMinimum(100)
    tab.sine_wave_growth.setMaximum(400)
    sine_growth_val = int(tab._default_float('spotify_visualizer', 'sine_wave_growth', 1.0) * 100)
    tab.sine_wave_growth.setValue(max(100, min(400, sine_growth_val)))
    tab.sine_wave_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.sine_wave_growth.setTickInterval(50)
    tab.sine_wave_growth.setToolTip("Height multiplier for the sine wave card.")
    tab.sine_wave_growth.valueChanged.connect(tab._save_settings)
    sine_growth_row.addWidget(tab.sine_wave_growth)
    tab.sine_wave_growth_label = QLabel(f"{sine_growth_val / 100.0:.1f}x")
    tab.sine_wave_growth.valueChanged.connect(
        lambda v: tab.sine_wave_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    sine_growth_row.addWidget(tab.sine_wave_growth_label)
    sine_layout.addLayout(sine_growth_row)

    _svctl.addWidget(tab._sine_wave_settings_container)

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

    spotify_vis_layout.addWidget(tab._spotify_vis_controls_container)
    tab.spotify_vis_enabled.stateChanged.connect(lambda: _update_spotify_vis_enabled_visibility(tab))
    _update_spotify_vis_enabled_visibility(tab)

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
    tab.media_spotify_volume_enabled.setChecked(
        tab._config_bool('media', media_config, 'spotify_volume_enabled', True)
    )
    tab.media_mute_button_enabled.setChecked(
        tab._config_bool('media', media_config, 'mute_button_enabled', False)
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

    _update_media_bg_visibility(tab)

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
    if hasattr(tab, 'osc_sensitivity'):
        osc_sens_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_sensitivity', 3.0) * 10)
        tab.osc_sensitivity.setValue(max(5, min(100, osc_sens_val)))
        tab.osc_sensitivity_label.setText(f"{osc_sens_val / 10.0:.1f}x")
    if hasattr(tab, 'osc_smoothing'):
        osc_smooth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_smoothing', 0.7) * 100)
        tab.osc_smoothing.setValue(max(0, min(100, osc_smooth_val)))
        tab.osc_smoothing_label.setText(f"{osc_smooth_val}%")
    if hasattr(tab, 'osc_growth'):
        osc_growth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_growth', 1.0) * 100)
        tab.osc_growth.setValue(max(100, min(400, osc_growth_val)))
        tab.osc_growth_label.setText(f"{osc_growth_val / 100.0:.1f}x")
    if hasattr(tab, 'osc_speed'):
        osc_speed_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_speed', 1.0) * 100)
        tab.osc_speed.setValue(max(10, min(100, osc_speed_val)))
        tab.osc_speed_label.setText(f"{osc_speed_val}%")
    if hasattr(tab, 'osc_line_dim'):
        tab.osc_line_dim.setChecked(bool(spotify_vis_config.get('osc_line_dim', False)))
    if hasattr(tab, 'osc_line_offset_bias'):
        osc_lob_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_line_offset_bias', 0.0) * 100)
        tab.osc_line_offset_bias.setValue(max(0, min(100, osc_lob_val)))
        tab.osc_line_offset_bias_label.setText(f"{osc_lob_val}%")
    if hasattr(tab, 'osc_vertical_shift'):
        osc_vs = int(spotify_vis_config.get('osc_vertical_shift', 0))
        if isinstance(spotify_vis_config.get('osc_vertical_shift'), bool):
            osc_vs = 100 if spotify_vis_config.get('osc_vertical_shift') else 0
        tab.osc_vertical_shift.setValue(max(-50, min(200, osc_vs)))
        tab.osc_vertical_shift_label.setText(f"{osc_vs}")
    if hasattr(tab, 'spectrum_growth'):
        spectrum_growth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_growth', 1.0) * 100)
        tab.spectrum_growth.setValue(max(100, min(400, spectrum_growth_val)))
        tab.spectrum_growth_label.setText(f"{spectrum_growth_val / 100.0:.1f}x")
    if hasattr(tab, 'spectrum_single_piece'):
        tab.spectrum_single_piece.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'spectrum_single_piece', False)
        )
    if hasattr(tab, 'spectrum_curved_profile'):
        tab.spectrum_curved_profile.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'spectrum_curved_profile', False)
        )

    # Oscilloscope colours
    osc_line_color_data = spotify_vis_config.get('osc_line_color', [255, 255, 255, 255])
    try:
        tab._osc_line_color = QColor(*osc_line_color_data)
    except Exception:
        tab._osc_line_color = QColor(255, 255, 255, 255)
    osc_glow_color_data = spotify_vis_config.get('osc_glow_color', [0, 200, 255, 230])
    try:
        tab._osc_glow_color = QColor(*osc_glow_color_data)
    except Exception:
        tab._osc_glow_color = QColor(0, 200, 255, 230)

    # Multi-line
    osc_line_count = int(spotify_vis_config.get('osc_line_count', 1))
    if hasattr(tab, 'osc_multi_line'):
        tab.osc_multi_line.setChecked(osc_line_count > 1)
    if hasattr(tab, 'osc_line_count'):
        tab.osc_line_count.setValue(max(2, min(3, osc_line_count)))
        tab.osc_line_count_label.setText(str(max(2, min(3, osc_line_count))))
    for attr, key, fallback in (
        ('_osc_line2_color', 'osc_line2_color', [255, 120, 50, 230]),
        ('_osc_line2_glow_color', 'osc_line2_glow_color', [255, 120, 50, 180]),
        ('_osc_line3_color', 'osc_line3_color', [50, 255, 120, 230]),
        ('_osc_line3_glow_color', 'osc_line3_glow_color', [50, 255, 120, 180]),
    ):
        data = spotify_vis_config.get(key, fallback)
        try:
            setattr(tab, attr, QColor(*data))
        except Exception:
            setattr(tab, attr, QColor(*fallback))
    _update_osc_multi_line_visibility(tab)

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
    # Nebula tint colours
    for attr, key, fallback in (
        ('_nebula_tint1', 'nebula_tint1', [20, 40, 120]),
        ('_nebula_tint2', 'nebula_tint2', [80, 20, 100]),
    ):
        c = spotify_vis_config.get(key, fallback) if spotify_vis_config else fallback
        if isinstance(c, (list, tuple)) and len(c) >= 3:
            setattr(tab, attr, QColor(*c))
        else:
            setattr(tab, attr, QColor(*fallback))
    if hasattr(tab, 'nebula_cycle_speed'):
        ncs_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'nebula_cycle_speed', 0.3) * 100)
        tab.nebula_cycle_speed.setValue(max(0, min(100, ncs_val)))
        tab.nebula_cycle_speed_label.setText(f"{ncs_val}%")

    # Per-mode settings: Blob
    if hasattr(tab, 'blob_pulse'):
        blob_pulse_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_pulse', 1.0) * 100)
        tab.blob_pulse.setValue(max(0, min(200, blob_pulse_val)))
        tab.blob_pulse_label.setText(f"{blob_pulse_val / 100.0:.2f}x")
    for attr, key, fallback in (
        ('_blob_color', 'blob_color', [0, 180, 255, 230]),
        ('_blob_glow_color', 'blob_glow_color', [0, 140, 255, 180]),
        ('_blob_edge_color', 'blob_edge_color', [100, 220, 255, 230]),
        ('_blob_outline_color', 'blob_outline_color', [0, 0, 0, 0]),
    ):
        data = spotify_vis_config.get(key, fallback)
        try:
            setattr(tab, attr, QColor(*data))
        except Exception:
            setattr(tab, attr, QColor(*fallback))
    if hasattr(tab, 'blob_width'):
        blob_width_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_width', 1.0) * 100)
        tab.blob_width.setValue(max(30, min(100, blob_width_val)))
        tab.blob_width_label.setText(f"{blob_width_val}%")
    if hasattr(tab, 'blob_size'):
        blob_size_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_size', 1.0) * 100)
        tab.blob_size.setValue(max(30, min(200, blob_size_val)))
        tab.blob_size_label.setText(f"{blob_size_val}%")
    if hasattr(tab, 'blob_glow_intensity'):
        blob_gi_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_glow_intensity', 0.5) * 100)
        tab.blob_glow_intensity.setValue(max(0, min(100, blob_gi_val)))
        tab.blob_glow_intensity_label.setText(f"{blob_gi_val}%")
    if hasattr(tab, 'blob_reactive_glow'):
        tab.blob_reactive_glow.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'blob_reactive_glow', True)
        )
    if hasattr(tab, 'blob_reactive_deformation'):
        blob_rd_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_reactive_deformation', 1.0) * 100)
        tab.blob_reactive_deformation.setValue(max(0, min(300, blob_rd_val)))
        tab.blob_reactive_deformation_label.setText(f"{blob_rd_val}%")
    if hasattr(tab, 'blob_constant_wobble'):
        blob_cw_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_constant_wobble', 1.0) * 100)
        tab.blob_constant_wobble.setValue(max(0, min(200, blob_cw_val)))
        tab.blob_constant_wobble_label.setText(f"{blob_cw_val}%")
    if hasattr(tab, 'blob_reactive_wobble'):
        blob_rw_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_reactive_wobble', 1.0) * 100)
        tab.blob_reactive_wobble.setValue(max(0, min(200, blob_rw_val)))
        tab.blob_reactive_wobble_label.setText(f"{blob_rw_val}%")
    if hasattr(tab, 'blob_stretch_tendency'):
        blob_st_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'blob_stretch_tendency', 0.0) * 100)
        tab.blob_stretch_tendency.setValue(max(0, min(100, blob_st_val)))
        tab.blob_stretch_tendency_label.setText(f"{blob_st_val}%")
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
    helix_glow_color_data = spotify_vis_config.get('helix_glow_color', [0, 200, 255, 180])
    try:
        tab._helix_glow_color = QColor(*helix_glow_color_data)
    except Exception:
        tab._helix_glow_color = QColor(0, 200, 255, 180)
    if hasattr(tab, 'helix_reactive_glow'):
        tab.helix_reactive_glow.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'helix_reactive_glow', True)
        )
    if hasattr(tab, 'helix_growth'):
        helix_growth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'helix_growth', 2.0) * 100)
        tab.helix_growth.setValue(max(100, min(400, helix_growth_val)))
        tab.helix_growth_label.setText(f"{helix_growth_val / 100.0:.1f}x")

    # Sine Wave settings
    if hasattr(tab, 'sine_glow_enabled'):
        tab.sine_glow_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'sine_glow_enabled', True)
        )
    if hasattr(tab, 'sine_glow_intensity'):
        sine_gi_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_glow_intensity', 0.5) * 100)
        tab.sine_glow_intensity.setValue(max(0, min(100, sine_gi_val)))
        tab.sine_glow_intensity_label.setText(f"{sine_gi_val}%")
    sine_glow_color_data = spotify_vis_config.get('sine_glow_color', [0, 200, 255, 230])
    try:
        tab._sine_glow_color = QColor(*sine_glow_color_data)
    except Exception:
        tab._sine_glow_color = QColor(0, 200, 255, 230)
    sine_line_color_data = spotify_vis_config.get('sine_line_color', [255, 255, 255, 255])
    try:
        tab._sine_line_color = QColor(*sine_line_color_data)
    except Exception:
        tab._sine_line_color = QColor(255, 255, 255, 255)
    if hasattr(tab, 'sine_reactive_glow'):
        tab.sine_reactive_glow.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'sine_reactive_glow', True)
        )
    if hasattr(tab, 'sine_sensitivity'):
        sine_sens_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_sensitivity', 1.0) * 100)
        tab.sine_sensitivity.setValue(max(10, min(500, sine_sens_val)))
        tab.sine_sensitivity_label.setText(f"{sine_sens_val / 100.0:.2f}x")
    if hasattr(tab, 'sine_speed'):
        sine_speed_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_speed', 1.0) * 100)
        tab.sine_speed.setValue(max(10, min(100, sine_speed_val)))
        tab.sine_speed_label.setText(f"{sine_speed_val / 100.0:.2f}x")
    if hasattr(tab, 'sine_wave_effect'):
        sine_wfx = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_wave_effect',
                       tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_wobble_amount', 0.0)) * 100)
        tab.sine_wave_effect.setValue(max(0, min(100, sine_wfx)))
        tab.sine_wave_effect_label.setText(f"{sine_wfx}%")
    if hasattr(tab, 'sine_micro_wobble'):
        sine_mw = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_micro_wobble', 0.0) * 100)
        tab.sine_micro_wobble.setValue(max(0, min(100, sine_mw)))
        tab.sine_micro_wobble_label.setText(f"{sine_mw}%")
    if hasattr(tab, 'sine_vertical_shift'):
        sine_vs = int(spotify_vis_config.get('sine_vertical_shift', 0))
        if isinstance(spotify_vis_config.get('sine_vertical_shift'), bool):
            sine_vs = 100 if spotify_vis_config.get('sine_vertical_shift') else 0
        tab.sine_vertical_shift.setValue(max(-50, min(200, sine_vs)))
        tab.sine_vertical_shift_label.setText(f"{sine_vs}")
    if hasattr(tab, 'sine_travel'):
        sine_travel_val = int(spotify_vis_config.get('sine_wave_travel', 0) or 0)
        tab.sine_travel.setCurrentIndex(max(0, min(2, sine_travel_val)))
    if hasattr(tab, 'sine_travel_line2'):
        stl2 = int(spotify_vis_config.get('sine_travel_line2', 0) or 0)
        tab.sine_travel_line2.setCurrentIndex(max(0, min(2, stl2)))
    if hasattr(tab, 'sine_travel_line3'):
        stl3 = int(spotify_vis_config.get('sine_travel_line3', 0) or 0)
        tab.sine_travel_line3.setCurrentIndex(max(0, min(2, stl3)))
    if hasattr(tab, 'sine_multi_line'):
        sine_lc = int(spotify_vis_config.get('sine_line_count', 1) or 1)
        tab.sine_multi_line.setChecked(sine_lc > 1)
    if hasattr(tab, 'sine_line_count_slider'):
        sine_lc = int(spotify_vis_config.get('sine_line_count', 2) or 2)
        tab.sine_line_count_slider.setValue(max(2, min(3, sine_lc)))
        tab.sine_line_count_label.setText(str(max(2, min(3, sine_lc))))
    # Sine line 2/3 colours
    for attr, key, fallback in (
        ('_sine_line2_color', 'sine_line2_color', [255, 120, 50, 230]),
        ('_sine_line2_glow_color', 'sine_line2_glow_color', [255, 120, 50, 180]),
        ('_sine_line3_color', 'sine_line3_color', [50, 255, 120, 230]),
        ('_sine_line3_glow_color', 'sine_line3_glow_color', [50, 255, 120, 180]),
    ):
        data = spotify_vis_config.get(key, fallback)
        try:
            setattr(tab, attr, QColor(*data))
        except Exception:
            setattr(tab, attr, QColor(*fallback))
    _update_sine_multi_line_visibility(tab)
    if hasattr(tab, 'sine_line_offset_bias'):
        sine_lob_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_line_offset_bias', 0.0) * 100)
        tab.sine_line_offset_bias.setValue(max(0, min(100, sine_lob_val)))
        tab.sine_line_offset_bias_label.setText(f"{sine_lob_val}%")
    if hasattr(tab, 'sine_card_adaptation'):
        sine_ca = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_card_adaptation', 0.3) * 100)
        tab.sine_card_adaptation.setValue(max(3, min(100, sine_ca)))
        tab.sine_card_adaptation_label.setText(f"{sine_ca}%")
    if hasattr(tab, 'sine_wave_growth'):
        sine_gv = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_wave_growth', 1.0) * 100)
        tab.sine_wave_growth.setValue(max(100, min(400, sine_gv)))
        tab.sine_wave_growth_label.setText(f"{sine_gv / 100.0:.1f}x")

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
    _update_ghost_visibility(tab)
    _update_media_enabled_visibility(tab)
    _update_spotify_vis_enabled_visibility(tab)


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
        'spotify_volume_enabled': tab.media_spotify_volume_enabled.isChecked(),
        'mute_button_enabled': tab.media_mute_button_enabled.isChecked(),
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
        'osc_sensitivity': (getattr(tab, 'osc_sensitivity', None) and tab.osc_sensitivity.value() or 30) / 10.0,
        'osc_smoothing': (getattr(tab, 'osc_smoothing', None) and tab.osc_smoothing.value() or 70) / 100.0,
        'osc_line_color': _qcolor_to_list(getattr(tab, '_osc_line_color', None), [255, 255, 255, 255]),
        'osc_glow_color': _qcolor_to_list(getattr(tab, '_osc_glow_color', None), [0, 200, 255, 230]),
        'osc_line_count': (getattr(tab, 'osc_line_count', None).value() if getattr(tab, 'osc_multi_line', None) and tab.osc_multi_line.isChecked() else 1),
        'osc_line2_color': _qcolor_to_list(getattr(tab, '_osc_line2_color', None), [255, 120, 50, 230]),
        'osc_line2_glow_color': _qcolor_to_list(getattr(tab, '_osc_line2_glow_color', None), [255, 120, 50, 180]),
        'osc_line3_color': _qcolor_to_list(getattr(tab, '_osc_line3_color', None), [50, 255, 120, 230]),
        'osc_line3_glow_color': _qcolor_to_list(getattr(tab, '_osc_line3_glow_color', None), [50, 255, 120, 180]),
        'star_travel_speed': (getattr(tab, 'star_travel_speed', None) and tab.star_travel_speed.value() or 50) / 100.0,
        'star_reactivity': (getattr(tab, 'star_reactivity', None) and tab.star_reactivity.value() or 100) / 100.0,
        'nebula_tint1': _qcolor_to_list(getattr(tab, '_nebula_tint1', None), [20, 40, 120]),
        'nebula_tint2': _qcolor_to_list(getattr(tab, '_nebula_tint2', None), [80, 20, 100]),
        'nebula_cycle_speed': (getattr(tab, 'nebula_cycle_speed', None) and tab.nebula_cycle_speed.value() or 30) / 100.0,
        'blob_pulse': (getattr(tab, 'blob_pulse', None) and tab.blob_pulse.value() or 100) / 100.0,
        'blob_color': _qcolor_to_list(getattr(tab, '_blob_color', None), [0, 180, 255, 230]),
        'blob_glow_color': _qcolor_to_list(getattr(tab, '_blob_glow_color', None), [0, 140, 255, 180]),
        'blob_edge_color': _qcolor_to_list(getattr(tab, '_blob_edge_color', None), [100, 220, 255, 230]),
        'blob_outline_color': _qcolor_to_list(getattr(tab, '_blob_outline_color', None), [0, 0, 0, 0]),
        'blob_width': (getattr(tab, 'blob_width', None) and tab.blob_width.value() or 100) / 100.0,
        'blob_size': (getattr(tab, 'blob_size', None) and tab.blob_size.value() or 100) / 100.0,
        'blob_glow_intensity': (getattr(tab, 'blob_glow_intensity', None) and tab.blob_glow_intensity.value() or 50) / 100.0,
        'blob_reactive_glow': getattr(tab, 'blob_reactive_glow', None) and tab.blob_reactive_glow.isChecked(),
        'blob_reactive_deformation': (getattr(tab, 'blob_reactive_deformation', None) and tab.blob_reactive_deformation.value() or 100) / 100.0,
        'blob_constant_wobble': (getattr(tab, 'blob_constant_wobble', None) and tab.blob_constant_wobble.value() or 100) / 100.0,
        'blob_reactive_wobble': (getattr(tab, 'blob_reactive_wobble', None) and tab.blob_reactive_wobble.value() or 100) / 100.0,
        'blob_stretch_tendency': (getattr(tab, 'blob_stretch_tendency', None) and tab.blob_stretch_tendency.value() or 0) / 100.0,
        'helix_turns': getattr(tab, 'helix_turns', None) and tab.helix_turns.value() or 4,
        'helix_double': getattr(tab, 'helix_double', None) and tab.helix_double.isChecked(),
        'helix_speed': (getattr(tab, 'helix_speed', None) and tab.helix_speed.value() or 100) / 100.0,
        'helix_glow_enabled': getattr(tab, 'helix_glow_enabled', None) and tab.helix_glow_enabled.isChecked(),
        'helix_glow_intensity': (getattr(tab, 'helix_glow_intensity', None) and tab.helix_glow_intensity.value() or 50) / 100.0,
        'helix_glow_color': _qcolor_to_list(getattr(tab, '_helix_glow_color', None), [0, 200, 255, 180]),
        'helix_reactive_glow': getattr(tab, 'helix_reactive_glow', None) and tab.helix_reactive_glow.isChecked(),
        'spectrum_growth': (getattr(tab, 'spectrum_growth', None) and tab.spectrum_growth.value() or 100) / 100.0,
        'spectrum_single_piece': getattr(tab, 'spectrum_single_piece', None) and tab.spectrum_single_piece.isChecked() or False,
        'spectrum_curved_profile': getattr(tab, 'spectrum_curved_profile', None) and tab.spectrum_curved_profile.isChecked() or False,
        'starfield_growth': (getattr(tab, 'starfield_growth', None) and tab.starfield_growth.value() or 200) / 100.0,
        'blob_growth': (getattr(tab, 'blob_growth', None) and tab.blob_growth.value() or 250) / 100.0,
        'helix_growth': (getattr(tab, 'helix_growth', None) and tab.helix_growth.value() or 200) / 100.0,
        'osc_growth': (getattr(tab, 'osc_growth', None) and tab.osc_growth.value() or 100) / 100.0,
        'osc_speed': (getattr(tab, 'osc_speed', None) and tab.osc_speed.value() or 100) / 100.0,
        'osc_line_dim': getattr(tab, 'osc_line_dim', None) and tab.osc_line_dim.isChecked(),
        'osc_line_offset_bias': (getattr(tab, 'osc_line_offset_bias', None) and tab.osc_line_offset_bias.value() or 0) / 100.0,
        'osc_vertical_shift': getattr(tab, 'osc_vertical_shift', None) and tab.osc_vertical_shift.value() or 0,
        'sine_glow_enabled': getattr(tab, 'sine_glow_enabled', None) and tab.sine_glow_enabled.isChecked(),
        'sine_glow_intensity': (getattr(tab, 'sine_glow_intensity', None) and tab.sine_glow_intensity.value() or 50) / 100.0,
        'sine_glow_color': _qcolor_to_list(getattr(tab, '_sine_glow_color', None), [0, 200, 255, 230]),
        'sine_line_color': _qcolor_to_list(getattr(tab, '_sine_line_color', None), [255, 255, 255, 255]),
        'sine_reactive_glow': getattr(tab, 'sine_reactive_glow', None) and tab.sine_reactive_glow.isChecked(),
        'sine_sensitivity': (getattr(tab, 'sine_sensitivity', None) and tab.sine_sensitivity.value() or 100) / 100.0,
        'sine_speed': (getattr(tab, 'sine_speed', None) and tab.sine_speed.value() or 100) / 100.0,
        'sine_wave_effect': (getattr(tab, 'sine_wave_effect', None) and tab.sine_wave_effect.value() or 0) / 100.0,
        'sine_micro_wobble': (getattr(tab, 'sine_micro_wobble', None) and tab.sine_micro_wobble.value() or 0) / 100.0,
        'sine_vertical_shift': getattr(tab, 'sine_vertical_shift', None) and tab.sine_vertical_shift.value() or 0,
        'sine_wave_travel': getattr(tab, 'sine_travel', None) and tab.sine_travel.currentIndex() or 0,
        'sine_travel_line2': getattr(tab, 'sine_travel_line2', None) and tab.sine_travel_line2.currentIndex() or 0,
        'sine_travel_line3': getattr(tab, 'sine_travel_line3', None) and tab.sine_travel_line3.currentIndex() or 0,
        'sine_line_count': (getattr(tab, 'sine_line_count_slider', None) and tab.sine_line_count_slider.value() or 2) if (getattr(tab, 'sine_multi_line', None) and tab.sine_multi_line.isChecked()) else 1,
        'sine_line_offset_bias': (getattr(tab, 'sine_line_offset_bias', None) and tab.sine_line_offset_bias.value() or 0) / 100.0,
        'sine_card_adaptation': (getattr(tab, 'sine_card_adaptation', None) and tab.sine_card_adaptation.value() or 30) / 100.0,
        'sine_wave_growth': (getattr(tab, 'sine_wave_growth', None) and tab.sine_wave_growth.value() or 100) / 100.0,
        'sine_line2_color': _qcolor_to_list(getattr(tab, '_sine_line2_color', None), [255, 120, 50, 230]),
        'sine_line2_glow_color': _qcolor_to_list(getattr(tab, '_sine_line2_glow_color', None), [255, 120, 50, 180]),
        'sine_line3_color': _qcolor_to_list(getattr(tab, '_sine_line3_color', None), [50, 255, 120, 230]),
        'sine_line3_glow_color': _qcolor_to_list(getattr(tab, '_sine_line3_glow_color', None), [50, 255, 120, 180]),
    }

    tab._update_spotify_vis_sensitivity_enabled_state()
    tab._update_spotify_vis_floor_enabled_state()

    return media_config, spotify_vis_config
