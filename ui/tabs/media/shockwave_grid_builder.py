"""Lazy Settings body for the Shockwave Grid visualizer."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import bind_color_button, bind_setting_signal, build_collapsible_bucket, build_mode_scaffold
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget

_WAVE_SLIDERS = (
    ("shockwave_grid_wave_height", "Wave Height:", 0, 100,
     "How high each beat's shockwave lifts the grid."),
    ("shockwave_grid_wave_speed", "Wave Speed:", 0, 100,
     "How fast the shockwaves spread across the grid."),
    ("shockwave_grid_horizon", "Horizon:", 0, 100,
     "How strongly Spectrum's bar field raises the grid horizon."),
    ("shockwave_grid_idle", "Idle Swell:", 0, 100,
     "How much the grid breathes when the music is quiet."),
    ("shockwave_grid_tilt", "Tilt:", 0, 100,
     "How far the view looks down onto the grid (W and S while it shows)."),
    ("shockwave_grid_turn", "Turn:", -100, 100,
     "Turns the grid around its vertical axis (A and D while it shows)."),
)
_RENDER_SLIDERS = (
    ("shockwave_grid_density", "Grid Density:", 0, 100, "How many grid lines there are."),
    ("shockwave_grid_glow", "Glow:", 0, 100,
     "How much the lines and the shockwave crests glow; zero turns the glow off."),
    ("shockwave_grid_floor", "Floor:", 0, 100,
     "How much of the receding grid floor remains visible."),
    ("shockwave_grid_scroll", "Scroll:", 0, 100,
     "How quickly the grid texture travels under the camera."),
)
_COLOURS = (
    ("shockwave_grid_line_color", "Line Colour:", "Choose Grid Line Colour",
     "The base grid line colour, including alpha."),
    ("shockwave_grid_crest_color", "Crest Colour:", "Choose Shockwave Crest Colour",
     "The colour the lines turn as a shockwave's crest and the horizon pass through them, including alpha."),
)


def build_shockwave_grid_ui(tab, parent_layout) -> None:
    """Build Shockwave Grid's body and its consumed source/technical profile."""

    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key="shockwave_grid",
        settings_container_attr="_shockwave_grid_settings_container",
        preset_slider_attr="_shockwave_grid_preset_slider",
        normal_attr="_shockwave_grid_normal",
        advanced_host_attr="_shockwave_grid_advanced_host",
        advanced_toggle_attr="_shockwave_grid_adv_toggle",
        advanced_helper_attr="_shockwave_grid_adv_helper",
        advanced_attr="_shockwave_grid_advanced",
    )
    _, appearance = build_collapsible_bucket(
        tab, scaffold.normal_layout, mode_key="shockwave_grid", bucket_key="appearance", title="Appearance",
        helper_text="Author the grid-line and shockwave-crest colours directly, including alpha.",
    )
    _, waves = build_collapsible_bucket(
        tab, scaffold.normal_layout, mode_key="shockwave_grid", bucket_key="waves", title="Waves",
        helper_text=("Beats send shockwaves across a neon grid; Spectrum's bars raise its horizon. "
                     "This grid owns the horizon's bar count and response."),
    )
    _, response = build_collapsible_bucket(
        tab, scaffold.normal_layout, mode_key="shockwave_grid", bucket_key="response", title="Bar Response",
        helper_text="The shared Spectrum shaper is reused, while this grid owns its layout, nodes, lanes and response.",
    )
    _, render = build_collapsible_bucket(
        tab, scaffold.advanced_layout, mode_key="shockwave_grid", bucket_key="render", title="Render",
        helper_text="Density, glow, floor, scrolling and overflow are rendering axes, not colour authoring.",
    )

    def row(layout, label):
        _widget, content, _ = add_aligned_row_widget(layout, label, label_width=150)
        return content

    def slider(layout, key, label, minimum, maximum, tooltip):
        content = row(layout, label)
        control = NoWheelSlider(Qt.Orientation.Horizontal)
        control.setRange(minimum, maximum)
        control.setValue(round(float(tab._default_float("spotify_visualizer", key)) * 100.0))
        control.setToolTip(tooltip)
        value = QLabel()

        def update(number):
            value.setText(f"{number / 100.0:.2f}")

        update(control.value())
        control.valueChanged.connect(update)
        bind_setting_signal(tab, control.valueChanged, auto_switch=True)
        setattr(tab, key, control)
        content.addWidget(control)
        content.addWidget(value)

    for key, label, title, tooltip in _COLOURS:
        content = row(appearance, label)
        colour = tab._color_from_default("spotify_visualizer", key)
        setattr(tab, f"_{key}", colour)
        button = ColorSwatchButton(title=title)
        button.setToolTip(tooltip)
        bind_color_button(tab, button, f"_{key}", auto_switch=True, initial_color=colour)
        setattr(tab, f"{key}_btn", button)
        content.addWidget(button)
        content.addStretch()

    for spec in _WAVE_SLIDERS:
        slider(waves, *spec)

    content = row(response, "Mirrored Layout:")
    tab.shockwave_grid_mirrored = QCheckBox("Center-Out (Mirrored Shape)")
    tab.shockwave_grid_mirrored.setProperty("circleIndicator", True)
    tab.shockwave_grid_mirrored.setChecked(
        tab._default_bool("spotify_visualizer", "shockwave_grid_mirrored"))
    tab.shockwave_grid_mirrored.setToolTip(
        "On: use the center-out profile. Off: use the left-to-right profile.")
    bind_setting_signal(tab, tab.shockwave_grid_mirrored.stateChanged, auto_switch=True)
    content.addWidget(tab.shockwave_grid_mirrored)
    content.addStretch()

    hint = QLabel("Left-click to add a control node (max 5). Right-click a node to remove it. Drag to reshape.")
    hint.setWordWrap(True)
    response.addWidget(hint)
    from ui.tabs.media.spectrum_shape_editor import SpectrumShapeEditor
    tab.shockwave_grid_shape_editor = SpectrumShapeEditor(
        parent=None,
        mirrored=tab._default_bool("spotify_visualizer", "shockwave_grid_mirrored"),
        default_nodes=tab._widget_default("spotify_visualizer", "shockwave_grid_shape_nodes"),
        default_notches_mirrored=tab._widget_default("spotify_visualizer", "shockwave_grid_notch_positions_mirrored"),
        default_notches_linear=tab._widget_default("spotify_visualizer", "shockwave_grid_notch_positions_linear"),
        default_lane_strengths_mirrored=tab._widget_default("spotify_visualizer", "shockwave_grid_lane_strengths_mirrored"),
        default_lane_strengths_linear=tab._widget_default("spotify_visualizer", "shockwave_grid_lane_strengths_linear"),
    )
    tab.shockwave_grid_shape_editor.nodes_changed.connect(tab._save_settings)
    tab.shockwave_grid_shape_editor.notch_positions_changed.connect(tab._save_settings)
    tab.shockwave_grid_shape_editor.lane_strengths_changed.connect(tab._save_settings)
    response.addWidget(tab.shockwave_grid_shape_editor)
    tab.shockwave_grid_mirrored.stateChanged.connect(
        lambda state: tab.shockwave_grid_shape_editor.set_mirrored(bool(state))
    )
    for spec in (
        ("shockwave_grid_wave_amplitude", "Reactivity:", 0, 100,
         "Overall horizon response after the authored lane routing."),
        ("shockwave_grid_profile_floor", "Shape Floor:", 5, 30,
         "Minimum bar field retained by the authored profile."),
        ("shockwave_grid_drop_speed", "Falloff:", 50, 300,
         "How quickly the shared bar field falls after an energy drop."),
    ):
        slider(response, *spec)
    from ui.tabs.media.spectrum_smoothing_controls import build_spectrum_smoothing_controls
    build_spectrum_smoothing_controls(tab, response, mode_key="shockwave_grid")

    for spec in _RENDER_SLIDERS:
        slider(render, *spec)
    content = row(render, "Allow Overflow:")
    tab.shockwave_grid_allow_overflow = QCheckBox("Let the grid leave the visualizer's rectangle")
    tab.shockwave_grid_allow_overflow.setProperty("circleIndicator", True)
    tab.shockwave_grid_allow_overflow.setChecked(
        tab._default_bool("spotify_visualizer", "shockwave_grid_allow_overflow"))
    tab.shockwave_grid_allow_overflow.setToolTip(
        "On: the grid may reach past the rectangle as it turns and tilts. Off: it is cut at the rectangle.")
    bind_setting_signal(tab, tab.shockwave_grid_allow_overflow.toggled, auto_switch=True)
    content.addWidget(tab.shockwave_grid_allow_overflow)
    content.addStretch()
