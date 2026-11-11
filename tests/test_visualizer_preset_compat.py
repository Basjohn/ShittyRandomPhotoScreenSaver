"""The curated preset tree and its compatibility record agree (1C.1).

Removing, renaming or adding a curated preset changes what a stored reference can name. Renumbering is free (the
resolver follows the name); anything else needs its line in ``core/settings/visualizer_preset_compat.py``. Both
sides are read: the tree through the canonical preset owner, the record from its module. Nothing about a preset's
content is read or pinned.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.settings import visualizer_presets as vp
from core.settings.visualizer_preset_compat import RETIRED_CURATED_PRESETS, SHIPPED_CURATED_PRESETS
from core.settings.visualizer_preset_indices import preset_identity

TREE = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"


def _tree_identities(mode: str, folder: Path) -> set[str]:
    identities = set()
    for path in folder.glob("*.json"):
        parsed = vp._parse_preset_payload(path, json.loads(path.read_text(encoding="utf-8")), mode,
                                          prefer_filename_index=True, prefer_filename_name=True)
        if parsed:
            identities.add(preset_identity(parsed[1].name))
    return identities


def _disagreements(mode: str, folder: Path) -> list[str]:
    tree = _tree_identities(mode, folder)
    shipped = set(SHIPPED_CURATED_PRESETS.get(mode, ()))
    retired = RETIRED_CURATED_PRESETS.get(mode, {})
    problems = [f"{mode}: {name!r} left the tree without a RETIRED entry" for name in sorted(shipped - tree)
                if name not in retired]
    problems += [f"{mode}: {name!r} is in the tree but not recorded as SHIPPED" for name in sorted(tree - shipped)]
    problems += [f"{mode}: retired {name!r} names a successor {to!r} that is not shipped"
                 for name, to in retired.items() if to is not None and to not in shipped]
    problems += [f"{mode}: {name!r} is both shipped and retired" for name in sorted(shipped & set(retired))]
    return problems


@pytest.mark.parametrize("mode", vp.MODES)
def test_the_curated_tree_and_its_compatibility_record_agree(mode):
    assert _disagreements(mode, TREE / mode) == []


def test_every_registered_mode_with_curated_presets_is_recorded():
    assert {m for m in vp.MODES if _tree_identities(m, TREE / m)} == set(SHIPPED_CURATED_PRESETS)


@pytest.mark.parametrize("change", ["removed", "renamed", "added"])
def test_negative_control_a_tree_change_without_its_entry_is_caught(tmp_path, change):
    mode = next(m for m in vp.MODES if len(_tree_identities(m, TREE / m)) >= 2)
    folder = tmp_path / mode
    folder.mkdir()
    files = sorted((TREE / mode).glob("*.json"))
    for path in files:
        (folder / path.name).write_bytes(path.read_bytes())
    victim = folder / files[-1].name
    if change == "removed":
        victim.unlink()
    elif change == "renamed":
        payload = json.loads(victim.read_text(encoding="utf-8"))
        payload.pop("name", None)
        victim.rename(victim.with_name(victim.stem.split("_")[0] + "_" + victim.stem.split("_")[1]
                                       + "_compat_guard_rename.json"))
    else:
        (folder / "preset_99_compat_guard_added.json").write_bytes(victim.read_bytes())
    assert _disagreements(mode, folder), change


def test_a_reference_to_a_retired_preset_opens_its_successor(monkeypatch):
    from core.settings import visualizer_preset_compat as compat
    from core.settings.visualizer_preset_indices import (
        PRESET_REFERENCES_KEY, get_missing_preset_fallback_index, resolve_preset_index_from_mapping,
    )
    from core.settings.visualizer_mode_registry import get_preset_key
    mode = next(m for m in vp.MODES if vp.get_custom_preset_index(m) >= 2)
    names = [preset_identity(n) for n in vp.get_preset_names(mode)]
    successor = names[-2]                                  # the last curated preset, never the fallback
    section = {get_preset_key(mode): 0,
               PRESET_REFERENCES_KEY: {mode: {"preset": "Compat Guard Gone", "catalogue": "older"}}}
    assert resolve_preset_index_from_mapping(mode, section) == get_missing_preset_fallback_index(mode)
    monkeypatch.setitem(compat.RETIRED_CURATED_PRESETS, mode, {"Compat Guard Gone": successor})
    assert resolve_preset_index_from_mapping(mode, section) == names.index(successor)


def test_renumbering_alone_needs_no_entry(tmp_path):
    mode = next(m for m in vp.MODES if len(_tree_identities(m, TREE / m)) >= 2)
    folder = tmp_path / mode
    folder.mkdir()
    files = sorted((TREE / mode).glob("*.json"))
    for path in files:
        (folder / path.name).write_bytes(path.read_bytes())
    moved = folder / files[0].name
    payload = json.loads(moved.read_text(encoding="utf-8"))
    suffix = moved.stem.split("_", 2)[2]
    payload["preset_index"] = 40
    (folder / f"preset_41_{suffix}.json").write_text(json.dumps(payload), encoding="utf-8")
    moved.unlink()
    assert _disagreements(mode, folder) == []
