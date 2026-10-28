"""Critical preset data-integrity checks; no GUI / visual acceptance tests.

Fixtures are test-authored. Never assert operator preset settings or defaults.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")  # The tool is a native Qt Foundry on Windows.
from tools import visualizer_preset_repair as repair


def _write(directory: Path, slot: int, suffix: str, identity: str, *, embedded: int | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"preset_{slot}_{suffix}.json"
    path.write_text(json.dumps({
        "mode": "bubble", "preset_index": slot - 1 if embedded is None else embedded,
        "name": f"Preset {slot} ({identity})",
        "snapshot": {"widgets": {"spotify_visualizer": {"bubble_sentinel_fixture": identity}}},
    }, indent=2), encoding="utf-8")
    return path


def _values(path: Path) -> tuple[int, str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return (payload["preset_index"], payload["name"],
            payload["snapshot"]["widgets"]["spotify_visualizer"]["bubble_sentinel_fixture"])


def test_reindex_obeys_filenames_not_embedded_metadata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(repair, "ROOT", tmp_path)
    monkeypatch.setattr(repair, "_BACKUP_ROOT", tmp_path / "backups")
    mode = tmp_path / "presets" / "visualizer_modes" / "bubble"
    _write(mode, 1, "alpha", "A", embedded=6)
    _write(mode, 2, "beta", "B", embedded=0)
    _write(mode, 3, "gamma", "C", embedded=1)
    results = repair.reindex_mode_presets("bubble")
    assert len(results) == 3
    assert _values(mode / "preset_1_alpha.json") == (0, "Preset 1 (A)", "A")
    assert _values(mode / "preset_2_beta.json") == (1, "Preset 2 (B)", "B")
    assert _values(mode / "preset_3_gamma.json") == (2, "Preset 3 (C)", "C")
    assert repair.reindex_mode_presets("bubble") == []


def test_reindex_fills_gaps_in_filename_order_without_changing_content(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(repair, "ROOT", tmp_path)
    monkeypatch.setattr(repair, "_BACKUP_ROOT", tmp_path / "backups")
    mode = tmp_path / "presets" / "visualizer_modes" / "bubble"
    _write(mode, 1, "start", "S", embedded=6)
    _write(mode, 5, "fifth", "F", embedded=0)
    repair.reindex_mode_presets("bubble")
    assert _values(mode / "preset_2_fifth.json") == (1, "Preset 2 (F)", "F")
    assert not (mode / "preset_5_fifth.json").exists()


def test_swap_switches_both_indices_and_undo_restores_both(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(repair, "_BACKUP_ROOT", tmp_path / "backups")
    mode = tmp_path / "presets" / "visualizer_modes" / "bubble"
    a = _write(mode, 1, "alpha", "A")
    b = _write(mode, 3, "beta", "B")
    one, two = repair.swap_mode_presets("bubble", a, b, mode_dir=mode)
    assert _values(mode / "preset_3_alpha.json") == (2, "Preset 3 (A)", "A")
    assert _values(mode / "preset_1_beta.json") == (0, "Preset 1 (B)", "B")
    assert not a.exists() and not b.exists()
    undo_rows = ((one[0], one[2], one[1]), (two[0], two[2], two[1]))
    entry = repair.UndoEntry(one[0], one[2], one[1], related=(undo_rows[1],),
                             expected_hashes=repair._undo_hashes(undo_rows))
    changed = json.loads(one[1].read_text(encoding="utf-8"))
    changed["newer_test_owned_edit"] = "must survive"
    one[1].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(RuntimeError, match="Undo refused"):
        repair.restore_undo_entry(entry)
    assert json.loads(one[1].read_text(encoding="utf-8"))["newer_test_owned_edit"] == "must survive"
    changed.pop("newer_test_owned_edit")
    one[1].write_text(json.dumps(changed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    repair.restore_undo_entry(entry)
    assert _values(a) == (0, "Preset 1 (A)", "A")
    assert _values(b) == (2, "Preset 3 (B)", "B")
    assert not one[1].exists() and not two[1].exists()


def test_swap_rejects_collision_without_modifying_files(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(repair, "_BACKUP_ROOT", tmp_path / "backups")
    mode = tmp_path / "presets" / "visualizer_modes" / "bubble"
    a = _write(mode, 1, "alpha", "A")
    b = _write(mode, 2, "beta", "B")
    occupied = _write(mode, 2, "alpha", "C")
    before = {p.name: p.read_bytes() for p in mode.glob("*.json")}
    with pytest.raises(ValueError, match="Duplicate numbered slots"):
        repair.swap_mode_presets("bubble", a, b, mode_dir=mode)
    assert before == {p.name: p.read_bytes() for p in mode.glob("*.json")}
    assert occupied.exists()


def test_repair_has_no_manifest_regeneration_surface():
    assert not hasattr(repair, 'regenerate_existing_visualizer_manifest')
    assert not hasattr(repair, 'get_visualizer_preset_manifest_path')
