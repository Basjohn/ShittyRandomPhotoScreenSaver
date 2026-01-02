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

from typing import List

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPixmap, QImage, QColor, QPalette
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest


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
        # Each pixel is 4 bytes (BGRA or ARGB depending on platform), but we can
        # just use pixel() for clarity at this scale; the images are tiny.
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.red() < threshold and c.green() < threshold and c.blue() < threshold:
                dark += 1

    if total == 0:
        return 1.0
    return dark / float(total)


def _fraction_matching_color(img: QImage, color: QColor, tolerance: int = 16) -> float:
    """Return fraction of pixels approximately matching the given colour."""
    if img.isNull():
        return 0.0

    if img.format() not in (QImage.Format.Format_ARGB32, QImage.Format.Format_RGB32):
        img = img.convertToFormat(QImage.Format.Format_ARGB32)

    target_r = color.red()
    target_g = color.green()
    target_b = color.blue()

    match = 0
    total = img.width() * img.height()
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if (
                abs(c.red() - target_r) <= tolerance
                and abs(c.green() - target_g) <= tolerance
                and abs(c.blue() - target_b) <= tolerance
            ):
                match += 1

    if total == 0:
        return 0.0
    return match / float(total)


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
@pytest.mark.parametrize(
    "transition_cls, overlay_attr",
    [
        pytest.param(
            "transitions.gl_crossfade_transition.GLCrossfadeTransition",
            "_srpss_gl_xfade_overlay",
            id="GLCrossfade",
        ),
        pytest.param(
            "transitions.gl_slide_transition.GLSlideTransition",
            "_srpss_gl_slide_overlay",
            id="GLSlide",
        ),
    ],
)
def test_display_widget_gl_transitions_cover_underlay(qapp, transition_cls, overlay_attr):
    """DisplayWidget should not expose underlay or blank frames during GL transition."""
    from rendering.display_widget import DisplayWidget
    from rendering.display_modes import DisplayMode

    parent = QWidget()
    parent.resize(96, 96)
    palette = parent.palette()
    magenta = QColor(Qt.GlobalColor.magenta)
    palette.setColor(QPalette.ColorRole.Window, magenta)
    parent.setAutoFillBackground(True)
    parent.setPalette(palette)
    parent.show()

    widget = DisplayWidget(0, DisplayMode.FILL, None, parent)
    widget.setGeometry(0, 0, 96, 96)
    widget.show()
    QTest.qWait(50)

    old_pm = _solid_pixmap(96, 96, Qt.GlobalColor.red)
    new_pm = _solid_pixmap(96, 96, Qt.GlobalColor.blue)
    widget.previous_pixmap = old_pm
    widget.current_pixmap = new_pm

    module_name, cls_name = transition_cls.rsplit(".", 1)
    mod = __import__(module_name, fromlist=[cls_name])
    cls = getattr(mod, cls_name)
    transition = cls(duration_ms=400)

    try:
        transition.set_resource_manager(getattr(widget, "_resource_manager", None))
    except Exception:
        pass

    try:
        started = transition.start(old_pm, new_pm, widget)
    except Exception:
        started = False
    if not started:
        pytest.skip(f"{cls_name} could not be started in this environment")

    overlay = None
    for _ in range(40):
        qapp.processEvents()
        overlay = getattr(widget, overlay_attr, None)
        if overlay is not None:
            break
        QTest.qWait(15)

    if overlay is None:
        pytest.skip(f"Overlay {overlay_attr} was not created for {cls_name}")

    try:
        overlay.makeCurrent()
    except Exception:
        pytest.skip(f"GL context not available for {cls_name}")

    frames: List[QImage] = []
    for _ in range(15):
        qapp.processEvents()
        frames.append(parent.grab().toImage())
        QTest.qWait(15)

    try:
        transition.stop()
    except Exception:
        pass
    try:
        transition.cleanup()
    except Exception:
        pass

    for img in frames:
        underlay_fraction = _fraction_matching_color(img, magenta, tolerance=16)
        dark_fraction = _fraction_dark_pixels(img, threshold=16)

        assert (
            underlay_fraction < 0.05
        ), f"Underlay leak detected ({underlay_fraction:.2%}) for {cls_name}"

        assert (
            dark_fraction < 0.7
        ), f"Blank/very dark frame detected ({dark_fraction:.2%}) for {cls_name}"


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
