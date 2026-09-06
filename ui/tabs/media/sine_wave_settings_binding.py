"""Sine Wave visualizer settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from PySide6.QtGui import QColor

from core.logging.logger import get_logger
from ui.color_utils import qcolor_to_list as _qcolor_to_list

logger = get_logger(__name__)

_SINE_COLOR_BINDINGS: tuple[tuple[str, str], ...] = (
    ("_sine_glow_color", "sine_glow_color"),
    ("_sine_line_color", "sine_line_color"),
    ("_sine_line2_color", "sine_line2_color"),
    ("_sine_line2_glow_color", "sine_line2_glow_color"),
    ("_sine_line3_color", "sine_line3_color"),
    ("_sine_line3_glow_color", "sine_line3_glow_color"),
    ("_sine_line4_color", "sine_line4_color"),
    ("_sine_line4_glow_color", "sine_line4_glow_color"),
    ("_sine_line5_color", "sine_line5_color"),
    ("_sine_line5_glow_color", "sine_line5_glow_color"),
    ("_sine_line6_color", "sine_line6_color"),
    ("_sine_line6_glow_color", "sine_line6_glow_color"),
)



def load_sine_wave_mode_settings(
    tab,
    spotify_vis_config: Mapping[str, Any] | None,
    *,
    sync_color_button: Callable[[str, str], None],
    update_multi_line_visibility: Callable[[Any], None],
) -> None:
    """Load Sine-owned settings from the visualizer config into the tab."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}

    if hasattr(tab, "sine_glow_enabled"):
        tab.sine_glow_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "sine_glow_enabled")
        )
    if hasattr(tab, "sine_glow_intensity"):
        sine_glow_intensity = int(tab._config_float("spotify_visualizer", config, "sine_glow_intensity") * 100)
        tab.sine_glow_intensity.setValue(max(0, min(100, sine_glow_intensity)))
        tab.sine_glow_intensity_label.setText(f"{sine_glow_intensity}%")
    if hasattr(tab, "sine_glow_reactivity"):
        sine_glow_reactivity = int(
            tab._config_float(
                "spotify_visualizer",
                config,
                "sine_glow_reactivity") * 100
        )
        tab.sine_glow_reactivity.setValue(max(0, min(200, sine_glow_reactivity)))
        tab.sine_glow_reactivity_label.setText(f"{sine_glow_reactivity}%")
    if hasattr(tab, "sine_reactive_glow"):
        tab.sine_reactive_glow.setChecked(
            tab._config_bool("spotify_visualizer", config, "sine_reactive_glow")
        )
    if hasattr(tab, "sine_sensitivity"):
        sine_sensitivity = int(tab._config_float("spotify_visualizer", config, "sine_sensitivity") * 100)
        tab.sine_sensitivity.setValue(max(10, min(500, sine_sensitivity)))
        tab.sine_sensitivity_label.setText(f"{sine_sensitivity / 100.0:.2f}x")
    if hasattr(tab, "sine_smoothing"):
        sine_smoothing = int(tab._config_float("spotify_visualizer", config, "sine_smoothing") * 100)
        tab.sine_smoothing.setValue(max(0, min(100, sine_smoothing)))
        tab.sine_smoothing_label.setText(f"{sine_smoothing}%")
    if hasattr(tab, "sine_speed"):
        sine_speed = int(tab._config_float("spotify_visualizer", config, "sine_speed") * 100)
        tab.sine_speed.setValue(max(10, min(100, sine_speed)))
        tab.sine_speed_label.setText(f"{sine_speed / 100.0:.2f}x")
    if hasattr(tab, "sine_wave_effect"):
        sine_wave_effect = int(
            tab._config_float(
                "spotify_visualizer",
                config,
                "sine_wave_effect") * 100
        )
        tab.sine_wave_effect.setValue(max(0, min(100, sine_wave_effect)))
        tab.sine_wave_effect_label.setText(f"{sine_wave_effect}%")
    if hasattr(tab, "sine_micro_wobble"):
        sine_micro_wobble = int(
            tab._config_float(
                "spotify_visualizer",
                config,
                "sine_micro_wobble") * 100
        )
        tab.sine_micro_wobble.setValue(max(0, min(100, sine_micro_wobble)))
        tab.sine_micro_wobble_label.setText(f"{sine_micro_wobble}%")
    if hasattr(tab, "sine_crawl_slider"):
        sine_crawl_amount = int(
            tab._config_float(
                "spotify_visualizer",
                config,
                "sine_crawl_amount") * 100
        )
        tab.sine_crawl_slider.setValue(max(0, min(100, sine_crawl_amount)))
        tab.sine_crawl_label.setText(f"{sine_crawl_amount}%")
    if hasattr(tab, "sine_width_reaction"):
        sine_width_reaction = int(tab._config_float("spotify_visualizer", config, "sine_width_reaction") * 100)
        tab.sine_width_reaction.setValue(max(0, min(100, sine_width_reaction)))
        tab.sine_width_reaction_label.setText(f"{sine_width_reaction}%")
    if hasattr(tab, "sine_density"):
        sine_density = int(tab._config_float("spotify_visualizer", config, "sine_density") * 100)
        tab.sine_density.setValue(max(25, min(300, sine_density)))
        tab.sine_density_label.setText(f"{max(25, min(300, sine_density)) / 100.0:.2f}×")
    if hasattr(tab, "sine_heartbeat"):
        sine_heartbeat = int(tab._config_float("spotify_visualizer", config, "sine_heartbeat") * 100)
        tab.sine_heartbeat.setValue(max(0, min(100, sine_heartbeat)))
        tab.sine_heartbeat_label.setText(f"{sine_heartbeat}%")
    if hasattr(tab, "sine_displacement"):
        sine_displacement = int(tab._config_float("spotify_visualizer", config, "sine_displacement") * 100)
        tab.sine_displacement.setValue(max(0, min(100, sine_displacement)))
        tab.sine_displacement_label.setText(f"{sine_displacement}%")
    if hasattr(tab, "sine_vertical_shift"):
        sine_vertical_shift = int(config.get("sine_vertical_shift", tab._widget_default("spotify_visualizer", "sine_vertical_shift")))
        if isinstance(config.get("sine_vertical_shift"), bool):
            sine_vertical_shift = 100 if config.get("sine_vertical_shift") else 0
        tab.sine_vertical_shift.setValue(max(-50, min(200, sine_vertical_shift)))
        tab.sine_vertical_shift_label.setText(f"{sine_vertical_shift}")
    if hasattr(tab, "sine_line1_shift"):
        sine_line1_shift = int(tab._config_float("spotify_visualizer", config, "sine_line1_shift") * 100)
        tab.sine_line1_shift.setValue(max(-100, min(100, sine_line1_shift)))
        tab.sine_line1_shift_label.setText(f"{sine_line1_shift / 100.0:.2f} cycles")
    if hasattr(tab, "sine_travel"):
        sine_wave_travel = int(config.get("sine_wave_travel", tab._widget_default("spotify_visualizer", "sine_wave_travel")) or 0)
        tab.sine_travel.setCurrentIndex(max(0, min(2, sine_wave_travel)))
    if hasattr(tab, "sine_travel_line2"):
        sine_travel_line2 = int(config.get("sine_travel_line2", tab._widget_default("spotify_visualizer", "sine_travel_line2")) or 0)
        tab.sine_travel_line2.setCurrentIndex(max(0, min(2, sine_travel_line2)))
    if hasattr(tab, "sine_travel_line3"):
        sine_travel_line3 = int(config.get("sine_travel_line3", tab._widget_default("spotify_visualizer", "sine_travel_line3")) or 0)
        tab.sine_travel_line3.setCurrentIndex(max(0, min(2, sine_travel_line3)))
    if hasattr(tab, "sine_travel_line4"):
        sine_travel_line4 = int(config.get("sine_travel_line4", tab._widget_default("spotify_visualizer", "sine_travel_line4")) or 0)
        tab.sine_travel_line4.setCurrentIndex(max(0, min(2, sine_travel_line4)))
    if hasattr(tab, "sine_travel_line5"):
        sine_travel_line5 = int(config.get("sine_travel_line5", tab._widget_default("spotify_visualizer", "sine_travel_line5")) or 0)
        tab.sine_travel_line5.setCurrentIndex(max(0, min(2, sine_travel_line5)))
    if hasattr(tab, "sine_travel_line6"):
        sine_travel_line6 = int(config.get("sine_travel_line6", tab._widget_default("spotify_visualizer", "sine_travel_line6")) or 0)
        tab.sine_travel_line6.setCurrentIndex(max(0, min(2, sine_travel_line6)))

    sine_line_count = int(config.get("sine_line_count", tab._widget_default("spotify_visualizer", "sine_line_count")) or 1)
    if hasattr(tab, "sine_multi_line"):
        tab.sine_multi_line.setChecked(sine_line_count > 1)
    if hasattr(tab, "sine_line_count_slider"):
        clamped_line_count = max(2, min(6, int(config.get("sine_line_count", tab._widget_default("spotify_visualizer", "sine_line_count")) or 2)))
        tab.sine_line_count_slider.setValue(clamped_line_count)
        tab.sine_line_count_label.setText(str(clamped_line_count))

    for attr, key in _SINE_COLOR_BINDINGS:
        default = tab._widget_default("spotify_visualizer", key)
        color_data = config.get(key, default)
        try:
            setattr(tab, attr, QColor(*color_data))
        except Exception:
            logger.debug("[SINE_BINDING] Failed to set %s=%s", attr, color_data, exc_info=True)
            setattr(tab, attr, QColor(*default))

    sync_color_button("sine_glow_color_btn", "_sine_glow_color")
    sync_color_button("sine_line_color_btn", "_sine_line_color")
    sync_color_button("sine_line2_color_btn", "_sine_line2_color")
    sync_color_button("sine_line2_glow_btn", "_sine_line2_glow_color")
    sync_color_button("sine_line3_color_btn", "_sine_line3_color")
    sync_color_button("sine_line3_glow_btn", "_sine_line3_glow_color")
    sync_color_button("sine_line4_color_btn", "_sine_line4_color")
    sync_color_button("sine_line4_glow_btn", "_sine_line4_glow_color")
    sync_color_button("sine_line5_color_btn", "_sine_line5_color")
    sync_color_button("sine_line5_glow_btn", "_sine_line5_glow_color")
    sync_color_button("sine_line6_color_btn", "_sine_line6_color")
    sync_color_button("sine_line6_glow_btn", "_sine_line6_glow_color")
    update_multi_line_visibility(tab)

    if hasattr(tab, "sine_line2_shift"):
        sine_line2_shift = int(tab._config_float("spotify_visualizer", config, "sine_line2_shift") * 100)
        tab.sine_line2_shift.setValue(max(-100, min(100, sine_line2_shift)))
        tab.sine_line2_shift_label.setText(f"{sine_line2_shift / 100.0:.2f} cycles")
    if hasattr(tab, "sine_line3_shift"):
        sine_line3_shift = int(tab._config_float("spotify_visualizer", config, "sine_line3_shift") * 100)
        tab.sine_line3_shift.setValue(max(-100, min(100, sine_line3_shift)))
        tab.sine_line3_shift_label.setText(f"{sine_line3_shift / 100.0:.2f} cycles")
    if hasattr(tab, "sine_line4_shift"):
        sine_line4_shift = int(tab._config_float("spotify_visualizer", config, "sine_line4_shift") * 100)
        tab.sine_line4_shift.setValue(max(-100, min(100, sine_line4_shift)))
        tab.sine_line4_shift_label.setText(f"{sine_line4_shift / 100.0:.2f} cycles")
    if hasattr(tab, "sine_line5_shift"):
        sine_line5_shift = int(tab._config_float("spotify_visualizer", config, "sine_line5_shift") * 100)
        tab.sine_line5_shift.setValue(max(-100, min(100, sine_line5_shift)))
        tab.sine_line5_shift_label.setText(f"{sine_line5_shift / 100.0:.2f} cycles")
    if hasattr(tab, "sine_line6_shift"):
        sine_line6_shift = int(tab._config_float("spotify_visualizer", config, "sine_line6_shift") * 100)
        tab.sine_line6_shift.setValue(max(-100, min(100, sine_line6_shift)))
        tab.sine_line6_shift_label.setText(f"{sine_line6_shift / 100.0:.2f} cycles")
    if hasattr(tab, "sine_line_dim"):
        tab.sine_line_dim.setChecked(bool(config.get("sine_line_dim", tab._widget_default("spotify_visualizer", "sine_line_dim"))))
    if hasattr(tab, "sine_line_offset_bias"):
        sine_line_offset_bias = int(tab._config_float("spotify_visualizer", config, "sine_line_offset_bias") * 100)
        tab.sine_line_offset_bias.setValue(max(0, min(100, sine_line_offset_bias)))
        tab.sine_line_offset_bias_label.setText(f"{sine_line_offset_bias}%")
    if hasattr(tab, "sine_card_adaptation"):
        sine_card_adaptation = int(tab._config_float("spotify_visualizer", config, "sine_card_adaptation") * 100)
        tab.sine_card_adaptation.setValue(max(5, min(100, sine_card_adaptation)))
        tab.sine_card_adaptation_label.setText(f"{sine_card_adaptation}%")
    if hasattr(tab, "sine_ghost_enabled"):
        tab.sine_ghost_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "sine_ghosting_enabled")
        )
    if hasattr(tab, "sine_ghost_opacity"):
        sine_ghost_alpha = int(tab._config_float("spotify_visualizer", config, "sine_ghost_alpha") * 100)
        tab.sine_ghost_opacity.setValue(max(0, min(100, sine_ghost_alpha)))
        tab.sine_ghost_opacity_label.setText(f"{sine_ghost_alpha}%")
    if hasattr(tab, "sine_ghost_decay_slider"):
        sine_ghost_decay = int(tab._config_float("spotify_visualizer", config, "sine_ghost_decay") * 100)
        tab.sine_ghost_decay_slider.setValue(max(10, min(100, sine_ghost_decay)))
        tab.sine_ghost_decay_label.setText(f"{sine_ghost_decay / 100.0:.2f}x")
    if hasattr(tab, "sine_ghost_line2_enabled"):
        tab.sine_ghost_line2_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "sine_ghost_line2_enabled")
        )
    if hasattr(tab, "sine_ghost_line3_enabled"):
        tab.sine_ghost_line3_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "sine_ghost_line3_enabled")
        )
    if hasattr(tab, "sine_ghost_line4_enabled"):
        tab.sine_ghost_line4_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "sine_ghost_line4_enabled")
        )
    if hasattr(tab, "sine_ghost_line5_enabled"):
        tab.sine_ghost_line5_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "sine_ghost_line5_enabled")
        )
    if hasattr(tab, "sine_ghost_line6_enabled"):
        tab.sine_ghost_line6_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "sine_ghost_line6_enabled")
        )


