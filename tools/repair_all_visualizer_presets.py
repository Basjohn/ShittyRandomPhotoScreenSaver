"""Batch repair all visualizer presets using tools.visualizer_preset_repair."""
from __future__ import annotations

import sys
import importlib
from pathlib import Path

def _load_repair_file():
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    module = importlib.import_module('tools.visualizer_preset_repair')
    return module.repair_file  # type: ignore[attr-defined]


repair_file = _load_repair_file()


def main() -> None:
    root = Path(__file__).resolve().parents[1] / 'presets' / 'visualizer_modes'
    if not root.exists():
        raise SystemExit(f"Preset directory not found: {root}")

    project_root = Path(__file__).resolve().parents[1]
    processed = 0
    failures = []
    for mode_dir in sorted(root.iterdir()):
        if not mode_dir.is_dir():
            continue
        mode = mode_dir.name
        for preset in sorted(mode_dir.glob('*.json')):
            try:
                backup, stats = repair_file(preset, mode)
            except Exception as exc:  # noqa: BLE001
                failures.append((preset, mode, exc))
                print(f"FAILED {preset.relative_to(project_root)} (mode={mode}): {exc}")
                continue
            processed += 1
            print(
                f"Repaired {preset.relative_to(project_root)} (mode={mode}) -> backup {backup.name} | "
                f"added={len(stats['added'])} removed={len(stats['removed'])} changed={len(stats['changed'])}"
            )
    print(f"Total presets repaired: {processed}")
    if failures:
        print(f"Failures: {len(failures)}")
        for preset, mode, exc in failures:
            print(f" - {preset.relative_to(project_root)} (mode={mode}): {exc}")


if __name__ == '__main__':
    main()
