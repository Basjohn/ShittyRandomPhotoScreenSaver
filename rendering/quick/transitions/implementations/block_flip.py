"""Lazy Quick renderer for shader-authoritative Block Puzzle Flip slabs."""

from __future__ import annotations

from collections.abc import Mapping

from OpenGL import GL as gl

from rendering.quick.render.gl_resources import compile_program
from ..render_contract import (
    QUICK_TRANSITION_VERTEX_SOURCE,
    QuickTransitionRenderFrame,
)


_DIRECTION_VECTORS = {
    "left": (1.0, 0.0),
    "right": (-1.0, 0.0),
    "up": (0.0, -1.0),
    "down": (0.0, 1.0),
    "diag_tl_br": (1.0, 1.0),
    "diag_tr_bl": (-1.0, 1.0),
}
_MIN_STRIPS = 2
_MAX_STRIPS = 25


_BLOCK_FLIP_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_grid;
uniform vec2 u_direction;

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);

    // Exact endpoints keep the baseline and destination free of slab shading,
    // seams, or the old full-screen dark/soft-lined startup wash.
    if (t <= 0.0) {
        FragColor = texture(uOldTex, uv);
        return;
    }
    if (t >= 1.0) {
        FragColor = texture(uNewTex, uv);
        return;
    }

    vec2 grid = max(u_grid, vec2(2.0));
    vec2 direction = u_direction;
    bool diagonal = abs(direction.x) > 0.5 && abs(direction.y) > 0.5;
    float stripCount;
    float stripAxis;
    vec2 stripBasis;

    if (diagonal) {
        // Diagonal settings remain genuine diagonal strip waves. The basis
        // changes the texture coordinate along the diagonal slab normal.
        stripCount = max(grid.x, grid.y);
        if (direction.x > 0.0) {
            stripAxis = (uv.x + uv.y) * 0.5;
            stripBasis = vec2(1.0, 1.0);
        } else {
            stripAxis = ((1.0 - uv.x) + uv.y) * 0.5;
            stripBasis = vec2(-1.0, 1.0);
        }
    } else if (abs(direction.x) > 0.5) {
        // Horizontal travel flips vertical column slabs.
        stripCount = grid.x;
        if (direction.x > 0.0) {
            stripAxis = uv.x;
            stripBasis = vec2(1.0, 0.0);
        } else {
            stripAxis = 1.0 - uv.x;
            stripBasis = vec2(-1.0, 0.0);
        }
    } else {
        // Vertical travel flips horizontal row slabs.
        stripCount = grid.y;
        if (direction.y > 0.0) {
            stripAxis = uv.y;
            stripBasis = vec2(0.0, 1.0);
        } else {
            stripAxis = 1.0 - uv.y;
            stripBasis = vec2(0.0, -1.0);
        }
    }

    float scaledAxis = min(clamp(stripAxis, 0.0, 1.0), 0.999999)
        * stripCount;
    float stripIndex = floor(scaledAxis);
    float stripLocal = fract(scaledAxis);
    float order = stripCount > 1.0
        ? stripIndex / (stripCount - 1.0)
        : 0.0;

    // A linear run feeds authored stagger and local cosine rotation. The
    // short clean lead-in prevents a first-frame whole-screen appearance
    // change, while the final slab still lands exactly at the deadline.
    float start = 0.03 + order * 0.64;
    float localLinear = clamp((t - start) / 0.33, 0.0, 1.0);
    if (localLinear <= 0.0) {
        FragColor = texture(uOldTex, uv);
        return;
    }
    if (localLinear >= 1.0) {
        FragColor = texture(uNewTex, uv);
        return;
    }

    float localTurn = 0.5 - 0.5 * cos(localLinear * 3.14159265);
    float faceScale = abs(cos(localTurn * 3.14159265));
    float halfWidth = 0.5 * faceScale;
    if (abs(stripLocal - 0.5) > halfWidth) {
        // The main Quick render target is the only surface. This is the void
        // exposed behind a slab as its projected face turns edge-on.
        FragColor = vec4(0.0, 0.0, 0.0, 1.0);
        return;
    }

    float faceLocal = (stripLocal - 0.5) / max(faceScale, 0.0001) + 0.5;
    bool showsNewFace = localTurn >= 0.5;
    if (showsNewFace) {
        faceLocal = 1.0 - faceLocal;
    }
    float axisDelta = (faceLocal - stripLocal) / stripCount;
    vec2 sampleUv = clamp(
        uv + stripBasis * axisDelta,
        vec2(0.0),
        vec2(1.0)
    );
    vec4 face = showsNewFace
        ? texture(uNewTex, sampleUv)
        : texture(uOldTex, sampleUv);

    float diffuse = 0.42 + 0.58 * pow(faceScale, 0.55);
    float edgeHighlight = 0.10 * pow(1.0 - faceScale, 6.0)
        * (1.0 - abs(faceLocal * 2.0 - 1.0));
    float acrossFace = mix(0.94, 1.04, clamp(faceLocal, 0.0, 1.0));
    float light = clamp(diffuse * acrossFace + edgeHighlight, 0.0, 1.08);
    FragColor = vec4(face.rgb * light, face.a);
}
"""


def _block_flip_direction_vector(direction: object) -> tuple[float, float]:
    value = str(direction).strip().lower()
    vector = _DIRECTION_VECTORS.get(value)
    if vector is None:
        raise ValueError(
            f"unknown resolved Block Puzzle Flip direction: {direction!r}"
        )
    return vector


def _block_flip_grid(parameters: Mapping[str, object]) -> tuple[int, int]:
    """Read the resolved Settings-owned grid without a silent renderer fallback."""

    values: list[int] = []
    for name in ("cols", "rows"):
        raw = parameters.get(name)
        if isinstance(raw, bool) or not isinstance(raw, int):
            raise ValueError(
                f"Block Puzzle Flip requires resolved integer parameter {name!r}"
            )
        value = int(raw)
        if not _MIN_STRIPS <= value <= _MAX_STRIPS:
            raise ValueError(
                f"Block Puzzle Flip {name} must be between "
                f"{_MIN_STRIPS} and {_MAX_STRIPS}"
            )
        values.append(value)
    return values[0], values[1]


class QuickBlockFlipRenderer:
    transition_id = "block_flip"

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
        cols, rows = _block_flip_grid(frame.run.request.parameter_dict())
        direction = _block_flip_direction_vector(frame.run.request.direction)

        gl.glUseProgram(self._program)
        gl.glUniformMatrix4fv(
            uniforms["uMatrix"],
            1,
            gl.GL_FALSE,
            frame.matrix_values,
        )
        gl.glUniform2f(uniforms["uItemSize"], *frame.logical_size)
        gl.glUniform1f(
            uniforms["u_progress"],
            float(frame.sample.eased_progress),
        )
        gl.glUniform2f(uniforms["u_grid"], float(cols), float(rows))
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
            _BLOCK_FLIP_FRAGMENT_SOURCE,
            label="Quick Block Puzzle Flip",
        )
        self._program = program
        try:
            uniform_names = (
                "uMatrix",
                "uItemSize",
                "u_progress",
                "u_grid",
                "u_direction",
                "uOldTex",
                "uNewTex",
            )
            uniforms = {
                name: int(gl.glGetUniformLocation(program, name))
                for name in uniform_names
            }
            missing = [
                name for name, location in uniforms.items() if location < 0
            ]
            if missing:
                raise RuntimeError(
                    "Quick Block Puzzle Flip uniforms are incomplete: "
                    + ", ".join(missing)
                )
            self._uniforms = uniforms
        except Exception:
            self.release_resources()
            raise


def create_transition_renderer() -> QuickBlockFlipRenderer:
    return QuickBlockFlipRenderer()
