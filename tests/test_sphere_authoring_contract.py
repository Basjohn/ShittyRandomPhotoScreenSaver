"""Sphere authoring crosses canonical Settings, shared source and the real lazy UI."""
from __future__ import annotations

from copy import deepcopy

import pytest


@pytest.mark.parametrize("flat", (False, True))
def test_legacy_sst_cache_uses_incoming_raw_profile_before_normalizing_any_section(tmp_path, flat):
    import json
    from core.settings.settings_manager import SettingsManager
    from core.settings.sst_io import import_from_sst, normalize_sst_snapshot

    raw = {"spectrum_bar_count": 51, "spectrum_sensitivity": .79, "spectrum_mirrored": False,
           "spectrum_notch_positions_linear": [[0., "Bass"], [.2371, "Low"], [.47, "Mid"], [.7693, "High"], [1., "End"]]}
    root = {"visualizer_custom_presets": {"sphere": {"sphere_fill_color": [23, 34, 45, 79]}}}
    if flat:
        root.update({f"widgets.spotify_visualizer.{key}": value for key, value in raw.items()})
    else:
        root["widgets"] = {"spotify_visualizer": raw}
    normalized = normalize_sst_snapshot(root)
    cached = normalized["visualizer_custom_presets"]["sphere"]
    assert cached["sphere_bar_count"] == 51
    assert cached["sphere_sensitivity"] == pytest.approx(.79)
    assert [item[0] for item in cached["sphere_analysis_notch_positions"]] == [0., .2371, .7693, 1.]
    path = tmp_path / "sphere.sst"
    path.write_text(json.dumps({"settings_version": 2, "snapshot": root}), encoding="utf-8")
    manager = SettingsManager(application="SphereSst", storage_base_dir=tmp_path / "store")
    assert import_from_sst(manager, str(path), merge=False)
    assert manager.get("visualizer_custom_presets")["sphere"] == cached


def test_settings_startup_seeds_raw_sphere_before_default_fill_and_reopen_is_stable(tmp_path):
    from core.settings.json_store import determine_storage_path, get_json_settings_store
    from core.settings.settings_manager import SettingsManager

    profile = "SphereRawStartup"
    path = determine_storage_path(profile, base_dir=tmp_path)
    store = get_json_settings_store(storage_path=path, profile=profile)
    store.setValue("widgets", {"spotify_visualizer": {
        "mode": "sphere", "preset_spectrum": 1,
        "spectrum_bar_count": 47, "spectrum_sensitivity": .83,
        "spectrum_mirrored": False,
        "spectrum_notch_positions_linear": [[0., "Bass"], [.1937, "Low"], [.41, "Mid"], [.7182, "High"], [1., "End"]],
        "sphere_manual_floor": .37,
    }})
    store.update_metadata(visualizer_schema_version=9)
    store.setValue("visualizer_custom_presets", {"sphere": {
        "mode": "sphere", "sphere_fill_color": [23, 34, 45, 79], "sphere_manual_floor": .29,
    }})
    # This test represents a pre-existing on-disk profile. ``sync()`` is only
    # asynchronous admission; force the durability boundary before constructing
    # the new manager so startup cannot race the fixture writer on Windows.
    assert store.flush(timeout=5.0)
    manager = SettingsManager(application=profile, storage_base_dir=tmp_path)
    first = manager.get("widgets.spotify_visualizer")
    assert first["sphere_bar_count"] == 47
    assert first["sphere_sensitivity"] == pytest.approx(.83)
    assert first["sphere_manual_floor"] == pytest.approx(.37)
    assert [item[0] for item in first["sphere_analysis_notch_positions"]] == [0., .1937, .7182, 1.]
    cached = manager.get("visualizer_custom_presets")["sphere"]
    assert cached["sphere_bar_count"] == 47
    assert cached["sphere_sensitivity"] == pytest.approx(.83)
    assert cached["sphere_manual_floor"] == pytest.approx(.29)
    assert cached["sphere_fill_color"] == [23, 34, 45, 79]
    assert cached["sphere_analysis_notch_positions"] == first["sphere_analysis_notch_positions"]
    manager.set("widgets.spotify_visualizer.spectrum_bar_count", 8)
    manager.set("widgets.spotify_visualizer.preset_spectrum", 0)
    reopened = SettingsManager(application=profile, storage_base_dir=tmp_path)
    second = reopened.get("widgets.spotify_visualizer")
    assert second["sphere_bar_count"] == 47
    assert second["sphere_analysis_notch_positions"] == first["sphere_analysis_notch_positions"]


