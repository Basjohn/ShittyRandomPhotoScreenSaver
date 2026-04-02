from __future__ import annotations

from pathlib import Path

from core.visualizer_preset_manifest import (
    build_curated_visualizer_manifest_payload,
    is_managed_curated_preset_path,
    load_curated_visualizer_preset_manifest,
    resolve_curated_visualizer_manifest_entries,
    scan_curated_visualizer_preset_tree,
    sync_curated_preset_tree,
    write_curated_visualizer_preset_manifest,
)


def test_visualizer_preset_manifest_matches_repo_tree() -> None:
    root = Path(__file__).resolve().parents[1] / "presets" / "visualizer_modes"
    manifest = resolve_curated_visualizer_manifest_entries(root)
    repo_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*.json")
    }

    assert manifest == repo_paths


def test_scan_curated_visualizer_preset_tree_ignores_custom_slots(tmp_path: Path) -> None:
    root = tmp_path / "visualizer_modes"
    spectrum = root / "spectrum"
    spectrum.mkdir(parents=True)
    (spectrum / "preset_1_pillars.json").write_text("{}", encoding="utf-8")
    (spectrum / "preset_4_custom.json").write_text("{}", encoding="utf-8")

    assert scan_curated_visualizer_preset_tree(root) == {"spectrum/preset_1_pillars.json"}


def test_resolve_manifest_entries_accepts_live_files_missing_from_manifest(tmp_path: Path) -> None:
    root = tmp_path / "visualizer_modes"
    spectrum = root / "spectrum"
    spectrum.mkdir(parents=True)
    (spectrum / "preset_1_pillars.json").write_text("{}", encoding="utf-8")
    (spectrum / "preset_2_new_hotness.json").write_text("{}", encoding="utf-8")
    manifest_path = root.parent / "visualizer_modes_manifest.json"
    manifest_path.write_text(
        '{"managed_curated_files":["spectrum/preset_1_pillars.json"]}',
        encoding="utf-8",
    )

    assert resolve_curated_visualizer_manifest_entries(root) == {
        "spectrum/preset_1_pillars.json",
        "spectrum/preset_2_new_hotness.json",
    }


def test_resolve_manifest_entries_ignores_stale_paths_missing_from_live_tree(tmp_path: Path) -> None:
    root = tmp_path / "visualizer_modes"
    spectrum = root / "spectrum"
    spectrum.mkdir(parents=True)
    (spectrum / "preset_1_pillars.json").write_text("{}", encoding="utf-8")
    manifest_path = root.parent / "visualizer_modes_manifest.json"
    manifest_path.write_text(
        '{"managed_curated_files":["spectrum/preset_1_pillars.json","spectrum/preset_9_removed.json"]}',
        encoding="utf-8",
    )

    assert load_curated_visualizer_preset_manifest(root) == {
        "spectrum/preset_1_pillars.json",
        "spectrum/preset_9_removed.json",
    }
    assert resolve_curated_visualizer_manifest_entries(root) == {
        "spectrum/preset_1_pillars.json",
    }


def test_build_manifest_payload_sorts_and_normalizes_entries() -> None:
    payload = build_curated_visualizer_manifest_payload(
        {
            Path("spectrum\\preset_2_new_hotness.json"),
            "spectrum/preset_1_pillars.json",
        }
    )

    assert payload == {
        "managed_curated_files": [
            "spectrum/preset_1_pillars.json",
            "spectrum/preset_2_new_hotness.json",
        ]
    }


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


def test_write_manifest_persists_reconciled_live_entries_for_future_sync(tmp_path: Path) -> None:
    root = tmp_path / "visualizer_modes"
    spectrum = root / "spectrum"
    spectrum.mkdir(parents=True)
    kept = spectrum / "preset_1_pillars.json"
    added = spectrum / "preset_2_new_hotness.json"
    kept.write_text("{}", encoding="utf-8")
    added.write_text("{}", encoding="utf-8")

    manifest_path = root.parent / "visualizer_modes_manifest.json"
    manifest_path.write_text(
        '{"managed_curated_files":["spectrum/preset_1_pillars.json"]}',
        encoding="utf-8",
    )

    resolved = resolve_curated_visualizer_manifest_entries(root)
    assert resolved == {
        "spectrum/preset_1_pillars.json",
        "spectrum/preset_2_new_hotness.json",
    }

    written = write_curated_visualizer_preset_manifest(root, resolved)
    assert written == resolved
    assert load_curated_visualizer_preset_manifest(root) == resolved

    removed = sync_curated_preset_tree(root, allow_non_frozen=True)
    assert removed == []
    assert kept.exists()
    assert added.exists()


def test_is_managed_curated_preset_path_excludes_custom_slot_names() -> None:
    assert is_managed_curated_preset_path(Path("spectrum/preset_2_organs.json")) is True
    assert is_managed_curated_preset_path(Path("spectrum/preset_4_custom.json")) is False
