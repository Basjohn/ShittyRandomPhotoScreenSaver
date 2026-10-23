"""An isolated SettingsManager owns every Settings-side storage path.

``APPDATA`` points at a separate "real profile" directory in each test; any
file appearing there is a leak through profile-name resolution.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.settings import storage_paths
from core.settings.storage_paths import StorageRoot


@pytest.fixture
def real_profile(tmp_path, monkeypatch) -> Path:
    real = tmp_path / "real_appdata"
    real.mkdir()
    monkeypatch.setenv("APPDATA", str(real))
    storage_paths.reset_module_cache()
    yield real
    storage_paths.reset_module_cache()


@pytest.fixture
def isolated_settings(tmp_path):
    from core.settings import SettingsManager

    return SettingsManager(
        organization="Test",
        application=f"StorageRoot_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path / "isolated",
    )


def _files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*") if path.is_file()]


def test_storage_root_overrides_profile_resolution(real_profile, tmp_path) -> None:
    root = StorageRoot(tmp_path / "explicit")

    assert storage_paths.get_app_data_dir(root) == root.app_data_dir.resolve()
    assert storage_paths.get_steam_credential_meta_file(root).is_relative_to(root.app_data_dir.resolve())
    assert storage_paths.get_steam_cache_dir(root, "profile_x").is_relative_to(root.app_data_dir.resolve())
    # An explicit root never becomes the process's cached profile resolution.
    assert storage_paths.resolve_app_data_dir() == (real_profile / "SRPSS").resolve()
    assert _files(real_profile) == []


def test_isolated_manager_exposes_its_settings_directory_as_storage_root(
    real_profile, isolated_settings
) -> None:
    root = isolated_settings.get_storage_root()

    assert root == StorageRoot(isolated_settings.get_settings_dir())
    assert storage_paths.get_steam_dir(root).is_relative_to(isolated_settings.get_settings_dir())
    assert _files(real_profile) == []


def test_steam_settings_tab_reads_and_writes_only_the_isolated_root(
    real_profile, isolated_settings
) -> None:
    from core.steam.credentials import (
        SteamCredentialPayload,
        read_credential_metadata,
        write_credential_metadata,
    )
    from ui.tabs import widgets_tab_steam

    tab = SimpleNamespace(_settings=isolated_settings)
    profile = widgets_tab_steam._steam_storage_profile(tab)
    assert profile == isolated_settings.get_storage_root()

    credential = SteamCredentialPayload(api_key="k" * 32, profile_identifier="76561197960287930")
    meta_path = write_credential_metadata(credential, profile=profile)
    assert meta_path.is_relative_to(isolated_settings.get_settings_dir())
    assert read_credential_metadata(profile=profile) is not None
    # The production resolution sees nothing: the isolated write did not leak.
    assert read_credential_metadata() is None

    controller = widgets_tab_steam._steam_connection_controller(tab)
    controller.disconnect()
    assert not meta_path.exists()
    assert _files(real_profile) == []


def test_production_settings_keep_canonical_steam_resolution() -> None:
    from ui.tabs import widgets_tab_steam

    class _ProductionSettings:
        def get_storage_root(self):
            return None

    assert widgets_tab_steam._steam_storage_profile(SimpleNamespace(_settings=_ProductionSettings())) is None
    assert widgets_tab_steam._steam_storage_profile(SimpleNamespace()) is None


def test_guided_setup_account_hints_use_the_isolated_root(
    real_profile, isolated_settings
) -> None:
    from ui.onboarding.state import saved_account_states

    gmail_marker = real_profile / "SRPSS" / "gmail_imap_creds.enc"
    gmail_marker.parent.mkdir(parents=True)
    gmail_marker.write_bytes(b"real")

    assert saved_account_states(isolated_settings)["gmail"] is False

    (isolated_settings.get_settings_dir() / "gmail_imap_creds.enc").write_bytes(b"isolated")
    assert saved_account_states(isolated_settings)["gmail"] is True


def test_cache_maintenance_targets_the_data_root_not_the_settings_folder(real_profile, isolated_settings) -> None:
    from ui.tabs.widgets_tab_defaults import _cache_data_root

    class _McSettings:
        def get_storage_root(self):
            return None  # Production manager, e.g. Screensaver_MC with settings in SRPSS_MC.

    assert _cache_data_root(SimpleNamespace(_settings=_McSettings())) == (real_profile / "SRPSS").resolve()
    assert _cache_data_root(SimpleNamespace(_settings=isolated_settings)) == (
        isolated_settings.get_settings_dir().resolve()
    )
