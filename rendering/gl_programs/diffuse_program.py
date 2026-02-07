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
uniform int u_shapeMode;    // 0=Rectangle, 1=Membrane, 2=Lines, 3=Diamonds, 4=Amorph

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

    // Rectangle (0): whole-block transition with slight edge feathering.
    vec2 cellFrac = fract(uv * grid);
    float edgeDist = min(min(cellFrac.x, 1.0 - cellFrac.x), 
                        min(cellFrac.y, 1.0 - cellFrac.y));
    float rectEdgeFeather = smoothstep(0.0, 0.08, edgeDist);
    float rectMix = local * mix(0.92, 1.0, rectEdgeFeather);

    // Per-block shape progress.
    float shapeProgress = 0.0;
    if (t > threshold) {
        float span = max(1e-4, 1.0 - threshold);
        shapeProgress = clamp((t - threshold) / span, 0.0, 1.0);
    }

    float blockMix = rectMix;

    if (u_shapeMode == 1) {
        // Membrane mode: cohesive overlapping circles that blend together.
        float totalMask = 0.0;
        
        for (int dy = -1; dy <= 1; dy++) {
            for (int dx = -1; dx <= 1; dx++) {
                vec2 neighborCell = cell + vec2(float(dx), float(dy));
                
                if (neighborCell.x < 0.0 || neighborCell.x >= cols ||
                    neighborCell.y < 0.0 || neighborCell.y >= rows) {
                    continue;
                }
                
                float neighborIndex = neighborCell.y * cols + neighborCell.x;
                float neighborRnd = hash1(neighborIndex * 37.0 + 13.0);
                float neighborShaped = pow(neighborRnd, 1.35);
                float neighborThreshold = min(neighborShaped, 1.0 - width);
                
                float neighborProgress = 0.0;
                if (t > neighborThreshold) {
                    float span = max(1e-4, 1.0 - neighborThreshold);
                    neighborProgress = clamp((t - neighborThreshold) / span, 0.0, 1.0);
                }
                
                if (neighborProgress <= 0.0) continue;
                
                vec2 neighborCenter = (neighborCell + vec2(0.5)) / grid;
                float cellRnd1 = hash1(neighborIndex * 91.0 + 7.0);
                float cellRnd2 = hash1(neighborIndex * 53.0 + 23.0);
                vec2 offset = (vec2(cellRnd1, cellRnd2) - 0.5) * 0.3 / grid;
                neighborCenter += offset * neighborProgress;
                
                vec2 toCenter = uv - neighborCenter;
                float dist = length(toCenter);
                
                float maxRadius = 1.2 / min(cols, rows);
                float circleR = mix(0.0, maxRadius, neighborProgress);
                float feather = 0.15 / min(cols, rows);
                float circleMask = 1.0 - smoothstep(circleR - feather, circleR + feather, dist);
                
                totalMask = max(totalMask, circleMask);
            }
        }
        
        blockMix = totalMask;

    } else if (u_shapeMode == 2) {
        // Lines mode: alternating horizontal/vertical line sweeps per block.
        float lineDir = hash1(cellIndex * 71.0 + 3.0);
        float linePos;
        if (lineDir > 0.5) {
            linePos = cellFrac.x;  // vertical line sweep
        } else {
            linePos = cellFrac.y;  // horizontal line sweep
        }
        // Sweep from one edge — direction per block
        float sweepDir = hash1(cellIndex * 43.0 + 17.0);
        if (sweepDir > 0.5) linePos = 1.0 - linePos;
        float lineEdge = shapeProgress * 1.15;
        float lineFeather = 0.12;
        float lineMask = smoothstep(lineEdge - lineFeather, lineEdge, linePos);
        lineMask = 1.0 - lineMask;
        blockMix = lineMask;

    } else if (u_shapeMode == 3 || (u_shapeMode == 5 && mod(cellIndex, 3.0) < 1.0)) {
        // Diamonds mode: cross-block diamond sampling to avoid square edges.
        float totalMask = 0.0;
        for (int dy = -1; dy <= 1; dy++) {
            for (int dx = -1; dx <= 1; dx++) {
                vec2 nCell = cell + vec2(float(dx), float(dy));
                if (nCell.x < 0.0 || nCell.x >= cols ||
                    nCell.y < 0.0 || nCell.y >= rows) continue;
                float nIdx = nCell.y * cols + nCell.x;
                float nRnd = hash1(nIdx * 37.0 + 13.0);
                float nThresh = min(pow(nRnd, 1.35), 1.0 - width);
                float nProg = 0.0;
                if (t > nThresh) {
                    nProg = clamp((t - nThresh) / max(1e-4, 1.0 - nThresh), 0.0, 1.0);
                }
                if (nProg <= 0.0) continue;
                vec2 nCenter = (nCell + vec2(0.5)) / grid;
                vec2 toC = uv - nCenter;
                float dDist = (abs(toC.x) + abs(toC.y)) * min(cols, rows);
                float dR = nProg * 1.15;
                float dFeather = 0.12;
                float dMask = 1.0 - smoothstep(dR - dFeather, dR + dFeather, dDist);
                totalMask = max(totalMask, dMask);
            }
        }
        blockMix = totalMask;

    } else if (u_shapeMode == 4 || (u_shapeMode == 5 && mod(cellIndex, 3.0) >= 2.0)) {
        // Amorph mode: cross-block oval sampling to avoid square edges.
        float totalMask = 0.0;
        for (int dy = -1; dy <= 1; dy++) {
            for (int dx = -1; dx <= 1; dx++) {
                vec2 nCell = cell + vec2(float(dx), float(dy));
                if (nCell.x < 0.0 || nCell.x >= cols ||
                    nCell.y < 0.0 || nCell.y >= rows) continue;
                float nIdx = nCell.y * cols + nCell.x;
                float nRnd = hash1(nIdx * 37.0 + 13.0);
                float nThresh = min(pow(nRnd, 1.35), 1.0 - width);
                float nProg = 0.0;
                if (t > nThresh) {
                    nProg = clamp((t - nThresh) / max(1e-4, 1.0 - nThresh), 0.0, 1.0);
                }
                if (nProg <= 0.0) continue;
                vec2 nCenter = (nCell + vec2(0.5)) / grid;
                float nAngle = hash1(nIdx * 67.0 + 11.0) * 3.14159;
                float eccX = 0.6 + hash1(nIdx * 89.0 + 31.0) * 0.8;
                float eccY = 0.6 + hash1(nIdx * 97.0 + 41.0) * 0.8;
                vec2 toC = uv - nCenter;
                float cs2 = cos(nAngle); float sn2 = sin(nAngle);
                vec2 rot = vec2(toC.x * cs2 - toC.y * sn2,
                                toC.x * sn2 + toC.y * cs2);
                float oDist = length(rot * vec2(eccX, eccY) * min(cols, rows));
                float noise = hash2(nCell + rot * 3.0) * 0.12;
                oDist += noise;
                float oR = nProg * 0.9;
                float oFeather = 0.1;
                float oMask = 1.0 - smoothstep(oR - oFeather, oR + oFeather, oDist);
                totalMask = max(totalMask, oMask);
            }
        }
        blockMix = totalMask;

    } else if (u_shapeMode == 5) {
        // Random fallback bucket (lines) for remaining cells
        float lineDir = hash1(cellIndex * 71.0 + 3.0);
        float linePos = lineDir > 0.5 ? cellFrac.x : cellFrac.y;
        float sweepDir = hash1(cellIndex * 43.0 + 17.0);
        if (sweepDir > 0.5) linePos = 1.0 - linePos;
        float lineEdge = shapeProgress * 1.15;
        float lineMask = 1.0 - smoothstep(lineEdge - 0.12, lineEdge, linePos);
        blockMix = lineMask;
    }

    // Global tail for clean landing.
    float tail;
    if (u_shapeMode == 1) {
        tail = smoothstep(0.92, 1.0, t);
    } else if (u_shapeMode == 4 || u_shapeMode == 5) {
        tail = smoothstep(0.88, 1.0, t);
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
