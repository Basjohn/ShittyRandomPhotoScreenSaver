#version 440
// The surface pattern pass (Current_Plan.md item 8b, N2.4; native/core/src/surfaces.h): one triangle over the whole
// target in clip space. No matrix: the colour depends only on the texel each fragment lands on.

layout(location = 0) in vec2 position;

void main()
{
    gl_Position = vec4(position, 0.0, 1.0);
}
