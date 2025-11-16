"""Tests for GLCompositorWidget slide transitions.

These tests validate that the compositor-based slide path does not produce
mostly-black frames or expose a coloured underlay when driven in a simple
QWidget hierarchy.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QImage, QPalette, QColor
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from rendering.gl_compositor import GLCompositorWidget
from transitions.gl_compositor_slide_transition import GLCompositorSlideTransition
from transitions.slide_transition import SlideDirection
from tests._gl_test_utils import solid_pixmap, fraction_dark_pixels, fraction_matching_color


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.mark.qt_no_exception_capture
def test_gl_compositor_slide_no_underlay_and_no_black(qapp):
    """Compositor-driven slide should not leak underlay or show black frames.

    Mirrors the compositor crossfade test but drives a LEFT slide between
    solid-colour images via GLCompositorSlideTransition.
    """

    # Parent with loud magenta background (acts as underlay)
    parent = QWidget()
    parent.resize(96, 96)
    pal = parent.palette()
    magenta = QColor(Qt.GlobalColor.magenta)
    pal.setColor(QPalette.ColorRole.Window, magenta)
    parent.setAutoFillBackground(True)
    parent.setPalette(pal)
    parent.show()

    # Compositor child covering parent; attach as the shared compositor that
    # GLCompositorSlideTransition expects on its widget.
    comp = GLCompositorWidget(parent)
    comp.setGeometry(parent.rect())
    comp.show()
    setattr(parent, "_gl_compositor", comp)

    # Prime compositor base image
    old_pm = solid_pixmap(96, 96, Qt.GlobalColor.red)
    new_pm = solid_pixmap(96, 96, Qt.GlobalColor.blue)
    comp.set_base_pixmap(old_pm)

    trans = GLCompositorSlideTransition(
        duration_ms=300,
        direction=SlideDirection.LEFT,
        easing="Auto",
    )

    # Start transition; if GL context is not available, skip.
    try:
        started = trans.start(old_pm, new_pm, parent)
    except Exception:
        started = False
    if not started:
        pytest.skip("GL compositor slide could not be started in this environment")

    try:
        comp.makeCurrent()
    except Exception:
        pytest.skip("GL context not available for GLCompositorWidget (slide)")

    # Capture a series of frames from the parent while the compositor slides.
    frames: list[QImage] = []
    for _ in range(24):
        qapp.processEvents()
        frames.append(parent.grab().toImage())
        QTest.qWait(20)

    # Analyse frames for underlay leaks (magenta) and blank/very dark frames.
    for img in frames:
        underlay_fraction = fraction_matching_color(img, magenta, tolerance=16)
        dark_fraction = fraction_dark_pixels(img, threshold=16)

        # Underlay should not dominate any frame.
        assert (
            underlay_fraction < 0.05
        ), f"GL compositor slide underlay leak detected ({underlay_fraction:.2%})"

        # No mostly-black frames while transitioning between non-black colours.
        assert (
            dark_fraction < 0.7
        ), f"GL compositor slide produced blank/very dark frame ({dark_fraction:.2%})"
