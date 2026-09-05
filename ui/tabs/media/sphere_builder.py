"""Lazy Settings body for the experimental Sphere visualizer."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from ui.tabs.media.builder_scaffold import bind_setting_signal, build_collapsible_bucket, build_mode_scaffold
from ui.tabs.shared_styles import NoWheelSlider, add_aligned_row_widget
from ui.widgets import StyledComboBox


def build_sphere_ui(tab, parent_layout) -> None:
    scaffold = build_mode_scaffold(tab, parent_layout, mode_key="sphere",
        settings_container_attr="_sphere_settings_container", preset_slider_attr="_sphere_preset_slider",
        normal_attr="_sphere_normal", advanced_host_attr="_sphere_advanced_host",
        advanced_toggle_attr="_sphere_adv_toggle", advanced_helper_attr="_sphere_adv_helper",
        advanced_attr="_sphere_advanced")
    _, surface = build_collapsible_bucket(tab, scaffold.normal_layout, mode_key="sphere",
        bucket_key="surface", title="Surface", helper_text="Choose the material, lighting, and surface finish for the sphere.", default_expanded=True)
    _, motion = build_collapsible_bucket(tab, scaffold.normal_layout, mode_key="sphere",
        bucket_key="motion", title="Motion", helper_text="Tune rotation, deformation, and the gentle motion shown while music is quiet.", default_expanded=True)

    def row(layout, label):
        widget, content, _ = add_aligned_row_widget(layout, label, label_width=150)
        return widget, content

    _widget, content = row(surface, "Material:")
    tab.sphere_material = StyledComboBox()
    tab.sphere_material.addItems(["Chrome", "Obsidian", "Magma", "Silver", "Water"])
    tab.sphere_material.setCurrentText(tab._default_str("spotify_visualizer", "sphere_material", "Chrome"))
    bind_setting_signal(tab, tab.sphere_material.currentTextChanged, auto_switch=True)
    content.addWidget(tab.sphere_material); content.addStretch()
    _widget, content = row(surface, "Light Direction:")
    tab.sphere_light_direction = StyledComboBox()
    tab.sphere_light_direction.addItems(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
    tab.sphere_light_direction.setCurrentText(tab._default_str("spotify_visualizer", "sphere_light_direction", "NW").upper())
    bind_setting_signal(tab, tab.sphere_light_direction.currentTextChanged, auto_switch=True)
    content.addWidget(tab.sphere_light_direction); content.addStretch()

    def slider(layout, attr, key, label, maximum, default, suffix, divisor=100.0, minimum=0):
        _widget, content = row(layout, label)
        control = NoWheelSlider(Qt.Orientation.Horizontal)
        control.setRange(minimum, maximum)
        control.setValue(round(float(tab._default_float("spotify_visualizer", key, default)) * divisor))
        value = QLabel()
        def update(number): value.setText(f"{number / divisor:.2f}{suffix}")
        update(control.value())
        control.valueChanged.connect(update)
        bind_setting_signal(tab, control.valueChanged, auto_switch=True)
        setattr(tab, attr, control)
        content.addWidget(control); content.addWidget(value)

    slider(surface, "sphere_gloss", "sphere_gloss", "Gloss:", 100, .65, "")
    slider(surface, "sphere_specular", "sphere_specular", "Specular:", 200, .8, "", 100.0)
    slider(surface, "sphere_surface_detail", "sphere_surface_detail", "Bump Strength:", 200, 1.15, "", 100.0)
    tab.sphere_surface_detail.setToolTip("Controls the strength of the procedural relief.")
    slider(motion, "sphere_deformation", "sphere_deformation", "Deformation:", 200, 1.0, "", 100.0)
    slider(motion, "sphere_size_response", "sphere_size_response", "Size Response:", 200, 1.5, "", 100.0)
    tab.sphere_size_response.setToolTip("Controls whole-sphere growth and shrink from musical transients independently of surface Deformation.")
    slider(motion, "sphere_bass_response", "sphere_bass_response", "Bass Response:", 200, 1.0, "", 100.0)
    slider(motion, "sphere_mid_response", "sphere_mid_response", "Mid Response:", 200, 1.0, "", 100.0)
    slider(motion, "sphere_high_response", "sphere_high_response", "High Response:", 200, 1.0, "", 100.0)
    slider(motion, "sphere_vocal_response", "sphere_vocal_response", "Vocal Response:", 200, 1.4, "", 100.0)
    tab.sphere_vocal_response.setToolTip("Shapes the vocal-frequency range (a mid/high blend); it does not isolate voices.")
    slider(motion, "sphere_bump_reactivity", "sphere_bump_reactivity", "Bump Reactivity:", 200, .65, "", 100.0)
    tab.sphere_bump_reactivity.setToolTip("Controls added relief from music; zero retains the set base relief.")
    slider(motion, "sphere_energy_curve", "sphere_energy_curve", "Energy Curve:", 200, .60, "", 100.0, minimum=20)
    tab.sphere_energy_curve.setToolTip("Lower values make quiet music more responsive; higher values emphasize louder passages.")
    slider(surface, "sphere_material_fx", "sphere_material_fx", "Material Effects:", 200, 1.0, "", 100.0)
    slider(motion, "sphere_rotation_speed", "sphere_rotation_speed", "Rotation:", 200, .35, "x", 100.0)
    slider(motion, "sphere_idle_motion", "sphere_idle_motion", "Idle Motion:", 100, .12, "", 100.0)


__all__ = ["build_sphere_ui"]
