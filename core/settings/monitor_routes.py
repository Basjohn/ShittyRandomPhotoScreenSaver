"""Physical widget assignments; display numbers are authoring labels, not hotplug identity.

Settings captures numbered routes once, or when a route is explicitly changed.
Runtime admission compares the same stable identities as CUSTOM geometry. No
topology edge rewrites an assignment or borrows another display's layout.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

BINDINGS_KEY = "monitor_bindings"


def current_screen_identities() -> tuple[str, ...]:
    from PySide6.QtCore import QThread
    from PySide6.QtGui import QGuiApplication
    from rendering.custom_layout_contract import get_screen_signature

    app = QGuiApplication.instance()
    if not isinstance(app, QGuiApplication) or QThread.currentThread() != app.thread():
        return ()
    return tuple(get_screen_signature(screen) for screen in app.screens())


def numbered_route(value: object) -> str | None:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return str(number) if number > 0 else None


def bound_monitor_identity(widgets: Mapping, section: str, route: object) -> str | None:
    bindings = widgets.get(BINDINGS_KEY, {})
    binding = bindings.get(section) if isinstance(bindings, Mapping) else None
    if not isinstance(binding, Mapping) or binding.get("monitor") != numbered_route(route):
        return None
    identity = binding.get("screen")
    if not isinstance(identity, str) or not identity:
        return None
    from rendering.custom_layout_contract import normalize_screen_signature
    return normalize_screen_signature(identity)


def reconcile_monitor_bindings(
    widgets: Mapping,
    previous: Mapping,
    screens: Sequence[str],
) -> dict:
    """Keep unchanged assignments; bind changed/unbound numbered routes once.

    The map is part of the widgets transaction, so layout slots and imports can
    carry their own assignments. A stale binding accompanying a changed number
    is replaced. ALL has no physical binding. Missing targets stay unresolved.
    """
    result = {}
    incoming = widgets.get(BINDINGS_KEY, {})
    if not isinstance(incoming, Mapping):
        incoming = {}
    for section, values in widgets.items():
        if not isinstance(values, Mapping) or "monitor" not in values:
            continue
        route = numbered_route(values["monitor"])
        if route is None:
            continue
        identity = bound_monitor_identity(widgets, section, route)
        old_values = previous.get(section, {})
        # Older Settings page serializers do not own routing metadata. Preserve
        # the existing binding on unrelated saves, including while unplugged.
        if identity is None and BINDINGS_KEY not in widgets and isinstance(old_values, Mapping):
            if numbered_route(old_values.get("monitor")) == route:
                identity = bound_monitor_identity(previous, section, route)
        # Existing CUSTOM geometry can establish a legacy route even when its
        # display is already unplugged on first upgraded run. A changed route
        # or explicit new binding always wins over that old authored bucket.
        if (identity is None and section not in incoming
                and isinstance(old_values, Mapping)
                and numbered_route(old_values.get("monitor")) == route
                and str(values.get("position", "")).lower() == "custom"):
            layout = widgets.get("custom_layout", {})
            displays = layout.get("displays", {}) if isinstance(layout, Mapping) else {}
            if isinstance(displays, Mapping):
                from rendering.custom_layout_contract import normalize_screen_signature
                homes = {
                    normalize_screen_signature(key)
                    for key, entries in displays.items()
                    if isinstance(key, str) and isinstance(entries, Mapping)
                    and isinstance(entries.get(section), Mapping) and entries[section]
                }
                if len(homes) == 1:
                    identity = homes.pop()
        if identity is None and int(route) <= len(screens):
            identity = screens[int(route) - 1]
        if identity:
            result[section] = {"monitor": route, "screen": identity}
    return result


def bound_monitor_index(identity: str, screens: Sequence[str]) -> int:
    """Absent is a positive out-of-range index, never the ALL sentinel (-1)."""
    from rendering.custom_layout_contract import normalize_screen_signature
    expected = normalize_screen_signature(identity)
    matches = [i for i, screen in enumerate(screens) if normalize_screen_signature(screen) == expected]
    return matches[0] if len(matches) == 1 else len(screens)
