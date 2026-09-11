"""Lazy Settings body for the isolated experimental voxel Sphere visualizer."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QCheckBox

from ui.tabs.media.builder_scaffold import (
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import NoWheelSlider, RecommendedMarkSlider, add_aligned_row_widget
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

# UI-only guidance markers matching the accepted Glass Current golden. These are
# not defaults and do not alter saved/runtime values.
_RECOMMENDED_SLIDER_VALUES: dict[str, float] = {
    "sphere_gloss": 0.75,
    "sphere_specular": 1.08,
    "sphere_fragment_strength": 3.60,
    "sphere_particle_distance": 2.25,
    "sphere_particle_amount": 1.00,
    "sphere_perspective_strength": 1.00,
    "sphere_edge_weight": 1.00,
    "sphere_voxel_size_variation": 0.35,
    "sphere_depth_shading_strength": 0.20,
    "sphere_shadow_opacity": 1.00,
    "sphere_shadow_softness": 0.18,
    "sphere_shadow_distance": 1.00,
    "sphere_shadow_size": 1.00,
    "sphere_size_response": 2.25,
    "sphere_vocal_response": 1.35,
    "sphere_base_rotation_speed": 0.02,
    "sphere_rotation_speed": 0.99,
}


def build_sphere_ui(tab, parent_layout) -> None:
    """Build Sphere's Settings UI without changing its experimental ownership.

    Sphere remains deliberately isolated from shared visualizer setting families.
    This builder may reuse generic *UI widgets/scaffolding*, but all controls below
    persist only canonical ``sphere_*`` state and may not silently acquire shared
    Rainbow, technical-profile, or accepted-mode ownership.
    """

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

    _, appearance = build_collapsible_bucket(
        tab,
        scaffold.normal_layout,
        mode_key="sphere",
        bucket_key="appearance",
        title="Appearance",
        helper_text=(
            "Literal voxel colours, finish and fixed-light presentation. These are "
            "Sphere-local presentation controls and do not author audio response."
        ),
    )
    _, particle_flow = build_collapsible_bucket(
        tab,
        scaffold.normal_layout,
        mode_key="sphere",
        bucket_key="particle_flow",
        title="Particle Flow",
        helper_text=(
            "Detached voxel intake/outtake options. Sub-options keep their authored "
            "values when the master Particle Flow switch is off."
        ),
    )
    _, reaction = build_collapsible_bucket(
        tab,
        scaffold.advanced_layout,
        mode_key="sphere",
        bucket_key="reaction",
        title="Reactivity",
        helper_text=(
            "Music-driven geometry response. These controls affect the isolated Sphere "
            "experiment only; they do not retune shared visualizer analysis."
        ),
    )
    _, rotation = build_collapsible_bucket(
        tab,
        scaffold.advanced_layout,
        mode_key="sphere",
        bucket_key="rotation",
        title="Rotation",
        helper_text=(
            "Base Rotation is the continuous floor; Velocity Reaction adds music-driven "
            "speed without changing phase or direction."
        ),
    )
    _, effects = build_collapsible_bucket(
        tab,
        scaffold.advanced_layout,
        mode_key="sphere",
        bucket_key="effects",
        title="Effects",
        helper_text=(
            "Optional Sphere-only render effects. None may become a shared visualizer "
            "setting family while Sphere remains experimental."
        ),
    )
    def row(layout, label):
        widget, content, _ = add_aligned_row_widget(layout, label, label_width=150)
        return widget, content

    def toggle(layout, attr, key, label, text, tooltip):
        _widget, content = row(layout, label)
        control = QCheckBox(text)
        control.setProperty("circleIndicator", True)
        control.setChecked(tab._default_bool("spotify_visualizer", key))
        control.setToolTip(tooltip)
        bind_setting_signal(tab, control.toggled, auto_switch=True)
        setattr(tab, attr, control)
        content.addWidget(control)
        content.addStretch()
        return control

    def slider(layout, attr, key, label, maximum, suffix, divisor=100.0, minimum=0):
        _widget, content = row(layout, label)
        recommended = _RECOMMENDED_SLIDER_VALUES.get(key)
        if recommended is None:
            control = NoWheelSlider(Qt.Orientation.Horizontal)
        else:
            control = RecommendedMarkSlider(Qt.Orientation.Horizontal)
        control.setRange(minimum, maximum)
        control.setValue(round(float(tab._default_float("spotify_visualizer", key)) * divisor))
        if recommended is not None:
            control.set_recommended_value(round(float(recommended) * divisor))
        value = QLabel()

        def update(number):
            value.setText(f"{number / divisor:.2f}{suffix}")

        update(control.value())
        control.valueChanged.connect(update)
        bind_setting_signal(tab, control.valueChanged, auto_switch=True)
        setattr(tab, attr, control)
        content.addWidget(control)
        content.addWidget(value)
        return control

    # ------------------------------------------------------------------
    # Appearance
    # ------------------------------------------------------------------
    _widget, content = row(appearance, "Finish Preset:")
    tab.sphere_finish = StyledComboBox()
    tab.sphere_finish.addItems(["Custom", *_FINISH_PRESETS.keys()])
    tab.sphere_finish.setCurrentText(tab._default_str("spotify_visualizer", "sphere_finish"))
    tab.sphere_finish.setToolTip(
        "Convenience only: choosing a finish writes the visible Gloss and Specular sliders. "
        "The finish name is never sent to the voxel renderer and cannot recolour blocks."
    )
    content.addWidget(tab.sphere_finish)
    content.addStretch()

    _widget, content = row(appearance, "Fill Color:")
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

    _widget, content = row(appearance, "Edge Color:")
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

    slider(appearance, "sphere_edge_weight", "sphere_edge_weight", "Edge Weight:", 175, "x", 100.0, 25)
    tab.sphere_edge_weight.setToolTip(
        "Controls how much of each existing cube face is treated as the authored Edge Color. 1.0 is the accepted current edge width; lower values thin it and higher values thicken it without adding geometry or another draw."
    )
    slider(appearance, "sphere_voxel_size_variation", "sphere_voxel_size_variation", "Voxel Size Variation:", 100, "", 100.0, 0)
    tab.sphere_voxel_size_variation.setToolTip(
        "Exposes the existing deterministic per-voxel size variation. 0.35 is the accepted current appearance; zero makes every cube uniform and higher values increase the existing variation without changing voxel count or audio response."
    )

    rainbow_master = toggle(
        appearance,
        "sphere_taste_the_rainbow_enabled",
        "sphere_taste_the_rainbow_enabled",
        "Taste The Rainbow:",
        "Enable Sphere-local voxel rainbow",
        "Sphere-only presentation effect. It uses the voxel renderer's own colour field and does not opt Sphere into the shared Rainbow settings family.",
    )
    rainbow_surfaces = toggle(
        appearance,
        "sphere_taste_the_rainbow_surfaces",
        "sphere_taste_the_rainbow_surfaces",
        "Rainbow Surfaces:",
        "Apply rainbow to voxel surfaces",
        "Replaces Fill RGB with one coherent moving partial-spectrum gradient across blocks while preserving the authored Fill alpha.",
    )
    rainbow_edges = toggle(
        appearance,
        "sphere_taste_the_rainbow_edges",
        "sphere_taste_the_rainbow_edges",
        "Rainbow Edges:",
        "Apply rainbow to voxel edges",
        "Replaces Edge RGB with the same coherent moving partial-spectrum gradient while preserving the independently authored Edge alpha.",
    )

    def apply_rainbow_dependency(enabled: bool) -> None:
        for control in (rainbow_surfaces, rainbow_edges):
            control.setEnabled(bool(enabled))

    rainbow_master.toggled.connect(apply_rainbow_dependency)
    apply_rainbow_dependency(rainbow_master.isChecked())

    _widget, content = row(appearance, "Light Direction:")
    tab.sphere_light_direction = StyledComboBox()
    tab.sphere_light_direction.addItems(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    tab.sphere_light_direction.setCurrentText(
        tab._default_str("spotify_visualizer", "sphere_light_direction").upper()
    )
    bind_setting_signal(tab, tab.sphere_light_direction.currentTextChanged, auto_switch=True)
    content.addWidget(tab.sphere_light_direction)
    content.addStretch()

    slider(appearance, "sphere_perspective_strength", "sphere_perspective_strength", "Perspective Strength:", 100, "x", 100.0)
    tab.sphere_perspective_strength.setToolTip(
        "Controls only the existing voxel camera perspective. 1.0 is the accepted current projection; lower values flatten toward orthographic. The range cannot exceed the current golden perspective."
    )

    slider(appearance, "sphere_gloss", "sphere_gloss", "Gloss:", 100, "")
    tab.sphere_gloss.setToolTip(
        "Controls per-face highlight width/smoothness. It does not select or brighten a special cube."
    )
    slider(appearance, "sphere_specular", "sphere_specular", "Specular:", 200, "", 100.0)
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

    # ------------------------------------------------------------------
    # Particle Flow
    # ------------------------------------------------------------------
    flow_master = toggle(
        particle_flow,
        "sphere_fade_incoming_blocks",
        "sphere_fade_incoming_blocks",
        "Particle Flow:",
        "Enable detached voxel intake/outtake",
        "Master detached-voxel presentation. In Intake mode selected shell voxels begin outside and return to their canonical slots; Particle Outtake reverses newly launched cohorts so source voxels leave/fade while replacements fade into the canonical shell.",
    )
    density_control = toggle(
        particle_flow,
        "sphere_incoming_density_response_enabled",
        "sphere_incoming_density_response_enabled",
        "Particle Density Response:",
        "Scale detached voxel count with live energy",
        "Keeps all four stable ingress quadrants participating, but quiet passages launch a smaller subset and strong passages approach the full 46/46/46/70 population. Playing-state silence still admits no new detached voxels even when this option is off.",
    )
    velocity_control = toggle(
        particle_flow,
        "sphere_incoming_transient_velocity_enabled",
        "sphere_incoming_transient_velocity_enabled",
        "Particle Velocity:",
        "Use transient-responsive detached-voxel travel speed",
        "Uses real cohort travel progress. Speed is captured from Sphere-local acoustic contrast at launch; in-flight cohorts do not globally chase later audio.",
    )
    outtake_control = toggle(
        particle_flow,
        "sphere_particle_outtake_enabled",
        "sphere_particle_outtake_enabled",
        "Particle Outtake:",
        "Reverse detached voxel flow outward",
        "New qualified cohorts shed stable shell voxels outward and fade them gently while replacement voxels fade into the canonical shell positions. Direction is captured at launch, so toggling this never reverses a cohort already in flight.",
    )
    particle_amount_control = slider(
        particle_flow,
        "sphere_particle_amount",
        "sphere_particle_amount",
        "Particle Amount:",
        175,
        "x",
        100.0,
        25,
    )
    particle_amount_control.setToolTip(
        "Scales the number of voxels selected after a qualified cohort has already been admitted. It never changes onset thresholds, event qualification, acoustic impact or particle velocity."
    )

    def apply_flow_dependency(enabled: bool) -> None:
        # UI dependency only: preserve authored sub-control state while the master
        # is off. Runtime semantics remain exactly the existing Sphere-local gate.
        for control in (density_control, velocity_control, outtake_control, particle_amount_control):
            control.setEnabled(bool(enabled))

    flow_master.toggled.connect(apply_flow_dependency)
    apply_flow_dependency(flow_master.isChecked())

    # ------------------------------------------------------------------
    # Reactivity
    # ------------------------------------------------------------------
    toggle(
        reaction,
        "sphere_fragment_interpolation_enabled",
        "sphere_fragment_interpolation_enabled",
        "Fragment Interpolation:",
        "Smooth fragment travel (visual only)",
        "Keeps audio/onset admission instantaneous but interpolates detached cube displacement over a few rendered frames. It does not smooth the audio signal, reduce packet strength, blur frames, or add motion blur.",
    )
    slider(reaction, "sphere_fragment_strength", "sphere_fragment_strength", "Fragment Strength:", 900, "", 100.0)
    tab.sphere_fragment_strength.setToolTip(
        "Single authority for earned local sectional displacement. Existing settings migrate exactly from the former Deformation × Block Reactivity product."
    )
    slider(reaction, "sphere_particle_distance", "sphere_particle_distance", "Particle Distance:", 450, "", 100.0)
    tab.sphere_particle_distance.setToolTip(
        "Controls detached intake/outtake travel distance only. It no longer changes local fragment strength."
    )
    slider(reaction, "sphere_size_response", "sphere_size_response", "Size Response:", 254, "", 100.0)
    tab.sphere_size_response.setToolTip(
        "Controls staged slow sustained passage-weight growth without beat-pulsing or flicker. The range stops where the existing growth equation saturates."
    )
    slider(reaction, "sphere_vocal_response", "sphere_vocal_response", "Vocal Response:", 135, "", 100.0)
    tab.sphere_vocal_response.setToolTip(
        "Controls the dominant vocal/mid-high sectional event voice. The range ends at the existing effective maximum rather than exposing a dead tail."
    )

    # ------------------------------------------------------------------
    # Rotation
    # ------------------------------------------------------------------
    slider(rotation, "sphere_base_rotation_speed", "sphere_base_rotation_speed", "Base Rotation:", 50, "x", 100.0)
    tab.sphere_base_rotation_speed.setToolTip(
        "Continuous authored rotation floor/idle velocity."
    )
    slider(rotation, "sphere_rotation_speed", "sphere_rotation_speed", "Velocity Reaction:", 200, "x", 100.0)
    tab.sphere_rotation_speed.setToolTip(
        "Additional rotation velocity driven by current articulation; phase/direction remain continuous."
    )

    # ------------------------------------------------------------------
    # Optional effects
    # ------------------------------------------------------------------
    shadow_master = toggle(
        effects,
        "sphere_shadow_enabled",
        "sphere_shadow_enabled",
        "Drop Shadow:",
        "Enable projected voxel drop shadow",
        "Draws a Sphere-local flat-colour projection of the same rotating/deforming voxel instances. It follows detached particles without shadow maps, mutual lighting, an FBO blur, or another cadence.",
    )
    shadow_opacity = slider(
        effects, "sphere_shadow_opacity", "sphere_shadow_opacity",
        "Shadow Opacity:", 200, "x", 100.0, 0,
    )
    shadow_opacity.setToolTip(
        "Scales the inherited shadow-colour alpha. 1.00x preserves the previous Sphere shadow intensity curve; lower values soften it and values above 1.00x deliberately strengthen it."
    )
    shadow_softness = slider(
        effects, "sphere_shadow_softness", "sphere_shadow_softness",
        "Shadow Softness:", 45, "", 100.0, 0,
    )
    shadow_softness.setToolTip(
        "Controls one cheap expanded feather layer around the projected voxel silhouette. 0 disables that extra layer; 0.18 is the suggested starting point without an offscreen blur pass."
    )
    shadow_distance = slider(
        effects, "sphere_shadow_distance", "sphere_shadow_distance",
        "Shadow Distance:", 250, "x", 100.0, 0,
    )
    shadow_distance.setToolTip(
        "Scales the existing light-opposite Sphere shadow offset. 1.00x preserves the previous distance response, including its small whole-body pulse accent."
    )
    shadow_size = slider(
        effects, "sphere_shadow_size", "sphere_shadow_size",
        "Shadow Size:", 160, "x", 100.0, 60,
    )
    shadow_size.setToolTip(
        "Scales the projected silhouette around the Sphere centre. 1.00x follows the actual voxel projection; detached particle positions remain represented rather than collapsing back to a circular proxy."
    )

    def apply_shadow_dependency(enabled: bool) -> None:
        for control in (shadow_opacity, shadow_softness, shadow_distance, shadow_size):
            control.setEnabled(bool(enabled))

    shadow_master.toggled.connect(apply_shadow_dependency)
    apply_shadow_dependency(shadow_master.isChecked())

    depth_master = toggle(
        effects,
        "sphere_depth_shading_enabled",
        "sphere_depth_shading_enabled",
        "Depth Shading:",
        "Darken rear voxels to reinforce sphere depth",
        "Cheap Sphere-only luminance cue derived from the existing transformed voxel depth. It does not cast shadows, sample neighbouring voxels, desaturate colours, or add a render pass.",
    )
    depth_strength = slider(
        effects,
        "sphere_depth_shading_strength",
        "sphere_depth_shading_strength",
        "Depth Strength:",
        50,
        "",
        100.0,
        0,
    )
    depth_strength.setToolTip(
        "Maximum rear-hemisphere darkening. 0.20 is the suggested restrained value; the front remains unchanged and authored/Rainbow colour hue and alpha are preserved."
    )

    def apply_depth_dependency(enabled: bool) -> None:
        depth_strength.setEnabled(bool(enabled))

    depth_master.toggled.connect(apply_depth_dependency)
    apply_depth_dependency(depth_master.isChecked())

    toggle(
        effects,
        "sphere_cel_shading",
        "sphere_cel_shading",
        "Toon Shading:",
        "Enable hard toon bands + inked cube edges",
        "Uses deliberately hard light bands and strong edge ink. It changes presentation only, never voxel motion or audio reactivity.",
    )
    tracer_master = toggle(
        effects,
        "sphere_light_tracer_enabled",
        "sphere_light_tracer_enabled",
        "Light Tracer:",
        "Enable music-driven light snake",
        "The sole moving bright-block effect. Each accepted audio onset queues one bounded step; travel is speed-capped and settles before fading. Gloss/Specular are per-face finish controls and cannot create a competing bright block.",
    )

    _widget, content = row(effects, "Tracer Color:")
    tab._sphere_tracer_color = tab._color_from_default("spotify_visualizer", "sphere_tracer_color")
    tab.sphere_tracer_color_btn = ColorSwatchButton(title="Choose Sphere Tracer Color")
    tab.sphere_tracer_color_btn.setToolTip(
        "Styles the existing causal tracer only. The default warm cream exactly matches the accepted hard-coded tracer colour; alpha may soften its blend without changing tracer timing or admission."
    )
    bind_color_button(
        tab,
        tab.sphere_tracer_color_btn,
        "_sphere_tracer_color",
        auto_switch=True,
        initial_color=tab._sphere_tracer_color,
    )
    content.addWidget(tab.sphere_tracer_color_btn)
    content.addStretch()

    def apply_tracer_dependency(enabled: bool) -> None:
        tab.sphere_tracer_color_btn.setEnabled(bool(enabled))

    tracer_master.toggled.connect(apply_tracer_dependency)
    apply_tracer_dependency(tracer_master.isChecked())

    toggle(
        effects,
        "sphere_allow_overflow",
        "sphere_allow_overflow",
        "Scene Overflow:",
        "Allow blocks outside the visualizer bounds",
        "Sphere-only render capability. Other visualizer modes remain on the existing clipped path.",
    )



__all__ = ["build_sphere_ui"]
