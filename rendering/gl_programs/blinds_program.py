"""Blinds transition shader program.

Blinds is modelled as horizontal bands within each grid cell that grow
symmetrically from the centre outwards. At t=0 the bands are collapsed
to thin lines; by t=1 they cover the full cell width.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from rendering.gl_programs.base_program import BaseGLProgram

logger = logging.getLogger(__name__)

# PyOpenGL import with graceful fallback
try:
    from OpenGL import GL as gl
except ImportError:
    gl = None  # type: ignore


class BlindsProgram(BaseGLProgram):
    """Shader program for the Blinds transition effect."""

    @property
    def name(self) -> str:
        return "Blinds"

    @property
    def vertex_source(self) -> str:
        return """#version 410 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;

out vec2 vUv;

void main() {
    vUv = aUv;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

    @property
    def fragment_source(self) -> str:
        return """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_resolution;
uniform vec2 u_grid;        // (cols, rows)
uniform float u_feather;     // soft-edge width (0..0.5)
uniform int u_direction;     // 0=Horizontal, 1=Vertical, 2=Diagonal

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Logical grid in UV space; when u_grid is unset we fall back to a
    // single full-frame cell so the effect still works.
    vec2 grid = max(u_grid, vec2(1.0));
    vec2 cell = clamp(floor(uv * grid), vec2(0.0), grid - vec2(1.0));

    vec2 cellOrigin = cell / grid;
    vec2 cellSize = vec2(1.0) / grid;
    vec2 uvLocal = (uv - cellOrigin) / cellSize; // 0..1 inside cell

    // Pick the axis coordinate based on direction.
    // 0=Horizontal (bands grow along X), 1=Vertical (Y), 2=Diagonal (X+Y).
    float coord;
    if (u_direction == 1) {
        coord = uvLocal.y;
    } else if (u_direction == 2) {
        coord = (uvLocal.x + uvLocal.y) * 0.5;
    } else {
        coord = uvLocal.x;
    }

    // Blinds are modelled as bands within each cell that grow symmetrically
    // from the centre outwards. At t=0 the band is collapsed to a thin line;
    // by t=1 it covers the full cell.
    float w = clamp(t, 0.0, 1.0);
    float half = 0.5 * w;
    float left = 0.5 - half;
    float right = 0.5 + half;

    // Soft edges so the band does not appear as a harsh 1px stripe.
    float feather = clamp(u_feather, 0.001, 0.5);
    float edgeL = smoothstep(left - feather, left, coord);
    float edgeR = 1.0 - smoothstep(right, right + feather, coord);
    float bandMask = clamp(edgeL * edgeR, 0.0, 1.0);

    // Late global tail to guarantee we land on a fully revealed frame even
    // if numerical jitter leaves small gaps in the band coverage.
    float tail = smoothstep(0.96, 1.0, t);
    float mixFactor = clamp(max(bandMask, tail), 0.0, 1.0);

    FragColor = mix(oldColor, newColor, mixFactor);
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Blinds program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "u_resolution": gl.glGetUniformLocation(program, "u_resolution"),
            "uOldTex": gl.glGetUniformLocation(program, "uOldTex"),
            "uNewTex": gl.glGetUniformLocation(program, "uNewTex"),
            "u_grid": gl.glGetUniformLocation(program, "u_grid"),
            "u_feather": gl.glGetUniformLocation(program, "u_feather"),
            "u_direction": gl.glGetUniformLocation(program, "u_direction"),
        }

    def render(
        self,
        program: int,
        uniforms: Dict[str, int],
        viewport: Tuple[int, int],
        old_tex: int,
        new_tex: int,
        state: Any,
        quad_vao: int,
    ) -> None:
        """Draw one frame of the Blinds transition."""
        if gl is None:
            return

        vp_w, vp_h = viewport
        progress = max(0.0, min(1.0, float(getattr(state, "progress", 0.0))))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(program)
        try:
            if uniforms.get("u_progress", -1) != -1:
                gl.glUniform1f(uniforms["u_progress"], float(progress))

            if uniforms.get("u_resolution", -1) != -1:
                gl.glUniform2f(uniforms["u_resolution"], float(vp_w), float(vp_h))

            if uniforms.get("u_grid", -1) != -1:
                cols = float(max(1, int(getattr(state, "cols", 1))))
                rows = float(max(1, int(getattr(state, "rows", 1))))
                gl.glUniform2f(uniforms["u_grid"], cols, rows)

            if uniforms.get("u_feather", -1) != -1:
                feather = max(0.001, min(0.5, float(getattr(state, "feather", 0.08))))
                gl.glUniform1f(uniforms["u_feather"], feather)

            if uniforms.get("u_direction", -1) != -1:
                direction = int(getattr(state, "direction", 0))
                gl.glUniform1i(uniforms["u_direction"], direction)

            if uniforms.get("uOldTex", -1) != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, old_tex)
                gl.glUniform1i(uniforms["uOldTex"], 0)

            if uniforms.get("uNewTex", -1) != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, new_tex)
                gl.glUniform1i(uniforms["uNewTex"], 1)

            self._draw_fullscreen_quad(quad_vao)

        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)


# Singleton instance for convenience
blinds_program = BlindsProgram()
