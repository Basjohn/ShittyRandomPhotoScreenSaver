from __future__ import annotations

import pytest

from PySide6.QtCore import QEasingCurve, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from widgets.shadow_utils import ShadowFadeProfile, draw_rich_text_shadow_only, draw_text_rect_shadow_only


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


def test_shadow_tuning_payload_backfills_new_sections_without_clobbering_existing_values(tmp_path):
    from core.settings import shadow_tuning

    payload, needs_refresh = shadow_tuning._canonicalized_tuning_payload(
        {
            "card": {"offset_x": 9},
            "text": {"offset_x": 3},
            "header": {"alpha": 70},
        }
    )

    assert needs_refresh is True
    assert payload["card"]["offset_x"] == 9
    assert payload["text"]["offset_x"] == 3
    assert "text_large" in payload
    assert payload["text_large"]["offset_x"] == shadow_tuning._TEXT_LARGE_DEFAULTS["offset_x"]
    assert payload["header"]["alpha"] == 70
    assert "icon" in payload
    assert payload["icon"]["alpha"] == 67
    assert payload["icon"]["scale"] == shadow_tuning._ICON_DEFAULTS["scale"]
    assert "control" in payload
    assert payload["control"]["spread"] == shadow_tuning._CONTROL_DEFAULTS["spread"]


@pytest.mark.qt
def test_text_shadow_helpers_render_from_tuning_backed_paths(qt_app):
    pixmap = QPixmap(180, 80)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        painter.setFont(QFont("Segoe UI", 24))
        draw_text_rect_shadow_only(
            painter,
            QRect(10, 10, 160, 40),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "Weather",
            font_size=24,
        )
        draw_rich_text_shadow_only(
            painter,
            QRect(10, 35, 160, 40),
            "<div style='font-size:20pt; color:rgba(255,255,255,255);'>Media</div>",
            default_font=QFont("Segoe UI", 20),
            font_size=20,
            enabled=True,
        )
    finally:
        painter.end()

    image = pixmap.toImage()
    found_shadow_pixel = False
    for y in range(image.height()):
        for x in range(image.width()):
            color = QColor(image.pixelColor(x, y))
            if color.alpha() > 0:
                found_shadow_pixel = True
                break
        if found_shadow_pixel:
            break
    assert found_shadow_pixel is True
