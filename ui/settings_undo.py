"""Undo / redo of the edits made in one Settings session with its sliders and visual editors.

One owner per Settings dialog (``SettingsUndo``) keeps a short history of user edits across every page: Ctrl+Z
undoes the most recent, Ctrl+Y / Ctrl+Shift+Z redoes it. Memory only, for this session: nothing persists and the
history ends with the dialog.

Controls record **user gestures only** (``record_edit``: a drag from press to release, a key step, a picked colour,
a terrain stroke, a camera gesture), never values set by loading, presets or an undo itself, so undo can apply the old
value the same way a user edit would (the page saves it, switches to Custom and so on as for any edit). Controls
outside a Settings dialog (Guided Setup and the like) record nothing. Text fields keep their own native Ctrl+Z while
focused.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QWidget

SETTINGS_UNDO_DEPTH = 30
SETTINGS_UNDO_ATTR = "settings_undo"


@dataclass(frozen=True)
class _Edit:
    owner: QWidget
    before: Any
    after: Any
    apply: Callable[[Any], None]


def _alive(widget) -> bool:
    try:
        from shiboken6 import isValid
        return bool(isValid(widget))
    except Exception:
        return widget is not None


class SettingsUndo(QObject):
    """A Settings dialog's undo/redo of user edits (see the module doc)."""

    def __init__(self, dialog: QWidget, depth: int = SETTINGS_UNDO_DEPTH) -> None:
        super().__init__(dialog)
        self._undo: deque[_Edit] = deque(maxlen=depth)
        self._redo: deque[_Edit] = deque(maxlen=depth)
        self._applying = False
        self.generation = 0          # bumped by every undo/redo: a gesture it interrupts records nothing
        setattr(dialog, SETTINGS_UNDO_ATTR, self)
        self._shortcuts = []
        for sequence, action in ((QKeySequence.StandardKey.Undo, self.undo),
                                 (QKeySequence.StandardKey.Redo, self.redo),
                                 (QKeySequence("Ctrl+Shift+Z"), self.redo)):
            shortcut = QShortcut(QKeySequence(sequence), dialog)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(action)
            self._shortcuts.append(shortcut)

    @property
    def can_undo(self) -> bool:
        return any(_alive(edit.owner) for edit in self._undo)

    @property
    def can_redo(self) -> bool:
        return any(_alive(edit.owner) for edit in self._redo)

    def record(self, owner: QWidget, before, after, apply: Callable[[Any], None]) -> None:
        """A user edit on ``owner``: ``apply(state)`` puts ``before`` / ``after`` back as a user edit would."""
        if self._applying or before == after:
            return
        self._undo.append(_Edit(owner, before, after, apply))
        self._redo.clear()

    def undo(self) -> bool:
        return self._step(self._undo, self._redo, "before")

    def redo(self) -> bool:
        return self._step(self._redo, self._undo, "after")

    def _step(self, source: deque, target: deque, field: str) -> bool:
        while source:
            edit = source.pop()
            if not _alive(edit.owner):
                continue                 # its page was rebuilt or closed: that edit is gone
            self._applying = True
            self.generation += 1
            try:
                edit.apply(getattr(edit, field))
            finally:
                self._applying = False
            target.append(edit)
            return True
        return False


def settings_undo_for(widget) -> SettingsUndo | None:
    """The undo owner of the Settings dialog ``widget`` lives in, if any."""
    if widget is None or not _alive(widget):
        return None
    window = widget.window()
    return getattr(window, SETTINGS_UNDO_ATTR, None) if window is not None else None


def record_edit(widget, before, after, apply: Callable[[Any], None]) -> None:
    """Record a user edit made with ``widget`` (a no-op outside a Settings dialog)."""
    owner = settings_undo_for(widget)
    if owner is not None:
        owner.record(widget, before, after, apply)


_PRESSES = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick, QEvent.Type.KeyPress)
_RELEASES = (QEvent.Type.MouseButtonRelease, QEvent.Type.KeyRelease)
_MODIFIER_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Shift, Qt.Key.Key_Alt, Qt.Key.Key_Meta}


def gesture_event(widget, event, base_event: Callable[[QEvent], bool], state: Callable[[], Any],
                  apply: Callable[[Any], None]) -> bool:
    """A control's ``event()``: a mouse or key press opens a gesture (``state()`` before it); its release records
    the edit, if the state changed. Only user input opens gestures, so loading, presets and undo record nothing."""
    kind = event.type()
    keyed = kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease)
    if keyed and event.key() in _MODIFIER_KEYS:
        return base_event(event)
    if kind in _PRESSES and getattr(widget, "_undo_gesture", None) is None:
        owner = settings_undo_for(widget)
        widget._undo_gesture = (state(), owner.generation) if owner is not None else None
    handled = base_event(event)
    if kind in _RELEASES and not (keyed and event.isAutoRepeat()):
        gesture, widget._undo_gesture = getattr(widget, "_undo_gesture", None), None
        owner = settings_undo_for(widget) if gesture is not None else None
        if owner is not None and owner.generation == gesture[1]:
            owner.record(widget, gesture[0], state(), apply)
    return handled


__all__ = ["SETTINGS_UNDO_DEPTH", "SettingsUndo", "gesture_event", "record_edit", "settings_undo_for"]
