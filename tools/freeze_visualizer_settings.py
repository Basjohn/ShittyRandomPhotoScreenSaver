"""Freeze resolved Visualizer settings as test fixtures: python tools/freeze_visualizer_settings.py [mode ...]

Curated presets and canonical defaults are authored content the operator changes at will, so no test may
depend on their current values (Current_Plan N2). A test that needs a realistic, complete settings model
loads a frozen copy from ``tests/fixtures/visualizer_frozen_settings/<mode>.json`` instead
(``tests/_visualizer_frozen_settings.py``). This tool writes those copies from the mode's first curated preset
as the tree resolves it now; run it only to add a mode or to deliberately move a fixture, and say why in the
commit.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / "tests" / "fixtures" / "visualizer_frozen_settings"


def resolved_settings(mode: str) -> dict:
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_presets import resolve_visualizer_activation_payload

    activation = resolve_visualizer_activation_payload({"mode": mode, f"preset_{mode}": 0}, mode=mode)
    model = SpotifyVisualizerSettings.from_mapping(activation.resolved_config, apply_preset_overlay=False)
    return asdict(model)


def main() -> None:
    from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("modes", nargs="*", default=list(VISUALIZER_MODE_IDS))
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for mode in args.modes:
        path = args.output / f"{mode}.json"
        path.write_text(json.dumps(resolved_settings(mode), indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"froze {mode} -> {path}")


if __name__ == "__main__":
    main()
