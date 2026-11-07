"""Expanded Visualizer M1: the persisted intent ``widgets.spotify_visualizer.expanded_display_requested``.

One product-level user intent per settings profile (plan 01 §0.3, §B2, §B7): a canonical default, a typed model
field and the SettingsManager normaliser (the model behind ``normalize_visualizer_section_mapping``). It is never
part of a mode preset or the Custom payload, so preset application, Custom replacement and the runtime preset
transaction keep it and every other widget subtree. Values are written by the tests themselves; no preset value or
user-editable default is pinned (the canonical default is read, never restated).
"""
from __future__ import annotations

import json
import uuid
from copy import deepcopy
from pathlib import Path

import pytest

from core.settings.default_contract import MC_PROFILE, NORMAL_PROFILE, require_canonical_default
from core.settings.defaults import get_default_settings
from core.settings import models
from core.settings.models import SpotifyVisualizerSettings
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import VISUALIZER_MODE_IDS, get_preset_key, is_mode_active
from core.settings.visualizer_presets import (
    MODE_KEY_PREFIXES,
    apply_preset_to_config,
    build_normalized_custom_snapshot,
    get_custom_preset_index,
    get_preset_count,
    get_preset_settings,
    normalize_visualizer_custom_snapshot_cache,
    resolve_visualizer_activation_payload,
    restore_visualizer_snapshot,
)
from core.settings.visualizer_runtime_preset_cycle import resolve_next_visualizer_runtime_preset
from core.settings.visualizer_settings_snapshot import (
    normalize_visualizer_mode_payload,
    normalize_visualizer_section_mapping,
)

KEY = "expanded_display_requested"
DOTTED = f"widgets.spotify_visualizer.{KEY}"
ACTIVE_MODES = [mode for mode in VISUALIZER_MODE_IDS if is_mode_active(mode)]


def _canonical(profile: str = NORMAL_PROFILE) -> bool:
    return require_canonical_default(DOTTED, profile)


def _flipped(profile: str = NORMAL_PROFILE) -> bool:
    """The value a test writes: the opposite of the canonical default, so a dropped key is observable."""
    return not _canonical(profile)


def _section(profile: str = NORMAL_PROFILE) -> dict:
    return deepcopy(get_default_settings(profile)["widgets"]["spotify_visualizer"])


def _manager(root: Path, application: str | None = None) -> SettingsManager:
    return SettingsManager(organization="TestOrg", application=application or f"TestApp_{uuid.uuid4().hex}",
                           storage_base_dir=root)


# -------------------------------------------------------------------------------- default, model, normaliser


@pytest.mark.parametrize("profile", [NORMAL_PROFILE, MC_PROFILE])
def test_canonical_default_is_a_bool_in_every_profile(profile):
    assert isinstance(_canonical(profile), bool)
    assert get_default_settings(profile)["widgets"]["spotify_visualizer"][KEY] is _canonical(profile)


def test_typed_model_field_defaults_from_canonical_authority_and_serialises():
    model = SpotifyVisualizerSettings()
    assert model.expanded_display_requested is _canonical()
    model.expanded_display_requested = _flipped()
    assert model.to_dict()[DOTTED] is _flipped()


@pytest.mark.parametrize(("raw", "expected"), [
    (True, True), (False, False), (1, True), (0, False),
    ("true", True), (" On ", True), ("yes", True), ("1", True),
    ("false", False), ("OFF", False), ("no", False), ("0", False),
])
def test_normaliser_reads_boolean_spellings(raw, expected):
    assert models.normalize_expanded_display_requested(raw) is expected


@pytest.mark.parametrize("raw", [None, "", "maybe", 2, -1, 0.5, [], [True], {"on": True}, object()])
def test_normaliser_falls_back_to_the_canonical_default_for_malformed_input(raw):
    assert models.normalize_expanded_display_requested(raw) is _canonical()


def test_model_construction_normalises_a_hand_built_value():
    assert SpotifyVisualizerSettings(expanded_display_requested="off").expanded_display_requested is False
    assert SpotifyVisualizerSettings(expanded_display_requested="on").expanded_display_requested is True


@pytest.mark.parametrize("value", [True, False])
def test_section_normaliser_keeps_the_intent(value):
    section = _section()
    section[KEY] = value
    assert normalize_visualizer_section_mapping(section)[KEY] is value
    dotted = {f"widgets.spotify_visualizer.{k}": v for k, v in section.items()}
    assert normalize_visualizer_section_mapping(dotted)[KEY] is value


def test_section_normaliser_repairs_a_malformed_intent_and_fills_a_missing_one():
    section = _section()
    section[KEY] = "on"
    assert normalize_visualizer_section_mapping(section)[KEY] is True
    section[KEY] = ["junk"]
    assert normalize_visualizer_section_mapping(section)[KEY] is _canonical()
    section.pop(KEY)
    assert normalize_visualizer_section_mapping(section)[KEY] is _canonical()


# ------------------------------------------------------------------------------ preset and Custom exclusion


