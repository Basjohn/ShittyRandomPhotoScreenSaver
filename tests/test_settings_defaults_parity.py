"""Tests for canonical defaults and derived snapshot artifact parity."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.settings.defaults import CANONICAL_DEFAULTS, PRESERVE_ON_RESET, get_default_settings
from core.settings.defaults_generated import DEFAULT_SETTINGS as GENERATED_DEFAULTS
from core.settings.defaults_snapshot import DEFAULTS as SNAPSHOT_DEFAULTS
from core.settings.defaults_snapshot_builder import build_defaults_snapshot
from tools import visualizer_preset_repair as repair

SNAPSHOT_JSON_PATH = Path(__file__).resolve().parents[1] / "core" / "settings" / "defaults_snapshot.json"


def _load_snapshot_json() -> dict:
    return json.loads(SNAPSHOT_JSON_PATH.read_text(encoding="utf-8"))


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
        assert "hard_exit" in defaults["input"]

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
        assert SNAPSHOT_DEFAULTS == build_defaults_snapshot()

    def test_snapshot_json_matches_builder_output(self):
        assert _load_snapshot_json() == build_defaults_snapshot()

    def test_snapshot_sanitizes_doc_preserved_keys(self):
        snapshot = build_defaults_snapshot()

        assert snapshot["sources"]["folders"] == []
        assert snapshot["sources"]["rss_feeds"] == []
        assert snapshot["widgets"]["weather"]["location"] == ""
        assert "latitude" not in snapshot["widgets"]["weather"]
        assert "longitude" not in snapshot["widgets"]["weather"]
        assert snapshot["workers"]["fft"]["enabled"] is False

        custom_backup = snapshot["custom_preset_backup"]
        for key in (
            "sources.folders",
            "sources.rss_feeds",
            "widgets.weather.location",
            "widgets.weather.latitude",
            "widgets.weather.longitude",
        ):
            assert key not in custom_backup

    def test_visualizer_snapshot_matches_canonical_mode(self):
        canonical_visualizer = get_default_settings()["widgets"]["spotify_visualizer"]
        snapshot_visualizer = build_defaults_snapshot()["widgets"]["spotify_visualizer"]

        assert canonical_visualizer["enabled"] is True
        assert snapshot_visualizer["mode"] == canonical_visualizer["mode"]
        assert snapshot_visualizer["mode"] == "spectrum"
        assert snapshot_visualizer["enabled"] is True
        assert snapshot_visualizer["bubble_gradient_direction"] == canonical_visualizer["bubble_gradient_direction"]
        assert snapshot_visualizer["bubble_gradient_semantics_version"] == canonical_visualizer[
            "bubble_gradient_semantics_version"
        ]

    def test_transition_snapshot_keeps_burn_in_default_random_pool(self):
        snapshot_transitions = build_defaults_snapshot()["transitions"]
        assert snapshot_transitions["pool"]["Burn"] is True

    @pytest.mark.parametrize(
        "key",
        [
            "manual_floor",
            "blob_manual_floor",
            "bubble_manual_floor",
            "oscilloscope_manual_floor",
            "sine_wave_manual_floor",
            "spectrum_manual_floor",
        ],
    )
    def test_visualizer_snapshot_manual_floors_stay_on_current_contract(self, key: str):
        snapshot_visualizer = build_defaults_snapshot()["widgets"]["spotify_visualizer"]
        assert snapshot_visualizer[key] == pytest.approx(0.12)

    def test_visualizer_preset_repair_only_requires_keys_that_exist_in_canonical_defaults(self):
        defaults = get_default_settings()["widgets"]["spotify_visualizer"]

        for mode in repair._MODE_TECH_PREFIXES:
            required = repair._required_repair_default_keys_for_mode(mode)
            assert required
            assert required.issubset(defaults.keys()), (
                "visualizer_preset_repair derived keys missing from canonical defaults "
                f"for {mode}: {sorted(required - set(defaults.keys()))}"
            )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
