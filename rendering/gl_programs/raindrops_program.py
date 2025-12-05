"""Raindrops transition shader program.

Raindrops creates a water ripple effect that expands from the centre,
revealing the new image as the wave passes.
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


class RaindropsProgram(BaseGLProgram):
    """Shader program for the Raindrops/Ripple transition effect."""

    @property
    def name(self) -> str:
        return "Raindrops"

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

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);

    // Normalised coordinates with aspect compensation so the ripple is
    // circular even on non-square render targets.
    float aspect = u_resolution.x / max(u_resolution.y, 1.0);
    vec2 centered = uv - vec2(0.5, 0.5);
    centered.x *= aspect;
    float r = length(centered);

    // Use the true maximum radius from the centre to the furthest corner so
    // the ripple cleanly reaches the image corners without leaving a thin
    // untransitioned band.
    float maxR = length(vec2(0.5 * aspect, 0.5));
    float rNorm = clamp(r / maxR, 0.0, 1.0);
    float front = t;

    // Radial wave travelling outwards from the centre. Lower spatial and
    // temporal frequency to avoid judder.
    float wave = 0.0;
    if (rNorm < front + 0.25) {
        float spatialFreq = 18.0;
        float temporalFreq = 4.0;
        float phase = spatialFreq * (rNorm - front) - temporalFreq * t;
        float attenuation = exp(-6.0 * abs(rNorm - front));
        wave = 0.012 * sin(phase) * attenuation;
    }

    vec2 dir = (r > 1e-5) ? (centered / r) : vec2(0.0, 0.0);

    // Displace the sampling position along the radial direction to create
    // a water-like refraction of the old image.
    vec2 rippleUv = uv + dir * wave;
    rippleUv = clamp(rippleUv, vec2(0.0), vec2(1.0));
    vec4 rippleOld = texture(uOldTex, rippleUv);

    vec4 base = mix(oldColor, rippleOld, 0.7);

    // Reveal the NEW image from the centre outward. Points that the wave
    // front has already passed transition to the new image, and a gentle
    // global fade near the end guarantees we finish fully on the new frame.
    float localMix = smoothstep(-0.04, 0.18, front - rNorm);
    float globalMix = smoothstep(0.78, 0.95, t);
    float newMix = clamp(max(localMix, globalMix), 0.0, 1.0);

    vec4 mixed = mix(base, newColor, newMix);

    // Subtle highlight on the main ring to read as a bright water crest.
    float ringMask = smoothstep(front - 0.03, front, rNorm) *
                     (1.0 - smoothstep(front, front + 0.03, rNorm));
    mixed.rgb += vec3(0.08) * ringMask;

    FragColor = mixed;
}
"""

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        """Cache uniform locations for the Raindrops program."""
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
        """Draw one frame of the Raindrops transition."""
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
raindrops_program = RaindropsProgram()