def test_visualizer_reset_persists_canonical_sphere_owned_state_without_resetting_other_widgets(tmp_path):
    from core.settings.settings_manager import SettingsManager
    from core.settings.defaults import get_default_settings

    profile = "SphereReset"
    manager = SettingsManager(application=profile, storage_base_dir=tmp_path)
    manager.set("widgets.media.show_artwork", False)
    media_before = manager.get("widgets.media")
    for key, value in {
        "sphere_bar_count": 57, "sphere_fill_color": [12, 23, 34, 79],
        "sphere_edge_color": [45, 56, 67, 113],
        "sphere_taste_the_rainbow_speed": .173, "sphere_taste_the_rainbow_extent": .81,
        "sphere_analysis_notch_positions": [[0., "Bass"], [.19, "Mid"], [.73, "Treble"], [1., "End"]],
    }.items():
        manager.set(f"widgets.spotify_visualizer.{key}", value)
    manager.reset_visualizers_to_defaults()
    assert manager.flush()
    reopened = SettingsManager(application=profile, storage_base_dir=tmp_path)
    canonical = get_default_settings(profile)["widgets"]["spotify_visualizer"]
    actual = reopened.get("widgets.spotify_visualizer")
    assert {key: value for key, value in actual.items() if key.startswith("sphere_")} == {key: value for key, value in canonical.items() if key.startswith("sphere_")}
    assert reopened.get("widgets.media") == media_before


@pytest.mark.parametrize("dotted", (False, True))
def test_old_sphere_profile_copies_raw_spectrum_once_and_preserves_explicit_values(dotted):
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    from core.settings.visualizer_settings_contract import migrate_profile_lender_owned_settings

    prefix = "widgets.spotify_visualizer." if dotted else ""
    source = {
        prefix + "mode": "sphere", prefix + "preset_spectrum": 1,
        prefix + "spectrum_bar_count": 47, prefix + "spectrum_sensitivity": .83,
        prefix + "spectrum_input_gain": 1.24, prefix + "spectrum_mirrored": False,
        prefix + "spectrum_notch_positions_linear": [[0., "Bass"], [.1937, "Low"], [.41, "Mid"], [.7182, "High"], [1., "End"]],
        prefix + "sphere_manual_floor": .37,
    }
    migrated = migrate_profile_lender_owned_settings(source)
    assert migrated["sphere_bar_count"] == 47
    assert migrated["sphere_sensitivity"] == pytest.approx(.83)
    assert migrated["sphere_input_gain"] == pytest.approx(1.24)
    assert migrated[prefix + "sphere_manual_floor"] == pytest.approx(.37)
    assert [entry[0] for entry in migrated["sphere_analysis_notch_positions"]] == [0., .1937, .7182, 1.]
    owned = set(get_owned_mode_setting_keys("sphere", "technical").values())
    assert owned == {"sphere_" + key for key in (
        "bar_count", "audio_block_size", "adaptive_sensitivity", "sensitivity",
        "dynamic_floor", "manual_floor", "input_gain", "transient_clamp",
    )}
    changed = {**migrated, prefix + "spectrum_bar_count": 12, prefix + "preset_spectrum": 0}
    assert migrate_profile_lender_owned_settings(changed) == changed


