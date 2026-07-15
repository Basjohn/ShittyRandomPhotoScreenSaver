"""Regenerate deterministic SST artifacts from canonical profile defaults.

Generated defaults are documentation/distribution artifacts, not runtime
settings exports. They therefore bypass SettingsManager, legacy QSettings
migration, and installed profile storage entirely.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.settings.defaults_snapshot_builder import build_sst_defaults_snapshot
from core.settings.sst_io import SNAPSHOT_VERSION
from core.steam.credentials import STEAM_SECRET_FIELD_NAMES

DOCS_DIR = REPO_ROOT / "Docs"
EXPORT_TARGETS: Tuple[Tuple[str, str], ...] = (
    ("Screensaver", "SRPSS_Settings_Screensaver.sst"),
    ("Screensaver_MC", "SRPSS_Settings_Screensaver_MC.sst"),
)
GENERATED_METADATA = {
    "artifact_kind": "canonical_defaults",
    "generator": "tools/regenerate_sst_defaults.py",
    "source": "core.settings.defaults_snapshot_builder.build_sst_defaults_snapshot",
}
_PRIVATE_KEY_SEGMENTS = STEAM_SECRET_FIELD_NAMES | frozenset({
    "client_secret",
    "password",
})


def _walk_private_paths(value: Any, prefix: str = "") -> tuple[str, ...]:
    matches: list[str] = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            key_text = str(key)
            path = f"{prefix}.{key_text}" if prefix else key_text
            if key_text.casefold() in _PRIVATE_KEY_SEGMENTS:
                matches.append(path)
            matches.extend(_walk_private_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(_walk_private_paths(child, f"{prefix}[{index}]"))
    return tuple(matches)


def _build_payload(application: str) -> dict[str, Any]:
    snapshot = build_sst_defaults_snapshot(application)
    private_paths = _walk_private_paths(snapshot)
    if private_paths:
        raise ValueError(
            "Canonical defaults contain private credential fields: "
            + ", ".join(private_paths)
        )
    return {
        "settings_version": 2,
        "application": application,
        "profile": application,
        "snapshot_version": SNAPSHOT_VERSION,
        "metadata": dict(GENERATED_METADATA),
        "snapshot": snapshot,
    }


def _validate_payload(payload: Mapping[str, Any], application: str) -> None:
    if payload.get("application") != application or payload.get("profile") != application:
        raise ValueError(f"Generated SST profile mismatch for {application}")
    if payload.get("metadata") != GENERATED_METADATA:
        raise ValueError(f"Generated SST metadata is not deterministic for {application}")
    expected = build_sst_defaults_snapshot(application)
    if payload.get("snapshot") != expected:
        raise ValueError(f"Generated SST snapshot drifted from canonical {application} defaults")
    private_paths = _walk_private_paths(payload.get("snapshot"))
    if private_paths:
        raise ValueError(
            "Generated SST contains private credential fields: "
            + ", ".join(private_paths)
        )


def _write_payload_atomic(output_path: Path, payload: Mapping[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
            newline="\n",
        ) as handle:
            handle.write(serialized)
            temporary_path = Path(handle.name)
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _export_snapshot(
    application: str,
    output_path: Path,
) -> None:
    payload = _build_payload(application)
    _validate_payload(payload, application)
    _write_payload_atomic(output_path, payload)


def regenerate_sst_defaults(
    docs_dir: Path,
) -> tuple[Path, ...]:
    """Write both canonical profiles without opening runtime settings storage."""

    outputs: list[Path] = []
    for app_name, filename in EXPORT_TARGETS:
        output_file = docs_dir / filename
        _export_snapshot(
            app_name,
            output_file,
        )
        outputs.append(output_file)
    return tuple(outputs)


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Regenerate canonical SST snapshots from defaults")
    parser.add_argument(
        "--docs-dir",
        default=str(DOCS_DIR),
        help="Directory where SST files should be written (default: repo Docs folder)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    docs_dir = Path(args.docs_dir)
    outputs = regenerate_sst_defaults(docs_dir)
    for (app_name, _filename), output_file in zip(EXPORT_TARGETS, outputs):
        print(f"[DOCS] Exported {app_name} defaults to {output_file}")


if __name__ == "__main__":
    main()
