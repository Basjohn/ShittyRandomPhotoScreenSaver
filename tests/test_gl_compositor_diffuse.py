"""Tests for GLCompositorWidget diffuse transitions.

These tests validate that the compositor-based diffuse path does not produce
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
from transitions.gl_compositor_diffuse_transition import GLCompositorDiffuseTransition
from tests._gl_test_utils import solid_pixmap, fraction_dark_pixels, fraction_matching_color


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.mark.qt_no_exception_capture
def test_gl_compositor_diffuse_no_underlay_and_no_black(qapp):
    """Compositor-driven diffuse should not leak underlay or show black frames.

    Mirrors the compositor crossfade/slide/wipe/blinds/blockflip tests but
    drives a diffuse reveal between solid-colour images via
    GLCompositorDiffuseTransition.
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
    # GLCompositorDiffuseTransition expects on its widget.
    comp = GLCompositorWidget(parent)
    comp.setGeometry(parent.rect())
    comp.show()
    setattr(parent, "_gl_compositor", comp)

    # Prime compositor base image
    old_pm = solid_pixmap(96, 96, Qt.GlobalColor.red)
    new_pm = solid_pixmap(96, 96, Qt.GlobalColor.blue)
    comp.set_base_pixmap(old_pm)

    trans = GLCompositorDiffuseTransition(
        duration_ms=400,
        block_size=16,
        shape="Rectangle",
        easing="Auto",
    )

    # Start transition; if GL context is not available, skip.
    try:
        started = trans.start(old_pm, new_pm, parent)
    except Exception:
        started = False
    if not started:
        pytest.skip("GL compositor diffuse could not be started in this environment")

    try:
        comp.makeCurrent()
    except Exception:
        pytest.skip("GL context not available for GLCompositorWidget (diffuse)")

    # Capture a series of frames from the parent while the compositor runs.
    frames: list[QImage] = []
    for _ in range(28):
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
        ), f"GL compositor diffuse underlay leak detected ({underlay_fraction:.2%})"

        # No mostly-black frames while transitioning between non-black colours.
        assert (
            dark_fraction < 0.7
        ), f"GL compositor diffuse produced blank/very dark frame ({dark_fraction:.2%})"
