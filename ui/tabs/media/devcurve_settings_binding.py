"""Dev Curve settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from PySide6.QtGui import QColor

from ui.color_utils import qcolor_to_list as _qcolor_to_list

_LAYER_DEFAULTS = {
    "bass": {"color": [82, 167, 255, 230], "alpha": 0.55, "power": 1.0, "offset": 0.00, "enabled": True, "order": 1},
    "vocals": {"color": [136, 190, 255, 220], "alpha": 0.42, "power": 1.0, "offset": -0.01, "enabled": True, "order": 2},
    "mids": {"color": [100, 145, 255, 220], "alpha": 0.46, "power": 1.0, "offset": 0.01, "enabled": True, "order": 3},
    "transients": {"color": [215, 240, 255, 240], "alpha": 0.66, "power": 1.15, "offset": 0.00, "enabled": True, "order": 4},
}
_DEFAULT_SHAPE_NODES = [[0.0, 0.58], [0.35, 0.64], [0.70, 0.52], [1.0, 0.60]]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def load_devcurve_mode_settings(
    tab,
    spotify_vis_config: Mapping[str, Any] | None,
    *,
    sync_color_button: Callable[[str, str], None],
) -> None:
    _ = sync_color_button
    config = spotify_vis_config if isinstance(spotify_vis_config, Mapping) else {}

    if hasattr(tab, "devcurve_outline_width"):
        v = int(float(config.get("devcurve_outline_width", 0.006)) * 1000.0)
        v = max(1, min(20, v))
        tab.devcurve_outline_width.setValue(v)
        tab.devcurve_outline_width_label.setText(f"{v / 1000.0:.3f}")
    if hasattr(tab, "devcurve_outline_opacity"):
        v = int(float(config.get("devcurve_outline_alpha", 1.0)) * 100.0)
        v = max(0, min(100, v))
        tab.devcurve_outline_opacity.setValue(v)
        tab.devcurve_outline_opacity_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_base_level"):
        v = int(float(config.get("devcurve_base_level", 0.58)) * 100.0)
        v = max(10, min(90, v))
        tab.devcurve_base_level.setValue(v)
        tab.devcurve_base_level_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_motion_power"):
        v = int(float(config.get("devcurve_motion_power", 1.0)) * 100.0)
        v = max(0, min(300, v))
        tab.devcurve_motion_power.setValue(v)
        tab.devcurve_motion_power_label.setText(f"{v / 100.0:.2f}x")
    if hasattr(tab, "devcurve_idle_motion"):
        v = int(float(config.get("devcurve_idle_motion", 0.20)) * 100.0)
        v = max(0, min(150, v))
        tab.devcurve_idle_motion.setValue(v)
        tab.devcurve_idle_motion_label.setText(f"{v / 100.0:.2f}")
    if hasattr(tab, "devcurve_idle_speed"):
        v = int(float(config.get("devcurve_idle_speed", 0.60)) * 100.0)
        v = max(5, min(200, v))
        tab.devcurve_idle_speed.setValue(v)
        tab.devcurve_idle_speed_label.setText(f"{v / 100.0:.2f}x")
    if hasattr(tab, "devcurve_smoothness"):
        v = int(float(config.get("devcurve_smoothness", 0.55)) * 100.0)
        v = max(0, min(100, v))
        tab.devcurve_smoothness.setValue(v)
        tab.devcurve_smoothness_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_growth"):
        v = int(float(config.get("devcurve_growth", 3.0)) * 100.0)
        v = max(100, min(500, v))
        tab.devcurve_growth.setValue(v)
        tab.devcurve_growth_label.setText(f"{v / 100.0:.1f}x")
    if hasattr(tab, "devcurve_shape_editor"):
        layer_nodes = {}
        for src in _LAYER_DEFAULTS:
            key = f"devcurve_layer_{src}_shape_nodes"
            raw = config.get(key, _DEFAULT_SHAPE_NODES)
            if isinstance(raw, list) and raw:
                layer_nodes[src] = raw
        if hasattr(tab.devcurve_shape_editor, "set_layer_nodes_map"):
            tab.devcurve_shape_editor.set_layer_nodes_map(layer_nodes)
        if hasattr(tab.devcurve_shape_editor, "set_layer_strengths"):
            tab.devcurve_shape_editor.set_layer_strengths(
                {
                    src: _clamp01(float(config.get(f"devcurve_layer_{src}_power", defaults["power"])) / 3.0)
                    for src, defaults in _LAYER_DEFAULTS.items()
                }
            )
        if hasattr(tab.devcurve_shape_editor, "set_active_layer"):
            tab.devcurve_shape_editor.set_active_layer(
                str(config.get("devcurve_active_layer", "bass")).strip().lower()
            )

    for src, defaults in _LAYER_DEFAULTS.items():
        enabled = bool(config.get(f"devcurve_layer_{src}_enabled", defaults["enabled"]))
        setattr(tab, f"devcurve_layer_{src}_enabled", getattr(tab, f"devcurve_layer_{src}_enabled"))
        getattr(tab, f"devcurve_layer_{src}_enabled").setChecked(enabled)

        alpha = int(float(config.get(f"devcurve_layer_{src}_alpha", defaults["alpha"])) * 100.0)
        alpha = max(0, min(100, alpha))
        getattr(tab, f"devcurve_layer_{src}_alpha").setValue(alpha)
        getattr(tab, f"devcurve_layer_{src}_alpha_label").setText(f"{alpha}%")

        offset = int(float(config.get(f"devcurve_layer_{src}_offset", defaults["offset"])) * 100.0)
        offset = max(-45, min(45, offset))
        getattr(tab, f"devcurve_layer_{src}_offset").setValue(offset)
        getattr(tab, f"devcurve_layer_{src}_offset_label").setText(f"{offset / 100.0:+.2f}")
        order = int(float(config.get(f"devcurve_layer_{src}_order", defaults["order"])))
        order = max(1, min(4, order))
        setattr(tab, f"_devcurve_layer_{src}_order", order)
        order_slider = getattr(tab, f"devcurve_layer_{src}_order", None)
        order_label = getattr(tab, f"devcurve_layer_{src}_order_label", None)
        if order_slider is not None and hasattr(order_slider, "setValue"):
            order_slider.setValue(order)
        if order_label is not None and hasattr(order_label, "setText"):
            order_label.setText(f"{order}")

        color_data = config.get(f"devcurve_layer_{src}_color", defaults["color"])
        try:
            setattr(tab, f"_devcurve_layer_{src}_color", QColor(*color_data))
        except Exception:
            setattr(tab, f"_devcurve_layer_{src}_color", QColor(*defaults["color"]))
        if hasattr(tab, f"devcurve_layer_{src}_color_btn"):
            sync_color_button(f"devcurve_layer_{src}_color_btn", f"_devcurve_layer_{src}_color")

    apply_active_ui = getattr(tab, "_devcurve_apply_active_layer_ui", None)
    if callable(apply_active_ui):
        apply_active_ui(str(config.get("devcurve_active_layer", "bass")).strip().lower())
    normalize_layer_orders = getattr(tab, "_devcurve_normalize_layer_orders", None)
    if callable(normalize_layer_orders):
        normalize_layer_orders(save=False)

    if hasattr(tab, "devcurve_ghost_enabled"):
        tab.devcurve_ghost_enabled.setChecked(bool(config.get("devcurve_ghosting_enabled", False)))
    if hasattr(tab, "devcurve_ghost_opacity"):
        v = int(float(config.get("devcurve_ghost_alpha", 0.0)) * 100.0)
        v = max(0, min(100, v))
        tab.devcurve_ghost_opacity.setValue(v)
        tab.devcurve_ghost_opacity_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_ghost_decay"):
        v = int(float(config.get("devcurve_ghost_decay", 0.4)) * 100.0)
        v = max(10, min(100, v))
        tab.devcurve_ghost_decay.setValue(v)
        if hasattr(tab, "devcurve_ghost_decay_label"):
            tab.devcurve_ghost_decay_label.setText(f"{v / 100.0:.2f}x")


def collect_devcurve_mode_settings(tab) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "devcurve_outline_width": (tab.devcurve_outline_width.value() if hasattr(tab, "devcurve_outline_width") else 6) / 1000.0,
        "devcurve_outline_alpha": (tab.devcurve_outline_opacity.value() if hasattr(tab, "devcurve_outline_opacity") else 100) / 100.0,
        "devcurve_base_level": (tab.devcurve_base_level.value() if hasattr(tab, "devcurve_base_level") else 58) / 100.0,
        "devcurve_motion_power": (tab.devcurve_motion_power.value() if hasattr(tab, "devcurve_motion_power") else 100) / 100.0,
        "devcurve_idle_motion": (tab.devcurve_idle_motion.value() if hasattr(tab, "devcurve_idle_motion") else 20) / 100.0,
        "devcurve_idle_speed": (tab.devcurve_idle_speed.value() if hasattr(tab, "devcurve_idle_speed") else 60) / 100.0,
        "devcurve_smoothness": (tab.devcurve_smoothness.value() if hasattr(tab, "devcurve_smoothness") else 55) / 100.0,
        "devcurve_growth": (tab.devcurve_growth.value() if hasattr(tab, "devcurve_growth") else 300) / 100.0,
        "devcurve_active_layer": str(getattr(tab, "_devcurve_active_layer", "bass")),
        "devcurve_ghosting_enabled": tab.devcurve_ghost_enabled.isChecked() if hasattr(tab, "devcurve_ghost_enabled") else False,
        "devcurve_ghost_alpha": (tab.devcurve_ghost_opacity.value() if hasattr(tab, "devcurve_ghost_opacity") else 0) / 100.0,
        "devcurve_ghost_decay": (tab.devcurve_ghost_decay.value() if hasattr(tab, "devcurve_ghost_decay") else 40) / 100.0,
    }

    layer_strengths = {}
    if hasattr(tab, "devcurve_shape_editor") and hasattr(tab.devcurve_shape_editor, "get_layer_strengths"):
        try:
            layer_strengths = dict(tab.devcurve_shape_editor.get_layer_strengths())
        except Exception:
            layer_strengths = {}
    layer_nodes_map = {}
    if hasattr(tab, "devcurve_shape_editor") and hasattr(tab.devcurve_shape_editor, "get_layer_nodes_map"):
        try:
            layer_nodes_map = dict(tab.devcurve_shape_editor.get_layer_nodes_map())
        except Exception:
            layer_nodes_map = {}

    for src, defaults in _LAYER_DEFAULTS.items():
        payload[f"devcurve_layer_{src}_enabled"] = getattr(tab, f"devcurve_layer_{src}_enabled").isChecked()
        payload[f"devcurve_layer_{src}_alpha"] = getattr(tab, f"devcurve_layer_{src}_alpha").value() / 100.0
        payload[f"devcurve_layer_{src}_power"] = max(
            0.0,
            min(3.0, float(layer_strengths.get(src, defaults["power"] / 3.0)) * 3.0),
        )
        payload[f"devcurve_layer_{src}_offset"] = getattr(tab, f"devcurve_layer_{src}_offset").value() / 100.0
        order_widget = getattr(tab, f"devcurve_layer_{src}_order", None)
        if order_widget is not None and hasattr(order_widget, "value"):
            order_val = int(order_widget.value())
        else:
            order_val = int(getattr(tab, f"_devcurve_layer_{src}_order", defaults["order"]))
        payload[f"devcurve_layer_{src}_order"] = max(1, min(4, order_val))
        payload[f"devcurve_layer_{src}_color"] = _qcolor_to_list(
            getattr(tab, f"_devcurve_layer_{src}_color", None),
            defaults["color"],
        )
        layer_nodes = layer_nodes_map.get(src)
        payload[f"devcurve_layer_{src}_shape_nodes"] = (
            layer_nodes if isinstance(layer_nodes, list) and layer_nodes else list(_DEFAULT_SHAPE_NODES)
        )
    return payload


__all__ = ["load_devcurve_mode_settings", "collect_devcurve_mode_settings"]
