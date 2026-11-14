"""Where a display's photo lies over its background item: the presenter's fit and crop, one owner for both paths.

The fit and crop to the display (FILL, FIT, SHRINK) happens before any presenter, in the image worker, at the display's
device pixels (``rendering/image_processor_async.py``, ``rendering/image_quality.process_image``): both presenters draw
the same ``PresentationImage``. What is left to the presenter is this rule, read by both of them:

- the Python presenter's retained ``QSGImageNode`` (``render/background_image_node.py``: its source rect and its rect);
- the native core's background layer (``render/native_background.py``, N5.7a, D7 point 1: its pass's ``u_source_uv``
  over the background item's own rect).

The rule: the processed image's whole pixel rect over the item's whole logical rect. An image whose size is not the
item's device size (a stale image after a resolution change, until the next one is processed) is stretched by that
same rule on both paths. Never a second copy of it.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

Rect = tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class BackgroundPlacement:
    """``source_rect``: the photo's pixels drawn (x, y, width, height, in image pixels, rows top first);
    ``target_rect``: where they lie in the background item (logical, item-local)."""

    pixel_size: tuple[int, int]
    source_rect: Rect
    target_rect: Rect

    @property
    def source_uv(self) -> tuple[float, float, float, float]:
        """``source_rect`` in the photo's uv (0 to 1, v down from its top row): offset, then extent."""
        width, height = self.pixel_size
        x, y, w, h = self.source_rect
        return (x / width, y / height, w / width, h / height)


def background_placement(pixel_size: tuple[int, int], logical_size: tuple[float, float]) -> BackgroundPlacement:
    """The placement of a photo of ``pixel_size`` (image pixels) over a background item of ``logical_size``."""
    width, height = int(pixel_size[0]), int(pixel_size[1])
    if width <= 0 or height <= 0:
        raise ValueError(f"a photo has a positive pixel size, not {pixel_size!r}")
    item_width, item_height = float(logical_size[0]), float(logical_size[1])
    if not (math.isfinite(item_width) and math.isfinite(item_height)):
        raise ValueError(f"the background item's size is finite, not {logical_size!r}")
    return BackgroundPlacement(
        pixel_size=(width, height),
        source_rect=(0.0, 0.0, float(width), float(height)),
        target_rect=(0.0, 0.0, max(0.0, item_width), max(0.0, item_height)),
    )


__all__ = ["BackgroundPlacement", "background_placement"]
