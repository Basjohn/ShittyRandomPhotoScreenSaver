"""Pure adaptive layout decision for the future retained Games You Follow card.

Only accepted display rows are laid out. This calculator cannot change a
followed set, perform a network refresh, or write back the parent's size.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class FollowedNewsLayout:
    arrangement: str
    columns: int
    rows: int
    visible_count: int
    overflow_count: int


def followed_news_layout(
    width: float, height: float, item_count: int,
    *, previous_arrangement: str | None = None,
) -> FollowedNewsLayout:
    """Choose the three card shapes with a resize-state hysteresis deadband."""
    if (not math.isfinite(width) or not math.isfinite(height)
        or width < 0 or height < 0 or type(item_count) is not int):
        raise ValueError("Invalid followed-news display extent or row count")
    count = max(0, min(8, item_count))
    ratio = width / height if height else 0.0
    # Re-enter wide/tall only beyond the *outer* threshold. Retain an existing
    # orientation until the *inner* threshold is crossed. Tiny pointer movement
    # around an aspect boundary cannot retire/recreate repeated story delegates.
    if previous_arrangement == "wide" and ratio >= 1.55:
        arrangement = "wide"
    elif previous_arrangement == "tall" and ratio <= 0.86:
        arrangement = "tall"
    elif ratio >= 1.75:
        arrangement = "wide"
    elif ratio <= 0.72:
        arrangement = "tall"
    else:
        arrangement = "grid"
    # The header/overflow are family chrome, not additional story rows. A card
    # too small for one readable tile shows a truthful overflow summary instead.
    available_width = max(0.0, width - 32.0)
    available_height = max(0.0, height - 104.0)
    cols_fit = int((available_width + 8.0) // 180.0)
    rows_fit = int((available_height + 8.0) // 112.0)
    if arrangement == "wide":
        cols, rows = min(8, cols_fit), min(1, rows_fit)
    elif arrangement == "tall":
        cols, rows = min(1, cols_fit), min(8, rows_fit)
    else:
        cols, rows = min(8, cols_fit), min(8, rows_fit)
    capacity = max(0, cols * rows)
    visible = min(count, capacity)
    return FollowedNewsLayout(arrangement, cols, rows, visible, count - visible)
