#version 440
// N3.1's harness, D14 point 10's means (b): the surface's pass reading the "lin" target's nearest-resolved R32F
// attachment and its depth's nearest resolve, so both are read (the readback compares them; this is not a look).
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(binding = 1) uniform sampler2D u_lin;
layout(binding = 2) uniform sampler2D u_lin_depth;

void main()
{
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    fragColor = vec4(texture(u_lin, uv).r, texture(u_lin_depth, uv).r, 0.0, 1.0);
}
