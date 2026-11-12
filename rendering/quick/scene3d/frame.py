"""What a 3D scene needs from its render node's frame (pure; no GL).

Transition and Visualizer frames both carry the render-target ``viewport``, the
item's ``logical_size``, Qt's item ``matrix_values`` (item pixels -> clip space)
and a unit ``quad_vao``; the shared helpers take any frame with those fields.
"""
from __future__ import annotations

import math
from dataclasses import replace
from types import SimpleNamespace
from typing import Protocol

# QMatrix4x4 stores binary32 coefficients. Bound their rounding relative to the
# stored value, rather than treating cancellation noise as authored subpixels.
_MATRIX_ROUNDING = (2.0 ** -24) / (1.0 - 2.0 ** -24)

# The item quad: attribute 0 is a unit square placed in Qt Quick item pixels.
# vUv keeps the bottom-up convention the transition fragments were authored in.
ITEM_QUAD_VERTEX_SOURCE = """#version 460 core
layout(location = 0) in vec2 aPosition;

uniform mat4 uMatrix;
uniform vec2 uItemSize;

out vec2 vUv;

void main() {
    // Existing transition fragments flip Y. Feed their original bottom-up UV
    // convention while positioning the quad in Qt Quick item coordinates.
    vUv = vec2(aPosition.x, 1.0 - aPosition.y);
    gl_Position = uMatrix * vec4(aPosition * uItemSize, 0.0, 1.0);
}
"""


def item_quad_vertex_source(block_glsl: str) -> str:
    """The item quad for a program whose loose values are one std140 block (N1.6): ``block_glsl`` is that program's
    block declaration, holding ``uMatrix`` and ``uItemSize``, so the vertex and fragment stages declare the same block.
    The arithmetic is ``ITEM_QUAD_VERTEX_SOURCE``'s, which the 2D transitions' programs keep until they convert."""
    return f"""#version 460 core
layout(location = 0) in vec2 aPosition;
{block_glsl}
layout(location = 0) out vec2 vUv;

void main() {{
    vUv = vec2(aPosition.x, 1.0 - aPosition.y);
    gl_Position = uMatrix * vec4(aPosition * uItemSize, 0.0, 1.0);
}}
"""


class SceneFrame(Protocol):
    viewport: tuple[int, int, int, int]
    logical_size: tuple[float, float]
    matrix_values: tuple[float, ...]
    quad_vao: int


def _clip_turn(matrix, quarters):
    """Rotate clip XY (column-major), leaving Z/W and camera payload untouched."""
    result = list(matrix)
    for column in range(0, 16, 4):
        x, y = matrix[column], matrix[column + 1]
        result[column:column + 2] = ((-y, x) if quarters == 1 else (-x, -y)
                                    if quarters == 2 else (y, -x))
    return tuple(result)


def orient_visualizer_scene_frame(frame):
    """Render Scene3D in the quarter-turn's logical world; q0 is exactly the original frame.

    The virtual viewport is the physical viewport turned back by the content quarter-turn. The existing target
    composite turns its integer texels forward again. No pixel is stretched and no camera/world field is rewritten.
    """
    quarters = frame.content_rotation_quarters
    if not quarters or frame.scene_output_rotation:
        return frame
    width, height = frame.logical_size
    matrix = frame.matrix_values
    # New logical item coordinates -> the unchanged physical item (clockwise in Qt's top-down coordinates).
    x_basis, y_basis, translation = ((0, 1), (-1, 0), (width, 0)) if quarters == 1 else (
        ((-1, 0), (0, -1), (width, height)) if quarters == 2 else ((0, -1), (1, 0), (0, height)))
    turned = list(matrix)
    for row in range(4):
        turned[row] = matrix[row] * x_basis[0] + matrix[4 + row] * x_basis[1]
        turned[4 + row] = matrix[row] * y_basis[0] + matrix[4 + row] * y_basis[1]
        turned[12 + row] = matrix[12 + row] + matrix[row] * translation[0] + matrix[4 + row] * translation[1]
    turned = _clip_turn(turned, quarters)
    size = frame.oriented_logical_size
    presentation = frame.snapshot.presentation
    oriented = replace(presentation, outer_rect=(0.0, 0.0, *size), content_rect=frame.logical_content_rect,
                       viewport_extent=presentation.logical_viewport_extent, content_rotation_quarters=0)
    _vx, _vy, vw, vh = frame.viewport
    viewport = (0, 0, vh, vw) if quarters & 1 else (0, 0, vw, vh)
    return replace(frame, snapshot=replace(frame.snapshot, presentation=oriented), viewport=viewport,
                   logical_size=size, matrix_values=turned, scene_output_rotation=quarters,
                   scene_output_viewport=frame.viewport)


def scene_output_frame(frame):
    """The same quad placed back in Quick's physical window for the existing target composite."""
    quarters = getattr(frame, "scene_output_rotation", 0)
    if not quarters:
        return frame
    return SimpleNamespace(viewport=frame.scene_output_viewport, logical_size=frame.logical_size,
                           matrix_values=_clip_turn(frame.matrix_values, 4 - quarters), quad_vao=frame.quad_vao,
                           scene_output_rotation=quarters, scene_output_viewport=frame.scene_output_viewport)


