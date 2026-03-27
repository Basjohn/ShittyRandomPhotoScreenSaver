"""Spectrum visualizer settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from PySide6.QtGui import QColor

from core.logging.logger import get_logger
from ui.color_utils import qcolor_to_list as _qcolor_to_list

logger = get_logger(__name__)

_SPECTRUM_GLOW_DEFAULT = [110, 220, 255, 235]
_SPECTRUM_LOAD_DEFAULT_NODES = [[0.0, 0.45], [0.4, 0.62], [1.0, 0.70]]
_SPECTRUM_SAVE_DEFAULT_NODES = [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]]
_SPECTRUM_DEFAULT_NOTCHES_MIRRORED = [[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]]
_SPECTRUM_DEFAULT_NOTCHES_LINEAR = [[0.0, "Bass"], [0.25, "Low"], [0.50, "Mid"], [0.75, "Hi-Mid"], [1.0, "Treble"]]


def load_spectrum_mode_settings(
    tab,
    spotify_vis_config: Mapping[str, Any] | None,
    *,
    sync_color_button: Callable[[str, str], None],
    update_ghost_visibility: Callable[[Any], None],
) -> None:
    """Load Spectrum-owned settings from the visualizer config into the tab."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}

    if hasattr(tab, "spectrum_growth"):
        spectrum_growth = int(tab._config_float("spotify_visualizer", config, "spectrum_growth", 1.0) * 100)
        tab.spectrum_growth.setValue(max(100, min(500, spectrum_growth)))
        tab.spectrum_growth_label.setText(f"{spectrum_growth / 100.0:.1f}x")
    if hasattr(tab, "spectrum_single_piece"):
        tab.spectrum_single_piece.setChecked(
            tab._config_bool("spotify_visualizer", config, "spectrum_single_piece", False)
        )
    if hasattr(tab, "spectrum_rainbow_per_bar"):
        tab.spectrum_rainbow_per_bar.setChecked(
            tab._config_bool("spotify_visualizer", config, "spectrum_rainbow_per_bar", False)
        )
    if hasattr(tab, "spectrum_bass_emphasis"):
        spectrum_bass_emphasis = int(tab._config_float("spotify_visualizer", config, "spectrum_bass_emphasis", 0.50) * 100)
        tab.spectrum_bass_emphasis.setValue(max(0, min(100, spectrum_bass_emphasis)))
        tab.spectrum_bass_emphasis_label.setText(f"{spectrum_bass_emphasis}%")
    if hasattr(tab, "spectrum_vocal_position"):
        spectrum_vocal_position = int(tab._config_float("spotify_visualizer", config, "spectrum_vocal_position", 0.40) * 100)
        tab.spectrum_vocal_position.setValue(max(20, min(60, spectrum_vocal_position)))
    if hasattr(tab, "spectrum_mid_suppression"):
        spectrum_mid_suppression = int(
            tab._config_float("spotify_visualizer", config, "spectrum_mid_suppression", 0.50) * 100
        )
        tab.spectrum_mid_suppression.setValue(max(0, min(100, spectrum_mid_suppression)))
        tab.spectrum_mid_suppression_label.setText(f"{spectrum_mid_suppression}%")
    if hasattr(tab, "spectrum_wave_amplitude"):
        spectrum_wave_amplitude = int(tab._config_float("spotify_visualizer", config, "spectrum_wave_amplitude", 0.50) * 100)
        tab.spectrum_wave_amplitude.setValue(max(0, min(100, spectrum_wave_amplitude)))
        tab.spectrum_wave_amplitude_label.setText(f"{spectrum_wave_amplitude}%")
    if hasattr(tab, "spectrum_profile_floor"):
        spectrum_profile_floor = int(tab._config_float("spotify_visualizer", config, "spectrum_profile_floor", 0.12) * 100)
        tab.spectrum_profile_floor.setValue(max(5, min(30, spectrum_profile_floor)))
        tab.spectrum_profile_floor_label.setText(f"{spectrum_profile_floor / 100.0:.2f}")
    if hasattr(tab, "spectrum_drop_speed"):
        spectrum_drop_speed = int(tab._config_float("spotify_visualizer", config, "spectrum_drop_speed", 1.0) * 100)
        tab.spectrum_drop_speed.setValue(max(50, min(300, spectrum_drop_speed)))
        tab.spectrum_drop_speed_label.setText(f"{spectrum_drop_speed / 100.0:.1f}x")
    if hasattr(tab, "spectrum_border_radius"):
        spectrum_border_radius = int(tab._config_float("spotify_visualizer", config, "spectrum_border_radius", 0.0))
        tab.spectrum_border_radius.setValue(max(0, min(12, spectrum_border_radius)))
        tab.spectrum_border_radius_label.setText(f"{spectrum_border_radius}px")
    if hasattr(tab, "spectrum_glow_enabled"):
        tab.spectrum_glow_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "spectrum_glow_enabled", False)
        )
    if hasattr(tab, "spectrum_glow_intensity"):
        spectrum_glow_intensity = int(tab._config_float("spotify_visualizer", config, "spectrum_glow_intensity", 0.55) * 100)
        tab.spectrum_glow_intensity.setValue(max(0, min(150, spectrum_glow_intensity)))
        tab.spectrum_glow_intensity_label.setText(f"{spectrum_glow_intensity}%")

    spectrum_glow_color_data = config.get("spectrum_glow_color", _SPECTRUM_GLOW_DEFAULT)
    try:
        tab._spectrum_glow_color = QColor(*spectrum_glow_color_data)
    except Exception:
        logger.debug("[SPECTRUM_BINDING] Failed to set spectrum_glow_color=%s", spectrum_glow_color_data, exc_info=True)
        tab._spectrum_glow_color = QColor(*_SPECTRUM_GLOW_DEFAULT)
    sync_color_button("spectrum_glow_color_btn", "_spectrum_glow_color")

    if hasattr(tab, "spectrum_mirrored"):
        tab.spectrum_mirrored.setChecked(
            tab._config_bool("spotify_visualizer", config, "spectrum_mirrored", True)
        )
    if hasattr(tab, "spectrum_shape_editor"):
        saved_nodes = config.get("spectrum_shape_nodes", _SPECTRUM_LOAD_DEFAULT_NODES)
        if isinstance(saved_nodes, list) and len(saved_nodes) >= 1:
            tab.spectrum_shape_editor.set_nodes(saved_nodes)
        mirrored = tab._config_bool("spotify_visualizer", config, "spectrum_mirrored", True)
        tab.spectrum_shape_editor.set_mirrored(mirrored)
        notch_positions_mirrored = config.get("spectrum_notch_positions_mirrored", None)
        if isinstance(notch_positions_mirrored, list) and len(notch_positions_mirrored) >= 2:
            tab.spectrum_shape_editor.set_notch_positions(notch_positions_mirrored, mirrored=True)
        notch_positions_linear = config.get("spectrum_notch_positions_linear", None)
        if isinstance(notch_positions_linear, list) and len(notch_positions_linear) >= 2:
            tab.spectrum_shape_editor.set_notch_positions(notch_positions_linear, mirrored=False)

    ghost_enabled = config.get(
        "spectrum_ghosting_enabled",
        tab._config_bool("spotify_visualizer", config, "ghosting_enabled", True),
    )
    tab.vis_ghost_enabled.setChecked(bool(ghost_enabled))
    ghost_alpha = float(
        config.get(
            "spectrum_ghost_alpha",
            tab._config_float("spotify_visualizer", config, "ghost_alpha", 0.4),
        )
    )
    ghost_alpha_pct = max(0, min(100, int(ghost_alpha * 100)))
    tab.vis_ghost_opacity_slider.setValue(ghost_alpha_pct)
    tab.vis_ghost_opacity_label.setText(f"{ghost_alpha_pct}%")

    ghost_decay = float(
        config.get(
            "spectrum_ghost_decay",
            tab._config_float("spotify_visualizer", config, "ghost_decay", 0.4),
        )
    )
    ghost_decay_slider = max(10, min(100, int(ghost_decay * 100.0)))
    tab.vis_ghost_decay_slider.setValue(ghost_decay_slider)
    tab.vis_ghost_decay_label.setText(f"{ghost_decay_slider / 100.0:.2f}x")
    update_ghost_visibility(tab)


