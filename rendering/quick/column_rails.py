"""CUSTOM list-column order, shared by retained QML projection and Edit transactions.

One widget-wide discrete permutation, never per-row offsets or provider state.
"""
from __future__ import annotations

from collections.abc import Sequence

COLUMN_RAILS_PAYLOAD_KEY = "column_rails"
COLUMN_RAIL_IDS: dict[str, tuple[str, ...]] = {
    "reddit": ("age", "ago", "title"),
    "reddit2": ("age", "ago", "title"),
    "gmail": ("timestamp", "sender", "subject"),
}


def normalize_column_rails(widget_id: str, value: object) -> tuple[str, ...] | None:
    """Accept only an exact family permutation; malformed/stale input is inert."""
    allowed = COLUMN_RAIL_IDS.get(widget_id)
    if allowed is None or not isinstance(value, (list, tuple)):
        return None
    if len(value) != len(allowed) or any(not isinstance(x, str) for x in value):
        return None
    result = tuple(value)
    return result if len(set(result)) == len(allowed) and set(result) == set(allowed) else None


def swap_column_rails(
    widget_id: str, current: Sequence[str], source: str, target: str
) -> tuple[str, ...] | None:
    """One completed drag = one swap, independent of the number of list rows."""
    order = normalize_column_rails(widget_id, current)
    if order is None or source == target or source not in order or target not in order:
        return None
    updated = list(order)
    first, second = updated.index(source), updated.index(target)
    updated[first], updated[second] = updated[second], updated[first]
    return tuple(updated)
