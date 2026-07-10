"""Utility to regenerate canonical SST snapshots from default settings.

This script instantiates SettingsManager against a temporary filesystem root,
so reset/save/export work can never touch an installed Normal or MC profile.
It resets to the current canonical defaults, removes user-preserved fields,
and exports the snapshots into Docs/.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path
from typing import Iterable, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.settings.settings_manager import SettingsManager

DOCS_DIR = REPO_ROOT / "Docs"
EXPORT_TARGETS: Tuple[Tuple[str, str], ...] = (
    ("Screensaver", "SRPSS_Settings_Screensaver.sst"),
    ("Screensaver_MC", "SRPSS_Settings_Screensaver_MC.sst"),
)


def _apply_doc_overrides(manager: SettingsManager) -> None:
    """Normalize user-preserved keys to doc-friendly defaults."""
    manager.set('sources.folders', [])
    manager.set('sources.rss_feeds', [])
    manager.set('widgets.weather.location', '')
    manager.set('widgets.weather.latitude', '')
    manager.set('widgets.weather.longitude', '')


def _export_snapshot(
    application: str,
    output_path: Path,
    *,
    organization: str,
    storage_base_dir: Path,
) -> None:
    manager = SettingsManager(
        organization=organization,
        application=application,
        storage_base_dir=storage_base_dir,
    )
    manager.reset_to_defaults()
    _apply_doc_overrides(manager)
    manager.save()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not manager.export_to_sst(str(output_path)):
        raise RuntimeError(f"Failed to export SST for {application} to {output_path}")


def regenerate_sst_defaults(
    docs_dir: Path,
    *,
    organization: str = "SRPSS_DocSnapshot",
    storage_base_dir: Path,
) -> tuple[Path, ...]:
    """Export both profiles while keeping all SettingsManager writes isolated."""

    outputs: list[Path] = []
    for app_name, filename in EXPORT_TARGETS:
        output_file = docs_dir / filename
        _export_snapshot(
            app_name,
            output_file,
            organization=organization,
            storage_base_dir=storage_base_dir,
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
    parser.add_argument(
        "--organization",
        default="SRPSS_DocSnapshot",
        help="QSettings organization name to use for the temporary SettingsManager",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    docs_dir = Path(args.docs_dir)
    with tempfile.TemporaryDirectory(prefix="srpss_defaults_") as temp_dir:
        outputs = regenerate_sst_defaults(
            docs_dir,
            organization=args.organization,
            storage_base_dir=Path(temp_dir),
        )
    for (app_name, _filename), output_file in zip(EXPORT_TARGETS, outputs):
        print(f"[DOCS] Exported {app_name} defaults to {output_file}")


if __name__ == "__main__":
    main()
