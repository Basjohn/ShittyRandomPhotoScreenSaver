"""Spline Curve settings load/save binding helpers."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSignalBlocker
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


def load_devcurve_mode_settings(tab, config) -> None:
    from ui.tabs.media.spec_mode_builder import load_spec_mode_settings

    load_spec_mode_settings(tab, "devcurve", config)


def collect_devcurve_mode_settings(tab) -> dict[str, Any]:
    from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings

    return collect_spec_mode_settings(tab, "devcurve")


def load_devcurve_layers(tab, config) -> None:
    # The Custom entry obeys the same silent-load boundary as spec-built controls.
    blockers = [QSignalBlocker(tab.devcurve_shape_editor)]
    blockers.extend(
        QSignalBlocker(getattr(tab, f"devcurve_layer_{source}_{field}"))
        for source in _LAYER_SOURCES
        for field in ("enabled", "alpha", "offset")
    )
    try:
        _load_devcurve_layers(tab, config)
    finally:
        del blockers


def _load_devcurve_layers(tab, config) -> None:
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



def collect_devcurve_layers(tab) -> dict[str, Any]:
    payload = {"devcurve_active_layer": str(getattr(tab, "_devcurve_active_layer", tab._default_str("spotify_visualizer", "devcurve_active_layer")))}
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
        canonical_nodes = tab._widget_default("spotify_visualizer", f"devcurve_layer_{src}_shape_nodes")
        payload[f"devcurve_layer_{src}_shape_nodes"] = (
            layer_nodes if isinstance(layer_nodes, list) and layer_nodes else canonical_nodes
        )
    return payload


__all__ = ["load_devcurve_mode_settings", "collect_devcurve_mode_settings", "load_devcurve_layers", "collect_devcurve_layers"]
