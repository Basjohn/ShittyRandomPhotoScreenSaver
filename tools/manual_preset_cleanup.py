"""Manual cleanup script to remove custom_preset_backup duplication.

This script merges widgets.spotify_visualizer.* entries from the legacy
custom_preset_backup block into snapshot.widgets.spotify_visualizer and then
removes the backup block for curated presets under presets/visualizer_modes.
"""
from __future__ import annotations

import json
from pathlib import Path

PREFIX = "widgets.spotify_visualizer."
ROOT = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"


def main() -> None:
    updated: list[Path] = []
    if not ROOT.exists():
        print(f"Preset root {ROOT} missing, nothing to do")
        return

    for path in sorted(ROOT.rglob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Skipping {path}: failed to parse ({exc})")
            continue

        snapshot = data.get("snapshot")
        if not isinstance(snapshot, dict):
            continue

        backup = snapshot.get("custom_preset_backup")
        widgets = snapshot.get("widgets")

        if not isinstance(backup, dict):
            continue

        sv = None
        if isinstance(widgets, dict):
            sv = widgets.get("spotify_visualizer")
        if not isinstance(sv, dict):
            sv = {}
            if isinstance(widgets, dict):
                widgets["spotify_visualizer"] = sv
            else:
                snapshot["widgets"] = {"spotify_visualizer": sv}

        changed = False
        for key, value in backup.items():
            if isinstance(key, str) and key.startswith(PREFIX):
                trimmed = key[len(PREFIX):]
                if sv.get(trimmed) != value:
                    sv[trimmed] = value
                    changed = True

        if changed:
            updated.append(path)
        # Remove the backup block either way to avoid duplication.
        snapshot.pop("custom_preset_backup", None)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Updated {len(updated)} preset(s)")
    for entry in updated:
        print(f" - {entry}")


if __name__ == "__main__":
    main()
