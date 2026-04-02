from __future__ import annotations

from pathlib import Path

from core.visualizer_preset_manifest import (
    build_curated_visualizer_manifest_payload,
    is_managed_curated_preset_path,
    load_curated_visualizer_preset_manifest,
    mirror_curated_visualizer_preset_tree,
    regenerate_repo_shipped_visualizer_preset_artifacts,
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


def test_mirror_curated_visualizer_preset_tree_prunes_stale_targets_and_writes_manifest(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source" / "visualizer_modes"
    target_root = tmp_path / "target" / "visualizer_modes"
    source_mode = source_root / "blob"
    target_mode = target_root / "blob"
    source_mode.mkdir(parents=True)
    target_mode.mkdir(parents=True)

    (source_mode / "preset_1_alpha.json").write_text('{"name":"Alpha"}', encoding="utf-8")
    (source_mode / "preset_2_beta.json").write_text('{"name":"Beta"}', encoding="utf-8")
    (source_root.parent / "visualizer_modes_manifest.json").write_text(
        '{"managed_curated_files":["blob/preset_1_alpha.json"]}',
        encoding="utf-8",
    )
    (target_mode / "preset_1_alpha.json").write_text('{"name":"Old Alpha"}', encoding="utf-8")
    (target_mode / "preset_9_stale.json").write_text('{"name":"Stale"}', encoding="utf-8")

    mirrored = mirror_curated_visualizer_preset_tree(source_root, target_root)

    assert mirrored == {
        "blob/preset_1_alpha.json",
        "blob/preset_2_beta.json",
    }
    assert (target_mode / "preset_1_alpha.json").read_text(encoding="utf-8") == '{"name":"Alpha"}'
    assert (target_mode / "preset_2_beta.json").read_text(encoding="utf-8") == '{"name":"Beta"}'
    assert not (target_mode / "preset_9_stale.json").exists()
    assert load_curated_visualizer_preset_manifest(target_root) == mirrored


def test_regenerate_repo_shipped_visualizer_preset_artifacts_rebuilds_release_tree_from_source(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "presets" / "visualizer_modes" / "spectrum"
    release_root = tmp_path / "release" / "main_mc.dist" / "presets" / "visualizer_modes" / "spectrum"
    source_root.mkdir(parents=True)
    release_root.mkdir(parents=True)

    (source_root / "preset_1_organs.json").write_text('{"name":"Organs"}', encoding="utf-8")
    (source_root / "preset_2_bars.json").write_text('{"name":"Bars"}', encoding="utf-8")
    (release_root / "preset_9_stale.json").write_text('{"name":"Stale"}', encoding="utf-8")

    artifacts = regenerate_repo_shipped_visualizer_preset_artifacts(tmp_path)

    assert artifacts["entry_count"] == 2
    assert load_curated_visualizer_preset_manifest(tmp_path / "presets" / "visualizer_modes") == {
        "spectrum/preset_1_organs.json",
        "spectrum/preset_2_bars.json",
    }
    assert load_curated_visualizer_preset_manifest(
        tmp_path / "release" / "main_mc.dist" / "presets" / "visualizer_modes"
    ) == {
        "spectrum/preset_1_organs.json",
        "spectrum/preset_2_bars.json",
    }
    assert not (release_root / "preset_9_stale.json").exists()
    assert (release_root / "preset_1_organs.json").read_text(encoding="utf-8") == '{"name":"Organs"}'
    assert (release_root / "preset_2_bars.json").read_text(encoding="utf-8") == '{"name":"Bars"}'


def test_is_managed_curated_preset_path_excludes_custom_slot_names() -> None:
    assert is_managed_curated_preset_path(Path("spectrum/preset_2_organs.json")) is True
    assert is_managed_curated_preset_path(Path("spectrum/preset_4_custom.json")) is False
