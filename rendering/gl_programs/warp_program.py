"""Warp Dissolve transition shader program.

Warp Dissolve creates a vortex effect that swirls both images together,
with the new image gradually emerging from the centre outward.
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


class WarpProgram(BaseGLProgram):
    """Shader program for the Warp Dissolve transition effect."""

    @property
    def name(self) -> str:
        return "Warp"

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

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 newColor = texture(uNewTex, uv);
    vec4 oldColor = texture(uOldTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Normalised, aspect-corrected coordinates around the image centre.
    float aspect = u_resolution.x / max(u_resolution.y, 1.0);
    vec2 centered = uv - vec2(0.5, 0.5);
    centered.x *= aspect;

    float r = length(centered);
    float maxR = length(vec2(0.5 * aspect, 0.5));
    float rNorm = clamp(r / maxR, 0.0, 1.0);

    // Angle in polar space.
    float theta = atan(centered.y, centered.x);

    // Strong vortex: peak twist at t=0.5 and near the centre. Allow up to
    // ~1.65 turns at the core so the motion clearly reads as a whirlpool.
    float swirlPhase = sin(t * 3.14159265);          // 0 at 0/1, 1 at 0.5
    float swirlStrength = 3.3 * 3.14159265;          // ~10% stronger than 1.5
    float radialFalloff = (1.0 - rNorm);
    radialFalloff *= radialFalloff;                  // bias towards centre
    // Suppress twist in a thin border near the outer edge to avoid visible
    // bending of the very top/left edges on wide aspect ratios.
    float edgeMask = 1.0 - smoothstep(0.94, 1.0, rNorm);
    radialFalloff *= edgeMask;
    float swirl = swirlPhase * swirlStrength * radialFalloff;

    // Shared swirl field that gradually unwinds as we approach the end of the
    // transition so the new image relaxes back to its original orientation.
    float unwhirl = smoothstep(0.6, 1.0, t);
    float sharedSwirl = swirl * (1.0 - 0.75 * unwhirl);

    // OLD image - fully participates in the vortex.
    float thetaOld = theta + sharedSwirl;
    float rOld = r * (1.0 - 0.45 * t * (1.0 - rNorm));
    vec2 dirOld = vec2(cos(thetaOld), sin(thetaOld));
    dirOld.x /= aspect;
    vec2 uvOld = vec2(0.5, 0.5) + dirOld * rOld;
    uvOld = clamp(uvOld, vec2(0.0), vec2(1.0));
    vec4 warpedOld = texture(uOldTex, uvOld);

    // NEW image - equally twisted into the same vortex, then gently unwound as
    // we approach t=1 so the final frame is stable. Retain a mild zoom-in
    // early on but guarantee that we land exactly on the original framing
    // once the unwhirl phase has completed.
    float thetaNew = theta + sharedSwirl;
    float zoomPhase = 0.85 + 0.25 * t;
    float zoom = mix(zoomPhase, 1.0, unwhirl);
    float rNew = r * zoom;
    vec2 dirNew = vec2(cos(thetaNew), sin(thetaNew));
    dirNew.x /= aspect;
    vec2 uvNew = vec2(0.5, 0.5) + dirNew * rNew;
    uvNew = clamp(uvNew, vec2(0.0), vec2(1.0));
    vec4 warpedNew = texture(uNewTex, uvNew);

    // Mixing: fade into a shared vortex, then unwhirl to the final frame.
    //  - Centre reveals first once the vortex has formed
    //  - Outer ring follows a bit later
    //  - Global tail guarantees a clean landing on the new image
    // Slightly earlier phases (~10%) so the dissolve feels a bit snappier.
    float centrePhase = smoothstep(0.16, 0.41, t) * (1.0 - rNorm);
    float ringPhase = smoothstep(0.27, 0.63, t) * smoothstep(0.15, 1.0, rNorm);
    float tailPhase = smoothstep(0.72, 0.94, t);
    float mixFactor = clamp(max(max(centrePhase, ringPhase), tailPhase), 0.0, 1.0);

    vec4 color = mix(warpedOld, warpedNew, mixFactor);

    FragColor = color;
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Warp program."""
        if gl is None:
            return {}
        return {
            "u_progress": gl.glGetUniformLocation(program, "u_progress"),
            "u_resolution": gl.glGetUniformLocation(program, "u_resolution"),
            "uOldTex": gl.glGetUniformLocation(program, "uOldTex"),
            "uNewTex": gl.glGetUniformLocation(program, "uNewTex"),
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
        """Draw one frame of the Warp Dissolve transition."""
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
warp_program = WarpProgram()
