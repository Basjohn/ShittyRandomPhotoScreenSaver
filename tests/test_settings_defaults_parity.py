"""Tests for canonical defaults and derived snapshot artifact parity."""
from __future__ import annotations

import json
import importlib
from pathlib import Path

import pytest

from core.settings.defaults import CANONICAL_DEFAULTS, PRESERVE_ON_RESET, get_default_settings
from core.settings.defaults_generated import DEFAULT_SETTINGS as GENERATED_DEFAULTS
from core.settings.defaults_snapshot_builder import build_defaults_snapshot
from tools import visualizer_preset_repair as repair

SNAPSHOT_JSON_PATH = Path(__file__).resolve().parents[1] / "core" / "settings" / "defaults_snapshot.json"


def _load_snapshot_json() -> dict:
    return json.loads(SNAPSHOT_JSON_PATH.read_text(encoding="utf-8"))


def _build_snapshot_with_default_gates() -> dict:
    from core.dev_gates import force_gate, is_blob_enabled

    prior_blob_gate = is_blob_enabled()
    force_gate(blob=False)
    try:
        return build_defaults_snapshot()
    finally:
        force_gate(blob=prior_blob_gate)


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

        assert shadows["enabled"] is True
        assert shadows["text_enabled"] is True
        assert shadows["header_enabled"] is True

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
        from core.dev_gates import force_gate, is_blob_enabled
        import core.settings.defaults_snapshot as defaults_snapshot_module

        prior_blob_gate = is_blob_enabled()
        force_gate(blob=False)
        try:
            reloaded = importlib.reload(defaults_snapshot_module)
            assert reloaded.DEFAULTS == _build_snapshot_with_default_gates()
        finally:
            force_gate(blob=prior_blob_gate)

    def test_snapshot_json_matches_builder_output(self):
        assert _load_snapshot_json() == _build_snapshot_with_default_gates()

    def test_snapshot_sanitizes_doc_preserved_keys(self):
        snapshot = _build_snapshot_with_default_gates()

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
        snapshot_visualizer = _build_snapshot_with_default_gates()["widgets"]["spotify_visualizer"]

        assert canonical_visualizer["enabled"] is True
        assert snapshot_visualizer["mode"] == canonical_visualizer["mode"]
        assert snapshot_visualizer["mode"] == "spectrum"
        assert snapshot_visualizer["enabled"] is True
        assert snapshot_visualizer["bubble_gradient_direction"] == canonical_visualizer["bubble_gradient_direction"]
        assert snapshot_visualizer["bubble_gradient_semantics_version"] == canonical_visualizer[
            "bubble_gradient_semantics_version"
        ]

    def test_transition_snapshot_keeps_burn_in_default_random_pool(self):
        snapshot_transitions = _build_snapshot_with_default_gates()["transitions"]
        assert snapshot_transitions["pool"]["Burn"] is True

    @pytest.mark.parametrize(
        "key",
        [
            "blob_manual_floor",
            "bubble_manual_floor",
            "oscilloscope_manual_floor",
            "sine_wave_manual_floor",
            "spectrum_manual_floor",
        ],
    )
    def test_visualizer_snapshot_manual_floors_stay_on_current_contract(self, key: str):
        snapshot_visualizer = _build_snapshot_with_default_gates()["widgets"]["spotify_visualizer"]
        assert snapshot_visualizer[key] == pytest.approx(0.12)
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
