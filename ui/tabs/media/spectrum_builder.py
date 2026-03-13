"""Spectrum visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QWidget, QToolButton,
)
from PySide6.QtCore import Qt

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.technical_controls import build_per_mode_technical_group
from ui.tabs.shared_styles import ADV_HELPER_LABEL_STYLE

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def _update_ghost_visibility(tab) -> None:
    show = getattr(tab, 'vis_ghost_enabled', None) and tab.vis_ghost_enabled.isChecked()
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
    tab._spectrum_preset_slider.preset_changed.connect(
        lambda idx: tab._on_visualizer_preset_changed("spectrum", idx)
    )
    spectrum_layout.addWidget(tab._spectrum_preset_slider)

    tab._spectrum_normal = QWidget()
    _normal_layout = QVBoxLayout(tab._spectrum_normal)
    _normal_layout.setContentsMargins(0, 0, 0, 0)
    _normal_layout.setSpacing(4)
    spectrum_layout.addWidget(tab._spectrum_normal)

    # --- Advanced host (toggle + helper + controls) ---
    tab._spectrum_advanced_host = QWidget()
    _adv_host = QVBoxLayout(tab._spectrum_advanced_host)
    _adv_host.setContentsMargins(0, 0, 0, 0)
    _adv_host.setSpacing(4)
    spectrum_layout.addWidget(tab._spectrum_advanced_host)

    _adv_toggle_row = QHBoxLayout()
    _adv_toggle_row.setContentsMargins(0, 0, 0, 0)
    _adv_toggle_row.setSpacing(4)
    tab._spectrum_adv_toggle = QToolButton()
    tab._spectrum_adv_toggle.setText("Advanced")
    tab._spectrum_adv_toggle.setCheckable(True)
    _spectrum_adv_default = False
    getter = getattr(tab, "get_visualizer_adv_state", None)
    if callable(getter):
        try:
            _spectrum_adv_default = bool(getter("spectrum"))
        except Exception:
            _spectrum_adv_default = False
    tab._spectrum_adv_toggle.setChecked(_spectrum_adv_default)
    tab._spectrum_adv_toggle.setArrowType(Qt.DownArrow)
    tab._spectrum_adv_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    tab._spectrum_adv_toggle.setAutoRaise(True)
    _adv_toggle_row.addWidget(tab._spectrum_adv_toggle)
    _adv_toggle_row.addStretch()
    _adv_host.addLayout(_adv_toggle_row)

    tab._spectrum_adv_helper = QLabel("Advanced sliders still apply when hidden.")
    tab._spectrum_adv_helper.setProperty("class", "adv-helper")
    tab._spectrum_adv_helper.setStyleSheet(ADV_HELPER_LABEL_STYLE)
    _adv_host.addWidget(tab._spectrum_adv_helper)

    tab._spectrum_advanced = QWidget()
    _adv_layout = QVBoxLayout(tab._spectrum_advanced)
    _adv_layout.setContentsMargins(0, 0, 0, 0)
    _adv_layout.setSpacing(4)
    _adv_host.addWidget(tab._spectrum_advanced)

    tab._spectrum_preset_slider.set_advanced_container(tab._spectrum_advanced_host)

    def _apply_spectrum_adv_toggle_state(checked: bool) -> None:
        tab._spectrum_adv_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        tab._spectrum_advanced.setVisible(checked)
        tab._spectrum_adv_helper.setVisible(not checked)
        setter = getattr(tab, "set_visualizer_adv_state", None)
        if callable(setter):
            try:
                setter("spectrum", checked)
            except Exception:
                pass

    tab._spectrum_adv_toggle.toggled.connect(_apply_spectrum_adv_toggle_state)
    _apply_spectrum_adv_toggle_state(tab._spectrum_adv_toggle.isChecked())

    def _handle_spectrum_preset_adv(is_custom: bool) -> None:
        tab._spectrum_normal.setVisible(is_custom)
        tab._spectrum_advanced_host.setVisible(is_custom)

    tab._spectrum_preset_slider.advanced_toggled.connect(_handle_spectrum_preset_adv)
    _handle_spectrum_preset_adv(True)

    # Technical bucket (ordered after Advanced)
    _spectrum_tech_host = build_per_mode_technical_group(tab, spectrum_layout, "spectrum")
    tab._spectrum_preset_slider.set_technical_container(_spectrum_tech_host)

    LABEL_WIDTH = 150

    def _aligned_row_widget(parent_layout: QVBoxLayout, label_text: str):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        label = QLabel(label_text)
        label.setFixedWidth(LABEL_WIDTH)
        row_layout.addWidget(label)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(8)
        row_layout.addLayout(content, 1)
        parent_layout.addWidget(row_widget)
        return row_widget, content

    def _aligned_row(parent_layout: QVBoxLayout, label_text: str):
        _, content = _aligned_row_widget(parent_layout, label_text)
        return content

    spotify_vis_fill_row = _aligned_row(_normal_layout, "Bar Fill Color:")
    tab.vis_fill_color_btn = ColorSwatchButton(title="Choose Beat Bar Fill Color")
    tab.vis_fill_color_btn.set_color(tab._spotify_vis_fill_color)
    tab.vis_fill_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_spotify_vis_fill_color', c), tab._save_settings())
    )
    spotify_vis_fill_row.addWidget(tab.vis_fill_color_btn)
    spotify_vis_fill_row.addStretch()

    spotify_vis_border_color_row = _aligned_row(_normal_layout, "Bar Border Color:")
    tab.vis_border_color_btn = ColorSwatchButton(title="Choose Beat Bar Border Color")
    tab.vis_border_color_btn.set_color(tab._spotify_vis_border_color)
    tab.vis_border_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_spotify_vis_border_color', c), tab._save_settings())
    )
    spotify_vis_border_color_row.addWidget(tab.vis_border_color_btn)
    spotify_vis_border_color_row.addStretch()

    spotify_vis_border_opacity_row = _aligned_row(_normal_layout, "Bar Border Opacity:")
    tab.vis_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.vis_border_opacity.setMinimum(0)
    tab.vis_border_opacity.setMaximum(100)
    spotify_vis_border_opacity_pct = int(
        tab._default_float('spotify_visualizer', 'bar_border_opacity', 0.85) * 100
    )
    tab.vis_border_opacity.setValue(spotify_vis_border_opacity_pct)
    tab.vis_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.vis_border_opacity.setTickInterval(5)
    tab.vis_border_opacity.valueChanged.connect(tab._save_settings)
    spotify_vis_border_opacity_row.addWidget(tab.vis_border_opacity)
    tab.vis_border_opacity_label = QLabel(f"{spotify_vis_border_opacity_pct}%")
    tab.vis_border_opacity.valueChanged.connect(
        lambda v: tab.vis_border_opacity_label.setText(f"{v}%")
    )
    spotify_vis_border_opacity_row.addWidget(tab.vis_border_opacity_label)

    # Ghosting controls
    ghost_toggle_row = _aligned_row(_adv_layout, "")
    tab.vis_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.vis_ghost_enabled.setProperty("circleIndicator", True)
    tab.vis_ghost_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'ghosting_enabled', True)
    )
    tab.vis_ghost_enabled.setToolTip(
        "When enabled, the visualizer draws trailing ghost bars above the current height."
    )
    tab.vis_ghost_enabled.stateChanged.connect(tab._save_settings)
    ghost_toggle_row.addWidget(tab.vis_ghost_enabled)
    ghost_toggle_row.addStretch()

    tab._ghost_sub_container = QWidget()
    _ghost_layout = QVBoxLayout(tab._ghost_sub_container)
    _ghost_layout.setContentsMargins(0, 0, 0, 0)
    _ghost_layout.setSpacing(4)

    spotify_vis_ghost_opacity_row = _aligned_row(_ghost_layout, "Ghost Opacity:")
    tab.vis_ghost_opacity_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.vis_ghost_opacity_slider.setMinimum(0)
    tab.vis_ghost_opacity_slider.setMaximum(100)
    ghost_alpha_pct = int(tab._default_float('spotify_visualizer', 'ghost_alpha', 0.4) * 100)
    tab.vis_ghost_opacity_slider.setValue(ghost_alpha_pct)
    tab.vis_ghost_opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.vis_ghost_opacity_slider.setTickInterval(5)
    tab.vis_ghost_opacity_slider.valueChanged.connect(tab._save_settings)
    spotify_vis_ghost_opacity_row.addWidget(tab.vis_ghost_opacity_slider)
    tab.vis_ghost_opacity_label = QLabel(f"{ghost_alpha_pct}%")
    tab.vis_ghost_opacity_slider.valueChanged.connect(
        lambda v: tab.vis_ghost_opacity_label.setText(f"{v}%")
    )
    spotify_vis_ghost_opacity_row.addWidget(tab.vis_ghost_opacity_label)

    spotify_vis_ghost_decay_row = _aligned_row(_ghost_layout, "Ghost Decay Speed:")
    tab.vis_ghost_decay_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.vis_ghost_decay_slider.setMinimum(10)
    tab.vis_ghost_decay_slider.setMaximum(100)
    ghost_decay_slider = int(tab._default_float('spotify_visualizer', 'ghost_decay', 0.4) * 100)
    tab.vis_ghost_decay_slider.setValue(max(10, min(100, ghost_decay_slider)))
    tab.vis_ghost_decay_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.vis_ghost_decay_slider.setTickInterval(5)
    tab.vis_ghost_decay_slider.valueChanged.connect(tab._save_settings)
    spotify_vis_ghost_decay_row.addWidget(tab.vis_ghost_decay_slider)
    tab.vis_ghost_decay_label = QLabel(f"{tab.vis_ghost_decay_slider.value() / 100.0:.2f}x")
    tab.vis_ghost_decay_slider.valueChanged.connect(
        lambda v: tab.vis_ghost_decay_label.setText(f"{v / 100.0:.2f}x")
    )
    spotify_vis_ghost_decay_row.addWidget(tab.vis_ghost_decay_label)

    _adv_layout.addWidget(tab._ghost_sub_container)
    tab.vis_ghost_enabled.stateChanged.connect(lambda: _update_ghost_visibility(tab))
    _update_ghost_visibility(tab)

    # Single Piece Mode (solid bars, no segment gaps)
    single_piece_row = _aligned_row(_adv_layout, "")
    tab.spectrum_single_piece = QCheckBox("Single Piece Mode")
    tab.spectrum_single_piece.setProperty("circleIndicator", True)
    tab.spectrum_single_piece.setChecked(
        tab._default_bool('spotify_visualizer', 'spectrum_single_piece', False)
    )
    tab.spectrum_single_piece.setToolTip(
        "Render solid continuous bars instead of segmented blocks. "
        "Produces a clean pillar look while keeping all other bar behaviour."
    )
    tab.spectrum_single_piece.stateChanged.connect(tab._save_settings)
    single_piece_row.addWidget(tab.spectrum_single_piece)
    single_piece_row.addStretch()

    # Unique Colours Per Bar (rainbow per-bar mode, only relevant when rainbow is on)
    rainbow_row = _aligned_row(_adv_layout, "")
    tab.spectrum_rainbow_per_bar = QCheckBox("Unique Colours Per Bar")
    tab.spectrum_rainbow_per_bar.setProperty("circleIndicator", True)
    tab.spectrum_rainbow_per_bar.setChecked(
        tab._default_bool('spotify_visualizer', 'spectrum_rainbow_per_bar', False)
    )
    tab.spectrum_rainbow_per_bar.setToolTip(
        "When 'Taste The Rainbow' is enabled: each bar gets its own unique colour "
        "spread across the rainbow. Off = all bars share one shifting colour."
    )
    tab.spectrum_rainbow_per_bar.stateChanged.connect(tab._save_settings)
    rainbow_row.addWidget(tab.spectrum_rainbow_per_bar)
    rainbow_row.addStretch()

    # Border Radius
    _br_row = _aligned_row(_adv_layout, "Border Radius:")
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

    # Mirrored Layout
    _mirror_row = QHBoxLayout()
    _mirror_row.setSpacing(6)
    _mirror_lbl = QLabel("Mirrored Layout:")
    _mirror_lbl.setFixedWidth(130)
    _mirror_row.addWidget(_mirror_lbl)
    tab.spectrum_mirrored = QCheckBox("Center-out (bass on edges)")
    _mirror_default = tab._default_bool('spotify_visualizer', 'spectrum_mirrored', True)
    tab.spectrum_mirrored.setChecked(_mirror_default)
    tab.spectrum_mirrored.setToolTip(
        "On: bars mirror from center outward (bass on edges, mids in center).\n"
        "Off: bars run left-to-right (low→high frequency)."
    )
    tab.spectrum_mirrored.stateChanged.connect(tab._save_settings)
    _mirror_row.addWidget(tab.spectrum_mirrored)
    _mirror_row.addStretch()
    _adv_layout.addLayout(_mirror_row)

    # --- Spectrum Shaping section ---
    _shape_header = QLabel("Spectrum Shaping")
    _shape_header.setStyleSheet("font-weight: 600; margin-top: 8px; margin-bottom: 2px;")
    _adv_layout.addWidget(_shape_header)
    _shape_hint = QLabel(
        "Left-click to add a control node (max 5). "
        "Right-click a node to remove it. Drag to reshape."
    )
    _shape_hint.setStyleSheet(ADV_HELPER_LABEL_STYLE)
    _shape_hint.setWordWrap(True)
    _adv_layout.addWidget(_shape_hint)

    # Visual shape editor
    from ui.tabs.media.spectrum_shape_editor import SpectrumShapeEditor
    _mirror_default_for_editor = tab._default_bool('spotify_visualizer', 'spectrum_mirrored', True)
    tab.spectrum_shape_editor = SpectrumShapeEditor(
        parent=None, mirrored=_mirror_default_for_editor,
    )
    tab.spectrum_shape_editor.nodes_changed.connect(tab._save_settings)
    _adv_layout.addWidget(tab.spectrum_shape_editor)
    # Connect mirrored checkbox to update editor display
    tab.spectrum_mirrored.stateChanged.connect(
        lambda state: tab.spectrum_shape_editor.set_mirrored(bool(state))
    )

    # --- Audio Influence sliders (control energy zone weights, not shape) ---
    _influence_header = QLabel("Audio Influence")
    _influence_header.setStyleSheet("font-weight: 600; margin-top: 8px; margin-bottom: 2px;")
    _adv_layout.addWidget(_influence_header)
    _influence_hint = QLabel("How much each frequency band drives bar height.")
    _influence_hint.setStyleSheet(ADV_HELPER_LABEL_STYLE)
    _adv_layout.addWidget(_influence_hint)

    # Bass Influence (0–100 → 0.0–1.0)
    _bass_row = _aligned_row(_adv_layout, "Bass Influence:")
    tab.spectrum_bass_emphasis = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_bass_emphasis.setMinimum(0)
    tab.spectrum_bass_emphasis.setMaximum(100)
    _bass_default = int(tab._default_float('spotify_visualizer', 'spectrum_bass_emphasis', 0.50) * 100)
    tab.spectrum_bass_emphasis.setValue(max(0, min(100, _bass_default)))
    tab.spectrum_bass_emphasis.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_bass_emphasis.setTickInterval(25)
    tab.spectrum_bass_emphasis.setToolTip("How strongly bass energy drives edge bars. 0 = subtle, 100 = dominant.")
    tab.spectrum_bass_emphasis.valueChanged.connect(tab._save_settings)
    _bass_row.addWidget(tab.spectrum_bass_emphasis)
    tab.spectrum_bass_emphasis_label = QLabel(f"{_bass_default}%")
    tab.spectrum_bass_emphasis.valueChanged.connect(
        lambda v: tab.spectrum_bass_emphasis_label.setText(f"{v}%")
    )
    _bass_row.addWidget(tab.spectrum_bass_emphasis_label)

    # Vocal Position (kept for preset compat, hidden — still saved)
    tab.spectrum_vocal_position = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_vocal_position.setMinimum(20)
    tab.spectrum_vocal_position.setMaximum(60)
    _vocal_default = int(tab._default_float('spotify_visualizer', 'spectrum_vocal_position', 0.40) * 100)
    tab.spectrum_vocal_position.setValue(max(20, min(60, _vocal_default)))
    tab.spectrum_vocal_position.hide()

    # Mid Dampening (0–100 → 0.0–1.0)
    _mid_row = _aligned_row(_adv_layout, "Mid Dampening:")
    tab.spectrum_mid_suppression = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_mid_suppression.setMinimum(0)
    tab.spectrum_mid_suppression.setMaximum(100)
    _mid_default = int(tab._default_float('spotify_visualizer', 'spectrum_mid_suppression', 0.50) * 100)
    tab.spectrum_mid_suppression.setValue(max(0, min(100, _mid_default)))
    tab.spectrum_mid_suppression.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_mid_suppression.setTickInterval(25)
    tab.spectrum_mid_suppression.setToolTip("Reduce mid-frequency energy contribution. 0 = full mid, 100 = heavily dampened.")
    tab.spectrum_mid_suppression.valueChanged.connect(tab._save_settings)
    _mid_row.addWidget(tab.spectrum_mid_suppression)
    tab.spectrum_mid_suppression_label = QLabel(f"{_mid_default}%")
    tab.spectrum_mid_suppression.valueChanged.connect(
        lambda v: tab.spectrum_mid_suppression_label.setText(f"{v}%")
    )
    _mid_row.addWidget(tab.spectrum_mid_suppression_label)

    # Reactivity (0–100 → 0.0–1.0)
    _wave_row = _aligned_row(_adv_layout, "Reactivity:")
    tab.spectrum_wave_amplitude = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_wave_amplitude.setMinimum(0)
    tab.spectrum_wave_amplitude.setMaximum(100)
    _wave_default = int(tab._default_float('spotify_visualizer', 'spectrum_wave_amplitude', 0.50) * 100)
    tab.spectrum_wave_amplitude.setValue(max(0, min(100, _wave_default)))
    tab.spectrum_wave_amplitude.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_wave_amplitude.setTickInterval(25)
    tab.spectrum_wave_amplitude.setToolTip("Overall audio reactivity scaling. 0 = calm, 100 = intense.")
    tab.spectrum_wave_amplitude.valueChanged.connect(tab._save_settings)
    _wave_row.addWidget(tab.spectrum_wave_amplitude)
    tab.spectrum_wave_amplitude_label = QLabel(f"{_wave_default}%")
    tab.spectrum_wave_amplitude.valueChanged.connect(
        lambda v: tab.spectrum_wave_amplitude_label.setText(f"{v}%")
    )
    _wave_row.addWidget(tab.spectrum_wave_amplitude_label)

    # Profile Floor (5–30 → 0.05–0.30)
    _floor_row = _aligned_row(_adv_layout, "Min Height:")
    tab.spectrum_profile_floor = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_profile_floor.setMinimum(5)
    tab.spectrum_profile_floor.setMaximum(30)
    _floor_default = int(tab._default_float('spotify_visualizer', 'spectrum_profile_floor', 0.12) * 100)
    tab.spectrum_profile_floor.setValue(max(5, min(30, _floor_default)))
    tab.spectrum_profile_floor.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_profile_floor.setTickInterval(5)
    tab.spectrum_profile_floor.setToolTip("Minimum bar height floor. Lower = bars can shrink more.")
    tab.spectrum_profile_floor.valueChanged.connect(tab._save_settings)
    _floor_row.addWidget(tab.spectrum_profile_floor)
    tab.spectrum_profile_floor_label = QLabel(f"{_floor_default / 100.0:.2f}")
    tab.spectrum_profile_floor.valueChanged.connect(
        lambda v: tab.spectrum_profile_floor_label.setText(f"{v / 100.0:.2f}")
    )
    _floor_row.addWidget(tab.spectrum_profile_floor_label)

    # Spectrum card height growth slider (1.0 .. 3.0)
    spectrum_growth_row = _aligned_row(_adv_layout, "Card Height:")
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

    parent_layout.addWidget(tab._spectrum_settings_container)
