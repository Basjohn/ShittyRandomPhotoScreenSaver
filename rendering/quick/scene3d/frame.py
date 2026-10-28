"""What a 3D scene needs from its render node's frame (pure; no GL).

Transition and Visualizer frames both carry the render-target ``viewport``, the
item's ``logical_size``, Qt's item ``matrix_values`` (item pixels -> clip space)
and a unit ``quad_vao``; the shared helpers take any frame with those fields.
"""
from __future__ import annotations

import math
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


class SceneFrame(Protocol):
    viewport: tuple[int, int, int, int]
    logical_size: tuple[float, float]
    matrix_values: tuple[float, ...]
    quad_vao: int


def _stable_pixel_boundary(value: float, uncertainty: float):
    integer = round(value)
    return integer if abs(value-integer) <= uncertainty else value


def item_pixel_rect(frame: SceneFrame) -> tuple[int, int, int, int]:
    """Outward pixel coverage, with integer boundaries stable under Qt's float32 transform.

    Only a boundary inside the propagated matrix-coefficient rounding uncertainty
    is snapped to an integer. Actual fractional edges still round outward, and
    viewport clipping remains the final authority.
    """
    matrix = frame.matrix_values
    width, height = frame.logical_size
    vx, vy, vw, vh = frame.viewport
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
    from types import SimpleNamespace

    m = list(frame.matrix_values)
    for row in range(4):
        m[12 + row] -= left * m[row] + top * m[4 + row]
    width, height = frame.logical_size
    return SimpleNamespace(viewport=frame.viewport, logical_size=(width + left + right, height + top + bottom),
                           matrix_values=tuple(m), quad_vao=frame.quad_vao)


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
