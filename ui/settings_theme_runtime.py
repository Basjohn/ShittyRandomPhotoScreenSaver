"""Runtime authority for the active Settings ThemeSpec.

This module deliberately has no Qt dependency. Renderers subscribe with stable
module-level callbacks and remain responsible for applying theme data to their
own widgets/native surfaces.

Theme changes are transactional at the listener boundary: if a renderer fails
while applying a new theme, the active theme is restored and every listener is
asked to reapply the previous theme before the original exception is re-raised.
"""

from __future__ import annotations

from collections.abc import Callable

from ui.settings_theme_spec import (
    DEFAULT_DARK_SETTINGS_THEME,
    SettingsThemeSpec,
)


SettingsThemeListener = Callable[[SettingsThemeSpec], None]

_active_theme = DEFAULT_DARK_SETTINGS_THEME
_listeners: list[SettingsThemeListener] = []


def get_active_settings_theme() -> SettingsThemeSpec:
    """Return the Settings ThemeSpec currently active in this process."""

    return _active_theme


def subscribe_settings_theme(
    listener: SettingsThemeListener,
    *,
    call_immediately: bool = False,
) -> Callable[[], None]:
    """Subscribe one stable renderer callback and return an unsubscribe closure."""

    if not callable(listener):
        raise TypeError("Settings theme listener must be callable")

    if listener not in _listeners:
        _listeners.append(listener)

    if call_immediately:
        listener(_active_theme)

    def unsubscribe() -> None:
        try:
            _listeners.remove(listener)
        except ValueError:
            pass

    return unsubscribe


def set_active_settings_theme(theme: SettingsThemeSpec) -> bool:
    """Activate ``theme`` and synchronously refresh subscribed renderers.

    Returns ``True`` when the active theme changed and ``False`` for an
    equivalent no-op assignment.
    """

    global _active_theme

    if not isinstance(theme, SettingsThemeSpec):
        raise TypeError("Active Settings theme must be a SettingsThemeSpec")

    previous = _active_theme
    if theme == previous:
        return False

    _active_theme = theme
    listeners = tuple(_listeners)
    notified: list[SettingsThemeListener] = []

    try:
        for listener in listeners:
            notified.append(listener)
            listener(theme)
    except Exception:
        _active_theme = previous
        for listener in reversed(notified):
            try:
                listener(previous)
            except Exception:
                # Preserve the original renderer failure. A rollback listener
                # failure is secondary and must not hide the initiating error.
                pass
        raise

    return True


def reset_active_settings_theme() -> bool:
    """Restore the built-in Default Dark theme through the normal live path."""

    return set_active_settings_theme(DEFAULT_DARK_SETTINGS_THEME)


__all__ = [
    "SettingsThemeListener",
    "get_active_settings_theme",
    "reset_active_settings_theme",
    "set_active_settings_theme",
    "subscribe_settings_theme",
]
