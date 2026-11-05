"""One typed edit session over a canonical settings store.

Preview values (a live gesture) are kept apart from committed values. Only a
committed gesture reaches the store, once, through the store's own canonical save
path; the store answers with the canonical post-save snapshot, which becomes the
committed state (so normalization done by the real save path is never hidden).

The session holds no Qt objects and no mode knowledge: values are opaque JSON-like
data addressed by ``(settings_key, *index)`` paths and admitted by the schema's
mode-supplied validator.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from ui.studio.schema import Path, StudioSchema


class CanonicalStore(Protocol):
    """The existing persistence owner the Studio edits through (never raw preset JSON)."""

    def snapshot(self) -> dict[str, Any]:
        """Exact current canonical values for (at least) every key the schema edits."""

    def commit(self, values: Mapping[str, Any], changed: frozenset[str]) -> dict[str, Any]:
        """Persist ``values`` through the canonical Custom path; return the canonical snapshot after it."""

    def preset_label(self) -> str:
        """Human name of the active preset slot (Custom after the first committed edit)."""


@dataclass(frozen=True)
class UndoEntry:
    label: str
    before: Mapping[str, Any]
    after: Mapping[str, Any]


def read_path(values: Mapping[str, Any], path: Path) -> Any:
    node: Any = values[path[0]]
    for index in path[1:]:
        node = node[index]
    return node


def write_path(value: Any, subpath: tuple, item: Any) -> Any:
    """Return a deep copy of ``value`` with ``item`` placed at ``subpath`` (empty: replace)."""
    if not subpath:
        return deepcopy(item)
    copy = deepcopy(value)
    node = copy
    for index in subpath[:-1]:
        node = node[index]
    node[subpath[-1]] = deepcopy(item)
    return copy


class StudioEditSession:
    """Hydrate → preview → commit, with named undo/redo scoped to this session."""

    def __init__(self, schema: StudioSchema, store: CanonicalStore) -> None:
        self._schema = schema
        self._store = store
        self._listeners: list[Callable[[str], None]] = []
        self._baseline: dict[str, Any] = {}
        self._committed: dict[str, Any] = {}
        self._preview: dict[str, Any] = {}
        self._gesture: str | None = None
        self._gesture_before: dict[str, Any] = {}
        self._undo: list[UndoEntry] = []
        self._redo: list[UndoEntry] = []
        self.revision = 0
        self.commit_count = 0
        self.hydrate()

    # ------------------------------------------------------------------ state
    @property
    def schema(self) -> StudioSchema:
        return self._schema

    def hydrate(self) -> None:
        """(Re)load the exact canonical snapshot; drops any gesture and history."""
        snapshot = self._store.snapshot()
        missing = self._schema.keys - set(snapshot)
        if missing:
            raise KeyError(f"Canonical snapshot lacks Studio keys: {sorted(missing)}")
        self._committed = deepcopy(dict(snapshot))
        self._baseline = deepcopy(self._committed)
        self._preview.clear()
        self._gesture = None
        self._gesture_before = {}
        self._undo.clear()
        self._redo.clear()
        self._changed("hydrate")

    @property
    def values(self) -> dict[str, Any]:
        """Effective values the preview renders: committed plus any live gesture."""
        if not self._preview:
            return self._committed
        merged = dict(self._committed)
        merged.update(self._preview)
        return merged

    @property
    def committed_values(self) -> dict[str, Any]:
        return self._committed

    @property
    def baseline_values(self) -> dict[str, Any]:
        """The canonical values the session opened with (reversible starting points use these)."""
        return self._baseline

    def set_many(self, changes: dict[Path, Any], label: str) -> bool:
        """Several values as ONE committed, undoable action (e.g. a material starting point)."""
        self.begin_gesture(label)
        for path, value in changes.items():
            self.preview(path, value)
        return self.end_gesture()

    def get(self, path: Path) -> Any:
        return read_path(self.values, path)

    @property
    def dirty(self) -> bool:
        """The canonical state differs from what the session opened with."""
        return bool(self.changed_keys)

    @property
    def changed_keys(self) -> frozenset[str]:
        keys = self._schema.keys
        return frozenset(key for key in keys if self._committed.get(key) != self._baseline.get(key))

    @property
    def gesture_active(self) -> bool:
        return self._gesture is not None

    @property
    def preset_label(self) -> str:
        return self._store.preset_label()

    # --------------------------------------------------------------- gestures
    def begin_gesture(self, label: str) -> None:
        if self._gesture is not None:
            self.end_gesture()
        self._gesture = str(label) or "Edit"
        self._gesture_before = {}

    def preview(self, path: Path, value: Any) -> Any:
        """Live value for the renderer; nothing is persisted. Returns the admitted value."""
        if self._gesture is None:
            self.begin_gesture("Edit")
        key = path[0]
        if key not in self._schema.keys:
            raise KeyError(f"{key} is not editable in this Studio")
        current = self.values[key]
        candidate = write_path(current, tuple(path[1:]), value)
        admitted = self._schema.admit(key, candidate, current)
        if key not in self._gesture_before:
            self._gesture_before[key] = deepcopy(self._committed[key])
        self._preview[key] = admitted
        follow = getattr(self._schema, "follow", None)
        if follow is not None:
            for other, value in dict(follow(key, admitted, self.values) or {}).items():
                if other == key or other not in self._schema.keys:
                    continue
                previous = self.values[other]
                if other not in self._gesture_before:
                    self._gesture_before[other] = deepcopy(self._committed[other])
                self._preview[other] = self._schema.admit(other, value, previous)
        self._changed("preview")
        return read_path({key: admitted}, (key, *path[1:]))

    def end_gesture(self) -> bool:
        """Commit the live gesture through the store. Returns True if anything was saved."""
        label, before = self._gesture, self._gesture_before
        self._gesture, self._gesture_before = None, {}
        after = {key: self._preview.pop(key) for key in tuple(self._preview)}
        if label is None:
            return False
        changed = {key: value for key, value in after.items() if value != before.get(key)}
        if not changed:
            self._changed("cancel")
            return False
        self._persist(changed)
        self._undo.append(UndoEntry(label, {key: before[key] for key in changed}, changed))
        self._redo.clear()
        self._changed("commit")
        return True

    def cancel_gesture(self) -> None:
        if self._gesture is None and not self._preview:
            return
        self._gesture, self._gesture_before = None, {}
        self._preview.clear()
        self._changed("cancel")

    def set(self, path: Path, value: Any, label: str) -> bool:
        """A discrete edit (toggle, chip, keyboard step, typed value): one committed action."""
        self.begin_gesture(label)
        self.preview(path, value)
        return self.end_gesture()

    # ------------------------------------------------------------- history
    @property
    def undo_label(self) -> str:
        return self._undo[-1].label if self._undo else ""

    @property
    def redo_label(self) -> str:
        return self._redo[-1].label if self._redo else ""

    def undo(self) -> bool:
        self.cancel_gesture()
        if not self._undo:
            return False
        entry = self._undo.pop()
        self._persist(dict(entry.before))
        self._redo.append(entry)
        self._changed("undo")
        return True

    def redo(self) -> bool:
        self.cancel_gesture()
        if not self._redo:
            return False
        entry = self._redo.pop()
        self._persist(dict(entry.after))
        self._undo.append(entry)
        self._changed("redo")
        return True

    def revert_all(self) -> bool:
        """Restore the opening snapshot as one undoable action."""
        self.cancel_gesture()
        before = {key: deepcopy(self._committed[key]) for key in self.changed_keys}
        if not before:
            return False
        after = {key: deepcopy(self._baseline[key]) for key in before}
        self._persist(after)
        self._undo.append(UndoEntry("Revert All", before, after))
        self._redo.clear()
        self._changed("commit")
        return True

    def reset_property(self, path: Path, label: str) -> bool:
        """Restore one value to the opening snapshot (explicit, scoped reset)."""
        return self.set(path, read_path(self._baseline, path), label)

    # ------------------------------------------------------------ plumbing
    def _persist(self, changed: Mapping[str, Any]) -> None:
        merged = deepcopy(self._committed)
        merged.update(deepcopy(dict(changed)))
        canonical = self._store.commit(merged, frozenset(changed))
        self.commit_count += 1
        for key in self._schema.keys:
            if key in canonical:
                self._committed[key] = deepcopy(canonical[key])

    def subscribe(self, listener: Callable[[str], None]) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass
        return unsubscribe

    def _changed(self, reason: str) -> None:
        self.revision += 1
        for listener in tuple(self._listeners):
            listener(reason)


__all__ = ["CanonicalStore", "StudioEditSession", "UndoEntry", "read_path", "write_path"]
