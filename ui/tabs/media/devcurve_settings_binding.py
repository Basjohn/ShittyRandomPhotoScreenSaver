"""Spline Curve settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Callable

from PySide6.QtGui import QColor

from ui.color_utils import qcolor_to_list as _qcolor_to_list

_LAYER_SOURCES = ("bass", "vocals", "mids", "transients")
_LAYER_FIELDS = (
    "color",
    "outline_color",
    "outline_width",
    "alpha",
    "power",
    "offset",
    "enabled",
    "order",
)


def _layer_defaults(tab, source: str) -> dict[str, Any]:
    """Project one DevCurve layer's baseline strictly from canonical defaults."""
    return {
        field: tab._widget_default(
            "spotify_visualizer", f"devcurve_layer_{source}_{field}"
        )
        for field in _LAYER_FIELDS
    }



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

    if hasattr(tab, "devcurve_base_level"):
        v = int(float(config.get("devcurve_base_level", tab._widget_default("spotify_visualizer", "devcurve_base_level"))) * 100.0)
        v = max(10, min(90, v))
        tab.devcurve_base_level.setValue(v)
        tab.devcurve_base_level_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_motion_power"):
        v = int(float(config.get("devcurve_motion_power", tab._widget_default("spotify_visualizer", "devcurve_motion_power"))) * 100.0)
        v = max(0, min(300, v))
        tab.devcurve_motion_power.setValue(v)
        tab.devcurve_motion_power_label.setText(f"{v / 100.0:.2f}x")
    if hasattr(tab, "devcurve_idle_motion"):
        v = int(float(config.get("devcurve_idle_motion", tab._widget_default("spotify_visualizer", "devcurve_idle_motion"))) * 100.0)
        v = max(0, min(150, v))
        tab.devcurve_idle_motion.setValue(v)
        tab.devcurve_idle_motion_label.setText(f"{v / 100.0:.2f}")
    if hasattr(tab, "devcurve_idle_speed"):
        v = int(float(config.get("devcurve_idle_speed", tab._widget_default("spotify_visualizer", "devcurve_idle_speed"))) * 100.0)
        v = max(5, min(200, v))
        tab.devcurve_idle_speed.setValue(v)
        tab.devcurve_idle_speed_label.setText(f"{v / 100.0:.2f}x")
    if hasattr(tab, "devcurve_smoothness"):
        v = int(float(config.get("devcurve_smoothness", tab._widget_default("spotify_visualizer", "devcurve_smoothness"))) * 100.0)
        v = max(0, min(100, v))
        tab.devcurve_smoothness.setValue(v)
        tab.devcurve_smoothness_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_shape_editor"):
        layer_nodes = {}
        for src in _LAYER_SOURCES:
            key = f"devcurve_layer_{src}_shape_nodes"
            raw = config.get(key, tab._widget_default("spotify_visualizer", key))
            if isinstance(raw, list) and raw:
                layer_nodes[src] = raw
        if hasattr(tab.devcurve_shape_editor, "set_layer_nodes_map"):
            tab.devcurve_shape_editor.set_layer_nodes_map(layer_nodes)
        if hasattr(tab.devcurve_shape_editor, "set_layer_strengths"):
            tab.devcurve_shape_editor.set_layer_strengths(
                {
                    src: _clamp01(float(config.get(f"devcurve_layer_{src}_power", defaults["power"])) / 3.0)
                    for src in _LAYER_SOURCES
                    for defaults in (_layer_defaults(tab, src),)
                }
            )
        if hasattr(tab.devcurve_shape_editor, "set_active_layer"):
            tab.devcurve_shape_editor.set_active_layer(
                str(config.get("devcurve_active_layer", tab._widget_default("spotify_visualizer", "devcurve_active_layer"))).strip().lower()
            )

    for src in _LAYER_SOURCES:
        defaults = _layer_defaults(tab, src)
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
        outline_width = int(float(config.get(f"devcurve_layer_{src}_outline_width", defaults["outline_width"])) * 1000.0)
        setattr(tab, f"_devcurve_layer_{src}_outline_width", max(1, min(20, outline_width)))
        outline_color_data = config.get(f"devcurve_layer_{src}_outline_color", defaults["outline_color"])
        try:
            oc = QColor(*outline_color_data)
        except Exception:
            oc = QColor(*defaults["outline_color"])
        oc.setAlpha(255)
        setattr(tab, f"_devcurve_layer_{src}_outline_color", oc)

    apply_active_ui = getattr(tab, "_devcurve_apply_active_layer_ui", None)
    if callable(apply_active_ui):
        apply_active_ui(str(config.get("devcurve_active_layer", tab._widget_default("spotify_visualizer", "devcurve_active_layer"))).strip().lower())
    normalize_layer_orders = getattr(tab, "_devcurve_normalize_layer_orders", None)
    if callable(normalize_layer_orders):
        normalize_layer_orders(save=False)

    if hasattr(tab, "devcurve_foreground_shadow_enabled"):
        tab.devcurve_foreground_shadow_enabled.setChecked(
            bool(config.get("devcurve_foreground_shadow_enabled", tab._widget_default("spotify_visualizer", "devcurve_foreground_shadow_enabled")))
        )
    if hasattr(tab, "devcurve_foreground_specular_enabled"):
        tab.devcurve_foreground_specular_enabled.setChecked(
            bool(config.get("devcurve_foreground_specular_enabled", tab._widget_default("spotify_visualizer", "devcurve_foreground_specular_enabled")))
        )
    if hasattr(tab, "devcurve_foreground_shadow_alpha"):
        v = int(float(config.get("devcurve_foreground_shadow_alpha", tab._widget_default("spotify_visualizer", "devcurve_foreground_shadow_alpha"))) * 100.0)
        v = max(0, min(100, v))
        tab.devcurve_foreground_shadow_alpha.setValue(v)
        tab.devcurve_foreground_shadow_alpha_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_foreground_shadow_darken"):
        v = int(float(config.get("devcurve_foreground_shadow_darken", tab._widget_default("spotify_visualizer", "devcurve_foreground_shadow_darken"))) * 100.0)
        v = max(0, min(100, v))
        tab.devcurve_foreground_shadow_darken.setValue(v)
        tab.devcurve_foreground_shadow_darken_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_foreground_shadow_offset"):
        v = int(float(config.get("devcurve_foreground_shadow_offset", tab._widget_default("spotify_visualizer", "devcurve_foreground_shadow_offset"))) * 100.0)
        v = max(0, min(45, v))
        tab.devcurve_foreground_shadow_offset.setValue(v)
        tab.devcurve_foreground_shadow_offset_label.setText(f"{v / 100.0:.2f}")
    if hasattr(tab, "devcurve_foreground_specular_alpha"):
        v = int(float(config.get("devcurve_foreground_specular_alpha", tab._widget_default("spotify_visualizer", "devcurve_foreground_specular_alpha"))) * 100.0)
        v = max(0, min(100, v))
        tab.devcurve_foreground_specular_alpha.setValue(v)
        tab.devcurve_foreground_specular_alpha_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_foreground_specular_width"):
        v = int(float(config.get("devcurve_foreground_specular_width", tab._widget_default("spotify_visualizer", "devcurve_foreground_specular_width"))) * 1000.0)
        v = max(2, min(120, v))
        tab.devcurve_foreground_specular_width.setValue(v)
        tab.devcurve_foreground_specular_width_label.setText(f"{v / 1000.0:.3f}")
    if hasattr(tab, "devcurve_foreground_specular_offset"):
        v = int(float(config.get("devcurve_foreground_specular_offset", tab._widget_default("spotify_visualizer", "devcurve_foreground_specular_offset"))) * 100.0)
        v = max(-20, min(20, v))
        tab.devcurve_foreground_specular_offset.setValue(v)
        tab.devcurve_foreground_specular_offset_label.setText(f"{v / 100.0:+.2f}")
    if hasattr(tab, "devcurve_foreground_specular_crest_bias"):
        v = int(float(config.get("devcurve_foreground_specular_crest_bias", tab._widget_default("spotify_visualizer", "devcurve_foreground_specular_crest_bias"))) * 100.0)
        v = max(0, min(200, v))
        tab.devcurve_foreground_specular_crest_bias.setValue(v)
        tab.devcurve_foreground_specular_crest_bias_label.setText(f"{v / 100.0:.2f}x")
    update_fx_visibility = getattr(tab, "_devcurve_update_foreground_fx_visibility", None)
    if callable(update_fx_visibility):
        update_fx_visibility()

    if hasattr(tab, "devcurve_ghost_enabled"):
        tab.devcurve_ghost_enabled.setChecked(bool(config.get("devcurve_ghosting_enabled", tab._widget_default("spotify_visualizer", "devcurve_ghosting_enabled"))))
    if hasattr(tab, "devcurve_ghost_opacity"):
        v = int(float(config.get("devcurve_ghost_alpha", tab._widget_default("spotify_visualizer", "devcurve_ghost_alpha"))) * 100.0)
        v = max(0, min(100, v))
        tab.devcurve_ghost_opacity.setValue(v)
        tab.devcurve_ghost_opacity_label.setText(f"{v}%")
    if hasattr(tab, "devcurve_ghost_decay"):
        v = int(float(config.get("devcurve_ghost_decay", tab._widget_default("spotify_visualizer", "devcurve_ghost_decay"))) * 100.0)
        v = max(10, min(100, v))
        tab.devcurve_ghost_decay.setValue(v)
        if hasattr(tab, "devcurve_ghost_decay_label"):
            tab.devcurve_ghost_decay_label.setText(f"{v / 100.0:.2f}x")