@pytest.mark.parametrize("mode", VISUALIZER_MODE_IDS)
def test_mode_payload_and_custom_snapshot_exclude_the_intent(mode):
    # A live-section key no mode prefix can claim ...
    assert not [p for p in MODE_KEY_PREFIXES[mode] if KEY.startswith(p)]
    section = _section()
    section.update({"mode": mode, KEY: _flipped()})
    assert normalize_visualizer_section_mapping(section)[KEY] is _flipped()
    # ... so the mode payload, a Custom snapshot and a leaked Custom cache entry never carry it.
    assert KEY not in normalize_visualizer_mode_payload(mode, section)
    assert KEY not in build_normalized_custom_snapshot(mode, section)
    leaked = normalize_visualizer_custom_snapshot_cache({mode: {"mode": mode, KEY: _flipped()}})
    assert KEY not in leaked[mode]


@pytest.mark.parametrize("mode", VISUALIZER_MODE_IDS)
def test_no_curated_preset_carries_the_intent(mode):
    # The key is a canonical live-section default (structure only, its value is not pinned) ...
    assert KEY in _section()
    # ... that no curated preset of the mode authors.
    for index in range(get_preset_count(mode)):
        assert KEY not in get_preset_settings(mode, index)


@pytest.mark.parametrize("mode", VISUALIZER_MODE_IDS)
def test_preset_application_preserves_the_intent_and_every_non_mode_key(mode):
    section = _section()
    section.update({"mode": mode, KEY: _flipped()})
    prefixes = MODE_KEY_PREFIXES[mode]
    live_only = {k: v for k, v in section.items() if not any(k.startswith(p) for p in prefixes)}
    for index in range(get_preset_count(mode)):
        applied = apply_preset_to_config(mode, index, deepcopy(section))
        assert applied[KEY] is _flipped(), index
        for key, value in live_only.items():
            if key != "mode":
                assert applied.get(key) == value, (index, key)


@pytest.mark.parametrize("mode", VISUALIZER_MODE_IDS)
def test_custom_replacement_preserves_the_intent(mode):
    section = _section()
    section.update({"mode": mode, KEY: _flipped()})
    payload = build_normalized_custom_snapshot(mode, section)
    target = deepcopy(section)
    restore_visualizer_snapshot(mode, target, {**payload, KEY: _canonical()})
    assert target[KEY] is _flipped()


@pytest.mark.parametrize("mode", ACTIVE_MODES)
def test_runtime_activation_payload_keeps_the_intent(mode):
    section = _section()
    section.update({"mode": mode, KEY: _flipped()})
    for index in range(get_preset_count(mode)):
        section[get_preset_key(mode)] = index
        assert resolve_visualizer_activation_payload(section, mode=mode).resolved_config[KEY] is _flipped()


@pytest.mark.parametrize("mode", [m for m in ACTIVE_MODES if get_preset_count(m) >= 2])
def test_runtime_preset_cycle_keeps_the_intent_out_of_the_custom_cache(mode):
    config = _section()
    config.update({"mode": mode, KEY: _flipped(), get_preset_key(mode): get_custom_preset_index(mode)})
    cache: dict = {}
    for _ in range(get_preset_count(mode)):
        target = resolve_next_visualizer_runtime_preset(config, cache, mode=mode)
        config, cache = target.visualizer_config, target.custom_presets
        assert config[KEY] is _flipped()
        assert KEY not in cache.get(mode, {})
    assert config[get_preset_key(mode)] == get_custom_preset_index(mode)


# ------------------------------------------------------------------------------------ SettingsManager seams


@pytest.mark.parametrize("value", [True, False])
def test_replace_visualizer_runtime_preset_state_round_trips_the_intent(tmp_path, value):
    manager = _manager(tmp_path / "store")
    app = manager.get_application_name()
    manager.set(DOTTED, value)
    widgets = manager.get("widgets", {})
    siblings = {name: json.loads(json.dumps(sub)) for name, sub in widgets.items() if name != "spotify_visualizer"}
    mode = "extruded_bubble"
    target = resolve_next_visualizer_runtime_preset({**widgets["spotify_visualizer"], "mode": mode},
                                                    manager.get("visualizer_custom_presets", {}) or {}, mode=mode)

    manager.replace_visualizer_runtime_preset_state(target.visualizer_config, target.custom_presets)

    assert manager.get(DOTTED) is value
    assert KEY not in manager.get("visualizer_custom_presets", {}).get(mode, {})
    after = manager.get("widgets", {})
    assert {name: sub for name, sub in after.items() if name != "spotify_visualizer"} == siblings
    assert manager.flush(timeout=5.0) is True
    reloaded = _manager(tmp_path / "store", app)
    assert reloaded.get(DOTTED) is value
    assert reloaded.get_spotify_visualizer_settings().expanded_display_requested is value


def test_a_later_widgets_root_write_keeps_the_intent(tmp_path):
    manager = _manager(tmp_path)
    manager.set(DOTTED, _flipped())
    widgets = manager.get("widgets", {})
    widgets["clock"] = {**widgets.get("clock", {}), "enabled": not widgets.get("clock", {}).get("enabled", True)}
    manager.set("widgets", widgets)
    assert manager.get(DOTTED) is _flipped()


