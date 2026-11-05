"""Sine Waves retired (2026-11-05): saved Sine state migrates once at the input boundary.

Bridge: ``core.settings.visualizer_retired_modes`` (recorded in
Docs/Architecture/Persisted_Input_Compatibility.md "Retired visualizer keys").
"""
from __future__ import annotations

import pytest

from core.settings.visualizer_mode_registry import (
    VISUALIZER_MODE_IDS,
    get_default_visualizer_mode_id,
    iter_visualizer_mode_descriptors,
    resolve_effective_mode,
)
from core.settings.visualizer_retired_modes import (
    is_retired_visualizer_mode,
    strip_retired_visualizer_settings,
)

# An old-input fixture: the shape a pre-retirement profile could hold (values are arbitrary).
_OLD_SINE_SECTION = {
    "mode": "sine_wave",
    "mode_activation": {"sine_wave": True, "bubble": False, "spectrum": True},
    "preset_sine_wave": 4,
    "sine_speed": 0.42,
    "sine_line_count": 3,
    "sine_line2_color": [192, 224, 255, 198],
    "sine_wave_travel": 2,
    "sine_wave_transient_width_mix": 0.32,
    "sine_wave_bar_count": 40,
}


def _sine_keys(mapping):
    return [key for key in mapping if "sine" in str(key).lower()]


def test_sine_is_no_longer_a_registered_or_selectable_mode():
    assert "sine_wave" not in VISUALIZER_MODE_IDS
    assert "sine_wave" not in {d.mode_id for d in iter_visualizer_mode_descriptors()}
    assert is_retired_visualizer_mode("sine_wave")
    assert is_retired_visualizer_mode("sine_wave.sine_speed")


def test_saved_sine_selection_migrates_to_the_default_mode_and_drops_sine_keys():
    other = {"preset_bubble": 2, "spectrum_bar_count": 48, "osc_gain": 2.0}
    cleaned = strip_retired_visualizer_settings({**_OLD_SINE_SECTION, **other})

    assert cleaned["mode"] == get_default_visualizer_mode_id()
    assert _sine_keys(cleaned) == []
    assert "sine_wave" not in cleaned["mode_activation"]
    # Negative control: every non-Sine key, other modes' preset indices included, survives untouched.
    for key, value in other.items():
        assert cleaned[key] == value
    assert cleaned["mode_activation"] == {"bubble": False, "spectrum": True}


def test_dotted_sine_keys_are_dropped_too():
    prefix = "widgets.spotify_visualizer"
    dotted = {f"{prefix}.{key}": value for key, value in _OLD_SINE_SECTION.items()}
    dotted[f"{prefix}.preset_spectrum"] = 1
    cleaned = strip_retired_visualizer_settings(dotted)
    assert cleaned[f"{prefix}.mode"] == get_default_visualizer_mode_id()
    assert cleaned[f"{prefix}.preset_spectrum"] == 1
    assert [key for key in cleaned if "sine" in key] == []


def test_bridge_is_idempotent():
    once = strip_retired_visualizer_settings(_OLD_SINE_SECTION)
    assert strip_retired_visualizer_settings(once) == once


def test_canonical_section_normalization_never_emits_sine_state():
    from core.settings.visualizer_settings_snapshot import normalize_visualizer_section_mapping

    normalized = normalize_visualizer_section_mapping(dict(_OLD_SINE_SECTION), apply_preset_overlay=False)
    assert normalized["mode"] in VISUALIZER_MODE_IDS
    assert _sine_keys(normalized) == []
    assert set(normalized["mode_activation"]) == set(VISUALIZER_MODE_IDS)
    assert normalize_visualizer_section_mapping(normalized, apply_preset_overlay=False) == normalized


def test_a_sine_only_activation_still_resolves_to_a_live_mode():
    # The stored request names a retired mode: resolution substitutes, never instantiates it.
    resolved, substituted = resolve_effective_mode("sine_wave", {"sine_wave": True})
    assert substituted is True
    assert resolved in VISUALIZER_MODE_IDS


def test_custom_cache_drops_sine_snapshots_but_still_refuses_unknown_entries():
    from core.settings.visualizer_presets import normalize_visualizer_custom_snapshot_cache

    cache = {"sine_wave": {"sine_speed": 0.5}, "sine_wave.sine_line_count": 2}
    assert normalize_visualizer_custom_snapshot_cache(cache) == {}
    # Negative control: a mode that never existed is still a malformed cache, not a silent drop.
    with pytest.raises(ValueError):
        normalize_visualizer_custom_snapshot_cache({"not_a_visualizer_mode": {}})


def test_persisted_profile_migrates_once_and_reloads_without_drift(qt_app, tmp_path):
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_presets import get_custom_preset_index

    org = "SineRetirementBridgeTest"
    manager = SettingsManager(organization=org, application="isolated", storage_base_dir=tmp_path)
    bubble_custom = get_custom_preset_index("bubble")
    raw = {**_OLD_SINE_SECTION, "preset_bubble": bubble_custom}
    manager._settings.setValue("widgets", {"spotify_visualizer": raw})
    manager._settings.setValue("visualizer_custom_presets", {"sine_wave": {"sine_speed": 0.9}})
    manager._settings.update_metadata(visualizer_schema_version=13)
    assert manager.flush(timeout=5.0)

    reloaded = SettingsManager(organization=org, application="isolated", storage_base_dir=tmp_path)
    section = reloaded.get("widgets.spotify_visualizer")
    assert section["mode"] in VISUALIZER_MODE_IDS
    assert _sine_keys(section) == []
    assert "sine_wave" not in section["mode_activation"]
    assert section["preset_bubble"] == bubble_custom
    assert "sine_wave" not in (reloaded.get("visualizer_custom_presets") or {})
    assert reloaded._settings.metadata()["visualizer_schema_version"] == SettingsManager._VISUALIZER_SCHEMA_VERSION
    assert reloaded.flush(timeout=5.0)

    again = SettingsManager(organization=org, application="isolated", storage_base_dir=tmp_path)
    assert again.get("widgets.spotify_visualizer") == section
    assert again.flush(timeout=5.0)
