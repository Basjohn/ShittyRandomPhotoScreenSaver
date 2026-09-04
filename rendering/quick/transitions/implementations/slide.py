"""Quick Slide renderer with one seam-proof cardinal coverage partition."""

from __future__ import annotations

import math

from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_DIRECTION_VECTORS = {
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "up": (0.0, -1.0),
    "down": (0.0, 1.0),
}
_MOTION_STYLE_CODES = {"Linear": 0, "Elastic": 1, "Wobble": 2, "Flex": 3}


_SLIDE_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_direction;
uniform int u_motionStyle;

float elasticArrival(float t) {
    // Preserve ordinary travel until the final arrival window, then settle
    // with a <= 2.5% damped overshoot. This is analytical and uses the run's
    // sole existing progress sample.
    const float arrivalStart = 0.78;
    if (t <= arrivalStart) return t;
    float q = (t - arrivalStart) / (1.0 - arrivalStart);
    return 1.0 - (1.0 - arrivalStart) * exp(-10.0 * q)
        * cos(12.566370614359172 * q);
}

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);
    if (t <= 0.0) {
        FragColor = texture(uOldTex, uv);
        return;
    }
    if (t >= 1.0) {
        FragColor = texture(uNewTex, uv);
        return;
    }
    float travel = u_motionStyle == 1 ? elasticArrival(t) : t;
    float orthogonalAxis = abs(u_direction.x) > 0.5 ? uv.y : uv.x;
    if (u_motionStyle == 3) {
        travel += 0.065 * sin(3.141592653589793 * t)
            * sin(6.283185307179586 * orthogonalAxis);
    }

    // Both images use the same sample and exactly one owner. During Elastic's
    // arrival overshoot, its full destination surface clamps at the departing
    // edge so an opposite texture strip cannot wrap into view.
    vec2 shiftedUv = uv - u_direction * travel;
    vec2 localUv = travel > 1.0
        ? clamp(uv - u_direction * (travel - 1.0), 0.0, 1.0)
        : fract(shiftedUv);
    if (u_motionStyle == 2) {
        float envelope = sin(3.141592653589793 * t);
        float wobble = 0.012 * envelope * (
            sin(12.566370614359172 * orthogonalAxis)
            + 0.5 * sin(25.132741228718345 * orthogonalAxis)
        );
        if (abs(u_direction.x) > 0.5) {
            localUv.y = clamp(localUv.y + wobble, 0.0, 1.0);
        } else {
            localUv.x = clamp(localUv.x + wobble, 0.0, 1.0);
        }
    }
    float axis = abs(u_direction.x) > 0.5 ? uv.x : uv.y;
    float signedDirection = u_direction.x + u_direction.y;
    float destinationOwns = travel >= 1.0 ? 1.0 : (signedDirection < 0.0
        ? step(1.0 - travel, axis)
        : 1.0 - step(travel, axis));

    vec4 oldColor = texture(uOldTex, localUv);
    vec4 newColor = texture(uNewTex, localUv);
    FragColor = mix(oldColor, newColor, destinationOwns);
}
"""


def _slide_motion_style(style: object) -> str:
    value = "Linear" if style is None else str(style).strip()
    if value not in _MOTION_STYLE_CODES:
        raise ValueError(f"unknown canonical Slide motion style: {style!r}")
    return value


def _slide_elastic_arrival(canonical_time: float) -> float:
    """Closed-form arrival overshoot with exact authored endpoints."""

    t = max(0.0, min(1.0, float(canonical_time)))
    if t == 0.0 or t == 1.0:
        return t
    arrival_start = 0.78
    if t <= arrival_start:
        return t
    q = (t - arrival_start) / (1.0 - arrival_start)
    return 1.0 - (1.0 - arrival_start) * math.exp(-10.0 * q) * math.cos(4.0 * math.pi * q)


def _slide_direction_vector(direction: object) -> tuple[float, float]:
    """Resolve one of Slide's four product-supported cardinal directions."""

    value = "left" if direction is None else str(direction).strip().lower()
    vector = _DIRECTION_VECTORS.get(value)
    if vector is None:
        raise ValueError(f"unknown canonical Slide direction: {direction!r}")
    return vector


