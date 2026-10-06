from __future__ import annotations

import json
from pathlib import Path

from core.settings import visualizer_presets as vp


def _write_sphere_preset(target: Path, *, slot: int, authored_name: str) -> None:
    """Write a self-owned valid Sphere preset fixture.

    Catalogue mechanics must not depend on whichever curated Sphere presets happen
    to ship today.  The filename supplies the stable source slot/name semantics;
    the payload only needs one mode-owned setting to be usable.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {
                "mode": "sphere",
                "name": authored_name,
                "preset_index": slot,
                "snapshot": {
                    "widgets": {
                        "spotify_visualizer": {
                            "mode": "sphere",
                            "sphere_gloss": 0.42,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def _build_sphere_from(tmp_path: Path, monkeypatch):
    root = tmp_path / "visualizer_modes"
    overrides = tmp_path / "visualizer_mode_overrides"
    overrides.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(vp, "_presets_root", lambda: root)
    monkeypatch.setattr(vp, "_snapshot_presets_root", lambda: overrides)
    # These tests exercise catalogue construction, not manifest reconciliation.
    monkeypatch.setattr(vp, "_CURATED_TREE_SYNCED", True)
    presets = vp._build_presets_for_mode("sphere")
    vp._PRESETS["sphere"] = presets
    return root, presets


def test_sparse_authored_slots_compact_to_runtime_positions(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "visualizer_modes" / "sphere"
    _write_sphere_preset(root / "preset_1_glass_current.json", slot=0, authored_name="ignored")
    _write_sphere_preset(root / "preset_5_user_extra.json", slot=4, authored_name="ignored")

    _root, presets = _build_sphere_from(tmp_path, monkeypatch)

    assert [preset.name for preset in presets] == [
        "Preset 1 (Glass Current)",
        "Preset 5 (User Extra)",
        "Custom",
    ]
    assert vp._PRESET_SOURCE_SLOTS["sphere"] == [0, 4]
    assert vp.get_custom_preset_index("sphere") == 2
    assert vp.get_preset_file_path("sphere", 0).name == "preset_1_glass_current.json"
    assert vp.get_preset_file_path("sphere", 1).name == "preset_5_user_extra.json"
    assert vp.get_next_visualizer_preset_ordinal("sphere") == 6


def test_single_high_numbered_authored_preset_is_valid(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "visualizer_modes" / "sphere"
    _write_sphere_preset(root / "preset_20_only_survivor.json", slot=19, authored_name="ignored")

    _root, presets = _build_sphere_from(tmp_path, monkeypatch)

    assert [preset.name for preset in presets] == ["Preset 20 (Only Survivor)", "Custom"]
    assert vp._PRESET_SOURCE_SLOTS["sphere"] == [19]
    assert vp.get_custom_preset_index("sphere") == 1
    assert vp.get_preset_file_path("sphere", 0).name == "preset_20_only_survivor.json"
    assert vp.get_next_visualizer_preset_ordinal("sphere") == 21
