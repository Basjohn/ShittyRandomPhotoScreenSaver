"""Tests for the canonical ``core.settings.storage_paths`` resolver.

Retired pre-canonical TEMP storage migrations are no longer supported. Current
path authority and engine startup must remain free of those historical names
and migration helpers.
"""
from __future__ import annotations

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

    def test_mc_profile_shares_the_data_root_but_keeps_its_settings_folder(self, tmp_base: Path, monkeypatch):
        from core.settings.json_store import determine_storage_path

        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        normal = storage_paths.get_app_data_dir("Screensaver")
        storage_paths.reset_module_cache()
        mc = storage_paths.get_app_data_dir("Screensaver_MC")
        assert mc == normal and mc.name == "SRPSS"
        for getter in (storage_paths.get_cache_dir, storage_paths.get_state_dir,
                       storage_paths.get_feed_cache_dir, storage_paths.get_steam_dir):
            assert getter("Screensaver_MC") == getter("Screensaver")
        assert storage_paths.get_steam_cache_dir("Screensaver_MC", "profile_x").is_relative_to(normal)
        assert not (tmp_base / "SRPSS_MC").exists()
        settings = determine_storage_path("Screensaver_MC", base_dir=tmp_base)
        assert settings.parent.name == "SRPSS_MC"

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

    def test_get_feed_cache_dir(self, tmp_base: Path, monkeypatch):
        monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_base)
        d = storage_paths.get_feed_cache_dir("Screensaver")
        assert d.exists()
        assert d.name == "feeds"
        assert d.parent.name == "cache"

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


def test_current_storage_owners_have_no_retired_temp_migration_surface() -> None:
    source = Path(storage_paths.__file__).read_text(encoding="utf-8")
    engine_source = Path("engine/screensaver_engine.py").read_text(encoding="utf-8")
    retired_names = (
        "screensaver_rss_cache",
        "srpss_feed_health.json",
        "screensaver_weather_cache.json",
        "storage_path_input_compat",
        "run_legacy_storage_path_imports",
    )
    for retired in retired_names:
        assert retired not in source
        assert retired not in engine_source
    assert "run_all_migrations" not in source
    assert "migrate_file" not in source
    assert "migrate_directory" not in source


def test_feed_snapshots_and_artwork_use_the_shared_data_root_under_mc(tmp_path, monkeypatch):
    import sys
    from core.feeds.cache import FeedCacheStore

    monkeypatch.setattr(storage_paths, "_appdata_root", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", ["main_mc.py"])
    assert storage_paths.detect_current_profile() == "Screensaver_MC"

    assert FeedCacheStore().root == tmp_path.resolve() / "SRPSS" / "cache" / "feeds"
    assert not (tmp_path / "SRPSS_MC").exists()
    for module in ("core/feeds/cache.py", "widgets/feed_runtime.py"):
        assert "detect_current_profile" not in Path(module).read_text(encoding="utf-8")
