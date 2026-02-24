"""Blob visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QWidget,
    QSpacerItem, QSizePolicy, QToolButton,
)
from PySide6.QtCore import Qt

from ui.styled_popup import ColorSwatchButton

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_blob_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Blob settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    LABEL_WIDTH = 120
    tab._blob_label_width = LABEL_WIDTH

    tab._blob_settings_container = QWidget()
    blob_layout = QVBoxLayout(tab._blob_settings_container)
    blob_layout.setContentsMargins(0, 0, 0, 0)

    # --- Preset slider ---
    tab._blob_preset_slider = VisualizerPresetSlider("blob")
    tab._blob_preset_slider.preset_changed.connect(tab._save_settings)
    blob_layout.addWidget(tab._blob_preset_slider)

    # --- Normal controls container ---
    tab._blob_normal = QWidget()
    normal_layout = QVBoxLayout(tab._blob_normal)
    normal_layout.setContentsMargins(0, 0, 0, 0)
    normal_layout.setSpacing(6)
    blob_layout.addWidget(tab._blob_normal)

    def _aligned_row(label_text: str) -> tuple[QWidget, QHBoxLayout]:
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(6)
        lbl = QLabel(label_text)
        lbl.setFixedWidth(LABEL_WIDTH)
        row_layout.addWidget(lbl)
        return row_widget, row_layout

    def _bind_slider(slider: QSlider, updater=None) -> None:
        slider.valueChanged.connect(tab._save_settings)
        slider.valueChanged.connect(tab._auto_switch_preset_to_custom)
        if updater is not None:
            slider.valueChanged.connect(updater)

    def _bind_color(button: ColorSwatchButton, attr_name: str) -> None:
        def _on_color(color):
            setattr(tab, attr_name, color)
            tab._auto_switch_preset_to_custom()
            tab._save_settings()

        button.color_changed.connect(_on_color)

    # Pulse intensity (top of stack)
    pulse_widget, pulse_layout = _aligned_row("Pulse Intensity:")
    tab.blob_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_pulse.setMinimum(0)
    tab.blob_pulse.setMaximum(200)
    pulse_val = int(tab._default_float('spotify_visualizer', 'blob_pulse', 1.0) * 100)
    tab.blob_pulse.setValue(pulse_val)
    tab.blob_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_pulse.setTickInterval(25)
    tab.blob_pulse_label = QLabel(f"{pulse_val / 100.0:.2f}x")
    _bind_slider(tab.blob_pulse, lambda v: tab.blob_pulse_label.setText(f"{v / 100.0:.2f}x"))
    pulse_layout.addWidget(tab.blob_pulse)
    pulse_layout.addWidget(tab.blob_pulse_label)
    normal_layout.addWidget(pulse_widget)

    tab.blob_reactive_glow = QCheckBox("Reactive Glow")
    tab.blob_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'blob_reactive_glow', True))
    tab.blob_reactive_glow.setToolTip("Outer glow pulses with audio energy.")
    tab.blob_reactive_glow.stateChanged.connect(tab._save_settings)
    tab.blob_reactive_glow.stateChanged.connect(tab._auto_switch_preset_to_custom)
    normal_layout.addWidget(tab.blob_reactive_glow)

    # Glow color (visible only when Reactive Glow is on)
    glow_widget, glow_layout = _aligned_row("Glow Color:")
    tab.blob_glow_color_btn = ColorSwatchButton(title="Choose Blob Glow Color")
    tab.blob_glow_color_btn.set_color(getattr(tab, '_blob_glow_color', None))
    _bind_color(tab.blob_glow_color_btn, '_blob_glow_color')
    glow_layout.addWidget(tab.blob_glow_color_btn)
    glow_layout.addStretch()
    normal_layout.addWidget(glow_widget)

    def _update_glow_row() -> None:
        glow_widget.setVisible(tab.blob_reactive_glow.isChecked())

    tab.blob_reactive_glow.stateChanged.connect(lambda _s: _update_glow_row())
    _update_glow_row()

    # Fill / Edge / Outline colors (always visible, aligned)
    fill_widget, fill_layout = _aligned_row("Fill Color:")
    tab.blob_fill_color_btn = ColorSwatchButton(title="Choose Blob Fill Color")
    tab.blob_fill_color_btn.set_color(getattr(tab, '_blob_color', None))
    _bind_color(tab.blob_fill_color_btn, '_blob_color')
    fill_layout.addWidget(tab.blob_fill_color_btn)
    fill_layout.addStretch()
    normal_layout.addWidget(fill_widget)

    edge_widget, edge_layout = _aligned_row("Edge Color:")
    tab.blob_edge_color_btn = ColorSwatchButton(title="Choose Blob Edge Color")
    tab.blob_edge_color_btn.set_color(getattr(tab, '_blob_edge_color', None))
    _bind_color(tab.blob_edge_color_btn, '_blob_edge_color')
    edge_layout.addWidget(tab.blob_edge_color_btn)
    edge_layout.addStretch()
    normal_layout.addWidget(edge_widget)

    outline_widget, outline_layout = _aligned_row("Outline Color:")
    tab.blob_outline_color_btn = ColorSwatchButton(title="Choose Blob Outline Color")
    tab.blob_outline_color_btn.set_color(getattr(tab, '_blob_outline_color', None))
    _bind_color(tab.blob_outline_color_btn, '_blob_outline_color')
    outline_layout.addWidget(tab.blob_outline_color_btn)
    outline_layout.addStretch()
    normal_layout.addWidget(outline_widget)

    normal_layout.addItem(QSpacerItem(0, 8, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

    # Card size grouping (width, blob scale, height via build_blob_growth)
    tab._blob_card_size_layout = QVBoxLayout()
    tab._blob_card_size_layout.setSpacing(4)
    normal_layout.addLayout(tab._blob_card_size_layout)

    width_widget, width_layout = _aligned_row("Card Width:")
    tab.blob_width = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_width.setMinimum(30)
    tab.blob_width.setMaximum(100)
    blob_width_val = int(tab._default_float('spotify_visualizer', 'blob_width', 1.0) * 100)
    tab.blob_width.setValue(max(30, min(100, blob_width_val)))
    tab.blob_width.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_width.setTickInterval(10)
    tab.blob_width_label = QLabel(f"{tab.blob_width.value()}%")
    _bind_slider(tab.blob_width, lambda v: tab.blob_width_label.setText(f"{v}%"))
    width_layout.addWidget(tab.blob_width)
    width_layout.addWidget(tab.blob_width_label)
    tab._blob_card_size_layout.addWidget(width_widget)

    size_widget, size_layout = _aligned_row("Blob Size:")
    tab.blob_size = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_size.setMinimum(30)
    tab.blob_size.setMaximum(200)
    blob_size_val = int(tab._default_float('spotify_visualizer', 'blob_size', 1.0) * 100)
    tab.blob_size.setValue(max(30, min(200, blob_size_val)))
    tab.blob_size.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_size.setTickInterval(20)
    tab.blob_size.setToolTip("Base SDF size (pre-staging). 100% = default card fit.")
    tab.blob_size_label = QLabel(f"{tab.blob_size.value()}%")
    _bind_slider(tab.blob_size, lambda v: tab.blob_size_label.setText(f"{v}%"))
    size_layout.addWidget(tab.blob_size)
    size_layout.addWidget(tab.blob_size_label)
    tab._blob_card_size_layout.addWidget(size_widget)

    normal_layout.addItem(QSpacerItem(0, 6, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

    # --- Advanced host (toggle + helper + controls) ---
    tab._blob_advanced_host = QWidget()
    host_layout = QVBoxLayout(tab._blob_advanced_host)
    host_layout.setContentsMargins(0, 0, 0, 0)
    host_layout.setSpacing(4)

    toggle_row = QHBoxLayout()
    toggle_row.setContentsMargins(0, 0, 0, 0)
    toggle_row.setSpacing(4)
    tab._blob_adv_toggle = QToolButton()
    tab._blob_adv_toggle.setText("Advanced")
    tab._blob_adv_toggle.setCheckable(True)
    tab._blob_adv_toggle.setChecked(True)
    tab._blob_adv_toggle.setArrowType(Qt.DownArrow)
    tab._blob_adv_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    tab._blob_adv_toggle.setAutoRaise(True)
    toggle_row.addWidget(tab._blob_adv_toggle)
    toggle_row.addStretch()
    host_layout.addLayout(toggle_row)

    tab._blob_adv_helper = QLabel("Advanced sliders still apply when hidden.")
    tab._blob_adv_helper.setProperty("class", "adv-helper")
    tab._blob_adv_helper.setStyleSheet("color: rgba(220,220,220,0.6); font-size: 11px;")
    host_layout.addWidget(tab._blob_adv_helper)

    tab._blob_advanced = QWidget()
    adv_layout = QVBoxLayout(tab._blob_advanced)
    adv_layout.setContentsMargins(0, 0, 0, 0)
    adv_layout.setSpacing(4)
    host_layout.addWidget(tab._blob_advanced)

    blob_layout.addWidget(tab._blob_advanced_host)
    tab._blob_preset_slider.set_advanced_container(tab._blob_advanced_host)

    tab._blob_adv_manual_visible = True

    def _update_blob_adv_helper() -> None:
        tab._blob_adv_helper.setVisible(
            tab._blob_adv_toggle.isEnabled() and not tab._blob_adv_toggle.isChecked()
        )

    def _set_blob_adv_toggle_state(checked: bool, *, update_manual: bool = True) -> None:
        tab._blob_adv_toggle.blockSignals(True)
        tab._blob_adv_toggle.setChecked(checked)
        tab._blob_adv_toggle.blockSignals(False)
        tab._blob_adv_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        tab._blob_advanced.setVisible(checked)
        if update_manual and tab._blob_adv_toggle.isEnabled():
            tab._blob_adv_manual_visible = checked
        _update_blob_adv_helper()

    def _on_blob_adv_toggle(checked: bool) -> None:
        if not tab._blob_adv_toggle.isEnabled():
            return
        tab._blob_adv_manual_visible = checked
        tab._blob_adv_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        tab._blob_advanced.setVisible(checked)
        _update_blob_adv_helper()

    tab._blob_adv_toggle.toggled.connect(_on_blob_adv_toggle)

    def _handle_blob_preset_adv(is_custom: bool) -> None:
        tab._blob_adv_toggle.setEnabled(is_custom)
        if is_custom:
            _set_blob_adv_toggle_state(tab._blob_adv_manual_visible, update_manual=False)
        else:
            _set_blob_adv_toggle_state(False, update_manual=False)
        _update_blob_adv_helper()

    tab._blob_preset_slider.advanced_toggled.connect(_handle_blob_preset_adv)
    _handle_blob_preset_adv(tab._blob_advanced.isVisible())

    # Glow intensity (advanced)
    glow_row, glow_layout = _aligned_row("Glow Intensity:")
    tab.blob_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_glow_intensity.setMinimum(0)
    tab.blob_glow_intensity.setMaximum(100)
    blob_gi_val = int(tab._default_float('spotify_visualizer', 'blob_glow_intensity', 0.5) * 100)
    tab.blob_glow_intensity.setValue(max(0, min(100, blob_gi_val)))
    tab.blob_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_glow_intensity.setTickInterval(10)
    tab.blob_glow_intensity.setToolTip("Controls the size and brightness of the glow around the blob.")
    tab.blob_glow_intensity_label = QLabel(f"{tab.blob_glow_intensity.value()}%")
    _bind_slider(tab.blob_glow_intensity, lambda v: tab.blob_glow_intensity_label.setText(f"{v}%"))
    glow_layout.addWidget(tab.blob_glow_intensity)
    glow_layout.addWidget(tab.blob_glow_intensity_label)
    adv_layout.addWidget(glow_row)

    # Stage bias (new slider)
    bias_row, bias_layout = _aligned_row("Stage Bias:")
    tab.blob_stage_bias = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stage_bias.setMinimum(-30)
    tab.blob_stage_bias.setMaximum(30)
    stage_bias_val = int(round(tab._default_float('spotify_visualizer', 'blob_stage_bias', 0.0) * 100))
    stage_bias_val = max(-30, min(30, stage_bias_val))
    tab.blob_stage_bias.setValue(stage_bias_val)
    tab.blob_stage_bias.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stage_bias.setTickInterval(5)
    tab.blob_stage_bias.setToolTip("Biases stage drive upward (+) or downward (-) before release smoothing.")
    tab.blob_stage_bias_label = QLabel(f"{tab.blob_stage_bias.value() / 100:+.2f}")
    _bind_slider(tab.blob_stage_bias, lambda v: tab.blob_stage_bias_label.setText(f"{v / 100:+.2f}"))
    bias_layout.addWidget(tab.blob_stage_bias)
    bias_layout.addWidget(tab.blob_stage_bias_label)
    adv_layout.addWidget(bias_row)

    # Stage gain
    stage_gain_row, stage_gain_layout = _aligned_row("Stage Gain:")
    tab.blob_stage_gain = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stage_gain.setMinimum(0)
    tab.blob_stage_gain.setMaximum(200)
    blob_stage_gain_val = int(tab._default_float('spotify_visualizer', 'blob_stage_gain', 1.0) * 100)
    tab.blob_stage_gain.setValue(max(0, min(200, blob_stage_gain_val)))
    tab.blob_stage_gain.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stage_gain.setTickInterval(25)
    tab.blob_stage_gain.setToolTip("Scales the amplitude of staged core growth.")
    tab.blob_stage_gain_label = QLabel(f"{tab.blob_stage_gain.value()}%")
    _bind_slider(tab.blob_stage_gain, lambda v: tab.blob_stage_gain_label.setText(f"{v}%"))
    stage_gain_layout.addWidget(tab.blob_stage_gain)
    stage_gain_layout.addWidget(tab.blob_stage_gain_label)
    adv_layout.addWidget(stage_gain_row)

    # Stage release sliders
    def _ms_label(ms: int) -> str:
        return f"{ms / 1000:.2f}s"

    s2_row, s2_layout = _aligned_row("Stage 2 Release:")
    tab.blob_stage2_release_ms = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stage2_release_ms.setMinimum(400)
    tab.blob_stage2_release_ms.setMaximum(2000)
    s2_default = tab._default_int('spotify_visualizer', 'blob_stage2_release_ms', 900)
    tab.blob_stage2_release_ms.setValue(max(400, min(2000, s2_default)))
    tab.blob_stage2_release_ms.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stage2_release_ms.setTickInterval(100)
    tab.blob_stage2_release_ms.setToolTip("Controls how long Stage 2 lingers before releasing (ms).")
    tab.blob_stage2_release_ms_label = QLabel(_ms_label(tab.blob_stage2_release_ms.value()))
    _bind_slider(tab.blob_stage2_release_ms, lambda v: tab.blob_stage2_release_ms_label.setText(_ms_label(v)))
    s2_layout.addWidget(tab.blob_stage2_release_ms)
    s2_layout.addWidget(tab.blob_stage2_release_ms_label)
    adv_layout.addWidget(s2_row)

    s3_row, s3_layout = _aligned_row("Stage 3 Release:")
    tab.blob_stage3_release_ms = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stage3_release_ms.setMinimum(400)
    tab.blob_stage3_release_ms.setMaximum(2000)
    s3_default = tab._default_int('spotify_visualizer', 'blob_stage3_release_ms', 1200)
    tab.blob_stage3_release_ms.setValue(max(400, min(2000, s3_default)))
    tab.blob_stage3_release_ms.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stage3_release_ms.setTickInterval(100)
    tab.blob_stage3_release_ms.setToolTip("Controls how long Stage 3 lingers before releasing (ms).")
    tab.blob_stage3_release_ms_label = QLabel(_ms_label(tab.blob_stage3_release_ms.value()))
    _bind_slider(tab.blob_stage3_release_ms, lambda v: tab.blob_stage3_release_ms_label.setText(_ms_label(v)))
    s3_layout.addWidget(tab.blob_stage3_release_ms)
    s3_layout.addWidget(tab.blob_stage3_release_ms_label)
    adv_layout.addWidget(s3_row)

    # Core scale and floor
    core_scale_row, core_scale_layout = _aligned_row("Core Scale %:")
    tab.blob_core_scale = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_core_scale.setMinimum(25)
    tab.blob_core_scale.setMaximum(250)
    blob_core_scale_val = int(tab._default_float('spotify_visualizer', 'blob_core_scale', 1.0) * 100)
    tab.blob_core_scale.setValue(max(25, min(250, blob_core_scale_val)))
    tab.blob_core_scale.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_core_scale.setTickInterval(25)
    tab.blob_core_scale.setToolTip("Uniform multiplier applied after staged offsets.")
    tab.blob_core_scale_label = QLabel(f"{tab.blob_core_scale.value()}%")
    _bind_slider(tab.blob_core_scale, lambda v: tab.blob_core_scale_label.setText(f"{v}%"))
    core_scale_layout.addWidget(tab.blob_core_scale)
    core_scale_layout.addWidget(tab.blob_core_scale_label)
    adv_layout.addWidget(core_scale_row)

    core_floor_row, core_floor_layout = _aligned_row("Core Floor %:")
    tab.blob_core_floor_bias = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_core_floor_bias.setMinimum(0)
    tab.blob_core_floor_bias.setMaximum(60)
    blob_core_floor_val = int(tab._default_float('spotify_visualizer', 'blob_core_floor_bias', 0.35) * 100)
    tab.blob_core_floor_bias.setValue(max(0, min(60, blob_core_floor_val)))
    tab.blob_core_floor_bias.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_core_floor_bias.setTickInterval(5)
    tab.blob_core_floor_bias.setToolTip("Minimum percentage of the staged core radius preserved during deformation.")
    tab.blob_core_floor_bias_label = QLabel(f"{tab.blob_core_floor_bias.value()}%")
    _bind_slider(tab.blob_core_floor_bias, lambda v: tab.blob_core_floor_bias_label.setText(f"{v}%"))
    core_floor_layout.addWidget(tab.blob_core_floor_bias)
    core_floor_layout.addWidget(tab.blob_core_floor_bias_label)
    adv_layout.addWidget(core_floor_row)

    # Reactive deformation
    rd_row, rd_layout = _aligned_row("Reactive Deformation:")
    tab.blob_reactive_deformation = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_reactive_deformation.setMinimum(0)
    tab.blob_reactive_deformation.setMaximum(300)
    blob_rd_val = int(tab._default_float('spotify_visualizer', 'blob_reactive_deformation', 1.0) * 100)
    tab.blob_reactive_deformation.setValue(max(0, min(300, blob_rd_val)))
    tab.blob_reactive_deformation.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_reactive_deformation.setTickInterval(50)
    tab.blob_reactive_deformation.setToolTip("Scales overall outward energy-driven growth.")
    tab.blob_reactive_deformation_label = QLabel(f"{tab.blob_reactive_deformation.value()}%")
    _bind_slider(tab.blob_reactive_deformation, lambda v: tab.blob_reactive_deformation_label.setText(f"{v}%"))
    rd_layout.addWidget(tab.blob_reactive_deformation)
    rd_layout.addWidget(tab.blob_reactive_deformation_label)
    adv_layout.addWidget(rd_row)

    # Constant wobble
    cw_row, cw_layout = _aligned_row("Constant Wobble:")
    tab.blob_constant_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_constant_wobble.setMinimum(0)
    tab.blob_constant_wobble.setMaximum(200)
    blob_cw_val = int(tab._default_float('spotify_visualizer', 'blob_constant_wobble', 1.0) * 100)
    tab.blob_constant_wobble.setValue(max(0, min(200, blob_cw_val)))
    tab.blob_constant_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_constant_wobble.setTickInterval(25)
    tab.blob_constant_wobble.setToolTip("Base wobble amplitude present even during silence.")
    tab.blob_constant_wobble_label = QLabel(f"{tab.blob_constant_wobble.value()}%")
    _bind_slider(tab.blob_constant_wobble, lambda v: tab.blob_constant_wobble_label.setText(f"{v}%"))
    cw_layout.addWidget(tab.blob_constant_wobble)
    cw_layout.addWidget(tab.blob_constant_wobble_label)
    adv_layout.addWidget(cw_row)

    # Reactive wobble
    rw_row, rw_layout = _aligned_row("Reactive Wobble:")
    tab.blob_reactive_wobble = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_reactive_wobble.setMinimum(0)
    tab.blob_reactive_wobble.setMaximum(200)
    blob_rw_val = int(tab._default_float('spotify_visualizer', 'blob_reactive_wobble', 1.0) * 100)
    tab.blob_reactive_wobble.setValue(max(0, min(200, blob_rw_val)))
    tab.blob_reactive_wobble.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_reactive_wobble.setTickInterval(25)
    tab.blob_reactive_wobble.setToolTip("Energy-driven wobble amplitude.")
    tab.blob_reactive_wobble_label = QLabel(f"{tab.blob_reactive_wobble.value()}%")
    _bind_slider(tab.blob_reactive_wobble, lambda v: tab.blob_reactive_wobble_label.setText(f"{v}%"))
    rw_layout.addWidget(tab.blob_reactive_wobble)
    rw_layout.addWidget(tab.blob_reactive_wobble_label)
    adv_layout.addWidget(rw_row)

    # Stretch tendency
    st_row, st_layout = _aligned_row("Stretch Tendency:")
    tab.blob_stretch_tendency = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stretch_tendency.setMinimum(0)
    tab.blob_stretch_tendency.setMaximum(100)
    blob_st_val = int(tab._default_float('spotify_visualizer', 'blob_stretch_tendency', 0.0) * 100)
    tab.blob_stretch_tendency.setValue(max(0, min(100, blob_st_val)))
    tab.blob_stretch_tendency.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stretch_tendency.setTickInterval(10)
    tab.blob_stretch_tendency.setToolTip("Bias deformation toward horizontal stretching rather than uniform growth.")
    tab.blob_stretch_tendency_label = QLabel(f"{tab.blob_stretch_tendency.value()}%")
    _bind_slider(tab.blob_stretch_tendency, lambda v: tab.blob_stretch_tendency_label.setText(f"{v}%"))
    st_layout.addWidget(tab.blob_stretch_tendency)
    st_layout.addWidget(tab.blob_stretch_tendency_label)
    adv_layout.addWidget(st_row)

    parent_layout.addWidget(tab._blob_settings_container)


def build_blob_growth(tab: "WidgetsTab") -> None:
    """Append height growth slider to the blob advanced container."""
    from ui.tabs.widgets_tab import NoWheelSlider

    parent_layout = getattr(tab, '_blob_card_size_layout', None)
    if parent_layout is None:
        parent_layout = tab._blob_advanced.layout()

    label_width = getattr(tab, '_blob_label_width', 120)
    blob_growth_row = QHBoxLayout()
    label = QLabel("Card Height:")
    label.setFixedWidth(label_width)
    blob_growth_row.addWidget(label)
    tab.blob_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_growth.setMinimum(100)
    tab.blob_growth.setMaximum(500)
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
    parent_layout.addLayout(blob_growth_row)
