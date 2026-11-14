#version 440
// Probe Rings, pass "glow" (blend add): a soft light at the centre that follows the level (native/core/python/
// probe_rings; mode_content.h). Its blocks are its own: the settings and record fields it reads.
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 1) uniform ModeSettings {
    vec2 u_target_px;
    float u_glow;
    float u_fade;
};

layout(std140, binding = 2) uniform ModeFrame {
    float level;
    float time;
    vec4 pulse_color;
};

void main() {
    vec2 p = fragPixel(u_target_px);
    float unit = 0.5 * min(u_target_px.x, u_target_px.y);
    float d = length(p - 0.5 * u_target_px) / unit;
    float pulse = 0.85 + 0.15 * sin(mod(time, 60.0) * 6.0);
    float g = u_glow * level * pulse * exp(-3.0 * d * d);
    fragColor = vec4(pulse_color.rgb, clamp(g, 0.0, 1.0) * u_fade);
}
