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
from os import PathLike
from time import perf_counter_ns

from core.logging.logger import get_logger

from ui.settings_theme_spec import (
    DEFAULT_DARK_SETTINGS_THEME,
    SettingsThemeSpec,
)


SettingsThemeListener = Callable[[SettingsThemeSpec], None]

logger = get_logger(__name__)

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

    transaction_started_ns = perf_counter_ns()
    listener_timings: list[tuple[str, float]] = []
    try:
        for listener in listeners:
            notified.append(listener)
            listener_started_ns = perf_counter_ns()
            listener(theme)
            elapsed_ms = (perf_counter_ns() - listener_started_ns) / 1_000_000.0
            listener_name = (
                f"{getattr(listener, '__module__', '<unknown>')}."
                f"{getattr(listener, '__qualname__', getattr(listener, '__name__', type(listener).__name__))}"
            )
            listener_timings.append((listener_name, elapsed_ms))
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

    total_ms = (perf_counter_ns() - transaction_started_ns) / 1_000_000.0
    detail = ", ".join(
        f"{name}={elapsed_ms:.2f}ms" for name, elapsed_ms in listener_timings
    )
    logger.info(
        "[PERF][SETTINGS_THEME] theme=%s total=%.2fms listeners=[%s]",
        theme.name,
        total_ms,
        detail,
    )
    return True


def reset_active_settings_theme() -> bool:
    """Restore the built-in Default Dark theme through the normal live path."""

    return set_active_settings_theme(DEFAULT_DARK_SETTINGS_THEME)


def activate_settings_theme_file(
    path: str | PathLike[str] | None,
):
    """Safely activate one optional file-backed theme.

    File absence or any parse/schema/semantic validation failure activates the
    compiled-in Default Dark ThemeSpec. The returned load result preserves the
    error detail for a future Themes UI without making Settings depend on disk
    theme files.
    """

    from ui.settings_theme_io import load_settings_theme_or_default

    result = load_settings_theme_or_default(path)
    set_active_settings_theme(result.theme)
    return result


__all__ = [
    "SettingsThemeListener",
    "activate_settings_theme_file",
    "get_active_settings_theme",
    "reset_active_settings_theme",
    "set_active_settings_theme",
    "subscribe_settings_theme",
]
