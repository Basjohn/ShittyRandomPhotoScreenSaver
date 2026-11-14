#version 440
// Probe Rings, pass "rings" (blend alpha): the harness-only mode of N2.9 (native/core/python/probe_rings), in the
// product 2D shaders' shape (mode_content.h): one block of its own filled by name from the core's conventions
// (u_target_px, u_fade), the settings (u_ring_color, u_thickness_px) and the record (rings, ring_alpha, ring_count,
// pulse_color); the target's pixel from fragPixel (the conventions include, spliced at the marker by the baker).
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 18) uniform ProbeRingsDraw {
    vec2 u_target_px;    // core: the surface's pixels
    float u_fade;        // core: the card's content fade
    vec4 u_ring_color;   // setting: the spec's colour, 0..1
    float u_thickness_px;// setting
    float rings[8];      // record: radii, in half the card's shorter side
    float ring_alpha[8]; // record
    int ring_count;      // record
    vec4 pulse_color;    // record
};

void main() {
    vec2 p = fragPixel(u_target_px);
    float unit = 0.5 * min(u_target_px.x, u_target_px.y);
    float d = length(p - 0.5 * u_target_px);
    float half_width = 0.5 * u_thickness_px;
    float a = 0.0;
    for (int i = 0; i < 8; ++i) {
        if (i >= ring_count)
            break;
        float k = 1.0 - smoothstep(half_width, half_width + 1.0, abs(d - rings[i] * unit));
        a = max(a, k * ring_alpha[i]);
    }
    vec3 rgb = mix(u_ring_color.rgb, pulse_color.rgb, 0.35);
    //@colour
    fragColor = vec4(rgb, a * u_ring_color.a * u_fade);
}
