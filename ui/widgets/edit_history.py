"""A Settings visual editor's short undo/redo memory: its last few committed states, in memory only.

Editors record each committed state (a gesture's end, never every drag step); undo and redo step through the
bounded history and return the state to restore. Nothing persists: an editor drops its history when its body is
rebuilt or rehydrated.
"""
from __future__ import annotations

from collections import deque

EDIT_HISTORY_DEPTH = 3


class EditHistory:
    def __init__(self, current, depth: int = EDIT_HISTORY_DEPTH) -> None:
        self._current = current
        self._undo: deque = deque(maxlen=depth)
        self._redo: deque = deque(maxlen=depth)

    @property
    def current(self):
        return self._current

    def record(self, state) -> None:
        """A newly committed state; an unchanged one is not an action."""
        if state == self._current:
            return
        self._undo.append(self._current)
        self._redo.clear()
        self._current = state

    def undo(self):
        """The state to restore, or None when there is nothing to undo."""
        if not self._undo:
            return None
        self._redo.append(self._current)
        self._current = self._undo.pop()
        return self._current

    def redo(self):
        if not self._redo:
            return None
        self._undo.append(self._current)
        self._current = self._redo.pop()
        return self._current
