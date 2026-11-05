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
