"""Bespoke persistence hooks for Sphere's spec-built Settings body."""
from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import QSignalBlocker
from PySide6.QtGui import QColor

from core.settings.visualizer_mode_settings import require_mode_settings
from ui.color_utils import qcolor_to_list
from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings


def load_sphere_mode_settings(tab, config) -> None:
    load_spec_mode_settings(tab, "sphere", config)


def collect_sphere_mode_settings(tab) -> dict:
    return collect_spec_mode_settings(tab, "sphere")


def load_sphere_analysis(tab, config) -> None:
    key = "sphere_analysis_notch_positions"
    notches = deepcopy(config.get(key, tab._widget_default("spotify_visualizer", key)))
    tab._sphere_analysis_notch_positions = notches
    for name, index in (("bass", 1), ("high", 2)):
        control = getattr(tab, f"sphere_analysis_{name}_boundary")
        blocker = QSignalBlocker(control)
        control.setValue(round(notches[index][0] * 1000))
        control._sphere_refresh_label()
        del blocker


def collect_sphere_analysis(tab) -> dict:
    return {"sphere_analysis_notch_positions": deepcopy(tab._sphere_analysis_notch_positions)}


def load_sphere_finish(tab, config) -> None:
    key = "sphere_finish"
    default = tab._widget_default("spotify_visualizer", key)
    value = require_mode_settings("sphere").control(key).admit(config.get(key, default), default)
    blocker = QSignalBlocker(tab.sphere_finish)
    tab.sphere_finish.setCurrentText(value)
    del blocker


def collect_sphere_finish(tab) -> dict:
    return {"sphere_finish": tab.sphere_finish.currentText()}


def _load_colour(tab, config, channel) -> None:
    key = f"sphere_{channel}_color"
    default = tab._widget_default("spotify_visualizer", key)
    value = require_mode_settings("sphere").control(key).admit(config.get(key, default), default)
    color = QColor(*value)
    setattr(tab, f"_{key}", color)
    button = getattr(tab, f"{key}_btn")
    alpha = getattr(tab, f"sphere_{channel}_alpha")
    blockers = [QSignalBlocker(button), QSignalBlocker(alpha)]
    button.set_color(color)
    alpha.setValue(color.alpha())
    alpha._sphere_refresh_label()
    del blockers
    if channel == "tracer":
        tab._sphere_apply_tracer_dependency()


def _collect_colour(tab, channel) -> dict:
    key = f"sphere_{channel}_color"
    return {key: qcolor_to_list(getattr(tab, f"_{key}"), tab._widget_default("spotify_visualizer", key))}


def load_sphere_fill_colour(tab, config) -> None:
    _load_colour(tab, config, "fill")


def collect_sphere_fill_colour(tab) -> dict:
    return _collect_colour(tab, "fill")


def load_sphere_edge_colour(tab, config) -> None:
    _load_colour(tab, config, "edge")


def collect_sphere_edge_colour(tab) -> dict:
    return _collect_colour(tab, "edge")


def load_sphere_tracer_colour(tab, config) -> None:
    _load_colour(tab, config, "tracer")


def collect_sphere_tracer_colour(tab) -> dict:
    return _collect_colour(tab, "tracer")
