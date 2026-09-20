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
    *, previous_arrangement: str | None = None, show_artwork: bool = True,
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
    # Mirror the family QML's authored grouped rail: choose readable card
    # widths BEFORE columns, then admit as many whole rows as height permits.
    # Width and height remain independent and neither is fed back to the parent.
    minimum_tile_width = (180.0 if arrangement == "tall"
                          else 294.0 if show_artwork else 235.0)
    available_width = max(0.0, width - 28.0)
    cols_fit = int((available_width + 4.0) // minimum_tile_width)
    max_cols = 1 if arrangement == "tall" else 8 if arrangement == "wide" else 4
    cols = min(max_cols, cols_fit)
    authored_cols = max(1, cols)
    authored_rows = math.ceil(count / authored_cols)
    authored_group_height = min(max(0.0, height - 110.0),
                                authored_rows * 160.0 + max(0, authored_rows - 1) * 8.0)
    rows_fit = int((authored_group_height + 14.0) // 112.0)
    rows = min(8, rows_fit, math.ceil(count / max(1, cols))) if cols > 0 else 0
    capacity = max(0, cols * rows)
    visible = min(count, capacity)
    return FollowedNewsLayout(arrangement, cols, rows, visible, count - visible)
