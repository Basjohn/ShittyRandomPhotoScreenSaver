"""SC1: the unused root ``transitions.direction`` is retired forward-only.

A profile or SST that still carries it loads, saves, exports and re-imports without it; defaults
cannot merge it back and the key cannot be written. Each directional transition keeps its own
``<section>.direction`` (those are untouched). No default or authored value is asserted.
"""
import json
import uuid

import pytest

from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from core.settings.sst_io import import_from_sst


def _manager(base):
    return SettingsManager(organization="Test", application=f"sc1_{uuid.uuid4().hex}", storage_base_dir=base)


def _reload(manager, base):
    return SettingsManager(organization=manager.get_organization_name(),
                           application=manager.get_application_name(), storage_base_dir=base)


def _profile_file(base):
    (path,) = base.rglob("settings_v2.json")
    return path


def _stored_transitions(base) -> dict:
    data = json.loads(_profile_file(base).read_text(encoding="utf-8"))
    found = []

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("transitions"), dict):
                found.append(node["transitions"])
            for value in node.values():
                walk(value)

    walk(data)
    assert found, "no transitions root in the saved profile"
    return found[0]


def test_defaults_no_longer_carry_the_root_direction():
    transitions = get_default_settings()["transitions"]
    assert "direction" not in transitions
    assert any(isinstance(v, dict) and "direction" in v for v in transitions.values())  # sections keep theirs


def test_a_profile_with_the_root_direction_loads_saves_and_round_trips_without_it(tmp_path):
    base = tmp_path / "profile"
    manager = _manager(base)
    assert manager.flush(timeout=5.0)
    path = _profile_file(base)
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    roots = []

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("transitions"), dict):
                roots.append(node["transitions"])
            for value in node.values():
                walk(value)

    walk(data)
    assert roots
    for root in roots:
        root["direction"] = "Left to Right"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert "direction" in _stored_transitions(base)                     # the old profile really has it

    loaded = _reload(manager, base)
    assert "direction" not in loaded.get("transitions")                # load strips it before the defaults merge
    with pytest.raises(KeyError, match="Retired setting key"):
        loaded.set("transitions.direction", "Random")

    loaded.set("transitions.random_always", not loaded.get("transitions.random_always"))  # an ordinary save
    assert loaded.flush(timeout=5.0)
    assert "direction" not in _stored_transitions(base)
    again = _reload(loaded, base)
    assert "direction" not in again.get("transitions")
    assert again.flush(timeout=5.0)
    assert "direction" not in _stored_transitions(base)

    exported = tmp_path / "export.sst"
    assert again.export_to_sst(str(exported)) is True
    assert '"direction": "Left to Right"' not in exported.read_text(encoding="utf-8")


@pytest.mark.parametrize("merge", [True, False])
def test_an_sst_with_the_root_direction_imports_without_it(tmp_path, merge):
    base = tmp_path / f"sst_{merge}"
    manager = _manager(base)
    snapshot = tmp_path / "old.sst"
    snapshot.write_text(json.dumps({"snapshot": {"transitions": {"direction": "Left to Right"}}}), encoding="utf-8")
    assert import_from_sst(manager, str(snapshot), merge=merge) is True
    assert "direction" not in manager.get("transitions")
    assert manager.flush(timeout=5.0)
    assert "direction" not in _stored_transitions(base)
