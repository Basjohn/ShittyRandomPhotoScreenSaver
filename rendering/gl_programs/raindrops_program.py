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
    vec2 u_target_px;   // the target's pixels (the viewport; the native core fills it by this name, N4.a)
    int u_ripple_count;  // 1-8, default 3
    float u_ripple_seed;  // per-transition random seed for position variety
};

// Integer hash (R-94's class; N5.2a): the ripple's index, a salt and the seed's bits, exact on every GPU, compiler and
// backend (a float fract(sin()) hash of a seed-scaled argument compiles to different values through SPIR-V).
uint rippleMix(uint x) {
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}
float rippleRandom(uint index, uint salt) {
    uint seed = floatBitsToUint(u_ripple_seed);
    return float(rippleMix(index * 0x9e3779b9u ^ rippleMix(seed * 0x85ebca6bu + salt))) * (1.0 / 4294967295.0);
}

void main() {
    // The pixel's own uv (N5.2a): the interpolated vUv differs in its last bits between renderers and backends; the
    // pixel's centre over the target's pixels does not. V flipped to match Qt's top-left image origin.
    vec2 pixelUv = (floor(vUv * u_target_px) + 0.5) / u_target_px;
    vec2 uv = vec2(pixelUv.x, 1.0 - pixelUv.y);

    vec4 oldColor = texture(uOldTex, uv);
    vec4 newColor = texture(uNewTex, uv);

    float t = clamp(u_progress, 0.0, 1.0);
    float aspect = u_target_px.x / max(u_target_px.y, 1.0);
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
            uint index = uint(i);
            center = vec2(
                0.15 + rippleRandom(index, 1u) * 0.7,
                0.15 + rippleRandom(index, 2u) * 0.7
            );
            // Stagger start times so ripples don't all fire at once.
            timeOffset = rippleRandom(index, 3u) * 0.25;
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
