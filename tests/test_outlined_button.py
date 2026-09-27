"""Seam-free painted borders for shared Settings action buttons (offscreen, never shown on screen)."""
from __future__ import annotations

import pytest
from PySide6.QtGui import QColor

from ui.settings_theme_runtime import get_active_settings_theme
from ui.widgets.outlined_button import BORDER_WIDTH, OutlinedButton


@pytest.mark.parametrize("role,token", [("secondary", "control.button.border")])
def test_border_is_painted_as_one_continuous_stroke(qt_app, role, token) -> None:
    button = OutlinedButton("Apply", role=role)
    button.resize(160, 36)
    try:
        assert "solid transparent" in button.styleSheet()  # the stylesheet no longer draws it
        image = button.grab().toImage()
        expected = QColor(*get_active_settings_theme().color(token).as_tuple())
        # The stroke's outer pixel row must carry border alpha along the whole
        # straight top edge: continuous, with no gap or doubled segment.
        alphas = [image.pixelColor(x, 0).alpha() for x in range(24, 136)]
        assert min(alphas) > 0
        assert max(alphas) - min(alphas) <= 12
        assert BORDER_WIDTH >= 2.0
        assert expected.alpha() > 0
    finally:
        button.deleteLater()


def test_unknown_role_is_rejected(qt_app) -> None:
    with pytest.raises(ValueError):
        OutlinedButton("x", role="nope")
