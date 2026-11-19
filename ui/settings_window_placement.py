"""Pure geometry policy for Settings' frameless window.

Called only when an explicit drag/resize finishes or a persisted position is
restored.  No Qt imports, event-loop hooks, timers or runtime render work.
Coordinates and dimensions are *logical* pixels; caller supplies the chosen
screen's availableGeometry (taskbars excluded).
"""
from __future__ import annotations


DEFAULT_SNAP_DISTANCE = 12


def settle_settings_rect(
    rect: tuple[int, int, int, int],
    work_area: tuple[int, int, int, int],
    minimum: tuple[int, int],
    *,
    snap_distance: int = DEFAULT_SNAP_DISTANCE,
) -> tuple[int, int, int, int]:
    """Keep a Settings rect in one work area, with gentle edge snapping.

    A window larger than the screen's work area is reduced *only* to its
    declared minimum.  If that minimum exceeds the work area, complete
    containment is impossible: anchor at the top-left, leaving the title bar
    usable and respecting the application's minimum-layout contract.
    """
    x, y, width, height = map(int, rect)
    left, top, area_width, area_height = map(int, work_area)
    minimum_width, minimum_height = map(int, minimum)
    if area_width <= 0 or area_height <= 0:
        return x, y, width, height

    width = max(minimum_width, min(max(width, minimum_width), area_width))
    height = max(minimum_height, min(max(height, minimum_height), area_height))
    end_x = left + max(0, area_width - width)
    end_y = top + max(0, area_height - height)
    snap = max(0, int(snap_distance))

    def settle_axis(position: int, start: int, end: int) -> int:
        # An oversized minimum leaves no legal position range.
        if start == end:
            return start
        if abs(position - start) <= snap:
            return start
        if abs(position - end) <= snap:
            return end
        return max(start, min(position, end))

    return (
        settle_axis(x, left, end_x),
        settle_axis(y, top, end_y),
        width,
        height,
    )
