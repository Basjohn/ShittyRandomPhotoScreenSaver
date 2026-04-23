"""
Canonical default settings for SRPSS.

These defaults are based on the recommended configuration and should be used
by reset_to_defaults(). Settings that are user-specific (sources, geo data)
are intentionally excluded and will be preserved during reset.

NOTE: Values here are *tuned production defaults* — they may differ from the
conservative dataclass defaults in ``core/settings/models.py``.  The models
serve as fallbacks when a key is missing from the JSON store; the values here
are what a fresh install or "Reset to Defaults" should produce.  When adding
a new setting, ensure both files are updated.

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
from .visualizer_settings_snapshot import normalize_visualizer_section_mapping

# Keys to preserve during reset (user-specific data)
PRESERVE_ON_RESET = frozenset({
    'sources.folders',
    'sources.rss_feeds',
    'widgets.weather.location',
    'widgets.weather.latitude',
    'widgets.weather.longitude',
})
CANONICAL_DEFAULTS = deepcopy(DEFAULT_SETTINGS)
CANONICAL_DEFAULTS.pop("preset", None)
CANONICAL_DEFAULTS.pop("custom_preset_backup", None)


def get_default_settings() -> Dict[str, Any]:
    """Return the canonical default settings dictionary."""
    defaults = deepcopy(CANONICAL_DEFAULTS)

    widgets = defaults.get("widgets")
    if isinstance(widgets, Mapping):
        visualizer = widgets.get("spotify_visualizer")
        if isinstance(visualizer, Mapping):
            seeded_visualizer = dict(visualizer)
            seeded_visualizer.setdefault("enabled", True)
            seeded_visualizer.setdefault("monitor", "ALL")
            widgets["spotify_visualizer"] = normalize_visualizer_section_mapping(
                seeded_visualizer,
                prefix="widgets.spotify_visualizer",
                apply_preset_overlay=False,
                resolve_preset_indices=False,
            )

    return defaults


def get_flat_defaults() -> Dict[str, Any]:
    """Return defaults in flat key format (e.g., 'display.mode').

    This is useful for QSettings which uses dot-notation keys.
    """
    nested = get_default_settings()
    flat: Dict[str, Any] = {}

    def flatten(d: Dict[str, Any], prefix: str = '') -> None:
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict) and not _is_leaf_dict(k, v):
                flatten(v, key)
            else:
                flat[key] = v

    def _is_leaf_dict(key: str, value: dict) -> bool:
        """Check if a dict should be stored as-is (leaf) vs flattened."""
        # These are stored as complete dicts, not flattened
        leaf_keys = {'transitions', 'widgets', 'display', 'input', 'queue', 'sources', 'timing'}
        return key in leaf_keys

    # For our structure, we store top-level sections as complete dicts
    for section, value in nested.items():
        flat[section] = value

    return flat
