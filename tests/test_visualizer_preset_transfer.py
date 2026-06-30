from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

from core.settings import visualizer_presets as vp
from core.settings.visualizer_preset_transfer import (
    export_visualizer_presets_zip,
    import_visualizer_preset_json_files,
    import_visualizer_presets_archive,
    import_visualizer_presets_folder,
)
from core.visualizer_preset_manifest import load_curated_visualizer_preset_manifest


def _preset_payload(mode: str, index: int, *, value: float = 1.0) -> dict:
    return {
        "mode": mode,
        "name": f"Preset {index + 1} (Demo)",
        "preset_index": index,
        "snapshot": {
            "widgets": {
                "spotify_visualizer": {
                    "mode": mode,
                    f"{mode}_growth" if mode == "bubble" else "spectrum_bar_width": value,
                }
            }
        },
    }


def test_export_visualizer_presets_zip_includes_tree_and_manifest(tmp_path: Path) -> None:
    root = tmp_path / "visualizer_modes"
    mode_dir = root / "bubble"
    mode_dir.mkdir(parents=True)
    (mode_dir / "preset_1_demo.json").write_text(
        json.dumps(_preset_payload("bubble", 0)),
        encoding="utf-8",
    )

    archive_path = tmp_path / "export.zip"
    result = export_visualizer_presets_zip(archive_path, source_root=root)

    assert result.files == 1
    with ZipFile(archive_path, "r") as archive:
        assert set(archive.namelist()) == {
            "visualizer_modes/bubble/preset_1_demo.json",
            "visualizer_modes_manifest.json",
        }


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

    monkeypatch.setattr(vp, "_presets_root", lambda: target_root)
    result = import_visualizer_presets_folder(source_root.parent, target_root=target_root)

    assert result.files == 1
    assert (target_mode / "preset_1_new.json").exists()
    assert not (target_mode / "preset_9_stale.json").exists()
    assert load_curated_visualizer_preset_manifest(target_root) == {
        "spectrum/preset_1_new.json",
    }


def test_archive_import_replaces_curated_tree(tmp_path: Path, monkeypatch) -> None:
    target_root = tmp_path / "active" / "visualizer_modes"
    target_root.mkdir(parents=True)
    archive_path = tmp_path / "incoming.zip"
    payload = json.dumps(_preset_payload("bubble", 0))
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("visualizer_modes/bubble/preset_1_demo.json", payload)

    monkeypatch.setattr(vp, "_presets_root", lambda: target_root)
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
    loose.write_text(json.dumps(_preset_payload("bubble", 0, value=4.0)), encoding="utf-8")

    monkeypatch.setattr(vp, "_presets_root", lambda: target_root)
    result = import_visualizer_preset_json_files([loose], target_root=target_root)

    assert result.files == 1
    assert not (mode_dir / "preset_1_old.json").exists()
    imported = mode_dir / "preset_1_fresh.json"
    assert imported.exists()
    payload = json.loads(imported.read_text(encoding="utf-8"))
    assert payload["snapshot"]["widgets"]["spotify_visualizer"]["bubble_growth"] == 4.0
    assert (mode_dir / "preset_2_keep.json").exists()
    assert load_curated_visualizer_preset_manifest(target_root) == {
        "bubble/preset_1_fresh.json",
        "bubble/preset_2_keep.json",
    }
