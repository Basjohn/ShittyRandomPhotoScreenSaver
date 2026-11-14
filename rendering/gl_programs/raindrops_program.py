"""Raindrops transition shader program.

Raindrops creates a water ripple effect that expands from the centre,
revealing the new image as the wave passes.
"""

from __future__ import annotations

from rendering.gl_programs.base_program import BaseGLProgram


class RaindropsProgram(BaseGLProgram):
    """Shader program for the Raindrops/Ripple transition effect."""

    @property
    def name(self) -> str:
        return "Raindrops"

    @property
    def vertex_source(self) -> str:
        return """#version 460 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;

layout(location = 0) out vec2 vUv;

void main() {
    vUv = aUv;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

    @property
    def fragment_source(self) -> str:
        return """#version 460 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(binding = 0) uniform sampler2D uOldTex;
layout(binding = 1) uniform sampler2D uNewTex;
// The pass block (N1.6): the item quad's values and this program's, one std140 block at the pass-block binding
// (SCENE3D_PASS_BLOCK_BINDING); the quad's vertex stage declares the same block (quick/transitions/fullscreen_pass).
layout(std140, binding = 18) uniform RipplePass {
    mat4 uMatrix;
    vec2 uItemSize;
    float u_progress;
    vec2 u_resolution;
    int u_ripple_count;  // 1-8, default 3
    float u_ripple_seed;  // per-transition random seed for position variety
};

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

        // Reveal mask. Each ripple's reveal and ring ramp in over its first moments: at its start
        // the front sits at the centre, where the mask would otherwise already show ~8% of the
        // new picture and a ring on the very first frame (a visible start pop).
        float start = smoothstep(0.0, 0.03, localT);
        float localMix = start * smoothstep(-0.04, 0.18, front - rNorm);
        bestLocalMix = max(bestLocalMix, localMix);

        // Ring highlight.
        float ringMask = start * smoothstep(front - 0.03, front, rNorm) *
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
    float ringIntensity = (1.0 - newMix) * bestRingMask;
    mixed.rgb += vec3(0.08) * ringIntensity;

    FragColor = mixed;
}
"""


# Singleton instance for convenience
raindrops_program = RaindropsProgram()
