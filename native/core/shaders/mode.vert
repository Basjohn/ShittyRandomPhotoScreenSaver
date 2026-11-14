#version 440
// A generic mode's vertex stage (Current_Plan.md item 8b, N2.9; native/core/src/mode_content.h): one triangle over the
// whole target in clip space, and the product 2D shaders' v_uv (location 0), as the native Spectrum's vertex stage gives
// it (position * 0.5 + 0.5: its row orientation is the backend's clip space; a pass that needs the target's pixel takes
// fragPixel from the conventions include).

layout(location = 0) in vec2 position;
layout(location = 0) out vec2 v_uv;

void main()
{
    v_uv = position * 0.5 + 0.5;
    gl_Position = vec4(position, 0.0, 1.0);
}
