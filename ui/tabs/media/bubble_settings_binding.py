"""Bubble visualizer settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from PySide6.QtGui import QColor

from core.settings.bubble_gradient_semantics import (
    CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION,
    get_bubble_gradient_semantics_version,
    normalize_bubble_specular_direction,
    resolve_bubble_gradient_direction,
)
from core.logging.logger import get_logger
from ui.color_utils import qcolor_to_list as _qcolor_to_list

logger = get_logger(__name__)

_BUBBLE_COLOR_DEFAULTS: tuple[tuple[str, str, list[int]], ...] = (
    ("_bubble_outline_color", "bubble_outline_color", [255, 255, 255, 230]),
    ("_bubble_specular_color", "bubble_specular_color", [255, 255, 255, 255]),
    ("_bubble_gradient_light", "bubble_gradient_light", [210, 170, 120, 255]),
    ("_bubble_gradient_dark", "bubble_gradient_dark", [80, 60, 50, 255]),
    ("_bubble_pop_color", "bubble_pop_color", [255, 255, 255, 180]),
)

_STREAM_DIRECTION_INDEX = {
    "none": 0,
    "up": 1,
    "down": 2,
    "left": 3,
    "right": 4,
    "diagonal": 5,
    "random": 6,
}


def _set_combo_data_or_fallback(combo, value: str, fallback: str) -> None:
    idx = combo.findData(value)
    if idx < 0:
        idx = combo.findData(fallback)
    combo.setCurrentIndex(max(0, idx))


def load_bubble_mode_settings(
    tab,
    spotify_vis_config: Mapping[str, Any] | None,
    *,
    sync_color_button: Callable[[str, str], None],
) -> None:
    """Load Bubble-owned settings from the visualizer config into the tab."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}
    bubble_gradient_semantics_version = get_bubble_gradient_semantics_version(config, prefix="widgets.spotify_visualizer")

    if hasattr(tab, "bubble_ghost_enabled"):
        tab.bubble_ghost_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "bubble_ghosting_enabled", False)
        )
    if hasattr(tab, "bubble_ghost_opacity"):
        bubble_ghost_alpha = int(tab._config_float("spotify_visualizer", config, "bubble_ghost_alpha", 0.0) * 100)
        tab.bubble_ghost_opacity.setValue(max(0, min(100, bubble_ghost_alpha)))
        tab.bubble_ghost_opacity_label.setText(f"{bubble_ghost_alpha}%")
    if hasattr(tab, "bubble_ghost_decay_slider"):
        bubble_ghost_decay = int(round(tab._config_float("spotify_visualizer", config, "bubble_ghost_decay", 0.4) * 100))
        tab.bubble_ghost_decay_slider.setValue(max(10, min(100, bubble_ghost_decay)))
        tab.bubble_ghost_decay_label.setText(f"{bubble_ghost_decay / 100.0:.2f}x")

    if hasattr(tab, "bubble_big_bass_pulse"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_bass_pulse", 0.5) * 100)
        tab.bubble_big_bass_pulse.setValue(max(0, min(200, v)))
        tab.bubble_big_bass_pulse_label.setText(f"{v}%")
    if hasattr(tab, "bubble_small_freq_pulse"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_small_freq_pulse", 0.5) * 100)
        tab.bubble_small_freq_pulse.setValue(max(0, min(200, v)))
        tab.bubble_small_freq_pulse_label.setText(f"{v}%")

    if hasattr(tab, "bubble_stream_direction"):
        stream_direction = tab._config_str("spotify_visualizer", config, "bubble_stream_direction", "up").lower()
        tab.bubble_stream_direction.setCurrentIndex(_STREAM_DIRECTION_INDEX.get(stream_direction, 1))
    if hasattr(tab, "bubble_stream_constant_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_stream_constant_speed", 0.5) * 100)
        tab.bubble_stream_constant_speed.setValue(max(0, min(200, v)))
        tab.bubble_stream_constant_speed_label.setText(f"{v}%")
    if hasattr(tab, "bubble_stream_speed_cap"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_stream_speed_cap", 2.0) * 100)
        tab.bubble_stream_speed_cap.setValue(max(50, min(400, v)))
        tab.bubble_stream_speed_cap_label.setText(f"{v}%")
    if hasattr(tab, "bubble_stream_reactivity"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_stream_reactivity", 0.5) * 100)
        clamped_v = max(0, min(200, v))
        tab.bubble_stream_reactivity.setValue(clamped_v)
        tab.bubble_stream_reactivity_label.setText(f"{clamped_v}%")

    if hasattr(tab, "bubble_rotation_amount"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_rotation_amount", 0.5) * 100)
        tab.bubble_rotation_amount.setValue(max(0, min(100, v)))
        tab.bubble_rotation_amount_label.setText(f"{v}%")
    if hasattr(tab, "bubble_drift_amount"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_drift_amount", 0.5) * 100)
        tab.bubble_drift_amount.setValue(max(0, min(100, v)))
        tab.bubble_drift_amount_label.setText(f"{v}%")
    if hasattr(tab, "bubble_drift_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_drift_speed", 0.5) * 100)
        tab.bubble_drift_speed.setValue(max(0, min(100, v)))
        tab.bubble_drift_speed_label.setText(f"{v}%")
    if hasattr(tab, "bubble_drift_frequency"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_drift_frequency", 0.5) * 100)
        tab.bubble_drift_frequency.setValue(max(0, min(100, v)))
        tab.bubble_drift_frequency_label.setText(f"{v}%")

    drift_direction = tab._config_str("spotify_visualizer", config, "bubble_drift_direction", "random").lower()
    if hasattr(tab, "bubble_drift_direction"):
        if drift_direction in ("swirl_cw", "swirl_ccw"):
            _set_combo_data_or_fallback(tab.bubble_drift_direction, "none", "random")
        else:
            _set_combo_data_or_fallback(tab.bubble_drift_direction, drift_direction, "random")
    if hasattr(tab, "bubble_swirl_enabled"):
        tab.bubble_swirl_enabled.setChecked(drift_direction in ("swirl_cw", "swirl_ccw"))
    if hasattr(tab, "bubble_swirl_direction"):
        _set_combo_data_or_fallback(tab.bubble_swirl_direction, drift_direction, "swirl_cw")

    if hasattr(tab, "bubble_big_count"):
        v = tab._config_int("spotify_visualizer", config, "bubble_big_count", 8)
        tab.bubble_big_count.setValue(max(1, min(30, v)))
        if hasattr(tab, "bubble_big_count_label"):
            tab.bubble_big_count_label.setText(str(v))
    if hasattr(tab, "bubble_small_count"):
        v = tab._config_int("spotify_visualizer", config, "bubble_small_count", 25)
        tab.bubble_small_count.setValue(max(5, min(80, v)))
        if hasattr(tab, "bubble_small_count_label"):
            tab.bubble_small_count_label.setText(str(v))
    if hasattr(tab, "bubble_surface_reach"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_surface_reach", 0.6) * 100)
        tab.bubble_surface_reach.setValue(max(0, min(100, v)))
        tab.bubble_surface_reach_label.setText(f"{v}%")
    if hasattr(tab, "bubble_bounce_big_pct"):
        v = tab._config_int("spotify_visualizer", config, "bubble_bounce_big_pct", 70)
        clamped_v = max(0, min(100, v))
        tab.bubble_bounce_big_pct.setValue(clamped_v)
        tab.bubble_bounce_big_pct_label.setText(f"{clamped_v}%")
    if hasattr(tab, "bubble_bounce_small_pct"):
        v = tab._config_int("spotify_visualizer", config, "bubble_bounce_small_pct", 30)
        clamped_v = max(0, min(100, v))
        tab.bubble_bounce_small_pct.setValue(clamped_v)
        tab.bubble_bounce_small_pct_label.setText(f"{clamped_v}%")
    if hasattr(tab, "bubble_bounce_big_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_bounce_big_speed", 0.8) * 100)
        clamped_v = max(0, min(200, v))
        tab.bubble_bounce_big_speed.setValue(clamped_v)
        tab.bubble_bounce_big_speed_label.setText(f"{clamped_v / 100.0:.2f}x")
    if hasattr(tab, "bubble_bounce_small_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_bounce_small_speed", 0.5) * 100)
        clamped_v = max(0, min(200, v))
        tab.bubble_bounce_small_speed.setValue(clamped_v)
        tab.bubble_bounce_small_speed_label.setText(f"{clamped_v / 100.0:.2f}x")

    if hasattr(tab, "bubble_specular_direction"):
        specular_direction = normalize_bubble_specular_direction(
            tab._config_str("spotify_visualizer", config, "bubble_specular_direction", "top_left")
        )
        _set_combo_data_or_fallback(tab.bubble_specular_direction, specular_direction, "top_left")
    if hasattr(tab, "bubble_gradient_direction"):
        gradient_direction = resolve_bubble_gradient_direction(
            tab._config_str("spotify_visualizer", config, "bubble_gradient_direction", "top"),
            semantics_version=bubble_gradient_semantics_version,
            default="top",
        )
        _set_combo_data_or_fallback(tab.bubble_gradient_direction, gradient_direction, "top")

    if hasattr(tab, "bubble_big_size_max"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_size_max", 0.038) * 1000)
        tab.bubble_big_size_max.setValue(max(10, min(60, v)))
        tab.bubble_big_size_max_label.setText(str(v))
    if hasattr(tab, "bubble_small_size_max"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_small_size_max", 0.018) * 1000)
        tab.bubble_small_size_max.setValue(max(4, min(30, v)))
        tab.bubble_small_size_max_label.setText(str(v))
    if hasattr(tab, "bubble_big_specular_max_size"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_specular_max_size", 2.5) * 100)
        tab.bubble_big_specular_max_size.setValue(max(50, min(500, v)))
        tab.bubble_big_specular_max_size_label.setText(f"{v / 100.0:.1f}x")
    if hasattr(tab, "bubble_big_size_clamp"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_size_clamp", 4.0) * 100)
        tab.bubble_big_size_clamp.setValue(max(150, min(800, v)))
        tab.bubble_big_size_clamp_label.setText(f"{v / 100.0:.1f}x")
    if hasattr(tab, "bubble_big_contraction_bias"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_contraction_bias", 1.0) * 100)
        tab.bubble_big_contraction_bias.setValue(max(0, min(100, v)))
        tab.bubble_big_contraction_bias_label.setText(f"{v}%")
    if hasattr(tab, "bubble_growth"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_growth", 3.0) * 100)
        tab.bubble_growth.setValue(max(100, min(500, v)))
        tab.bubble_growth_label.setText(f"{v / 100.0:.1f}x")
    if hasattr(tab, "bubble_trail_strength"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_trail_strength", 0.0) * 100)
        tab.bubble_trail_strength.setValue(max(0, min(150, v)))
        tab.bubble_trail_strength_label.setText(f"{v}%")
    if hasattr(tab, "bubble_tail_opacity"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_tail_opacity", 0.0) * 100)
        tab.bubble_tail_opacity.setValue(max(0, min(85, v)))
        tab.bubble_tail_opacity_label.setText(f"{v}%")

    for attr, key, default in _BUBBLE_COLOR_DEFAULTS:
        color_data = config.get(key, default)
        try:
            setattr(tab, attr, QColor(*color_data))
        except Exception:
            logger.debug("[BUBBLE_BINDING] Failed to set %s=%s", attr, color_data, exc_info=True)
            setattr(tab, attr, QColor(*default))

    sync_color_button("bubble_outline_color_btn", "_bubble_outline_color")
    sync_color_button("bubble_specular_color_btn", "_bubble_specular_color")
    sync_color_button("bubble_gradient_light_btn", "_bubble_gradient_light")
    sync_color_button("bubble_gradient_dark_btn", "_bubble_gradient_dark")
    sync_color_button("bubble_pop_color_btn", "_bubble_pop_color")


def collect_bubble_mode_settings(tab) -> dict[str, Any]:
    """Collect Bubble-owned settings from the tab into a config mapping."""
    return {
        "bubble_ghosting_enabled": tab.bubble_ghost_enabled.isChecked() if hasattr(tab, "bubble_ghost_enabled") else False,
        "bubble_ghost_alpha": (tab.bubble_ghost_opacity.value() if hasattr(tab, "bubble_ghost_opacity") else 0) / 100.0,
        "bubble_ghost_decay": max(
            0.1,
            (tab.bubble_ghost_decay_slider.value() if hasattr(tab, "bubble_ghost_decay_slider") else 40) / 100.0,
        ),
        "bubble_big_bass_pulse": (tab.bubble_big_bass_pulse.value() if hasattr(tab, "bubble_big_bass_pulse") else 50) / 100.0,
        "bubble_small_freq_pulse": (tab.bubble_small_freq_pulse.value() if hasattr(tab, "bubble_small_freq_pulse") else 50) / 100.0,
        "bubble_stream_direction": (
            tab.bubble_stream_direction.currentText().lower().replace(" ", "_")
            if hasattr(tab, "bubble_stream_direction")
            else "up"
        ),
        "bubble_stream_constant_speed": (
            tab.bubble_stream_constant_speed.value() if hasattr(tab, "bubble_stream_constant_speed") else 50
        ) / 100.0,
        "bubble_stream_speed_cap": (
            tab.bubble_stream_speed_cap.value() if hasattr(tab, "bubble_stream_speed_cap") else 200
        ) / 100.0,
        "bubble_stream_reactivity": (
            tab.bubble_stream_reactivity.value() if hasattr(tab, "bubble_stream_reactivity") else 50
        ) / 100.0,
        "bubble_rotation_amount": (tab.bubble_rotation_amount.value() if hasattr(tab, "bubble_rotation_amount") else 50) / 100.0,
        "bubble_drift_amount": (tab.bubble_drift_amount.value() if hasattr(tab, "bubble_drift_amount") else 50) / 100.0,
        "bubble_drift_speed": (tab.bubble_drift_speed.value() if hasattr(tab, "bubble_drift_speed") else 50) / 100.0,
        "bubble_drift_frequency": (
            tab.bubble_drift_frequency.value() if hasattr(tab, "bubble_drift_frequency") else 50
        ) / 100.0,
        "bubble_drift_direction": (
            (tab.bubble_swirl_direction.currentData() or "swirl_cw")
            if hasattr(tab, "bubble_swirl_enabled") and tab.bubble_swirl_enabled.isChecked()
            else (
                (tab.bubble_drift_direction.currentData() or "random")
                if hasattr(tab, "bubble_drift_direction")
                else "random"
            )
        ),
        "bubble_big_count": tab.bubble_big_count.value() if hasattr(tab, "bubble_big_count") else 8,
        "bubble_small_count": tab.bubble_small_count.value() if hasattr(tab, "bubble_small_count") else 25,
        "bubble_surface_reach": (tab.bubble_surface_reach.value() if hasattr(tab, "bubble_surface_reach") else 60) / 100.0,
        "bubble_bounce_big_pct": tab.bubble_bounce_big_pct.value() if hasattr(tab, "bubble_bounce_big_pct") else 70,
        "bubble_bounce_small_pct": tab.bubble_bounce_small_pct.value() if hasattr(tab, "bubble_bounce_small_pct") else 30,
        "bubble_bounce_big_speed": (
            tab.bubble_bounce_big_speed.value() if hasattr(tab, "bubble_bounce_big_speed") else 80
        ) / 100.0,
        "bubble_bounce_small_speed": (
            tab.bubble_bounce_small_speed.value() if hasattr(tab, "bubble_bounce_small_speed") else 50
        ) / 100.0,
        "bubble_outline_color": _qcolor_to_list(getattr(tab, "_bubble_outline_color", None), [255, 255, 255, 230]),
        "bubble_specular_color": _qcolor_to_list(getattr(tab, "_bubble_specular_color", None), [255, 255, 255, 255]),
        "bubble_gradient_light": _qcolor_to_list(getattr(tab, "_bubble_gradient_light", None), [210, 170, 120, 255]),
        "bubble_gradient_dark": _qcolor_to_list(getattr(tab, "_bubble_gradient_dark", None), [80, 60, 50, 255]),
        "bubble_pop_color": _qcolor_to_list(getattr(tab, "_bubble_pop_color", None), [255, 255, 255, 180]),
        "bubble_specular_direction": (
            tab.bubble_specular_direction.currentData()
            if hasattr(tab, "bubble_specular_direction")
            else "top_left"
        ),
        "bubble_gradient_direction": (
            tab.bubble_gradient_direction.currentData()
            if hasattr(tab, "bubble_gradient_direction")
            else "top"
        ),
        "bubble_gradient_semantics_version": CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION,
        "bubble_big_size_max": (tab.bubble_big_size_max.value() if hasattr(tab, "bubble_big_size_max") else 38) / 1000.0,
        "bubble_small_size_max": (tab.bubble_small_size_max.value() if hasattr(tab, "bubble_small_size_max") else 18) / 1000.0,
        "bubble_big_specular_max_size": (
            tab.bubble_big_specular_max_size.value() if hasattr(tab, "bubble_big_specular_max_size") else 250
        ) / 100.0,
        "bubble_big_size_clamp": (
            tab.bubble_big_size_clamp.value() if hasattr(tab, "bubble_big_size_clamp") else 400
        ) / 100.0,
        "bubble_big_contraction_bias": (
            tab.bubble_big_contraction_bias.value() if hasattr(tab, "bubble_big_contraction_bias") else 100
        ) / 100.0,
        "bubble_growth": (tab.bubble_growth.value() if hasattr(tab, "bubble_growth") else 300) / 100.0,
        "bubble_trail_strength": (tab.bubble_trail_strength.value() if hasattr(tab, "bubble_trail_strength") else 0) / 100.0,
        "bubble_tail_opacity": (tab.bubble_tail_opacity.value() if hasattr(tab, "bubble_tail_opacity") else 0) / 100.0,
    }
