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
uniform int u_ripple_count;  // 1-8, default 3
uniform float u_ripple_seed;  // per-transition random seed for position variety

float hash1(float n) {
    return fract(sin(n) * 43758.5453123);
}

void main() {
    // Flip V to match Qt's top-left image origin.
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);
    float aspect = u_resolution.x / max(u_resolution.y, 1.0);
    int count = clamp(u_ripple_count, 1, 8);

    // Accumulate wave displacement and reveal mask across all ripple sources.
    float totalWave = 0.0;
    float bestLocalMix = 0.0;
    float bestRingMask = 0.0;

    for (int i = 0; i < 8; i++) {
        if (i >= count) break;

        // Per-ripple random centre (first ripple always from screen centre).
        vec2 center;
        float timeOffset;
        if (i == 0) {
            center = vec2(0.5, 0.5);
            timeOffset = 0.0;
        } else {
            float fi = float(i);
            float seed = u_ripple_seed;
            center = vec2(
                0.15 + hash1(fi * 73.0 + 7.0 + seed * 127.1) * 0.7,
                0.15 + hash1(fi * 91.0 + 13.0 + seed * 311.7) * 0.7
            );
            // Stagger start times so ripples don't all fire at once.
            timeOffset = hash1(fi * 37.0 + 3.0 + seed * 59.3) * 0.25;
        }

        vec2 centered = uv - center;
        centered.x *= aspect;
        float r = length(centered);
        float maxR = length(vec2(0.5 * aspect, 0.5));
        float rNorm = clamp(r / maxR, 0.0, 1.0);

        float localT = clamp((t - timeOffset) / max(1.0 - timeOffset, 0.01), 0.0, 1.0);
        float front = localT;

        // Radial wave.
        float wave = 0.0;
        if (rNorm < front + 0.25 && localT > 0.0) {
            float spatialFreq = 18.0;
            float temporalFreq = 4.0;
            float phase = spatialFreq * (rNorm - front) - temporalFreq * localT;
            float attenuation = exp(-6.0 * abs(rNorm - front));
            wave = 0.012 * sin(phase) * attenuation;
        }
        totalWave += wave;

        // Reveal mask.
        float localMix = smoothstep(-0.04, 0.18, front - rNorm);
        bestLocalMix = max(bestLocalMix, localMix);

        // Ring highlight.
        float ringMask = smoothstep(front - 0.03, front, rNorm) *
                         (1.0 - smoothstep(front, front + 0.03, rNorm));
        bestRingMask = max(bestRingMask, ringMask);
    }

    // Displace sampling position.
    vec2 centered0 = uv - vec2(0.5, 0.5);
    centered0.x *= aspect;
    float r0 = length(centered0);
    vec2 dir = (r0 > 1e-5) ? (centered0 / r0) : vec2(0.0, 0.0);
    vec2 rippleUv = uv + dir * totalWave;
    rippleUv = clamp(rippleUv, vec2(0.0), vec2(1.0));
    vec4 rippleOld = texture(uOldTex, rippleUv);

    vec4 base = mix(oldColor, rippleOld, 0.7);

    float globalMix = smoothstep(0.78, 0.95, t);
    float newMix = clamp(max(bestLocalMix, globalMix), 0.0, 1.0);

    vec4 mixed = mix(base, newColor, newMix);
    mixed.rgb += vec3(0.08) * bestRingMask;

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
            "u_ripple_count": gl.glGetUniformLocation(program, "u_ripple_count"),
            "u_ripple_seed": gl.glGetUniformLocation(program, "u_ripple_seed"),
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

        ripple_count = int(getattr(state, "ripple_count", 3))

        gl.glUseProgram(program)
        try:
            if uniforms.get("u_progress", -1) != -1:
                gl.glUniform1f(uniforms["u_progress"], float(progress))

            if uniforms.get("u_resolution", -1) != -1:
                gl.glUniform2f(uniforms["u_resolution"], float(vp_w), float(vp_h))

            if uniforms.get("u_ripple_count", -1) != -1:
                gl.glUniform1i(uniforms["u_ripple_count"], ripple_count)

            if uniforms.get("u_ripple_seed", -1) != -1:
                seed = float(getattr(state, "ripple_seed", 0.0))
                gl.glUniform1f(uniforms["u_ripple_seed"], seed)

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
