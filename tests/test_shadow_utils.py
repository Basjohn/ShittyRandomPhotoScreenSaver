from __future__ import annotations

import pytest

from PySide6.QtCore import QEasingCurve
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from widgets.shadow_utils import ShadowFadeProfile


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
