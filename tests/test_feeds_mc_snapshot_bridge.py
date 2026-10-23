"""D3: MC's pre-shared-root Feeds snapshots move into the shared data root once."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.feeds import mc_snapshot_bridge
from core.feeds.mc_snapshot_bridge import adopt_mc_feed_snapshots


def _write(path: Path, text: str, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    os.utime(path, (mtime, mtime))


@pytest.fixture(autouse=True)
def _fresh_once_guard(monkeypatch):
    monkeypatch.setattr(mc_snapshot_bridge, "_ATTEMPTED", False)


def test_disjoint_and_colliding_files_merge_with_newer_winning(tmp_path) -> None:
    source, target = tmp_path / "mc", tmp_path / "shared"
    _write(source / "only_mc.json", "mc", 100.0)
    _write(source / "artwork" / "a.png", "mc-art", 100.0)
    _write(source / "mc_newer.json", "mc-new", 300.0)
    _write(target / "mc_newer.json", "shared-old", 200.0)
    _write(source / "shared_newer.json", "mc-old", 200.0)
    _write(target / "shared_newer.json", "shared-new", 300.0)
    _write(target / "only_shared.json", "shared", 100.0)

    result = adopt_mc_feed_snapshots(source, target)

    assert (result.moved, result.replaced, result.discarded_older, result.failed) == (2, 1, 1, 0)
    assert (target / "only_mc.json").read_text() == "mc"
    assert (target / "artwork" / "a.png").read_text() == "mc-art"
    assert (target / "mc_newer.json").read_text() == "mc-new"
    assert (target / "shared_newer.json").read_text() == "shared-new"
    assert (target / "only_shared.json").read_text() == "shared"
    assert not source.exists()
    # Idempotent: a rerun finds nothing to do.
    assert adopt_mc_feed_snapshots(source, target) == mc_snapshot_bridge.AdoptionResult()


def test_failed_file_stays_for_the_next_process(tmp_path, monkeypatch) -> None:
    source, target = tmp_path / "mc", tmp_path / "shared"
    _write(source / "stuck.json", "mc", 100.0)
    _write(source / "fine.json", "mc", 100.0)
    real_replace = os.replace

    def flaky(src, dst):
        if Path(src).name == "stuck.json":
            raise PermissionError("in use")
        return real_replace(src, dst)

    monkeypatch.setattr(mc_snapshot_bridge.os, "replace", flaky)
    result = adopt_mc_feed_snapshots(source, target)
    assert (result.moved, result.failed) == (1, 1)
    assert (source / "stuck.json").exists() and (target / "fine.json").exists()

    monkeypatch.setattr(mc_snapshot_bridge.os, "replace", real_replace)
    assert adopt_mc_feed_snapshots(source, target).moved == 1
    assert not source.exists()


def test_canonical_bridge_runs_once_and_never_touches_per_profile_files(tmp_path) -> None:
    mc = tmp_path / "SRPSS_MC"
    _write(mc / "cache" / "feeds" / "news_x.json", "mc", 100.0)
    _write(mc / "settings_v2.json", "settings", 100.0)
    _write(mc / "banned_images" / "v1" / ".active", "", 100.0)
    (mc / "steam").mkdir()
    shared_feeds = tmp_path / "SRPSS" / "cache" / "feeds"
    shared_feeds.mkdir(parents=True)

    mc_snapshot_bridge.adopt_canonical_mc_feed_snapshots_once(shared_feeds)

    assert (shared_feeds / "news_x.json").read_text() == "mc"
    assert not (mc / "cache").exists() and not (mc / "steam").exists()
    assert (mc / "settings_v2.json").exists() and (mc / "banned_images" / "v1" / ".active").exists()

    _write(mc / "cache" / "feeds" / "late.json", "late", 100.0)
    mc_snapshot_bridge.adopt_canonical_mc_feed_snapshots_once(shared_feeds)
    assert not (shared_feeds / "late.json").exists()  # Once per process.


def test_relocated_or_isolated_roots_never_reach_a_profile_folder(tmp_path) -> None:
    mc = tmp_path / "SRPSS_MC"
    _write(mc / "cache" / "feeds" / "news_x.json", "mc", 100.0)
    isolated = tmp_path / "isolated" / "cache" / "feeds"
    isolated.mkdir(parents=True)

    mc_snapshot_bridge.adopt_canonical_mc_feed_snapshots_once(isolated)

    assert (mc / "cache" / "feeds" / "news_x.json").exists()
    assert not any(isolated.iterdir())


def test_default_feed_store_adopts_from_its_own_base(tmp_path, monkeypatch) -> None:
    from core.feeds.cache import FeedCacheStore
    from core.settings import storage_paths

    monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_path)
    storage_paths.reset_module_cache()
    try:
        _write(tmp_path / "SRPSS_MC" / "cache" / "feeds" / "news_x.json", "mc", 100.0)
        store = FeedCacheStore()
        assert (store.root / "news_x.json").read_text() == "mc"
        explicit = FeedCacheStore(tmp_path / "explicit")
        assert not any(explicit.root.iterdir())
    finally:
        storage_paths.reset_module_cache()
