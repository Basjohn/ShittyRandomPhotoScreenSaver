"""Which displays ``display.show_on_monitors`` selects: one parser for the saver and Settings.

``show_on_monitors`` is ``"ALL"``, ``"NONE"``, a list of 1-based display numbers, or (historically)
that list written as a string. Numbers of displays that are not present are ignored.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable

from core.settings.default_contract import require_canonical_default


def selected_monitor_numbers(raw: object, screen_count: int) -> frozenset[int] | None:
    """The 1-based numbers of the present displays (``screen_count`` of them) that ``raw`` selects.

    None when ``raw`` is malformed or selects only displays that are not present: callers repair
    through the canonical value, never through an implicit "show everything".
    """

    every = frozenset(range(1, max(0, int(screen_count)) + 1))
    candidate = raw
    if isinstance(candidate, str):
        normalized = candidate.strip().upper()
        if normalized == "ALL":
            return every
        if normalized == "NONE":
            return frozenset()
        try:
            candidate = ast.literal_eval(candidate)
        except Exception:  # literal_eval raises several types on malformed text
            return None
    if not isinstance(candidate, (list, tuple, set, frozenset)):
        return None
    try:
        numbers = {int(value) for value in candidate}
    except (TypeError, ValueError):
        return None
    selected = frozenset(numbers) & every
    return selected or None


def enabled_monitor_numbers(raw: object, screen_count: int) -> frozenset[int]:
    """The displays the saver shows: ``raw`` repaired through the canonical selection."""

    selected = selected_monitor_numbers(raw, screen_count)
    if selected is not None:
        return selected
    canonical = require_canonical_default("display.show_on_monitors")
    selected = selected_monitor_numbers(canonical, screen_count)
    if selected is None:
        raise ValueError(f"canonical display.show_on_monitors is invalid for topology: {canonical!r}")
    return selected


def describe_monitors(numbers: Iterable[int]) -> str:
    """"Display 2" or "Displays 2 and 3"."""

    ordered = [str(number) for number in sorted(numbers)]
    if len(ordered) == 1:
        return f"Display {ordered[0]}"
    return f"Displays {', '.join(ordered[:-1])} and {ordered[-1]}"
