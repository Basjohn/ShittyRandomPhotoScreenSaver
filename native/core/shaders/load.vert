#version 440
// The known-cost pass (Current_Plan.md item 8b, N2.6; native/core/src/load_pass.h): one triangle over the whole target in
// clip space, its position handed on as the fragment loop's seed.

layout(location = 0) in vec2 position;
layout(location = 0) out vec2 seed;

void main()
{
    seed = position * 0.5 + 0.5;
    gl_Position = vec4(position, 0.0, 1.0);
}