def test_owned_source_and_complete_worker_profile_ignore_mutable_spectrum_settings():
    from core.settings.models import SpotifyVisualizerSettings
    from core.settings.visualizer_presets import get_custom_preset_index
    from widgets.spotify_visualizer.source_config_applier import resolve_mode_source_config
    from widgets.spotify_visualizer.technical_config import build_technical_cache, resolve_technical_config

    config = {
        "mode": "sphere", "preset_sphere": get_custom_preset_index("sphere"),
        "sphere_bar_count": 53, "sphere_adaptive_sensitivity": False, "sphere_sensitivity": .71,
        "sphere_input_gain": .63, "sphere_transient_clamp": .92,
        "sphere_analysis_notch_positions": [[0., "Bass"], [.23, "Mid"], [.61, "High"], [1., "End"]],
    }
    first = SpotifyVisualizerSettings.from_mapping(config, apply_preset_overlay=False, resolve_preset_indices=False)
    second = SpotifyVisualizerSettings.from_mapping({**config,
        "spectrum_bar_count": 8, "spectrum_input_gain": 1.8, "spectrum_agc_strength": .91,
        "spectrum_dynamic_range_enabled": True, "spectrum_sensitivity": 2.1,
        "spectrum_lane_transient_mix": .01, "spectrum_mirrored": False,
        "spectrum_notch_positions_linear": [[0., "Bass"], [.06, "Mid"], [.93, "High"], [1., "End"]],
    }, apply_preset_overlay=False, resolve_preset_indices=False)
    assert resolve_technical_config(build_technical_cache(None, first), "sphere") == resolve_technical_config(build_technical_cache(None, second), "sphere")
    first_source = resolve_mode_source_config("sphere", vars(first))
    second_source = resolve_mode_source_config("sphere", vars(second))
    from widgets.spotify_visualizer.source_config_applier import SPECTRUM_SOURCE_CONFIG_KEYS
    assert first_source["_source_spectrum_shaping_enabled"] is False
    assert second_source["_source_spectrum_shaping_enabled"] is False
    assert not SPECTRUM_SOURCE_CONFIG_KEYS.intersection(first_source)
    assert not SPECTRUM_SOURCE_CONFIG_KEYS.intersection(second_source)
    assert first_source["_source_analysis_notches"] == second_source["_source_analysis_notches"]
    assert [item[0] for item in first_source["_source_analysis_notches"]] == [
        item[0] for item in config["sphere_analysis_notch_positions"]
    ]
    payload = first.to_dict()
    for suffix in ("agc_strength", "dynamic_range_enabled", "kick_lane_gain", "transient_pulse_gain"):
        assert "widgets.spotify_visualizer.sphere_" + suffix not in payload


def test_each_authored_preset_is_self_contained_and_custom_restores_without_touching_other_modes():
    from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
    from core.settings.visualizer_presets import (
        apply_preset_to_config, build_normalized_custom_snapshot, get_custom_preset_index,
        get_presets, restore_visualizer_snapshot,
    )

    live = {
        "mode": "sphere", "monitor": "Secondary", "position": "Custom",
        "preset_sphere": get_custom_preset_index("sphere"), "spectrum_sensitivity": 1.73,
        "sphere_bar_count": 49, "sphere_input_gain": .76, "sphere_sensitivity": .93,
        "sphere_fill_color": [12, 23, 34, 79], "sphere_edge_color": [45, 56, 67, 113],
        "sphere_taste_the_rainbow_speed": .139, "sphere_taste_the_rainbow_extent": .71,
        "sphere_analysis_notch_positions": [[0., "Bass"], [.239, "Mid"], [.689, "High"], [1., "End"]],
    }
    custom = build_normalized_custom_snapshot("sphere", live)
    required = set(get_owned_mode_setting_keys("sphere", "technical").values()) | {
        "sphere_analysis_notch_positions", "sphere_taste_the_rainbow_speed", "sphere_taste_the_rainbow_extent",
    }
    for index, preset in enumerate(get_presets("sphere")[:-1]):
        assert required <= preset.settings.keys(), preset.name
        resolved = apply_preset_to_config("sphere", index, deepcopy(live))
        changed_lender = apply_preset_to_config("sphere", index, {**live, "spectrum_sensitivity": .25, "preset_spectrum": 0})
        assert {key: resolved[key] for key in required} == {key: changed_lender[key] for key in required}
        assert restore_visualizer_snapshot("sphere", resolved, custom)
        assert {key: resolved[key] for key in custom} == custom
        assert resolved["spectrum_sensitivity"] == live["spectrum_sensitivity"]
        assert resolved["monitor"] == "Secondary" and resolved["position"] == "Custom"


