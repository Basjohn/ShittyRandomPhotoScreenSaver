"""Bounded per-display image-processing descriptor (H).

The image pipeline needs only a small, presentation-neutral view of each display
to process an image for it: the target pixel size, the display (fill/fit) mode,
and the device pixel ratio. Historically it read these off live ``DisplayWidget``
objects; the Quick production owner exposes them as an immutable descriptor so
the pipeline never touches concrete presenter objects or their internals.

``DisplayManager`` builds one descriptor per selected display and hands the list
to the pipeline; the pipeline keys reuse/transform decisions on the descriptor
and returns processed images by ``screen_index`` for the owner to present.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize

from rendering.display_modes import DisplayMode


@dataclass(frozen=True, slots=True)
class DisplayProcessingDescriptor:
    """Immutable per-display processing inputs for the image pipeline."""

    screen_index: int
    target_size: QSize
    logical_size: QSize
    display_mode: DisplayMode
    device_pixel_ratio: float

    def __post_init__(self) -> None:
        if self.target_size.width() <= 0 or self.target_size.height() <= 0:
            raise ValueError("display processing target pixel size must be positive")
        if self.logical_size.width() <= 0 or self.logical_size.height() <= 0:
            raise ValueError("display processing target logical size must be positive")
        if self.device_pixel_ratio <= 0.0:
            raise ValueError("display processing target DPR must be positive")

    def get_target_size(self) -> QSize:
        """Compatibility with the presentation-neutral processing input protocol."""

        return QSize(self.target_size)

    def reuse_key(self) -> tuple[object, ...]:
        """Return the exact transform-reuse key for same-transform batching.

        Two displays with the same target size, display mode and DPR share one
        processed transform result, exactly as the legacy per-display key did.
        """

        return (
            int(self.target_size.width()),
            int(self.target_size.height()),
            self.display_mode.value,
            float(self.device_pixel_ratio),
        )


__all__ = ["DisplayProcessingDescriptor"]
