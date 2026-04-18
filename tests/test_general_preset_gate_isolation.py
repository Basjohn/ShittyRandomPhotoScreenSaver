"""Regression guard: general preset gate must not affect visualizer preset plumbing."""

from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_preset_key
from core.settings.visualizer_preset_indices import resolve_all_preset_indices_from_mapping


def test_general_preset_gate_does_not_change_visualizer_preset_resolution(monkeypatch):
    baseline_payload = {
        "widgets.spotify_visualizer.preset_spectrum": 2,
        "widgets.spotify_visualizer.preset_bubble": 1,
        "widgets.spotify_visualizer.preset_blob": 3,
    }

    monkeypatch.delenv("SRPSS_ENABLE_GENERAL_PRESETS", raising=False)
    off_indices = resolve_all_preset_indices_from_mapping(baseline_payload)
    off_keys = [get_preset_key(mode) for mode in VISUALIZER_MODE_IDS]

    monkeypatch.setenv("SRPSS_ENABLE_GENERAL_PRESETS", "1")
    on_indices = resolve_all_preset_indices_from_mapping(baseline_payload)
    on_keys = [get_preset_key(mode) for mode in VISUALIZER_MODE_IDS]

    assert on_keys == off_keys
    assert on_indices == off_indices
