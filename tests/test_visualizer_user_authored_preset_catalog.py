from __future__ import annotations

import shutil
from pathlib import Path

from core.settings import visualizer_presets as vp


def _copy_as(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


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
    source_root = Path(vp.__file__).resolve().parents[2] / "presets" / "visualizer_modes" / "sphere"
    root = tmp_path / "visualizer_modes" / "sphere"
    _copy_as(source_root / "preset_1_glass_current.json", root / "preset_1_glass_current.json")
    _copy_as(source_root / "preset_2_voxel_bloom.json", root / "preset_5_user_extra.json")

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
    source_root = Path(vp.__file__).resolve().parents[2] / "presets" / "visualizer_modes" / "sphere"
    root = tmp_path / "visualizer_modes" / "sphere"
    _copy_as(source_root / "preset_1_glass_current.json", root / "preset_20_only_survivor.json")

    _root, presets = _build_sphere_from(tmp_path, monkeypatch)

    assert [preset.name for preset in presets] == ["Preset 20 (Only Survivor)", "Custom"]
    assert vp._PRESET_SOURCE_SLOTS["sphere"] == [19]
    assert vp.get_custom_preset_index("sphere") == 1
    assert vp.get_preset_file_path("sphere", 0).name == "preset_20_only_survivor.json"
    assert vp.get_next_visualizer_preset_ordinal("sphere") == 21
