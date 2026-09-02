"""Helpers for derived defaults snapshot artifacts.

`core.settings.defaults.get_default_settings()` is the public source-of-truth
entrypoint for tuned production defaults. Snapshot artifacts are derived
outputs with doc/export-friendly sanitation applied so they do not drift into a
parallel settings universe.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from core.settings.defaults import get_default_settings
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

_PRESERVED_DOC_KEYS = (
    "sources.folders",
    "sources.rss_feeds",
    "widgets.weather.location",
    "widgets.weather.latitude",
    "widgets.weather.longitude",
)


def build_defaults_snapshot(application: str | None = None) -> Dict[str, Any]:
    """Return the sanitized canonical snapshot for the selected profile."""
    defaults = deepcopy(get_default_settings(application))
    defaults.pop("preset", None)
    defaults.pop("custom_preset_backup", None)

    sources = defaults.setdefault("sources", {})
    if isinstance(sources, dict):
        sources["folders"] = []
        sources["rss_feeds"] = []

    widgets = defaults.setdefault("widgets", {})
    if isinstance(widgets, dict):
        weather = widgets.setdefault("weather", {})
        if isinstance(weather, dict):
            weather["location"] = ""
            weather.pop("latitude", None)
            weather.pop("longitude", None)

        visualizer = widgets.get("spotify_visualizer")
        if isinstance(visualizer, Mapping):
            widgets["spotify_visualizer"] = normalize_visualizer_section_mapping(
                visualizer,
                prefix="widgets.spotify_visualizer",
                apply_preset_overlay=False,
                resolve_preset_indices=False,
            )

    mc = defaults.get("mc")
    if isinstance(mc, dict):
        mc.clear()

    workers = defaults.setdefault("workers", {})
    if isinstance(workers, dict):
        fft = workers.setdefault("fft", {})
        if isinstance(fft, dict):
            fft["enabled"] = False

    return defaults


def build_sst_defaults_snapshot(application: str | None = None) -> Dict[str, Any]:
    """Project canonical defaults into SettingsManager's SST transport shape."""
    defaults = build_defaults_snapshot(application)
    snapshot: Dict[str, Any] = {}

    def flatten_section(mapping: Mapping[str, Any], prefix: str = "") -> Dict[str, Any]:
        flattened: Dict[str, Any] = {}
        for key, value in mapping.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, Mapping):
                flattened.update(flatten_section(value, dotted))
            else:
                # Later dotted compatibility leaves intentionally override an
                # earlier nested form, matching reset_to_defaults().
                flattened[dotted] = deepcopy(value)
        return flattened

    for section, value in defaults.items():
        if section in {"widgets", "transitions", "visualizer_custom_presets", "widget_theme"}:
            snapshot[section] = deepcopy(value)
        elif isinstance(value, Mapping):
            flattened = flatten_section(value)
            if flattened:
                snapshot[section] = flattened
        else:
            snapshot[section] = deepcopy(value)

    return snapshot
