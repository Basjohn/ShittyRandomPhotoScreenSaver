"""Bounded process-engine image provider for retained Media artwork."""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QImage, QPainter, QPainterPath
from PySide6.QtQuick import QQuickImageProvider


class MediaArtworkImageProvider(QQuickImageProvider):
    """Serve immutable decoded artwork by stable runtime-owned identity."""

    provider_id = "mediaartwork"

    def __init__(self, *, unreferenced_capacity: int = 8) -> None:
        super().__init__(
            QQuickImageProvider.ImageType.Image,
            QQuickImageProvider.Flag.ForceAsynchronousImageLoading,
        )
        self._lock = RLock()
        self._images: OrderedDict[str, QImage] = OrderedDict()
        self._references: dict[str, int] = {}
        self._unreferenced_capacity = max(1, int(unreferenced_capacity))

    @staticmethod
    def identity_for_key(key: tuple[int, str]) -> str:
        size, digest = key
        normalized_digest = str(digest or "").strip().lower()
        if int(size) <= 0 or not normalized_digest:
            return ""
        return f"{int(size)}-{normalized_digest}"

    def publish(self, key: tuple[int, str], image: QImage) -> str:
        identity = self.identity_for_key(key)
        if not identity or not isinstance(image, QImage) or image.isNull():
            return ""
        with self._lock:
            if identity not in self._images:
                self._images[identity] = image.copy()
            self._images.move_to_end(identity)
            self._references[identity] = self._references.get(identity, 0) + 1
            self._evict_unreferenced()
        return f"image://{self.provider_id}/{identity}"

    def release(self, identity: str) -> None:
        normalized = str(identity or "").strip()
        if not normalized:
            return
        with self._lock:
            remaining = self._references.get(normalized, 0) - 1
            if remaining > 0:
                self._references[normalized] = remaining
            else:
                self._references.pop(normalized, None)
            self._evict_unreferenced()

    def requestImage(self, identity: str, size: QSize, requested_size: QSize) -> QImage:
        del requested_size
        normalized = str(identity or "").strip()
        stored_identity, _, variant = normalized.partition("/")
        with self._lock:
            stored = self._images.get(stored_identity)
            image = QImage(stored) if stored is not None else QImage()
            if stored is not None:
                self._images.move_to_end(stored_identity)
        if variant == "rounded" and not image.isNull():
            image = self._rounded_square(image)
        if not image.isNull():
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image

    def contains(self, identity: str) -> bool:
        with self._lock:
            return str(identity or "") in self._images

    @property
    def image_count(self) -> int:
        with self._lock:
            return len(self._images)

    def _evict_unreferenced(self) -> None:
        unreferenced = [
            identity
            for identity in self._images
            if self._references.get(identity, 0) <= 0
        ]
        while len(unreferenced) > self._unreferenced_capacity:
            identity = unreferenced.pop(0)
            self._images.pop(identity, None)

    @staticmethod
    def _rounded_square(source: QImage) -> QImage:
        side = min(source.width(), source.height())
        if side <= 0:
            return QImage()
        crop = source.copy(
            max(0, (source.width() - side) // 2),
            max(0, (source.height() - side) // 2),
            side,
            side,
        )
        rounded = QImage(side, side, QImage.Format.Format_ARGB32_Premultiplied)
        rounded.fill(Qt.GlobalColor.transparent)
        painter = QPainter(rounded)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            path = QPainterPath()
            radius = side / 8.0
            path.addRoundedRect(
                QRectF(0.0, 0.0, float(side), float(side)), radius, radius
            )
            painter.setClipPath(path)
            painter.drawImage(0, 0, crop)
        finally:
            painter.end()
        return rounded
