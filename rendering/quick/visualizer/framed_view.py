"""The drawn card's framed view, resolved on the GUI side with the renderer's own functions (native core N0.4).

A framed 3D renderer reads two things from its frame besides the parameters: the card's device-pixel rect
(``item_pixel_rect`` of the oriented frame: its width over height is the camera's aspect) and the presentation's
``framed_aperture_scale``. ``resolve_framed_view`` makes the frame the render node would make for a presentation and
asks the same functions: the item is the presentation's outer size (``VisualizerRenderNode`` sizes it from the record)
placed at the drawn card's origin (``resolve_card_drawn_rect``: the scene places the card on whole device pixels,
R-191), mapped to clip space by a float32 matrix as Qt's ``projectionMatrix() * matrix()`` is, then turned by
``orient_visualizer_scene_frame`` for a content quarter-turn. The viewport is the smallest that holds the card (the
renderer's is its window, which holds the card: the presentation resolver keeps the card on its display).

Resolved once per geometry edge by the scene (``QuickSceneController``), never per frame.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Any

from core.framed_view import FramedView
from rendering.quick.scene3d.frame import item_pixel_rect, orient_visualizer_scene_frame
from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
from widgets.spotify_visualizer.presentation_geometry import framed_aperture_scale, resolve_card_drawn_rect


@dataclass(frozen=True, slots=True)
class _PresentationOnly:
    """What ``orient_visualizer_scene_frame`` reads of a frame's snapshot (and replaces): its presentation."""

    presentation: Any


def _float32(value: float) -> float:
    return struct.unpack("f", struct.pack("f", float(value)))[0]


def drawn_card_frame(presentation: Any, *, viewport: tuple[int, int, int, int] | None = None,
                     origin: tuple[float, float] | None = None) -> QuickVisualizerRenderFrame:
    """The render node's frame for ``presentation`` (unoriented): the item at the drawn card's origin (or ``origin``,
    scene-logical), its size the record's outer size, in ``viewport`` (device pixels; default the smallest holding
    the card)."""
    dpr = float(presentation.dpr)
    drawn_x, drawn_y, _drawn_width, _drawn_height = resolve_card_drawn_rect(presentation)
    x, y = (drawn_x, drawn_y) if origin is None else (float(origin[0]), float(origin[1]))
    width, height = float(presentation.outer_rect[2]), float(presentation.outer_rect[3])
    if viewport is None:
        viewport = (0, 0, max(1, math.ceil((x + width) * dpr)), max(1, math.ceil((y + height) * dpr)))
    window_width, window_height = viewport[2] / dpr, viewport[3] / dpr
    # Column-major: the window's logical rect to clip space (Y up), after the item's translation to (x, y).
    matrix = (2.0 / window_width, 0.0, 0.0, 0.0,
              0.0, -2.0 / window_height, 0.0, 0.0,
              0.0, 0.0, -1.0, 0.0,
              -1.0 + 2.0 * x / window_width, 1.0 - 2.0 * y / window_height, 0.0, 1.0)
    return QuickVisualizerRenderFrame(snapshot=_PresentationOnly(presentation), viewport=tuple(viewport),
                                      logical_size=(width, height),
                                      matrix_values=tuple(_float32(value) for value in matrix), quad_vao=1)


def framed_view_of_frame(frame: Any) -> FramedView | None:
    """A render frame's framed view, read as the framed renderers read it: ``item_pixel_rect`` and
    ``framed_aperture_scale`` of the oriented frame. None when the card covers no pixel."""
    frame = orient_visualizer_scene_frame(frame)
    _x, _y, width, height = item_pixel_rect(frame)
    if width <= 0 or height <= 0:
        return None
    presentation = frame.snapshot.presentation
    return FramedView(width / height, framed_aperture_scale(presentation, content=True),
                      framed_aperture_scale(presentation))


def resolve_framed_view(presentation: Any) -> FramedView | None:
    """The framed view the renderer reads from the card it draws for ``presentation`` (None when it covers no pixel)."""
    return framed_view_of_frame(drawn_card_frame(presentation))


def framed_view_geometry_key(presentation: Any) -> tuple:
    """Everything ``resolve_framed_view`` reads of a record: equal keys, equal views (a fade changes no key)."""
    style = presentation.shell_style
    return (presentation.outer_rect, presentation.content_rect, presentation.viewport_extent, presentation.dpr,
            presentation.content_rotation_quarters, presentation.shell_policy, presentation.uniform_visual_scale,
            presentation.baseline_viewport_size, style["content_inset"], style["authored_border_width"])


__all__ = ["drawn_card_frame", "framed_view_geometry_key", "framed_view_of_frame", "resolve_framed_view"]
