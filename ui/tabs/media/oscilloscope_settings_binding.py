"""Oscilloscope visualizer settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from PySide6.QtGui import QColor

from core.logging.logger import get_logger
from ui.color_utils import qcolor_to_list as _qcolor_to_list

logger = get_logger(__name__)


def load_oscilloscope_mode_settings(
    tab,
    spotify_vis_config: Mapping[str, Any] | None,
    *,
    sync_color_button: Callable[[str, str], None],
    load_extra_color_bindings: Callable[[Any, Mapping[str, Any]], None],
    update_multi_line_visibility: Callable[[Any], None],
) -> None:
    """Load Oscilloscope-owned settings from config into the tab."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}

    if hasattr(tab, "osc_glow_enabled"):
        tab.osc_glow_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_glow_enabled", True)
        )
    if hasattr(tab, "osc_glow_intensity"):
        osc_glow_val = int(tab._config_float("spotify_visualizer", config, "osc_glow_intensity", 0.5) * 100)
        tab.osc_glow_intensity.setValue(max(0, min(100, osc_glow_val)))
        tab.osc_glow_intensity_label.setText(f"{osc_glow_val}%")
    if hasattr(tab, "osc_glow_reactivity"):
        osc_glow_reactivity = int(
            tab._config_float(
                "spotify_visualizer",
                config,
                "osc_glow_reactivity",
                tab._config_float("spotify_visualizer", config, "osc_glow_size", 1.0),
            ) * 100
        )
        tab.osc_glow_reactivity.setValue(max(0, min(200, osc_glow_reactivity)))
        tab.osc_glow_reactivity_label.setText(f"{osc_glow_reactivity}%")
    if hasattr(tab, "osc_reactive_glow"):
        tab.osc_reactive_glow.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_reactive_glow", True)
        )
    if hasattr(tab, "osc_line_amplitude"):
        osc_line_amplitude = int(
            tab._config_float("spotify_visualizer", config, "osc_line_amplitude", 3.0) * 10
        )
        tab.osc_line_amplitude.setValue(max(5, min(100, osc_line_amplitude)))
        tab.osc_line_amplitude_label.setText(f"{osc_line_amplitude / 10.0:.1f}x")
    if hasattr(tab, "osc_smoothing"):
        osc_smoothing = int(tab._config_float("spotify_visualizer", config, "osc_smoothing", 0.7) * 100)
        tab.osc_smoothing.setValue(max(0, min(100, osc_smoothing)))
        tab.osc_smoothing_label.setText(f"{osc_smoothing}%")
    if hasattr(tab, "osc_growth"):
        osc_growth = int(tab._config_float("spotify_visualizer", config, "osc_growth", 1.0) * 100)
        tab.osc_growth.setValue(max(100, min(500, osc_growth)))
        tab.osc_growth_label.setText(f"{osc_growth / 100.0:.1f}x")
    if hasattr(tab, "osc_speed"):
        osc_speed = int(tab._config_float("spotify_visualizer", config, "osc_speed", 1.0) * 100)
        tab.osc_speed.setValue(max(10, min(100, osc_speed)))
        tab.osc_speed_label.setText(f"{osc_speed}%")
    if hasattr(tab, "osc_line_dim"):
        tab.osc_line_dim.setChecked(bool(config.get("osc_line_dim", False)))
    if hasattr(tab, "osc_line_offset_bias"):
        osc_line_offset_bias = int(tab._config_float("spotify_visualizer", config, "osc_line_offset_bias", 0.0) * 100)
        tab.osc_line_offset_bias.setValue(max(0, min(100, osc_line_offset_bias)))
        tab.osc_line_offset_bias_label.setText(f"{osc_line_offset_bias}%")
    if hasattr(tab, "osc_vertical_shift"):
        osc_vertical_shift = int(config.get("osc_vertical_shift", 0))
        if isinstance(config.get("osc_vertical_shift"), bool):
            osc_vertical_shift = 100 if config.get("osc_vertical_shift") else 0
        tab.osc_vertical_shift.setValue(max(-50, min(200, osc_vertical_shift)))
        tab.osc_vertical_shift_label.setText(f"{osc_vertical_shift}")

    osc_line_color_data = config.get("osc_line_color", [255, 255, 255, 255])
    try:
        tab._osc_line_color = QColor(*osc_line_color_data)
    except Exception:
        logger.debug("[OSC_BINDING] Failed to set osc_line_color=%s", osc_line_color_data, exc_info=True)
        tab._osc_line_color = QColor(255, 255, 255, 255)
    osc_glow_color_data = config.get("osc_glow_color", [0, 200, 255, 230])
    try:
        tab._osc_glow_color = QColor(*osc_glow_color_data)
    except Exception:
        logger.debug("[OSC_BINDING] Failed to set osc_glow_color=%s", osc_glow_color_data, exc_info=True)
        tab._osc_glow_color = QColor(0, 200, 255, 230)
    sync_color_button("osc_line_color_btn", "_osc_line_color")
    sync_color_button("osc_glow_color_btn", "_osc_glow_color")

    osc_line_count = int(config.get("osc_line_count", 1))
    if hasattr(tab, "osc_multi_line"):
        tab.osc_multi_line.setChecked(osc_line_count > 1)
    if hasattr(tab, "osc_line_count"):
        clamped_line_count = max(2, min(3, osc_line_count))
        tab.osc_line_count.setValue(clamped_line_count)
        tab.osc_line_count_label.setText(str(clamped_line_count))

    load_extra_color_bindings(tab, config)
    sync_color_button("osc_line2_color_btn", "_osc_line2_color")
    sync_color_button("osc_line2_glow_btn", "_osc_line2_glow_color")
    sync_color_button("osc_line3_color_btn", "_osc_line3_color")
    sync_color_button("osc_line3_glow_btn", "_osc_line3_glow_color")
    update_multi_line_visibility(tab)

    if hasattr(tab, "osc_ghost_enabled"):
        tab.osc_ghost_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_ghosting_enabled", False)
        )
    if hasattr(tab, "osc_ghost_intensity"):
        osc_ghost_intensity = int(tab._config_float("spotify_visualizer", config, "osc_ghost_intensity", 0.4) * 100)
        tab.osc_ghost_intensity.setValue(max(5, min(100, osc_ghost_intensity)))
        tab.osc_ghost_intensity_label.setText(f"{osc_ghost_intensity}%")
    if hasattr(tab, "osc_ghost_line2_enabled"):
        tab.osc_ghost_line2_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_ghost_line2_enabled", True)
        )
    if hasattr(tab, "osc_ghost_line3_enabled"):
        tab.osc_ghost_line3_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_ghost_line3_enabled", True)
        )


