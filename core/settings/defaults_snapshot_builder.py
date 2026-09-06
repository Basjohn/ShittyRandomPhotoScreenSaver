"""Helpers for derived defaults snapshot artifacts.

`core.settings.defaults.get_default_settings()` is the public source-of-truth
entrypoint for tuned production defaults. Snapshot artifacts are derived
outputs with doc/export-friendly sanitation applied so they do not drift into a
parallel settings universe.
"""
from __future__ import annotations

from copy import deepcopy
import argparse
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from core.settings.defaults import get_default_settings
from core.settings.structured_roots import STRUCTURED_SETTINGS_ROOTS
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping


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


def serialize_defaults_snapshot() -> str:
    """Return the deterministic on-disk representation of the Normal snapshot."""

    return json.dumps(build_defaults_snapshot(), indent=2, sort_keys=True) + "\n"


def write_defaults_snapshot(path: str | Path | None = None) -> Path:
    """Regenerate the derived Normal-profile snapshot from canonical defaults."""

    target = Path(path) if path is not None else Path(__file__).with_name("defaults_snapshot.json")
    target.write_text(serialize_defaults_snapshot(), encoding="utf-8")
    return target


def defaults_snapshot_matches(path: str | Path | None = None) -> bool:
    """Return whether the stored snapshot exactly matches its canonical derivative."""

    target = Path(path) if path is not None else Path(__file__).with_name("defaults_snapshot.json")
    try:
        current = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return current == serialize_defaults_snapshot()


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify or regenerate the derived SRPSS defaults snapshot."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--check",
        action="store_true",
        help="verify the stored snapshot (default)",
    )
    action.add_argument(
        "--write",
        action="store_true",
        help="regenerate the stored snapshot from canonical defaults",
    )
    args = parser.parse_args(argv)

    if args.write:
        target = write_defaults_snapshot()
        print(f"wrote {target}")
        return 0

    target = Path(__file__).with_name("defaults_snapshot.json")
    if defaults_snapshot_matches(target):
        print(f"defaults snapshot OK: {target}")
        return 0
    print(f"defaults snapshot STALE: {target}")
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
