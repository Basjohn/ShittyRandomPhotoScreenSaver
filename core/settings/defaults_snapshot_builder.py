"""Helpers for deterministic derived-default artifacts.

``core.settings.defaults.get_default_settings()`` is the product-default authority.
The JSON snapshot and checked-in SST default documents are derived projections;
they must never become a second settings universe or be hand-edited.
"""
from __future__ import annotations

from copy import deepcopy
import argparse
import json
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence

from core.settings.default_contract import MC_PROFILE, NORMAL_PROFILE
from core.settings.defaults import get_default_settings
from core.settings.structured_roots import STRUCTURED_SETTINGS_ROOTS
from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping


_SST_DOC_FILENAMES = {
    NORMAL_PROFILE: "SRPSS_Settings_Screensaver.sst",
    MC_PROFILE: "SRPSS_Settings_Screensaver_MC.sst",
}
_SST_SETTINGS_VERSION = 2
_SST_SNAPSHOT_VERSION = 1
_SST_ARTIFACT_METADATA = {
    "artifact_kind": "canonical_defaults",
    "generator": "python -m core.settings.defaults_snapshot_builder --write-sst-docs",
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
    """Return one deterministic checked-in SST defaults document.

    This is transport metadata plus the canonical projection above.  The
    metadata describes the generator; it is not product-default authority.
    """
    profile = str(application)
    if profile not in _SST_DOC_FILENAMES:
        raise ValueError(f"Unsupported checked-in SST profile: {application!r}")
    return {
        "application": profile,
        "metadata": dict(_SST_ARTIFACT_METADATA),
        "profile": profile,
        "settings_version": _SST_SETTINGS_VERSION,
        "snapshot": build_sst_defaults_snapshot(profile),
        "snapshot_version": _SST_SNAPSHOT_VERSION,
    }


def serialize_defaults_snapshot() -> str:
    """Return the deterministic on-disk representation of the Normal snapshot."""
    return json.dumps(build_defaults_snapshot(), indent=2, sort_keys=True) + "\n"


def serialize_sst_defaults_document(application: str) -> str:
    """Return deterministic JSON for one checked-in SST defaults artifact."""
    return json.dumps(
        build_sst_defaults_document(application),
        indent=2,
        sort_keys=True,
    ) + "\n"


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


def _docs_directory(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else Path(__file__).resolve().parents[2] / "Docs"


def write_sst_defaults_documents(docs_directory: str | Path | None = None) -> tuple[Path, ...]:
    """Regenerate both checked-in SST defaults documents from canonical source."""
    root = _docs_directory(docs_directory)
    root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for profile, filename in _SST_DOC_FILENAMES.items():
        target = root / filename
        target.write_text(serialize_sst_defaults_document(profile), encoding="utf-8")
        written.append(target)
    return tuple(written)


def sst_defaults_documents_match(docs_directory: str | Path | None = None) -> bool:
    """Return whether both checked-in SST artifacts exactly match canonical source."""
    root = _docs_directory(docs_directory)
    for profile, filename in _SST_DOC_FILENAMES.items():
        target = root / filename
        try:
            current = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            return False
        if current != serialize_sst_defaults_document(profile):
            return False
    return True


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify or regenerate SRPSS derived defaults artifacts."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--check",
        action="store_true",
        help="verify the stored Normal JSON snapshot (default)",
    )
    action.add_argument(
        "--write",
        action="store_true",
        help="regenerate the stored Normal JSON snapshot",
    )
    action.add_argument(
        "--check-sst-docs",
        action="store_true",
        help="verify both checked-in SST defaults documents",
    )
    action.add_argument(
        "--write-sst-docs",
        action="store_true",
        help="regenerate both checked-in SST defaults documents",
    )
    action.add_argument(
        "--check-all",
        action="store_true",
        help="verify the JSON snapshot and both SST defaults documents",
    )
    action.add_argument(
        "--write-all",
        action="store_true",
        help="regenerate the JSON snapshot and both SST defaults documents",
    )
    args = parser.parse_args(argv)

    if args.write or args.write_all:
        target = write_defaults_snapshot()
        print(f"wrote {target}")
        if args.write and not args.write_all:
            return 0

    if args.write_sst_docs or args.write_all:
        for target in write_sst_defaults_documents():
            print(f"wrote {target}")
        return 0

    if args.check_sst_docs:
        if sst_defaults_documents_match():
            print("SST defaults documents OK")
            return 0
        print("SST defaults documents STALE")
        return 1

    if args.check_all:
        snapshot_ok = defaults_snapshot_matches()
        sst_ok = sst_defaults_documents_match()
        print("defaults snapshot OK" if snapshot_ok else "defaults snapshot STALE")
        print("SST defaults documents OK" if sst_ok else "SST defaults documents STALE")
        return 0 if snapshot_ok and sst_ok else 1

    target = Path(__file__).with_name("defaults_snapshot.json")
    if defaults_snapshot_matches(target):
        print(f"defaults snapshot OK: {target}")
        return 0
    print(f"defaults snapshot STALE: {target}")
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
