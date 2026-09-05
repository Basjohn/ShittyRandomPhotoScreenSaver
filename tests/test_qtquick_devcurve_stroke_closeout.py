"""Focused Qt Quick DevCurve viewport stroke closeout regression."""
from __future__ import annotations

import math

import pytest

from rendering.quick.visualizer.implementations.devcurve import (
    QuickDevCurveLayout,
    devcurve_outline_extra_total_px,
    devcurve_outline_half_width,
)


def _layout(*, x_scale: float, y_scale: float, width: float, height: float):
    return QuickDevCurveLayout(
        content_rect=(0.0, 0.0, width, height),
        visual_scale=1.0,
        normalized_x_scale=x_scale,
        normalized_y_scale=y_scale,
    )


def test_devcurve_quick_outline_adds_one_px_base_and_two_more_at_max_viewport():
    canonical = _layout(x_scale=1.0, y_scale=1.0, width=420.0, height=280.0)
    two_x = _layout(x_scale=0.5, y_scale=1.0, width=840.0, height=280.0)
    max_x = _layout(x_scale=1.0 / 3.0, y_scale=1.0, width=1260.0, height=280.0)

    assert devcurve_outline_extra_total_px(canonical) == pytest.approx(1.0)
    assert devcurve_outline_extra_total_px(two_x) == pytest.approx(2.0)
    assert devcurve_outline_extra_total_px(max_x) == pytest.approx(3.0)

    for layout in (canonical, two_x, max_x):
        resolved = devcurve_outline_half_width(0.006, layout)
        authored = 0.006 * layout.normalized_y_scale
        added_total_px = 2.0 * (resolved - authored) * layout.content_rect[3]
        assert added_total_px == pytest.approx(
            devcurve_outline_extra_total_px(layout), abs=1e-9
        )
        assert math.isfinite(resolved) and resolved > authored