def collect_sine_wave_mode_settings(tab) -> dict[str, Any]:
    """Collect Sine settings without introducing save-side shadow defaults."""
    d_bool = lambda key: tab._default_bool("spotify_visualizer", key)
    d_int = lambda key: tab._default_int("spotify_visualizer", key)
    d_float = lambda key: tab._default_float("spotify_visualizer", key)
    d_value = lambda key: tab._widget_default("spotify_visualizer", key)
    pct = lambda key: int(round(d_float(key) * 100.0))

    if hasattr(tab, "sine_line_count_slider") and hasattr(tab, "sine_multi_line"):
        line_count = tab.sine_line_count_slider.value() if tab.sine_multi_line.isChecked() else 1
    else:
        line_count = d_int("sine_line_count")

    payload = {
        "sine_glow_enabled": tab.sine_glow_enabled.isChecked() if hasattr(tab, "sine_glow_enabled") else d_bool("sine_glow_enabled"),
        "sine_glow_intensity": (tab.sine_glow_intensity.value() if hasattr(tab, "sine_glow_intensity") else pct("sine_glow_intensity")) / 100.0,
        "sine_glow_reactivity": (tab.sine_glow_reactivity.value() if hasattr(tab, "sine_glow_reactivity") else pct("sine_glow_reactivity")) / 100.0,
        "sine_glow_color": _qcolor_to_list(getattr(tab, "_sine_glow_color", None), d_value("sine_glow_color")),
        "sine_line_color": _qcolor_to_list(getattr(tab, "_sine_line_color", None), d_value("sine_line_color")),
        "sine_reactive_glow": tab.sine_reactive_glow.isChecked() if hasattr(tab, "sine_reactive_glow") else d_bool("sine_reactive_glow"),
        "sine_sensitivity": (tab.sine_sensitivity.value() if hasattr(tab, "sine_sensitivity") else pct("sine_sensitivity")) / 100.0,
        "sine_smoothing": (tab.sine_smoothing.value() if hasattr(tab, "sine_smoothing") else pct("sine_smoothing")) / 100.0,
        "sine_speed": (tab.sine_speed.value() if hasattr(tab, "sine_speed") else pct("sine_speed")) / 100.0,
        "sine_wave_effect": (tab.sine_wave_effect.value() if hasattr(tab, "sine_wave_effect") else pct("sine_wave_effect")) / 100.0,
        "sine_crawl_amount": (tab.sine_crawl_slider.value() if hasattr(tab, "sine_crawl_slider") else pct("sine_crawl_amount")) / 100.0,
        "sine_micro_wobble": (tab.sine_micro_wobble.value() if hasattr(tab, "sine_micro_wobble") else pct("sine_micro_wobble")) / 100.0,
        "sine_width_reaction": (tab.sine_width_reaction.value() if hasattr(tab, "sine_width_reaction") else pct("sine_width_reaction")) / 100.0,
        "sine_density": (tab.sine_density.value() if hasattr(tab, "sine_density") else pct("sine_density")) / 100.0,
        "sine_heartbeat": (tab.sine_heartbeat.value() if hasattr(tab, "sine_heartbeat") else pct("sine_heartbeat")) / 100.0,
        "sine_displacement": (tab.sine_displacement.value() if hasattr(tab, "sine_displacement") else pct("sine_displacement")) / 100.0,
        "sine_vertical_shift": tab.sine_vertical_shift.value() if hasattr(tab, "sine_vertical_shift") else d_int("sine_vertical_shift"),
        "sine_line1_shift": (tab.sine_line1_shift.value() if hasattr(tab, "sine_line1_shift") else pct("sine_line1_shift")) / 100.0,
        "sine_wave_travel": tab.sine_travel.currentIndex() if hasattr(tab, "sine_travel") else d_int("sine_wave_travel"),
        "sine_travel_line2": tab.sine_travel_line2.currentIndex() if hasattr(tab, "sine_travel_line2") else d_int("sine_travel_line2"),
        "sine_travel_line3": tab.sine_travel_line3.currentIndex() if hasattr(tab, "sine_travel_line3") else d_int("sine_travel_line3"),
        "sine_travel_line4": tab.sine_travel_line4.currentIndex() if hasattr(tab, "sine_travel_line4") else d_int("sine_travel_line4"),
        "sine_travel_line5": tab.sine_travel_line5.currentIndex() if hasattr(tab, "sine_travel_line5") else d_int("sine_travel_line5"),
        "sine_travel_line6": tab.sine_travel_line6.currentIndex() if hasattr(tab, "sine_travel_line6") else d_int("sine_travel_line6"),
        "sine_line_count": line_count,
        "sine_line_dim": tab.sine_line_dim.isChecked() if hasattr(tab, "sine_line_dim") else d_bool("sine_line_dim"),
        "sine_line_offset_bias": (tab.sine_line_offset_bias.value() if hasattr(tab, "sine_line_offset_bias") else pct("sine_line_offset_bias")) / 100.0,
        "sine_card_adaptation": (tab.sine_card_adaptation.value() if hasattr(tab, "sine_card_adaptation") else pct("sine_card_adaptation")) / 100.0,
        "sine_line2_shift": (tab.sine_line2_shift.value() if hasattr(tab, "sine_line2_shift") else pct("sine_line2_shift")) / 100.0,
        "sine_line3_shift": (tab.sine_line3_shift.value() if hasattr(tab, "sine_line3_shift") else pct("sine_line3_shift")) / 100.0,
        "sine_line4_shift": (tab.sine_line4_shift.value() if hasattr(tab, "sine_line4_shift") else pct("sine_line4_shift")) / 100.0,
        "sine_line5_shift": (tab.sine_line5_shift.value() if hasattr(tab, "sine_line5_shift") else pct("sine_line5_shift")) / 100.0,
        "sine_line6_shift": (tab.sine_line6_shift.value() if hasattr(tab, "sine_line6_shift") else pct("sine_line6_shift")) / 100.0,
        "sine_ghosting_enabled": tab.sine_ghost_enabled.isChecked() if hasattr(tab, "sine_ghost_enabled") else d_bool("sine_ghosting_enabled"),
        "sine_ghost_alpha": (tab.sine_ghost_opacity.value() if hasattr(tab, "sine_ghost_opacity") else pct("sine_ghost_alpha")) / 100.0,
        "sine_ghost_decay": max(0.1, (tab.sine_ghost_decay_slider.value() if hasattr(tab, "sine_ghost_decay_slider") else pct("sine_ghost_decay")) / 100.0),
        "sine_ghost_line2_enabled": tab.sine_ghost_line2_enabled.isChecked() if hasattr(tab, "sine_ghost_line2_enabled") else d_bool("sine_ghost_line2_enabled"),
        "sine_ghost_line3_enabled": tab.sine_ghost_line3_enabled.isChecked() if hasattr(tab, "sine_ghost_line3_enabled") else d_bool("sine_ghost_line3_enabled"),
        "sine_ghost_line4_enabled": tab.sine_ghost_line4_enabled.isChecked() if hasattr(tab, "sine_ghost_line4_enabled") else d_bool("sine_ghost_line4_enabled"),
        "sine_ghost_line5_enabled": tab.sine_ghost_line5_enabled.isChecked() if hasattr(tab, "sine_ghost_line5_enabled") else d_bool("sine_ghost_line5_enabled"),
        "sine_ghost_line6_enabled": tab.sine_ghost_line6_enabled.isChecked() if hasattr(tab, "sine_ghost_line6_enabled") else d_bool("sine_ghost_line6_enabled"),
    }
    for attr, key in _SINE_COLOR_BINDINGS[2:]:
        payload[key] = _qcolor_to_list(getattr(tab, attr, None), d_value(key))
    return payload
