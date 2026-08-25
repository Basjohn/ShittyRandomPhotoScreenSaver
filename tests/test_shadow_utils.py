from __future__ import annotations

import pytest

from PySide6.QtCore import QEasingCurve, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from widgets.shadow_utils import ShadowFadeProfile, draw_text_rect_with_shadow


@pytest.mark.qt
def test_shared_fade_shows_widget_immediately_at_zero_opacity(qt_app, qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    widget = QWidget(parent)
    qtbot.addWidget(widget)

    assert widget.isVisible() is False

    ShadowFadeProfile.start_fade_in(
        widget,
        {"enabled": False},
        has_background_frame=False,
    )

    effect = widget.graphicsEffect()
    assert widget.isVisible() is True
    assert isinstance(effect, QGraphicsOpacityEffect)
    assert effect.opacity() == pytest.approx(0.0)
    assert getattr(widget, "_shadowfade_progress", None) == pytest.approx(0.0)
    assert getattr(widget, "_shadowfade_completed", None) is False


def test_shared_fade_profile_stays_gentle_and_visible():
    assert ShadowFadeProfile.DURATION_MS >= 1800
    assert ShadowFadeProfile.default_duration_ms() == ShadowFadeProfile.DURATION_MS
    assert ShadowFadeProfile.EASING == QEasingCurve.InOutCubic


@pytest.mark.qt
def test_shared_fade_honors_explicit_duration_override(qt_app, qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    widget = QWidget(parent)
    qtbot.addWidget(widget)

    ShadowFadeProfile.start_fade_in(
        widget,
        {"enabled": False},
        duration_ms=321,
        has_background_frame=False,
    )

    anim = getattr(widget, "_shadowfade_anim", None)
    assert anim is not None
    assert anim.duration() == 321


@pytest.mark.qt
def test_retired_text_shadow_gate_does_not_change_visible_text_pixels(qt_app):
    def render(enabled: bool):
        pixmap = QPixmap(180, 80)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            painter.setFont(QFont("Segoe UI", 24))
            painter.setPen(QColor(255, 255, 255, 255))
            draw_text_rect_with_shadow(
                painter,
                QRect(10, 10, 160, 40),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                "Weather",
                font_size=24,
                enabled=enabled,
            )
        finally:
            painter.end()
        return pixmap.toImage()

    enabled_image = render(True)
    disabled_image = render(False)

    assert enabled_image == disabled_image
    assert any(
        enabled_image.pixelColor(x, y).alpha() > 0
        for y in range(enabled_image.height())
        for x in range(enabled_image.width())
    )