def collect_spectrum_mode_settings(tab) -> dict[str, Any]:
    """Collect Spectrum-owned settings from the tab into a config mapping."""
    return {
        "spectrum_ghosting_enabled": tab.vis_ghost_enabled.isChecked(),
        "spectrum_ghost_alpha": tab.vis_ghost_opacity_slider.value() / 100.0,
        "spectrum_ghost_decay": max(0.1, tab.vis_ghost_decay_slider.value() / 100.0),
        "spectrum_growth": (tab.spectrum_growth.value() if hasattr(tab, "spectrum_growth") else 100) / 100.0,
        "spectrum_single_piece": (
            tab.spectrum_single_piece.isChecked() if hasattr(tab, "spectrum_single_piece") else False
        ),
        "spectrum_rainbow_per_bar": (
            tab.spectrum_rainbow_per_bar.isChecked() if hasattr(tab, "spectrum_rainbow_per_bar") else False
        ),
        "spectrum_border_radius": (
            float(tab.spectrum_border_radius.value()) if hasattr(tab, "spectrum_border_radius") else 0.0
        ),
        "spectrum_glow_enabled": (
            tab.spectrum_glow_enabled.isChecked() if hasattr(tab, "spectrum_glow_enabled") else False
        ),
        "spectrum_glow_intensity": (
            (tab.spectrum_glow_intensity.value() if hasattr(tab, "spectrum_glow_intensity") else 55) / 100.0
        ),
        "spectrum_glow_color": _qcolor_to_list(getattr(tab, "_spectrum_glow_color", None), _SPECTRUM_GLOW_DEFAULT),
        "spectrum_mirrored": tab.spectrum_mirrored.isChecked() if hasattr(tab, "spectrum_mirrored") else True,
        "spectrum_shape_nodes": (
            tab.spectrum_shape_editor.get_nodes() if hasattr(tab, "spectrum_shape_editor") else _SPECTRUM_SAVE_DEFAULT_NODES
        ),
        "spectrum_notch_positions_mirrored": (
            tab.spectrum_shape_editor._notches_mirrored
            if hasattr(tab, "spectrum_shape_editor")
            else _SPECTRUM_DEFAULT_NOTCHES_MIRRORED
        ),
        "spectrum_notch_positions_linear": (
            tab.spectrum_shape_editor._notches_linear
            if hasattr(tab, "spectrum_shape_editor")
            else _SPECTRUM_DEFAULT_NOTCHES_LINEAR
        ),
        "spectrum_bass_emphasis": (
            tab.spectrum_bass_emphasis.value() if hasattr(tab, "spectrum_bass_emphasis") else 50
        ) / 100.0,
        "spectrum_vocal_position": (
            tab.spectrum_vocal_position.value() if hasattr(tab, "spectrum_vocal_position") else 40
        ) / 100.0,
        "spectrum_mid_suppression": (
            tab.spectrum_mid_suppression.value() if hasattr(tab, "spectrum_mid_suppression") else 50
        ) / 100.0,
        "spectrum_wave_amplitude": (
            tab.spectrum_wave_amplitude.value() if hasattr(tab, "spectrum_wave_amplitude") else 50
        ) / 100.0,
        "spectrum_profile_floor": (
            tab.spectrum_profile_floor.value() if hasattr(tab, "spectrum_profile_floor") else 12
        ) / 100.0,
        "spectrum_drop_speed": (
            tab.spectrum_drop_speed.value() if hasattr(tab, "spectrum_drop_speed") else 100
        ) / 100.0,
    }
