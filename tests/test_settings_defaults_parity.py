"""Tests for canonical defaults and derived snapshot artifact parity."""
from __future__ import annotations

import json
import importlib
from pathlib import Path

import pytest

from core.settings.defaults import (
    CANONICAL_DEFAULTS,
    MC_PROFILE,
    NORMAL_PROFILE,
    PRESERVE_ON_RESET,
    get_default_settings,
)
from core.settings.defaults_generated import DEFAULT_SETTINGS as GENERATED_DEFAULTS
from core.settings.defaults_snapshot_builder import build_defaults_snapshot
from tools import visualizer_preset_repair as repair

SNAPSHOT_JSON_PATH = Path(__file__).resolve().parents[1] / "core" / "settings" / "defaults_snapshot.json"


def _load_snapshot_json() -> dict:
    return json.loads(SNAPSHOT_JSON_PATH.read_text(encoding="utf-8"))


def _build_snapshot() -> dict:
    return build_defaults_snapshot()


class TestDefaultsStructure:
    """Tests for defaults structure and completeness."""

    def test_defaults_has_display_section(self):
        defaults = get_default_settings()
        assert "display" in defaults
        assert "mode" in defaults["display"]
        assert "hw_accel" in defaults["display"]

    def test_defaults_has_input_section(self):
        defaults = get_default_settings()
        assert "input" in defaults
        assert "interaction_mode" in defaults["input"]

    def test_defaults_has_queue_section(self):
        defaults = get_default_settings()
        assert "queue" in defaults
        assert "shuffle" in defaults["queue"]

    def test_defaults_has_sources_section(self):
        defaults = get_default_settings()
        assert "sources" in defaults
        assert "mode" in defaults["sources"]
        assert "local_ratio" in defaults["sources"]

    def test_defaults_has_timing_section(self):
        defaults = get_default_settings()
        assert "timing" in defaults
        assert "interval" in defaults["timing"]

    def test_defaults_has_transitions_section(self):
        defaults = get_default_settings()
        assert "transitions" in defaults
        assert "pool" in defaults["transitions"]
        assert "durations" in defaults["transitions"]

    def test_defaults_has_accessibility_section(self):
        defaults = get_default_settings()
        assert "accessibility" in defaults

    def test_defaults_has_widgets_section(self):
        defaults = get_default_settings()
        assert "widgets" in defaults

    def test_widget_shadow_defaults_use_runtime_painted_toggles_only(self):
        defaults = get_default_settings()
        widgets = defaults["widgets"]
        shadows = widgets["shadows"]

        assert isinstance(shadows["enabled"], bool)
        assert isinstance(shadows["text_enabled"], bool)
        assert isinstance(shadows["header_enabled"], bool)

        retired_keys = {"intense_shadow", "analog_shadow_intense", "digital_shadow_intense"}
        assert not retired_keys.intersection(defaults.keys())
        for section in widgets.values():
            if isinstance(section, dict):
                assert not retired_keys.intersection(section.keys())


class TestPreserveOnReset:
    """Tests for PRESERVE_ON_RESET configuration."""

    def test_preserve_on_reset_has_folders(self):
        assert "sources.folders" in PRESERVE_ON_RESET

    def test_preserve_on_reset_has_rss_feeds(self):
        assert "sources.rss_feeds" in PRESERVE_ON_RESET

    def test_preserve_on_reset_has_weather_location(self):
        assert "widgets.weather.location" in PRESERVE_ON_RESET


class TestDefaultsArtifactParity:
    """Tests for artifact derivation and visualizer-specific snapshot parity."""

    def test_generated_defaults_alias_matches_canonical_defaults(self):
        assert GENERATED_DEFAULTS == CANONICAL_DEFAULTS

    def test_snapshot_module_matches_builder_output(self):
        import core.settings.defaults_snapshot as defaults_snapshot_module

        reloaded = importlib.reload(defaults_snapshot_module)
        assert reloaded.DEFAULTS == _build_snapshot()

    def test_snapshot_json_matches_builder_output(self):
        assert _load_snapshot_json() == _build_snapshot()

    @pytest.mark.parametrize("application", [NORMAL_PROFILE, MC_PROFILE])
    def test_profile_snapshot_builder_uses_selected_canonical_defaults(self, application: str):
        snapshot = build_defaults_snapshot(application)
        canonical = get_default_settings(application)

        assert snapshot["display"] == canonical["display"]
        assert snapshot["input"] == canonical["input"]
        assert snapshot["widgets"]["gmail"] == canonical["widgets"]["gmail"]
        assert snapshot["widgets"]["media"] == canonical["widgets"]["media"]

    def test_snapshot_sanitizes_doc_preserved_keys(self):
        snapshot = _build_snapshot()

        assert snapshot["sources"]["folders"] == []
        assert snapshot["sources"]["rss_feeds"] == []
        assert snapshot["widgets"]["weather"]["location"] == ""
        assert "latitude" not in snapshot["widgets"]["weather"]
        assert "longitude" not in snapshot["widgets"]["weather"]
        assert snapshot["workers"]["fft"]["enabled"] is False

        assert "custom_preset_backup" not in snapshot
        assert "preset" not in snapshot

    def test_visualizer_snapshot_matches_canonical_mode(self):
        canonical_visualizer = get_default_settings()["widgets"]["spotify_visualizer"]
        snapshot_visualizer = _build_snapshot()["widgets"]["spotify_visualizer"]

        assert isinstance(canonical_visualizer["enabled"], bool)
        assert snapshot_visualizer["mode"] == canonical_visualizer["mode"]
        assert snapshot_visualizer["enabled"] == canonical_visualizer["enabled"]

    def test_transition_snapshot_keeps_canonical_burn_pool_choice(self):
        canonical_transitions = get_default_settings()["transitions"]
        snapshot_transitions = _build_snapshot()["transitions"]
        assert snapshot_transitions["pool"]["Burn"] == canonical_transitions["pool"]["Burn"]

    @pytest.mark.parametrize(
        "key",
        [
            "bubble_manual_floor",
            "oscilloscope_manual_floor",
            "sine_wave_manual_floor",
            "spectrum_manual_floor",
        ],
    )
    def test_visualizer_snapshot_manual_floors_stay_on_current_contract(self, key: str):
        canonical_visualizer = get_default_settings()["widgets"]["spotify_visualizer"]
        snapshot_visualizer = _build_snapshot()["widgets"]["spotify_visualizer"]
        assert snapshot_visualizer[key] == pytest.approx(canonical_visualizer[key])
        assert 0.0 <= snapshot_visualizer[key] <= 1.0
        assert "manual_floor" not in snapshot_visualizer

    def test_visualizer_preset_repair_uses_dynamic_mode_prefixes(self):
        defaults = get_default_settings()["widgets"]["spotify_visualizer"]
        mode = "devcurve"
        prefix = repair._canonical_mode_prefix(mode)
        assert prefix == "devcurve_"
        for suffix in repair._MANDATORY_TECH_SUFFIXES:
            assert f"{prefix}{suffix}" in defaults


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
