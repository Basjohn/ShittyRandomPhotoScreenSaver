"""Process-local authority for the active retained Widget Theme.

This mirrors ``ui.settings_theme_runtime`` but remains Qt-free.  The current
migration only needs construction-time reads; subscription exists so the future
Widget Themes UI can refresh retained presentations without adding polling or a
second theme authority.
"""

from __future__ import annotations

from collections.abc import Callable

from ui.widget_theme_spec import DEFAULT_DARK_WIDGET_THEME, WidgetThemeSpec


WidgetThemeListener = Callable[[WidgetThemeSpec], None]

_active_theme = DEFAULT_DARK_WIDGET_THEME
_listeners: list[WidgetThemeListener] = []


def get_active_widget_theme() -> WidgetThemeSpec:
    return _active_theme


def subscribe_widget_theme(
    listener: WidgetThemeListener,
    *,
    call_immediately: bool = False,
) -> Callable[[], None]:
    if not callable(listener):
        raise TypeError("Widget theme listener must be callable")
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


def set_active_widget_theme(theme: WidgetThemeSpec) -> bool:
    global _active_theme
    if not isinstance(theme, WidgetThemeSpec):
        raise TypeError("Active Widget theme must be a WidgetThemeSpec")
    previous = _active_theme
    if theme == previous:
        return False
    _active_theme = theme
    notified: list[WidgetThemeListener] = []
    try:
        for listener in tuple(_listeners):
            notified.append(listener)
            listener(theme)
    except Exception:
        _active_theme = previous
        for listener in reversed(notified):
            try:
                listener(previous)
            except Exception:
                pass
        raise
    return True


def reset_active_widget_theme() -> bool:
    return set_active_widget_theme(DEFAULT_DARK_WIDGET_THEME)


__all__ = [
    "WidgetThemeListener",
    "get_active_widget_theme",
    "reset_active_widget_theme",
    "set_active_widget_theme",
    "subscribe_widget_theme",
]
