"""Bounded process-engine image provider for retained Media artwork."""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


class MediaArtworkImageProvider(QQuickImageProvider):
    """Serve immutable decoded artwork by stable runtime-owned identity."""

    provider_id = "mediaartwork"

    # Spotify can expose video thumbnails whose encoded bitmap already contains
    # near-black letterbox bands.  QML PreserveAspectCrop cannot remove bars that
    # are part of the source pixels, so detect only strong/symmetric edge bands
    # once when a new artwork identity enters the provider.
    _LETTERBOX_SCAN_EXTENT = 192
    _LETTERBOX_MAX_CHANNEL = 42
    _LETTERBOX_MAX_MEAN_LUMA = 24.0
    _LETTERBOX_MIN_DARK_RATIO = 0.90
    _LETTERBOX_MIN_BAND_FRACTION = 0.025
    _LETTERBOX_MAX_BAND_FRACTION = 0.30
    _LETTERBOX_MAX_ASYMMETRY = 0.35
    _LETTERBOX_MIN_CONTENT_ASPECT = 1.12

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
            if identity in self._images:
                self._images.move_to_end(identity)
                self._references[identity] = self._references.get(identity, 0) + 1
                self._evict_unreferenced()
                return f"image://{self.provider_id}/{identity}"

        # Do the bounded source scan outside the provider lock so an artwork
        # change cannot hold up concurrent asynchronous image requests.  The
        # second check keeps the shared identity cache authoritative if two
        # presenters publish the same new identity concurrently.
        prepared = self._crop_embedded_letterbox(image)
        with self._lock:
            if identity not in self._images:
                self._images[identity] = prepared
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
        stored_identity = str(identity or "").strip().partition("/")[0]
        with self._lock:
            stored = self._images.get(stored_identity)
            image = QImage(stored) if stored is not None else QImage()
            if stored is not None:
                self._images.move_to_end(stored_identity)
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

    @classmethod
    def _crop_embedded_letterbox(cls, source: QImage) -> QImage:
        """Crop conservative symmetric near-black top/bottom source bands.

        This is deliberately not a generic dark-edge crop.  Both edge bands must
        be strongly near-black, materially sized, roughly symmetric, and reveal
        a landscape/video-like content rectangle after removal.  That keeps dark
        album artwork intact while repairing Spotify's baked-in video bars.
        """

        width = source.width()
        height = source.height()
        if width < 16 or height < 16:
            return source.copy()

        preview = source.scaled(
            QSize(cls._LETTERBOX_SCAN_EXTENT, cls._LETTERBOX_SCAN_EXTENT),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )
        preview_width = preview.width()
        preview_height = preview.height()
        if preview_width < 8 or preview_height < 8:
            return source.copy()

        max_band = max(
            1,
            int(round(preview_height * cls._LETTERBOX_MAX_BAND_FRACTION)),
        )
        top_band = cls._edge_dark_band(preview, from_top=True, limit=max_band)
        bottom_band = cls._edge_dark_band(preview, from_top=False, limit=max_band)
        # Hitting the scan cap means no reliable content boundary was found.
        # Treat that as genuinely dark artwork, never as evidence to crop.
        if top_band >= max_band or bottom_band >= max_band:
            return source.copy()

        min_band = max(
            2,
            int(round(preview_height * cls._LETTERBOX_MIN_BAND_FRACTION)),
        )
        if top_band < min_band or bottom_band < min_band:
            return source.copy()

        largest_band = max(top_band, bottom_band)
        allowed_difference = max(
            2,
            int(round(largest_band * cls._LETTERBOX_MAX_ASYMMETRY)),
        )
        if abs(top_band - bottom_band) > allowed_difference:
            return source.copy()

        remaining_preview_height = preview_height - top_band - bottom_band
        if remaining_preview_height <= 0:
            return source.copy()
        content_aspect = preview_width / float(remaining_preview_height)
        if content_aspect < cls._LETTERBOX_MIN_CONTENT_ASPECT:
            return source.copy()

        y_scale = height / float(preview_height)
        crop_top = max(0, min(height - 1, int(round(top_band * y_scale))))
        crop_bottom = max(
            0,
            min(height - crop_top - 1, int(round(bottom_band * y_scale))),
        )
        crop_height = height - crop_top - crop_bottom
        if crop_height <= 0:
            return source.copy()
        return source.copy(0, crop_top, width, crop_height)

    @classmethod
    def _edge_dark_band(cls, image: QImage, *, from_top: bool, limit: int) -> int:
        height = image.height()
        if height <= 0:
            return 0
        extent = min(height, max(0, int(limit)))
        count = 0
        for offset in range(extent):
            y = offset if from_top else height - 1 - offset
            if not cls._row_is_near_black(image, y):
                break
            count += 1
        return count

    @classmethod
    def _row_is_near_black(cls, image: QImage, y: int) -> bool:
        width = image.width()
        if width <= 0:
            return False

        # Cap Python-side sampling while still spanning the whole source row.
        sample_count = min(64, width)
        if sample_count <= 1:
            xs = (0,)
        else:
            xs = tuple(
                int(round(index * (width - 1) / float(sample_count - 1)))
                for index in range(sample_count)
            )

        dark = 0
        luma_total = 0.0
        for x in xs:
            pixel = int(image.pixel(x, y))
            red = (pixel >> 16) & 0xFF
            green = (pixel >> 8) & 0xFF
            blue = pixel & 0xFF
            luma = red * 0.2126 + green * 0.7152 + blue * 0.0722
            luma_total += luma
            if max(red, green, blue) <= cls._LETTERBOX_MAX_CHANNEL:
                dark += 1

        ratio = dark / float(len(xs))
        mean_luma = luma_total / float(len(xs))
        return (
            ratio >= cls._LETTERBOX_MIN_DARK_RATIO
            and mean_luma <= cls._LETTERBOX_MAX_MEAN_LUMA
        )
