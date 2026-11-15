#version 440
// N3.1's harness, the second attachment (Bubble's ambient target's shape, bubble_ambient_gl.py): into an explicit-size
// target, an RGBA8 coverage (premultiplied over) and an RGBA16F linear light (added), from a few soft discs; u_glow 0
// writes no light (the attachment then holds its clear: nothing glows).
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 coverage;
layout(location = 1) out vec4 light;

layout(std140, binding = 18) uniform AmbientLight {
    vec4 u_disc_colour;
    float u_glow;
    float u_radius;
};

void main()
{
    float a = 0.0;
    for (int i = 0; i < 5; ++i) {
        vec2 centre = vec2(0.15 + 0.17 * float(i), 0.3 + 0.1 * float(i % 3));
        a = max(a, smoothstep(u_radius, u_radius * 0.5, distance(vUv, centre)));
    }
    coverage = vec4(u_disc_colour.rgb * a, a);
    light = vec4(u_disc_colour.rgb * (u_glow * 2.5 * a), 0.0);
}
