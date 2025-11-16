"""DisplayWidget + GL overlay integration tests: underlay/blank-frame coverage.

These tests exercise the full DisplayWidget + GL transition overlay stack and
look for two classes of visual defects that correspond to what the USER sees
in practice:

- "Underlay leaks": frames where the underlying parent surface shows through
  instead of the DisplayWidget/overlay content.
- "Blank frames": frames that are mostly black even though we are transitioning
  between non-black images.

We intentionally do NOT assert anything about the *shape* of a particular
transition; we only assert that the GL-backed transition, once started, keeps
covering the presentation surface and does not devolve into empty/black frames.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtGui import QPixmap, QImage, QPalette, QColor
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

pytest.skip(
    "Legacy per-transition GL overlay underlay/blank-frame tests removed; superseded by compositor-based tests.",
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
    """Return fraction of pixels whose RGB components are all below threshold."""
    if img.isNull():
        return 1.0

    if img.format() not in (QImage.Format.Format_ARGB32, QImage.Format.Format_RGB32):
        img = img.convertToFormat(QImage.Format.Format_ARGB32)

    dark = 0
    total = img.width() * img.height()
    for y in range(img.height()):
        for x in range(img.width()):
            c = img.pixelColor(x, y)
            if c.red() < threshold and c.green() < threshold and c.blue() < threshold:
                dark += 1

    if total == 0:
        return 1.0
    return dark / float(total)


def _fraction_matching_color(img: QImage, color: QColor, tolerance: int = 16) -> float:
    """Return fraction of pixels approximately matching the given colour.

    Used to detect whether the parent's background colour (the "underlay") is
    visible through the DisplayWidget/overlay stack.
    """
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
        pytest.param(
            "transitions.gl_wipe_transition.GLWipeTransition",
            "_srpss_gl_wipe_overlay",
            id="GLWipe",
        ),
        pytest.param(
            "transitions.gl_blinds.GLBlindsTransition",
            "_srpss_gl_blinds_overlay",
            id="GLBlinds",
        ),
    ],
)
def test_gl_transitions_do_not_expose_underlay_or_blank_frames(qapp, transition_cls, overlay_attr):
    """Full DisplayWidget + GL overlay integration: no underlay or blank frames.

    This test creates a parent widget with a loud magenta background to act as
    the "underlay". A DisplayWidget is placed on top as a child and driven with
    a GL-backed transition between two non-black solid pixmaps.

    We repeatedly grab the *parent* surface while the transition runs and
    assert that:

    - The parent's magenta background is never a significant portion of any
      captured frame (no underlay leaks).
    - The frame is never mostly dark, indicating a blank/black presentation.
    """
    from rendering.display_widget import DisplayWidget
    from rendering.display_modes import DisplayMode

    # 1. Parent with loud background (underlay)
    parent = QWidget()
    parent.resize(128, 128)
    palette = parent.palette()
    magenta = QColor(Qt.GlobalColor.magenta)
    palette.setColor(QPalette.ColorRole.Window, magenta)
    parent.setAutoFillBackground(True)
    parent.setPalette(palette)
    parent.show()

    # 2. DisplayWidget child covering the parent
    widget = DisplayWidget(0, DisplayMode.FILL, None, parent)
    widget.setGeometry(0, 0, 128, 128)
    widget.show()
    QTest.qWait(50)

    # Seed DisplayWidget pixmaps with non-black colours
    old_pm = _solid_pixmap(128, 128, Qt.GlobalColor.red)
    new_pm = _solid_pixmap(128, 128, Qt.GlobalColor.blue)
    widget.previous_pixmap = old_pm
    widget.current_pixmap = new_pm

    # 3. Resolve transition class lazily from string to avoid import cycles
    module_name, cls_name = transition_cls.rsplit(".", 1)
    mod = __import__(module_name, fromlist=[cls_name])
    cls = getattr(mod, cls_name)
    transition = cls(duration_ms=500)

    # Attach shared ResourceManager if available; failure is non-fatal here.
    try:
        transition.set_resource_manager(getattr(widget, "_resource_manager", None))
    except Exception:
        pass

    # Start transition; if it cannot run in this environment, skip the test.
    try:
        started = transition.start(old_pm, new_pm, widget)
    except Exception:
        started = False
    if not started:
        pytest.skip(f"{cls_name} could not be started in this environment")

    # Wait for overlay to appear and ensure its GL context can be made current.
    overlay = None
    for _ in range(50):
        qapp.processEvents()
        overlay = getattr(widget, overlay_attr, None)
        if overlay is not None:
            break
        QTest.qWait(20)

    if overlay is None:
        pytest.skip(f"Overlay {overlay_attr} was not created for {cls_name}")

    try:
        overlay.makeCurrent()
    except Exception:
        pytest.skip(f"GL context not available for {cls_name}")

    # 4. Capture a series of frames from the parent while the transition runs.
    frames: list[QImage] = []
    for _ in range(20):
        qapp.processEvents()
        frames.append(parent.grab().toImage())
        QTest.qWait(20)

    # Optional: attempt to stop/cleanup transition; failure here is not fatal.
    try:
        transition.stop()
    except Exception:
        pass
    try:
        transition.cleanup()
    except Exception:
        pass

    # 5. Analyse frames for underlay leaks and blank frames.
    for img in frames:
        underlay_fraction = _fraction_matching_color(img, magenta, tolerance=16)
        dark_fraction = _fraction_dark_pixels(img, threshold=16)

        # No significant underlay leaks: magenta should not dominate any frame.
        assert (
            underlay_fraction < 0.05
        ), f"Underlay leak detected ({underlay_fraction:.2%}) for {cls_name}"

        # No mostly-black frames while transitioning between non-black colours.
        assert (
            dark_fraction < 0.7
        ), f"Blank/very dark frame detected ({dark_fraction:.2%}) for {cls_name}"
