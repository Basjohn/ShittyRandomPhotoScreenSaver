"""Spectrum visualizer settings load/save binding helpers."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from PySide6.QtCore import QSignalBlocker

from core.settings.visualizer_mode_settings import read_control_value, require_mode_settings
from ui.tabs.media.spec_mode_builder import collect_spec_mode_settings, load_spec_mode_settings


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


def load_spectrum_mode_settings(tab, config) -> None:
    load_spec_mode_settings(tab, "spectrum", config)


def collect_spectrum_mode_settings(tab) -> dict[str, Any]:
    return collect_spec_mode_settings(tab, "spectrum")


def load_spectrum_render_mode(tab, config) -> None:
    key = "spectrum_render_mode"
    default = tab._widget_default("spotify_visualizer", key)
    control = require_mode_settings("spectrum").control(key)
    value = control.admit(read_control_value(control, config.get, default), default)
    tab._set_spectrum_render_mode(value, save=False)


def collect_spectrum_render_mode(tab) -> dict:
    return {"spectrum_render_mode": tab._spectrum_render_mode}


def load_spectrum_shape(tab, config) -> None:
    blockers = [QSignalBlocker(tab.spectrum_mirrored), QSignalBlocker(tab.spectrum_shape_editor)]
    _load_spectrum_shape(tab, config)
    del blockers


def _load_spectrum_shape(tab, config) -> None:
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


def collect_spectrum_shape(tab) -> dict:
    editor = tab.spectrum_shape_editor
    return {
        "spectrum_mirrored": tab.spectrum_mirrored.isChecked(),
        "spectrum_shape_nodes": editor.get_nodes(),
        "spectrum_notch_positions_mirrored": list(editor._notches_mirrored),
        "spectrum_notch_positions_linear": list(editor._notches_linear),
        "spectrum_lane_strengths_mirrored": editor.get_lane_strengths(mirrored=True),
        "spectrum_lane_strengths_linear": editor.get_lane_strengths(mirrored=False),
    }


def load_spectrum_smoothing(tab, config) -> None:
    enabled = tab.spectrum_visual_smoothing_enabled
    strength = tab.spectrum_visual_smoothing
    blockers = [QSignalBlocker(enabled), QSignalBlocker(strength)]
    enabled.setChecked(tab._config_bool("spotify_visualizer", config, "spectrum_visual_smoothing_enabled"))
    strength.setValue(max(0, min(100, int(tab._config_float("spotify_visualizer", config, "spectrum_visual_smoothing") * 100))))
    tab.spectrum_visual_smoothing_label.setText(f"{strength.value()}%")
    strength.parentWidget().setVisible(enabled.isChecked())
    del blockers


def collect_spectrum_smoothing(tab) -> dict:
    return {"spectrum_visual_smoothing_enabled": tab.spectrum_visual_smoothing_enabled.isChecked(),
            "spectrum_visual_smoothing": tab.spectrum_visual_smoothing.value() / 100.0}
