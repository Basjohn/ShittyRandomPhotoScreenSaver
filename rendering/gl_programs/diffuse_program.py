"""Diffuse transition shader program.

Diffuse reveals the new image in a block-based pattern. Each logical block in
a grid receives a hashed random threshold so blocks fade in over time rather
than switching all at once. Supports Rectangle and Membrane shape modes.
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


class DiffuseProgram(BaseGLProgram):
    """Shader program for the Diffuse transition effect."""

    @property
    def name(self) -> str:
        return "Diffuse"

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
uniform int u_shapeMode;    // 0=Rectangle, 1=Membrane

float hash1(float n) {
    return fract(sin(n) * 43758.5453123);
}

float hash2(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Logical block grid in UV space; fall back to a single block when the
    // grid is not configured.
    vec2 grid = max(u_grid, vec2(1.0));
    vec2 cell = clamp(floor(uv * grid), vec2(0.0), grid - vec2(1.0));
    float cols = grid.x;
    float rows = grid.y;
    float cellIndex = cell.y * cols + cell.x;

    // Per-block randomised reveal threshold in [0, 1].
    float rnd = hash1(cellIndex * 37.0 + 13.0);
    float width = 0.18;
    float shaped = pow(rnd, 1.35);
    float threshold = min(shaped, 1.0 - width);

    // Small local smoothing window.
    float local = smoothstep(threshold, threshold + width, t);

    // Local UV inside the current block for shape masks.
    vec2 cellOrigin = cell / grid;
    vec2 cellSize = vec2(1.0) / grid;
    vec2 uvLocal = (uv - cellOrigin) / cellSize; // 0..1 inside block

    // Rectangle (0): whole-block transition using the local timing only.
    float rectMix = local;

    // Per-block shape progress.
    float shapeProgress = 0.0;
    if (t > threshold) {
        float span = max(1e-4, 1.0 - threshold);
        shapeProgress = clamp((t - threshold) / span, 0.0, 1.0);
    }

    float blockMix = rectMix;

    if (u_shapeMode == 1) {
        // Membrane mode: soft feathered circles that break apart organically.
        // Use continuous UV coordinates to avoid hard block edges.
        vec2 centred = uvLocal - vec2(0.5);
        
        // Per-cell random offset to break up the grid pattern.
        float cellRnd1 = hash1(cellIndex * 91.0 + 7.0);
        float cellRnd2 = hash1(cellIndex * 53.0 + 23.0);
        vec2 offset = (vec2(cellRnd1, cellRnd2) - 0.5) * 0.3;
        centred += offset * shapeProgress;
        
        float baseR = length(centred);
        
        // Angular wobble to make circles look like breaking membranes.
        float angle = atan(centred.y, centred.x);
        float wobbleFreq = 3.0 + cellRnd1 * 4.0;
        float wobbleAmp = 0.15 + cellRnd2 * 0.15;
        float wobble = sin(angle * wobbleFreq + cellIndex * 1.7) * wobbleAmp;
        wobble *= shapeProgress;  // Wobble grows as membrane breaks
        
        float r = baseR * (1.0 + wobble);
        
        // Expanding circle with very soft feathered edge.
        float memMinR = 0.05;
        float memMaxR = 0.75;  // Larger to ensure full coverage
        float memR = mix(memMinR, memMaxR, shapeProgress);
        
        // Wide feather for soft membrane edge.
        float feather = 0.35 + 0.15 * shapeProgress;
        float memInner = max(0.0, memR - feather);
        float memOuter = memR + feather * 0.5;
        
        float membraneMask = 1.0 - smoothstep(memInner, memOuter, r);
        blockMix = local * membraneMask;
        
        // Blend with neighboring cells to soften grid edges.
        // Sample nearby cells and blend their contributions.
        float edgeSoftness = 0.0;
        vec2 cellFrac = fract(uv * grid);
        float edgeDist = min(min(cellFrac.x, 1.0 - cellFrac.x), 
                            min(cellFrac.y, 1.0 - cellFrac.y));
        float edgeBlend = smoothstep(0.0, 0.15, edgeDist);
        blockMix *= mix(0.7, 1.0, edgeBlend);
    }

    // Global tail for clean landing.
    float tail;
    if (u_shapeMode == 1) {
        float blockFade = 1.0 - smoothstep(0.80, 0.92, t);
        blockMix *= blockFade;
        tail = smoothstep(0.80, 1.0, t);
        if (t > 0.92) {
            blockMix = min(blockMix, tail);
        }
    } else {
        tail = smoothstep(0.96, 1.0, t);
    }

    float mixFactor = clamp(max(blockMix, tail), 0.0, 1.0);

    vec4 color = mix(oldColor, newColor, mixFactor);
    FragColor = color;
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Diffuse program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "u_resolution": gl.glGetUniformLocation(program, "u_resolution"),
            "uOldTex": gl.glGetUniformLocation(program, "uOldTex"),
            "uNewTex": gl.glGetUniformLocation(program, "uNewTex"),
            "u_grid": gl.glGetUniformLocation(program, "u_grid"),
            "u_shapeMode": gl.glGetUniformLocation(program, "u_shapeMode"),
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
        """Draw one frame of the Diffuse transition."""
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

            if uniforms.get("u_shapeMode", -1) != -1:
                shape_mode = int(getattr(state, "shape_mode", 0))
                gl.glUniform1i(uniforms["u_shapeMode"], shape_mode)

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
diffuse_program = DiffuseProgram()
