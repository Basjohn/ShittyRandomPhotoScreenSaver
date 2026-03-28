"""Shared artwork sizing helpers for the media widget."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap


def compute_artwork_frame_size(pixmap: QPixmap | None, max_size: int) -> QSize:
    """Fit artwork into a square bounding box without distorting aspect ratio."""
    if pixmap is None or pixmap.isNull() or max_size <= 0:
        return QSize()

    source_w = max(1, int(pixmap.width()))
    source_h = max(1, int(pixmap.height()))
    scale = min(float(max_size) / float(source_w), float(max_size) / float(source_h))

    frame_w = max(1, int(round(source_w * scale)))
    frame_h = max(1, int(round(source_h * scale)))
    return QSize(frame_w, frame_h)
