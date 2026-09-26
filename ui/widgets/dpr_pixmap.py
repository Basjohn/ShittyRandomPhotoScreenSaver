"""Aspect-preserving source-pixmap scaling at the destination's physical DPR."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


def scale_pixmap_for_dpr(source: QPixmap, width: float, height: float, dpr: float) -> QPixmap:
    dpr = max(1.0, float(dpr))
    result = source.scaled(
        max(1, round(width * dpr)), max(1, round(height * dpr)),
        Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )
    result.setDevicePixelRatio(dpr)
    return result
