"""Utility to regenerate canonical SST snapshots from default settings.

This script instantiates a throwaway SettingsManager pointing at a dedicated
organization name so it never touches the real user profile. It resets to the
current canonical defaults, removes any user-preserved keys (sources folders,
and exports the snapshot to the Docs/ directory so the
documentation stays in sync with `core/settings/defaults.py`.
"""
from __future__ import annotations

import argparse
import sys
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


def _export_snapshot(application: str, output_path: Path, organization: str = "SRPSS_DocSnapshot") -> None:
    manager = SettingsManager(organization=organization, application=application)
    manager.reset_to_defaults()
    _apply_doc_overrides(manager)
    manager.save()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not manager.export_to_sst(str(output_path)):
        raise RuntimeError(f"Failed to export SST for {application} to {output_path}")


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
    for app_name, filename in EXPORT_TARGETS:
        output_file = docs_dir / filename
        _export_snapshot(app_name, output_file, organization=args.organization)
        print(f"[DOCS] Exported {app_name} defaults to {output_file}")


if __name__ == "__main__":
    main()
