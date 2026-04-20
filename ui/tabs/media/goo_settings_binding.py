"""Goo visualizer settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from PySide6.QtGui import QColor

from core.logging.logger import get_logger
from ui.color_utils import qcolor_to_list as _qcolor_to_list

logger = get_logger(__name__)

_GOO_COLOR_DEFAULTS: tuple[tuple[str, str, list[int]], ...] = (
    ("_goo_color", "goo_color", [0, 140, 220, 230]),
    ("_goo_outline_color", "goo_outline_color", [255, 255, 255, 255]),
    ("_goo_shadow_color", "goo_shadow_color", [0, 60, 110, 180]),
)


def load_goo_mode_settings(
    tab,
    spotify_vis_config: Mapping[str, Any] | None,
    *,
    sync_color_button: Callable[[str, str], None],
) -> None:
    """Load Goo-owned settings from the visualizer config into ``tab``."""
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}

    # --- Ghost block ---------------------------------------------------------
    if hasattr(tab, "goo_ghost_enabled"):
        tab.goo_ghost_enabled.setChecked(
            tab._config_bool("spotify_visualizer", config, "goo_ghosting_enabled", False)
        )
    if hasattr(tab, "goo_ghost_opacity"):
        alpha_pct = int(tab._config_float("spotify_visualizer", config, "goo_ghost_alpha", 0.0) * 100)
        tab.goo_ghost_opacity.setValue(max(0, min(100, alpha_pct)))
        tab.goo_ghost_opacity_label.setText(f"{alpha_pct}%")
    if hasattr(tab, "goo_ghost_decay_slider"):
        decay_pct = int(round(tab._config_float("spotify_visualizer", config, "goo_ghost_decay", 0.4) * 100))
        tab.goo_ghost_decay_slider.setValue(max(10, min(100, decay_pct)))
        tab.goo_ghost_decay_label.setText(f"{decay_pct / 100.0:.2f}x")

    # --- Appearance sliders --------------------------------------------------
    if hasattr(tab, "goo_outline_width"):
        v = int(tab._config_float("spotify_visualizer", config, "goo_outline_width", 0.004) * 1000)
        tab.goo_outline_width.setValue(max(0, min(50, v)))
        tab.goo_outline_width_label.setText(f"{v / 1000.0:.3f}")
    if hasattr(tab, "goo_shadow_strength"):
        v = int(tab._config_float("spotify_visualizer", config, "goo_shadow_strength", 0.3) * 100)
        tab.goo_shadow_strength.setValue(max(0, min(100, v)))
        tab.goo_shadow_strength_label.setText(f"{v}%")
    if hasattr(tab, "goo_specular_density"):
        v = int(tab._config_float("spotify_visualizer", config, "goo_specular_density", 0.3) * 100)
        tab.goo_specular_density.setValue(max(0, min(100, v)))
        tab.goo_specular_density_label.setText(f"{v}%")
    if hasattr(tab, "goo_void_floor"):
        v = int(tab._config_float("spotify_visualizer", config, "goo_void_floor", 0.15) * 100)
        tab.goo_void_floor.setValue(max(0, min(60, v)))
        tab.goo_void_floor_label.setText(f"{v}%")

    # --- Motion sliders ------------------------------------------------------
    if hasattr(tab, "goo_advance_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "goo_advance_speed", 1.0) * 100)
        tab.goo_advance_speed.setValue(max(10, min(300, v)))
        tab.goo_advance_speed_label.setText(f"{v / 100.0:.2f}x")
    if hasattr(tab, "goo_retreat_speed"):
        v = int(tab._config_float("spotify_visualizer", config, "goo_retreat_speed", 1.0) * 100)
        tab.goo_retreat_speed.setValue(max(10, min(300, v)))
        tab.goo_retreat_speed_label.setText(f"{v / 100.0:.2f}x")
    if hasattr(tab, "goo_source_count"):
        v = int(tab._config_int("spotify_visualizer", config, "goo_source_count", 64))
        tab.goo_source_count.setValue(max(16, min(128, v)))
        tab.goo_source_count_label.setText(str(max(16, min(128, v))))
    if hasattr(tab, "goo_growth"):
        v = int(tab._config_float("spotify_visualizer", config, "goo_growth", 3.5) * 100)
        tab.goo_growth.setValue(max(100, min(500, v)))
        tab.goo_growth_label.setText(f"{v / 100.0:.1f}x")

    # --- Colors --------------------------------------------------------------
    for attr, key, default in _GOO_COLOR_DEFAULTS:
        color_data = config.get(key, default)
        try:
            setattr(tab, attr, QColor(*color_data))
        except Exception:
            logger.debug("[GOO_BINDING] Failed to set %s=%s", attr, color_data, exc_info=True)
            setattr(tab, attr, QColor(*default))

    sync_color_button("goo_color_btn", "_goo_color")
    sync_color_button("goo_outline_color_btn", "_goo_outline_color")
    sync_color_button("goo_shadow_color_btn", "_goo_shadow_color")


def collect_goo_mode_settings(tab) -> dict[str, Any]:
    """Collect Goo-owned settings from ``tab`` into a config mapping."""
    return {
        "goo_ghosting_enabled": tab.goo_ghost_enabled.isChecked() if hasattr(tab, "goo_ghost_enabled") else False,
        "goo_ghost_alpha": (tab.goo_ghost_opacity.value() if hasattr(tab, "goo_ghost_opacity") else 0) / 100.0,
        "goo_ghost_decay": max(
            0.1,
            (tab.goo_ghost_decay_slider.value() if hasattr(tab, "goo_ghost_decay_slider") else 40) / 100.0,
        ),
        "goo_outline_width": (tab.goo_outline_width.value() if hasattr(tab, "goo_outline_width") else 4) / 1000.0,
        "goo_shadow_strength": (tab.goo_shadow_strength.value() if hasattr(tab, "goo_shadow_strength") else 30) / 100.0,
        "goo_specular_density": (tab.goo_specular_density.value() if hasattr(tab, "goo_specular_density") else 30) / 100.0,
        "goo_void_floor": (tab.goo_void_floor.value() if hasattr(tab, "goo_void_floor") else 15) / 100.0,
        "goo_advance_speed": (tab.goo_advance_speed.value() if hasattr(tab, "goo_advance_speed") else 100) / 100.0,
        "goo_retreat_speed": (tab.goo_retreat_speed.value() if hasattr(tab, "goo_retreat_speed") else 100) / 100.0,
        "goo_source_count": int(tab.goo_source_count.value()) if hasattr(tab, "goo_source_count") else 64,
        "goo_growth": (tab.goo_growth.value() if hasattr(tab, "goo_growth") else 350) / 100.0,
        "goo_color": _qcolor_to_list(getattr(tab, "_goo_color", None), [0, 140, 220, 230]),
        "goo_outline_color": _qcolor_to_list(getattr(tab, "_goo_outline_color", None), [255, 255, 255, 255]),
        "goo_shadow_color": _qcolor_to_list(getattr(tab, "_goo_shadow_color", None), [0, 60, 110, 180]),
    }


__all__ = ["load_goo_mode_settings", "collect_goo_mode_settings"]
