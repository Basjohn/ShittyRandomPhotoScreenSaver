"""The composite's Python face (D5.2; Current_Plan.md item 8b, N2.4).

What the core draws reaches the window as a scene-graph texture node carrying the card's coverage
(``native/core/src/composite.h``). Python owns its geometry, from the one record every consumer derives from
(``widgets/spotify_visualizer/presentation_geometry.py``); the C++ item only applies it:

- where the target lies: the card's drawn rect (``resolve_card_drawn_rect``, on whole device pixels, 1C.4); a frameless
  shell, drawn where it is, gets the smallest rect on whole device pixels around it, so the core always renders at a
  device-pixel rectangle and the composite maps texels one to one;
- the coverage: the card's clip path (``resolve_card_clip_path``: nothing outside the card, nothing under the border's
  anti-aliased edge), relative to that rect, in every display style (1D.2: the record carries the style's frame);
- the one admitted exception, a renderer's declared overflow (Sphere's, Extruded Spectrum's): the coverage is skipped
  and the target covers the rect the overflow may reach, unless the record holds the overflow
  (``renderer_overflow_held``: a non-Default display-wide card is the whole display), when the card's coverage stays;
- the content's quarter turns.

Nothing in the product places a composite yet: its first user is a native mode's surface (N2.5, Spectrum), in a window
the backend owner hosted (``rendering.quick.bootstrap``, N2.7).
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from types import ModuleType
from typing import Any, Sequence

#: The composite's options (``CompositeConfig`` in ``composite.h``).
COMPOSITE_OPTIONS = ("rect", "coverage", "quarters", "pattern", "visible", "opacity", "surface_format")
#: The surface's texel formats (``surface_format``): rgba8 (the product's), or rgba16f (translucent content not rounded
#: to 8 bits before the composite blends it). A harness switch: N2.5 round 5 measured no parity gain from rgba16f.
SURFACE_FORMATS = ("rgba8", "rgba16f")
#: The harness's surface content (``SurfacePattern`` in ``surfaces.h``): each texel's own index, or opaque white.
SURFACE_PATTERNS = ("texel_id", "white")
_GRID_TOLERANCE = 1e-6   # device pixels: a coordinate this close to a whole pixel is on it

Rect = tuple[float, float, float, float]


def _on_device_grid(rect: Sequence[float], dpr: float, *, quad_aligned: bool = False) -> Rect:
    """The smallest rect on whole device pixels containing ``rect`` (display-logical); ``quad_aligned``: every edge
    on an even device pixel, so the target's 2x2 derivative quads are the window's own whichever way it rasters."""
    x, y, width, height = (float(v) for v in rect)
    left = math.floor(x * dpr + _GRID_TOLERANCE)
    top = math.floor(y * dpr + _GRID_TOLERANCE)
    right = math.ceil((x + width) * dpr - _GRID_TOLERANCE)
    bottom = math.ceil((y + height) * dpr - _GRID_TOLERANCE)
    if quad_aligned:
        left, top, right, bottom = left - left % 2, top - top % 2, right + right % 2, bottom + bottom % 2
    return (left / dpr, top / dpr, max(1, right - left) / dpr, max(1, bottom - top) / dpr)


@dataclass(frozen=True)
class CompositeGeometry:
    """One record's composite: ``rect`` (display-logical, on whole device pixels) is where the target lies and
    ``pixel_size`` its device pixels as the window shows them (before the quarter turn); ``coverage`` is the card's
    clip path relative to ``rect`` (logical rect, corner radius), or None when an admitted overflow skips it."""

    rect: Rect
    pixel_size: tuple[int, int]
    coverage: tuple[Rect, float] | None
    quarters: int
    dpr: float
    overflow_admitted: bool = False

    @property
    def texture_size(self) -> tuple[int, int]:
        """The surface's own size: the content's orientation (the item's, turned by an odd quarter turn)."""
        width, height = self.pixel_size
        return (height, width) if self.quarters % 2 else (width, height)

    def item_config(self, parent_origin: Sequence[float] = (0.0, 0.0)) -> dict:
        """``CompositeItem.set``'s options for an item whose parent's top-left is ``parent_origin`` (display-logical)."""
        x, y, width, height = self.rect
        coverage = None
        if self.coverage is not None:
            (cx, cy, cw, ch), radius = self.coverage
            coverage = {"rect": [cx, cy, cw, ch], "radius": radius}
        return {"rect": [x - float(parent_origin[0]), y - float(parent_origin[1]), width, height],
                "coverage": coverage, "quarters": self.quarters}


def composite_geometry(presentation: Any, *, overflow_requested: bool = False,
                       overflow_rect: Sequence[float] | None = None, quad_aligned: bool = False) -> CompositeGeometry:
    """The composite of one ``ResolvedVisualizerPresentation``. ``overflow_requested``: the mode's own overflow
    choice (its ``renderer_overflow_setting`` on); ``overflow_rect`` (display-logical) is what such a renderer may
    reach when the record does not hold it."""
    from widgets.spotify_visualizer.presentation_geometry import (
        renderer_overflow_held,
        resolve_card_clip_path,
        resolve_card_drawn_rect,
    )

    dpr = float(presentation.dpr)
    quarters = int(presentation.content_rotation_quarters) % 4
    if overflow_requested and not renderer_overflow_held(presentation):
        if overflow_rect is None:
            raise ValueError("an admitted overflow names the rect it may reach (overflow_rect)")
        rect = _on_device_grid(overflow_rect, dpr, quad_aligned=quad_aligned)
        return CompositeGeometry(rect, _pixels(rect, dpr), None, quarters, dpr, overflow_admitted=True)
    rect = _on_device_grid(resolve_card_drawn_rect(presentation), dpr, quad_aligned=quad_aligned)
    (cx, cy, cw, ch), radius = resolve_card_clip_path(presentation)
    coverage = ((cx - rect[0], cy - rect[1], float(cw), float(ch)), float(radius))
    return CompositeGeometry(rect, _pixels(rect, dpr), coverage, quarters, dpr)


def _pixels(rect: Rect, dpr: float) -> tuple[int, int]:
    return (int(round(rect[2] * dpr)), int(round(rect[3] * dpr)))


class CompositeItem:
    """A composite item in a Qt Quick item of the caller's (``NativeCore.composite``); destroyed explicitly or with
    its parent. Its surface is drawn by the frame driver of a host attached to its window."""

    def __init__(self, module: ModuleType, handle: int) -> None:
        self._module = module
        self._handle = int(handle)
        self._destroyed = False

    @property
    def handle(self) -> int:
        return self._handle

    def _live(self) -> int:
        if self._destroyed:
            raise RuntimeError(f"the composite {self._handle} is destroyed")
        return self._handle

    def set(self, **config: Any) -> None:
        """Updates the item (``COMPOSITE_OPTIONS``; missing ones keep their values): ``rect`` [x, y, w, h] in its
        parent, ``coverage`` {rect, radius} item-local or None (skipped), ``quarters``, ``pattern``
        (``SURFACE_PATTERNS``), ``visible``, ``opacity``."""
        unknown = sorted(set(config) - set(COMPOSITE_OPTIONS))
        if unknown:
            raise ValueError(f"unknown composite option(s) {', '.join(unknown)} "
                             f"(the options are {', '.join(COMPOSITE_OPTIONS)})")
        surface_format = config.get("surface_format")
        if surface_format is not None and surface_format not in SURFACE_FORMATS:
            raise ValueError(f"unknown surface_format {surface_format!r} (the formats are {', '.join(SURFACE_FORMATS)})")
        pattern = config.get("pattern")
        if pattern is not None and pattern not in SURFACE_PATTERNS:
            raise ValueError(f"unknown pattern {pattern!r} (the patterns are {', '.join(SURFACE_PATTERNS)})")
        self._module.composite_set(self._live(), json.dumps(config))

    def place(self, geometry: CompositeGeometry, parent_origin: Sequence[float] = (0.0, 0.0), **config: Any) -> None:
        """The record's composite (``composite_geometry``), plus any other options."""
        self.set(**geometry.item_config(parent_origin), **config)

    def state(self) -> dict:
        """The item's configuration, its node's last sync (device pixel ratio, sizes, coverage in device pixels),
        its draws, and its surface (passes recorded, live QRhi objects)."""
        return json.loads(self._module.composite_state(self._live()))

    def destroy(self) -> bool:
        """Deletes the item (Qt Quick releases its node on the render thread at the next sync). Idempotent; False
        when its parent deleted it first."""
        if self._destroyed:
            return False
        self._destroyed = True
        return bool(self._module.composite_destroy(self._handle))


__all__ = ["COMPOSITE_OPTIONS", "CompositeGeometry", "CompositeItem", "SURFACE_FORMATS", "SURFACE_PATTERNS",
           "composite_geometry"]
