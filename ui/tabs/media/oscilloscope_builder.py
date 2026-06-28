"""Oscilloscope visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QWidget,
)
from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import (
    add_aligned_row_widget as shared_add_aligned_row_widget,
    add_aligned_row as shared_add_aligned_row,
)
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def _update_osc_multi_line_visibility(tab) -> None:
    enabled = getattr(tab, 'osc_multi_line', None) and tab.osc_multi_line.isChecked()
    container = getattr(tab, '_osc_multi_container', None)
    if container is not None:
        container.setVisible(bool(enabled))
    line_count = getattr(tab, 'osc_line_count', None)
    show_l2 = enabled and line_count is not None and line_count.value() >= 2
    show_l3 = enabled and line_count is not None and line_count.value() >= 3
    show_l4 = enabled and line_count is not None and line_count.value() >= 4
    show_l5 = enabled and line_count is not None and line_count.value() >= 5
    show_l6 = enabled and line_count is not None and line_count.value() >= 6
    for w in (getattr(tab, '_osc_line2_ghost_row_widget', None),):
        if w is not None:
            w.setVisible(bool(show_l2))
    for w in (getattr(tab, '_osc_l3_row_widget', None), getattr(tab, '_osc_line3_ghost_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l3))
    for w in (getattr(tab, '_osc_l4_row_widget', None), getattr(tab, '_osc_line4_ghost_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l4))
    for w in (getattr(tab, '_osc_l5_row_widget', None), getattr(tab, '_osc_line5_ghost_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l5))
    for w in (getattr(tab, '_osc_l6_row_widget', None), getattr(tab, '_osc_line6_ghost_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l6))


def build_oscilloscope_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Oscilloscope settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider

    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key="oscilloscope",
        settings_container_attr="_osc_settings_container",
        preset_slider_attr="_osc_preset_slider",
        normal_attr="_osc_normal",
        advanced_host_attr="_osc_advanced_host",
        advanced_toggle_attr="_osc_adv_toggle",
        advanced_helper_attr="_osc_adv_helper",
        advanced_attr="_osc_advanced",
    )
    _normal_layout = scaffold.normal_layout
    _adv_layout = scaffold.advanced_layout

    _, appearance_bucket = build_collapsible_bucket(
        tab,
        _normal_layout,
        mode_key="oscilloscope",
        bucket_key="appearance",
        title="Appearance",
        helper_text="Primary line color, glow color, and glow controls still apply when hidden.",
        default_expanded=True,
    )
    _, behavior_bucket = build_collapsible_bucket(
        tab,
        _normal_layout,
        mode_key="oscilloscope",
        bucket_key="behavior",
        title="Behavior",
        helper_text="Wave amplitude, smoothing, speed, and ghosting still apply when hidden.",
        default_expanded=True,
    )
    _, multi_line_bucket = build_collapsible_bucket(
        tab,
        _adv_layout,
        mode_key="oscilloscope",
        bucket_key="multi_line",
        title="Multi-Line",
        helper_text="Extra line colors, glow, and per-line ghost controls still apply when hidden.",
        default_expanded=False,
    )
    _, layout_bucket = build_collapsible_bucket(
        tab,
        _adv_layout,
        mode_key="oscilloscope",
        bucket_key="layout",
        title="Layout",
        helper_text="Card height and multi-line spacing controls still apply when hidden.",
        default_expanded=False,
    )

    LABEL_WIDTH = 150

    def _aligned_row_widget(parent_layout: QVBoxLayout, label_text: str):
        row_widget, content, _ = shared_add_aligned_row_widget(
            parent_layout,
            label_text,
            label_width=LABEL_WIDTH,
        )
        return row_widget, content

    def _aligned_row(parent_layout: QVBoxLayout, label_text: str):
        content, _ = shared_add_aligned_row(
            parent_layout,
            label_text,
            label_width=LABEL_WIDTH,
        )
        return content

    def _swatch_row_widget(parent_layout: QVBoxLayout, label_text: str):
        row_widget, content, _ = add_builder_swatch_row(
            parent_layout,
            label_text,
            label_width=LABEL_WIDTH,
        )
        return row_widget, content

    def _swatch_row(parent_layout: QVBoxLayout, label_text: str):
        _, content = _swatch_row_widget(parent_layout, label_text)
        return content

    osc_line_color_row = _swatch_row(appearance_bucket, "Line Color:")
    tab.osc_line_color_btn = ColorSwatchButton(title="Choose Oscilloscope Line Color")
    bind_color_button(tab, tab.osc_line_color_btn, '_osc_line_color')
    osc_line_color_row.addWidget(tab.osc_line_color_btn)
    osc_line_color_row.addStretch()

    osc_glow_color_row = _swatch_row(appearance_bucket, "Glow Color:")
    tab.osc_glow_color_btn = ColorSwatchButton(title="Choose Oscilloscope Glow Color")
    bind_color_button(tab, tab.osc_glow_color_btn, '_osc_glow_color')
    osc_glow_color_row.addWidget(tab.osc_glow_color_btn)
    osc_glow_color_row.addStretch()

    glow_toggle_row = _aligned_row(appearance_bucket, "")
    tab.osc_glow_enabled = QCheckBox("Enable Glow")
    tab.osc_glow_enabled.setProperty("circleIndicator", True)
    tab.osc_glow_enabled.setChecked(tab._default_bool('spotify_visualizer', 'osc_glow_enabled', True))
    tab.osc_glow_enabled.setToolTip("Draw a soft glow halo around the waveform line.")
    bind_setting_signal(tab, tab.osc_glow_enabled.stateChanged)
    glow_toggle_row.addWidget(tab.osc_glow_enabled)
    glow_toggle_row.addStretch()

    tab._osc_glow_widgets: list[QWidget] = []

    glow_intensity_widget, osc_glow_row = _aligned_row_widget(appearance_bucket, "Glow Intensity:")
    tab._osc_glow_widgets.append(glow_intensity_widget)
    tab.osc_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_glow_intensity.setMinimum(0)
    tab.osc_glow_intensity.setMaximum(100)
    osc_glow_val = int(tab._default_float('spotify_visualizer', 'osc_glow_intensity', 0.5) * 100)
    tab.osc_glow_intensity.setValue(osc_glow_val)
    tab.osc_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_glow_intensity.setTickInterval(10)
    bind_setting_signal(
        tab,
        tab.osc_glow_intensity.valueChanged,
        updater=lambda v: tab.osc_glow_intensity_label.setText(f"{v}%"),
    )
    osc_glow_row.addWidget(tab.osc_glow_intensity)
    tab.osc_glow_intensity_label = QLabel(f"{osc_glow_val}%")
    osc_glow_row.addWidget(tab.osc_glow_intensity_label)

    glow_reactivity_widget, osc_glow_reactivity_row = _aligned_row_widget(appearance_bucket, "Glow Reactivity:")
    tab._osc_glow_widgets.append(glow_reactivity_widget)
    tab.osc_glow_reactivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_glow_reactivity.setMinimum(0)
    tab.osc_glow_reactivity.setMaximum(200)
    osc_glow_reactivity_val = int(
        tab._default_float(
            'spotify_visualizer',
            'osc_glow_reactivity',
            tab._default_float('spotify_visualizer', 'osc_glow_size', 1.0),
        ) * 100
    )
    tab.osc_glow_reactivity.setValue(max(0, min(200, osc_glow_reactivity_val)))
    tab.osc_glow_reactivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_glow_reactivity.setTickInterval(20)
    bind_setting_signal(
        tab,
        tab.osc_glow_reactivity.valueChanged,
        updater=lambda v: tab.osc_glow_reactivity_label.setText(f"{v}%"),
    )
    osc_glow_reactivity_row.addWidget(tab.osc_glow_reactivity)
    tab.osc_glow_reactivity_label = QLabel(f"{osc_glow_reactivity_val}%")
    osc_glow_reactivity_row.addWidget(tab.osc_glow_reactivity_label)
    # Backward-compat alias: legacy code paths may still reference osc_glow_size.
    tab.osc_glow_size = tab.osc_glow_reactivity
    tab.osc_glow_size_label = tab.osc_glow_reactivity_label

    glow_reactive_widget, glow_reactive_row = _aligned_row_widget(appearance_bucket, "")
    tab._osc_glow_widgets.append(glow_reactive_widget)
    tab.osc_reactive_glow = QCheckBox("Reactive Glow (Bass-Driven)")
    tab.osc_reactive_glow.setProperty("circleIndicator", True)
    tab.osc_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'osc_reactive_glow', True))
    tab.osc_reactive_glow.setToolTip("Glow intensity pulses with bass energy.")
    bind_setting_signal(tab, tab.osc_reactive_glow.stateChanged)
    glow_reactive_row.addWidget(tab.osc_reactive_glow)
    glow_reactive_row.addStretch()

    def _update_osc_glow_vis(_s=None):
        visible = tab.osc_glow_enabled.isChecked()
        for widget in tab._osc_glow_widgets:
            widget.setVisible(visible)

    tab.osc_glow_enabled.stateChanged.connect(_update_osc_glow_vis)
    _update_osc_glow_vis()

    ghost_toggle_row = _aligned_row(behavior_bucket, "")
    tab.osc_ghost_enabled = QCheckBox("Ghost Trail")
    tab.osc_ghost_enabled.setProperty("circleIndicator", True)
    tab.osc_ghost_enabled.setChecked(tab._default_bool('spotify_visualizer', 'osc_ghosting_enabled', False))
    tab.osc_ghost_enabled.setToolTip("Show a faded trail of the previous waveform behind the current one.")
    bind_setting_signal(tab, tab.osc_ghost_enabled.stateChanged)
    ghost_toggle_row.addWidget(tab.osc_ghost_enabled)
    ghost_toggle_row.addStretch()

    tab._osc_ghost_widgets: list[QWidget] = []

    ghost_intensity_widget, osc_ghost_row = _aligned_row_widget(behavior_bucket, "Ghost Intensity:")
    tab._osc_ghost_widgets.append(ghost_intensity_widget)
    tab.osc_ghost_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_ghost_intensity.setMinimum(5)
    tab.osc_ghost_intensity.setMaximum(100)
    osc_gi_val = int(tab._default_float('spotify_visualizer', 'osc_ghost_intensity', 0.4) * 100)
    tab.osc_ghost_intensity.setValue(max(5, min(100, osc_gi_val)))
    tab.osc_ghost_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_ghost_intensity.setTickInterval(10)
    tab.osc_ghost_intensity.setToolTip("How visible the ghost trail is. Higher = more opaque trail.")
    bind_setting_signal(
        tab,
        tab.osc_ghost_intensity.valueChanged,
        updater=lambda v: tab.osc_ghost_intensity_label.setText(f"{v}%"),
    )
    osc_ghost_row.addWidget(tab.osc_ghost_intensity)
    tab.osc_ghost_intensity_label = QLabel(f"{osc_gi_val}%")
    osc_ghost_row.addWidget(tab.osc_ghost_intensity_label)

    ghost_decay_widget, osc_ghost_decay_row = _aligned_row_widget(behavior_bucket, "Ghost Decay:")
    tab._osc_ghost_widgets.append(ghost_decay_widget)
    tab.osc_ghost_decay = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_ghost_decay.setMinimum(10)
    tab.osc_ghost_decay.setMaximum(100)
    osc_gd_val = int(tab._default_float('spotify_visualizer', 'osc_ghost_decay', 0.4) * 100)
    tab.osc_ghost_decay.setValue(max(10, min(100, osc_gd_val)))
    tab.osc_ghost_decay.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_ghost_decay.setTickInterval(10)
    tab.osc_ghost_decay.setToolTip("How long the oscilloscope ghost trail persists. Higher = longer trailing outline.")
    bind_setting_signal(
        tab,
        tab.osc_ghost_decay.valueChanged,
        updater=lambda v: tab.osc_ghost_decay_label.setText(f"{v / 100.0:.2f}x"),
    )
    osc_ghost_decay_row.addWidget(tab.osc_ghost_decay)
    tab.osc_ghost_decay_label = QLabel(f"{tab.osc_ghost_decay.value() / 100.0:.2f}x")
    osc_ghost_decay_row.addWidget(tab.osc_ghost_decay_label)

    def _update_osc_ghost_vis(_s=None):
        visible = tab.osc_ghost_enabled.isChecked()
        for widget in tab._osc_ghost_widgets:
            widget.setVisible(visible)

    tab.osc_ghost_enabled.stateChanged.connect(_update_osc_ghost_vis)
    _update_osc_ghost_vis()

    osc_amp_row = _aligned_row(behavior_bucket, "Line Amplitude:")
    tab.osc_line_amplitude = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_line_amplitude.setMinimum(5)
    tab.osc_line_amplitude.setMaximum(100)
    osc_amp_default = tab._default_float('spotify_visualizer', 'osc_line_amplitude', 3.0)
    osc_amp_val = int(osc_amp_default * 10)
    tab.osc_line_amplitude.setValue(max(5, min(100, osc_amp_val)))
    tab.osc_line_amplitude.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_line_amplitude.setTickInterval(10)
    tab.osc_line_amplitude.setToolTip(
        "Renderer-side waveform amplitude multiplier.\n"
        "Lower = flatter line after the shared FFT signal is already computed.\n"
        "Higher = taller visible waveform motion. This is separate from Technical sensitivity."
    )
    bind_setting_signal(
        tab,
        tab.osc_line_amplitude.valueChanged,
        updater=lambda v: tab.osc_line_amplitude_label.setText(f"{v / 10.0:.1f}x"),
    )
    osc_amp_row.addWidget(tab.osc_line_amplitude)
    tab.osc_line_amplitude_label = QLabel(f"{osc_amp_val / 10.0:.1f}x")
    osc_amp_row.addWidget(tab.osc_line_amplitude_label)

    osc_smooth_row = _aligned_row(behavior_bucket, "Smoothing:")
    tab.osc_smoothing = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_smoothing.setMinimum(0)
    tab.osc_smoothing.setMaximum(100)
    osc_smooth_val = int(tab._default_float('spotify_visualizer', 'osc_smoothing', 0.7) * 100)
    tab.osc_smoothing.setValue(max(0, min(100, osc_smooth_val)))
    tab.osc_smoothing.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_smoothing.setTickInterval(10)
    bind_setting_signal(
        tab,
        tab.osc_smoothing.valueChanged,
        updater=lambda v: tab.osc_smoothing_label.setText(f"{v}%"),
    )
    osc_smooth_row.addWidget(tab.osc_smoothing)
    tab.osc_smoothing_label = QLabel(f"{osc_smooth_val}%")
    osc_smooth_row.addWidget(tab.osc_smoothing_label)

    osc_speed_row = _aligned_row(behavior_bucket, "Speed:")
    tab.osc_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_speed.setMinimum(1)
    tab.osc_speed.setMaximum(100)
    osc_speed_val = int(tab._default_float('spotify_visualizer', 'osc_speed', 1.0) * 100)
    tab.osc_speed.setValue(max(1, min(100, osc_speed_val)))
    tab.osc_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_speed.setTickInterval(10)
    tab.osc_speed.setToolTip("Controls how quickly the waveform updates. 100% = real-time, lower = smoother/slower transitions.")
    bind_setting_signal(
        tab,
        tab.osc_speed.valueChanged,
        updater=lambda v: tab.osc_speed_label.setText(f"{v}%"),
    )
    osc_speed_row.addWidget(tab.osc_speed)
    tab.osc_speed_label = QLabel(f"{osc_speed_val}%")
    osc_speed_row.addWidget(tab.osc_speed_label)

    osc_line_dim_row = _aligned_row(multi_line_bucket, "")
    tab.osc_line_dim = QCheckBox("Dim Lines 2/3 Glow")
    tab.osc_line_dim.setProperty("circleIndicator", True)
    tab.osc_line_dim.setChecked(tab._default_bool('spotify_visualizer', 'osc_line_dim', False))
    tab.osc_line_dim.setToolTip("When enabled, lines 2 and 3 have slightly reduced glow to let the primary line stand out.")
    bind_setting_signal(tab, tab.osc_line_dim.stateChanged)
    osc_line_dim_row.addWidget(tab.osc_line_dim)
    osc_line_dim_row.addStretch()

    osc_lob_row = _aligned_row(layout_bucket, "Line Offset Bias:")
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
    bind_setting_signal(
        tab,
        tab.osc_line_offset_bias.valueChanged,
        updater=lambda v: tab.osc_line_offset_bias_label.setText(f"{v}%"),
    )
    osc_lob_row.addWidget(tab.osc_line_offset_bias)
    tab.osc_line_offset_bias_label = QLabel(f"{osc_lob_val}%")
    osc_lob_row.addWidget(tab.osc_line_offset_bias_label)

    osc_vshift_row = _aligned_row(layout_bucket, "Vertical Shift:")
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
    bind_setting_signal(
        tab,
        tab.osc_vertical_shift.valueChanged,
        updater=lambda v: tab.osc_vertical_shift_label.setText(f"{v}"),
    )
    osc_vshift_row.addWidget(tab.osc_vertical_shift)
    tab.osc_vertical_shift_label = QLabel(f"{osc_vshift_val}")
    osc_vshift_row.addWidget(tab.osc_vertical_shift_label)

    tab.osc_multi_line_row = _aligned_row(multi_line_bucket, "")
    tab.osc_multi_line = QCheckBox("Multi-Line Mode (Up to 3 Lines)")
    tab.osc_multi_line.setProperty("circleIndicator", True)
    tab.osc_multi_line.setChecked(tab._default_int('spotify_visualizer', 'osc_line_count', 1) > 1)
    tab.osc_multi_line.setToolTip("Enable additional waveform lines with different oscillation distributions.")
    bind_setting_signal(tab, tab.osc_multi_line.stateChanged)
    tab.osc_multi_line.stateChanged.connect(lambda: _update_osc_multi_line_visibility(tab))
    tab.osc_multi_line_row.addWidget(tab.osc_multi_line)
    tab.osc_multi_line_row.addStretch()

    tab._osc_multi_container = QWidget()
    ml_layout = QVBoxLayout(tab._osc_multi_container)
    ml_layout.setContentsMargins(0, 0, 0, 12)
    ml_layout.setSpacing(12)

    osc_line_count_row = _aligned_row(ml_layout, "Line Count:")
    tab.osc_line_count = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_line_count.setMinimum(2)
    tab.osc_line_count.setMaximum(6)
    tab.osc_line_count.setValue(max(2, tab._default_int('spotify_visualizer', 'osc_line_count', 1)))
    tab.osc_line_count.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_line_count.setTickInterval(1)
    bind_setting_signal(
        tab,
        tab.osc_line_count.valueChanged,
        updater=lambda v: tab.osc_line_count_label.setText(str(v)),
    )
    tab.osc_line_count.valueChanged.connect(lambda: _update_osc_multi_line_visibility(tab))
    osc_line_count_row.addWidget(tab.osc_line_count)
    tab.osc_line_count_label = QLabel(str(max(2, tab._default_int('spotify_visualizer', 'osc_line_count', 1))))
    osc_line_count_row.addWidget(tab.osc_line_count_label)

    osc_l2_widget, osc_l2_row = _swatch_row_widget(ml_layout, "Line 2:")
    osc_l2_color_col = QVBoxLayout()
    osc_l2_color_label = QLabel("Line Color")
    osc_l2_color_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l2_color_col.addWidget(osc_l2_color_label)
    tab.osc_line2_color_btn = ColorSwatchButton(title="Line 2 Color")
    tab.osc_line2_color_btn.setToolTip("Oscilloscope line 2 colour")
    bind_color_button(tab, tab.osc_line2_color_btn, '_osc_line2_color')
    osc_l2_color_col.addWidget(tab.osc_line2_color_btn)
    osc_l2_row.addLayout(osc_l2_color_col)

    osc_l2_glow_col = QVBoxLayout()
    osc_l2_glow_label = QLabel("Glow Color")
    osc_l2_glow_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l2_glow_col.addWidget(osc_l2_glow_label)
    tab.osc_line2_glow_btn = ColorSwatchButton(title="Line 2 Glow Color")
    tab.osc_line2_glow_btn.setToolTip("Oscilloscope line 2 glow colour")
    bind_color_button(tab, tab.osc_line2_glow_btn, '_osc_line2_glow_color')
    osc_l2_glow_col.addWidget(tab.osc_line2_glow_btn)
    osc_l2_row.addLayout(osc_l2_glow_col)
    osc_l2_row.addStretch()

    tab._osc_line2_ghost_row_widget, osc_l2_ghost_row = _aligned_row_widget(ml_layout, "Line 2 Ghost:")
    tab.osc_ghost_line2_enabled = QCheckBox("Draw Ghost")
    tab.osc_ghost_line2_enabled.setProperty("circleIndicator", True)
    tab.osc_ghost_line2_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'osc_ghost_line2_enabled', True)
    )
    tab.osc_ghost_line2_enabled.setToolTip("Allow the ghost trail to render for oscilloscope line 2.")
    bind_setting_signal(tab, tab.osc_ghost_line2_enabled.stateChanged)
    osc_l2_ghost_row.addWidget(tab.osc_ghost_line2_enabled)
    osc_l2_ghost_row.addStretch()

    tab._osc_l3_row_widget, osc_l3_row = _swatch_row_widget(ml_layout, "Line 3:")

    osc_l3_color_col = QVBoxLayout()
    osc_l3_color_label = QLabel("Line Color")
    osc_l3_color_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l3_color_col.addWidget(osc_l3_color_label)
    tab.osc_line3_color_btn = ColorSwatchButton(title="Line 3 Color")
    tab.osc_line3_color_btn.setToolTip("Oscilloscope line 3 colour")
    bind_color_button(tab, tab.osc_line3_color_btn, '_osc_line3_color')
    osc_l3_color_col.addWidget(tab.osc_line3_color_btn)
    osc_l3_row.addLayout(osc_l3_color_col)

    osc_l3_glow_col = QVBoxLayout()
    osc_l3_glow_label = QLabel("Glow Color")
    osc_l3_glow_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l3_glow_col.addWidget(osc_l3_glow_label)
    tab.osc_line3_glow_btn = ColorSwatchButton(title="Line 3 Glow Color")
    tab.osc_line3_glow_btn.setToolTip("Oscilloscope line 3 glow colour")
    bind_color_button(tab, tab.osc_line3_glow_btn, '_osc_line3_glow_color')
    osc_l3_glow_col.addWidget(tab.osc_line3_glow_btn)
    osc_l3_row.addLayout(osc_l3_glow_col)
    osc_l3_row.addStretch()

    tab._osc_line3_ghost_row_widget, osc_l3_ghost_row = _aligned_row_widget(ml_layout, "Line 3 Ghost:")
    tab.osc_ghost_line3_enabled = QCheckBox("Draw Ghost")
    tab.osc_ghost_line3_enabled.setProperty("circleIndicator", True)
    tab.osc_ghost_line3_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'osc_ghost_line3_enabled', True)
    )
    tab.osc_ghost_line3_enabled.setToolTip("Allow the ghost trail to render for oscilloscope line 3.")
    bind_setting_signal(tab, tab.osc_ghost_line3_enabled.stateChanged)
    osc_l3_ghost_row.addWidget(tab.osc_ghost_line3_enabled)
    osc_l3_ghost_row.addStretch()

    tab._osc_l4_row_widget, osc_l4_row = _swatch_row_widget(ml_layout, "Line 4:")

    osc_l4_color_col = QVBoxLayout()
    osc_l4_color_label = QLabel("Line Color")
    osc_l4_color_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l4_color_col.addWidget(osc_l4_color_label)
    tab.osc_line4_color_btn = ColorSwatchButton(title="Line 4 Color")
    tab.osc_line4_color_btn.setToolTip("Oscilloscope line 4 colour")
    bind_color_button(tab, tab.osc_line4_color_btn, '_osc_line4_color')
    osc_l4_color_col.addWidget(tab.osc_line4_color_btn)
    osc_l4_row.addLayout(osc_l4_color_col)

    osc_l4_glow_col = QVBoxLayout()
    osc_l4_glow_label = QLabel("Glow Color")
    osc_l4_glow_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l4_glow_col.addWidget(osc_l4_glow_label)
    tab.osc_line4_glow_btn = ColorSwatchButton(title="Line 4 Glow Color")
    tab.osc_line4_glow_btn.setToolTip("Oscilloscope line 4 glow colour")
    bind_color_button(tab, tab.osc_line4_glow_btn, '_osc_line4_glow_color')
    osc_l4_glow_col.addWidget(tab.osc_line4_glow_btn)
    osc_l4_row.addLayout(osc_l4_glow_col)
    osc_l4_row.addStretch()

    tab._osc_line4_ghost_row_widget, osc_l4_ghost_row = _aligned_row_widget(ml_layout, "Line 4 Ghost:")
    tab.osc_ghost_line4_enabled = QCheckBox("Draw Ghost")
    tab.osc_ghost_line4_enabled.setProperty("circleIndicator", True)
    tab.osc_ghost_line4_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'osc_ghost_line4_enabled', True)
    )
    tab.osc_ghost_line4_enabled.setToolTip("Allow the ghost trail to render for oscilloscope line 4.")
    bind_setting_signal(tab, tab.osc_ghost_line4_enabled.stateChanged)
    osc_l4_ghost_row.addWidget(tab.osc_ghost_line4_enabled)
    osc_l4_ghost_row.addStretch()

    tab._osc_l5_row_widget, osc_l5_row = _swatch_row_widget(ml_layout, "Line 5:")

    osc_l5_color_col = QVBoxLayout()
    osc_l5_color_label = QLabel("Line Color")
    osc_l5_color_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l5_color_col.addWidget(osc_l5_color_label)
    tab.osc_line5_color_btn = ColorSwatchButton(title="Line 5 Color")
    tab.osc_line5_color_btn.setToolTip("Oscilloscope line 5 colour")
    bind_color_button(tab, tab.osc_line5_color_btn, '_osc_line5_color')
    osc_l5_color_col.addWidget(tab.osc_line5_color_btn)
    osc_l5_row.addLayout(osc_l5_color_col)

    osc_l5_glow_col = QVBoxLayout()
    osc_l5_glow_label = QLabel("Glow Color")
    osc_l5_glow_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l5_glow_col.addWidget(osc_l5_glow_label)
    tab.osc_line5_glow_btn = ColorSwatchButton(title="Line 5 Glow Color")
    tab.osc_line5_glow_btn.setToolTip("Oscilloscope line 5 glow colour")
    bind_color_button(tab, tab.osc_line5_glow_btn, '_osc_line5_glow_color')
    osc_l5_glow_col.addWidget(tab.osc_line5_glow_btn)
    osc_l5_row.addLayout(osc_l5_glow_col)
    osc_l5_row.addStretch()

    tab._osc_line5_ghost_row_widget, osc_l5_ghost_row = _aligned_row_widget(ml_layout, "Line 5 Ghost:")
    tab.osc_ghost_line5_enabled = QCheckBox("Draw Ghost")
    tab.osc_ghost_line5_enabled.setProperty("circleIndicator", True)
    tab.osc_ghost_line5_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'osc_ghost_line5_enabled', True)
    )
    tab.osc_ghost_line5_enabled.setToolTip("Allow the ghost trail to render for oscilloscope line 5.")
    bind_setting_signal(tab, tab.osc_ghost_line5_enabled.stateChanged)
    osc_l5_ghost_row.addWidget(tab.osc_ghost_line5_enabled)
    osc_l5_ghost_row.addStretch()

    tab._osc_l6_row_widget, osc_l6_row = _swatch_row_widget(ml_layout, "Line 6:")

    osc_l6_color_col = QVBoxLayout()
    osc_l6_color_label = QLabel("Line Color")
    osc_l6_color_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l6_color_col.addWidget(osc_l6_color_label)
    tab.osc_line6_color_btn = ColorSwatchButton(title="Line 6 Color")
    tab.osc_line6_color_btn.setToolTip("Oscilloscope line 6 colour")
    bind_color_button(tab, tab.osc_line6_color_btn, '_osc_line6_color')
    osc_l6_color_col.addWidget(tab.osc_line6_color_btn)
    osc_l6_row.addLayout(osc_l6_color_col)

    osc_l6_glow_col = QVBoxLayout()
    osc_l6_glow_label = QLabel("Glow Color")
    osc_l6_glow_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    osc_l6_glow_col.addWidget(osc_l6_glow_label)
    tab.osc_line6_glow_btn = ColorSwatchButton(title="Line 6 Glow Color")
    tab.osc_line6_glow_btn.setToolTip("Oscilloscope line 6 glow colour")
    bind_color_button(tab, tab.osc_line6_glow_btn, '_osc_line6_glow_color')
    osc_l6_glow_col.addWidget(tab.osc_line6_glow_btn)
    osc_l6_row.addLayout(osc_l6_glow_col)
    osc_l6_row.addStretch()

    tab._osc_line6_ghost_row_widget, osc_l6_ghost_row = _aligned_row_widget(ml_layout, "Line 6 Ghost:")
    tab.osc_ghost_line6_enabled = QCheckBox("Draw Ghost")
    tab.osc_ghost_line6_enabled.setProperty("circleIndicator", True)
    tab.osc_ghost_line6_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'osc_ghost_line6_enabled', True)
    )
    tab.osc_ghost_line6_enabled.setToolTip("Allow the ghost trail to render for oscilloscope line 6.")
    bind_setting_signal(tab, tab.osc_ghost_line6_enabled.stateChanged)
    osc_l6_ghost_row.addWidget(tab.osc_ghost_line6_enabled)
    osc_l6_ghost_row.addStretch()

    multi_line_bucket.addWidget(tab._osc_multi_container)
    _update_osc_multi_line_visibility(tab)

    osc_growth_row = _aligned_row(layout_bucket, "Card Height:")
    tab.osc_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.osc_growth.setMinimum(100)
    tab.osc_growth.setMaximum(500)
    osc_growth_val = int(tab._default_float('spotify_visualizer', 'osc_growth', 1.0) * 100)
    tab.osc_growth.setValue(max(100, min(500, osc_growth_val)))
    tab.osc_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.osc_growth.setTickInterval(50)
    tab.osc_growth.setToolTip("Height multiplier for the oscilloscope card.")
    bind_setting_signal(
        tab,
        tab.osc_growth.valueChanged,
        updater=lambda v: tab.osc_growth_label.setText(f"{v / 100.0:.1f}x"),
    )
    osc_growth_row.addWidget(tab.osc_growth)
    tab.osc_growth_label = QLabel(f"{osc_growth_val / 100.0:.1f}x")
    osc_growth_row.addWidget(tab.osc_growth_label)