def collect_oscilloscope_mode_settings(
    tab,
    *,
    collect_extra_color_bindings: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    """Collect Oscilloscope-owned settings from the tab into a config mapping."""
    payload = {
        "osc_glow_enabled": tab.osc_glow_enabled.isChecked() if hasattr(tab, "osc_glow_enabled") else True,
        "osc_glow_intensity": (tab.osc_glow_intensity.value() if hasattr(tab, "osc_glow_intensity") else 50) / 100.0,
        "osc_glow_reactivity": (tab.osc_glow_reactivity.value() if hasattr(tab, "osc_glow_reactivity") else 100) / 100.0,
        "osc_reactive_glow": tab.osc_reactive_glow.isChecked() if hasattr(tab, "osc_reactive_glow") else True,
        "osc_line_amplitude": (tab.osc_line_amplitude.value() if hasattr(tab, "osc_line_amplitude") else 30) / 10.0,
        "osc_smoothing": (tab.osc_smoothing.value() if hasattr(tab, "osc_smoothing") else 70) / 100.0,
        "osc_line_color": _qcolor_to_list(getattr(tab, "_osc_line_color", None), [255, 255, 255, 255]),
        "osc_glow_color": _qcolor_to_list(getattr(tab, "_osc_glow_color", None), [0, 200, 255, 230]),
        "osc_line_count": (
            tab.osc_line_count.value()
            if hasattr(tab, "osc_line_count") and hasattr(tab, "osc_multi_line") and tab.osc_multi_line.isChecked()
            else 1
        ),
        "osc_growth": (tab.osc_growth.value() if hasattr(tab, "osc_growth") else 100) / 100.0,
        "osc_speed": (tab.osc_speed.value() if hasattr(tab, "osc_speed") else 100) / 100.0,
        "osc_line_dim": tab.osc_line_dim.isChecked() if hasattr(tab, "osc_line_dim") else False,
        "osc_line_offset_bias": (tab.osc_line_offset_bias.value() if hasattr(tab, "osc_line_offset_bias") else 0) / 100.0,
        "osc_vertical_shift": tab.osc_vertical_shift.value() if hasattr(tab, "osc_vertical_shift") else 0,
        "osc_ghosting_enabled": tab.osc_ghost_enabled.isChecked() if hasattr(tab, "osc_ghost_enabled") else False,
        "osc_ghost_intensity": (tab.osc_ghost_intensity.value() if hasattr(tab, "osc_ghost_intensity") else 40) / 100.0,
        "osc_ghost_line2_enabled": tab.osc_ghost_line2_enabled.isChecked() if hasattr(tab, "osc_ghost_line2_enabled") else True,
        "osc_ghost_line3_enabled": tab.osc_ghost_line3_enabled.isChecked() if hasattr(tab, "osc_ghost_line3_enabled") else True,
    }
    payload.update(collect_extra_color_bindings(tab))
    return payload
