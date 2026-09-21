"""Bounded directional melt with rounded analytic drips."""

from __future__ import annotations


MELT_DRIP_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform float u_seed;
uniform float u_detail;
uniform vec2 u_direction;

float hash11(float p) { return fract(sin(p * 127.1) * 43758.5453123); }
float roundedDrips(float sideways, float seed, float detail) {
    float cells = 9.0 * detail;
    float cell = floor(sideways * cells);
    float local = fract(sideways * cells) - 0.5;
    float width = 0.16 + 0.26 * hash11(cell + seed);
    float depth = 0.06 + 0.19 * hash11(cell * 2.3 + seed);
    return depth * (1.0 - smoothstep(width * 0.42, width, abs(local)));
}
void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);
    if (t <= 0.0) { FragColor = texture(uOldTex, uv); return; }
    if (t >= 1.0) { FragColor = texture(uNewTex, uv); return; }
    float along = dot(uv - 0.5, u_direction) + 0.5;
    float sideways = dot(uv, vec2(-u_direction.y, u_direction.x));
    float envelope = sin(3.141592653589793 * t);
    envelope *= envelope;
    // Negative insets leave heavier source strands below the advancing front.
    float dripInset = -roundedDrips(sideways, u_seed, u_detail) * envelope;
    float front = -0.025 + 1.25 * t + dripInset;
    float destination = 1.0 - smoothstep(front - 0.018, front + 0.018, along);
    // Gravity-direction UV elongation pulls the surviving source into each drip.
    float stretch = (1.0 - destination) * envelope * (0.025 + 0.085 * t)
        * (0.5 - dripInset * 4.0);
    vec2 sourceUv = clamp(uv - u_direction * stretch, 0.0, 1.0);
    FragColor = mix(texture(uOldTex, sourceUv), texture(uNewTex, uv), destination);
}
"""
