"""Every curated Visualizer preset authors every Settings control of its mode (operator 2026-10-24).

A control a preset leaves out silently falls back to the canonical default, so a new control would reach every
preset unauthored. This checks presence only, never values (presets are authored art). The framed view pose is
optional ``starting_view`` metadata and is not required. Fill a new control with
``tools/visualizer_preset_repair.py --repair-all`` (adds it at its default, changes nothing authored), then author it.
"""
import json
from pathlib import Path

import pytest

from core.settings import visualizer_presets as vp

ROOT = Path(__file__).resolve().parents[1]


def _curated():
    for mode in vp.MODES:
        for path in sorted((ROOT / "presets" / "visualizer_modes" / mode).glob("*.json")):
            yield pytest.param(mode, path, id=f"{mode}/{path.stem}")


@pytest.mark.parametrize(("mode", "path"), list(_curated()))
def test_a_curated_preset_authors_every_control_of_its_mode(mode, path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    authored = set()
    for section in vp._collect_visualizer_sections(payload):
        authored.update(section)
    missing = sorted(set(vp.preset_artwork_keys(mode)) - authored)
    assert not missing, f"{path.name} leaves {missing} to the default: run the preset repair fill, then author them"
