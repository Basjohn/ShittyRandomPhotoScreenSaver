"""Shared list-capacity policy for active list widgets.

This keeps active row/list widgets on one contract so UI ranges, runtime
clamps, staged growth, and preview/status surfaces do not drift apart.
"""
from __future__ import annotations

from typing import Any

LIST_WIDGET_MIN_CAPACITY = 5
LIST_WIDGET_STAGE_MID_CAPACITY = 10
LIST_WIDGET_MAX_CAPACITY = 25


def clamp_list_capacity(value: Any, *, default: int = LIST_WIDGET_MIN_CAPACITY) -> int:
    """Clamp a list-widget capacity into the shared first-stage envelope."""

    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = int(default)
    return max(LIST_WIDGET_MIN_CAPACITY, min(LIST_WIDGET_MAX_CAPACITY, candidate))


def build_progressive_capacity_stages(target_capacity: Any) -> list[int]:
    """Build canonical staged growth limits for progressive list widgets."""

    target = clamp_list_capacity(target_capacity)
    stages = [LIST_WIDGET_MIN_CAPACITY]
    if target > LIST_WIDGET_MIN_CAPACITY:
        second = min(LIST_WIDGET_STAGE_MID_CAPACITY, target)
        if second != stages[-1]:
            stages.append(second)
    if target > LIST_WIDGET_STAGE_MID_CAPACITY and target != stages[-1]:
        stages.append(target)
    return stages
