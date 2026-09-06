"""Spectrum visualizer settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from PySide6.QtGui import QColor

from core.logging.logger import get_logger
from core.settings.visualizer_settings_contract import resolve_spectrum_render_mode
from ui.color_utils import qcolor_to_list as _qcolor_to_list

logger = get_logger(__name__)

_SPECTRUM_LEGACY_NOTCHES_LINEAR = [[0.0, "Bass"], [0.25, "Low"], [0.50, "Mid"], [0.75, "Hi-Mid"], [1.0, "Treble"]]



def _promote_legacy_linear_notch_family(
    normalized: list[list],
    canonical_default: list[list],
) -> list[list]:
    """Promote old non-mirrored notch families into an explicit vocal lane.

    The original linear layout used `Bass / Low / Mid / Hi-Mid / Treble`.
    Users may have slightly moved those boundaries over time, so we should
    not require an exact positional match before upgrading the labels.
    """
    if len(normalized) != 5:
        return normalized

    labels = [str(label).strip().lower() for _, label in normalized]
    if labels == ["bass", "low", "mid", "hi-mid", "treble"]:
        if normalized == _SPECTRUM_LEGACY_NOTCHES_LINEAR:
            return [list(n) for n in canonical_default]
        return [
            [float(normalized[0][0]), "Bass"],
            [float(normalized[1][0]), "Low-Mid"],
            [float(normalized[2][0]), "Vocal"],
            [float(normalized[3][0]), "Hi-Mid"],
            [float(normalized[4][0]), "Treble"],
        ]

    if labels == ["bass", "low-mid", "mid", "hi-mid", "treble"]:
        return [
            [float(normalized[0][0]), "Bass"],
            [float(normalized[1][0]), "Low-Mid"],
            [float(normalized[2][0]), "Vocal"],
            [float(normalized[3][0]), "Hi-Mid"],
            [float(normalized[4][0]), "Treble"],
        ]

    return normalized


def _normalize_linear_notches(positions: Any, canonical_default: list[list]) -> list[list]:
    """Promote untouched legacy linear defaults into the vocal-lane layout."""
    if not isinstance(positions, list) or len(positions) < 2:
        return [list(n) for n in canonical_default]

    try:
        normalized = [[float(x), str(label)] for x, label in positions]
    except Exception:
        return [list(n) for n in canonical_default]

    return _promote_legacy_linear_notch_family(normalized, canonical_default)


def _clamp_lane_strength(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return float(default)


def _normalize_lane_strengths(value: Any, defaults: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {label: float(default) for label, default in defaults.items()}
    return {
        label: _clamp_lane_strength(value.get(label, default), default)
        for label, default in defaults.items()
    }


def load_spectrum_mode_settings(
    tab,
    spotify_vis_config: Mapping[str, Any] | None,
    *,
    sync_color_button: Callable[[str, str], None],
    update_ghost_visibility: Callable[[Any], None],
) -> None:
    """Load Spectrum-owned settings from the visualizer config into the tab."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}
    spectrum_render_mode = resolve_spectrum_render_mode(
        lambda key, default=None: config.get(key, default),
        fallback=tab._default_str("spotify_visualizer", "spectrum_render_mode"),
    )
    if hasattr(tab, "_set_spectrum_render_mode"):
        tab._set_spectrum_render_mode(spectrum_render_mode, save=False)
    elif hasattr(tab, "spectrum_render_mode_buttons"):
        tab._spectrum_render_mode = spectrum_render_mode
        for key, button in getattr(tab, "spectrum_render_mode_buttons", {}).items():
            button.setChecked(key == spectrum_render_mode)
    if hasattr(tab, "spectrum_visual_smoothing_enabled"):
        tab.spectrum_visual_smoothing_enabled.setChecked(
            tab._config_bool(
                "spotify_visualizer",
                config,
                "spectrum_visual_smoothing_enabled")
        )
    if hasattr(tab, "spectrum_visual_smoothing"):
        spectrum_visual_smoothing = max(
            0,
            min(
                100,
                int(
                    tab._config_float(
                        "spotify_visualizer",
                        config,
                        "spectrum_visual_smoothing")
                    * 100
                ),
            ),
        )
        tab.spectrum_visual_smoothing.setValue(spectrum_visual_smoothing)
        tab.spectrum_visual_smoothing_label.setText(
            f"{spectrum_visual_smoothing}%"
        )
    if hasattr(tab, "spectrum_rainbow_per_bar"):
        tab.spectrum_rainbow_per_bar.setChecked(
            tab._config_bool("spotify_visualizer", config, "spectrum_unique_colors")
        )
    if hasattr(tab, "spectrum_rainbow_fill"):
        tab.spectrum_rainbow_fill.setChecked(
            tab._config_bool("spotify_visualizer", config, "spectrum_rainbow_fill")
        )
    if hasattr(tab, "spectrum_rainbow_border"):
        tab.spectrum_rainbow_border.setChecked(
            tab._config_bool("spotify_visualizer", config, "spectrum_rainbow_border")
        )
    if hasattr(tab, "spectrum_wave_amplitude"):
        spectrum_wave_amplitude = int(tab._config_float("spotify_visualizer", config, "spectrum_wave_amplitude") * 100)
        tab.spectrum_wave_amplitude.setValue(max(0, min(100, spectrum_wave_amplitude)))
        tab.spectrum_wave_amplitude_label.setText(f"{spectrum_wave_amplitude}%")
    if hasattr(tab, "spectrum_profile_floor"):
        spectrum_profile_floor = int(tab._config_float("spotify_visualizer", config, "spectrum_profile_floor") * 100)
        tab.spectrum_profile_floor.setValue(max(5, min(30, spectrum_profile_floor)))
        tab.spectrum_profile_floor_label.setText(f"{spectrum_profile_floor / 100.0:.2f}")
    if hasattr(tab, "spectrum_drop_speed"):
        spectrum_drop_speed = int(tab._config_float("spotify_visualizer", config, "spectrum_drop_speed") * 100)
        tab.spectrum_drop_speed.setValue(max(50, min(300, spectrum_drop_speed)))
        tab.spectrum_drop_speed_label.setText(f"{spectrum_drop_speed / 100.0:.1f}x")
    if hasattr(tab, "spectrum_border_radius"):
        spectrum_border_radius = int(tab._config_float("spotify_visualizer", config, "spectrum_border_radius"))
        tab.spectrum_border_radius.setValue(max(0, min(12, spectrum_border_radius)))
        tab.spectrum_border_radius_label.setText(f"{spectrum_border_radius}px")
    if hasattr(tab, "spectrum_glow_enabled"):
        tab.spectrum_glow_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "spectrum_glow_enabled")
        )
    if hasattr(tab, "spectrum_glow_intensity"):
        spectrum_glow_intensity = int(tab._config_float("spotify_visualizer", config, "spectrum_glow_intensity") * 100)
        tab.spectrum_glow_intensity.setValue(max(0, min(150, spectrum_glow_intensity)))
        tab.spectrum_glow_intensity_label.setText(f"{spectrum_glow_intensity}%")

    spectrum_glow_color_default = tab._widget_default("spotify_visualizer", "spectrum_glow_color")
    spectrum_glow_color_data = config.get("spectrum_glow_color", spectrum_glow_color_default)
    try:
        tab._spectrum_glow_color = QColor(*spectrum_glow_color_data)
    except Exception:
        logger.debug("[SPECTRUM_BINDING] Failed to set spectrum_glow_color=%s", spectrum_glow_color_data, exc_info=True)
        tab._spectrum_glow_color = QColor(*spectrum_glow_color_default)
    sync_color_button("spectrum_glow_color_btn", "_spectrum_glow_color")

    if hasattr(tab, "spectrum_mirrored"):
        tab.spectrum_mirrored.setChecked(
            tab._config_bool("spotify_visualizer", config, "spectrum_mirrored")
        )
    if hasattr(tab, "spectrum_shape_editor"):
        saved_nodes = config.get("spectrum_shape_nodes", tab._widget_default("spotify_visualizer", "spectrum_shape_nodes"))
        if isinstance(saved_nodes, list) and len(saved_nodes) >= 1:
            tab.spectrum_shape_editor.set_nodes(saved_nodes)
        mirrored = tab._config_bool("spotify_visualizer", config, "spectrum_mirrored")
        tab.spectrum_shape_editor.set_mirrored(mirrored)
        notch_positions_mirrored = config.get("spectrum_notch_positions_mirrored", tab._widget_default("spotify_visualizer", "spectrum_notch_positions_mirrored"))
        if isinstance(notch_positions_mirrored, list) and len(notch_positions_mirrored) >= 2:
            tab.spectrum_shape_editor.set_notch_positions(notch_positions_mirrored, mirrored=True)
        canonical_linear_notches = tab._widget_default("spotify_visualizer", "spectrum_notch_positions_linear")
        notch_positions_linear = _normalize_linear_notches(
            config.get("spectrum_notch_positions_linear", canonical_linear_notches),
            canonical_linear_notches,
        )
        if len(notch_positions_linear) >= 2:
            tab.spectrum_shape_editor.set_notch_positions(notch_positions_linear, mirrored=False)
        tab.spectrum_shape_editor.set_lane_strengths(
            _normalize_lane_strengths(
                config.get("spectrum_lane_strengths_mirrored", tab._widget_default("spotify_visualizer", "spectrum_lane_strengths_mirrored")),
                tab._widget_default("spotify_visualizer", "spectrum_lane_strengths_mirrored"),
            ),
            mirrored=True,
        )
        tab.spectrum_shape_editor.set_lane_strengths(
            _normalize_lane_strengths(
                config.get("spectrum_lane_strengths_linear", tab._widget_default("spotify_visualizer", "spectrum_lane_strengths_linear")),
                tab._widget_default("spotify_visualizer", "spectrum_lane_strengths_linear"),
            ),
            mirrored=False,
        )

    ghost_enabled = config.get(
        "spectrum_ghosting_enabled",
        tab._widget_default("spotify_visualizer", "spectrum_ghosting_enabled"),
    )
    tab.vis_ghost_enabled.setChecked(bool(ghost_enabled))
    ghost_alpha = float(
        config.get(
            "spectrum_ghost_alpha",
            tab._widget_default("spotify_visualizer", "spectrum_ghost_alpha"),
        )
    )
    ghost_alpha_pct = max(0, min(100, int(ghost_alpha * 100)))
    tab.vis_ghost_opacity_slider.setValue(ghost_alpha_pct)
    tab.vis_ghost_opacity_label.setText(f"{ghost_alpha_pct}%")

    ghost_decay = float(
        config.get(
            "spectrum_ghost_decay",
            tab._widget_default("spotify_visualizer", "spectrum_ghost_decay"),
        )
    )
    ghost_decay_slider = max(10, min(100, int(ghost_decay * 100.0)))
    tab.vis_ghost_decay_slider.setValue(ghost_decay_slider)
    tab.vis_ghost_decay_label.setText(f"{ghost_decay_slider / 100.0:.2f}x")
    update_ghost_visibility(tab)


