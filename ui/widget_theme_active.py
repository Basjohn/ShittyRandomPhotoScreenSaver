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
_active_material_mode = "normal"
_listeners: list[WidgetThemeListener] = []


def get_active_widget_theme() -> WidgetThemeSpec:
    return _active_theme


def get_active_widget_material_mode() -> str:
    """Return the admitted renderer-facing material for this generation.

    Phase 1 keeps the retained renderer Normal-only even when a theme file
    recommends Glass/Acrylic.  This process-local snapshot prevents a theme
    recommendation from looking live before the shared material path exists.
    """

    return _active_material_mode


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


def set_active_widget_theme(
    theme: WidgetThemeSpec,
    *,
    material_mode: str = "normal",
) -> bool:
    global _active_theme, _active_material_mode
    if not isinstance(theme, WidgetThemeSpec):
        raise TypeError("Active Widget theme must be a WidgetThemeSpec")
    normalized_material = str(material_mode or "normal").strip().lower()
    if normalized_material not in {"normal", "glass", "acrylic"}:
        normalized_material = "normal"
    previous = _active_theme
    previous_material = _active_material_mode
    if theme == previous and normalized_material == previous_material:
        return False
    _active_theme = theme
    _active_material_mode = normalized_material
    notified: list[WidgetThemeListener] = []
    try:
        for listener in tuple(_listeners):
            notified.append(listener)
            listener(theme)
    except Exception:
        _active_theme = previous
        _active_material_mode = previous_material
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
    "get_active_widget_material_mode",
    "get_active_widget_theme",
    "reset_active_widget_theme",
    "set_active_widget_theme",
    "subscribe_widget_theme",
]
