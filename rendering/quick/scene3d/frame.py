"""What a 3D scene needs from its render node's frame (pure; no GL).

Transition and Visualizer frames both carry the render-target ``viewport``, the
item's ``logical_size``, Qt's item ``matrix_values`` (item pixels -> clip space)
and a unit ``quad_vao``; the shared helpers take any frame with those fields.
"""
from __future__ import annotations

import math
from typing import Protocol

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


def item_pixel_rect(frame: SceneFrame) -> tuple[int, int, int, int]:
    """The item's bounding rect in render-target pixels (GL, bottom-up), clamped to the viewport."""
    matrix = frame.matrix_values
    width, height = frame.logical_size
    vx, vy, vw, vh = frame.viewport
    xs, ys = [], []
    for x, y in ((0.0, 0.0), (width, 0.0), (0.0, height), (width, height)):
        clip = [matrix[row] * x + matrix[4 + row] * y + matrix[12 + row] for row in range(4)]
        w = clip[3] if clip[3] else 1.0
        xs.append(vx + (clip[0] / w + 1.0) * 0.5 * vw)
        ys.append(vy + (clip[1] / w + 1.0) * 0.5 * vh)
    left = max(vx, math.floor(min(xs) + 1e-6))
    bottom = max(vy, math.floor(min(ys) + 1e-6))
    right = min(vx + vw, math.ceil(max(xs) - 1e-6))
    top = min(vy + vh, math.ceil(max(ys) - 1e-6))
    return left, bottom, max(0, right - left), max(0, top - bottom)


def padded_item_frame(frame: SceneFrame, pad: float):
    """A frame like ``frame`` whose item reaches ``pad`` item-local units further on every side
    (its matrix shifted to match): the target rect for a scene allowed to leave its item."""
    from types import SimpleNamespace

    m = list(frame.matrix_values)
    for row in range(4):
        m[12 + row] -= pad * (m[row] + m[4 + row])
    width, height = frame.logical_size
    return SimpleNamespace(viewport=frame.viewport, logical_size=(width + 2.0 * pad, height + 2.0 * pad),
                           matrix_values=tuple(m), quad_vao=frame.quad_vao)
