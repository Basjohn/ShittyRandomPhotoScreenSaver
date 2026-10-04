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
    return json.loads((FIXTURES / f"{mode}.json").read_text(encoding="utf-8"))
