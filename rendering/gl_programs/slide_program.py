"""Slide transition shader program.

Slide moves the old image out while the new image slides in from the opposite
direction. The shader uses rect uniforms to position both images.
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


class SlideProgram(BaseGLProgram):
    """Shader program for the Slide transition effect."""

    @property
    def name(self) -> str:
        return "Slide"

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
        # Optimized: Uses branchless bounds checking with step() for better GPU performance.
        # This eliminates thread divergence from if-statements.
        return """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec4 u_oldRect; // xy = pos, zw = size, in normalised viewport coords
uniform vec4 u_newRect; // xy = pos, zw = size, in normalised viewport coords

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    // Compute rect bounds
    vec2 oldMin = u_oldRect.xy;
    vec2 oldMax = u_oldRect.xy + u_oldRect.zw;
    vec2 newMin = u_newRect.xy;
    vec2 newMax = u_newRect.xy + u_newRect.zw;

    // Branchless bounds checking using step()
    // inOld = 1.0 if uv is inside old rect, 0.0 otherwise
    float inOld = step(oldMin.x, uv.x) * step(uv.x, oldMax.x) *
                  step(oldMin.y, uv.y) * step(uv.y, oldMax.y);
    
    // inNew = 1.0 if uv is inside new rect, 0.0 otherwise
    float inNew = step(newMin.x, uv.x) * step(uv.x, newMax.x) *
                  step(newMin.y, uv.y) * step(uv.y, newMax.y);

    // Compute texture coordinates (safe division)
    vec2 oldSpan = max(u_oldRect.zw, vec2(1e-5));
    vec2 newSpan = max(u_newRect.zw, vec2(1e-5));
    vec2 oldLocal = (uv - oldMin) / oldSpan;
    vec2 newLocal = (uv - newMin) / newSpan;

    // Sample textures (GPU prefetch friendly - always sample both)
    vec4 oldColor = texture(uOldTex, oldLocal);
    vec4 newColor = texture(uNewTex, newLocal);

    // Start with black background
    vec4 color = vec4(0.0, 0.0, 0.0, 1.0);
    
    // Layer old image where visible
    color = mix(color, oldColor, inOld);
    
    // Layer new image on top where visible (new always wins in overlap)
    color = mix(color, newColor, inNew);

    FragColor = color;
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Slide program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "uOldTex": gl.glGetUniformLocation(program, "uOldTex"),
            "uNewTex": gl.glGetUniformLocation(program, "uNewTex"),
            "u_oldRect": gl.glGetUniformLocation(program, "u_oldRect"),
            "u_newRect": gl.glGetUniformLocation(program, "u_newRect"),
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
        old_rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
        new_rect: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0),
    ) -> None:
        """Draw one frame of the Slide transition.
        
        Args:
            old_rect: (x, y, w, h) in normalized viewport coords for old image
            new_rect: (x, y, w, h) in normalized viewport coords for new image
        """
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

            if uniforms.get("u_oldRect", -1) != -1:
                gl.glUniform4f(uniforms["u_oldRect"], *old_rect)

            if uniforms.get("u_newRect", -1) != -1:
                gl.glUniform4f(uniforms["u_newRect"], *new_rect)

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
slide_program = SlideProgram()