def _slide_partition_sample(
    direction: object,
    progress: float,
    coordinate: tuple[float, float],
    motion_style: object = "Linear",
) -> tuple[str, tuple[float, float]]:
    """Return the sole image owner and shared local UV for one output point."""

    x, y = (float(value) for value in coordinate)
    if not 0.0 <= x < 1.0 or not 0.0 <= y < 1.0:
        raise ValueError("Slide coverage coordinates must be normalized pixel centres")
    dx, dy = _slide_direction_vector(direction)
    style = _slide_motion_style(motion_style)
    t = max(0.0, min(1.0, float(progress)))
    if t == 0.0:
        return "source", (x, y)
    if t == 1.0:
        return "destination", (x, y)
    if style == "Elastic":
        amount = _slide_elastic_arrival(t)
    elif style == "Flex":
        perpendicular = y if dx else x
        amount = t + 0.065 * math.sin(math.pi * t) * math.sin(2.0 * math.pi * perpendicular)
    else:
        amount = t
    axis = x if dx else y
    signed_direction = dx + dy
    if amount >= 1.0:
        destination_owns = True
    elif signed_direction < 0.0:
        destination_owns = axis >= 1.0 - amount
    else:
        destination_owns = axis < amount
    shifted_uv = (x - dx * amount, y - dy * amount)
    if amount > 1.0:
        arrived_uv = (x - dx * (amount - 1.0), y - dy * (amount - 1.0))
        local_uv = tuple(max(0.0, min(1.0, value)) for value in arrived_uv)
    else:
        local_uv = tuple(value % 1.0 for value in shifted_uv)
    if style == "Wobble":
        perpendicular = y if dx else x
        wobble = 0.012 * math.sin(math.pi * t) * (
            math.sin(4.0 * math.pi * perpendicular)
            + 0.5 * math.sin(8.0 * math.pi * perpendicular)
        )
        if dx:
            local_uv = (local_uv[0], max(0.0, min(1.0, local_uv[1] + wobble)))
        else:
            local_uv = (max(0.0, min(1.0, local_uv[0] + wobble)), local_uv[1])
    return ("destination" if destination_owns else "source"), local_uv


class QuickSlideRenderer:
    transition_id = "slide"

    def __init__(self) -> None:
        self._program = 0
        self._uniforms: dict[str, int] = {}

    @property
    def has_resources(self) -> bool:
        return bool(self._program)

    def render(self, frame: QuickTransitionRenderFrame) -> None:
        if not self._program:
            self._initialize()
        uniforms = self._uniforms
        progress = float(frame.sample.eased_progress)
        direction = _slide_direction_vector(frame.run.request.direction)
        motion_style = _slide_motion_style(
            frame.run.request.parameter_dict().get("motion_style", "Linear")
        )

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(uniforms["u_progress"], progress)
        gl.glUniform2f(uniforms["u_direction"], *direction)
        gl.glUniform1i(uniforms["u_motionStyle"], _MOTION_STYLE_CODES[motion_style])
        gl.glActiveTexture(gl.GL_TEXTURE0)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.source_texture_id)
        gl.glUniform1i(uniforms["uOldTex"], 0)
        gl.glActiveTexture(gl.GL_TEXTURE1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, frame.destination_texture_id)
        gl.glUniform1i(uniforms["uNewTex"], 1)
        gl.glBindVertexArray(frame.quad_vao)
        gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)

    def release_resources(self) -> None:
        if not self._program:
            return
        gl.glDeleteProgram(self._program)
        self._program = 0
        self._uniforms.clear()

    def _initialize(self) -> None:
        program = compile_program(
            QUICK_TRANSITION_VERTEX_SOURCE,
            _SLIDE_FRAGMENT_SOURCE,
            label="Quick Slide",
        )
        self._program = program
        try:
            uniform_names = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_direction",
                "u_motionStyle",
                "uOldTex",
                "uNewTex",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in uniform_names
            }
            required = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_direction",
                "u_motionStyle",
                "uOldTex",
                "uNewTex",
            )
            missing = [name for name in required if uniforms[name] < 0]
            if missing:
                raise RuntimeError(
                    "Quick Slide uniforms are incomplete: " + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickSlideRenderer:
    return QuickSlideRenderer()
