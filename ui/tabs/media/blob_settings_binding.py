"""Blob visualizer settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from PySide6.QtGui import QColor

from core.logging.logger import get_logger
from ui.color_utils import qcolor_to_list as _qcolor_to_list

logger = get_logger(__name__)

_BLOB_COLOR_DEFAULTS: tuple[tuple[str, str, list[int]], ...] = (
    ("_blob_color", "blob_color", [0, 180, 255, 230]),
    ("_blob_glow_color", "blob_glow_color", [0, 140, 255, 180]),
    ("_blob_edge_color", "blob_edge_color", [100, 220, 255, 230]),
    ("_blob_outline_color", "blob_outline_color", [0, 0, 0, 0]),
)


def load_blob_mode_settings(
    tab,
    spotify_vis_config: Mapping[str, Any] | None,
    *,
    sync_color_button: Callable[[str, str], None],
) -> None:
    """Load Blob-owned settings from the visualizer config into the tab."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}

    if hasattr(tab, "blob_ghost_enabled"):
        tab.blob_ghost_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "blob_ghosting_enabled", False)
        )
    if hasattr(tab, "blob_ghost_opacity"):
        blob_ghost_alpha = int(tab._config_float("spotify_visualizer", config, "blob_ghost_alpha", 0.4) * 100)
        tab.blob_ghost_opacity.setValue(max(0, min(100, blob_ghost_alpha)))
        tab.blob_ghost_opacity_label.setText(f"{blob_ghost_alpha}%")
    if hasattr(tab, "blob_ghost_decay_slider"):
        blob_ghost_decay = int(tab._config_float("spotify_visualizer", config, "blob_ghost_decay", 0.3) * 100)
        tab.blob_ghost_decay_slider.setValue(max(10, min(100, blob_ghost_decay)))
        tab.blob_ghost_decay_label.setText(f"{blob_ghost_decay / 100.0:.2f}x")

    if hasattr(tab, "blob_pulse"):
        blob_pulse_val = int(tab._config_float("spotify_visualizer", config, "blob_pulse", 1.0) * 100)
        tab.blob_pulse.setValue(max(0, min(200, blob_pulse_val)))
        tab.blob_pulse_label.setText(f"{blob_pulse_val / 100.0:.2f}x")

    for attr, key, fallback in _BLOB_COLOR_DEFAULTS:
        data = config.get(key, fallback)
        try:
            setattr(tab, attr, QColor(*data))
        except Exception:
            logger.debug("[BLOB_BINDING] Failed to set %s=%s", attr, data, exc_info=True)
            setattr(tab, attr, QColor(*fallback))

    sync_color_button("blob_fill_color_btn", "_blob_color")
    sync_color_button("blob_glow_color_btn", "_blob_glow_color")
    sync_color_button("blob_edge_color_btn", "_blob_edge_color")
    sync_color_button("blob_outline_color_btn", "_blob_outline_color")

    if hasattr(tab, "blob_width"):
        blob_width_val = int(tab._config_float("spotify_visualizer", config, "blob_width", 1.0) * 100)
        tab.blob_width.setValue(max(30, min(100, blob_width_val)))
        tab.blob_width_label.setText(f"{blob_width_val}%")
    if hasattr(tab, "blob_size"):
        blob_size_val = int(tab._config_float("spotify_visualizer", config, "blob_size", 1.0) * 100)
        tab.blob_size.setValue(max(30, min(200, blob_size_val)))
        tab.blob_size_label.setText(f"{blob_size_val}%")
    if hasattr(tab, "blob_glow_intensity"):
        blob_glow_intensity = int(tab._config_float("spotify_visualizer", config, "blob_glow_intensity", 0.5) * 100)
        tab.blob_glow_intensity.setValue(max(0, min(100, blob_glow_intensity)))
        tab.blob_glow_intensity_label.setText(f"{blob_glow_intensity}%")
    if hasattr(tab, "blob_glow_reactivity"):
        blob_glow_reactivity = int(tab._config_float("spotify_visualizer", config, "blob_glow_reactivity", 1.0) * 100)
        tab.blob_glow_reactivity.setValue(max(0, min(200, blob_glow_reactivity)))
        tab.blob_glow_reactivity_label.setText(f"{blob_glow_reactivity}%")
    if hasattr(tab, "blob_glow_drive_mode"):
        glow_drive = str(
            tab._config_str("spotify_visualizer", config, "blob_glow_drive_mode", "bass")
        ).strip().lower()
        tab.blob_glow_drive_mode.setCurrentIndex(1 if glow_drive == "vocal" else 0)
    if hasattr(tab, "blob_glow_max_size"):
        blob_glow_max_size = int(tab._config_float("spotify_visualizer", config, "blob_glow_max_size", 1.0) * 100)
        tab.blob_glow_max_size.setValue(max(10, min(300, blob_glow_max_size)))
        tab.blob_glow_max_size_label.setText(f"{blob_glow_max_size}%")
    if hasattr(tab, "blob_reactive_glow"):
        tab.blob_reactive_glow.setChecked(
            tab._config_bool("spotify_visualizer", config, "blob_reactive_glow", True)
        )
    if hasattr(tab, "blob_reactive_deformation"):
        blob_reactive_deformation = int(
            tab._config_float("spotify_visualizer", config, "blob_reactive_deformation", 1.0) * 100
        )
        tab.blob_reactive_deformation.setValue(max(0, min(300, blob_reactive_deformation)))
        tab.blob_reactive_deformation_label.setText(f"{blob_reactive_deformation}%")
    if hasattr(tab, "blob_pulse_cap"):
        blob_pulse_cap = int(tab._config_float("spotify_visualizer", config, "blob_pulse_cap", 1.0) * 100)
        tab.blob_pulse_cap.setValue(max(0, min(300, blob_pulse_cap)))
        tab.blob_pulse_cap_label.setText(f"{blob_pulse_cap}%")
    if hasattr(tab, "blob_pulse_release_ms"):
        blob_pulse_release_ms = tab._config_int("spotify_visualizer", config, "blob_pulse_release_ms", 220)
        blob_pulse_release_ms = max(60, min(1500, blob_pulse_release_ms))
        tab.blob_pulse_release_ms.setValue(blob_pulse_release_ms)
        tab.blob_pulse_release_ms_label.setText(f"{blob_pulse_release_ms / 1000:.2f}s")
    if hasattr(tab, "blob_core_scale"):
        blob_core_scale = int(tab._config_float("spotify_visualizer", config, "blob_core_scale", 1.0) * 100)
        tab.blob_core_scale.setValue(max(25, min(250, blob_core_scale)))
        tab.blob_core_scale_label.setText(f"{blob_core_scale}%")
    if hasattr(tab, "blob_stage_gain"):
        blob_stage_gain = int(tab._config_float("spotify_visualizer", config, "blob_stage_gain", 1.0) * 100)
        tab.blob_stage_gain.setValue(max(0, min(200, blob_stage_gain)))
        tab.blob_stage_gain_label.setText(f"{blob_stage_gain}%")
    if hasattr(tab, "blob_core_floor_bias"):
        blob_core_floor_bias = int(tab._config_float("spotify_visualizer", config, "blob_core_floor_bias", 0.35) * 100)
        tab.blob_core_floor_bias.setValue(max(0, min(60, blob_core_floor_bias)))
        tab.blob_core_floor_bias_label.setText(f"{blob_core_floor_bias}%")
    if hasattr(tab, "blob_stage_bias"):
        blob_stage_bias = int(tab._config_float("spotify_visualizer", config, "blob_stage_bias", 0.0) * 100)
        blob_stage_bias = max(-60, min(60, blob_stage_bias))
        tab.blob_stage_bias.setValue(blob_stage_bias)
        tab.blob_stage_bias_label.setText(f"{blob_stage_bias / 100.0:+.2f}")
    if hasattr(tab, "blob_stage2_release_ms"):
        blob_stage2_release_ms = tab._config_int("spotify_visualizer", config, "blob_stage2_release_ms", 900)
        blob_stage2_release_ms = max(400, min(2000, blob_stage2_release_ms))
        tab.blob_stage2_release_ms.setValue(blob_stage2_release_ms)
        tab.blob_stage2_release_ms_label.setText(f"{blob_stage2_release_ms / 1000:.2f}s")
    if hasattr(tab, "blob_stage3_release_ms"):
        blob_stage3_release_ms = tab._config_int("spotify_visualizer", config, "blob_stage3_release_ms", 1200)
        blob_stage3_release_ms = max(400, min(2000, blob_stage3_release_ms))
        tab.blob_stage3_release_ms.setValue(blob_stage3_release_ms)
        tab.blob_stage3_release_ms_label.setText(f"{blob_stage3_release_ms / 1000:.2f}s")
    if hasattr(tab, "blob_constant_wobble"):
        blob_constant_wobble = int(tab._config_float("spotify_visualizer", config, "blob_constant_wobble", 1.0) * 100)
        tab.blob_constant_wobble.setValue(max(0, min(200, blob_constant_wobble)))
        tab.blob_constant_wobble_label.setText(f"{blob_constant_wobble}%")
    if hasattr(tab, "blob_reactive_wobble"):
        blob_reactive_wobble = int(tab._config_float("spotify_visualizer", config, "blob_reactive_wobble", 1.0) * 100)
        tab.blob_reactive_wobble.setValue(max(0, min(300, blob_reactive_wobble)))
        tab.blob_reactive_wobble_label.setText(f"{blob_reactive_wobble}%")
    if hasattr(tab, "blob_stretch_tendency"):
        blob_stretch_tendency = int(tab._config_float("spotify_visualizer", config, "blob_stretch_tendency", 0.35) * 100)
        tab.blob_stretch_tendency.setValue(max(0, min(100, blob_stretch_tendency)))
        tab.blob_stretch_tendency_label.setText(f"{blob_stretch_tendency}%")
    if hasattr(tab, "blob_stretch_inner"):
        blob_stretch_inner = int(tab._config_float("spotify_visualizer", config, "blob_stretch_inner", 0.5) * 100)
        tab.blob_stretch_inner.setValue(max(0, min(100, blob_stretch_inner)))
        tab.blob_stretch_inner_label.setText(f"{blob_stretch_inner}%")
    if hasattr(tab, "blob_stretch_outer"):
        blob_stretch_outer = int(tab._config_float("spotify_visualizer", config, "blob_stretch_outer", 0.5) * 100)
        tab.blob_stretch_outer.setValue(max(0, min(100, blob_stretch_outer)))
        tab.blob_stretch_outer_label.setText(f"{blob_stretch_outer}%")
    if hasattr(tab, "blob_growth"):
        blob_growth = int(tab._config_float("spotify_visualizer", config, "blob_growth", 2.5) * 100)
        tab.blob_growth.setValue(max(100, min(500, blob_growth)))
        tab.blob_growth_label.setText(f"{blob_growth / 100.0:.1f}x")

    # --- Blob Shaper ---
    if hasattr(tab, "blob_shaper_enabled"):
        tab.blob_shaper_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "blob_shaper_enabled", False)
        )
    if hasattr(tab, "blob_shaper_base_strength"):
        val = int(tab._config_float("spotify_visualizer", config, "blob_shaper_base_strength", 0.5) * 100)
        tab.blob_shaper_base_strength.setValue(max(0, min(100, val)))
        tab.blob_shaper_base_strength_label.setText(f"{val}%")
    if hasattr(tab, "blob_shaper_react_strength"):
        val = int(tab._config_float("spotify_visualizer", config, "blob_shaper_react_strength", 0.5) * 100)
        tab.blob_shaper_react_strength.setValue(max(0, min(100, val)))
        tab.blob_shaper_react_strength_label.setText(f"{val}%")
    if hasattr(tab, "blob_topology_combo"):
        topo = str(config.get("blob_topology", "circle")).strip().lower()
        tab.blob_topology_combo.setCurrentIndex(1 if topo == "ring" else 0)
    if hasattr(tab, "blob_ring_thickness"):
        val = int(tab._config_float("spotify_visualizer", config, "blob_ring_thickness", 0.3) * 100)
        tab.blob_ring_thickness.setValue(max(5, min(100, val)))
        tab.blob_ring_thickness_label.setText(f"{val}%")
    # Shape editor nodes are loaded directly into the editor widget
    if hasattr(tab, "blob_shape_editor"):
        base_nodes = config.get("blob_shape_base_nodes", [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]])
        react_nodes = config.get("blob_shape_reaction_nodes", [[0.0, 1.0], [0.5, 1.0], [1.0, 1.0]])
        energy_nodes = config.get("blob_shape_energy_nodes", [])
        tab.blob_shape_editor.set_nodes(base_nodes, react_nodes, energy_nodes)


