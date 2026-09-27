"""In-memory projections of the canonical defaults (no files are generated).

``core.settings.defaults.get_default_settings()`` is the product-default
authority. These helpers project it on demand (sanitised defaults, SST
transport shape) for tooling, exports and tests. Nothing is written to disk:
checked-in derived copies were retired on 2026-09-27 because nothing at runtime
read them and every default change had to regenerate them.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Mapping

from core.settings.default_contract import MC_PROFILE, NORMAL_PROFILE
from core.settings.defaults import get_default_settings
from core.settings.structured_roots import STRUCTURED_SETTINGS_ROOTS
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping


_SST_PROFILES = (NORMAL_PROFILE, MC_PROFILE)
_SST_SETTINGS_VERSION = 2
_SST_SNAPSHOT_VERSION = 1
_SST_DEFAULTS_METADATA = {
    "artifact_kind": "canonical_defaults",
    "source": "core.settings.defaults_snapshot_builder.build_sst_defaults_snapshot",
}


def build_defaults_snapshot(application: str | None = None) -> Dict[str, Any]:
    """Return the sanitized canonical snapshot for the selected profile."""
    defaults = deepcopy(get_default_settings(application))

    sources = defaults.get("sources")
    if not isinstance(sources, dict):
        raise TypeError("Canonical defaults are missing the sources mapping")
    sources["folders"] = []
    sources["rss_feeds"] = []

    widgets = defaults.get("widgets")
    if not isinstance(widgets, dict):
        raise TypeError("Canonical defaults are missing the widgets mapping")

    weather = widgets.get("weather")
    if not isinstance(weather, dict):
        raise TypeError("Canonical defaults are missing widgets.weather")
    weather["location"] = ""
    weather.pop("latitude", None)
    weather.pop("longitude", None)

    visualizer = widgets.get("spotify_visualizer")
    if not isinstance(visualizer, Mapping):
        raise TypeError("Canonical defaults are missing widgets.spotify_visualizer")
    widgets["spotify_visualizer"] = normalize_visualizer_section_mapping(
        visualizer,
        prefix="widgets.spotify_visualizer",
        apply_preset_overlay=False,
        resolve_preset_indices=False,
    )

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
                flattened[dotted] = deepcopy(value)
        return flattened

    for section, value in defaults.items():
        if section in STRUCTURED_SETTINGS_ROOTS:
            snapshot[section] = deepcopy(value)
        elif isinstance(value, Mapping):
            flattened = flatten_section(value)
            if flattened:
                snapshot[section] = flattened
        else:
            snapshot[section] = deepcopy(value)

    return snapshot


def build_sst_defaults_document(application: str) -> Dict[str, Any]:
    """Return one deterministic SST defaults document for a profile.

    Transport metadata plus the canonical projection above, built on demand;
    the metadata is not product-default authority.
    """
    profile = str(application)
    if profile not in _SST_PROFILES:
        raise ValueError(f"Unsupported SST defaults profile: {application!r}")
    return {
        "application": profile,
        "metadata": dict(_SST_DEFAULTS_METADATA),
        "profile": profile,
        "settings_version": _SST_SETTINGS_VERSION,
        "snapshot": build_sst_defaults_snapshot(profile),
        "snapshot_version": _SST_SNAPSHOT_VERSION,
    }
