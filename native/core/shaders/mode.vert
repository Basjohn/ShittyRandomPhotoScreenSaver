#version 440
// A generic mode's vertex stage (Current_Plan.md item 8b, N2.9; native/core/src/mode_content.h): one triangle over the
// whole target in clip space, and nothing else. A pass's fragment stage reads no input: its pixel is fragPixel (the
// conventions include), the same on every backend.

layout(location = 0) in vec2 position;

void main()
{
    gl_Position = vec4(position, 0.0, 1.0);
}
