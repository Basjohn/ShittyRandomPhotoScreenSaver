"""Lazy Settings body for the experimental voxel Sphere visualizer."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QCheckBox

from ui.tabs.media.builder_scaffold import (
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget
from ui.widgets import StyledComboBox
from ui.styled_popup import ColorSwatchButton


_FINISH_PRESETS: dict[str, tuple[float, float]] = {
    "Neutral": (0.20, 0.25),
    "Matte": (0.05, 0.08),
    "Plastic": (0.55, 0.45),
    "Polished": (0.82, 0.70),
    "Metallic": (0.72, 1.00),
    "Glassy": (0.95, 0.75),
}


def build_sphere_ui(tab, parent_layout) -> None:
    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key="sphere",
        settings_container_attr="_sphere_settings_container",
        preset_slider_attr="_sphere_preset_slider",
        normal_attr="_sphere_normal",
        advanced_host_attr="_sphere_advanced_host",
        advanced_toggle_attr="_sphere_adv_toggle",
        advanced_helper_attr="_sphere_adv_helper",
        advanced_attr="_sphere_advanced",
    )
    _, surface = build_collapsible_bucket(
        tab,
        scaffold.normal_layout,
        mode_key="sphere",
        bucket_key="surface",
        title="Surface",
        helper_text=(
            "Author voxel fill/edge colours and explicit finish controls. Finish Preset "
            "only sets Gloss/Specular; the renderer has no hidden pseudo-material branch."
        ),
    )
    _, motion = build_collapsible_bucket(
        tab,
        scaffold.normal_layout,
        mode_key="sphere",
        bucket_key="motion",
        title="Motion",
        helper_text=(
            "Tune rotation and music-driven block movement. Positional deformation is "
            "audio-causal; quiet-state drift is rotation-only."
        ),
    )

    def row(layout, label):
        widget, content, _ = add_aligned_row_widget(layout, label, label_width=150)
        return widget, content

    _widget, content = row(surface, "Finish Preset:")
    tab.sphere_finish = StyledComboBox()
    tab.sphere_finish.addItems(["Custom", *_FINISH_PRESETS.keys()])
    tab.sphere_finish.setCurrentText(tab._default_str("spotify_visualizer", "sphere_finish"))
    tab.sphere_finish.setToolTip(
        "Convenience only: choosing a finish writes the visible Gloss and Specular sliders. "
        "The finish name is never sent to the voxel renderer and cannot recolour blocks."
    )
    content.addWidget(tab.sphere_finish)
    content.addStretch()

    _widget, content = row(surface, "Fill Color:")
    tab._sphere_fill_color = tab._color_from_default("spotify_visualizer", "sphere_fill_color")
    tab.sphere_fill_color_btn = ColorSwatchButton(title="Choose Sphere Fill Color")
    tab.sphere_fill_color_btn.setToolTip(
        "Literal voxel base RGBA. No finish preset or per-cube pseudo-material multiplier changes this colour."
    )
    bind_color_button(
        tab,
        tab.sphere_fill_color_btn,
        "_sphere_fill_color",
        auto_switch=True,
        initial_color=tab._sphere_fill_color,
    )
    content.addWidget(tab.sphere_fill_color_btn)
    content.addStretch()

    _widget, content = row(surface, "Edge Color:")
    tab._sphere_edge_color = tab._color_from_default("spotify_visualizer", "sphere_edge_color")
    tab.sphere_edge_color_btn = ColorSwatchButton(title="Choose Sphere Edge Color")
    tab.sphere_edge_color_btn.setToolTip(
        "Independent cube bevel/ink RGBA. Its alpha is authored separately from Fill Color alpha."
    )
    bind_color_button(
        tab,
        tab.sphere_edge_color_btn,
        "_sphere_edge_color",
        auto_switch=True,
        initial_color=tab._sphere_edge_color,
    )
    content.addWidget(tab.sphere_edge_color_btn)
    content.addStretch()

    _widget, content = row(surface, "Light Direction:")
    tab.sphere_light_direction = StyledComboBox()
    tab.sphere_light_direction.addItems(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    tab.sphere_light_direction.setCurrentText(
        tab._default_str("spotify_visualizer", "sphere_light_direction").upper()
    )
    bind_setting_signal(tab, tab.sphere_light_direction.currentTextChanged, auto_switch=True)
    content.addWidget(tab.sphere_light_direction)
    content.addStretch()

    def toggle(layout, attr, key, label, text, tooltip):
        _widget, content = row(layout, label)
        control = QCheckBox(text)
        control.setChecked(tab._default_bool("spotify_visualizer", key))
        control.setToolTip(tooltip)
        bind_setting_signal(tab, control.toggled, auto_switch=True)
        setattr(tab, attr, control)
        content.addWidget(control)
        content.addStretch()

    toggle(
        surface,
        "sphere_shadow_enabled",
        "sphere_shadow_enabled",
        "Drop Shadow:",
        "Enable flat Sphere drop shadow",
        "Draws the Sphere-only flat 2D light-opposite shadow. It has no 3D voxel geometry, depth, or accepted-mode ownership.",
    )
    toggle(
        surface,
        "sphere_cel_shading",
        "sphere_cel_shading",
        "Toon Shading:",
        "Enable hard toon bands + inked cube edges",
        "Uses deliberately hard light bands and strong edge ink. It changes presentation only, never voxel motion or audio reactivity.",
    )
    toggle(
        surface,
        "sphere_light_tracer_enabled",
        "sphere_light_tracer_enabled",
        "Light Tracer:",
        "Enable music-driven light snake",
        "The sole moving bright-block effect. Each accepted audio onset queues one bounded step; travel is speed-capped and settles before fading. Gloss/Specular are per-face finish controls and cannot create a competing bright block.",
    )
    toggle(
        surface,
        "sphere_allow_overflow",
        "sphere_allow_overflow",
        "Scene Overflow:",
        "Allow blocks outside the visualizer bounds",
        "Sphere-only render capability. Other visualizer modes remain on the existing clipped path.",
    )
    toggle(
        surface,
        "sphere_fade_incoming_blocks",
        "sphere_fade_incoming_blocks",
        "Incoming Fade:",
        "Fade distant returning blocks",
        "Fades strongly detached outward blocks while they are far from the shell. The detached travel distance is unchanged.",
    )
    toggle(
        surface,
        "sphere_rainbow_ghosting",
        "sphere_rainbow_ghosting",
        "Rainbow Ghosting:",
        "Enable short rainbow trails",
        "Draws a bounded renderer-local history of reactive/moving voxel ghosts only. It adds no timer/poller and has no audio-authoring authority.",
    )

    def slider(layout, attr, key, label, maximum, suffix, divisor=100.0, minimum=0):
        _widget, content = row(layout, label)
        control = NoWheelSlider(Qt.Orientation.Horizontal)
        control.setRange(minimum, maximum)
        control.setValue(round(float(tab._default_float("spotify_visualizer", key)) * divisor))
        value = QLabel()

        def update(number):
            value.setText(f"{number / divisor:.2f}{suffix}")

        update(control.value())
        control.valueChanged.connect(update)
        bind_setting_signal(tab, control.valueChanged, auto_switch=True)
        setattr(tab, attr, control)
        content.addWidget(control)
        content.addWidget(value)

    slider(surface, "sphere_gloss", "sphere_gloss", "Gloss:", 100, "")
    tab.sphere_gloss.setToolTip(
        "Controls per-face highlight width/smoothness. It does not select or brighten a special cube."
    )
    slider(surface, "sphere_specular", "sphere_specular", "Specular:", 200, "", 100.0)
    tab.sphere_specular.setToolTip(
        "Controls per-face reflected sheen strength. Zero is matte; high values increase face shine without a shell-space glow lobe."
    )

    # Finish is a UI bundle only. Any manual finish-axis edit immediately marks
    # the bundle Custom so the label never becomes a second hidden authority.
    finish_edit = {"applying": False}

    def apply_finish(name: str) -> None:
        values = _FINISH_PRESETS.get(str(name))
        if values is None:
            return
        finish_edit["applying"] = True
        try:
            tab.sphere_gloss.setValue(round(values[0] * 100.0))
            tab.sphere_specular.setValue(round(values[1] * 100.0))
        finally:
            finish_edit["applying"] = False

    def mark_finish_custom(_value: int) -> None:
        if finish_edit["applying"]:
            return
        if tab.sphere_finish.currentText() != "Custom":
            tab.sphere_finish.setCurrentText("Custom")

    tab.sphere_finish.currentTextChanged.connect(apply_finish)
    bind_setting_signal(tab, tab.sphere_finish.currentTextChanged, auto_switch=True)
    tab.sphere_gloss.valueChanged.connect(mark_finish_custom)
    tab.sphere_specular.valueChanged.connect(mark_finish_custom)

    slider(surface, "sphere_surface_detail", "sphere_surface_detail", "Block Relief:", 200, "", 100.0)
    tab.sphere_surface_detail.setToolTip(
        "Experimental static: per-block relief is fixed while detached-cube movement is being evaluated."
    )
    toggle(
        motion,
        "sphere_fragment_interpolation_enabled",
        "sphere_fragment_interpolation_enabled",
        "Fragment Interpolation:",
        "Smooth fragment travel (visual only)",
        "Keeps audio/onset admission instantaneous but interpolates detached cube displacement over a few rendered frames. It does not smooth the audio signal, reduce packet strength, blur frames, or add motion blur.",
    )
    slider(motion, "sphere_deformation", "sphere_deformation", "Deformation:", 450, "", 100.0)
    tab.sphere_deformation.setToolTip(
        "Controls the distance of mode-authored sectional in/out movement."
    )
    slider(motion, "sphere_size_response", "sphere_size_response", "Size Response:", 300, "", 100.0)
    tab.sphere_size_response.setToolTip(
        "Controls staged slow sustained passage-weight growth without beat-pulsing or flicker."
    )
    slider(motion, "sphere_bass_response", "sphere_bass_response", "Bass Response:", 200, "", 100.0)
    slider(motion, "sphere_mid_response", "sphere_mid_response", "Mid Response:", 200, "", 100.0)
    slider(motion, "sphere_high_response", "sphere_high_response", "High Response:", 200, "", 100.0)
    slider(motion, "sphere_vocal_response", "sphere_vocal_response", "Vocal Response:", 300, "", 100.0)
    tab.sphere_vocal_response.setToolTip(
        "Controls the dominant vocal/mid-high sectional event voice."
    )
    slider(motion, "sphere_bump_reactivity", "sphere_bump_reactivity", "Block Reactivity:", 200, "", 100.0)
    tab.sphere_bump_reactivity.setToolTip(
        "Scales how strongly an earned local section moves."
    )
    slider(motion, "sphere_energy_curve", "sphere_energy_curve", "Energy Curve:", 200, "", 100.0, minimum=20)
    tab.sphere_energy_curve.setToolTip(
        "Experimental static: the rejected absolute-level energy curve is no longer part of voxel motion."
    )
    slider(motion, "sphere_base_rotation_speed", "sphere_base_rotation_speed", "Base Rotation:", 50, "x", 100.0)
    tab.sphere_base_rotation_speed.setToolTip(
        "Continuous authored rotation floor/idle velocity."
    )
    slider(motion, "sphere_rotation_speed", "sphere_rotation_speed", "Velocity Reaction:", 200, "x", 100.0)
    tab.sphere_rotation_speed.setToolTip(
        "Additional rotation velocity driven by current articulation; phase/direction remain continuous."
    )
    slider(motion, "sphere_idle_motion", "sphere_idle_motion", "Idle Drift:", 100, "", 100.0)
    tab.sphere_idle_motion.setToolTip(
        "Experimental static: independent idle drift is disabled."
    )

    for control, explanation in (
        (tab.sphere_surface_detail, "Block relief is fixed while displacement is the authored reward"),
        (tab.sphere_bass_response, "Bass level is intentionally only a minimal implicit source; kicks own strong low-end motion"),
        (tab.sphere_mid_response, "Section routing is mode-authored rather than a global mid gain"),
        (tab.sphere_high_response, "Section routing is mode-authored rather than a global high gain"),
        (tab.sphere_energy_curve, "Absolute-level energy shaping is not used by the voxel reaction contract"),
        (tab.sphere_idle_motion, "No independent idle motion; Rotation is the sole time-authored movement"),
    ):
        control.setEnabled(False)
        control.setToolTip(f"{control.toolTip()}\n\n{explanation}.")


__all__ = ["build_sphere_ui"]
