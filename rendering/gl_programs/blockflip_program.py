"""BlockFlip transition shader program.

BlockFlip is implemented as a fullscreen-quad shader that renders a grid of
blocks, each flipping from the old image to the new image in a directional
wave pattern. The wave travels from a leading edge (based on SlideDirection)
with a center-biased curve and per-block jitter for organic feel.
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


class BlockFlipProgram(BaseGLProgram):
    """Shader program for the BlockFlip transition effect."""

    @property
    def name(self) -> str:
        return "BlockFlip"

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
uniform vec2 u_direction;   // slide direction, cardinal

float hash1(float n) {
    return fract(sin(n) * 43758.5453123);
}

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    if (t <= 0.0) {
        FragColor = oldColor;
        return;
    }
    if (t >= 1.0) {
        FragColor = newColor;
        return;
    }

    // Logical block grid in UV space.
    vec2 grid = max(u_grid, vec2(1.0));
    vec2 cell = clamp(floor(uv * grid), vec2(0.0), grid - vec2(1.0));
    float cols = grid.x;
    float rows = grid.y;
    float cellIndex = cell.y * cols + cell.x;

    vec2 cellOrigin = cell / grid;
    vec2 cellSize = vec2(1.0) / grid;
    vec2 uvLocal = (uv - cellOrigin) / cellSize; // 0..1 inside block

    // Direction-aware wave based on the *block* row/column, mirroring the
    // legacy BlockPuzzleFlip controller. This determines when each block
    // begins its flip relative to the chosen edge.
    vec2 dir = u_direction;
    if (length(dir) < 1e-3) {
        dir = vec2(1.0, 0.0);
    } else {
        dir = normalize(dir);
    }

    float colIndex = cell.x;
    float rowIndex = cell.y;
    bool horizontal = abs(dir.x) >= abs(dir.y);

    // Base start timing from the leading edge, matching the CPU
    // BlockPuzzleFlip controller.
    float base = 0.0;
    if (horizontal) {
        // LEFT/RIGHT: wave travels across columns.
        if (dir.x > 0.0) {
            // SlideDirection.LEFT semantics: left→right.
            if (cols > 1.0) {
                base = colIndex / (cols - 1.0);
            }
        } else {
            // SlideDirection.RIGHT semantics: right→left.
            if (cols > 1.0) {
                base = (cols - 1.0 - colIndex) / (cols - 1.0);
            }
        }
    } else {
        // UP/DOWN: wave travels across rows.
        if (dir.y > 0.0) {
            // SlideDirection.DOWN: top→bottom.
            if (rows > 1.0) {
                base = rowIndex / (rows - 1.0);
            }
        } else {
            // SlideDirection.UP: bottom→top.
            if (rows > 1.0) {
                base = (rows - 1.0 - rowIndex) / (rows - 1.0);
            }
        }
    }

    // Center bias: blocks nearer the center of the orthogonal axis begin
    // slightly earlier so the wavefront forms a shallow arrow/curve shape
    // rather than a perfectly straight slit.
    float colNorm = (cols > 1.0) ? colIndex / (cols - 1.0) : 0.5;
    float rowNorm = (rows > 1.0) ? rowIndex / (rows - 1.0) : 0.5;
    float ortho = horizontal ? abs(rowNorm - 0.5) : abs(colNorm - 0.5);
    float centerFactor = (0.5 - ortho) * 2.0; // 1 at center, 0 at edges.
    // Use a slightly stronger bias for vertical waves (fewer rows) so the
    // centre band feels more pronounced, while keeping horizontal behaviour
    // close to the original Block Puzzle Flip look.
    float centerBiasStrength = horizontal ? 0.25 : 0.32;
    base -= centerFactor * centerBiasStrength;
    base = clamp(base, 0.0, 1.0);

    // Small jitter so neighbouring blocks do not all start at exactly the
    // same moment; scaled by grid density so the wavefront remains coherent.
    float span = max(cols, rows);
    float jitterBase = horizontal ? 0.18 : 0.10;
    float jitterSpan = span > 0.0 ? jitterBase / span : 0.0;
    if (jitterSpan > 0.0) {
        base += (hash1(cellIndex * 91.0 + 7.0) - 0.5) * jitterSpan;
    }
    base = clamp(base, 0.0, 1.0);

    float start = clamp(base * 0.9, 0.0, 1.0 - 0.25);
    float end = start + 0.25;

    float local = 0.0;
    if (t >= start) {
        float span = max(end - start, 1e-4);
        local = clamp((t - start) / span, 0.0, 1.0);
    }

    // Cosine-based easing for the apparent flip, mirroring the legacy
    // BlockPuzzleFlip controller: eased in [0, 1] drives the width of a
    // hard-edged central band within each block.
    float eased = 0.5 - 0.5 * cos(local * 3.14159265);

    // Width of the revealed band within this block.
    float w = clamp(eased, 0.0, 1.0);
    float half = 0.5 * w;
    float left = 0.5 - half;
    float right = 0.5 + half;

    // Choose local axis according to the flip direction. For horizontal
    // flips use X inside the block; for vertical flips use Y.
    float coord = horizontal ? uvLocal.x : uvLocal.y;

    // Hard-edged band: pixels inside the band are fully new image, outside
    // are fully old image. No spatial feathering.
    float inBand = step(left, coord) * step(coord, right);

    // Late global tail so any remaining stragglers land cleanly on new even
    // if numerical jitter leaves tiny gaps.
    float tail = smoothstep(0.92, 1.0, t);
    float useNew = clamp(max(inBand, tail), 0.0, 1.0);
    float useOld = 1.0 - useNew;

    vec4 color = oldColor * useOld + newColor * useNew;
    FragColor = color;
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the BlockFlip program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "u_resolution": gl.glGetUniformLocation(program, "u_resolution"),
            "uOldTex": gl.glGetUniformLocation(program, "uOldTex"),
            "uNewTex": gl.glGetUniformLocation(program, "uNewTex"),
            "u_grid": gl.glGetUniformLocation(program, "u_grid"),
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
        """Draw one frame of the BlockFlip transition.
        
        Args:
            program: GL program ID
            uniforms: Dict of uniform locations from cache_uniforms()
            viewport: (width, height) of the viewport
            old_tex: GL texture ID for old image
            new_tex: GL texture ID for new image
            state: BlockFlipState dataclass with progress, cols, rows, direction
            quad_vao: VAO for fullscreen quad
        """
        if gl is None:
            return

        vp_w, vp_h = viewport
        progress = max(0.0, min(1.0, float(getattr(state, "progress", 0.0))))

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(program)
        try:
            # Set progress uniform
            if uniforms.get("u_progress", -1) != -1:
                gl.glUniform1f(uniforms["u_progress"], float(progress))

            # Set resolution uniform
            if uniforms.get("u_resolution", -1) != -1:
                gl.glUniform2f(uniforms["u_resolution"], float(vp_w), float(vp_h))

            # Set grid uniform
            if uniforms.get("u_grid", -1) != -1:
                float_cols = float(max(1, int(getattr(state, "cols", 1))))
                float_rows = float(max(1, int(getattr(state, "rows", 1))))
                gl.glUniform2f(uniforms["u_grid"], float_cols, float_rows)

            # Map direction to travel vector
            dx, dy = self._get_direction_vector(state)
            if uniforms.get("u_direction", -1) != -1:
                gl.glUniform2f(uniforms["u_direction"], float(dx), float(dy))

            # Bind old texture to unit 0
            if uniforms.get("uOldTex", -1) != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, old_tex)
                gl.glUniform1i(uniforms["uOldTex"], 0)

            # Bind new texture to unit 1
            if uniforms.get("uNewTex", -1) != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, new_tex)
                gl.glUniform1i(uniforms["uNewTex"], 1)

            # Draw fullscreen quad
            self._draw_fullscreen_quad(quad_vao)

        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)

    def _get_direction_vector(self, state: Any) -> Tuple[float, float]:
        """Map SlideDirection to a cardinal direction vector.
        
        LEFT maps to (1, 0) for left-to-right wave.
        RIGHT maps to (-1, 0) for right-to-left wave.
        DOWN maps to (0, 1) for top-to-bottom wave.
        UP maps to (0, -1) for bottom-to-top wave.
        """
        try:
            direction = getattr(state, "direction", None)
            if direction is None:
                return (1.0, 0.0)
            
            # Import here to avoid circular imports
            from transitions.slide_transition import SlideDirection
            
            if direction == SlideDirection.LEFT:
                return (1.0, 0.0)
            elif direction == SlideDirection.RIGHT:
                return (-1.0, 0.0)
            elif direction == SlideDirection.DOWN:
                return (0.0, 1.0)
            elif direction == SlideDirection.UP:
                return (0.0, -1.0)
        except Exception as e:
            logger.debug("[MISC] Exception suppressed: %s", e)
        return (1.0, 0.0)


# Singleton instance for convenience
blockflip_program = BlockFlipProgram()
