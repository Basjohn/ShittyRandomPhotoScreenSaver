"""
Canonical default settings for SRPSS.

These defaults are based on the recommended configuration and should be used
by reset_to_defaults(). Settings that are user-specific (sources, geo data)
are intentionally excluded and will be preserved during reset.

NOTE: Values here are *tuned production defaults*. Every persisted product
setting has one canonical value here. Runtime readers and typed settings models
project from this authority; call-site literals cannot override a missing
canonical product value. Fresh install, partial-profile repair and "Reset to
Defaults" therefore resolve identically.

Excluded from reset:
- sources.folders (user's image folders)
- sources.rss_feeds (user's RSS feeds)
- widgets.weather.location (auto-detected or user-set)
- widgets.weather.latitude (auto-detected)
- widgets.weather.longitude (auto-detected)
"""
from typing import Dict, Any, Mapping
from copy import deepcopy

from .default_settings import DEFAULT_SETTINGS
from .default_profile_overrides import PROFILE_DEFAULT_OVERRIDES
from .default_contract import (
    MC_PROFILE,
    NORMAL_PROFILE,
    get_canonical_default,
    get_raw_default_settings,
    merge_default_overrides,
    require_canonical_default,
)
from .visualizer_settings_snapshot import normalize_visualizer_section_mapping
from .structured_roots import STRUCTURED_SETTINGS_ROOTS

# Keys to preserve during reset (user-specific data)
PRESERVE_ON_RESET = frozenset({
    'sources.folders',
    'sources.rss_feeds',
    'widgets.weather.location',
    'widgets.weather.latitude',
    'widgets.weather.longitude',
    # Custom visualizer snapshots are user-authored state, never product defaults.
    'visualizer_custom_presets',
})
def get_base_default_settings() -> Dict[str, Any]:
    """Return the authoritative Normal-profile defaults."""

    return deepcopy(DEFAULT_SETTINGS)


def get_profile_default_overrides() -> Dict[str, Dict[str, Any]]:
    """Return a safe copy of the editable profile override data."""

    return deepcopy(PROFILE_DEFAULT_OVERRIDES)


def get_default_settings(application: str | None = None) -> Dict[str, Any]:
    """Return canonical defaults resolved for Normal or MC profile behavior."""

    defaults = get_raw_default_settings(application)

    widgets = defaults.get("widgets")
    if isinstance(widgets, Mapping):
        visualizer = widgets.get("spotify_visualizer")
        if isinstance(visualizer, Mapping):
            widgets["spotify_visualizer"] = normalize_visualizer_section_mapping(
                dict(visualizer),
                prefix="widgets.spotify_visualizer",
                apply_preset_overlay=False,
                resolve_preset_indices=False,
            )

    return defaults


CANONICAL_DEFAULTS = get_default_settings(NORMAL_PROFILE)


def get_flat_defaults(application: str | None = None) -> Dict[str, Any]:
    """Return defaults in the runtime store's key shape.

    Declared structured roots remain complete mappings. Other mapping roots are
    flattened to dotted leaf keys, matching :class:`JsonSettingsStore` rather
    than maintaining a second hand-written list of special sections.
    """
    nested = get_default_settings(application)
    flat: Dict[str, Any] = {}

    def flatten_mapping(mapping: Mapping[str, Any], prefix: str) -> None:
        for key, value in mapping.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, Mapping):
                flatten_mapping(value, dotted)
            else:
                flat[dotted] = deepcopy(value)

    for section, value in nested.items():
        if section in STRUCTURED_SETTINGS_ROOTS:
            flat[section] = deepcopy(value)
        elif isinstance(value, Mapping):
            flatten_mapping(value, section)
        else:
            flat[section] = deepcopy(value)

    return flat
