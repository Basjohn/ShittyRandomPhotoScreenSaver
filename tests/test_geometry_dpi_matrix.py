"""Deterministic geometry/DPI/DPR matrix tests.

These tests do not require real multi-monitor hardware. They exercise the
DisplayWidget screen-change path with fake QScreen objects to validate that:

- Geometry (x/y/width/height) is applied consistently for common monitor layouts
  including negative coordinates.
- The device pixel ratio (DPR) is captured and used for physical size math.

The goal is to catch regressions in the code paths that users hit with mixed-DPI
and unusual monitor arrangements.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QRect, QSize

from rendering.display_widget import DisplayWidget


class _FakeScreen:
    def __init__(self, rect: QRect, dpr: float) -> None:
        self._rect = QRect(rect)
        self._dpr = float(dpr)

    def geometry(self) -> QRect:
        return QRect(self._rect)

    def devicePixelRatio(self) -> float:
        return float(self._dpr)


@pytest.mark.parametrize(
    "rect,dpr",
    [
        pytest.param(QRect(0, 0, 1920, 1080), 1.0, id="1080p_dpr1_primary"),
        pytest.param(QRect(-2560, 0, 2560, 1440), 1.0, id="left_negative_origin"),
        pytest.param(QRect(0, 0, 3840, 2160), 1.25, id="4k_125pct"),
        pytest.param(QRect(3840, 0, 3840, 2160), 1.5, id="right_4k_150pct"),
        pytest.param(QRect(0, -1920, 1080, 1920), 2.0, id="portrait_above_200pct"),
        pytest.param(QRect(0, 0, 1366, 768), 1.75, id="laptop_175pct"),
    ],
)
def test_handle_screen_change_applies_geometry_and_dpr(qt_app, settings_manager, rect: QRect, dpr: float):
    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    widget.resize(100, 100)

    try:
        fake = _FakeScreen(rect, dpr)
        widget._handle_screen_change(fake)

        # Geometry should match, including negative origins.
        assert widget.x() == rect.x()
        assert widget.y() == rect.y()
        assert widget.width() == rect.width()

        # Height may be reduced by the fullscreen compat workaround (-1).
        expected_h = rect.height()
        assert widget.height() in {expected_h, max(1, expected_h - 1)}

        assert pytest.approx(widget._device_pixel_ratio, rel=1e-3) == float(dpr)

        # Physical size should scale by DPR.
        logical = widget.size()
        physical = widget.logical_to_physical_size()
        assert isinstance(physical, QSize)
        assert physical.width() == int(logical.width() * float(dpr))
        assert physical.height() == int(logical.height() * float(dpr))

    finally:
        widget.close()
