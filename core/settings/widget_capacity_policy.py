"""Shared list-capacity policy for active list widgets.

This keeps active row/list widgets on one contract so UI ranges, runtime
clamps, fetch-cache envelopes, and preview/status surfaces do not drift apart.
"""
from __future__ import annotations

from typing import Any

LIST_WIDGET_MIN_CAPACITY = 5
LIST_WIDGET_MAX_CAPACITY = 25


def clamp_list_capacity(value: Any, *, default: int = LIST_WIDGET_MIN_CAPACITY) -> int:
    """Clamp a list-widget visible capacity into the shared candidate envelope."""

    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = int(default)
    return max(LIST_WIDGET_MIN_CAPACITY, min(LIST_WIDGET_MAX_CAPACITY, candidate))
