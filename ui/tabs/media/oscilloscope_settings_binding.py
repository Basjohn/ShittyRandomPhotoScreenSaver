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
            tab._config_bool("spotify_visualizer", config, "osc_glow_enabled")
        )
    if hasattr(tab, "osc_glow_intensity"):
        osc_glow_val = int(tab._config_float("spotify_visualizer", config, "osc_glow_intensity") * 100)
        tab.osc_glow_intensity.setValue(max(0, min(100, osc_glow_val)))
        tab.osc_glow_intensity_label.setText(f"{osc_glow_val}%")
    if hasattr(tab, "osc_glow_reactivity"):
        osc_glow_reactivity = int(
            tab._config_float(
                "spotify_visualizer",
                config,
                "osc_glow_reactivity") * 100
        )
        tab.osc_glow_reactivity.setValue(max(0, min(200, osc_glow_reactivity)))
        tab.osc_glow_reactivity_label.setText(f"{osc_glow_reactivity}%")
    if hasattr(tab, "osc_reactive_glow"):
        tab.osc_reactive_glow.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_reactive_glow")
        )
    if hasattr(tab, "osc_line_amplitude"):
        osc_line_amplitude = int(
            tab._config_float("spotify_visualizer", config, "osc_line_amplitude") * 10
        )
        tab.osc_line_amplitude.setValue(max(5, min(100, osc_line_amplitude)))
        tab.osc_line_amplitude_label.setText(f"{osc_line_amplitude / 10.0:.1f}x")
    if hasattr(tab, "osc_smoothing"):
        osc_smoothing = int(tab._config_float("spotify_visualizer", config, "osc_smoothing") * 100)
        tab.osc_smoothing.setValue(max(0, min(100, osc_smoothing)))
        tab.osc_smoothing_label.setText(f"{osc_smoothing}%")
    if hasattr(tab, "osc_speed"):
        osc_speed = int(tab._config_float("spotify_visualizer", config, "osc_speed") * 100)
        tab.osc_speed.setValue(max(10, min(100, osc_speed)))
        tab.osc_speed_label.setText(f"{osc_speed}%")
    if hasattr(tab, "osc_line_dim"):
        tab.osc_line_dim.setChecked(bool(config.get("osc_line_dim", tab._widget_default("spotify_visualizer", "osc_line_dim"))))
    if hasattr(tab, "osc_line_offset_bias"):
        osc_line_offset_bias = int(tab._config_float("spotify_visualizer", config, "osc_line_offset_bias") * 100)
        tab.osc_line_offset_bias.setValue(max(0, min(100, osc_line_offset_bias)))
        tab.osc_line_offset_bias_label.setText(f"{osc_line_offset_bias}%")
    if hasattr(tab, "osc_vertical_shift"):
        osc_vertical_shift = int(config.get("osc_vertical_shift", tab._widget_default("spotify_visualizer", "osc_vertical_shift")))
        if isinstance(config.get("osc_vertical_shift"), bool):
            osc_vertical_shift = 100 if config.get("osc_vertical_shift") else 0
        tab.osc_vertical_shift.setValue(max(-50, min(200, osc_vertical_shift)))
        tab.osc_vertical_shift_label.setText(f"{osc_vertical_shift}")

    osc_line_color_default = tab._widget_default("spotify_visualizer", "osc_line_color")
    osc_line_color_data = config.get("osc_line_color", osc_line_color_default)
    try:
        tab._osc_line_color = QColor(*osc_line_color_data)
    except Exception:
        logger.debug("[OSC_BINDING] Failed to set osc_line_color=%s", osc_line_color_data, exc_info=True)
        tab._osc_line_color = QColor(*osc_line_color_default)
    osc_glow_color_default = tab._widget_default("spotify_visualizer", "osc_glow_color")
    osc_glow_color_data = config.get("osc_glow_color", osc_glow_color_default)
    try:
        tab._osc_glow_color = QColor(*osc_glow_color_data)
    except Exception:
        logger.debug("[OSC_BINDING] Failed to set osc_glow_color=%s", osc_glow_color_data, exc_info=True)
        tab._osc_glow_color = QColor(*osc_glow_color_default)
    sync_color_button("osc_line_color_btn", "_osc_line_color")
    sync_color_button("osc_glow_color_btn", "_osc_glow_color")

    osc_line_count = int(config.get("osc_line_count", tab._widget_default("spotify_visualizer", "osc_line_count")))
    if hasattr(tab, "osc_multi_line"):
        tab.osc_multi_line.setChecked(osc_line_count > 1)
    if hasattr(tab, "osc_line_count"):
        clamped_line_count = max(2, min(6, osc_line_count))
        tab.osc_line_count.setValue(clamped_line_count)
        tab.osc_line_count_label.setText(str(clamped_line_count))

    load_extra_color_bindings(tab, config)
    sync_color_button("osc_line2_color_btn", "_osc_line2_color")
    sync_color_button("osc_line2_glow_btn", "_osc_line2_glow_color")
    sync_color_button("osc_line3_color_btn", "_osc_line3_color")
    sync_color_button("osc_line3_glow_btn", "_osc_line3_glow_color")
    sync_color_button("osc_line4_color_btn", "_osc_line4_color")
    sync_color_button("osc_line4_glow_btn", "_osc_line4_glow_color")
    sync_color_button("osc_line5_color_btn", "_osc_line5_color")
    sync_color_button("osc_line5_glow_btn", "_osc_line5_glow_color")
    sync_color_button("osc_line6_color_btn", "_osc_line6_color")
    sync_color_button("osc_line6_glow_btn", "_osc_line6_glow_color")
    update_multi_line_visibility(tab)

    if hasattr(tab, "osc_ghost_enabled"):
        tab.osc_ghost_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_ghosting_enabled")
        )
    if hasattr(tab, "osc_ghost_intensity"):
        osc_ghost_intensity = int(tab._config_float("spotify_visualizer", config, "osc_ghost_intensity") * 100)
        tab.osc_ghost_intensity.setValue(max(5, min(100, osc_ghost_intensity)))
        tab.osc_ghost_intensity_label.setText(f"{osc_ghost_intensity}%")
    if hasattr(tab, "osc_ghost_decay"):
        osc_ghost_decay = int(round(tab._config_float("spotify_visualizer", config, "osc_ghost_decay") * 100))
        tab.osc_ghost_decay.setValue(max(10, min(100, osc_ghost_decay)))
        tab.osc_ghost_decay_label.setText(f"{osc_ghost_decay / 100.0:.2f}x")
    if hasattr(tab, "osc_ghost_line2_enabled"):
        tab.osc_ghost_line2_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_ghost_line2_enabled")
        )
    if hasattr(tab, "osc_ghost_line3_enabled"):
        tab.osc_ghost_line3_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_ghost_line3_enabled")
        )
    if hasattr(tab, "osc_ghost_line4_enabled"):
        tab.osc_ghost_line4_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_ghost_line4_enabled")
        )
    if hasattr(tab, "osc_ghost_line5_enabled"):
        tab.osc_ghost_line5_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_ghost_line5_enabled")
        )
    if hasattr(tab, "osc_ghost_line6_enabled"):
        tab.osc_ghost_line6_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "osc_ghost_line6_enabled")
        )


