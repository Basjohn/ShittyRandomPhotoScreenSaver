from __future__ import annotations

from pathlib import Path

from core.visualizer_preset_manifest import (
    build_curated_visualizer_manifest_payload,
    is_managed_curated_preset_path,
    load_curated_visualizer_preset_manifest,
    mirror_curated_visualizer_preset_tree,
    prune_duplicate_curated_preset_slots,
    reconcile_curated_visualizer_preset_tree,
    regenerate_repo_shipped_visualizer_preset_artifacts,
    resolve_curated_visualizer_manifest_entries,
    scan_curated_visualizer_preset_tree,
    sync_curated_preset_tree,
    write_curated_visualizer_preset_manifest,
)
from tools.regenerate_visualizer_shipped_presets import audit_repo_shipped_visualizer_preset_artifacts


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


def test_reconcile_curated_preset_tree_prunes_duplicate_slots_and_rewrites_manifest(tmp_path: Path) -> None:
    root = tmp_path / "visualizer_modes"
    spectrum = root / "spectrum"
    spectrum.mkdir(parents=True)
    stale = spectrum / "preset_2_old.json"
    current = spectrum / "preset_2_new.json"
    other = spectrum / "preset_3_other.json"
    stale.write_text('{"name":"Old"}', encoding="utf-8")
    current.write_text('{"name":"New"}', encoding="utf-8")
    other.write_text('{"name":"Other"}', encoding="utf-8")

    old_time = 1_700_000_000
    new_time = old_time + 60
    stale.touch()
    current.touch()
    other.touch()
    import os

    os.utime(stale, (old_time, old_time))
    os.utime(current, (new_time, new_time))

    manifest_path = root.parent / "visualizer_modes_manifest.json"
    manifest_path.write_text(
        '{"managed_curated_files":["spectrum/preset_2_old.json"]}',
        encoding="utf-8",
    )

    resolved = reconcile_curated_visualizer_preset_tree(root, allow_non_frozen=True)

    assert stale.exists() is False
    assert current.exists() is True
    assert resolved == {"spectrum/preset_2_new.json", "spectrum/preset_3_other.json"}
    assert load_curated_visualizer_preset_manifest(root) == resolved


def test_duplicate_prune_is_frozen_or_explicit_only(tmp_path: Path) -> None:
    root = tmp_path / "visualizer_modes"
    spectrum = root / "spectrum"
    spectrum.mkdir(parents=True)
    old = spectrum / "preset_2_old.json"
    new = spectrum / "preset_2_new.json"
    old.write_text("{}", encoding="utf-8")
    new.write_text("{}", encoding="utf-8")

    assert prune_duplicate_curated_preset_slots(root) == []
    assert old.exists()
    assert new.exists()


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
    source_mode = source_root / "bubble"
    target_mode = target_root / "bubble"
    source_mode.mkdir(parents=True)
    target_mode.mkdir(parents=True)

    (source_mode / "preset_1_alpha.json").write_text('{"name":"Alpha"}', encoding="utf-8")
    (source_mode / "preset_2_beta.json").write_text('{"name":"Beta"}', encoding="utf-8")
    (source_root.parent / "visualizer_modes_manifest.json").write_text(
        '{"managed_curated_files":["bubble/preset_1_alpha.json"]}',
        encoding="utf-8",
    )
    (target_mode / "preset_1_alpha.json").write_text('{"name":"Old Alpha"}', encoding="utf-8")
    (target_mode / "preset_9_stale.json").write_text('{"name":"Stale"}', encoding="utf-8")

    mirrored = mirror_curated_visualizer_preset_tree(source_root, target_root)

    assert mirrored == {
        "bubble/preset_1_alpha.json",
        "bubble/preset_2_beta.json",
    }
    assert (target_mode / "preset_1_alpha.json").read_text(encoding="utf-8") == '{"name":"Alpha"}'
    assert (target_mode / "preset_2_beta.json").read_text(encoding="utf-8") == '{"name":"Beta"}'
    assert not (target_mode / "preset_9_stale.json").exists()
    assert load_curated_visualizer_preset_manifest(target_root) == mirrored


def test_regenerate_repo_shipped_visualizer_preset_artifacts_rebuilds_release_tree_from_source(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "presets" / "visualizer_modes" / "spectrum"
    release_root = tmp_path / "release" / "media_center" / "presets" / "visualizer_modes" / "spectrum"
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
        tmp_path / "release" / "media_center" / "presets" / "visualizer_modes"
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


def test_shipped_visualizer_preset_audit_is_read_only_and_detects_drift(tmp_path: Path) -> None:
    source_root = tmp_path / "presets" / "visualizer_modes" / "spectrum"
    source_root.mkdir(parents=True)
    source_file = source_root / "preset_1_organs.json"
    source_file.write_text('{"name":"Organs"}', encoding="utf-8")

    regenerate_repo_shipped_visualizer_preset_artifacts(tmp_path)
    source_before = source_file.read_bytes()
    release_file = (
        tmp_path
        / "release"
        / "media_center"
        / "presets"
        / "visualizer_modes"
        / "spectrum"
        / "preset_1_organs.json"
    )
    release_before = release_file.read_bytes()

    assert audit_repo_shipped_visualizer_preset_artifacts(tmp_path) == ()
    assert source_file.read_bytes() == source_before
    assert release_file.read_bytes() == release_before

    release_file.write_text('{"name":"Drift"}', encoding="utf-8")
    findings = audit_repo_shipped_visualizer_preset_artifacts(tmp_path)
    assert any("release content drift: spectrum/preset_1_organs.json" in item for item in findings)
    assert source_file.read_bytes() == source_before
