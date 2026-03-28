from __future__ import annotations

from pathlib import Path

from core.visualizer_preset_manifest import (
    is_managed_curated_preset_path,
    load_curated_visualizer_preset_manifest,
    sync_curated_preset_tree,
)


def test_visualizer_preset_manifest_matches_repo_tree() -> None:
    root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"
    manifest = load_curated_visualizer_preset_manifest(root)
    repo_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.json")
    }

    assert manifest == repo_paths


def test_sync_curated_preset_tree_removes_stale_managed_file(tmp_path: Path) -> None:
    root = tmp_path / "visualizer_modes"
    spectrum = root / "spectrum"
    spectrum.mkdir(parents=True)
    kept = spectrum / "preset_1_pillars.json"
    stale = spectrum / "preset_9_stale.json"
    custom = spectrum / "preset_4_custom.json"
    kept.write_text("{}", encoding="utf-8")
    stale.write_text("{}", encoding="utf-8")
    custom.write_text("{}", encoding="utf-8")

    removed = sync_curated_preset_tree(
        root,
        manifest_entries={"spectrum/preset_1_pillars.json"},
        allow_non_frozen=True,
    )

    assert removed == [stale]
    assert kept.exists()
    assert not stale.exists()
    assert custom.exists()


def test_is_managed_curated_preset_path_excludes_custom_slot_names() -> None:
    assert is_managed_curated_preset_path(Path("spectrum/preset_2_organs.json")) is True
    assert is_managed_curated_preset_path(Path("spectrum/preset_4_custom.json")) is False
