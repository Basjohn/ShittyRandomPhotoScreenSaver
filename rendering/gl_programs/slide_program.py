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
        return """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform vec2 u_resolution;
uniform vec4 u_oldRect; // xy = pos, zw = size, in normalised viewport coords
uniform vec4 u_newRect; // xy = pos, zw = size, in normalised viewport coords

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    // Start from a black background; old and new images layer on top.
    vec4 color = vec4(0.0, 0.0, 0.0, 1.0);

    // OLD image contribution.
    vec2 oldMin = u_oldRect.xy;
    vec2 oldMax = u_oldRect.xy + u_oldRect.zw;
    if (uv.x >= oldMin.x && uv.x <= oldMax.x && uv.y >= oldMin.y && uv.y <= oldMax.y) {
        vec2 span = max(u_oldRect.zw, vec2(1e-5));
        vec2 local = (uv - oldMin) / span;
        color = texture(uOldTex, local);
    }

    // NEW image overlays OLD where they overlap, mirroring the QPainter
    // behaviour where the new pixmap is drawn last.
    vec2 newMin = u_newRect.xy;
    vec2 newMax = u_newRect.xy + u_newRect.zw;
    if (uv.x >= newMin.x && uv.x <= newMax.x && uv.y >= newMin.y && uv.y <= newMax.y) {
        vec2 span = max(u_newRect.zw, vec2(1e-5));
        vec2 local = (uv - newMin) / span;
        vec4 newColor = texture(uNewTex, local);
        color = newColor;
    }

    FragColor = color;
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Slide program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "u_resolution": gl.glGetUniformLocation(program, "u_resolution"),
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

            if uniforms.get("u_resolution", -1) != -1:
                gl.glUniform2f(uniforms["u_resolution"], float(vp_w), float(vp_h))

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
