"""Regression coverage for retired global/general preset plumbing."""

from __future__ import annotations

import uuid
from pathlib import Path

from core.settings.presets import (
    PRESET_DEFINITIONS,
    are_general_presets_enabled,
    apply_preset,
    check_and_switch_to_custom,
    get_current_preset_info,
    get_ordered_presets,
)
from core.settings.settings_manager import SettingsManager


def _make_manager(tmp_path: Path) -> SettingsManager:
    return SettingsManager(
        organization="Test",
        application=f"ScreensaverTest_{uuid.uuid4().hex}",
        storage_base_dir=tmp_path / uuid.uuid4().hex,
    )


def test_global_presets_are_always_disabled(monkeypatch):
    monkeypatch.setenv("SRPSS_ENABLE_GENERAL_PRESETS", "1")
    assert are_general_presets_enabled() is False


def test_ordered_presets_is_custom_only():
    assert get_ordered_presets() == ["custom"]


def test_apply_preset_only_accepts_custom(tmp_path: Path):
    manager = _make_manager(tmp_path)
    assert apply_preset(manager, "purist") is False
    assert apply_preset(manager, "custom") is True


def test_current_preset_info_is_stable_custom(tmp_path: Path):
    manager = _make_manager(tmp_path)
    info = get_current_preset_info(manager)
    assert info["key"] == "custom"
    assert info["name"] == PRESET_DEFINITIONS["custom"].name


def test_check_and_switch_to_custom_is_noop(tmp_path: Path):
    manager = _make_manager(tmp_path)
    assert check_and_switch_to_custom(manager) is False
