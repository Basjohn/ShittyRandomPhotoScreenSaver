"""Spectrum visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QWidget,
    QPushButton,
    QButtonGroup,
    QToolButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import (
    ADV_HELPER_LABEL_STYLE,
    add_aligned_row_widget as shared_add_aligned_row_widget,
    add_aligned_row as shared_add_aligned_row,
)

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

    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key="spectrum",
        settings_container_attr="_spectrum_settings_container",
        preset_slider_attr="_spectrum_preset_slider",
        normal_attr="_spectrum_normal",
        advanced_host_attr="_spectrum_advanced_host",
        advanced_toggle_attr="_spectrum_adv_toggle",
        advanced_helper_attr="_spectrum_adv_helper",
        advanced_attr="_spectrum_advanced",
    )
    spectrum_layout = scaffold.layout
    _normal_layout = scaffold.normal_layout
    _adv_layout = scaffold.advanced_layout

    LABEL_WIDTH = 150

    _, appearance_bucket = build_collapsible_bucket(
        tab,
        _normal_layout,
        mode_key="spectrum",
        bucket_key="appearance",
        title="Appearance",
        helper_text="Spectrum colors and rim-glow styling still apply when hidden.",
        default_expanded=True,
    )
    _, shape_bucket = build_collapsible_bucket(
        tab,
        _normal_layout,
        mode_key="spectrum",
        bucket_key="shape",
        title="Shape",
        helper_text="Spectrum layout and authored silhouette still apply when hidden.",
        default_expanded=True,
    )
    _, render_bucket = build_collapsible_bucket(
        tab,
        _adv_layout,
        mode_key="spectrum",
        bucket_key="render",
        title="Render",
        helper_text="Render-style controls still apply when hidden.",
        default_expanded=True,
    )
    _, audio_bucket = build_collapsible_bucket(
        tab,
        _adv_layout,
        mode_key="spectrum",
        bucket_key="audio",
        title="Audio",
        helper_text="Audio weighting and falloff controls still apply when hidden.",
        default_expanded=True,
    )
    _, ghost_bucket = build_collapsible_bucket(
        tab,
        _adv_layout,
        mode_key="spectrum",
        bucket_key="ghost",
        title="Ghost",
        helper_text="Ghost controls still apply when hidden.",
        default_expanded=True,
    )

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

    def _swatch_row(parent_layout: QVBoxLayout, label_text: str):
        _, content, _ = add_builder_swatch_row(
            parent_layout,
            label_text,
            label_width=LABEL_WIDTH,
        )
        return content

    _mode_button_style = """
        QPushButton {
            background-color: #232323;
            color: #ffffff;
            border: 2px solid #f1f1f1;
            border-radius: 18px;
            padding: 10px 20px;
            font-weight: 600;
            min-height: 18px;
        }
        QPushButton:hover {
            background-color: #2a2a2a;
        }
        QPushButton:checked {
            background-color: #4a4a4a;
            border-color: #f7f7f7;
        }
        QPushButton:disabled {
            color: #7a7a7a;
            border-color: #6a6a6a;
        }
    """

    spotify_vis_fill_row = _swatch_row(appearance_bucket, "Bar Fill Color:")
    tab.vis_fill_color_btn = ColorSwatchButton(title="Choose Beat Bar Fill Color")
    bind_color_button(
        tab,
        tab.vis_fill_color_btn,
        '_spotify_vis_fill_color',
        initial_color=tab._spotify_vis_fill_color,
    )
    spotify_vis_fill_row.addWidget(tab.vis_fill_color_btn)
    spotify_vis_fill_row.addStretch()

    spotify_vis_border_color_row = _swatch_row(appearance_bucket, "Bar Border Color:")
    tab.vis_border_color_btn = ColorSwatchButton(title="Choose Beat Bar Border Color")
    bind_color_button(
        tab,
        tab.vis_border_color_btn,
        '_spotify_vis_border_color',
        initial_color=tab._spotify_vis_border_color,
    )
    spotify_vis_border_color_row.addWidget(tab.vis_border_color_btn)
    spotify_vis_border_color_row.addStretch()

    glow_toggle_row = _aligned_row(appearance_bucket, "")
    tab.spectrum_glow_enabled = QCheckBox("Enable Rim Glow")
    tab.spectrum_glow_enabled.setProperty("circleIndicator", True)
    tab.spectrum_glow_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'spectrum_glow_enabled', False)
    )
    tab.spectrum_glow_enabled.setToolTip(
        "Add a thin emissive rim around Spectrum bars without adding bloom smear."
    )
    bind_setting_signal(tab, tab.spectrum_glow_enabled.stateChanged)
    glow_toggle_row.addWidget(tab.spectrum_glow_enabled)
    glow_toggle_row.addStretch()

    tab._spectrum_glow_widgets: list[QWidget] = []

    spectrum_glow_color_widget, spectrum_glow_color_row = _aligned_row_widget(appearance_bucket, "Glow Color:")
    tab._spectrum_glow_widgets.append(spectrum_glow_color_widget)
    _spectrum_glow_default = getattr(tab, "_settings", {}).get("widgets", {}).get(
        "spotify_visualizer", {}
    ).get("spectrum_glow_color", [110, 220, 255, 235])
    try:
        tab._spectrum_glow_color = QColor(*_spectrum_glow_default)
    except Exception:
        tab._spectrum_glow_color = QColor(110, 220, 255, 235)
    tab.spectrum_glow_color_btn = ColorSwatchButton(title="Choose Spectrum Rim Glow Color")
    bind_color_button(
        tab,
        tab.spectrum_glow_color_btn,
        '_spectrum_glow_color',
        initial_color=tab._spectrum_glow_color,
    )
    spectrum_glow_color_row.addWidget(tab.spectrum_glow_color_btn)
    spectrum_glow_color_row.addStretch()

    spectrum_glow_intensity_widget, spectrum_glow_intensity_row = _aligned_row_widget(appearance_bucket, "Glow Intensity:")
    tab._spectrum_glow_widgets.append(spectrum_glow_intensity_widget)
    tab.spectrum_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_glow_intensity.setMinimum(0)
    tab.spectrum_glow_intensity.setMaximum(150)
    _sg_default = int(tab._default_float('spotify_visualizer', 'spectrum_glow_intensity', 0.55) * 100)
    tab.spectrum_glow_intensity.setValue(max(0, min(150, _sg_default)))
    tab.spectrum_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_glow_intensity.setTickInterval(10)
    tab.spectrum_glow_intensity.setToolTip(
        "How bright the thin Spectrum rim glow appears. Higher = stronger emissive edge."
    )
    bind_setting_signal(
        tab,
        tab.spectrum_glow_intensity.valueChanged,
        updater=lambda v: tab.spectrum_glow_intensity_label.setText(f"{v}%"),
    )
    spectrum_glow_intensity_row.addWidget(tab.spectrum_glow_intensity)
    tab.spectrum_glow_intensity_label = QLabel(f"{_sg_default}%")
    spectrum_glow_intensity_row.addWidget(tab.spectrum_glow_intensity_label)

    def _update_spectrum_glow_visibility(_state=None):
        visible = tab.spectrum_glow_enabled.isChecked()
        for widget in tab._spectrum_glow_widgets:
            widget.setVisible(visible)

    tab.spectrum_glow_enabled.stateChanged.connect(_update_spectrum_glow_visibility)
    _update_spectrum_glow_visibility()

    spotify_vis_border_opacity_row = _aligned_row(appearance_bucket, "Bar Border Opacity:")
    tab.vis_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.vis_border_opacity.setMinimum(0)
    tab.vis_border_opacity.setMaximum(100)
    spotify_vis_border_opacity_pct = int(
        tab._default_float('spotify_visualizer', 'bar_border_opacity', 0.85) * 100
    )
    tab.vis_border_opacity.setValue(spotify_vis_border_opacity_pct)
    tab.vis_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.vis_border_opacity.setTickInterval(5)
    bind_setting_signal(
        tab,
        tab.vis_border_opacity.valueChanged,
        updater=lambda v: tab.vis_border_opacity_label.setText(f"{v}%"),
    )
    spotify_vis_border_opacity_row.addWidget(tab.vis_border_opacity)
    tab.vis_border_opacity_label = QLabel(f"{spotify_vis_border_opacity_pct}%")
    spotify_vis_border_opacity_row.addWidget(tab.vis_border_opacity_label)

    # Ghosting controls
    ghost_toggle_row = _aligned_row(ghost_bucket, "")
    tab.vis_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.vis_ghost_enabled.setProperty("circleIndicator", True)
    tab.vis_ghost_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'spectrum_ghosting_enabled',
                          tab._default_bool('spotify_visualizer', 'ghosting_enabled', True))
    )
    tab.vis_ghost_enabled.setToolTip(
        "When enabled, the visualizer draws trailing ghost bars above the current height."
    )
    bind_setting_signal(tab, tab.vis_ghost_enabled.stateChanged)
    ghost_toggle_row.addWidget(tab.vis_ghost_enabled)
    ghost_toggle_row.addStretch()

    tab._ghost_sub_container = QWidget()
    _ghost_layout = QVBoxLayout(tab._ghost_sub_container)
    _ghost_layout.setContentsMargins(0, 0, 0, 12)
    _ghost_layout.setSpacing(12)

    spotify_vis_ghost_opacity_row = _aligned_row(_ghost_layout, "Ghost Opacity:")
    tab.vis_ghost_opacity_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.vis_ghost_opacity_slider.setMinimum(0)
    tab.vis_ghost_opacity_slider.setMaximum(100)
    ghost_alpha_pct = int(tab._default_float('spotify_visualizer', 'spectrum_ghost_alpha',
                           tab._default_float('spotify_visualizer', 'ghost_alpha', 0.4)) * 100)
    tab.vis_ghost_opacity_slider.setValue(ghost_alpha_pct)
    tab.vis_ghost_opacity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.vis_ghost_opacity_slider.setTickInterval(5)
    bind_setting_signal(
        tab,
        tab.vis_ghost_opacity_slider.valueChanged,
        updater=lambda v: tab.vis_ghost_opacity_label.setText(f"{v}%"),
    )
    spotify_vis_ghost_opacity_row.addWidget(tab.vis_ghost_opacity_slider)
    tab.vis_ghost_opacity_label = QLabel(f"{ghost_alpha_pct}%")
    spotify_vis_ghost_opacity_row.addWidget(tab.vis_ghost_opacity_label)

    spotify_vis_ghost_decay_row = _aligned_row(_ghost_layout, "Ghost Decay Speed:")
    tab.vis_ghost_decay_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.vis_ghost_decay_slider.setMinimum(10)
    tab.vis_ghost_decay_slider.setMaximum(100)
    ghost_decay_slider = int(tab._default_float('spotify_visualizer', 'spectrum_ghost_decay',
                              tab._default_float('spotify_visualizer', 'ghost_decay', 0.4)) * 100)
    tab.vis_ghost_decay_slider.setValue(max(10, min(100, ghost_decay_slider)))
    tab.vis_ghost_decay_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.vis_ghost_decay_slider.setTickInterval(5)
    bind_setting_signal(
        tab,
        tab.vis_ghost_decay_slider.valueChanged,
        updater=lambda v: tab.vis_ghost_decay_label.setText(f"{v / 100.0:.2f}x"),
    )
    spotify_vis_ghost_decay_row.addWidget(tab.vis_ghost_decay_slider)
    tab.vis_ghost_decay_label = QLabel(f"{tab.vis_ghost_decay_slider.value() / 100.0:.2f}x")
    spotify_vis_ghost_decay_row.addWidget(tab.vis_ghost_decay_label)

    ghost_bucket.addWidget(tab._ghost_sub_container)
    tab.vis_ghost_enabled.stateChanged.connect(lambda: _update_ghost_visibility(tab))
    _update_ghost_visibility(tab)

    render_mode_row = _aligned_row(render_bucket, "Render Mode:")
    tab.spectrum_render_mode_group = QButtonGroup(tab)
    tab.spectrum_render_mode_group.setExclusive(True)
    tab.spectrum_render_mode_buttons = {}

    def _make_render_mode_button(text: str, mode: str) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        button.setStyleSheet(_mode_button_style)
        button.setProperty("renderMode", mode)
        button.clicked.connect(lambda _checked=False, selected=mode: _set_render_mode(selected))
        tab.spectrum_render_mode_group.addButton(button)
        tab.spectrum_render_mode_buttons[mode] = button
        return button

    def _set_render_mode(mode: str, *, save: bool = True) -> None:
        for key, button in tab.spectrum_render_mode_buttons.items():
            button.blockSignals(True)
            button.setChecked(key == mode)
            button.blockSignals(False)
        changed = getattr(tab, "_spectrum_render_mode", None) != mode
        if changed:
            tab._spectrum_render_mode = mode
            if save:
                tab._force_visualizer_preset_to_custom()
        if save:
            tab._save_settings()

    tab._set_spectrum_render_mode = _set_render_mode
    tab._spectrum_render_mode = str(tab._default_str('spotify_visualizer', 'spectrum_render_mode', 'bars') or 'bars').lower()
    render_mode_row.addWidget(_make_render_mode_button("SEGMENTS", "segment"))
    render_mode_row.addWidget(_make_render_mode_button("BAR", "bars"))
    render_mode_row.addStretch()
    for key, button in tab.spectrum_render_mode_buttons.items():
        button.setChecked(key == ("segment" if tab._spectrum_render_mode == "segment" else "bars"))

    # Unique Colours Per Bar (rainbow per-bar mode, only relevant when rainbow is on)
    rainbow_row = _aligned_row(render_bucket, "")
    tab.spectrum_rainbow_per_bar = QCheckBox("Unique Colours Per Bar")
    tab.spectrum_rainbow_per_bar.setProperty("circleIndicator", True)
    tab.spectrum_rainbow_per_bar.setChecked(
        tab._default_bool('spotify_visualizer', 'spectrum_rainbow_per_bar', False)
    )
    tab.spectrum_rainbow_per_bar.setToolTip(
        "When 'Taste The Rainbow' is enabled: each bar gets its own unique colour "
        "spread across the rainbow. Off = all bars share one shifting colour."
    )
    bind_setting_signal(tab, tab.spectrum_rainbow_per_bar.stateChanged)
    rainbow_row.addWidget(tab.spectrum_rainbow_per_bar)
    rainbow_row.addStretch()

    # Rainbow Border Participation
    rb_border_row = _aligned_row(render_bucket, "")
    tab.spectrum_rainbow_border = QCheckBox("Rainbow Borders")
    tab.spectrum_rainbow_border.setProperty("circleIndicator", True)
    tab.spectrum_rainbow_border.setChecked(
        tab._default_bool('spotify_visualizer', 'spectrum_rainbow_border', False)
    )
    tab.spectrum_rainbow_border.setToolTip(
        "When rainbow/unique colours are active: bar borders also participate "
        "in the colour shift. Off = borders keep their configured border colour."
    )
    bind_setting_signal(tab, tab.spectrum_rainbow_border.stateChanged)
    rb_border_row.addWidget(tab.spectrum_rainbow_border)
    rb_border_row.addStretch()

    # Border Radius
    _br_row = _aligned_row(render_bucket, "Border Radius:")
    tab.spectrum_border_radius = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_border_radius.setMinimum(0)
    tab.spectrum_border_radius.setMaximum(12)
    _br_default = int(tab._default_float('spotify_visualizer', 'spectrum_border_radius', 0.0))
    tab.spectrum_border_radius.setValue(max(0, min(12, _br_default)))
    tab.spectrum_border_radius.setToolTip("Round bar corners (0 = square, 6 = nicely rounded).")
    bind_setting_signal(
        tab,
        tab.spectrum_border_radius.valueChanged,
        updater=lambda v: tab.spectrum_border_radius_label.setText(f"{v}px"),
    )
    _br_row.addWidget(tab.spectrum_border_radius)
    tab.spectrum_border_radius_label = QLabel(f"{_br_default}px")
    _br_row.addWidget(tab.spectrum_border_radius_label)

    # Mirrored Layout
    _mirror_row = _aligned_row(shape_bucket, "Mirrored Layout:")
    tab.spectrum_mirrored = QCheckBox("Center-out (mirrored shape)")
    tab.spectrum_mirrored.setProperty("circleIndicator", True)
    _mirror_default = tab._default_bool('spotify_visualizer', 'spectrum_mirrored', True)
    tab.spectrum_mirrored.setChecked(_mirror_default)
    tab.spectrum_mirrored.setToolTip(
        "On: mirrored shape profile around the center divider (center ↔ edge symmetry).\n"
        "Off: bars use left-to-right linear profile mapping."
    )
    bind_setting_signal(tab, tab.spectrum_mirrored.stateChanged)
    _mirror_row.addWidget(tab.spectrum_mirrored)
    _mirror_row.addStretch()

    # --- Spectrum Shaping section ---
    _shape_hint = QLabel(
        "Left-click to add a control node (max 5). "
        "Right-click a node to remove it. Drag to reshape."
    )
    _shape_hint.setStyleSheet(ADV_HELPER_LABEL_STYLE)
    _shape_hint.setWordWrap(True)
    shape_bucket.addWidget(_shape_hint)

    # Visual shape editor
    from ui.tabs.media.spectrum_shape_editor import SpectrumShapeEditor
    _mirror_default_for_editor = tab._default_bool('spotify_visualizer', 'spectrum_mirrored', True)
    tab.spectrum_shape_editor = SpectrumShapeEditor(
        parent=None, mirrored=_mirror_default_for_editor,
    )
    tab.spectrum_shape_editor.nodes_changed.connect(tab._save_settings)
    tab.spectrum_shape_editor.notch_positions_changed.connect(tab._save_settings)
    tab.spectrum_shape_editor.lane_strengths_changed.connect(tab._save_settings)
    shape_bucket.addWidget(tab.spectrum_shape_editor)
    # Connect mirrored checkbox to update editor display
    tab.spectrum_mirrored.stateChanged.connect(
        lambda state: tab.spectrum_shape_editor.set_mirrored(bool(state))
    )

    # --- Audio controls that remain global instead of lane-authored ---
    _influence_hint = QLabel(
        "Lane strength now lives in the top arrows inside the shaper. "
        "These controls only handle global reactivity and floor behavior."
    )
    _influence_hint.setStyleSheet(ADV_HELPER_LABEL_STYLE)
    _influence_hint.setWordWrap(True)
    audio_bucket.addWidget(_influence_hint)

    # Reactivity (0–100 → 0.0–1.0)
    _wave_row = _aligned_row(audio_bucket, "Reactivity:")
    tab.spectrum_wave_amplitude = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_wave_amplitude.setMinimum(0)
    tab.spectrum_wave_amplitude.setMaximum(100)
    _wave_default = int(tab._default_float('spotify_visualizer', 'spectrum_wave_amplitude', 0.50) * 100)
    tab.spectrum_wave_amplitude.setValue(max(0, min(100, _wave_default)))
    tab.spectrum_wave_amplitude.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_wave_amplitude.setTickInterval(25)
    tab.spectrum_wave_amplitude.setToolTip("Overall audio reactivity scaling. 0 = calm, 100 = intense.")
    bind_setting_signal(
        tab,
        tab.spectrum_wave_amplitude.valueChanged,
        updater=lambda v: tab.spectrum_wave_amplitude_label.setText(f"{v}%"),
    )
    _wave_row.addWidget(tab.spectrum_wave_amplitude)
    tab.spectrum_wave_amplitude_label = QLabel(f"{_wave_default}%")
    _wave_row.addWidget(tab.spectrum_wave_amplitude_label)

    # Profile Floor (5–30 → 0.05–0.30)
    _floor_row = _aligned_row(audio_bucket, "Profile Floor:")
    tab.spectrum_profile_floor = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_profile_floor.setMinimum(5)
    tab.spectrum_profile_floor.setMaximum(30)
    _floor_default = int(tab._default_float('spotify_visualizer', 'spectrum_profile_floor', 0.12) * 100)
    tab.spectrum_profile_floor.setValue(max(5, min(30, _floor_default)))
    tab.spectrum_profile_floor.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_profile_floor.setTickInterval(5)
    tab.spectrum_profile_floor.setToolTip(
        "Minimum profile-shape floor (visual floor, not technical Manual Floor/noise floor). "
        "Lower = bars can shrink more according to the shape profile."
    )
    bind_setting_signal(
        tab,
        tab.spectrum_profile_floor.valueChanged,
        updater=lambda v: tab.spectrum_profile_floor_label.setText(f"{v / 100.0:.2f}"),
    )
    _floor_row.addWidget(tab.spectrum_profile_floor)
    tab.spectrum_profile_floor_label = QLabel(f"{_floor_default / 100.0:.2f}")
    _floor_row.addWidget(tab.spectrum_profile_floor_label)

    # Drop Speed (50–300 → 0.5–3.0)
    _drop_row = _aligned_row(audio_bucket, "Drop Speed:")
    tab.spectrum_drop_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_drop_speed.setMinimum(50)
    tab.spectrum_drop_speed.setMaximum(300)
    _drop_default = int(tab._default_float('spotify_visualizer', 'spectrum_drop_speed', 1.0) * 100)
    tab.spectrum_drop_speed.setValue(max(50, min(300, _drop_default)))
    tab.spectrum_drop_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_drop_speed.setTickInterval(25)
    tab.spectrum_drop_speed.setToolTip(
        "How fast bars fall after a peak. 1.0x = default, higher = snappier drops, lower = sticky bars."
    )
    bind_setting_signal(
        tab,
        tab.spectrum_drop_speed.valueChanged,
        updater=lambda v: tab.spectrum_drop_speed_label.setText(f"{v / 100.0:.1f}x"),
    )
    _drop_row.addWidget(tab.spectrum_drop_speed)
    tab.spectrum_drop_speed_label = QLabel(f"{_drop_default / 100.0:.1f}x")
    _drop_row.addWidget(tab.spectrum_drop_speed_label)

    # Spectrum card height growth slider (1.0 .. 3.0)
    spectrum_growth_row = _aligned_row(audio_bucket, "Card Height:")
    tab.spectrum_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.spectrum_growth.setMinimum(100)
    tab.spectrum_growth.setMaximum(500)
    spectrum_growth_val = int(tab._default_float('spotify_visualizer', 'spectrum_growth', 1.0) * 100)
    tab.spectrum_growth.setValue(max(100, min(500, spectrum_growth_val)))
    tab.spectrum_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.spectrum_growth.setTickInterval(50)
    tab.spectrum_growth.setToolTip("Height multiplier for the spectrum card. 100% = current default height.")
    bind_setting_signal(
        tab,
        tab.spectrum_growth.valueChanged,
        updater=lambda v: tab.spectrum_growth_label.setText(f"{v / 100.0:.1f}x"),
    )
    spectrum_growth_row.addWidget(tab.spectrum_growth)
    tab.spectrum_growth_label = QLabel(f"{spectrum_growth_val / 100.0:.1f}x")
    spectrum_growth_row.addWidget(tab.spectrum_growth_label)
