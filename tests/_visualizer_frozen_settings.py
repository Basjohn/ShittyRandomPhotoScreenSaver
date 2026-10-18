"""Frozen, complete Visualizer settings for tests (Current_Plan N2).

Curated presets and canonical defaults are authored content the operator changes at will; a test that needs a
realistic settings model loads one of these frozen copies instead (written by
``tools/freeze_visualizer_settings.py``). Keys added to the model later resolve to their defaults.
"""
from __future__ import annotations

import json
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "visualizer_frozen_settings"


def frozen_visualizer_settings(mode: str) -> dict:
    frozen = json.loads((FIXTURES / f"{mode}.json").read_text(encoding="utf-8"))
    from core.settings.defaults import get_default_settings

    # A mode key the model gained after the copy was frozen resolves to its canonical default.
    defaults = get_default_settings()["widgets"]["spotify_visualizer"]
    later = {key: value for key, value in defaults.items() if key.startswith(f"{mode}_") and key not in frozen}
    return {**later, **frozen}
