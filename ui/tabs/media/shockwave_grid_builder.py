"""Lazy Settings body for the Shockwave Grid visualizer."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget

# (setting key, label, slider minimum, slider maximum, tooltip); sliders store hundredths.
_WAVE_SLIDERS = (
    ("shockwave_grid_wave_height", "Wave Height:", 0, 100,
     "How high each beat's shockwave lifts the grid."),
    ("shockwave_grid_wave_speed", "Wave Speed:", 0, 100,
     "How fast the shockwaves spread across the grid."),
    ("shockwave_grid_horizon", "Horizon:", 0, 100,
     "How high Spectrum's bars raise the far edge of the grid; zero keeps it flat."),
    ("shockwave_grid_idle", "Idle Swell:", 0, 100,
     "A soft swell that drifts from side to side, so the grid moves between beats; zero holds it still."),
    ("shockwave_grid_tilt", "Tilt:", 0, 100,
     "How far the view looks down onto the grid, from level to straight down (W and S while it shows)."),
    ("shockwave_grid_turn", "Turn:", -100, 100,
     "Turns the grid a full circle (A and D while it shows)."),
)
_LOOK_SLIDERS = (
    ("shockwave_grid_density", "Grid Density:", 0, 100, "How many grid lines there are."),
    ("shockwave_grid_glow", "Glow:", 0, 100,
     "How much the lines and the shockwave crests glow; zero turns the glow off."),
    ("shockwave_grid_floor", "Floor:", 0, 100,
     "How dark the floor between the lines is; zero leaves only the lines over the wallpaper."),
    ("shockwave_grid_scroll", "Scroll:", 0, 100,
     "How fast the grid travels toward you; zero holds it still."),
)
_COLOURS = (
    ("shockwave_grid_line_color", "Line Colour:", "Choose Grid Line Colour",
     "The grid lines' colour."),
    ("shockwave_grid_crest_color", "Crest Colour:", "Choose Shockwave Crest Colour",
     "The colour the lines turn as a shockwave's crest and the horizon pass through them."),
)


def build_shockwave_grid_ui(tab, parent_layout) -> None:
    """Build Shockwave Grid's body. Its bars, analysis and technical response come from
    Spectrum's settings; the grid, its shockwaves and the view are its own."""

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
    _, waves = build_collapsible_bucket(
        tab, scaffold.normal_layout, mode_key="shockwave_grid", bucket_key="waves", title="Waves",
        helper_text=("Beats send shockwaves across a neon grid; Spectrum's bars raise its horizon. "
                     "Bar count and response follow Spectrum's settings."),
    )
    _, look = build_collapsible_bucket(
        tab, scaffold.advanced_layout, mode_key="shockwave_grid", bucket_key="look", title="Look",
        helper_text="Colours, density, glow, the floor, scrolling and whether the grid may leave its rectangle.",
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

    for spec in _WAVE_SLIDERS:
        slider(waves, *spec)
    for key, label, title, tooltip in _COLOURS:
        content = row(look, label)
        colour = tab._color_from_default("spotify_visualizer", key)
        setattr(tab, f"_{key}", colour)
        button = ColorSwatchButton(title=title)
        button.setToolTip(tooltip)
        bind_color_button(tab, button, f"_{key}", auto_switch=True, initial_color=colour)
        setattr(tab, f"{key}_btn", button)
        content.addWidget(button)
        content.addStretch()
    for spec in _LOOK_SLIDERS:
        slider(look, *spec)
    content = row(look, "Allow Overflow:")
    tab.shockwave_grid_allow_overflow = QCheckBox("Let the grid leave the visualizer's rectangle")
    tab.shockwave_grid_allow_overflow.setProperty("circleIndicator", True)
    tab.shockwave_grid_allow_overflow.setChecked(
        tab._default_bool("spotify_visualizer", "shockwave_grid_allow_overflow"))
    tab.shockwave_grid_allow_overflow.setToolTip(
        "On: the grid may reach past the rectangle as it turns and tilts. Off: it is cut at the rectangle.")
    bind_setting_signal(tab, tab.shockwave_grid_allow_overflow.toggled, auto_switch=True)
    content.addWidget(tab.shockwave_grid_allow_overflow)
    content.addStretch()
