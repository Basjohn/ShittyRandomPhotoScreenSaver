"""Studio edit session: hydrate / preview / commit / undo / redo / dirty against test-owned stores."""
from __future__ import annotations

from copy import deepcopy

import pytest

from ui.studio.schema import QUIET_PEAK, SCALAR, StudioProperty, StudioSchema, Workspace
from ui.studio.session import StudioEditSession


class MemoryStore:
    """Test-owned canonical store; ``normalize`` mimics a save path that admits values."""

    def __init__(self, values, normalize=None):
        self.values = deepcopy(values)
        self.commits: list[tuple[dict, frozenset]] = []
        self._normalize = normalize or (lambda v: v)

    def snapshot(self):
        return deepcopy(self.values)

    def commit(self, values, changed):
        self.commits.append((deepcopy(dict(values)), changed))
        self.values = self._normalize(deepcopy(dict(values)))
        return deepcopy(self.values)

    def preset_label(self):
        return "Test Slot"


def _schema():
    def admit(key, candidate, previous):
        if key == "pair":
            low, high = sorted(float(v) for v in candidate)
            return [max(0., min(1., low)), max(0., min(1., high))]
        return max(0., min(10., float(candidate)))
    return StudioSchema("toy", "Toy", (Workspace("w", "W", ("G",)),), (
        StudioProperty("size", ("size",), "Size", "w", "G", SCALAR, 0., 10.),
        StudioProperty("pair", ("pair",), "Pair", "w", "G", QUIET_PEAK, 0., 1.),
    ), admit)


def _session(**store_kwargs):
    store = MemoryStore({"size": 2.0, "pair": [0.2, 0.8], "untouched": {"nested": [1, 2]}}, **store_kwargs)
    return StudioEditSession(_schema(), store), store


def test_hydrate_uses_the_exact_canonical_snapshot_and_starts_clean():
    session, store = _session()
    assert session.values == store.values
    assert not session.dirty and session.changed_keys == frozenset()
    assert session.undo_label == "" and session.redo_label == ""


def test_hydrate_refuses_a_snapshot_missing_an_editable_key():
    store = MemoryStore({"size": 1.0})
    with pytest.raises(KeyError):
        StudioEditSession(_schema(), store)


def test_preview_is_live_but_unsaved_and_commit_saves_once_per_gesture():
    session, store = _session()
    session.begin_gesture("Drag Size")
    for value in (3.0, 4.0, 5.0, 6.0):
        session.preview(("size",), value)
    assert session.values["size"] == 6.0
    assert session.committed_values["size"] == 2.0
    assert store.commits == []                                   # no persistence during the gesture
    assert session.end_gesture() is True
    assert len(store.commits) == 1 and store.commits[0][1] == frozenset({"size"})
    assert store.values["size"] == 6.0 and session.dirty
    assert session.undo_label == "Drag Size"


def test_cancelled_gesture_restores_and_saves_nothing():
    session, store = _session()
    session.begin_gesture("Drag")
    session.preview(("size",), 9.0)
    session.cancel_gesture()
    assert session.values["size"] == 2.0 and store.commits == [] and not session.dirty


def test_endpoint_preview_edits_one_side_and_admission_still_applies():
    session, store = _session()
    session.set(("pair", 1), 0.5, "Set Peak")
    assert store.values["pair"] == [0.2, 0.5]
    session.set(("pair", 0), 0.9, "Set Quiet")        # canonical admission keeps quiet <= peak
    assert store.values["pair"] == [0.5, 0.9]


def test_named_undo_redo_round_trips_through_the_store():
    session, store = _session()
    session.set(("size",), 4.0, "Set Size")
    session.set(("pair", 0), 0.1, "Set Quiet")
    assert session.undo_label == "Set Quiet"
    assert session.undo() and store.values["pair"] == [0.2, 0.8] and session.redo_label == "Set Quiet"
    assert session.undo() and store.values["size"] == 2.0 and not session.dirty
    assert not session.undo()
    assert session.redo() and store.values["size"] == 4.0
    session.set(("size",), 5.0, "Set Size Again")       # a new action clears redo
    assert session.redo_label == "" and not session.redo()
    assert len(store.commits) == 6          # 3 edits + 2 undos + 1 redo, one save each


def test_canonical_normalization_from_the_save_path_becomes_the_committed_state():
    session, store = _session(normalize=lambda v: {**v, "size": round(v["size"])})
    session.set(("size",), 3.4, "Set Size")
    assert session.committed_values["size"] == 3 and session.values["size"] == 3


def test_revert_all_is_one_undoable_action_and_reset_is_scoped():
    session, store = _session()
    session.set(("size",), 7.0, "Set Size")
    session.set(("pair", 1), 0.4, "Set Peak")
    assert session.reset_property(("size",), "Reset Size") and store.values["size"] == 2.0
    assert store.values["pair"] == [0.2, 0.4]
    assert session.revert_all() and not session.dirty and session.undo_label == "Revert All"
    assert session.undo() and store.values["pair"] == [0.2, 0.4]


def test_unchanged_gesture_is_not_a_save_or_history_entry():
    session, store = _session()
    session.set(("size",), 2.0, "No Change")
    assert store.commits == [] and session.undo_label == ""


def test_listeners_see_every_state_change_and_revisions_advance():
    session, _store = _session()
    seen = []
    unsubscribe = session.subscribe(seen.append)
    first = session.revision
    session.begin_gesture("Drag")
    session.preview(("size",), 3.0)
    session.end_gesture()
    session.undo()
    unsubscribe()
    session.redo()
    assert seen == ["preview", "commit", "undo"] and session.revision > first + 3
