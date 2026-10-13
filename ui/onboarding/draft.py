"""Guided Setup's unsaved changes: a draft over the real Settings store.

``SettingsManager.set`` persists and publishes immediately, so the wizard never
talks to it directly.  Pages read and write this draft instead; nothing reaches
the user's settings until :meth:`SettingsDraft.commit` (Finish, or an explicit
"save" answer when leaving early).  :meth:`discard` drops everything and puts the
live Settings/Widget theme back, because the Theme page previews themes live.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_MISSING = object()
_THEME_KEYS = ("ui.settings_theme_selection", "widget_theme")
# Mutators that would bypass the draft; wizard code must never reach them.
_BLOCKED = ("set_", "reset", "import", "remove", "delete", "clear", "flush", "restore")


def _dig(value: Any, path: list[str]) -> Any:
    for part in path:
        if not isinstance(value, dict) or part not in value:
            return _MISSING
        value = value[part]
    return value


def _patch(value: Any, path: list[str], leaf: Any) -> Any:
    root = dict(value) if isinstance(value, dict) else {}
    target = root
    for part in path[:-1]:
        child = target.get(part)
        target[part] = dict(child) if isinstance(child, dict) else {}
        target = target[part]
    target[path[-1]] = deepcopy(leaf)
    return root


class SettingsDraft:
    """``get``/``set``-compatible view of the settings with uncommitted edits."""

    def __init__(self, settings) -> None:
        self._real = settings
        self._entries: list[tuple[str, Any]] = []
        from ui.settings_theme_runtime import get_active_settings_theme
        from ui.widget_theme_active import get_active_widget_theme
        self._settings_theme = get_active_settings_theme()
        self._widget_theme = get_active_widget_theme()

    @property
    def real(self):
        return self._real

    @property
    def pending(self) -> bool:
        return bool(self._entries)

    def get(self, key: str, default: Any = _MISSING) -> Any:
        value = _MISSING
        decided = False  # a recorded write at or above ``key`` shadows the real store
        for recorded, recorded_value in self._entries:
            if recorded == key:
                value, decided = deepcopy(recorded_value), True
            elif key.startswith(recorded + "."):
                found = _dig(recorded_value, key[len(recorded) + 1:].split("."))
                value, decided = (_MISSING if found is _MISSING else deepcopy(found)), True
            elif recorded.startswith(key + "."):
                if value is _MISSING and not decided:
                    value = self._real_get(key)
                value = _patch(value, recorded[len(key) + 1:].split("."), recorded_value)
                decided = True
        if value is _MISSING and not decided:
            return self._real_get(key, default)
        if value is _MISSING:
            return None if default is _MISSING else default
        return value

    def _real_get(self, key: str, default: Any = _MISSING) -> Any:
        value = self._real.get(key) if default is _MISSING else self._real.get(key, default)
        return deepcopy(value)

    def set(self, key: str, value: Any) -> None:
        from core.settings.display_selection import normalize_selection, selection_bindings, SELECTION_KEY, BINDINGS_KEY
        from core.settings.monitor_routes import current_screen_identities
        if key == SELECTION_KEY:
            selection = normalize_selection(value)
            if selection is None:
                from core.logging.logger import get_logger
                from core.settings.default_contract import require_canonical_default
                get_logger(__name__).warning("[DISPLAY_SELECTION] Invalid draft selection %r; repairing through profile default", value)
                selection = require_canonical_default(SELECTION_KEY, getattr(self._real, '_application', None))
            # Explicit authoring captures today's target, including the same
            # number after renumbering. Preview and Finish share this snapshot.
            self._record(BINDINGS_KEY, selection_bindings(selection, {}, current_screen_identities(), explicit=True))
            value = selection
        elif key == "display" and isinstance(value, dict) and "show_on_monitors" in value:
            value = deepcopy(value)
            selection = normalize_selection(value["show_on_monitors"])
            if selection is None:
                from core.logging.logger import get_logger
                from core.settings.default_contract import require_canonical_default
                get_logger(__name__).warning("[DISPLAY_SELECTION] Invalid draft selection %r; repairing through profile default", value["show_on_monitors"])
                selection = require_canonical_default(SELECTION_KEY, getattr(self._real, '_application', None))
            value["show_on_monitors"] = selection
            value["monitor_bindings"] = selection_bindings(
                selection, value.get("monitor_bindings", {}), current_screen_identities(),
                explicit="monitor_bindings" not in value,
            )
        self._record(key, value)

    def _record(self, key: str, value: Any) -> None:
        # A later whole-key write supersedes earlier writes to it or beneath it.
        self._entries = [(k, v) for k, v in self._entries if k != key and not k.startswith(key + ".")]
        self._entries.append((key, deepcopy(value)))

    def ensure_display_monitor_bindings(self) -> None:
        """Resolve an unbound legacy draft without writing through to real Settings."""
        from core.settings.display_selection import SELECTION_KEY, BINDINGS_KEY, selection_bindings
        from core.settings.monitor_routes import current_screen_identities
        screens = current_screen_identities()
        if not screens:
            from PySide6.QtCore import QThread
            from PySide6.QtGui import QGuiApplication
            app = QGuiApplication.instance()
            if not isinstance(app, QGuiApplication) or QThread.currentThread() != app.thread():
                return
        old = self.get(BINDINGS_KEY, {})
        bindings = selection_bindings(self.get(SELECTION_KEY), old, screens)
        if bindings != old:
            self._record(BINDINGS_KEY, bindings)

    def save(self) -> None:
        """Persistence is explicit: only :meth:`commit` saves."""

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self.get(key)
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def get_widgets_map(self) -> dict:
        widgets = self.get("widgets")
        return widgets if isinstance(widgets, dict) else {}

    def persist_now(self, key: str, value: Any) -> None:
        """An explicit save button (e.g. Save to Slot) writes straight through."""
        self.set(key, value)
        if key == "display.show_on_monitors":
            self._real.set("display", {"show_on_monitors": self.get(key),
                                       "monitor_bindings": self.get("display.monitor_bindings")})
        else:
            self._real.set(key, deepcopy(value))
        self._real.save()

    def commit(self) -> None:
        display = {}
        for key, value in self._entries:
            if key == "display":
                display = deepcopy(value)
            elif key.startswith("display."):
                display = _patch(display, key[len("display."):].split("."), value)
        # Carry staged physical bindings together with selection; Finish must
        # not recapture a different screen from its current enumeration.
        if display:
            self._real.set("display", display)
        for key, value in self._entries:
            if key != "display" and not key.startswith("display."):
                self._real.set(key, value)
        self._real.save()
        self._entries = []

    def discard(self) -> None:
        touched_theme = any(key == theme or key.startswith(theme + ".") for key, _ in self._entries for theme in _THEME_KEYS)
        self._entries = []
        if touched_theme:
            from ui.settings_theme_runtime import set_active_settings_theme
            from ui.widget_theme_active import set_active_widget_theme
            set_active_settings_theme(self._settings_theme)
            set_active_widget_theme(self._widget_theme)

    def __getattr__(self, name: str):
        if name.startswith("_") or name.startswith(_BLOCKED):
            raise AttributeError(f"SettingsDraft does not forward {name!r}; the wizard writes only through set()")
        return getattr(self._real, name)
