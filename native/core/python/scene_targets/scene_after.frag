#version 440
// N3.1's harness scene, pass 3, after the capture: drawn at a fixed depth with the depth test less_equal and no depth
// write, so it shows only where the depth loaded across the capture split is at or behind it (the split keeps the
// depth: a cleared depth would let it cover everything). Straight-alpha over the colour, emission masked.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 colour;
layout(location = 1) out vec4 emission;

layout(std140, binding = 18) uniform SceneAfter {
    vec4 u_after_colour;
    float u_after_depth;
};

void main()
{
    colour = u_after_colour;
    emission = vec4(0.0);
    gl_FragDepth = u_after_depth;
}
