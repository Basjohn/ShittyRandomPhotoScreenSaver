"""Quick Slide renderer with one seam-proof cardinal coverage partition."""

from __future__ import annotations

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


_SLIDE_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_direction;

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);

    // Both images use this one immutable sample. Wrapping the shared shifted
    // coordinate and selecting exactly one owner leaves no background branch
    // and therefore no cadence- or rounding-dependent seam.
    vec2 localUv = fract(uv - u_direction * t);
    float axis = abs(u_direction.x) > 0.5 ? uv.x : uv.y;
    float signedDirection = u_direction.x + u_direction.y;
    float destinationOwns = signedDirection < 0.0
        ? step(1.0 - t, axis)
        : 1.0 - step(t, axis);

    vec4 oldColor = texture(uOldTex, localUv);
    vec4 newColor = texture(uNewTex, localUv);
    FragColor = mix(oldColor, newColor, destinationOwns);
}
"""


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
) -> tuple[str, tuple[float, float]]:
    """Return the sole image owner and shared local UV for one output point."""

    amount = max(0.0, min(1.0, float(progress)))
    x, y = (float(value) for value in coordinate)
    if not 0.0 <= x < 1.0 or not 0.0 <= y < 1.0:
        raise ValueError("Slide coverage coordinates must be normalized pixel centres")
    dx, dy = _slide_direction_vector(direction)
    axis = x if dx else y
    signed_direction = dx + dy
    if signed_direction < 0.0:
        destination_owns = axis >= 1.0 - amount
    else:
        destination_owns = axis < amount
    local_uv = ((x - dx * amount) % 1.0, (y - dy * amount) % 1.0)
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