def test_typed_settings_write_round_trips_the_intent(tmp_path):
    manager = _manager(tmp_path)
    model = manager.get_spotify_visualizer_settings()
    assert model.expanded_display_requested is _canonical()
    model.expanded_display_requested = _flipped()
    manager.set_spotify_visualizer_settings(model)
    assert manager.get(DOTTED) is _flipped()
    assert manager.get_spotify_visualizer_settings().expanded_display_requested is _flipped()


def test_reset_to_defaults_returns_the_canonical_intent(tmp_path):
    manager = _manager(tmp_path)
    manager.set(DOTTED, _flipped())
    manager.reset_to_defaults()
    assert manager.get(DOTTED) is _canonical()


def test_visualizer_reset_returns_the_canonical_intent(tmp_path):
    manager = _manager(tmp_path)
    manager.set(DOTTED, _flipped())
    manager.reset_visualizers_to_defaults()
    assert manager.get(DOTTED) is _canonical()


def test_export_then_import_carries_the_intent(tmp_path):
    source = _manager(tmp_path / "source")
    source.set(DOTTED, _flipped())
    path = tmp_path / "intent.sst"
    assert source.export_to_sst(str(path)) is True
    exported = json.loads(path.read_text(encoding="utf-8"))
    assert exported["snapshot"]["widgets"]["spotify_visualizer"][KEY] is _flipped()

    for merge in (True, False):
        target = _manager(tmp_path / f"target_{merge}")
        assert target.get(DOTTED) is _canonical()
        assert target.import_from_sst(str(path), merge=merge) is True
        assert target.get(DOTTED) is _flipped()


def test_importing_an_older_export_without_the_intent_resolves_the_canonical_default(tmp_path):
    manager = _manager(tmp_path)
    path = tmp_path / "older.sst"
    path.write_text(json.dumps({"snapshot": {"widgets": {"spotify_visualizer": {
        "enabled": True, "mode": "extruded_bubble"}}}}), encoding="utf-8")
    assert manager.import_from_sst(str(path), merge=False) is True
    assert manager.get(DOTTED) is _canonical()


def test_an_older_profile_without_the_intent_loads_the_canonical_default(tmp_path):
    manager = _manager(tmp_path / "store")
    app = manager.get_application_name()
    widgets = dict(manager._settings.value("widgets", {}))
    section = dict(widgets["spotify_visualizer"])
    section.pop(KEY, None)
    widgets["spotify_visualizer"] = section
    manager._settings.setValue("widgets", widgets)
    manager._settings.sync()
    assert manager.flush(timeout=5.0) is True

    reloaded = _manager(tmp_path / "store", app)
    assert reloaded.get(DOTTED) is _canonical()
    assert reloaded.get_spotify_visualizer_settings().expanded_display_requested is _canonical()


def test_visualizer_schema_migration_keeps_a_stored_intent(tmp_path):
    manager = _manager(tmp_path / "store")
    app = manager.get_application_name()
    widgets = dict(manager._settings.value("widgets", {}))
    widgets["spotify_visualizer"] = {**widgets["spotify_visualizer"], KEY: _flipped()}
    manager._settings.setValue("widgets", widgets)
    manager._settings.update_metadata(visualizer_schema_version=SettingsManager._VISUALIZER_SCHEMA_VERSION - 1)
    manager._settings.sync()
    assert manager.flush(timeout=5.0) is True

    reloaded = _manager(tmp_path / "store", app)
    assert reloaded._settings.metadata().get("visualizer_schema_version") == SettingsManager._VISUALIZER_SCHEMA_VERSION
    assert reloaded.get(DOTTED) is _flipped()


def test_a_hand_edited_spelling_reads_through_the_typed_model(tmp_path):
    manager = _manager(tmp_path)
    manager.set(DOTTED, "on")
    assert manager.get_spotify_visualizer_settings().expanded_display_requested is True
    manager.set(DOTTED, "nonsense")
    assert manager.get_spotify_visualizer_settings().expanded_display_requested is _canonical()


def test_standard_and_mc_profiles_keep_independent_intents(tmp_path):
    standard = _manager(tmp_path, NORMAL_PROFILE)
    mc = _manager(tmp_path, MC_PROFILE)
    assert standard.get_storage_path() != mc.get_storage_path()

    mc.set(DOTTED, _flipped(MC_PROFILE))
    assert standard.get(DOTTED) is _canonical(NORMAL_PROFILE)
    standard.set(DOTTED, _flipped(NORMAL_PROFILE))
    mc.reset_to_defaults()
    assert mc.get(DOTTED) is _canonical(MC_PROFILE)
    assert standard.get(DOTTED) is _flipped(NORMAL_PROFILE)

    assert standard.flush(timeout=5.0) is True and mc.flush(timeout=5.0) is True
    assert _manager(tmp_path, NORMAL_PROFILE).get(DOTTED) is _flipped(NORMAL_PROFILE)
    assert _manager(tmp_path, MC_PROFILE).get(DOTTED) is _canonical(MC_PROFILE)