def collect_spectrum_mode_settings(tab) -> dict[str, Any]:
    """Collect Spectrum settings without introducing save-side shadow defaults."""
    d_bool = lambda key: tab._default_bool("spotify_visualizer", key)
    d_float = lambda key: tab._default_float("spotify_visualizer", key)
    d_str = lambda key: tab._default_str("spotify_visualizer", key)
    d_value = lambda key: tab._widget_default("spotify_visualizer", key)
    pct = lambda key: int(round(d_float(key) * 100.0))

    shape_editor = getattr(tab, "spectrum_shape_editor", None)
    return {
        "spectrum_ghosting_enabled": tab.vis_ghost_enabled.isChecked() if hasattr(tab, "vis_ghost_enabled") else d_bool("spectrum_ghosting_enabled"),
        "spectrum_ghost_alpha": (tab.vis_ghost_opacity_slider.value() if hasattr(tab, "vis_ghost_opacity_slider") else pct("spectrum_ghost_alpha")) / 100.0,
        "spectrum_ghost_decay": max(0.1, (tab.vis_ghost_decay_slider.value() if hasattr(tab, "vis_ghost_decay_slider") else pct("spectrum_ghost_decay")) / 100.0),
        "spectrum_render_mode": getattr(tab, "_spectrum_render_mode", d_str("spectrum_render_mode")),
        "spectrum_visual_smoothing_enabled": tab.spectrum_visual_smoothing_enabled.isChecked() if hasattr(tab, "spectrum_visual_smoothing_enabled") else d_bool("spectrum_visual_smoothing_enabled"),
        "spectrum_visual_smoothing": (tab.spectrum_visual_smoothing.value() if hasattr(tab, "spectrum_visual_smoothing") else pct("spectrum_visual_smoothing")) / 100.0,
        "spectrum_unique_colors": tab.spectrum_rainbow_per_bar.isChecked() if hasattr(tab, "spectrum_rainbow_per_bar") else d_bool("spectrum_unique_colors"),
        "spectrum_rainbow_fill": tab.spectrum_rainbow_fill.isChecked() if hasattr(tab, "spectrum_rainbow_fill") else d_bool("spectrum_rainbow_fill"),
        "spectrum_rainbow_border": tab.spectrum_rainbow_border.isChecked() if hasattr(tab, "spectrum_rainbow_border") else d_bool("spectrum_rainbow_border"),
        "spectrum_border_radius": float(tab.spectrum_border_radius.value()) if hasattr(tab, "spectrum_border_radius") else d_float("spectrum_border_radius"),
        "spectrum_glow_enabled": tab.spectrum_glow_enabled.isChecked() if hasattr(tab, "spectrum_glow_enabled") else d_bool("spectrum_glow_enabled"),
        "spectrum_glow_intensity": (tab.spectrum_glow_intensity.value() if hasattr(tab, "spectrum_glow_intensity") else pct("spectrum_glow_intensity")) / 100.0,
        "spectrum_glow_color": _qcolor_to_list(getattr(tab, "_spectrum_glow_color", None), d_value("spectrum_glow_color")),
        "spectrum_mirrored": tab.spectrum_mirrored.isChecked() if hasattr(tab, "spectrum_mirrored") else d_bool("spectrum_mirrored"),
        "spectrum_shape_nodes": shape_editor.get_nodes() if shape_editor is not None else d_value("spectrum_shape_nodes"),
        "spectrum_notch_positions_mirrored": list(shape_editor._notches_mirrored) if shape_editor is not None else d_value("spectrum_notch_positions_mirrored"),
        "spectrum_notch_positions_linear": list(shape_editor._notches_linear) if shape_editor is not None else d_value("spectrum_notch_positions_linear"),
        "spectrum_lane_strengths_mirrored": shape_editor.get_lane_strengths(mirrored=True) if shape_editor is not None else d_value("spectrum_lane_strengths_mirrored"),
        "spectrum_lane_strengths_linear": shape_editor.get_lane_strengths(mirrored=False) if shape_editor is not None else d_value("spectrum_lane_strengths_linear"),
        "spectrum_wave_amplitude": (tab.spectrum_wave_amplitude.value() if hasattr(tab, "spectrum_wave_amplitude") else pct("spectrum_wave_amplitude")) / 100.0,
        "spectrum_profile_floor": (tab.spectrum_profile_floor.value() if hasattr(tab, "spectrum_profile_floor") else pct("spectrum_profile_floor")) / 100.0,
        "spectrum_drop_speed": (tab.spectrum_drop_speed.value() if hasattr(tab, "spectrum_drop_speed") else pct("spectrum_drop_speed")) / 100.0,
    }