def _collect_blob_shape_editor(tab) -> dict[str, Any]:
    """Collect shape editor node data from the tab's blob_shape_editor widget."""
    if not hasattr(tab, "blob_shape_editor"):
        return {}
    editor = tab.blob_shape_editor
    base_nodes, react_nodes, energy_nodes = editor.get_nodes()
    return {
        "blob_shape_base_nodes": base_nodes,
        "blob_shape_reaction_nodes": react_nodes,
        "blob_shape_energy_nodes": energy_nodes,
    }


def collect_blob_mode_settings(tab) -> dict[str, Any]:
    """Collect Blob-owned settings from the tab into a config mapping."""
    return {
        "blob_ghosting_enabled": tab.blob_ghost_enabled.isChecked() if hasattr(tab, "blob_ghost_enabled") else False,
        "blob_ghost_alpha": (tab.blob_ghost_opacity.value() if hasattr(tab, "blob_ghost_opacity") else 40) / 100.0,
        "blob_ghost_decay": max(
            0.1,
            (tab.blob_ghost_decay_slider.value() if hasattr(tab, "blob_ghost_decay_slider") else 30) / 100.0,
        ),
        "blob_pulse": (tab.blob_pulse.value() if hasattr(tab, "blob_pulse") else 100) / 100.0,
        "blob_color": _qcolor_to_list(getattr(tab, "_blob_color", None), [0, 180, 255, 230]),
        "blob_glow_color": _qcolor_to_list(getattr(tab, "_blob_glow_color", None), [0, 140, 255, 180]),
        "blob_edge_color": _qcolor_to_list(getattr(tab, "_blob_edge_color", None), [100, 220, 255, 230]),
        "blob_outline_color": _qcolor_to_list(getattr(tab, "_blob_outline_color", None), [0, 0, 0, 0]),
        "blob_width": (tab.blob_width.value() if hasattr(tab, "blob_width") else 100) / 100.0,
        "blob_size": (tab.blob_size.value() if hasattr(tab, "blob_size") else 100) / 100.0,
        "blob_glow_intensity": (tab.blob_glow_intensity.value() if hasattr(tab, "blob_glow_intensity") else 50) / 100.0,
        "blob_glow_reactivity": (tab.blob_glow_reactivity.value() if hasattr(tab, "blob_glow_reactivity") else 100) / 100.0,
        "blob_glow_drive_mode": (
            "vocal"
            if hasattr(tab, "blob_glow_drive_mode") and tab.blob_glow_drive_mode.currentIndex() == 1
            else "bass"
        ),
        "blob_glow_max_size": (tab.blob_glow_max_size.value() if hasattr(tab, "blob_glow_max_size") else 100) / 100.0,
        "blob_reactive_glow": tab.blob_reactive_glow.isChecked() if hasattr(tab, "blob_reactive_glow") else False,
        "blob_reactive_deformation": (
            tab.blob_reactive_deformation.value() if hasattr(tab, "blob_reactive_deformation") else 100
        ) / 100.0,
        "blob_pulse_cap": (tab.blob_pulse_cap.value() if hasattr(tab, "blob_pulse_cap") else 100) / 100.0,
        "blob_pulse_release_ms": tab.blob_pulse_release_ms.value() if hasattr(tab, "blob_pulse_release_ms") else 220,
        "blob_stage_gain": (tab.blob_stage_gain.value() if hasattr(tab, "blob_stage_gain") else 100) / 100.0,
        "blob_core_scale": (tab.blob_core_scale.value() if hasattr(tab, "blob_core_scale") else 100) / 100.0,
        "blob_core_floor_bias": (
            tab.blob_core_floor_bias.value() if hasattr(tab, "blob_core_floor_bias") else 35
        ) / 100.0,
        "blob_stage_bias": (tab.blob_stage_bias.value() if hasattr(tab, "blob_stage_bias") else 0) / 100.0,
        "blob_stage2_release_ms": tab.blob_stage2_release_ms.value() if hasattr(tab, "blob_stage2_release_ms") else 900,
        "blob_stage3_release_ms": tab.blob_stage3_release_ms.value() if hasattr(tab, "blob_stage3_release_ms") else 1200,
        "blob_constant_wobble": (
            tab.blob_constant_wobble.value() if hasattr(tab, "blob_constant_wobble") else 100
        ) / 100.0,
        "blob_reactive_wobble": (
            tab.blob_reactive_wobble.value() if hasattr(tab, "blob_reactive_wobble") else 100
        ) / 100.0,
        "blob_stretch_tendency": (
            tab.blob_stretch_tendency.value() if hasattr(tab, "blob_stretch_tendency") else 35
        ) / 100.0,
        "blob_stretch_inner": (tab.blob_stretch_inner.value() if hasattr(tab, "blob_stretch_inner") else 50) / 100.0,
        "blob_stretch_outer": (tab.blob_stretch_outer.value() if hasattr(tab, "blob_stretch_outer") else 50) / 100.0,
        "blob_growth": (tab.blob_growth.value() if hasattr(tab, "blob_growth") else 250) / 100.0,
        # Blob Shaper
        "blob_shaper_enabled": tab.blob_shaper_enabled.isChecked() if hasattr(tab, "blob_shaper_enabled") else False,
        "blob_shaper_base_strength": (
            tab.blob_shaper_base_strength.value() if hasattr(tab, "blob_shaper_base_strength") else 50
        ) / 100.0,
        "blob_shaper_react_strength": (
            tab.blob_shaper_react_strength.value() if hasattr(tab, "blob_shaper_react_strength") else 50
        ) / 100.0,
        "blob_topology": (
            "ring"
            if hasattr(tab, "blob_topology_combo") and tab.blob_topology_combo.currentIndex() == 1
            else "circle"
        ),
        "blob_ring_thickness": (
            tab.blob_ring_thickness.value() if hasattr(tab, "blob_ring_thickness") else 30
        ) / 100.0,
        **(_collect_blob_shape_editor(tab)),
    }
