"""Immutable image content crossing into the Qt Quick render thread."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


PixelSize = tuple[int, int]
LogicalSize = tuple[float, float]


@dataclass(frozen=True, slots=True)
class PresentationImage:
    """Detached, tightly packed RGBA image state for one processed image."""

    identity: str
    source_path: str
    logical_size: LogicalSize
    device_pixel_ratio: float
    pixel_size: PixelSize
    row_stride: int
    rgba8: bytes

    def __post_init__(self) -> None:
        identity = str(self.identity).strip()
        if not identity:
            raise ValueError("presentation image identity must not be empty")

        pixel_size = (int(self.pixel_size[0]), int(self.pixel_size[1]))
        if pixel_size[0] <= 0 or pixel_size[1] <= 0:
            raise ValueError(
                f"presentation image pixel size must be positive: {pixel_size}"
            )

        logical_size = (
            float(self.logical_size[0]),
            float(self.logical_size[1]),
        )
        if (
            not all(math.isfinite(value) and value > 0.0 for value in logical_size)
        ):
            raise ValueError(
                f"presentation image logical size must be positive: {logical_size}"
            )

        device_pixel_ratio = float(self.device_pixel_ratio)
        if not math.isfinite(device_pixel_ratio) or device_pixel_ratio <= 0.0:
            raise ValueError("presentation image DPR must be finite and positive")

        row_stride = int(self.row_stride)
        expected_stride = pixel_size[0] * 4
        if row_stride != expected_stride:
            raise ValueError(
                "presentation RGBA rows must be tightly packed: "
                f"stride={row_stride} expected={expected_stride}"
            )

        rgba8 = bytes(self.rgba8)
        expected_bytes = row_stride * pixel_size[1]
        if len(rgba8) != expected_bytes:
            raise ValueError(
                "presentation RGBA payload has the wrong size: "
                f"bytes={len(rgba8)} expected={expected_bytes}"
            )

        object.__setattr__(self, "identity", identity)
        object.__setattr__(self, "source_path", str(self.source_path or ""))
        object.__setattr__(self, "logical_size", logical_size)
        object.__setattr__(self, "device_pixel_ratio", device_pixel_ratio)
        object.__setattr__(self, "pixel_size", pixel_size)
        object.__setattr__(self, "row_stride", row_stride)
        object.__setattr__(self, "rgba8", rgba8)

    @property
    def byte_count(self) -> int:
        return len(self.rgba8)

    def describe(self) -> dict[str, Any]:
        """Return diagnostic metadata without copying the frame payload."""

        return {
            "identity": self.identity,
            "source_path": self.source_path,
            "logical_size": self.logical_size,
            "device_pixel_ratio": self.device_pixel_ratio,
            "pixel_size": self.pixel_size,
            "row_stride": self.row_stride,
            "byte_count": self.byte_count,
        }
