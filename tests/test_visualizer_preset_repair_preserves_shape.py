"""The preset repair fill keeps each curated file's own shape (side defect, 5 Nov).

``--repair-all`` used to re-sort every key and drop inert authored entries (Waveform snapshot pose leaves,
``preset_<mode>`` slot metadata). Run on copies of real curated presets: structural assertions only (never preset
values or counts): every pre-existing key and value keeps its place, metadata and line endings survive, and the
only change is the missing controls coming back.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

pytest.importorskip("PySide6")  # The tool is a native Qt Foundry on Windows.
from core.settings import visualizer_presets as vp
from tools import visualizer_preset_repair as repair

ROOT = Path(__file__).resolve().parents[1]
MODES = ("waveform_ribbon", "spectrum", "bubble", "extruded_bubble", "sphere")


def _first_curated(mode: str) -> Path:
    paths = sorted((ROOT / "presets" / "visualizer_modes" / mode).glob("*.json"))
    if not paths:
        pytest.skip(f"no curated {mode} presets")
    return paths[0]


def _section(payload: dict) -> dict:
    return payload["snapshot"]["widgets"]["spotify_visualizer"]


def _order(value):
    if isinstance(value, dict):
        return [(key, _order(item)) for key, item in value.items()]
    if isinstance(value, list):
        return [_order(item) for item in value]
    return value


def _shape_violations(before: dict, after: dict, removed: tuple[str, ...]) -> list[str]:
    """Everything that differs except the removed controls returning (structure + values + order)."""
    problems = []
    restored = dict(_section(after))
    if set(restored) - set(_section(before)) != set(removed):
        problems.append(f"added keys {sorted(set(restored) - set(_section(before)))} != {sorted(removed)}")
    for key in removed:
        restored.pop(key, None)
    trimmed = json.loads(json.dumps(after))
    trimmed["snapshot"]["widgets"]["spotify_visualizer"] = restored
    if _order(trimmed) != _order(before):
        problems.append("a pre-existing key, value, metadata entry or key order changed")
    return problems


def _strip_controls(path: Path, mode: str) -> tuple[dict, tuple[str, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    section = _section(payload)
    present = [key for key in vp.preset_artwork_keys(mode) if key in section]
    assert len(present) >= 3, "curated preset carries too few controls to exercise the fill"
    removed = (present[0], present[len(present) // 2], present[-1])
    for key in removed:
        section.pop(key)
    return payload, removed


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("newline", ("\n", "\r\n"))
def test_repair_adds_only_missing_controls_and_keeps_everything_else(tmp_path, monkeypatch, mode, newline):
    monkeypatch.setattr(repair, "_BACKUP_ROOT", tmp_path / "backups")
    source = _first_curated(mode)
    stripped, removed = _strip_controls(source, mode)
    path = tmp_path / source.name
    path.write_bytes((json.dumps(stripped, indent=2) + "\n").replace("\n", newline).encode("utf-8"))

    _backup, stats = repair.repair_file(path, mode, sync_shipped_artifacts=False)

    raw = path.read_bytes()
    after = json.loads(raw.decode("utf-8"))
    assert _shape_violations(stripped, after, removed) == []
    assert set(stats["added"]) == set(removed) and not stats["removed"] and not stats["changed"]
    if newline == "\r\n":
        assert raw.count(b"\n") == raw.count(b"\r\n")
    else:
        assert b"\r" not in raw
    keys = list(_section(after))
    if list(_section(stripped)) == sorted(_section(stripped)):
        assert keys == sorted(keys)
    else:  # unsorted authoring: each control lands right after its nearest registry predecessor in the file
        registry = list(vp.preset_artwork_keys(mode))
        for key in removed:
            earlier = [k for k in registry[: registry.index(key)] if k in _section(after)]
            if earlier:
                assert keys.index(key) == keys.index(earlier[-1]) + 1


@pytest.mark.parametrize("mode", MODES)
def test_repair_of_a_complete_curated_preset_leaves_its_bytes_alone(tmp_path, monkeypatch, mode):
    monkeypatch.setattr(repair, "_BACKUP_ROOT", tmp_path / "backups")
    source = _first_curated(mode)
    path = tmp_path / source.name
    shutil.copyfile(source, path)
    raw = path.read_bytes()
    backup, _stats = repair.repair_file(path, mode, sync_shipped_artifacts=False)
    assert path.read_bytes() == raw
    assert backup.read_bytes() == raw and backup != path


def test_shape_check_rejects_the_former_sorted_full_section_rewrite():
    """Negative control: the old rewrite (sorted keys, section replaced by the sanitized block) is caught."""
    mode = "waveform_ribbon"
    stripped, removed = _strip_controls(_first_curated(mode), mode)
    cleaned, _stats = repair._sanitize_settings(mode, stripped)
    legacy = json.loads(json.dumps(stripped))
    legacy["snapshot"]["widgets"]["spotify_visualizer"] = dict(cleaned)
    legacy = json.loads(json.dumps(legacy, sort_keys=True))
    assert _shape_violations(stripped, legacy, removed)
