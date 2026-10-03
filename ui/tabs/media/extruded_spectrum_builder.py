"""Lazy Settings body for the Extruded Spectrum visualizer."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel

from rendering.gl_programs.extruded_spectrum_options import EXTRUDED_COLOURINGS
from ui.tabs.media.builder_scaffold import bind_setting_signal, build_collapsible_bucket, build_mode_scaffold
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget
from ui.widgets import StyledComboBox

# (setting key, label, slider minimum, slider maximum, tooltip); sliders store hundredths.
_SHAPE_SLIDERS = (
    ("extruded_spectrum_depth", "Bar Depth:", 25, 300,
     "How deep each bar is, as a multiple of its width."),
    ("extruded_spectrum_tilt", "Tilt:", 0, 100,
     "How far the view looks down onto the bars: more shows more of their tops."),
    ("extruded_spectrum_turn", "Turn:", -100, 100,
     "Turns the row of bars to either side, so it is seen at an angle."),
)
_FINISH_SLIDERS = (
    ("extruded_spectrum_hue_drift", "Hue Drift:", 0, 100,
     "How fast spectral colours drift around the colour wheel; zero holds them still."),
    ("extruded_spectrum_gloss", "Gloss:", 0, 100, "Shine on the bars' faces."),
    ("extruded_spectrum_face_mirror", "Mirror Faces:", 0, 100,
     "Gives the bars' faces (not their edges) a polished, reflective surface that catches a "
     "studio's lights as the bars move; zero leaves them plain."),
    ("extruded_spectrum_reflection", "Reflection:", 0, 100,
     "How strongly the bars reflect in the floor beneath them; zero shows no floor."),
)


def build_extruded_spectrum_ui(tab, parent_layout) -> None:
    """Build Extruded Spectrum's body. Its bars, analysis, shape, bar colours and ghosting come
    from Spectrum's settings; only its 3D presentation is its own."""

    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key="extruded_spectrum",
        settings_container_attr="_extruded_spectrum_settings_container",
        preset_slider_attr="_extruded_spectrum_preset_slider",
        normal_attr="_extruded_spectrum_normal",
        advanced_host_attr="_extruded_spectrum_advanced_host",
        advanced_toggle_attr="_extruded_spectrum_adv_toggle",
        advanced_helper_attr="_extruded_spectrum_adv_helper",
        advanced_attr="_extruded_spectrum_advanced",
    )
    _, shape = build_collapsible_bucket(
        tab, scaffold.normal_layout, mode_key="extruded_spectrum", bucket_key="shape", title="Shape",
        helper_text=("Spectrum's bars in 3D. Bar count, response, the shape editor and ghosting follow "
                     "Spectrum's settings."),
    )
    _, finish = build_collapsible_bucket(
        tab, scaffold.advanced_layout, mode_key="extruded_spectrum", bucket_key="finish", title="Finish",
        helper_text="Colour, shine, reflections, edge smoothing and whether the 3D may leave its rectangle.",
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

    for spec in _SHAPE_SLIDERS:
        slider(shape, *spec)

    content = row(finish, "Colouring:")
    tab.extruded_spectrum_colouring = StyledComboBox()
    tab.extruded_spectrum_colouring.addItems(list(EXTRUDED_COLOURINGS))
    tab.extruded_spectrum_colouring.setCurrentText(tab._default_str("spotify_visualizer", "extruded_spectrum_colouring"))
    tab.extruded_spectrum_colouring.setToolTip(
        "Spectral Faces: each bar coloured by its place in the spectrum. Spectral Edges: Spectrum's bar "
        "colour with glowing spectral edges, like Spectrum's Organs. Bar Colours: Spectrum's bar colours.")
    bind_setting_signal(tab, tab.extruded_spectrum_colouring.currentTextChanged, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_colouring)
    content.addStretch()
    for spec in _FINISH_SLIDERS:
        slider(finish, *spec)
    content = row(finish, "Allow Overflow:")
    tab.extruded_spectrum_allow_overflow = QCheckBox("Let the 3D leave the visualizer's rectangle")
    tab.extruded_spectrum_allow_overflow.setProperty("circleIndicator", True)
    tab.extruded_spectrum_allow_overflow.setChecked(
        tab._default_bool("spotify_visualizer", "extruded_spectrum_allow_overflow"))
    tab.extruded_spectrum_allow_overflow.setToolTip(
        "On: the bars keep Spectrum's size and tilted tops, the turn and the reflection may reach past the "
        "rectangle. Off: the whole 3D scene is fitted inside it.")
    bind_setting_signal(tab, tab.extruded_spectrum_allow_overflow.toggled, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_allow_overflow)
    content.addStretch()
    content = row(finish, "Smooth Edges:")
    tab.extruded_spectrum_smooth_edges = QCheckBox("Anti-alias the bars' edge lines at an angle")
    tab.extruded_spectrum_smooth_edges.setProperty("circleIndicator", True)
    tab.extruded_spectrum_smooth_edges.setChecked(
        tab._default_bool("spotify_visualizer", "extruded_spectrum_smooth_edges"))
    tab.extruded_spectrum_smooth_edges.setToolTip(
        "On: the edge lines keep an even, smoothed width however the bars are turned or tilted. "
        "Off: lines are sized as if seen head-on, which thins and roughens them on faces seen at an angle.")
    bind_setting_signal(tab, tab.extruded_spectrum_smooth_edges.toggled, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_smooth_edges)
    content.addStretch()
