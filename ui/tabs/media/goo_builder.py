"""Goo visualizer UI builder (dev-gated behind ``-devgoo``).

Builds a compact settings panel for Goo mode using the shared
``build_mode_scaffold`` + ``build_collapsible_bucket`` helpers, so the
layout matches the other visualizer builders (Spectrum, Blob, Bubble).

Kept intentionally lean during Phase 1 — exposes only the controls the
Goo solver and shader actually consume. Additional tuning buckets can
be added incrementally without reshaping the scaffold.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel, QSlider, QVBoxLayout

from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import add_aligned_row

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


LABEL_WIDTH = 150


def build_goo_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Goo visualizer settings panel and append it to ``parent_layout``."""
    from ui.tabs.widgets_tab import NoWheelSlider

    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key="goo",
        settings_container_attr="_goo_settings_container",
        preset_slider_attr="_goo_preset_slider",
        normal_attr="_goo_normal",
        advanced_host_attr="_goo_advanced_host",
        advanced_toggle_attr="_goo_adv_toggle",
        advanced_helper_attr="_goo_adv_helper",
        advanced_attr="_goo_advanced",
    )
    normal_layout = scaffold.normal_layout
    adv_layout = scaffold.advanced_layout

    _, appearance_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="goo",
        bucket_key="appearance",
        title="Appearance",
        helper_text="Colors, outline, and void sizing still apply when hidden.",
        default_expanded=True,
    )
    _, motion_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="goo",
        bucket_key="motion",
        title="Motion",
        helper_text="Core size and inward edge depth still apply when hidden.",
        default_expanded=True,
    )
    _, ghost_bucket = build_collapsible_bucket(
        tab,
        adv_layout,
        mode_key="goo",
        bucket_key="ghost",
        title="Ghost",
        helper_text="Goo ghosting still applies when hidden.",
        default_expanded=False,
    )

    def _aligned_row(parent_layout: QVBoxLayout, label_text: str, *, wrap: bool = True):
        content, _ = add_aligned_row(
            parent_layout, label_text, label_width=LABEL_WIDTH, wrap=wrap
        )
        return content

    def _swatch_row(parent_layout: QVBoxLayout, label_text: str):
        _, content, _ = add_builder_swatch_row(
            parent_layout, label_text, label_width=LABEL_WIDTH
        )
        return content

    # --- Appearance: swatches -------------------------------------------------
    for attr_name, label_text, color_attr, title in (
        ("goo_color_btn", "Liquid Colour", "_goo_color", "Choose Goo Liquid Color"),
        ("goo_outline_color_btn", "Outline Colour", "_goo_outline_color", "Choose Goo Outline Color"),
        ("goo_shadow_color_btn", "Shadow Colour", "_goo_shadow_color", "Choose Goo Shadow Color"),
    ):
        row = _swatch_row(appearance_bucket, f"{label_text}:")
        btn = ColorSwatchButton(title=title)
        bind_color_button(
            tab,
            btn,
            color_attr,
            initial_color=getattr(tab, color_attr, None),
        )
        setattr(tab, attr_name, btn)
        row.addWidget(btn)
        row.addStretch()

    # --- Appearance: sliders --------------------------------------------------
    outline_row = _aligned_row(appearance_bucket, "Outline Width:")
    tab.goo_outline_width = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.goo_outline_width.setMinimum(0)
    tab.goo_outline_width.setMaximum(12)
    val = int(tab._default_float("spotify_visualizer", "goo_outline_width", 0.008) * 1000)
    val = max(0, min(12, val))
    tab.goo_outline_width.setValue(val)
    tab.goo_outline_width.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.goo_outline_width.setTickInterval(1)
    bind_setting_signal(
        tab,
        tab.goo_outline_width.valueChanged,
        updater=lambda v: tab.goo_outline_width_label.setText(f"{v / 1000.0:.3f}"),
    )
    outline_row.addWidget(tab.goo_outline_width)
    tab.goo_outline_width_label = QLabel(f"{val / 1000.0:.3f}")
    outline_row.addWidget(tab.goo_outline_width_label)

    inward_outline_row = _aligned_row(appearance_bucket, "Inward Line Width:")
    tab.goo_inward_outline_width = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.goo_inward_outline_width.setMinimum(0)
    tab.goo_inward_outline_width.setMaximum(12)
    val = int(tab._default_float("spotify_visualizer", "goo_inward_outline_width", 0.004) * 1000)
    val = max(0, min(12, val))
    tab.goo_inward_outline_width.setValue(val)
    tab.goo_inward_outline_width.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.goo_inward_outline_width.setTickInterval(1)
    bind_setting_signal(
        tab,
        tab.goo_inward_outline_width.valueChanged,
        updater=lambda v: tab.goo_inward_outline_width_label.setText(f"{v / 1000.0:.3f}"),
    )
    inward_outline_row.addWidget(tab.goo_inward_outline_width)
    tab.goo_inward_outline_width_label = QLabel(f"{val / 1000.0:.3f}")
    inward_outline_row.addWidget(tab.goo_inward_outline_width_label)

    shadow_row = _aligned_row(appearance_bucket, "Shadow Strength:")
    tab.goo_shadow_strength = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.goo_shadow_strength.setMinimum(0)
    tab.goo_shadow_strength.setMaximum(100)
    val = int(tab._default_float("spotify_visualizer", "goo_shadow_strength", 0.3) * 100)
    tab.goo_shadow_strength.setValue(max(0, min(100, val)))
    bind_setting_signal(
        tab,
        tab.goo_shadow_strength.valueChanged,
        updater=lambda v: tab.goo_shadow_strength_label.setText(f"{v}%"),
    )
    shadow_row.addWidget(tab.goo_shadow_strength)
    tab.goo_shadow_strength_label = QLabel(f"{val}%")
    shadow_row.addWidget(tab.goo_shadow_strength_label)

    spec_row = _aligned_row(appearance_bucket, "Specular Density:")
    tab.goo_specular_density = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.goo_specular_density.setMinimum(0)
    tab.goo_specular_density.setMaximum(100)
    val = int(tab._default_float("spotify_visualizer", "goo_specular_density", 0.3) * 100)
    tab.goo_specular_density.setValue(max(0, min(100, val)))
    bind_setting_signal(
        tab,
        tab.goo_specular_density.valueChanged,
        updater=lambda v: tab.goo_specular_density_label.setText(f"{v}%"),
    )
    spec_row.addWidget(tab.goo_specular_density)
    tab.goo_specular_density_label = QLabel(f"{val}%")
    spec_row.addWidget(tab.goo_specular_density_label)

    # --- Motion ---------------------------------------------------------------
    growth_row = _aligned_row(motion_bucket, "Card Height:")
    tab.goo_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.goo_growth.setMinimum(100)
    tab.goo_growth.setMaximum(500)
    val = int(tab._default_float("spotify_visualizer", "goo_growth", 3.0) * 100)
    tab.goo_growth.setValue(max(100, min(500, val)))
    tab.goo_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.goo_growth.setTickInterval(50)
    bind_setting_signal(
        tab,
        tab.goo_growth.valueChanged,
        updater=lambda v: tab.goo_growth_label.setText(f"{v / 100.0:.1f}x"),
    )
    growth_row.addWidget(tab.goo_growth)
    tab.goo_growth_label = QLabel(f"{val / 100.0:.1f}x")
    growth_row.addWidget(tab.goo_growth_label)

    core_row = _aligned_row(motion_bucket, "Core Size:")
    tab.goo_core_size = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.goo_core_size.setMinimum(6)
    tab.goo_core_size.setMaximum(30)
    val = int(tab._default_float("spotify_visualizer", "goo_core_size", 0.18) * 100)
    tab.goo_core_size.setValue(max(6, min(30, val)))
    bind_setting_signal(
        tab,
        tab.goo_core_size.valueChanged,
        updater=lambda v: tab.goo_core_size_label.setText(f"{v}%"),
    )
    core_row.addWidget(tab.goo_core_size)
    tab.goo_core_size_label = QLabel(f"{val}%")
    core_row.addWidget(tab.goo_core_size_label)

    inward_row = _aligned_row(motion_bucket, "Inward Depth:")
    tab.goo_edge_inward_depth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.goo_edge_inward_depth.setMinimum(0)
    tab.goo_edge_inward_depth.setMaximum(45)
    val = int(tab._default_float("spotify_visualizer", "goo_edge_inward_depth", 0.18) * 100)
    tab.goo_edge_inward_depth.setValue(max(0, min(45, val)))
    bind_setting_signal(
        tab,
        tab.goo_edge_inward_depth.valueChanged,
        updater=lambda v: tab.goo_edge_inward_depth_label.setText(f"{v}%"),
    )
    inward_row.addWidget(tab.goo_edge_inward_depth)
    tab.goo_edge_inward_depth_label = QLabel(f"{val}%")
    inward_row.addWidget(tab.goo_edge_inward_depth_label)

    # --- Ghost (advanced) -----------------------------------------------------
    toggle_row = _aligned_row(ghost_bucket, "")
    tab.goo_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.goo_ghost_enabled.setProperty("circleIndicator", True)
    tab.goo_ghost_enabled.setChecked(
        tab._default_bool("spotify_visualizer", "goo_ghosting_enabled", False)
    )
    bind_setting_signal(tab, tab.goo_ghost_enabled.stateChanged)
    toggle_row.addWidget(tab.goo_ghost_enabled)
    toggle_row.addStretch()

    ghost_opa_row = _aligned_row(ghost_bucket, "Ghost Opacity:")
    tab.goo_ghost_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.goo_ghost_opacity.setMinimum(0)
    tab.goo_ghost_opacity.setMaximum(100)
    val = int(tab._default_float("spotify_visualizer", "goo_ghost_alpha", 0.0) * 100)
    tab.goo_ghost_opacity.setValue(max(0, min(100, val)))
    bind_setting_signal(
        tab,
        tab.goo_ghost_opacity.valueChanged,
        updater=lambda v: tab.goo_ghost_opacity_label.setText(f"{v}%"),
    )
    ghost_opa_row.addWidget(tab.goo_ghost_opacity)
    tab.goo_ghost_opacity_label = QLabel(f"{val}%")
    ghost_opa_row.addWidget(tab.goo_ghost_opacity_label)

    ghost_decay_row = _aligned_row(ghost_bucket, "Ghost Decay:")
    tab.goo_ghost_decay_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.goo_ghost_decay_slider.setMinimum(10)
    tab.goo_ghost_decay_slider.setMaximum(100)
    val = int(round(tab._default_float("spotify_visualizer", "goo_ghost_decay", 0.4) * 100))
    tab.goo_ghost_decay_slider.setValue(max(10, min(100, val)))
    bind_setting_signal(
        tab,
        tab.goo_ghost_decay_slider.valueChanged,
        updater=lambda v: tab.goo_ghost_decay_label.setText(f"{v / 100.0:.2f}x"),
    )
    ghost_decay_row.addWidget(tab.goo_ghost_decay_slider)
    tab.goo_ghost_decay_label = QLabel(f"{val / 100.0:.2f}x")
    ghost_decay_row.addWidget(tab.goo_ghost_decay_label)


__all__ = ["build_goo_ui"]
