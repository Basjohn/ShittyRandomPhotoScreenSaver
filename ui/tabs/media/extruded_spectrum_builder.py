"""Lazy Settings body for the Extruded Spectrum visualizer."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QButtonGroup, QCheckBox, QLabel, QVBoxLayout, QWidget

from ui.tabs.media.builder_scaffold import bind_setting_signal, build_collapsible_bucket, build_mode_scaffold
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget
from ui.widgets import StyledComboBox

# (setting key, label, slider minimum, slider maximum, tooltip); sliders store hundredths.
_SHAPE_SLIDERS = (
    ("extruded_spectrum_depth", "Bar Depth:", 25, 300,
     "How deep each bar is, as a multiple of its width."),
)
_APPEARANCE_SLIDERS = (
    ("extruded_spectrum_hue_drift", "Hue Drift:", 0, 100,
     "How fast Rainbow hues drift across the bars; zero holds the spectral colours still."),
)
_MATERIAL_SLIDERS = (
    ("extruded_spectrum_gloss", "Gloss:", 0, 100, "Shine on the bars' faces."),
    ("extruded_spectrum_face_mirror", "Mirror Faces:", 0, 100,
     "Gives the bars' faces (not their edges) a polished, mirror surface reflecting the wallpaper, "
     "sharper with Gloss; zero leaves them plain."),
)
_REFLECTION_SLIDERS = (
    ("extruded_spectrum_reflection", "Reflection:", 0, 100,
     "How strongly the bars reflect in the floor beneath them; zero shows no floor."),
)
_SHADOW_SLIDERS = (
    ("extruded_spectrum_shadow_strength", "Shadow Strength:", 0, 100,
     "Opacity of the cast shadow (requires Cast Shadow enabled)."),
)


def build_extruded_spectrum_ui(tab, parent_layout) -> None:
    """Build Extruded Spectrum's independently-authored 3D and bar profile."""

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
    _, appearance = build_collapsible_bucket(
        tab, scaffold.normal_layout, mode_key="extruded_spectrum", bucket_key="appearance", title="Appearance",
        helper_text=("Rainbow participation and hue drift are authored explicitly here. Fill and border colour/alpha "
                     "live in this mode's Bar Appearance bucket rather than behind a colouring preset."),
    )
    _, shape = build_collapsible_bucket(
        tab, scaffold.normal_layout, mode_key="extruded_spectrum", bucket_key="shape", title="Shape",
        helper_text="3D bar geometry plus this mode's mirrored/linear silhouette and lane-energy mapping.",
    )
    _, response = build_collapsible_bucket(
        tab, scaffold.normal_layout, mode_key="extruded_spectrum", bucket_key="response", title="Response",
        helper_text="Tune global reactivity, shape-floor support, falloff and smoothing after the authored lane mapping.",
    )
    # One Effects bucket replaces six tiny Material/Reflection/Shadow/Render/Ghost
    # buckets. The Shape editor remains independent; Appearance and Response retain
    # their existing product ownership. No controls/settings are silently dropped.
    _, effects = build_collapsible_bucket(
        tab, scaffold.advanced_layout, mode_key="extruded_spectrum", bucket_key="effects",
        title="3D Effects",
        helper_text="Material finish, floor reflection, directional shadow, overflow and trailing ghosts.",
    )
    material = reflection = shadow = render = ghost = effects

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

    # The old Spectral Faces / Spectral Edges / Bar Colours combo remains only
    # as persisted/runtime compatibility state. Product authoring is explicit:
    # enable Rainbow, then choose which surface participates.
    default_colouring = tab._default_str("spotify_visualizer", "extruded_spectrum_colouring")
    content = row(appearance, "Rainbow:")
    tab.extruded_spectrum_rainbow_enabled = QCheckBox("Enable Rainbow")
    tab.extruded_spectrum_rainbow_enabled.setProperty("circleIndicator", True)
    tab.extruded_spectrum_rainbow_enabled.setChecked(default_colouring != "Bar Colours")
    tab.extruded_spectrum_rainbow_enabled.setToolTip(
        "Off: use the authored Fill/Border colours. On: apply spectral hues to the selected bar surface."
    )
    bind_setting_signal(tab, tab.extruded_spectrum_rainbow_enabled.toggled, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_rainbow_enabled)
    content.addStretch()

    content = row(appearance, "Rainbow On:")
    tab.extruded_spectrum_rainbow_faces = QCheckBox("Faces")
    tab.extruded_spectrum_rainbow_faces.setProperty("circleIndicator", True)
    tab.extruded_spectrum_rainbow_faces.setToolTip(
        "Apply spectral hues to the 3D bar faces while edges keep the authored Border colour."
    )
    tab.extruded_spectrum_rainbow_edges = QCheckBox("Edges")
    tab.extruded_spectrum_rainbow_edges.setProperty("circleIndicator", True)
    tab.extruded_spectrum_rainbow_edges.setToolTip(
        "Apply spectral hues to the bar edges while faces keep the authored Fill colour."
    )
    tab._extruded_spectrum_rainbow_surface_group = QButtonGroup(tab)
    tab._extruded_spectrum_rainbow_surface_group.setExclusive(True)
    tab._extruded_spectrum_rainbow_surface_group.addButton(tab.extruded_spectrum_rainbow_faces)
    tab._extruded_spectrum_rainbow_surface_group.addButton(tab.extruded_spectrum_rainbow_edges)
    if default_colouring == "Spectral Edges":
        tab.extruded_spectrum_rainbow_edges.setChecked(True)
    else:
        tab.extruded_spectrum_rainbow_faces.setChecked(True)
    bind_setting_signal(tab, tab.extruded_spectrum_rainbow_faces.toggled, auto_switch=True)
    bind_setting_signal(tab, tab.extruded_spectrum_rainbow_edges.toggled, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_rainbow_faces)
    content.addWidget(tab.extruded_spectrum_rainbow_edges)
    content.addStretch()

    def _update_rainbow_surface_enabled(_checked=None):
        enabled = tab.extruded_spectrum_rainbow_enabled.isChecked()
        tab.extruded_spectrum_rainbow_faces.setEnabled(enabled)
        tab.extruded_spectrum_rainbow_edges.setEnabled(enabled)

    tab.extruded_spectrum_rainbow_enabled.toggled.connect(_update_rainbow_surface_enabled)
    _update_rainbow_surface_enabled()
    for spec in _APPEARANCE_SLIDERS:
        slider(appearance, *spec)

    for spec in _SHAPE_SLIDERS:
        slider(shape, *spec)

    content = row(shape, "Mirrored Layout:")
    tab.extruded_spectrum_mirrored = QCheckBox("Center-Out (Mirrored Shape)")
    tab.extruded_spectrum_mirrored.setProperty("circleIndicator", True)
    tab.extruded_spectrum_mirrored.setChecked(
        tab._default_bool("spotify_visualizer", "extruded_spectrum_mirrored"))
    tab.extruded_spectrum_mirrored.setToolTip(
        "On: use the center-out profile. Off: use the left-to-right profile.")
    bind_setting_signal(tab, tab.extruded_spectrum_mirrored.stateChanged, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_mirrored)
    content.addStretch()

    hint = QLabel("Left-click to add a control node (max 5). Right-click a node to remove it. Drag to reshape.")
    hint.setWordWrap(True)
    shape.addWidget(hint)
    from ui.tabs.media.spectrum_shape_editor import SpectrumShapeEditor
    tab.extruded_spectrum_shape_editor = SpectrumShapeEditor(
        parent=None,
        mirrored=tab._default_bool("spotify_visualizer", "extruded_spectrum_mirrored"),
        default_nodes=tab._widget_default("spotify_visualizer", "extruded_spectrum_shape_nodes"),
        default_notches_mirrored=tab._widget_default("spotify_visualizer", "extruded_spectrum_notch_positions_mirrored"),
        default_notches_linear=tab._widget_default("spotify_visualizer", "extruded_spectrum_notch_positions_linear"),
        default_lane_strengths_mirrored=tab._widget_default("spotify_visualizer", "extruded_spectrum_lane_strengths_mirrored"),
        default_lane_strengths_linear=tab._widget_default("spotify_visualizer", "extruded_spectrum_lane_strengths_linear"),
    )
    tab.extruded_spectrum_shape_editor.nodes_changed.connect(tab._save_settings)
    tab.extruded_spectrum_shape_editor.notch_positions_changed.connect(tab._save_settings)
    tab.extruded_spectrum_shape_editor.lane_strengths_changed.connect(tab._save_settings)
    shape.addWidget(tab.extruded_spectrum_shape_editor)
    tab.extruded_spectrum_mirrored.stateChanged.connect(
        lambda state: tab.extruded_spectrum_shape_editor.set_mirrored(bool(state))
    )
    for key, label, minimum, maximum, tooltip in (
        ("extruded_spectrum_wave_amplitude", "Reactivity:", 0, 100,
         "Overall motion scaling after the authored lane routing."),
        ("extruded_spectrum_profile_floor", "Shape Floor:", 5, 30,
         "Minimum body retained by the authored bar profile."),
        ("extruded_spectrum_drop_speed", "Falloff:", 50, 300,
         "How quickly the shared bar field falls after an energy drop."),
    ):
        slider(response, key, label, minimum, maximum, tooltip)
    from ui.tabs.media.spectrum_smoothing_controls import build_spectrum_smoothing_controls
    build_spectrum_smoothing_controls(tab, response, mode_key="extruded_spectrum")

    for spec in _MATERIAL_SLIDERS:
        slider(material, *spec)
    content = row(material, "Smooth Edges:")
    tab.extruded_spectrum_smooth_edges = QCheckBox("Anti-alias the bars' edge lines at an angle")
    tab.extruded_spectrum_smooth_edges.setProperty("circleIndicator", True)
    tab.extruded_spectrum_smooth_edges.setChecked(
        tab._default_bool("spotify_visualizer", "extruded_spectrum_smooth_edges"))
    tab.extruded_spectrum_smooth_edges.setToolTip(
        "On: edge lines keep an even, smoothed width however the bars are turned or tilted. "
        "Off: lines are sized as if seen head-on, which thins and roughens them on faces seen at an angle.")
    bind_setting_signal(tab, tab.extruded_spectrum_smooth_edges.toggled, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_smooth_edges)
    content.addStretch()

    for spec in _REFLECTION_SLIDERS:
        slider(reflection, *spec)

    content = row(shadow, "Cast Shadow:")
    tab.extruded_spectrum_shadow_enabled = QCheckBox("Project a shared Scene3D shadow")
    tab.extruded_spectrum_shadow_enabled.setProperty("circleIndicator", True)
    tab.extruded_spectrum_shadow_enabled.setChecked(
        tab._default_bool("spotify_visualizer", "extruded_spectrum_shadow_enabled"))
    tab.extruded_spectrum_shadow_enabled.setToolTip(
        "Draw the optional Scene3D ground shadow using the display's existing shadow direction.")
    bind_setting_signal(tab, tab.extruded_spectrum_shadow_enabled.toggled, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_shadow_enabled)
    content.addStretch()
    content = row(shadow, 'Shadow Reach:')
    tab.extruded_spectrum_shadow_reach = StyledComboBox()
    tab.extruded_spectrum_shadow_reach.addItems(['Nearby', 'Distant'])
    tab.extruded_spectrum_shadow_reach.setCurrentText(
        tab._default_str('spotify_visualizer', 'extruded_spectrum_shadow_reach'))
    tab.extruded_spectrum_shadow_reach.setToolTip(
        'Nearby hugs the base line; Distant casts a longer silhouette. Both inherit the global Widgets shadow direction.')
    bind_setting_signal(tab, tab.extruded_spectrum_shadow_reach.currentTextChanged, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_shadow_reach)
    content.addStretch()
    for spec in _SHADOW_SLIDERS:
        slider(shadow, *spec)
    # Shadow Strength must never look effective while Cast Shadow is off.
    # This is presentation-only UI state; no duplicate settings or preset write.
    tab.extruded_spectrum_shadow_strength.setEnabled(
        tab.extruded_spectrum_shadow_enabled.isChecked())
    tab.extruded_spectrum_shadow_enabled.toggled.connect(
        tab.extruded_spectrum_shadow_strength.setEnabled)

    content = row(render, "Allow Overflow:")
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

    content = row(ghost, "Enable Ghosting:")
    tab.extruded_spectrum_ghosting_enabled = QCheckBox("Draw trailing bar ghosts")
    tab.extruded_spectrum_ghosting_enabled.setProperty("circleIndicator", True)
    tab.extruded_spectrum_ghosting_enabled.setChecked(
        tab._default_bool("spotify_visualizer", "extruded_spectrum_ghosting_enabled"))
    bind_setting_signal(tab, tab.extruded_spectrum_ghosting_enabled.toggled, auto_switch=True)
    content.addWidget(tab.extruded_spectrum_ghosting_enabled)
    content.addStretch()
    ghost_details = QWidget()
    ghost_details_layout = QVBoxLayout(ghost_details)
    ghost_details_layout.setContentsMargins(0, 0, 0, 0)
    ghost_details_layout.setSpacing(12)
    ghost.addWidget(ghost_details)
    for key, label, minimum, maximum, tooltip in (
        ("extruded_spectrum_ghost_alpha", "Ghost Opacity:", 0, 100,
         "Opacity of the bar-history ghosts."),
        ("extruded_spectrum_ghost_decay", "Ghost Decay:", 10, 100,
         "How quickly ghosts descend after a bar falls."),
    ):
        slider(ghost_details_layout, key, label, minimum, maximum, tooltip)
    tab.extruded_spectrum_ghosting_enabled.toggled.connect(ghost_details.setVisible)
    ghost_details.setVisible(tab.extruded_spectrum_ghosting_enabled.isChecked())
