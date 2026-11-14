"""A widgets write that changes only the Visualizer's route re-normalises only that route (Current_Plan 1C.2).

A display move's Save writes the whole widgets map from the GUI thread at the fade's midpoint. Each write re-ran the
whole Visualizer section's normalisation (15-27 ms on a real profile) although the move changes only the widget's
route. The store's own canonical section is remembered per preset catalogue, and a write differing from it only in
key-local settings derives its section from it; the result is the full normalisation's, value for value and type
for type. The keys and values here come from the canonical owners, never from preset or default values.
"""
from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from core.settings import settings_manager as settings_manager_module
from core.settings.json_store import JsonSettingsStore
from core.settings.models._spotify_visualizer import KEY_LOCAL_VISUALIZER_SETTINGS
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_settings_snapshot import (
    _same_stored_value,
    normalize_visualizer_section_from_canonical,
    normalize_visualizer_section_mapping,
)

# Values of every type a route key may be handed (each key's coercion decides what it stores).
_PROBE_VALUES = (True, False, 0, 1, 2, "1", "2", "ALL", "Custom", "", None)


def _manager(tmp_path: Path) -> SettingsManager:
    return SettingsManager(organization="TestOrg", application=f"TestApp_{uuid.uuid4().hex}",
                           storage_base_dir=tmp_path / uuid.uuid4().hex)


def _full(section):
    return normalize_visualizer_section_mapping(section, apply_preset_overlay=False)


@pytest.fixture
def counted(monkeypatch):
    """Counts the manager's whole-section normalisations."""
    calls = []
    original = settings_manager_module.normalize_visualizer_section_mapping

    def counting(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(settings_manager_module, "normalize_visualizer_section_mapping", counting)
    return calls


def _other_route_value(key, current):
    return next(value for value in _PROBE_VALUES
                if not _same_stored_value(_full_value(key, value), current))


def _full_value(key, value):
    from core.settings.models._spotify_visualizer import normalize_key_local_visualizer_value
    return normalize_key_local_visualizer_value(key, value)


def test_the_key_local_settings_are_derived_exactly_as_the_whole_normaliser_writes_them(tmp_path):
    manager = _manager(tmp_path)
    canonical = _full(manager.get_widgets_map()["spotify_visualizer"])
    assert KEY_LOCAL_VISUALIZER_SETTINGS and set(KEY_LOCAL_VISUALIZER_SETTINGS) <= set(canonical)
    assert _same_stored_value(_full(canonical), canonical), "the normaliser is idempotent"
    for key in KEY_LOCAL_VISUALIZER_SETTINGS:
        for value in _PROBE_VALUES:
            incoming = dict(canonical)
            incoming[key] = value
            derived = normalize_visualizer_section_from_canonical(canonical, canonical, incoming)
            assert derived is not None, (key, value)
            assert _same_stored_value(derived, _full(incoming)), (key, value)


def test_any_other_difference_is_left_to_the_whole_normaliser(tmp_path):
    manager = _manager(tmp_path)
    canonical = _full(manager.get_widgets_map()["spotify_visualizer"])
    other = next(key for key in sorted(canonical) if key not in KEY_LOCAL_VISUALIZER_SETTINGS)
    changed = dict(canonical)
    changed[other] = ["not", "the", "stored", "value"]
    assert normalize_visualizer_section_from_canonical(canonical, canonical, changed) is None
    added = dict(canonical)
    added["an_unknown_key"] = 1
    assert normalize_visualizer_section_from_canonical(canonical, canonical, added) is None
    removed = dict(canonical)
    removed.pop(KEY_LOCAL_VISUALIZER_SETTINGS[0])
    assert normalize_visualizer_section_from_canonical(canonical, canonical, removed) is None
    retyped = dict(canonical)        # equal but stored differently (1 == 1.0): not the same section
    number = next(key for key in sorted(canonical)
                  if type(canonical[key]) is int and key not in KEY_LOCAL_VISUALIZER_SETTINGS)
    retyped[number] = float(canonical[number])
    assert normalize_visualizer_section_from_canonical(canonical, canonical, retyped) is None


def test_a_route_only_widgets_write_does_not_renormalise_the_whole_section(tmp_path, counted):
    """Negative control: before 1C.2 every widgets write normalised the whole section (one call per write here)."""
    manager = _manager(tmp_path)
    for key in KEY_LOCAL_VISUALIZER_SETTINGS:
        widgets = manager.get_widgets_map()
        section = widgets["spotify_visualizer"]
        section[key] = _other_route_value(key, section[key])
        expected = _full(dict(section))
        calls_before = len(counted)
        manager.set_widgets_map(widgets, emit_change=False)
        assert len(counted) == calls_before, key
        assert _same_stored_value(manager.get_widgets_map()["spotify_visualizer"], expected), key


def test_the_first_route_write_after_load_derives_from_the_stored_section(tmp_path, counted):
    """The load remembers the stored section's normalisation once (a lifecycle cost), so the session's first write
    (a display move's Save) derives too, even when the stored section was not yet canonical."""
    base = tmp_path / uuid.uuid4().hex
    application = f"TestApp_{uuid.uuid4().hex}"
    first = SettingsManager(organization="TestOrg", application=application, storage_base_dir=base)
    widgets = first.get_widgets_map()
    route = KEY_LOCAL_VISUALIZER_SETTINGS[0]
    # A stored section that is not canonical (as an older build's profile can be): one key it no longer stores.
    raw = dict(widgets["spotify_visualizer"])
    raw["a_retired_key_from_an_older_build"] = 1
    with first._lock:
        widgets_raw = dict(first._settings.value("widgets"))
        widgets_raw["spotify_visualizer"] = raw
        first._settings.setValue("widgets", widgets_raw)
    settings_manager_module._VISUALIZER_NORMALIZATION_MEMOS.pop(first._settings, None)
    first._seed_visualizer_normalization_memo()
    calls_before = len(counted)
    widgets = first.get_widgets_map()
    widgets["spotify_visualizer"][route] = _other_route_value(route, widgets["spotify_visualizer"][route])
    expected = _full(dict(widgets["spotify_visualizer"]))
    first.set_widgets_map(widgets, emit_change=False)
    assert len(counted) == calls_before
    stored = first.get_widgets_map()["spotify_visualizer"]
    assert "a_retired_key_from_an_older_build" not in stored
    assert _same_stored_value(stored, expected)


def test_a_changed_preset_catalogue_renormalises_the_whole_section(tmp_path, counted, monkeypatch):
    manager = _manager(tmp_path)
    route = KEY_LOCAL_VISUALIZER_SETTINGS[0]
    current = settings_manager_module.catalogue_state()
    monkeypatch.setattr(settings_manager_module, "catalogue_state", lambda: current + (("another",),))
    widgets = manager.get_widgets_map()
    widgets["spotify_visualizer"][route] = _other_route_value(route, widgets["spotify_visualizer"][route])
    calls_before = len(counted)
    manager.set_widgets_map(widgets, emit_change=False)
    assert len(counted) == calls_before + 1


def test_the_writer_never_changes_the_stored_values_it_shares(tmp_path):
    """The store hands the writer a shallow snapshot; a dotted key beside a stored mapping of the same section must
    be written into the writer's own container. Negative control: the pre-change writer added the dotted key to the
    store's own mapping (seen with the shallow snapshot and the old writer)."""
    store = JsonSettingsStore(storage_path=tmp_path / "settings_v2.json", profile="writer-probe")
    store.setValue("probe_section", {"kept": 1})
    store.setValue("probe_section.added", 2)
    assert store.flush(timeout=5.0)
    assert store.peek("probe_section") == {"kept": 1}
