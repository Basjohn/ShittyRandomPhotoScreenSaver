"""Integration tests for the JSON-backed SettingsManager."""

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

import pytest

from core.settings.settings_manager import SettingsManager


def _make_manager(tmp_path: Path, *, base_dir: Path | None = None) -> SettingsManager:
    """Create a SettingsManager that stores JSON under a temp directory."""
    storage_base = base_dir or (tmp_path / uuid.uuid4().hex)
    return SettingsManager(
        organization="TestOrg",
        application=f"TestApp_{uuid.uuid4().hex}",
        storage_base_dir=storage_base,
    )


class TestSettingsManagerBasics:
    def test_init_creates_instance(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        assert manager is not None

    def test_get_returns_default_for_missing_key(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        assert manager.get("nonexistent.key", "default_value") == "default_value"

    def test_set_and_get_string(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        manager.set("test.key", "test_value")
        assert manager.get("test.key") == "test_value"

    def test_set_and_get_integer(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        manager.set("test.number", 42)
        assert manager.get("test.number") == 42

    def test_set_and_get_boolean(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        manager.set("test.flag", True)
        assert manager.get("test.flag") is True

    def test_set_and_get_dict(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        payload = {"nested": {"key": "value"}, "list": [1, 2, 3]}
        manager.set("test.config", payload)
        assert manager.get("test.config") == payload

    def test_save_and_reload_from_disk(self, tmp_path: Path) -> None:
        storage_root = tmp_path / "settings"
        app_name = f"TestApp_{uuid.uuid4().hex}"
        manager = SettingsManager(
            organization="TestOrg",
            application=app_name,
            storage_base_dir=storage_root,
        )
        manager.set("persist.key", "value123")
        manager.save()

        # New manager pointing at same storage with same app name should see persisted value
        reloaded = SettingsManager(
            organization="TestOrg",
            application=app_name,
            storage_base_dir=storage_root,
        )
        assert reloaded.get("persist.key") == "value123"


class TestSettingsManagerTypeConversion:
    def test_to_bool_true_values(self) -> None:
        assert SettingsManager.to_bool(True, False) is True
        assert SettingsManager.to_bool("true", False) is True
        assert SettingsManager.to_bool("1", False) is True
        assert SettingsManager.to_bool("yes", False) is True
        assert SettingsManager.to_bool(1, False) is True

    def test_to_bool_false_values(self) -> None:
        assert SettingsManager.to_bool(False, True) is False
        assert SettingsManager.to_bool("false", True) is False
        assert SettingsManager.to_bool("0", True) is False
        assert SettingsManager.to_bool("no", True) is False
        assert SettingsManager.to_bool(0, True) is False

    def test_to_bool_default_on_none(self) -> None:
        assert SettingsManager.to_bool(None, True) is True
        assert SettingsManager.to_bool(None, False) is False

    def test_to_bool_default_on_invalid(self) -> None:
        assert SettingsManager.to_bool("invalid", True) is True
        assert SettingsManager.to_bool("invalid", False) is False

    def test_to_bool_with_float_values(self) -> None:
        assert SettingsManager.to_bool(1.0, False) is True
        assert SettingsManager.to_bool(0.0, True) is False


class TestSettingsManagerNestedKeys:
    def test_get_nested_key(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        manager.set("widgets", {"clock": {"enabled": True}})
        widgets = manager.get("widgets")
        assert widgets["clock"]["enabled"] is True

    def test_set_nested_key(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        config = {
            "clock": {"enabled": True},
            "weather": {"enabled": False},
        }
        manager.set("widgets", config)
        result = manager.get("widgets")
        assert result["clock"]["enabled"] is True
        assert result["weather"]["enabled"] is False


class TestSettingsManagerChangeNotifications:
    def test_settings_changed_signal_emitted(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        received: list[tuple[str, object]] = []
        manager.settings_changed.connect(lambda k, v: received.append((k, v)))
        manager.set("test.key", "new_value")
        assert received == [("test.key", "new_value")]

    def test_multiple_signal_receivers(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        received1: list[tuple[str, object]] = []
        received2: list[tuple[str, object]] = []
        manager.settings_changed.connect(lambda k, v: received1.append((k, v)))
        manager.settings_changed.connect(lambda k, v: received2.append((k, v)))
        manager.set("test.key", "value1")
        assert len(received1) == len(received2) == 1


class TestSettingsManagerThreadSafety:
    def test_concurrent_reads(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        manager.set("test.key", "value")

        results: list[str] = []
        errors: list[Exception] = []

        def reader() -> None:
            try:
                for _ in range(10):
                    results.append(manager.get("test.key", "default"))
                    time.sleep(0.001)
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors
        assert len(results) == 50

    def test_concurrent_writes(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        errors: list[Exception] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(10):
                    manager.set(f"key.{thread_id}", i)
            except Exception as exc:  # pragma: no cover - defensive
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors


class TestSettingsManagerDefaults:
    def test_default_parameter_used_when_missing(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        interval = manager.get("display.image_interval", 30)
        assert interval == 30

    def test_get_with_explicit_default(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        manager.set("existing.key", 42)
        result = manager.get("existing.key", 0)
        assert result == 42

    def test_reset_to_defaults_reapplies_mc_profile_overrides(self, tmp_path: Path) -> None:
        manager = SettingsManager(
            organization="TestOrg",
            application="Screensaver_MC",
            storage_base_dir=tmp_path / "mc_profile",
        )
        manager.set("input.hard_exit", False)
        manager.set("display.show_on_monitors", [0, 1, 2])

        manager.reset_to_defaults()

        assert manager.get("input.hard_exit") is True
        assert manager.get("display.show_on_monitors") == [1]

    def test_reset_visualizers_to_defaults_replaces_stale_visualizer_section(self, tmp_path: Path) -> None:
        from core.settings.defaults import get_default_settings
        from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

        manager = _make_manager(tmp_path)
        manager.set(
            "widgets",
            {
                "spotify_visualizer": {
                    "mode": "blob",
                    "blob_growth": 9.9,
                    "obsolete_custom_key": "remove-me",
                }
            },
        )

        manager.reset_visualizers_to_defaults()

        widgets = manager.get("widgets")
        vis = widgets["spotify_visualizer"]
        expected = normalize_visualizer_section_mapping(
            get_default_settings()["widgets"]["spotify_visualizer"],
            apply_preset_overlay=False,
        )
        assert vis == expected
        assert "obsolete_custom_key" not in vis

    def test_existing_visualizer_section_does_not_gain_bubble_semantics_marker_during_default_merge(
        self,
        tmp_path: Path,
    ) -> None:
        from core.settings.defaults import get_default_settings

        manager = _make_manager(tmp_path)
        legacy_widgets = {
            "spotify_visualizer": {
                "mode": "bubble",
                "bubble_gradient_direction": "left",
            }
        }
        manager._settings.setValue("widgets", legacy_widgets)

        manager._ensure_widgets_defaults(get_default_settings()["widgets"])

        widgets = manager.get("widgets")
        vis = widgets["spotify_visualizer"]
        assert vis["bubble_gradient_direction"] == "left"
        assert "bubble_gradient_semantics_version" not in vis


class TestSettingsManagerValidation:
    def test_validate_and_repair_handles_missing_keys(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        # Should not raise
        manager.validate_and_repair()

    def test_validate_and_repair_fixes_invalid_types(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        manager.set("timing.interval", "invalid")
        manager.validate_and_repair()
        assert isinstance(manager.get("timing.interval"), int)


class TestSettingsManagerManualFloorClamp:
    def test_validate_and_repair_clamps_global_manual_floor(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        manager.set(
            "widgets",
            {
                "spotify_visualizer": {
                    "manual_floor": 2.1,
                    "spectrum_manual_floor": 0.5,
                }
            },
        )

        repairs = manager.validate_and_repair()

        widgets = manager.get("widgets")
        assert widgets["spotify_visualizer"]["manual_floor"] == pytest.approx(1.0)
        assert "widgets.spotify_visualizer.manual_floor" in repairs

    def test_validate_and_repair_clamps_per_mode_manual_floors(self, tmp_path: Path) -> None:
        manager = _make_manager(tmp_path)
        manager.set(
            "widgets",
            {
                "spotify_visualizer": {
                    "bubble_manual_floor": 3.5,
                    "spectrum_manual_floor": 0.05,
                    "oscilloscope_manual_floor": "not_a_number",
                }
            },
        )

        repairs = manager.validate_and_repair()

        vis = manager.get("widgets")["spotify_visualizer"]
        assert vis["bubble_manual_floor"] == pytest.approx(1.0)
        assert vis["spectrum_manual_floor"] == pytest.approx(0.12)
        assert vis["oscilloscope_manual_floor"] == pytest.approx(0.12)
        assert {
            "widgets.spotify_visualizer.bubble_manual_floor",
            "widgets.spotify_visualizer.spectrum_manual_floor",
            "widgets.spotify_visualizer.oscilloscope_manual_floor",
        }.issubset(repairs.keys())
