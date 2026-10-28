from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from core.settings import visualizer_presets as vp
from core.settings.visualizer_preset_transfer import (
    export_visualizer_presets_zip,
    import_visualizer_preset_json_files,
    import_visualizer_presets_archive,
    import_visualizer_presets_folder,
)
from core.visualizer_preset_tree import scan_curated_visualizer_preset_tree


@pytest.fixture(autouse=True)
def _restore_visualizer_preset_registry():
    original_presets = {mode: list(presets) for mode, presets in vp._PRESETS.items()}
    yield
    vp._PRESETS.clear()
    vp._PRESETS.update(original_presets)


def _preset_payload(mode: str, index: int, *, value: float = 1.0) -> dict:
    return {
        "mode": mode,
        "name": f"Preset {index + 1} (Demo)",
        "preset_index": index,
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": mode,
                    # Use real canonical setting keys so the loose-import
                    # canonicalizer preserves the value (unknown keys are dropped).
                    "bubble_big_size_max" if mode == "bubble" else "spectrum_bar_width": value,
                }
            }
        },
    }


def test_export_visualizer_presets_zip_includes_only_directory_contents(tmp_path: Path) -> None:
    root = tmp_path / "visualizer_modes"
    mode_dir = root / "bubble"
    mode_dir.mkdir(parents=True)
    (mode_dir / "preset_1_demo.json").write_text(
        json.dumps(_preset_payload("bubble", 0)),
        encoding="utf-8",
    )

    archive_path = tmp_path / "export.zip"
    before = {p.relative_to(root): p.read_bytes() for p in root.rglob('*.json')}
    result = export_visualizer_presets_zip(archive_path, source_root=root)

    assert result.files == 1
    with ZipFile(archive_path, "r") as archive:
        assert set(archive.namelist()) == {
            "visualizer_modes/bubble/preset_1_demo.json",
        }
    assert {p.relative_to(root): p.read_bytes() for p in root.rglob('*.json')} == before
    assert not (root.parent / 'visualizer_modes_manifest.json').exists()


def test_folder_import_replaces_tree_and_prunes_stale_files(tmp_path: Path, monkeypatch) -> None:
    source_root = tmp_path / "incoming" / "visualizer_modes"
    target_root = tmp_path / "active" / "visualizer_modes"
    source_mode = source_root / "spectrum"
    target_mode = target_root / "spectrum"
    source_mode.mkdir(parents=True)
    target_mode.mkdir(parents=True)
    (source_mode / "preset_1_new.json").write_text(
        json.dumps(_preset_payload("spectrum", 0)),
        encoding="utf-8",
    )
    (target_mode / "preset_9_stale.json").write_text("{}", encoding="utf-8")

    # Do not repoint _presets_root at this single-mode tmp tree: the import's
    # internal reload_presets() rebuilds every mode and the current registry
    # requires >=1 authored preset per mode (a mode can be pruned to one but not
    # to zero). Let reload read the real complete shipped tree (non-frozen
    # reconcile/sync are read-only no-ops); the assertions below target target_root.
    result = import_visualizer_presets_folder(source_root.parent, target_root=target_root)

    assert result.files == 1
    assert (target_mode / "preset_1_new.json").exists()
    assert not (target_mode / "preset_9_stale.json").exists()
    assert scan_curated_visualizer_preset_tree(target_root) == {
        "spectrum/preset_1_new.json",
    }


def test_archive_import_replaces_curated_tree(tmp_path: Path, monkeypatch) -> None:
    import tempfile
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    target_root = tmp_path / "active" / "visualizer_modes"
    target_root.mkdir(parents=True)
    archive_path = tmp_path / "incoming.zip"
    payload = json.dumps(_preset_payload("bubble", 0))
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("visualizer_modes/bubble/preset_1_demo.json", payload)

    # See folder-import note: reload_presets() rebuilds every mode and requires
    # >=1 authored preset per mode, so let it read the real complete shipped tree.
    result = import_visualizer_presets_archive(archive_path, target_root=target_root)

    assert result.files == 1
    assert (target_root / "bubble" / "preset_1_demo.json").exists()


def test_loose_json_import_infers_mode_and_replaces_matching_slot(tmp_path: Path, monkeypatch) -> None:
    target_root = tmp_path / "active" / "visualizer_modes"
    mode_dir = target_root / "bubble"
    mode_dir.mkdir(parents=True)
    (mode_dir / "preset_1_old.json").write_text(
        json.dumps(_preset_payload("bubble", 0, value=0.5)),
        encoding="utf-8",
    )
    (mode_dir / "preset_2_keep.json").write_text(
        json.dumps(_preset_payload("bubble", 1, value=2.0)),
        encoding="utf-8",
    )
    loose = tmp_path / "preset_1_fresh.json"
    # A value Bubble's spec admits unchanged (an out-of-range one would read back clamped).
    from core.settings.visualizer_mode_settings import require_mode_settings
    control = require_mode_settings("bubble").control("bubble_big_size_max")
    fresh = control.low + 0.75 * (control.high - control.low)
    loose.write_text(json.dumps(_preset_payload("bubble", 0, value=fresh)), encoding="utf-8")

    # See folder-import note: reload_presets() rebuilds every mode and requires
    # >=1 authored preset per mode, so let it read the real complete shipped tree.
    result = import_visualizer_preset_json_files([loose], target_root=target_root)

    assert result.files == 1
    assert not (mode_dir / "preset_1_old.json").exists()
    imported = mode_dir / "preset_1_fresh.json"
    assert imported.exists()
    payload = json.loads(imported.read_text(encoding="utf-8"))
    assert payload["snapshot"]["widgets"]["spotify_visualizer"]["bubble_big_size_max"] == pytest.approx(fresh)
    assert (mode_dir / "preset_2_keep.json").exists()
    assert scan_curated_visualizer_preset_tree(target_root) == {
        "bubble/preset_1_fresh.json",
        "bubble/preset_2_keep.json",
    }


@pytest.mark.parametrize('failure', ('invalid_second', 'duplicate_slot'))
def test_loose_batch_is_fully_validated_before_deleting_any_target(tmp_path, failure):
    root = tmp_path / 'active'
    path = root / 'bubble/preset_1_existing.json'
    path.parent.mkdir(parents=True)
    path.write_bytes(b'valuable existing bytes\r\n')
    first = tmp_path / 'preset_1_incoming.json'
    first.write_text(json.dumps(_preset_payload('bubble', 0)), encoding='utf-8')
    second = tmp_path / 'other' / 'preset_1_duplicate.json'
    second.parent.mkdir()
    second.write_text('{broken' if failure == 'invalid_second'
                      else json.dumps(_preset_payload('bubble', 0)), encoding='utf-8')
    with pytest.raises(ValueError):
        import_visualizer_preset_json_files([first, second], target_root=root)
    assert path.read_bytes() == b'valuable existing bytes\r\n'
    assert tuple(root.rglob('*.json')) == (path,)
