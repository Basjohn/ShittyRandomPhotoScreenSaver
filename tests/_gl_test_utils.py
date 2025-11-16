"""Shared helpers for GL-related tests (pixel analysis, solid pixmaps)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage, QColor


def solid_pixmap(w: int, h: int, color: Qt.GlobalColor) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(color)
    return pm


def fraction_dark_pixels(img: QImage, threshold: int = 16) -> float:
    """Return fraction of pixels whose RGB components are all below threshold.

    Used as a coarse "mostly black" detector for captured frames.
    """
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


def fraction_matching_color(img: QImage, color: QColor, tolerance: int = 16) -> float:
    """Return fraction of pixels approximately matching the given colour.

    Used to detect whether a known background ("underlay") colour is visible in
    the presented surface.
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
