"""A settings write costs what it changes and never changes a stored value in place (Current_Plan 1C.2).

A display move's Save wrote the whole widgets root from the GUI thread at the fade's midpoint, and the store
deep-copied all 300 KB of it on every write (inflated by every GIL hand-off to the render threads). The store now
keeps the stored objects for every unchanged part and makes new containers only on a changed path
(``share_unchanged``); the Save reads the root without copying it (``get_widgets_map_to_write``). Keys and values
come from the canonical owners, never from preset or default values.
"""
from __future__ import annotations

import uuid
from copy import deepcopy
from pathlib import Path

from core.settings.json_store import JsonSettingsStore
from core.settings.models._spotify_visualizer import (
    KEY_LOCAL_VISUALIZER_SETTINGS,
    normalize_key_local_visualizer_value,
)
from core.settings.settings_manager import SettingsManager
from core.settings.stored_values import same_stored_value, share_unchanged

_PROBE_VALUES = (True, False, 0, 1, 2, "1", "2", "ALL", "Custom", "", None)


def _containers(value, found=None):
    found = {} if found is None else found
    if isinstance(value, (dict, list, tuple)):
        found[id(value)] = value
        for item in (value.values() if isinstance(value, dict) else value):
            _containers(item, found)
    return found


def _manager(tmp_path: Path) -> SettingsManager:
    return SettingsManager(organization="TestOrg", application=f"TestApp_{uuid.uuid4().hex}",
                           storage_base_dir=tmp_path / uuid.uuid4().hex)


def _other_route_value(key, current):
    return next(value for value in _PROBE_VALUES
                if not same_stored_value(normalize_key_local_visualizer_value(key, value), current))


def test_a_shared_write_is_strictly_the_new_value_and_reuses_every_unchanged_part():
    old = {"same": {"list": [1, 2.0, {"x": "y"}], "n": 1}, "changed": {"a": 1, "b": [1, 2]},
           "typed": {"i": 1, "f": 1.0, "b": True}, "removed": 1, "seq": [1, [2], 3]}
    new = deepcopy(old)
    new["changed"]["b"].append(3)
    new["typed"] = {"i": 1.0, "f": 1, "b": 1}          # equal values, other types: stored as the new types
    del new["removed"]
    new["added"] = {"fresh": [1]}
    new["seq"] = [1, [2]]
    result = share_unchanged(old, new)
    assert same_stored_value(result, new)
    assert [type(v) for v in result["typed"].values()] == [type(v) for v in new["typed"].values()]
    assert result["same"] is old["same"]
    assert result["changed"]["a"] is old["changed"]["a"] and result["seq"][1] is old["seq"][1]
    assert not set(_containers(result)) & set(_containers(new)), "the result holds a container of the caller's"
    assert share_unchanged(old, deepcopy(old)) is old
    fresh = share_unchanged(None, new)
    assert same_stored_value(fresh, new) and not set(_containers(fresh)) & set(_containers(new))


def test_a_write_never_changes_a_stored_value_in_place(tmp_path):
    """The store keeps none of the caller's containers, so a caller that keeps and changes what it wrote, or builds
    the next write from the stored parts, cannot reach a stored value. Negative control: a store that adopts the
    caller's containers (``share_unchanged`` returning ``new``) fails here."""
    store = JsonSettingsStore(storage_path=tmp_path / "settings_v2.json", profile="sharing-probe")
    store.setValue("root", {"a": {"x": [1, 2], "y": {"z": 1}}, "b": {"k": "v"}})
    held = store.peek("root")
    snapshot = deepcopy(held)
    written = {key: dict(section) for key, section in held.items()}  # the next write, from the stored parts
    written["a"]["x"] = [1, 2, 3]
    written["b"]["k"] = "w"
    written["c"] = {"new": [1]}
    assert store.setValue("root", written) is True
    written["a"]["x"].append("later")                  # the caller keeps and changes what it handed over
    written["c"]["new"].append("later")
    written["b"]["k"] = "later"
    assert same_stored_value(held, snapshot), "a later write changed a stored value in place"
    stored = store.peek("root")
    assert stored["a"]["x"] == [1, 2, 3] and stored["c"] == {"new": [1]} and stored["b"] == {"k": "w"}
    assert stored["a"]["y"] is held["a"]["y"]


def test_a_route_only_save_shares_every_unchanged_part_of_the_widgets_root(tmp_path):
    """The display move's Save: read without a copy, change the route, write. Every strictly unchanged section of the
    stored root, and every unchanged value of the Visualizer section, stays the stored object (nothing of the root is
    copied), and the stored root equals what the copying read's write stores. Negative control: the pre-change
    store (a whole deepcopy per write) fails the identity checks."""
    manager = _manager(tmp_path)
    twin = _manager(tmp_path)
    for key in KEY_LOCAL_VISUALIZER_SETTINGS:
        previous = manager._settings.peek("widgets")
        widgets = manager.get_widgets_map_to_write()
        route = _other_route_value(key, widgets["spotify_visualizer"][key])
        widgets["spotify_visualizer"][key] = route
        manager.set_widgets_map(widgets, emit_change=False)
        stored = manager._settings.peek("widgets")
        assert stored is not previous
        for name, section in previous.items():
            if same_stored_value(section, stored.get(name)):
                assert stored[name] is section, (key, name)
        vis_before, vis_after = previous["spotify_visualizer"], stored["spotify_visualizer"]
        for name, value in vis_before.items():
            if name != key:
                assert vis_after[name] is value, (key, name)
        copied = twin.get_widgets_map()
        copied["spotify_visualizer"][key] = route
        twin.set_widgets_map(copied, emit_change=False)
        assert same_stored_value(twin._settings.peek("widgets"), stored), key


def test_change_listeners_get_their_own_copy_of_the_widgets_root(tmp_path):
    """A written root shares values with the store; a listener that changes what it is handed must not reach the
    store. Negative control: publishing the written root itself fails here."""
    manager = _manager(tmp_path)
    route = KEY_LOCAL_VISUALIZER_SETTINGS[0]
    received = []
    manager.settings_changed.connect(lambda key, value: received.append((key, value)))
    widgets = manager.get_widgets_map_to_write()
    widgets["spotify_visualizer"][route] = _other_route_value(route, widgets["spotify_visualizer"][route])
    manager.set_widgets_map(widgets)
    published = [value for key, value in received if key == "widgets"]
    assert published
    stored_snapshot = deepcopy(manager._settings.peek("widgets"))
    for root in published:
        assert not set(_containers(root)) & set(_containers(manager._settings.peek("widgets")))
        for section in root.values():
            if isinstance(section, dict):
                for value in section.values():
                    if isinstance(value, dict):
                        value["changed_by_a_listener"] = True
                    elif isinstance(value, list):
                        value.append("changed_by_a_listener")
    assert same_stored_value(manager._settings.peek("widgets"), stored_snapshot)
