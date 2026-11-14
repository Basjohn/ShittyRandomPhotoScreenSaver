#version 440
// Probe Rings, pass "glow" (blend add): a soft light at the centre that follows the level (native/core/python/
// probe_rings; mode_content.h), in the product 2D shaders' shape: v_uv from the core's triangle (the light is radially
// symmetric, so v_uv's row orientation, the backend's clip space, never shows) and one block of its own.
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 18) uniform ProbeRingsDraw {
    vec2 u_target_px;    // core
    float u_fade;        // core
    float u_glow;        // setting
    float level;         // record
    float time;          // record
    vec4 pulse_color;    // record
};

void main() {
    float unit = 0.5 * min(u_target_px.x, u_target_px.y);
    float d = length((v_uv - 0.5) * u_target_px) / unit;
    float pulse = 0.85 + 0.15 * sin(mod(time, 60.0) * 6.0);
    float g = u_glow * level * pulse * exp(-3.0 * d * d);
    fragColor = vec4(pulse_color.rgb, clamp(g, 0.0, 1.0) * u_fade);
}
