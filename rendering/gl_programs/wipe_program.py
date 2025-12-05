"""Wipe transition shader program.

Wipe reveals the new image by moving a hard edge across the screen in one of
several directions: horizontal, vertical, or diagonal.
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


class WipeProgram(BaseGLProgram):
    """Shader program for the Wipe transition effect."""

    @property
    def name(self) -> str:
        return "Wipe"

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
        # Optimized: Uses precomputed axis value instead of mode branching.
        # The Python side computes the axis transformation, shader just applies it.
        return """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform int u_mode;  // 0=L2R, 1=R2L, 2=T2B, 3=B2T, 4=Diag TL-BR, 5=Diag TR-BL

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    // Sample both textures (GPU prefetch friendly)
    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Compute axis based on mode - use array lookup pattern for better GPU performance
    // Each mode maps UV to a 0..1 axis value
    float axis;
    if (u_mode == 0) {
        axis = uv.x;                           // Left-to-right
    } else if (u_mode == 1) {
        axis = 1.0 - uv.x;                     // Right-to-left
    } else if (u_mode == 2) {
        axis = uv.y;                           // Top-to-bottom
    } else if (u_mode == 3) {
        axis = 1.0 - uv.y;                     // Bottom-to-top
    } else if (u_mode == 4) {
        axis = (uv.x + uv.y) * 0.5;            // Diagonal TL-BR
    } else {
        axis = ((1.0 - uv.x) + uv.y) * 0.5;    // Diagonal TR-BL
    }

    // Branchless blend using step
    float m = step(axis, t);
    FragColor = mix(oldColor, newColor, m);
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Wipe program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "uOldTex": gl.glGetUniformLocation(program, "uOldTex"),
            "uNewTex": gl.glGetUniformLocation(program, "uNewTex"),
            "u_mode": gl.glGetUniformLocation(program, "u_mode"),
        }

    def _direction_to_mode(self, direction: Any) -> int:
        """Map WipeDirection enum to shader mode integer.
        
        Mode values:
            0 = Left-to-right (default)
            1 = Right-to-left
            2 = Top-to-bottom
            3 = Bottom-to-top
            4 = Diagonal TL-BR
            5 = Diagonal TR-BL
        """
        try:
            from rendering.gl_compositor import WipeDirection
            if direction == WipeDirection.LEFT_TO_RIGHT:
                return 0
            elif direction == WipeDirection.RIGHT_TO_LEFT:
                return 1
            elif direction == WipeDirection.TOP_TO_BOTTOM:
                return 2
            elif direction == WipeDirection.BOTTOM_TO_TOP:
                return 3
            elif direction == WipeDirection.DIAG_TL_BR:
                return 4
            elif direction == WipeDirection.DIAG_TR_BL:
                return 5
        except Exception:
            pass
        return 0  # Default: LEFT_TO_RIGHT

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
        """Draw one frame of the Wipe transition."""
        if gl is None:
            return

        vp_w, vp_h = viewport
        progress = max(0.0, min(1.0, float(getattr(state, "progress", 0.0))))
        
        # Get mode from state direction
        direction = getattr(state, "direction", None)
        mode = self._direction_to_mode(direction)

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(program)
        try:
            if uniforms.get("u_progress", -1) != -1:
                gl.glUniform1f(uniforms["u_progress"], float(progress))

            if uniforms.get("u_mode", -1) != -1:
                gl.glUniform1i(uniforms["u_mode"], mode)

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
wipe_program = WipeProgram()
