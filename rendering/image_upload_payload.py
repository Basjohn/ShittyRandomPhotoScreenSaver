"""Immutable, tightly packed image bytes prepared for GL texture upload."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from PySide6.QtGui import QImage


@dataclass(frozen=True, slots=True)
class ImageUploadPayload:
    """A stable RGBA8 image snapshot that is safe to pass between stages."""

    width: int
    height: int
    stride: int
    data: bytes
    pixel_format: str = "rgba8"
    identity_seed: str = field(default="", repr=False, compare=False)
    content_id: str = field(init=False)
    byte_size: int = field(init=False)

    def __post_init__(self) -> None:
        width = int(self.width)
        height = int(self.height)
        stride = int(self.stride)
        if width <= 0 or height <= 0:
            raise ValueError("Image upload dimensions must be positive")
        if self.pixel_format != "rgba8":
            raise ValueError(f"Unsupported image upload pixel format: {self.pixel_format!r}")
        minimum_stride = width * 4
        if stride < minimum_stride:
            raise ValueError(
                f"Image upload stride {stride} is smaller than RGBA8 row size {minimum_stride}"
            )
        immutable_data = bytes(self.data)
        expected_size = stride * height
        if len(immutable_data) != expected_size:
            raise ValueError(
                f"Image upload data length {len(immutable_data)} does not match "
                f"stride*height {expected_size}"
            )

        digest = hashlib.sha256()
        digest.update(b"SRPSS.ImageUploadPayload\0")
        digest.update(width.to_bytes(8, "big", signed=False))
        digest.update(height.to_bytes(8, "big", signed=False))
        digest.update(stride.to_bytes(8, "big", signed=False))
        digest.update(self.pixel_format.encode("ascii"))
        digest.update(b"\0")
        digest.update(immutable_data)

        object.__setattr__(self, "width", width)
        object.__setattr__(self, "height", height)
        object.__setattr__(self, "stride", stride)
        object.__setattr__(self, "data", immutable_data)
        object.__setattr__(self, "byte_size", len(immutable_data))
        object.__setattr__(self, "content_id", digest.hexdigest())

    @classmethod
    def from_rgba8(
        cls,
        width: int,
        height: int,
        data: bytes | bytearray | memoryview,
        *,
        stride: int | None = None,
        identity_seed: str = "",
    ) -> "ImageUploadPayload":
        """Build an immutable payload from caller-owned RGBA8 bytes."""

        resolved_stride = int(stride) if stride is not None else int(width) * 4
        return cls(
            width=width,
            height=height,
            stride=resolved_stride,
            data=bytes(data),
            identity_seed=identity_seed,
        )


def prepare_qimage_upload_payload(
    image: QImage,
    identity_seed: str = "",
) -> ImageUploadPayload:
    """Normalize a QImage to tightly packed, immutable RGBA8 upload bytes."""

    if image is None or image.isNull():
        raise ValueError("Cannot prepare an upload payload from a null QImage")
    normalized = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width = int(normalized.width())
    height = int(normalized.height())
    source_stride = int(normalized.bytesPerLine())
    tight_stride = width * 4
    source_size = source_stride * height
    pointer = normalized.constBits()
    if hasattr(pointer, "setsize"):
        pointer.setsize(source_size)
    source = bytes(pointer)
    if len(source) < source_size:
        raise ValueError("QImage buffer is shorter than its declared row layout")
    if source_stride == tight_stride:
        packed = source[:source_size]
    else:
        packed = b"".join(
            source[offset : offset + tight_stride]
            for offset in range(0, source_size, source_stride)
        )
    return ImageUploadPayload.from_rgba8(
        width,
        height,
        packed,
        stride=tight_stride,
        identity_seed=identity_seed,
    )
