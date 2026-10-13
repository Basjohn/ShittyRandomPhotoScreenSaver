"""Canonical saver selection: numbers are authoring labels bound to physical screens."""
from __future__ import annotations
import ast
from collections.abc import Iterable, Mapping, Sequence
from core.settings.default_contract import require_canonical_default

SELECTION_KEY = "display.show_on_monitors"
BINDINGS_KEY = "display.monitor_bindings"


def normalize_selection(raw: object) -> str | list[int] | None:
    if isinstance(raw, str):
        token = raw.strip().upper()
        if token in ("ALL", "NONE"):
            return token
        try:
            raw = ast.literal_eval(raw)
        except (ValueError, SyntaxError, TypeError):
            return None
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return None
    numbers = set()
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            return None
        try:
            number = int(value)
        except (ValueError, TypeError):
            return None
        if number < 1:
            return None
        numbers.add(number)
    return sorted(numbers) if numbers else "NONE"


def selected_monitor_numbers(raw: object, screen_count: int) -> frozenset[int] | None:
    selection = normalize_selection(raw)
    if selection is None:
        return None
    every = frozenset(range(1, max(0, int(screen_count)) + 1))
    if selection == "ALL":
        return every
    if selection == "NONE":
        return frozenset()
    return frozenset(selection) & every


def enabled_monitor_numbers(raw: object, screen_count: int, *, profile: str | None = None) -> frozenset[int]:
    selected = selected_monitor_numbers(raw, screen_count)
    if selected is None:
        selected = selected_monitor_numbers(require_canonical_default(SELECTION_KEY, profile), screen_count)
    if selected is None:
        raise ValueError("Invalid canonical display selection")
    return selected


def selection_bindings(raw: object, bindings: object, screens: Sequence[str], *, explicit: bool = False) -> dict:
    """Capture once; an unresolved numbered target stays unresolved until authored again."""
    selection = normalize_selection(raw)
    if not isinstance(selection, list):
        return {}
    incoming = bindings if isinstance(bindings, Mapping) else {}
    from rendering.custom_layout_contract import normalize_screen_signature
    result = {}
    for number in selection:
        key = str(number)
        identity = incoming.get(key)
        if not explicit and key in incoming and (identity is None or isinstance(identity, str) and identity):
            result[key] = normalize_screen_signature(identity) if identity else None
        else:
            result[key] = normalize_screen_signature(screens[number - 1]) if number <= len(screens) else None
    return result


def resolve_monitor_numbers(settings, screens: Sequence[str] | None = None) -> frozenset[int]:
    from core.settings.monitor_routes import current_screen_identities, bound_monitor_index
    if screens is None:
        screens = current_screen_identities()
    ensure = getattr(settings, "ensure_display_monitor_bindings", None)
    if ensure is not None:
        ensure()
    raw = settings.get(SELECTION_KEY)
    selection = normalize_selection(raw)
    if selection is None:
        selection = normalize_selection(require_canonical_default(SELECTION_KEY, getattr(settings, '_application', None)))
    if not isinstance(selection, list):
        return enabled_monitor_numbers(selection, len(screens))
    bindings = settings.get(BINDINGS_KEY, {})
    bindings = selection_bindings(selection, bindings, screens)
    return frozenset(index + 1 for identity in bindings.values() if identity
                     for index in (bound_monitor_index(identity, screens),) if index < len(screens))


def describe_monitors(numbers: Iterable[int]) -> str:
    ordered = [str(number) for number in sorted(numbers)]
    if len(ordered) == 1:
        return f"Display {ordered[0]}"
    return f"Displays {', '.join(ordered[:-1])} and {ordered[-1]}"
