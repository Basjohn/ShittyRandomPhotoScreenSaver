"""Bounded connected wet-ink reveal shader."""

from __future__ import annotations


INK_BLOOM_FRAGMENT_SOURCE = """#version 410 core
in vec2 vUv;
out vec4 FragColor;
uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform float u_seed;
uniform float u_detail;

float hash21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123); }
float inkNoise(vec2 p) {
    vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
    return mix(mix(hash21(i), hash21(i+vec2(1,0)), f.x),
               mix(hash21(i+vec2(0,1)), hash21(i+vec2(1,1)), f.x), f.y);
}
float bloomField(vec2 uv, float seed, float detail) {
    vec2 p = uv - 0.5;
    vec2 domain = uv * detail;
    vec2 warp = vec2(
        inkNoise(domain * 5.0 + vec2(seed, 17.0)),
        inkNoise(domain * 5.0 + vec2(31.0, seed))
    ) - 0.5;
    domain += warp * 0.16;
    p = domain / detail - 0.5;
    float field = length(p) - 0.092;
    // The centres overlap the core, creating one connected pigment front.
    for (int i = 0; i < 6; ++i) {
        float fi = float(i);
        float angle = 6.28318530718 * (hash21(vec2(seed, fi)) + fi / 6.0);
        vec2 centre = vec2(cos(angle), sin(angle)) * (0.09 + 0.055 * hash21(vec2(fi, seed)));
        field = min(field, length(p - centre) - (0.102 + 0.034 * hash21(centre + seed)));
    }
    float coarse = inkNoise(domain * 8.0 + seed) - 0.5;
    float fine = inkNoise(domain * 21.0 + vec2(seed, 53.0)) - 0.5;
    return field + (coarse * 0.045 + fine * 0.018) / detail;
}
void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);
    if (t <= 0.0) { FragColor = texture(uOldTex, uv); return; }
    if (t >= 1.0) { FragColor = texture(uNewTex, uv); return; }
    // Starts below the smallest connected core and reaches outer corners only
    // late in the run, avoiding both an opening pop and a generic early blob.
    float front = -0.19 + 1.05 * pow(t, 1.65);
    float field = bloomField(uv, u_seed, u_detail);
    float aa=max(fwidth(field)*1.1,.0007);
    float revealed = 1.0 - smoothstep(front-aa,front+aa,field);
    float wetEdge = exp(-115.0 * abs(field - front));
    vec4 colour = mix(texture(uOldTex, uv), texture(uNewTex, uv), revealed);
    colour.rgb *= 1.0-.13*wetEdge*revealed;
    colour.rgb += wetEdge * (1.0 - revealed) * vec3(0.045, 0.022, 0.065);
    FragColor = colour;
}
"""
