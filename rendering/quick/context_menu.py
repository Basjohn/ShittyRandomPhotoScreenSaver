"""Retained Quick context-menu state and semantic action admission."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtGui import QColor

from core.settings.shadow_direction import (
    resolve_directional_extensions,
    resolve_signed_offset,
)
from ui.settings_theme_spec import Rgba
from ui.widget_theme_active import get_active_widget_theme
from ui.widget_visual_roles import resolve_widget_visual_color


_CONTEXT_MENU_SHADOW_BASE = (4.0, 4.0)


def _bounded_float(value: object, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float(default)
    return max(low, min(high, parsed))


def _as_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default if value is None else bool(value)


def _shadow_rgba(value: object) -> tuple[int, int, int, int]:
    if isinstance(value, QColor):
        color = QColor(value)
    elif isinstance(value, (tuple, list)) and len(value) in {3, 4}:
        channels = list(value)
        if len(channels) == 3:
            channels.append(255)
        try:
            color = QColor(*(max(0, min(255, int(v))) for v in channels))
        except (TypeError, ValueError):
            color = QColor(0, 0, 0, 255)
    else:
        color = QColor(str(value)) if value is not None else QColor()
    if not color.isValid():
        color = QColor(0, 0, 0, 255)
    return color.red(), color.green(), color.blue(), color.alpha()


@dataclass(frozen=True, slots=True)
class QuickContextMenuShadowStyle:
    """Generation-scoped projection of the canonical widget shadow controls."""

    enabled: bool
    color: tuple[int, int, int, int]
    blur: float
    offset_x: float
    offset_y: float
    extend_left: float
    extend_top: float
    extend_right: float
    extend_bottom: float


def project_quick_context_menu_shadow(
    shadow_values: Mapping[str, object],
) -> QuickContextMenuShadowStyle:
    """Project global Card shadow semantics onto the retained context menu.

    The context menu is a runtime overlay, so it follows the same Card shadow
    direction/opacity/blur/Extra Offset contract as widgets. Direction and Extra
    Offset are asymmetric geometry; Qt's effect offset stays zero so the opposite
    edge never loses coverage.
    """

    direction = shadow_values.get("direction", "SE")
    frame_extra = _bounded_float(
        shadow_values.get("frame_extra_offset"), 0.0, 0.0, 40.0
    )
    frame_opacity = _bounded_float(
        shadow_values.get("frame_opacity"), 0.77, 0.0, 1.0
    )
    blur = _bounded_float(shadow_values.get("blur_radius"), 18.0, 0.0, 128.0)
    rgba = list(_shadow_rgba(shadow_values.get("color", (0, 0, 0, 255))))
    rgba[3] = max(0, min(255, int(round(rgba[3] * frame_opacity))))
    offset_x, offset_y = resolve_signed_offset(direction, *_CONTEXT_MENU_SHADOW_BASE)
    left, top, right, bottom = resolve_directional_extensions(direction, frame_extra)
    return QuickContextMenuShadowStyle(
        enabled=_as_bool(shadow_values.get("enabled"), True),
        color=tuple(rgba),
        blur=blur,
        offset_x=float(offset_x),
        offset_y=float(offset_y),
        extend_left=float(left),
        extend_top=float(top),
        extend_right=float(right),
        extend_bottom=float(bottom),
    )


@dataclass(frozen=True, slots=True)
class QuickContextMenuPaletteStyle:
    """Generation-scoped semantic palette for the retained Context Menu."""

    menu_surface: tuple[int, int, int, int]
    menu_border: tuple[int, int, int, int]
    menu_text: tuple[int, int, int, int]
    menu_selected_surface: tuple[int, int, int, int]
    menu_separator: tuple[int, int, int, int]
    menu_indicator_border: tuple[int, int, int, int]
    menu_indicator_fill: tuple[int, int, int, int]
    menu_arrow: tuple[int, int, int, int]
    submenu_surface: tuple[int, int, int, int]
    submenu_border: tuple[int, int, int, int]
    submenu_text: tuple[int, int, int, int]
    submenu_selected_surface: tuple[int, int, int, int]
    submenu_checked_text: tuple[int, int, int, int]
    submenu_checked_surface: tuple[int, int, int, int]
    submenu_indicator_border: tuple[int, int, int, int]
    submenu_indicator_fill: tuple[int, int, int, int]


def project_quick_context_menu_palette() -> QuickContextMenuPaletteStyle:
    """Resolve the active Widget Theme once for one display generation.

    The Context Menu has no per-family override layer, so its palette consumes the
    active Widget Theme directly. Default Dark materializes the physically accepted
    current menu pixels, while sparse schema-v2 detail roles inherit through the
    shared semantic role graph. No Settings or catalogue read occurs here.
    """

    theme = get_active_widget_theme()

    def resolved(role: str, fallback: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        return resolve_widget_visual_color(
            theme,
            role,
            fallback=Rgba(*fallback),
        ).color.as_tuple()

    return QuickContextMenuPaletteStyle(
        menu_surface=resolved("context.menu.surface", (27, 29, 36, 242)),
        menu_border=resolved("context.menu.border", (216, 243, 255, 255)),
        menu_text=resolved("context.menu.text", (246, 248, 255, 255)),
        menu_selected_surface=resolved(
            "context.menu.selected_surface", (119, 185, 232, 79)
        ),
        menu_separator=resolved("context.menu.separator", (89, 119, 138, 255)),
        menu_indicator_border=resolved(
            "context.menu.indicator.border", (185, 234, 255, 255)
        ),
        menu_indicator_fill=resolved(
            "context.menu.indicator.fill", (130, 205, 255, 255)
        ),
        menu_arrow=resolved("context.menu.arrow", (216, 243, 255, 255)),
        submenu_surface=resolved("context.submenu.surface", (27, 29, 36, 242)),
        submenu_border=resolved("context.submenu.border", (216, 243, 255, 255)),
        submenu_text=resolved("context.submenu.text", (246, 248, 255, 255)),
        submenu_selected_surface=resolved(
            "context.submenu.selected_surface", (119, 185, 232, 79)
        ),
        submenu_checked_text=resolved(
            "context.submenu.checked_text", (185, 234, 255, 255)
        ),
        submenu_checked_surface=resolved(
            "context.submenu.checked_surface", (78, 113, 139, 51)
        ),
        submenu_indicator_border=resolved(
            "context.submenu.indicator.border", (185, 234, 255, 255)
        ),
        submenu_indicator_fill=resolved(
            "context.submenu.indicator.fill", (130, 205, 255, 255)
        ),
    )


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


def enforce_single_visible_context_menu(
    models: Iterable["QuickContextMenuModel"],
    opened_model: "QuickContextMenuModel",
) -> list["QuickContextMenuModel"]:
    """Dismiss every retained menu model except the one that just opened.

    There is exactly one product context menu globally: opening one display's
    menu must retire any menu still visible on another display. This is a pure
    coordination helper over the per-generation menu models the cross-display
    owner already holds; it creates no new menu, window or surface. A model whose
    C++ object has already retired is skipped rather than raising. Returns the
    models that were actually dismissed by this call.
    """

    dismissed: list["QuickContextMenuModel"] = []
    for model in models:
        if model is opened_model:
            continue
        try:
            if model.dismiss():
                dismissed.append(model)
        except RuntimeError:
            # A concurrently retiring generation's model may already be gone;
            # single-menu enforcement must never fault on a dead sibling.
            continue
    return dismissed


__all__ = [
    "QuickContextMenuEntry",
    "QuickContextMenuPaletteStyle",
    "QuickContextMenuShadowStyle",
    "QuickContextMenuModel",
    "build_quick_context_menu_entries",
    "enforce_single_visible_context_menu",
    "project_quick_context_menu_palette",
    "project_quick_context_menu_shadow",
]
