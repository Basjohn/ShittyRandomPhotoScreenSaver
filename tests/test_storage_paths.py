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