def collect_devcurve_mode_settings(tab) -> dict[str, Any]:
    """Collect DevCurve settings without introducing save-side shadow defaults."""
    d_bool = lambda key: tab._default_bool("spotify_visualizer", key)
    d_int = lambda key: tab._default_int("spotify_visualizer", key)
    d_float = lambda key: tab._default_float("spotify_visualizer", key)
    d_str = lambda key: tab._default_str("spotify_visualizer", key)
    d_value = lambda key: tab._widget_default("spotify_visualizer", key)
    pct = lambda key: int(round(d_float(key) * 100.0))
    milli = lambda key: int(round(d_float(key) * 1000.0))

    payload: dict[str, Any] = {
        "devcurve_base_level": (tab.devcurve_base_level.value() if hasattr(tab, "devcurve_base_level") else pct("devcurve_base_level")) / 100.0,
        "devcurve_motion_power": (tab.devcurve_motion_power.value() if hasattr(tab, "devcurve_motion_power") else pct("devcurve_motion_power")) / 100.0,
        "devcurve_idle_motion": (tab.devcurve_idle_motion.value() if hasattr(tab, "devcurve_idle_motion") else pct("devcurve_idle_motion")) / 100.0,
        "devcurve_idle_speed": (tab.devcurve_idle_speed.value() if hasattr(tab, "devcurve_idle_speed") else pct("devcurve_idle_speed")) / 100.0,
        "devcurve_smoothness": (tab.devcurve_smoothness.value() if hasattr(tab, "devcurve_smoothness") else pct("devcurve_smoothness")) / 100.0,
        "devcurve_active_layer": str(getattr(tab, "_devcurve_active_layer", d_str("devcurve_active_layer"))),
        "devcurve_ghosting_enabled": tab.devcurve_ghost_enabled.isChecked() if hasattr(tab, "devcurve_ghost_enabled") else d_bool("devcurve_ghosting_enabled"),
        "devcurve_ghost_alpha": (tab.devcurve_ghost_opacity.value() if hasattr(tab, "devcurve_ghost_opacity") else pct("devcurve_ghost_alpha")) / 100.0,
        "devcurve_ghost_decay": (tab.devcurve_ghost_decay.value() if hasattr(tab, "devcurve_ghost_decay") else pct("devcurve_ghost_decay")) / 100.0,
        "devcurve_foreground_shadow_enabled": (
            tab.devcurve_foreground_shadow_enabled.isChecked()
            if hasattr(tab, "devcurve_foreground_shadow_enabled")
            else d_bool("devcurve_foreground_shadow_enabled")
        ),
        "devcurve_foreground_shadow_alpha": (
            (tab.devcurve_foreground_shadow_alpha.value() if hasattr(tab, "devcurve_foreground_shadow_alpha") else pct("devcurve_foreground_shadow_alpha")) / 100.0
        ),
        "devcurve_foreground_shadow_darken": (
            (tab.devcurve_foreground_shadow_darken.value() if hasattr(tab, "devcurve_foreground_shadow_darken") else pct("devcurve_foreground_shadow_darken")) / 100.0
        ),
        "devcurve_foreground_shadow_offset": (
            (tab.devcurve_foreground_shadow_offset.value() if hasattr(tab, "devcurve_foreground_shadow_offset") else pct("devcurve_foreground_shadow_offset")) / 100.0
        ),
        "devcurve_foreground_specular_enabled": (
            tab.devcurve_foreground_specular_enabled.isChecked()
            if hasattr(tab, "devcurve_foreground_specular_enabled")
            else d_bool("devcurve_foreground_specular_enabled")
        ),
        "devcurve_foreground_specular_alpha": (
            (tab.devcurve_foreground_specular_alpha.value() if hasattr(tab, "devcurve_foreground_specular_alpha") else pct("devcurve_foreground_specular_alpha")) / 100.0
        ),
        "devcurve_foreground_specular_width": (
            (tab.devcurve_foreground_specular_width.value() if hasattr(tab, "devcurve_foreground_specular_width") else milli("devcurve_foreground_specular_width")) / 1000.0
        ),
        "devcurve_foreground_specular_offset": (
            (tab.devcurve_foreground_specular_offset.value() if hasattr(tab, "devcurve_foreground_specular_offset") else pct("devcurve_foreground_specular_offset")) / 100.0
        ),
        "devcurve_foreground_specular_crest_bias": (
            (tab.devcurve_foreground_specular_crest_bias.value() if hasattr(tab, "devcurve_foreground_specular_crest_bias") else pct("devcurve_foreground_specular_crest_bias")) / 100.0
        ),
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

    for src in _LAYER_SOURCES:
        defaults = _layer_defaults(tab, src)
        payload[f"devcurve_layer_{src}_enabled"] = (
            getattr(tab, f"devcurve_layer_{src}_enabled").isChecked()
            if hasattr(tab, f"devcurve_layer_{src}_enabled")
            else bool(defaults["enabled"])
        )
        payload[f"devcurve_layer_{src}_alpha"] = (
            getattr(tab, f"devcurve_layer_{src}_alpha").value() / 100.0
            if hasattr(tab, f"devcurve_layer_{src}_alpha")
            else float(defaults["alpha"])
        )
        payload[f"devcurve_layer_{src}_power"] = max(
            0.0,
            min(3.0, float(layer_strengths.get(src, float(defaults["power"]) / 3.0)) * 3.0),
        )
        payload[f"devcurve_layer_{src}_offset"] = (
            getattr(tab, f"devcurve_layer_{src}_offset").value() / 100.0
            if hasattr(tab, f"devcurve_layer_{src}_offset")
            else float(defaults["offset"])
        )
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
        outline_color = getattr(tab, f"_devcurve_layer_{src}_outline_color", None)
        outline_color_list = _qcolor_to_list(outline_color, defaults["outline_color"])
        if len(outline_color_list) < 4:
            outline_color_list = list(outline_color_list) + [255]
        outline_color_list[3] = 255
        payload[f"devcurve_layer_{src}_outline_color"] = outline_color_list
        payload[f"devcurve_layer_{src}_outline_width"] = max(
            0.001,
            min(0.020, float(getattr(tab, f"_devcurve_layer_{src}_outline_width", int(float(defaults["outline_width"]) * 1000))) / 1000.0),
        )
        layer_nodes = layer_nodes_map.get(src)
        canonical_nodes = d_value(f"devcurve_layer_{src}_shape_nodes")
        payload[f"devcurve_layer_{src}_shape_nodes"] = (
            layer_nodes if isinstance(layer_nodes, list) and layer_nodes else canonical_nodes
        )
    return payload


__all__ = ["load_devcurve_mode_settings", "collect_devcurve_mode_settings"]

