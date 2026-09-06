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

_BUBBLE_COLOR_KEYS: tuple[tuple[str, str], ...] = (
    ("_bubble_outline_color", "bubble_outline_color"),
    ("_bubble_specular_color", "bubble_specular_color"),
    ("_bubble_gradient_light", "bubble_gradient_light"),
    ("_bubble_gradient_dark", "bubble_gradient_dark"),
    ("_bubble_pop_color", "bubble_pop_color"),
)

_STREAM_DIRECTION_INDEX = {
    "none": 0,
    "up": 1,
    "down": 2,
    "left": 3,
    "right": 4,
    "top_left": 5,
    "top_right": 6,
    "bottom_left": 7,
    "bottom_right": 8,
    "random": 9,
}


def _set_combo_data_or_fallback(combo, value: str, fallback: str) -> None:
    """Select *value*, repairing only to an explicitly supplied authority value."""
    idx = combo.findData(value)
    if idx < 0:
        idx = combo.findData(fallback)
    if idx < 0:
        raise ValueError(
            f"Neither requested nor repair Bubble combo value is represented: "
            f"value={value!r} repair={fallback!r}"
        )
    combo.setCurrentIndex(idx)


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
            tab._config_bool("spotify_visualizer", config, "bubble_ghosting_enabled")
        )
    if hasattr(tab, "bubble_ghost_opacity"):
        bubble_ghost_alpha = int(tab._config_float("spotify_visualizer", config, "bubble_ghost_alpha") * 100)
        tab.bubble_ghost_opacity.setValue(max(0, min(100, bubble_ghost_alpha)))
        tab.bubble_ghost_opacity_label.setText(f"{bubble_ghost_alpha}%")
    if hasattr(tab, "bubble_ghost_decay_slider"):
        bubble_ghost_decay = int(round(tab._config_float("spotify_visualizer", config, "bubble_ghost_decay") * 100))
        tab.bubble_ghost_decay_slider.setValue(max(10, min(100, bubble_ghost_decay)))
        tab.bubble_ghost_decay_label.setText(f"{bubble_ghost_decay / 100.0:.2f}x")

    if hasattr(tab, "bubble_big_bass_pulse"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_bass_pulse") * 100)
        tab.bubble_big_bass_pulse.setValue(max(0, min(200, v)))
        tab.bubble_big_bass_pulse_label.setText(f"{v}%")
    if hasattr(tab, "bubble_small_freq_pulse"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_small_freq_pulse") * 100)
        tab.bubble_small_freq_pulse.setValue(max(0, min(200, v)))
        tab.bubble_small_freq_pulse_label.setText(f"{v}%")
    if hasattr(tab, "bubble_big_visual_smoothing"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_visual_smoothing") * 100)
        tab.bubble_big_visual_smoothing.setValue(max(0, min(100, v)))
        tab.bubble_big_visual_smoothing_label.setText(f"{v}%")

    if hasattr(tab, "bubble_stream_direction"):
        canonical_stream_direction = tab._default_str(
            "spotify_visualizer", "bubble_stream_direction"
        ).strip().lower()
        if canonical_stream_direction not in _STREAM_DIRECTION_INDEX:
            raise ValueError(
                f"Canonical Bubble stream direction is unsupported: {canonical_stream_direction!r}"
            )
        stream_direction = tab._config_str(
            "spotify_visualizer", config, "bubble_stream_direction"
        ).strip().lower()
        if stream_direction == "diagonal":
            # Retained migration spelling; current schema uses top_right.
            stream_direction = "top_right"
        stream_index = _STREAM_DIRECTION_INDEX.get(stream_direction)
        if stream_index is None:
            stream_index = _STREAM_DIRECTION_INDEX[canonical_stream_direction]
        tab.bubble_stream_direction.setCurrentIndex(stream_index)
    if hasattr(tab, "bubble_stream_constant_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_stream_constant_speed") * 100)
        tab.bubble_stream_constant_speed.setValue(max(0, min(200, v)))
        tab.bubble_stream_constant_speed_label.setText(f"{v}%")
    if hasattr(tab, "bubble_stream_speed_cap"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_stream_speed_cap") * 100)
        tab.bubble_stream_speed_cap.setValue(max(50, min(400, v)))
        tab.bubble_stream_speed_cap_label.setText(f"{v}%")
    if hasattr(tab, "bubble_stream_reactivity"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_stream_reactivity") * 100)
        clamped_v = max(0, min(200, v))
        tab.bubble_stream_reactivity.setValue(clamped_v)
        tab.bubble_stream_reactivity_label.setText(f"{clamped_v}%")

    if hasattr(tab, "bubble_rotation_amount"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_rotation_amount") * 100)
        tab.bubble_rotation_amount.setValue(max(0, min(100, v)))
        tab.bubble_rotation_amount_label.setText(f"{v}%")
    if hasattr(tab, "bubble_drift_amount"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_drift_amount") * 100)
        tab.bubble_drift_amount.setValue(max(0, min(100, v)))
        tab.bubble_drift_amount_label.setText(f"{v}%")
    if hasattr(tab, "bubble_group_drift"):
        tab.bubble_group_drift.setChecked(
            tab._config_bool("spotify_visualizer", config, "bubble_group_drift")
        )
    if hasattr(tab, "bubble_drift_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_drift_speed") * 100)
        tab.bubble_drift_speed.setValue(max(0, min(100, v)))
        tab.bubble_drift_speed_label.setText(f"{v}%")
    if hasattr(tab, "bubble_drift_frequency"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_drift_frequency") * 100)
        tab.bubble_drift_frequency.setValue(max(0, min(100, v)))
        tab.bubble_drift_frequency_label.setText(f"{v}%")

    canonical_drift_direction = tab._default_str(
        "spotify_visualizer", "bubble_drift_direction"
    ).strip().lower()
    if not canonical_drift_direction:
        raise ValueError("Canonical Bubble drift direction is empty")
    drift_direction = tab._config_str(
        "spotify_visualizer", config, "bubble_drift_direction"
    ).strip().lower()
    if hasattr(tab, "bubble_drift_direction"):
        if drift_direction in ("swirl_cw", "swirl_ccw"):
            # ``none`` is a UI projection meaning the dedicated swirl control owns
            # the persisted drift value. It is not a product-default fallback.
            _set_combo_data_or_fallback(tab.bubble_drift_direction, "none", "none")
        else:
            _set_combo_data_or_fallback(
                tab.bubble_drift_direction, drift_direction, canonical_drift_direction
            )
    if hasattr(tab, "bubble_swirl_enabled"):
        tab.bubble_swirl_enabled.setChecked(drift_direction in ("swirl_cw", "swirl_ccw"))
    if hasattr(tab, "bubble_swirl_direction"):
        _set_combo_data_or_fallback(tab.bubble_swirl_direction, drift_direction, "swirl_cw")

    if hasattr(tab, "bubble_big_count"):
        v = tab._config_int("spotify_visualizer", config, "bubble_big_count")
        tab.bubble_big_count.setValue(max(0, min(30, v)))
        if hasattr(tab, "bubble_big_count_label"):
            tab.bubble_big_count_label.setText(str(v))
    if hasattr(tab, "bubble_small_count"):
        v = tab._config_int("spotify_visualizer", config, "bubble_small_count")
        tab.bubble_small_count.setValue(max(5, min(80, v)))
        if hasattr(tab, "bubble_small_count_label"):
            tab.bubble_small_count_label.setText(str(v))
    if hasattr(tab, "bubble_surface_reach"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_surface_reach") * 100)
        tab.bubble_surface_reach.setValue(max(0, min(100, v)))
        tab.bubble_surface_reach_label.setText(f"{v}%")
    if hasattr(tab, "bubble_bounce_big_pct"):
        v = tab._config_int("spotify_visualizer", config, "bubble_bounce_big_pct")
        clamped_v = max(0, min(100, v))
        tab.bubble_bounce_big_pct.setValue(clamped_v)
        tab.bubble_bounce_big_pct_label.setText(f"{clamped_v}%")
    if hasattr(tab, "bubble_bounce_small_pct"):
        v = tab._config_int("spotify_visualizer", config, "bubble_bounce_small_pct")
        clamped_v = max(0, min(100, v))
        tab.bubble_bounce_small_pct.setValue(clamped_v)
        tab.bubble_bounce_small_pct_label.setText(f"{clamped_v}%")
    if hasattr(tab, "bubble_bounce_big_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_bounce_big_speed") * 100)
        clamped_v = max(0, min(200, v))
        tab.bubble_bounce_big_speed.setValue(clamped_v)
        tab.bubble_bounce_big_speed_label.setText(f"{clamped_v / 100.0:.2f}x")
    if hasattr(tab, "bubble_bounce_small_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_bounce_small_speed") * 100)
        clamped_v = max(0, min(200, v))
        tab.bubble_bounce_small_speed.setValue(clamped_v)
        tab.bubble_bounce_small_speed_label.setText(f"{clamped_v / 100.0:.2f}x")
    if hasattr(tab, "bubble_bounce_same_only"):
        tab.bubble_bounce_same_only.setChecked(
            tab._config_bool("spotify_visualizer", config, "bubble_bounce_same_only")
        )
    if hasattr(tab, "bubble_collision_pop_mode"):
        pop_mode = str(tab._config_str("spotify_visualizer", config, "bubble_collision_pop_mode")).lower()
        if pop_mode not in {"off", "one", "all"}:
            pop_mode = "off"
        _set_combo_data_or_fallback(tab.bubble_collision_pop_mode, pop_mode, "off")

    if hasattr(tab, "bubble_specular_direction"):
        specular_direction = normalize_bubble_specular_direction(
            tab._config_str("spotify_visualizer", config, "bubble_specular_direction")
        )
        _set_combo_data_or_fallback(tab.bubble_specular_direction, specular_direction, "top_left")
    if hasattr(tab, "bubble_gradient_direction"):
        gradient_direction = resolve_bubble_gradient_direction(
            tab._config_str("spotify_visualizer", config, "bubble_gradient_direction"),
            semantics_version=bubble_gradient_semantics_version,
            default="top",
        )
        _set_combo_data_or_fallback(tab.bubble_gradient_direction, gradient_direction, "top")

    if hasattr(tab, "bubble_big_size_max"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_size_max") * 1000)
        tab.bubble_big_size_max.setValue(max(10, min(60, v)))
        tab.bubble_big_size_max_label.setText(str(v))
    if hasattr(tab, "bubble_small_size_max"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_small_size_max") * 1000)
        tab.bubble_small_size_max.setValue(max(4, min(30, v)))
        tab.bubble_small_size_max_label.setText(str(v))
    if hasattr(tab, "bubble_big_specular_max_size"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_specular_max_size") * 100)
        tab.bubble_big_specular_max_size.setValue(max(50, min(500, v)))
        tab.bubble_big_specular_max_size_label.setText(f"{v / 100.0:.1f}x")
    if hasattr(tab, "bubble_big_size_clamp"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_size_clamp") * 100)
        tab.bubble_big_size_clamp.setValue(max(150, min(800, v)))
        tab.bubble_big_size_clamp_label.setText(f"{v / 100.0:.1f}x")
    if hasattr(tab, "bubble_big_contraction_bias"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_big_contraction_bias") * 100)
        tab.bubble_big_contraction_bias.setValue(max(0, min(100, v)))
        tab.bubble_big_contraction_bias_label.setText(f"{v}%")
    if hasattr(tab, "bubble_trail_strength"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_trail_strength") * 100)
        tab.bubble_trail_strength.setValue(max(0, min(150, v)))
        tab.bubble_trail_strength_label.setText(f"{v}%")
    if hasattr(tab, "bubble_tail_opacity"):
        v = int(tab._config_float("spotify_visualizer", config, "bubble_tail_opacity") * 100)
        tab.bubble_tail_opacity.setValue(max(0, min(85, v)))
        tab.bubble_tail_opacity_label.setText(f"{v}%")

    for attr, key in _BUBBLE_COLOR_KEYS:
        default = tab._widget_default("spotify_visualizer", key)
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
    """Collect Bubble-owned settings with canonical-only missing-control defaults."""
    d_bool = lambda key: tab._default_bool("spotify_visualizer", key)
    d_int = lambda key: tab._default_int("spotify_visualizer", key)
    d_float = lambda key: tab._default_float("spotify_visualizer", key)
    d_str = lambda key: tab._default_str("spotify_visualizer", key)
    d_value = lambda key: tab._widget_default("spotify_visualizer", key)
    pct = lambda key: int(round(d_float(key) * 100.0))
    milli = lambda key: int(round(d_float(key) * 1000.0))

    drift_default = d_str("bubble_drift_direction").strip().lower()
    if not drift_default:
        raise ValueError("Canonical Bubble drift direction is empty")
    if hasattr(tab, "bubble_swirl_enabled") and tab.bubble_swirl_enabled.isChecked():
        drift_direction = tab.bubble_swirl_direction.currentData()
        if drift_direction not in {"swirl_cw", "swirl_ccw"}:
            raise ValueError(
                f"Bubble swirl is enabled without a valid swirl direction: {drift_direction!r}"
            )
    elif hasattr(tab, "bubble_drift_direction"):
        drift_direction = tab.bubble_drift_direction.currentData()
        if not drift_direction:
            drift_direction = drift_default
    else:
        drift_direction = drift_default

    return {
        "bubble_ghosting_enabled": tab.bubble_ghost_enabled.isChecked() if hasattr(tab, "bubble_ghost_enabled") else d_bool("bubble_ghosting_enabled"),
        "bubble_ghost_alpha": (tab.bubble_ghost_opacity.value() if hasattr(tab, "bubble_ghost_opacity") else pct("bubble_ghost_alpha")) / 100.0,
        "bubble_ghost_decay": max(0.1, (tab.bubble_ghost_decay_slider.value() if hasattr(tab, "bubble_ghost_decay_slider") else pct("bubble_ghost_decay")) / 100.0),
        "bubble_big_bass_pulse": (tab.bubble_big_bass_pulse.value() if hasattr(tab, "bubble_big_bass_pulse") else pct("bubble_big_bass_pulse")) / 100.0,
        "bubble_small_freq_pulse": (tab.bubble_small_freq_pulse.value() if hasattr(tab, "bubble_small_freq_pulse") else pct("bubble_small_freq_pulse")) / 100.0,
        "bubble_big_visual_smoothing": (tab.bubble_big_visual_smoothing.value() if hasattr(tab, "bubble_big_visual_smoothing") else pct("bubble_big_visual_smoothing")) / 100.0,
        "bubble_stream_direction": ((tab.bubble_stream_direction.currentData() or d_str("bubble_stream_direction")) if hasattr(tab, "bubble_stream_direction") else d_str("bubble_stream_direction")),
        "bubble_stream_constant_speed": (tab.bubble_stream_constant_speed.value() if hasattr(tab, "bubble_stream_constant_speed") else pct("bubble_stream_constant_speed")) / 100.0,
        "bubble_stream_speed_cap": (tab.bubble_stream_speed_cap.value() if hasattr(tab, "bubble_stream_speed_cap") else pct("bubble_stream_speed_cap")) / 100.0,
        "bubble_stream_reactivity": (tab.bubble_stream_reactivity.value() if hasattr(tab, "bubble_stream_reactivity") else pct("bubble_stream_reactivity")) / 100.0,
        "bubble_rotation_amount": (tab.bubble_rotation_amount.value() if hasattr(tab, "bubble_rotation_amount") else pct("bubble_rotation_amount")) / 100.0,
        "bubble_drift_amount": (tab.bubble_drift_amount.value() if hasattr(tab, "bubble_drift_amount") else pct("bubble_drift_amount")) / 100.0,
        "bubble_group_drift": tab.bubble_group_drift.isChecked() if hasattr(tab, "bubble_group_drift") else d_bool("bubble_group_drift"),
        "bubble_drift_speed": (tab.bubble_drift_speed.value() if hasattr(tab, "bubble_drift_speed") else pct("bubble_drift_speed")) / 100.0,
        "bubble_drift_frequency": (tab.bubble_drift_frequency.value() if hasattr(tab, "bubble_drift_frequency") else pct("bubble_drift_frequency")) / 100.0,
        "bubble_drift_direction": drift_direction,
        "bubble_big_count": tab.bubble_big_count.value() if hasattr(tab, "bubble_big_count") else d_int("bubble_big_count"),
        "bubble_small_count": tab.bubble_small_count.value() if hasattr(tab, "bubble_small_count") else d_int("bubble_small_count"),
        "bubble_surface_reach": (tab.bubble_surface_reach.value() if hasattr(tab, "bubble_surface_reach") else pct("bubble_surface_reach")) / 100.0,
        "bubble_bounce_big_pct": tab.bubble_bounce_big_pct.value() if hasattr(tab, "bubble_bounce_big_pct") else d_int("bubble_bounce_big_pct"),
        "bubble_bounce_small_pct": tab.bubble_bounce_small_pct.value() if hasattr(tab, "bubble_bounce_small_pct") else d_int("bubble_bounce_small_pct"),
        "bubble_bounce_big_speed": (tab.bubble_bounce_big_speed.value() if hasattr(tab, "bubble_bounce_big_speed") else pct("bubble_bounce_big_speed")) / 100.0,
        "bubble_bounce_small_speed": (tab.bubble_bounce_small_speed.value() if hasattr(tab, "bubble_bounce_small_speed") else pct("bubble_bounce_small_speed")) / 100.0,
        "bubble_bounce_same_only": tab.bubble_bounce_same_only.isChecked() if hasattr(tab, "bubble_bounce_same_only") else d_bool("bubble_bounce_same_only"),
        "bubble_collision_pop_mode": ((tab.bubble_collision_pop_mode.currentData() or d_str("bubble_collision_pop_mode")) if hasattr(tab, "bubble_collision_pop_mode") else d_str("bubble_collision_pop_mode")),
        "bubble_outline_color": _qcolor_to_list(getattr(tab, "_bubble_outline_color", None), d_value("bubble_outline_color")),
        "bubble_specular_color": _qcolor_to_list(getattr(tab, "_bubble_specular_color", None), d_value("bubble_specular_color")),
        "bubble_gradient_light": _qcolor_to_list(getattr(tab, "_bubble_gradient_light", None), d_value("bubble_gradient_light")),
        "bubble_gradient_dark": _qcolor_to_list(getattr(tab, "_bubble_gradient_dark", None), d_value("bubble_gradient_dark")),
        "bubble_pop_color": _qcolor_to_list(getattr(tab, "_bubble_pop_color", None), d_value("bubble_pop_color")),
        "bubble_specular_direction": tab.bubble_specular_direction.currentData() if hasattr(tab, "bubble_specular_direction") else d_str("bubble_specular_direction"),
        "bubble_gradient_direction": tab.bubble_gradient_direction.currentData() if hasattr(tab, "bubble_gradient_direction") else d_str("bubble_gradient_direction"),
        "bubble_gradient_semantics_version": CURRENT_BUBBLE_GRADIENT_SEMANTICS_VERSION,
        "bubble_big_size_max": (tab.bubble_big_size_max.value() if hasattr(tab, "bubble_big_size_max") else milli("bubble_big_size_max")) / 1000.0,
        "bubble_small_size_max": (tab.bubble_small_size_max.value() if hasattr(tab, "bubble_small_size_max") else milli("bubble_small_size_max")) / 1000.0,
        "bubble_big_specular_max_size": (tab.bubble_big_specular_max_size.value() if hasattr(tab, "bubble_big_specular_max_size") else pct("bubble_big_specular_max_size")) / 100.0,
        "bubble_big_size_clamp": (tab.bubble_big_size_clamp.value() if hasattr(tab, "bubble_big_size_clamp") else pct("bubble_big_size_clamp")) / 100.0,
        "bubble_big_contraction_bias": (tab.bubble_big_contraction_bias.value() if hasattr(tab, "bubble_big_contraction_bias") else pct("bubble_big_contraction_bias")) / 100.0,
        "bubble_trail_strength": (tab.bubble_trail_strength.value() if hasattr(tab, "bubble_trail_strength") else pct("bubble_trail_strength")) / 100.0,
        "bubble_tail_opacity": (tab.bubble_tail_opacity.value() if hasattr(tab, "bubble_tail_opacity") else pct("bubble_tail_opacity")) / 100.0,
    }
