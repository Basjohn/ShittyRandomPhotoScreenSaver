"""Retained Quick context-menu state and semantic action admission."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot


@dataclass(frozen=True, slots=True)
class QuickContextMenuEntry:
    """One immutable menu row or submenu descriptor."""

    action_id: str
    label: str
    payload: str = ""
    kind: str = "action"
    enabled: bool = True
    checked: bool = False
    children: tuple["QuickContextMenuEntry", ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "actionId": self.action_id,
            "label": self.label,
            "payload": self.payload,
            "kind": self.kind,
            "enabled": self.enabled,
            "checked": self.checked,
            "children": [child.as_dict() for child in self.children],
        }


def build_quick_context_menu_entries(
    *,
    transition_names: Iterable[str],
    current_transition: str,
    random_enabled: bool,
    random_selectable: bool,
    visualizer_modes: Iterable[tuple[str, str]],
    current_visualizer: str,
    visualizer_available: bool,
    dimming_enabled: bool,
    interaction_mode_enabled: bool,
    interaction_mode_locked: bool,
    edit_mode_active: bool,
    layout_actions_available: bool = True,
) -> tuple[QuickContextMenuEntry, ...]:
    """Build the retained equivalent of the admitted product menu structure."""

    transitions = (
        QuickContextMenuEntry(
            "transition",
            "Random",
            payload="Random",
            kind="choice",
            enabled=bool(random_selectable),
            checked=bool(random_enabled),
        ),
        *(
            QuickContextMenuEntry(
                "transition",
                str(name),
                payload=str(name),
                kind="choice",
                checked=(not random_enabled and str(name) == current_transition),
            )
            for name in transition_names
        ),
    )
    visualizers = tuple(
        QuickContextMenuEntry(
            "visualizer",
            str(label),
            payload=str(mode_id),
            kind="choice",
            checked=str(mode_id) == current_visualizer,
        )
        for mode_id, label in visualizer_modes
    )
    layout_entries = ()
    if layout_actions_available:
        layout_entries = (
            (
                QuickContextMenuEntry("save_layout", "✓  Save Widget Layout"),
                QuickContextMenuEntry("cancel_layout", "↺  Cancel Widget Layout"),
                QuickContextMenuEntry("reset_layout", "⟲  Reset To Saved Layout"),
            )
            if edit_mode_active
            else (QuickContextMenuEntry("edit_layout", "✥  Edit Widget Layout"),)
        )
    entries = [
        QuickContextMenuEntry("previous", "◂  Previous Image"),
        QuickContextMenuEntry("next", "▸  Next Image"),
        QuickContextMenuEntry("", "", kind="separator"),
        QuickContextMenuEntry(
            "",
            "⟳  Change Transition",
            kind="submenu",
            children=tuple(transitions),
        ),
    ]
    if visualizer_available and visualizers:
        entries.append(
            QuickContextMenuEntry(
                "",
                "⟳  Change Visualizer",
                kind="submenu",
                children=visualizers,
            )
        )
    entries.extend(
        (
            QuickContextMenuEntry("", "", kind="separator"),
            QuickContextMenuEntry("settings", "⚙  Settings"),
            *layout_entries,
            QuickContextMenuEntry("", "", kind="separator"),
            QuickContextMenuEntry(
                "toggle_dimming",
                "◐  Background Dimming",
                kind="toggle",
                checked=bool(dimming_enabled),
            ),
            QuickContextMenuEntry(
                "toggle_interaction",
                "⊘  Interaction Mode",
                kind="toggle",
                enabled=not interaction_mode_locked,
                checked=(
                    True if interaction_mode_locked else bool(interaction_mode_enabled)
                ),
            ),
            QuickContextMenuEntry("", "", kind="separator"),
            QuickContextMenuEntry("exit", "✕  Exit Screensaver"),
        )
    )
    return tuple(entries)


class QuickContextMenuModel(QObject):
    """Own one display generation's retained menu state and action admission."""

    stateChanged = Signal()
    visibilityChanged = Signal(bool)

    def __init__(
        self,
        *,
        screen_index: int,
        runtime_generation: int | None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._screen_index = int(screen_index)
        self._runtime_generation = (
            None if runtime_generation is None else int(runtime_generation)
        )
        self._entries: tuple[QuickContextMenuEntry, ...] = ()
        self._entries_payload: list[dict[str, Any]] = []
        self._visible = False
        self._anchor_x = 0.0
        self._anchor_y = 0.0
        self._admission_open = True
        self._action_handler: Callable[[str, str], bool] | None = None

    @Property("QVariantList", notify=stateChanged)
    def entries(self) -> list[dict[str, Any]]:
        return list(self._entries_payload)

    @Property(bool, notify=stateChanged)
    def menuVisible(self) -> bool:
        return self._visible

    @Property(float, notify=stateChanged)
    def anchorX(self) -> float:
        return self._anchor_x

    @Property(float, notify=stateChanged)
    def anchorY(self) -> float:
        return self._anchor_y

    @property
    def screen_index(self) -> int:
        return self._screen_index

    @property
    def runtime_generation(self) -> int | None:
        return self._runtime_generation

    def replace_entries(self, entries: Iterable[QuickContextMenuEntry]) -> bool:
        normalized = tuple(entries)
        if not all(isinstance(entry, QuickContextMenuEntry) for entry in normalized):
            raise TypeError("Quick context menu entries must be QuickContextMenuEntry")
        if normalized == self._entries:
            return False
        self._entries = normalized
        self._entries_payload = [entry.as_dict() for entry in normalized]
        self.stateChanged.emit()
        return True

    def set_action_handler(
        self,
        handler: Callable[[str, str], bool] | None,
    ) -> None:
        self._action_handler = handler

    def open_at(self, x: float, y: float) -> bool:
        if not self._admission_open or not self._entries:
            return False
        self._anchor_x = float(x)
        self._anchor_y = float(y)
        if not self._visible:
            self._visible = True
            self.visibilityChanged.emit(True)
        self.stateChanged.emit()
        return True

    @Slot(result=bool)
    def dismiss(self) -> bool:
        if not self._visible:
            return False
        self._visible = False
        self.stateChanged.emit()
        self.visibilityChanged.emit(False)
        return True

    @Slot(str, str, bool, result=bool)
    def requestAction(self, action_id: str, payload: str, checked: bool) -> bool:
        normalized_action = str(action_id or "")
        normalized_payload = str(payload or "")
        entry = self._find_admitted_entry(normalized_action, normalized_payload)
        if entry is None:
            return False
        if entry.kind == "toggle":
            normalized_payload = "true" if bool(checked) else "false"
        handler = self._action_handler
        accepted = bool(
            handler is not None and handler(normalized_action, normalized_payload)
        )
        if accepted:
            self.dismiss()
        return accepted

    def close(self) -> bool:
        if not self._admission_open:
            return False
        self.dismiss()
        self._admission_open = False
        self._entries = ()
        self._entries_payload = []
        self._action_handler = None
        self.stateChanged.emit()
        return True

    def describe(self) -> dict[str, object]:
        return {
            "screen_index": self._screen_index,
            "runtime_generation": self._runtime_generation,
            "admission_open": self._admission_open,
            "visible": self._visible,
            "anchor": [self._anchor_x, self._anchor_y],
            "entry_count": len(self._entries),
        }

    def _find_admitted_entry(
        self,
        action_id: str,
        payload: str,
    ) -> QuickContextMenuEntry | None:
        if not self._admission_open or not self._visible or not action_id:
            return None

        def walk(
            entries: tuple[QuickContextMenuEntry, ...],
        ) -> QuickContextMenuEntry | None:
            for entry in entries:
                if (
                    entry.action_id == action_id
                    and entry.payload == payload
                    and entry.enabled
                    and entry.kind not in {"separator", "submenu"}
                ):
                    return entry
                nested = walk(entry.children)
                if nested is not None:
                    return nested
            return None

        return walk(self._entries)


__all__ = [
    "QuickContextMenuEntry",
    "QuickContextMenuModel",
    "build_quick_context_menu_entries",
]
