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
from ui.tabs.media.technical_controls import build_per_mode_technical_group
from ui.tabs.shared_styles import ADV_HELPER_LABEL_STYLE

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_blob_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Blob settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider
    from ui.tabs.media.preset_slider import VisualizerPresetSlider

    LABEL_WIDTH = 140
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
        inner = QHBoxLayout()
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(6)
        row_layout.addLayout(inner, 1)
        return row_widget, inner

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
    tab.blob_reactive_glow.setProperty("circleIndicator", True)
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
    _blob_adv_default = False
    getter = getattr(tab, "get_visualizer_adv_state", None)
    if callable(getter):
        try:
            _blob_adv_default = bool(getter("blob"))
        except Exception:
            _blob_adv_default = False
    tab._blob_adv_toggle.setChecked(_blob_adv_default)
    tab._blob_adv_toggle.setArrowType(Qt.DownArrow)
    tab._blob_adv_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    tab._blob_adv_toggle.setAutoRaise(True)
    toggle_row.addWidget(tab._blob_adv_toggle)
    toggle_row.addStretch()
    host_layout.addLayout(toggle_row)

    tab._blob_adv_helper = QLabel("Advanced sliders still apply when hidden.")
    tab._blob_adv_helper.setProperty("class", "adv-helper")
    tab._blob_adv_helper.setStyleSheet(ADV_HELPER_LABEL_STYLE)
    host_layout.addWidget(tab._blob_adv_helper)

    tab._blob_advanced = QWidget()
    adv_layout = QVBoxLayout(tab._blob_advanced)
    adv_layout.setContentsMargins(0, 0, 0, 0)
    adv_layout.setSpacing(4)
    build_per_mode_technical_group(tab, host_layout, "blob")
    host_layout.addWidget(tab._blob_advanced)

    blob_layout.addWidget(tab._blob_advanced_host)
    tab._blob_preset_slider.set_advanced_container(tab._blob_advanced_host)

    def _apply_blob_adv_toggle_state(checked: bool) -> None:
        tab._blob_adv_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        tab._blob_advanced.setVisible(checked)
        tab._blob_adv_helper.setVisible(not checked)
        setter = getattr(tab, "set_visualizer_adv_state", None)
        if callable(setter):
            try:
                setter("blob", checked)
            except Exception:
                pass

    tab._blob_adv_toggle.toggled.connect(_apply_blob_adv_toggle_state)
    _apply_blob_adv_toggle_state(tab._blob_adv_toggle.isChecked())

    def _handle_blob_preset_adv(is_custom: bool) -> None:
        tab._blob_advanced_host.setVisible(is_custom)

    tab._blob_preset_slider.advanced_toggled.connect(_handle_blob_preset_adv)
    _handle_blob_preset_adv(True)

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

    # Glow Reactivity (how strongly glow responds to audio energy)
    glow_react_row, glow_react_layout = _aligned_row("Glow Reactivity:")
    tab.blob_glow_reactivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_glow_reactivity.setMinimum(0)
    tab.blob_glow_reactivity.setMaximum(200)
    blob_gr_val = int(tab._default_float('spotify_visualizer', 'blob_glow_reactivity', 1.0) * 100)
    tab.blob_glow_reactivity.setValue(max(0, min(200, blob_gr_val)))
    tab.blob_glow_reactivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_glow_reactivity.setTickInterval(25)
    tab.blob_glow_reactivity.setToolTip("How strongly the glow responds to audio energy. 0% = static glow, 200% = very reactive.")
    tab.blob_glow_reactivity_label = QLabel(f"{tab.blob_glow_reactivity.value()}%")
    _bind_slider(tab.blob_glow_reactivity, lambda v: tab.blob_glow_reactivity_label.setText(f"{v}%"))
    glow_react_layout.addWidget(tab.blob_glow_reactivity)
    glow_react_layout.addWidget(tab.blob_glow_reactivity_label)
    adv_layout.addWidget(glow_react_row)

    # Glow Max Size (maximum glow spread radius)
    glow_max_row, glow_max_layout = _aligned_row("Glow Max Size:")
    tab.blob_glow_max_size = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_glow_max_size.setMinimum(10)
    tab.blob_glow_max_size.setMaximum(300)
    blob_gms_val = int(tab._default_float('spotify_visualizer', 'blob_glow_max_size', 1.0) * 100)
    tab.blob_glow_max_size.setValue(max(10, min(300, blob_gms_val)))
    tab.blob_glow_max_size.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_glow_max_size.setTickInterval(25)
    tab.blob_glow_max_size.setToolTip("Maximum radius the glow can spread to. Higher = larger glow halo.")
    tab.blob_glow_max_size_label = QLabel(f"{tab.blob_glow_max_size.value()}%")
    _bind_slider(tab.blob_glow_max_size, lambda v: tab.blob_glow_max_size_label.setText(f"{v}%"))
    glow_max_layout.addWidget(tab.blob_glow_max_size)
    glow_max_layout.addWidget(tab.blob_glow_max_size_label)
    adv_layout.addWidget(glow_max_row)

    # --- Ghosting controls (advanced bucket) ---
    ghost_toggle_row_w, ghost_toggle_row = _aligned_row("")
    tab.blob_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.blob_ghost_enabled.setProperty("circleIndicator", True)
    tab.blob_ghost_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'blob_ghosting_enabled', False)
    )
    tab.blob_ghost_enabled.setToolTip(
        "Show a faded outline ring at the blob's recent peak size."
    )
    tab.blob_ghost_enabled.stateChanged.connect(tab._save_settings)
    ghost_toggle_row.addWidget(tab.blob_ghost_enabled)
    ghost_toggle_row.addStretch()
    adv_layout.addWidget(ghost_toggle_row_w)

    tab._blob_ghost_sub = QWidget()
    _ghost_layout = QVBoxLayout(tab._blob_ghost_sub)
    _ghost_layout.setContentsMargins(0, 0, 0, 0)
    _ghost_layout.setSpacing(4)

    ghost_opa_w, ghost_opa_l = _aligned_row("Ghost Opacity:")
    tab.blob_ghost_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_ghost_opacity.setMinimum(0)
    tab.blob_ghost_opacity.setMaximum(100)
    _bg_alpha_pct = int(tab._default_float('spotify_visualizer', 'blob_ghost_alpha', 0.4) * 100)
    tab.blob_ghost_opacity.setValue(max(0, min(100, _bg_alpha_pct)))
    tab.blob_ghost_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_ghost_opacity.setTickInterval(5)
    tab.blob_ghost_opacity.valueChanged.connect(tab._save_settings)
    ghost_opa_l.addWidget(tab.blob_ghost_opacity)
    tab.blob_ghost_opacity_label = QLabel(f"{_bg_alpha_pct}%")
    tab.blob_ghost_opacity.valueChanged.connect(
        lambda v: tab.blob_ghost_opacity_label.setText(f"{v}%")
    )
    ghost_opa_l.addWidget(tab.blob_ghost_opacity_label)
    _ghost_layout.addWidget(ghost_opa_w)

    ghost_dec_w, ghost_dec_l = _aligned_row("Ghost Decay:")
    tab.blob_ghost_decay_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_ghost_decay_slider.setMinimum(10)
    tab.blob_ghost_decay_slider.setMaximum(100)
    _bg_decay_pct = int(tab._default_float('spotify_visualizer', 'blob_ghost_decay', 0.3) * 100)
    tab.blob_ghost_decay_slider.setValue(max(10, min(100, _bg_decay_pct)))
    tab.blob_ghost_decay_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_ghost_decay_slider.setTickInterval(5)
    tab.blob_ghost_decay_slider.valueChanged.connect(tab._save_settings)
    ghost_dec_l.addWidget(tab.blob_ghost_decay_slider)
    tab.blob_ghost_decay_label = QLabel(f"{tab.blob_ghost_decay_slider.value() / 100.0:.2f}x")
    tab.blob_ghost_decay_slider.valueChanged.connect(
        lambda v: tab.blob_ghost_decay_label.setText(f"{v / 100.0:.2f}x")
    )
    ghost_dec_l.addWidget(tab.blob_ghost_decay_label)
    _ghost_layout.addWidget(ghost_dec_w)

    adv_layout.addWidget(tab._blob_ghost_sub)

    def _update_blob_ghost_vis(tab=tab):
        tab._blob_ghost_sub.setVisible(tab.blob_ghost_enabled.isChecked())

    tab.blob_ghost_enabled.stateChanged.connect(lambda _s: _update_blob_ghost_vis())
    _update_blob_ghost_vis()

    # Stage bias (new slider)
    bias_row, bias_layout = _aligned_row("Stage Bias:")
    tab.blob_stage_bias = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stage_bias.setMinimum(-60)
    tab.blob_stage_bias.setMaximum(60)
    stage_bias_val = int(round(tab._default_float('spotify_visualizer', 'blob_stage_bias', 0.0) * 100))
    stage_bias_val = max(-60, min(60, stage_bias_val))
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
    blob_st_val = int(tab._default_float('spotify_visualizer', 'blob_stretch_tendency', 0.35) * 100)
    tab.blob_stretch_tendency.setValue(max(0, min(100, blob_st_val)))
    tab.blob_stretch_tendency.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stretch_tendency.setTickInterval(10)
    tab.blob_stretch_tendency.setToolTip("How much peak energy creates directional juts/stretches.")
    tab.blob_stretch_tendency_label = QLabel(f"{tab.blob_stretch_tendency.value()}%")
    _bind_slider(tab.blob_stretch_tendency, lambda v: tab.blob_stretch_tendency_label.setText(f"{v}%"))
    st_layout.addWidget(tab.blob_stretch_tendency)
    st_layout.addWidget(tab.blob_stretch_tendency_label)
    adv_layout.addWidget(st_row)

    # Inner Stretch (how deep inward dents can go)
    si_row, si_layout = _aligned_row("Inner Stretch:")
    tab.blob_stretch_inner = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stretch_inner.setMinimum(0)
    tab.blob_stretch_inner.setMaximum(100)
    blob_si_val = int(tab._default_float('spotify_visualizer', 'blob_stretch_inner', 0.5) * 100)
    tab.blob_stretch_inner.setValue(max(0, min(100, blob_si_val)))
    tab.blob_stretch_inner.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stretch_inner.setTickInterval(10)
    tab.blob_stretch_inner.setToolTip("How deep the blob can indent inward. Higher = deeper dents.")
    tab.blob_stretch_inner_label = QLabel(f"{tab.blob_stretch_inner.value()}%")
    _bind_slider(tab.blob_stretch_inner, lambda v: tab.blob_stretch_inner_label.setText(f"{v}%"))
    si_layout.addWidget(tab.blob_stretch_inner)
    si_layout.addWidget(tab.blob_stretch_inner_label)
    adv_layout.addWidget(si_row)

    # Outer Stretch (how far outward protrusions extend)
    so_row, so_layout = _aligned_row("Outer Stretch:")
    tab.blob_stretch_outer = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_stretch_outer.setMinimum(0)
    tab.blob_stretch_outer.setMaximum(100)
    blob_so_val = int(tab._default_float('spotify_visualizer', 'blob_stretch_outer', 0.5) * 100)
    tab.blob_stretch_outer.setValue(max(0, min(100, blob_so_val)))
    tab.blob_stretch_outer.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_stretch_outer.setTickInterval(10)
    tab.blob_stretch_outer.setToolTip("How far the blob extends outward. Higher = bigger protrusions.")
    tab.blob_stretch_outer_label = QLabel(f"{tab.blob_stretch_outer.value()}%")
    _bind_slider(tab.blob_stretch_outer, lambda v: tab.blob_stretch_outer_label.setText(f"{v}%"))
    so_layout.addWidget(tab.blob_stretch_outer)
    so_layout.addWidget(tab.blob_stretch_outer_label)
    adv_layout.addWidget(so_row)

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
