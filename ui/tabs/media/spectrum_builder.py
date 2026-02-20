"""Spectrum visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QCheckBox, QPushButton, QSlider, QWidget,
)
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def _update_ghost_visibility(tab) -> None:
    show = getattr(tab, 'spotify_vis_ghost_enabled', None) and tab.spotify_vis_ghost_enabled.isChecked()
    container = getattr(tab, '_ghost_sub_container', None)
    if container is not None:
        container.setVisible(bool(show))


def build_spectrum_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Spectrum-only settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    tab._spectrum_settings_container = QWidget()
    spectrum_layout = QVBoxLayout(tab._spectrum_settings_container)
    spectrum_layout.setContentsMargins(0, 0, 0, 0)

    # --- Preset slider (always visible) ---
    tab._spectrum_preset_slider = VisualizerPresetSlider("spectrum")
    tab._spectrum_preset_slider.preset_changed.connect(tab._save_settings)
    spectrum_layout.addWidget(tab._spectrum_preset_slider)

    # --- Advanced container (shown only when Custom preset is selected) ---
    tab._spectrum_advanced = QWidget()
    _adv_layout = QVBoxLayout(tab._spectrum_advanced)
    _adv_layout.setContentsMargins(0, 0, 0, 0)
    _adv_layout.setSpacing(4)
    tab._spectrum_preset_slider.set_advanced_container(tab._spectrum_advanced)

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
    _adv_layout.addLayout(spotify_vis_bar_row)

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
    _adv_layout.addLayout(spotify_vis_block_row)

    spotify_vis_fill_row = QHBoxLayout()
    spotify_vis_fill_row.addWidget(QLabel("Bar Fill Color:"))
    tab.spotify_vis_fill_color_btn = QPushButton("Choose Color...")
    tab.spotify_vis_fill_color_btn.clicked.connect(tab._choose_spotify_vis_fill_color)
    spotify_vis_fill_row.addWidget(tab.spotify_vis_fill_color_btn)
    spotify_vis_fill_row.addStretch()
    _adv_layout.addLayout(spotify_vis_fill_row)

    spotify_vis_border_color_row = QHBoxLayout()
    spotify_vis_border_color_row.addWidget(QLabel("Bar Border Color:"))
    tab.spotify_vis_border_color_btn = QPushButton("Choose Color...")
    tab.spotify_vis_border_color_btn.clicked.connect(tab._choose_spotify_vis_border_color)
    spotify_vis_border_color_row.addWidget(tab.spotify_vis_border_color_btn)
    spotify_vis_border_color_row.addStretch()
    _adv_layout.addLayout(spotify_vis_border_color_row)

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
    _adv_layout.addLayout(spotify_vis_border_opacity_row)

    tab.spotify_vis_recommended = QCheckBox("Adaptive")
    tab.spotify_vis_recommended.setChecked(
        tab._default_bool('spotify_visualizer', 'adaptive_sensitivity', True)
    )
    tab.spotify_vis_recommended.setToolTip(
        "When enabled, the visualizer uses the adaptive (v1.4) sensitivity baseline. Disable to adjust manually."
    )
    tab.spotify_vis_recommended.stateChanged.connect(tab._save_settings)
    tab.spotify_vis_recommended.stateChanged.connect(lambda _: tab._update_spotify_vis_sensitivity_enabled_state())
    _adv_layout.addWidget(tab.spotify_vis_recommended)

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
    _adv_layout.addLayout(spotify_vis_sensitivity_slider_row)

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
    _adv_layout.addWidget(tab.spotify_vis_dynamic_floor)

    tab._manual_floor_container = QWidget()
    _mf_layout = QVBoxLayout(tab._manual_floor_container)
    _mf_layout.setContentsMargins(16, 0, 0, 0)

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
    _mf_layout.addLayout(spotify_vis_manual_floor_row)

    _adv_layout.addWidget(tab._manual_floor_container)

    def _update_manual_floor_vis(_s=None):
        tab._manual_floor_container.setVisible(not tab.spotify_vis_dynamic_floor.isChecked())
    tab.spotify_vis_dynamic_floor.stateChanged.connect(_update_manual_floor_vis)
    _update_manual_floor_vis()

    # Ghosting controls
    tab.spotify_vis_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.spotify_vis_ghost_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'ghosting_enabled', True)
    )
    tab.spotify_vis_ghost_enabled.setToolTip(
        "When enabled, the visualizer draws trailing ghost bars above the current height."
    )
    tab.spotify_vis_ghost_enabled.stateChanged.connect(tab._save_settings)
    _adv_layout.addWidget(tab.spotify_vis_ghost_enabled)

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

    _adv_layout.addWidget(tab._ghost_sub_container)
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
    _adv_layout.addWidget(tab.spectrum_single_piece)

    # Unique Colours Per Bar (rainbow per-bar mode, only relevant when rainbow is on)
    tab.spectrum_rainbow_per_bar = QCheckBox("Unique Colours Per Bar")
    tab.spectrum_rainbow_per_bar.setChecked(
        tab._default_bool('spotify_visualizer', 'spectrum_rainbow_per_bar', False)
    )
    tab.spectrum_rainbow_per_bar.setToolTip(
        "When 'Taste The Rainbow' is enabled: each bar gets its own unique colour "
        "spread across the rainbow. Off = all bars share one shifting colour."
    )
    tab.spectrum_rainbow_per_bar.stateChanged.connect(tab._save_settings)
    _adv_layout.addWidget(tab.spectrum_rainbow_per_bar)

    # Bar Profile selector (Legacy / Curved)
    _profile_row = QHBoxLayout()
    _profile_row.addWidget(QLabel("Bar Profile:"))
    tab.spectrum_bar_profile = QComboBox()
    tab.spectrum_bar_profile.addItem("Legacy", "legacy")
    tab.spectrum_bar_profile.addItem("Curved Bar Profile", "curved")
    _profile_default = tab._default_str('spotify_visualizer', 'spectrum_bar_profile', 'legacy')
    _profile_idx = tab.spectrum_bar_profile.findData(_profile_default)
    if _profile_idx >= 0:
        tab.spectrum_bar_profile.setCurrentIndex(_profile_idx)
    tab.spectrum_bar_profile.setToolTip(
        "Legacy: classic flat profile. "
        "Curved: dual-peak wave profile with rounded bar corners."
    )
    tab.spectrum_bar_profile.currentIndexChanged.connect(tab._save_settings)
    _profile_row.addWidget(tab.spectrum_bar_profile)
    _profile_row.addStretch()
    _adv_layout.addLayout(_profile_row)

    # --- Profile sub-options: border radius (Curved only) ---
    tab._profile_sub_container = QWidget()
    _profile_sub_layout = QVBoxLayout(tab._profile_sub_container)
    _profile_sub_layout.setContentsMargins(16, 0, 0, 0)

    _br_row = QHBoxLayout()
    _br_row.addWidget(QLabel("Border Radius:"))
    tab.spectrum_border_radius = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_border_radius.setMinimum(0)
    tab.spectrum_border_radius.setMaximum(12)
    _br_default = int(tab._default_float('spotify_visualizer', 'spectrum_border_radius', 0.0))
    tab.spectrum_border_radius.setValue(max(0, min(12, _br_default)))
    tab.spectrum_border_radius.setToolTip("Round bar corners (0 = square, 6 = nicely rounded).")
    tab.spectrum_border_radius.valueChanged.connect(tab._save_settings)
    _br_row.addWidget(tab.spectrum_border_radius)
    tab.spectrum_border_radius_label = QLabel(f"{_br_default}px")
    tab.spectrum_border_radius.valueChanged.connect(
        lambda v: tab.spectrum_border_radius_label.setText(f"{v}px")
    )
    _br_row.addWidget(tab.spectrum_border_radius_label)
    _profile_sub_layout.addLayout(_br_row)

    _adv_layout.addWidget(tab._profile_sub_container)

    # Conditional visibility for curved sub-options
    def _update_profile_sub_vis(_idx=None):
        profile = tab.spectrum_bar_profile.currentData()
        tab._profile_sub_container.setVisible(profile == 'curved')
    tab.spectrum_bar_profile.currentIndexChanged.connect(_update_profile_sub_vis)
    _update_profile_sub_vis()

    # Spectrum card height growth slider (1.0 .. 3.0)
    spectrum_growth_row = QHBoxLayout()
    spectrum_growth_row.addWidget(QLabel("Card Height:"))
    tab.spectrum_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_growth.setMinimum(100)
    tab.spectrum_growth.setMaximum(500)
    spectrum_growth_val = int(tab._default_float('spotify_visualizer', 'spectrum_growth', 1.0) * 100)
    tab.spectrum_growth.setValue(max(100, min(500, spectrum_growth_val)))
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
    _adv_layout.addLayout(spectrum_growth_row)

    spectrum_layout.addWidget(tab._spectrum_advanced)
    parent_layout.addWidget(tab._spectrum_settings_container)
