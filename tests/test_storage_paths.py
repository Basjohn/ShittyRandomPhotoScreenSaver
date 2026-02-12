"""Tests for core.settings.storage_paths — canonical path resolver and migration.

Covers:
- Path resolution under custom base dirs (test isolation)
- Directory creation on first access
- File migration (old → new, skip if exists)
- Directory migration (old → new, skip existing files)
- run_all_migrations end-to-end
- Module cache reset
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from core.settings import storage_paths


@pytest.fixture(autouse=True)
def _reset_module_cache():
    """Ensure module-level cache is clean before/after each test."""
    storage_paths.reset_module_cache()
    yield
    storage_paths.reset_module_cache()


@pytest.fixture
def tmp_base(tmp_path: Path) -> Path:
    """Provide a temporary base directory simulating %APPDATA%."""
    return tmp_path


# ------------------------------------------------------------------
# Phase 1: Path resolution
# ------------------------------------------------------------------

class TestPathResolution:
    def test_get_app_data_dir_creates_folder(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        d = storage_paths.get_app_data_dir("Screensaver")
        assert d.exists()
        assert d.name == "SRPSS"

    def test_get_app_data_dir_mc_profile(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        d = storage_paths.get_app_data_dir("Screensaver_MC")
        assert d.exists()
        assert d.name == "SRPSS_MC"

    def test_get_app_data_dir_unknown_profile(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        d = storage_paths.get_app_data_dir("TestProfile123")
        assert d.exists()
        assert "SRPSS_profiles" in str(d)
        assert "TestProfile123" in str(d)

    def test_get_cache_dir(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        d = storage_paths.get_cache_dir("Screensaver")
        assert d.exists()
        assert d.name == "cache"
        assert d.parent.name == "SRPSS"

    def test_get_rss_cache_dir(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        d = storage_paths.get_rss_cache_dir("Screensaver")
        assert d.exists()
        assert d.name == "rss"

    def test_get_imgur_cache_dir(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        d = storage_paths.get_imgur_cache_dir("Screensaver")
        assert d.exists()
        assert d.name == "imgur"

    def test_get_weather_cache_file(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        f = storage_paths.get_weather_cache_file("Screensaver")
        assert f.name == "weather.json"
        assert f.parent.name == "cache"

    def test_get_state_dir(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        d = storage_paths.get_state_dir("Screensaver")
        assert d.exists()
        assert d.name == "state"

    def test_get_feed_health_file(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        f = storage_paths.get_feed_health_file("Screensaver")
        assert f.name == "feed_health.json"
        assert f.parent.name == "state"

    def test_module_cache_reused(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        d1 = storage_paths.get_app_data_dir("Screensaver")
        d2 = storage_paths.get_app_data_dir("Screensaver")
        assert d1 == d2


# ------------------------------------------------------------------
# Phase 2: File migration
# ------------------------------------------------------------------

class TestFileMigration:
    def test_migrate_file_copies(self, tmp_path: Path):
        old = tmp_path / "old" / "data.json"
        old.parent.mkdir(parents=True)
        old.write_text('{"key": "value"}')
        new = tmp_path / "new" / "data.json"

        result = storage_paths.migrate_file(old, new)
        assert result is True
        assert new.exists()
        assert json.loads(new.read_text()) == {"key": "value"}
        assert old.exists()  # old NOT deleted

    def test_migrate_file_skips_if_target_exists(self, tmp_path: Path):
        old = tmp_path / "old.json"
        old.write_text("old_content")
        new = tmp_path / "new.json"
        new.write_text("new_content")

        result = storage_paths.migrate_file(old, new)
        assert result is False
        assert new.read_text() == "new_content"  # not overwritten

    def test_migrate_file_noop_if_missing(self, tmp_path: Path):
        old = tmp_path / "nonexistent.json"
        new = tmp_path / "dest.json"
        result = storage_paths.migrate_file(old, new)
        assert result is False
        assert not new.exists()


# ------------------------------------------------------------------
# Phase 3: Directory migration
# ------------------------------------------------------------------

class TestDirectoryMigration:
    def test_migrate_directory_copies_files(self, tmp_path: Path):
        old_dir = tmp_path / "old_cache"
        old_dir.mkdir()
        (old_dir / "img1.jpg").write_bytes(b"\xff\xd8\xff")
        (old_dir / "img2.png").write_bytes(b"\x89PNG")

        new_dir = tmp_path / "new_cache"
        count = storage_paths.migrate_directory(old_dir, new_dir)
        assert count == 2
        assert (new_dir / "img1.jpg").exists()
        assert (new_dir / "img2.png").exists()

    def test_migrate_directory_skips_existing(self, tmp_path: Path):
        old_dir = tmp_path / "old"
        old_dir.mkdir()
        (old_dir / "a.txt").write_text("old_a")

        new_dir = tmp_path / "new"
        new_dir.mkdir()
        (new_dir / "a.txt").write_text("new_a")

        count = storage_paths.migrate_directory(old_dir, new_dir)
        assert count == 0
        assert (new_dir / "a.txt").read_text() == "new_a"  # not overwritten

    def test_migrate_directory_noop_if_missing(self, tmp_path: Path):
        old_dir = tmp_path / "nonexistent"
        new_dir = tmp_path / "dest"
        count = storage_paths.migrate_directory(old_dir, new_dir)
        assert count == 0

    def test_migrate_directory_remove_old(self, tmp_path: Path):
        old_dir = tmp_path / "old"
        old_dir.mkdir()
        (old_dir / "f.txt").write_text("data")

        new_dir = tmp_path / "new"
        count = storage_paths.migrate_directory(old_dir, new_dir, remove_old=True)
        assert count == 1
        assert not old_dir.exists()


# ------------------------------------------------------------------
# Phase 4: run_all_migrations end-to-end
# ------------------------------------------------------------------

class TestRunAllMigrations:
    def test_migrates_all_legacy_paths(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_path / "appdata")

        # Simulate legacy %TEMP% paths
        fake_temp = tmp_path / "fake_temp"
        fake_temp.mkdir()
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_temp))

        # Create legacy RSS cache
        rss_old = fake_temp / "screensaver_rss_cache"
        rss_old.mkdir()
        (rss_old / "img.jpg").write_bytes(b"\xff")

        # Create legacy feed health
        health_old = fake_temp / "srpss_feed_health.json"
        health_old.write_text('{"url": {"failures": 2}}')

        # Create legacy weather cache
        weather_old = fake_temp / "screensaver_weather_cache.json"
        weather_old.write_text('{"cached": true}')

        # Create legacy imgur cache
        imgur_old = fake_temp / "imgur_cache"
        imgur_old.mkdir()
        (imgur_old / "pic.png").write_bytes(b"\x89")

        storage_paths.run_all_migrations("Screensaver")

        # Verify new paths
        app_dir = tmp_path / "appdata" / "SRPSS"
        assert (app_dir / "cache" / "rss" / "img.jpg").exists()
        assert (app_dir / "state" / "feed_health.json").exists()
        assert json.loads((app_dir / "state" / "feed_health.json").read_text()) == {"url": {"failures": 2}}
        assert (app_dir / "cache" / "weather.json").exists()
        assert (app_dir / "cache" / "imgur" / "pic.png").exists()

    def test_idempotent(self, tmp_path: Path, monkeypatch):
        """Calling run_all_migrations twice should not fail or duplicate."""
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_path / "appdata")
        fake_temp = tmp_path / "fake_temp"
        fake_temp.mkdir()
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(fake_temp))

        health_old = fake_temp / "srpss_feed_health.json"
        health_old.write_text('{"test": 1}')

        storage_paths.run_all_migrations("Screensaver")
        storage_paths.reset_module_cache()
        storage_paths.run_all_migrations("Screensaver")

        health_new = tmp_path / "appdata" / "SRPSS" / "state" / "feed_health.json"
        assert health_new.exists()
        assert json.loads(health_new.read_text()) == {"test": 1}
