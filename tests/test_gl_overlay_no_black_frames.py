"""GL overlay visual regression tests.

These tests exercise the core OpenGL-backed overlay widgets used by transitions
(Crossfade, Slide, Wipe) and verify that their rendered frames are not
"mostly black" when given non-black input pixmaps.

The goal is to provide a repeatable, architecture-level guard against
full-frame black flashes originating from the GL overlay FBOs themselves.

Notes
-----
- Tests are skipped if a valid GL context cannot be created on the test
  environment (e.g. in headless CI without GPU support).
- We use small solid-colour pixmaps so we can make simple assertions about
  the framebuffer contents without depending on real photos.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt

pytest.skip(
    "Legacy GL overlay visual regression tests removed; superseded by compositor-based tests.",
    allow_module_level=True,
)


@pytest.fixture
def qapp():
    """Ensure a QApplication exists for these tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def _solid_pixmap(w: int, h: int, color: Qt.GlobalColor) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(color)
    return pm


def _fraction_dark_pixels(img: QImage, threshold: int = 16) -> float:
    """Return fraction of pixels whose RGB components are all below threshold.

    This is a simple heuristic to detect frames that are essentially black.
    """

    if img.isNull():
        return 1.0

    # Convert to a known 32-bit format to simplify access
    if img.format() not in (QImage.Format.Format_ARGB32, QImage.Format.Format_RGB32):
        img = img.convertToFormat(QImage.Format.Format_ARGB32)

    dark = 0
    total = img.width() * img.height()
    for y in range(img.height()):
        scan_line = img.scanLine(y)
        # Each pixel is 4 bytes (BGRA or ARGB depending on platform), but we can
        # just use pixel() for clarity at this scale; the images are tiny.
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.red() < threshold and c.green() < threshold and c.blue() < threshold:
                dark += 1

    if total == 0:
        return 1.0
    return dark / float(total)


@pytest.mark.qt_no_exception_capture
class TestGLFadeOverlayNoBlack:
    """Guard against black frames from the GL crossfade overlay itself."""

    def test_gl_fade_initial_and_mid_frames_not_black(self, qapp):
        from transitions.gl_crossfade_transition import _GLFadeWidget

        widget = QWidget()
        widget.setGeometry(0, 0, 64, 64)

        old_pm = _solid_pixmap(64, 64, Qt.GlobalColor.red)
        new_pm = _solid_pixmap(64, 64, Qt.GlobalColor.blue)

        try:
            overlay = _GLFadeWidget(widget, old_pm, new_pm)
            overlay.setGeometry(0, 0, 64, 64)
            overlay.show()
            QApplication.processEvents()

            # Force GL init and capture a frame at alpha=0.0 (should look like old_pm)
            try:
                overlay.makeCurrent()
            except Exception:
                pytest.skip("GL context not available for _GLFadeWidget")

            overlay.set_alpha(0.0)
            QApplication.processEvents()
            img0 = overlay.grabFramebuffer()
            frac_dark0 = _fraction_dark_pixels(img0)

            # At alpha=0.0 with a solid red old pixmap, the frame should not be
            # mostly black (allow small margins for driver/compositor artefacts).
            assert frac_dark0 < 0.3, f"Initial GL fade frame too dark: {frac_dark0:.2%} dark"

            # Now capture a mid-transition frame at alpha=0.5; this should still not
            # be mostly black even though it is a blend of old/new.
            overlay.set_alpha(0.5)
            QApplication.processEvents()
            img_mid = overlay.grabFramebuffer()
            frac_dark_mid = _fraction_dark_pixels(img_mid)
            assert frac_dark_mid < 0.3, f"Mid GL fade frame too dark: {frac_dark_mid:.2%} dark"
        finally:
            widget.close()


@pytest.mark.qt_no_exception_capture
class TestGLSlideOverlayNoBlack:
    """Guard against black frames from the GL slide overlay itself."""

    def test_gl_slide_initial_and_mid_frames_not_black(self, qapp):
        from transitions.gl_slide_transition import _GLSlideWidget
        from transitions.slide_transition import SlideDirection

        widget = QWidget()
        widget.setGeometry(0, 0, 64, 64)

        old_pm = _solid_pixmap(64, 64, Qt.GlobalColor.red)
        new_pm = _solid_pixmap(64, 64, Qt.GlobalColor.green)

        try:
            overlay = _GLSlideWidget(widget, old_pm, new_pm, SlideDirection.LEFT)
            overlay.setGeometry(0, 0, 64, 64)
            overlay.show()
            QApplication.processEvents()

            try:
                overlay.makeCurrent()
            except Exception:
                pytest.skip("GL context not available for _GLSlideWidget")

            # Initial frame at progress=0.0 should show full old image and not be black.
            overlay.set_progress(0.0)
            QApplication.processEvents()
            img0 = overlay.grabFramebuffer()
            frac_dark0 = _fraction_dark_pixels(img0)
            assert frac_dark0 < 0.3, f"Initial GL slide frame too dark: {frac_dark0:.2%} dark"

            # Mid-transition frame at progress=0.5 should still not be mostly black.
            overlay.set_progress(0.5)
            QApplication.processEvents()
            img_mid = overlay.grabFramebuffer()
            frac_dark_mid = _fraction_dark_pixels(img_mid)
            assert frac_dark_mid < 0.3, f"Mid GL slide frame too dark: {frac_dark_mid:.2%} dark"
        finally:
            widget.close()


@pytest.mark.qt_no_exception_capture
class TestGLWipeOverlayNoBlack:
    """Guard against black frames from the GL wipe overlay itself."""

    def test_gl_wipe_initial_and_mid_frames_not_black(self, qapp):
        from transitions.gl_wipe_transition import _GLWipeWidget
        from transitions.wipe_transition import WipeDirection

        widget = QWidget()
        widget.setGeometry(0, 0, 64, 64)

        old_pm = _solid_pixmap(64, 64, Qt.GlobalColor.red)
        new_pm = _solid_pixmap(64, 64, Qt.GlobalColor.yellow)

        try:
            overlay = _GLWipeWidget(widget, old_pm, new_pm, WipeDirection.LEFT_TO_RIGHT)
            overlay.setGeometry(0, 0, 64, 64)
            overlay.show()
            QApplication.processEvents()

            try:
                overlay.makeCurrent()
            except Exception:
                pytest.skip("GL context not available for _GLWipeWidget")

            # Initial frame at progress=0.0 should show full old image and not be black.
            overlay.set_progress(0.0)
            QApplication.processEvents()
            img0 = overlay.grabFramebuffer()
            frac_dark0 = _fraction_dark_pixels(img0)
            assert frac_dark0 < 0.3, f"Initial GL wipe frame too dark: {frac_dark0:.2%} dark"

            # Mid-transition frame at progress=0.5 should still not be mostly black.
            overlay.set_progress(0.5)
            QApplication.processEvents()
            img_mid = overlay.grabFramebuffer()
            frac_dark_mid = _fraction_dark_pixels(img_mid)
            assert frac_dark_mid < 0.3, f"Mid GL wipe frame too dark: {frac_dark_mid:.2%} dark"
        finally:
            widget.close()
