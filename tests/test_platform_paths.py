"""Per-OS base directories: Windows resolution is frozen, Linux follows XDG.

Both branches are selected through ``core.platform_paths.IS_WINDOWS`` so this
file proves each contract on either operating system.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core import platform_paths


_ENV = ("APPDATA", "PROGRAMDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for name in _ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return monkeypatch


def test_windows_roots_keep_historical_resolution(clean_env, tmp_path):
    clean_env.setattr(platform_paths, "IS_WINDOWS", True)

    assert platform_paths.user_roaming_root() == (tmp_path / "AppData" / "Roaming").resolve()
    assert platform_paths.machine_shared_root() == Path(r"C:\ProgramData")
    assert platform_paths.configured_machine_shared_root() is None
    assert platform_paths.user_local_root() is None

    clean_env.setenv("APPDATA", r"D:\Roam")
    clean_env.setenv("PROGRAMDATA", r"D:\PD")
    clean_env.setenv("LOCALAPPDATA", r"D:\Local")
    # XDG variables never influence Windows.
    clean_env.setenv("XDG_CONFIG_HOME", "/xdg/config")
    assert platform_paths.user_roaming_root() == Path(r"D:\Roam")
    assert platform_paths.machine_shared_root() == Path(r"D:\PD")
    assert platform_paths.configured_machine_shared_root() == Path(r"D:\PD")
    assert platform_paths.user_local_root() == Path(r"D:\Local")


def test_linux_roots_follow_xdg_and_ignore_windows_variables(clean_env, tmp_path):
    clean_env.setattr(platform_paths, "IS_WINDOWS", False)
    clean_env.setenv("APPDATA", r"C:\Should\Not\Matter")
    clean_env.setenv("PROGRAMDATA", r"C:\Should\Not\Matter")

    assert platform_paths.user_roaming_root() == (tmp_path / ".config").resolve()
    assert platform_paths.machine_shared_root() == (tmp_path / ".local" / "share").resolve()
    assert platform_paths.configured_machine_shared_root() == (tmp_path / ".local" / "share").resolve()
    assert platform_paths.user_local_root() == (tmp_path / ".local" / "state").resolve()

    clean_env.setenv("XDG_CONFIG_HOME", "/xdg/config")
    clean_env.setenv("XDG_DATA_HOME", "relative/is/ignored")
    clean_env.setenv("XDG_STATE_HOME", "/xdg/state")
    assert platform_paths.user_roaming_root() == Path("/xdg/config")
    assert platform_paths.machine_shared_root() == (tmp_path / ".local" / "share").resolve()
    assert platform_paths.user_local_root() == Path("/xdg/state")


def test_settings_and_data_roots_derive_from_the_platform_owner(clean_env, tmp_path):
    from core.settings import json_store, storage_paths

    clean_env.setattr(platform_paths, "IS_WINDOWS", False)
    storage_paths.reset_module_cache()
    try:
        assert json_store._default_appdata_dir() == (tmp_path / ".config").resolve()
        assert storage_paths.resolve_app_data_dir("Screensaver") == (tmp_path / ".config" / "SRPSS").resolve()
    finally:
        storage_paths.reset_module_cache()