def _stable_pixel_boundary(value: float, uncertainty: float):
    integer = round(value)
    return integer if abs(value-integer) <= uncertainty else value


# item_pixel_rect is a pure function of (matrix, logical size, viewport), which change only when the
# item or window does; renderers ask for it every frame. Remembering the last few answers by exact
# input keeps the uncertainty arithmetic off every frame at rest (identical output by construction).
# A few entries cover several displays' render threads and a renderer's reach frame beside its item.
_RECT_MEMO: dict = {}
_RECT_MEMO_LIMIT = 16


def item_pixel_rect(frame: SceneFrame) -> tuple[int, int, int, int]:
    """Outward pixel coverage, with integer boundaries stable under Qt's float32 transform.

    Only a boundary inside the propagated matrix-coefficient rounding uncertainty
    is snapped to an integer. Actual fractional edges still round outward, and
    viewport clipping remains the final authority.
    """
    key = (frame.matrix_values, frame.logical_size, frame.viewport)
    try:
        rect = _RECT_MEMO.get(key)
    except TypeError:                     # a caller-built frame holding lists: not memoised
        return _item_pixel_rect(*key)
    if rect is None:
        rect = _item_pixel_rect(*key)
        if len(_RECT_MEMO) >= _RECT_MEMO_LIMIT:
            _RECT_MEMO.clear()
        _RECT_MEMO[key] = rect
    return rect


def _item_pixel_rect(matrix, logical_size, viewport) -> tuple[int, int, int, int]:
    width, height = logical_size
    vx, vy, vw, vh = viewport
    xs, ys = [], []
    for x, y in ((0.0, 0.0), (width, 0.0), (0.0, height), (width, height)):
        clip = [matrix[row] * x + matrix[4 + row] * y + matrix[12 + row] for row in range(4)]
        w = clip[3] if clip[3] else 1.0
        px = vx + (clip[0] / w + 1.0) * 0.5 * vw
        py = vy + (clip[1] / w + 1.0) * 0.5 * vh
        # Error of c/w is bounded by (error(c)+abs(c/w)*error(w)) /
        # (abs(w)-error(w)). No snap is justified at an uncertain zero w.
        error_w = _MATRIX_ROUNDING * (abs(matrix[3]*x) + abs(matrix[7]*y) + abs(matrix[15]))
        denominator = abs(w) - error_w
        if clip[3] and denominator > 0.0:
            error_x = _MATRIX_ROUNDING * (abs(matrix[0]*x) + abs(matrix[4]*y) + abs(matrix[12]))
            error_y = _MATRIX_ROUNDING * (abs(matrix[1]*x) + abs(matrix[5]*y) + abs(matrix[13]))
            px = _stable_pixel_boundary(px, 0.5*vw*(error_x + abs(clip[0]/w)*error_w)/denominator)
            py = _stable_pixel_boundary(py, 0.5*vh*(error_y + abs(clip[1]/w)*error_w)/denominator)
        xs.append(px)
        ys.append(py)
    left = max(vx, math.floor(min(xs)))
    bottom = max(vy, math.floor(min(ys)))
    right = min(vx + vw, math.ceil(max(xs)))
    top = min(vy + vh, math.ceil(max(ys)))
    return left, bottom, max(0, right - left), max(0, top - bottom)


def _extended_item_frame(frame: SceneFrame, left: float, top: float, right: float, bottom: float):
    m = list(frame.matrix_values)
    for row in range(4):
        m[12 + row] -= left * m[row] + top * m[4 + row]
    width, height = frame.logical_size
    return SimpleNamespace(viewport=frame.viewport, logical_size=(width + left + right, height + top + bottom),
                           matrix_values=tuple(m), quad_vao=frame.quad_vao,
                           scene_output_rotation=getattr(frame, "scene_output_rotation", 0),
                           scene_output_viewport=getattr(frame, "scene_output_viewport", None))


# A reaching scene's target grows in steps of this share of the item's height, so it reallocates
# only when the scene's reach crosses a step (an orbit), never per frame of music.
REACH_STEP = 0.25


def reach_item_frame(frame: SceneFrame, bounds: tuple[float, float, float, float]):
    """A frame like ``frame`` whose item covers ``bounds`` too: the item-local (left, top, right,
    bottom) extent of everything a 3D + frameless scene can draw, for its render target. Each side
    reaches just past the bounds in ``REACH_STEP`` steps and never past the window (a 3D frameless
    Visualizer is not contained to its frame, operator 2026-10-04)."""
    width, height = frame.logical_size
    step = max(1e-6, REACH_STEP * height)
    m = frame.matrix_values
    _vx, _vy, vw, vh = frame.viewport
    per_unit = min(abs(m[0]) * 0.5 * vw, abs(m[5]) * 0.5 * vh) or 1.0
    most = max(vw, vh) / per_unit                     # item units across the whole window
    left, top, right, bottom = (max(0.0, value) for value in (
        -bounds[0], -bounds[1], bounds[2] - width, bounds[3] - height))
    reach = [min(most, math.ceil(value / step - 1e-9) * step) for value in (left, top, right, bottom)]
    return _extended_item_frame(frame, *reach)