def collect_oscilloscope_mode_settings(
    tab,
    *,
    collect_extra_color_bindings: Callable[[Any], dict[str, Any]],
) -> dict[str, Any]:
    """Collect Oscilloscope settings without introducing shadow defaults."""
    d_bool = lambda key: tab._default_bool("spotify_visualizer", key)
    d_int = lambda key: tab._default_int("spotify_visualizer", key)
    d_float = lambda key: tab._default_float("spotify_visualizer", key)
    d_value = lambda key: tab._widget_default("spotify_visualizer", key)
    pct = lambda key: int(round(d_float(key) * 100.0))
    tenths = lambda key: int(round(d_float(key) * 10.0))

    if hasattr(tab, "osc_line_count") and hasattr(tab, "osc_multi_line"):
        line_count = tab.osc_line_count.value() if tab.osc_multi_line.isChecked() else 1
    else:
        line_count = d_int("osc_line_count")

    payload = {
        "osc_glow_enabled": tab.osc_glow_enabled.isChecked() if hasattr(tab, "osc_glow_enabled") else d_bool("osc_glow_enabled"),
        "osc_glow_intensity": (tab.osc_glow_intensity.value() if hasattr(tab, "osc_glow_intensity") else pct("osc_glow_intensity")) / 100.0,
        "osc_glow_reactivity": (tab.osc_glow_reactivity.value() if hasattr(tab, "osc_glow_reactivity") else pct("osc_glow_reactivity")) / 100.0,
        "osc_reactive_glow": tab.osc_reactive_glow.isChecked() if hasattr(tab, "osc_reactive_glow") else d_bool("osc_reactive_glow"),
        "osc_line_amplitude": (tab.osc_line_amplitude.value() if hasattr(tab, "osc_line_amplitude") else tenths("osc_line_amplitude")) / 10.0,
        "osc_smoothing": (tab.osc_smoothing.value() if hasattr(tab, "osc_smoothing") else pct("osc_smoothing")) / 100.0,
        "osc_line_color": _qcolor_to_list(getattr(tab, "_osc_line_color", None), d_value("osc_line_color")),
        "osc_glow_color": _qcolor_to_list(getattr(tab, "_osc_glow_color", None), d_value("osc_glow_color")),
        "osc_line_count": line_count,
        "osc_speed": (tab.osc_speed.value() if hasattr(tab, "osc_speed") else pct("osc_speed")) / 100.0,
        "osc_line_dim": tab.osc_line_dim.isChecked() if hasattr(tab, "osc_line_dim") else d_bool("osc_line_dim"),
        "osc_line_offset_bias": (tab.osc_line_offset_bias.value() if hasattr(tab, "osc_line_offset_bias") else pct("osc_line_offset_bias")) / 100.0,
        "osc_vertical_shift": tab.osc_vertical_shift.value() if hasattr(tab, "osc_vertical_shift") else d_int("osc_vertical_shift"),
        "osc_ghosting_enabled": tab.osc_ghost_enabled.isChecked() if hasattr(tab, "osc_ghost_enabled") else d_bool("osc_ghosting_enabled"),
        "osc_ghost_intensity": (tab.osc_ghost_intensity.value() if hasattr(tab, "osc_ghost_intensity") else pct("osc_ghost_intensity")) / 100.0,
        "osc_ghost_decay": (tab.osc_ghost_decay.value() if hasattr(tab, "osc_ghost_decay") else pct("osc_ghost_decay")) / 100.0,
        "osc_ghost_line2_enabled": tab.osc_ghost_line2_enabled.isChecked() if hasattr(tab, "osc_ghost_line2_enabled") else d_bool("osc_ghost_line2_enabled"),
        "osc_ghost_line3_enabled": tab.osc_ghost_line3_enabled.isChecked() if hasattr(tab, "osc_ghost_line3_enabled") else d_bool("osc_ghost_line3_enabled"),
        "osc_ghost_line4_enabled": tab.osc_ghost_line4_enabled.isChecked() if hasattr(tab, "osc_ghost_line4_enabled") else d_bool("osc_ghost_line4_enabled"),
        "osc_ghost_line5_enabled": tab.osc_ghost_line5_enabled.isChecked() if hasattr(tab, "osc_ghost_line5_enabled") else d_bool("osc_ghost_line5_enabled"),
        "osc_ghost_line6_enabled": tab.osc_ghost_line6_enabled.isChecked() if hasattr(tab, "osc_ghost_line6_enabled") else d_bool("osc_ghost_line6_enabled"),
    }
    payload.update(collect_extra_color_bindings(tab))
    return payload
