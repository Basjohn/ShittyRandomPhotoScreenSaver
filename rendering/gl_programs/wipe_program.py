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
        return """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_resolution;
uniform int u_mode;   // 0=L2R,1=R2L,2=T2B,3=B2T,4=Diag TL-BR,5=Diag TR-BL

void main() {
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

    // Compute a scalar axis in [0,1] that the wipe front travels along.
    float axis = 0.0;

    if (u_mode == 0) {
        // Left-to-right
        axis = uv.x;
    } else if (u_mode == 1) {
        // Right-to-left
        axis = 1.0 - uv.x;
    } else if (u_mode == 2) {
        // Top-to-bottom
        axis = uv.y;
    } else if (u_mode == 3) {
        // Bottom-to-top
        axis = 1.0 - uv.y;
    } else if (u_mode == 4) {
        // Diagonal TL-BR: project onto (1,1) and normalise back to 0..1.
        float proj = (uv.x + uv.y) * 0.5;
        axis = clamp(proj, 0.0, 1.0);
    } else if (u_mode == 5) {
        // Diagonal TR-BL: project onto (-1,1).
        float proj = ((1.0 - uv.x) + uv.y) * 0.5;
        axis = clamp(proj, 0.0, 1.0);
    }

    float m = step(axis, t);

    vec4 color = mix(oldColor, newColor, m);
    FragColor = color;
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Wipe program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "u_resolution": gl.glGetUniformLocation(program, "u_resolution"),
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
            # Import here to avoid circular imports
            from rendering.gl_compositor import WipeDirection
            if direction == WipeDirection.RIGHT_TO_LEFT:
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
        
        # Get mode from state - either pre-computed or from direction enum
        mode = getattr(state, "mode", None)
        if mode is None:
            direction = getattr(state, "direction", None)
            mode = self._direction_to_mode(direction) if direction else 0
        else:
            mode = int(mode)

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)

        gl.glUseProgram(program)
        try:
            if uniforms.get("u_progress", -1) != -1:
                gl.glUniform1f(uniforms["u_progress"], float(progress))

            if uniforms.get("u_resolution", -1) != -1:
                gl.glUniform2f(uniforms["u_resolution"], float(vp_w), float(vp_h))

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
