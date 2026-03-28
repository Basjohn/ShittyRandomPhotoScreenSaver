"""Shared artwork sizing helpers for the media widget."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap

_LANDSCAPE_COVER_THRESHOLD = 1.2


def compute_artwork_frame_size(pixmap: QPixmap | None, max_size: int) -> QSize:
    """Return the target artwork frame size inside the configured box.

    Square/near-square art keeps aspect-fit behavior. Wide video-frame style
    artwork uses the full square frame so the existing crop-to-fill paint path
    can eliminate visible letterboxing.
    """
    if pixmap is None or pixmap.isNull() or max_size <= 0:
        return QSize()

    source_w = max(1, int(pixmap.width()))
    source_h = max(1, int(pixmap.height()))
    if (float(source_w) / float(source_h)) >= _LANDSCAPE_COVER_THRESHOLD:
        return QSize(max_size, max_size)

    scale = min(float(max_size) / float(source_w), float(max_size) / float(source_h))

    frame_w = max(1, int(round(source_w * scale)))
    frame_h = max(1, int(round(source_h * scale)))
    return QSize(frame_w, frame_h)
