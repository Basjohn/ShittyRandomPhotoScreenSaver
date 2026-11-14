#version 440
// N3.1's harness scene, pass 2: a nearer plane over the content's lower half (depth test less, writes on), a flat
// colour and no emission (its emission attachment masked): the nearer plane wins where it is nearer than pass 1's.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 colour;
layout(location = 1) out vec4 emission;

layout(std140, binding = 18) uniform SceneNearer {
    vec4 u_nearer_colour;
    float u_nearer_depth;
};

void main()
{
    if (vUv.y > 0.5)
        discard;
    colour = u_nearer_colour;
    emission = vec4(0.0);
    gl_FragDepth = u_nearer_depth;
}
