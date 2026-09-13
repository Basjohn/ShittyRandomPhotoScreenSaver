from __future__ import annotations

import pytest

from core.settings.defaults import get_default_settings
from ui.widget_stack_predictor import (
    WidgetType,
    build_widget_estimates,
    estimate_friend_pulse_size,
)


@pytest.mark.parametrize("view_mode", ("rows", "grid"))
@pytest.mark.parametrize("capacity", range(1, 25))
def test_friend_pulse_predictor_matches_retained_capacity_geometry(
    view_mode: str,
    capacity: int,
) -> None:
    width, height = estimate_friend_pulse_size(
        width=420,
        view_mode=view_mode,
        capacity=capacity,
    )

    if view_mode == "rows":
        expected_height = 102 + capacity * 58
    else:
        content_width = width - 36
        columns = min(capacity, 6, max(1, int((content_width + 10) // 120)))
        rows = (capacity + columns - 1) // columns
        expected_height = 120 + rows * 132 + max(0, rows - 1) * 10

    assert (width, height) == (420, expected_height)


@pytest.mark.parametrize("view_mode", ("rows", "grid"))
@pytest.mark.parametrize("capacity", range(1, 25))
def test_friend_pulse_stack_estimate_uses_view_and_capacity(
    view_mode: str,
    capacity: int,
) -> None:
    defaults = get_default_settings()["widgets"]
    estimates = build_widget_estimates(
        {
            "friend_pulse": {
                "enabled": True,
                "view_mode": view_mode,
                "visible_row_capacity": capacity,
            }
        },
        defaults=defaults,
    )

    estimate = next(item for item in estimates if item.widget_type is WidgetType.FRIEND_PULSE)
    expected = estimate_friend_pulse_size(
        width=int(defaults["friend_pulse"]["preferred_width"]),
        view_mode=view_mode,
        capacity=capacity,
    )
    assert (estimate.estimated_width, estimate.estimated_height) == expected
