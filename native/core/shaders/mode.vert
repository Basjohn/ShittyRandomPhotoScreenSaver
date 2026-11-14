#version 440
// A generic mode's and a fullscreen pass's vertex stage (Current_Plan.md item 8b, N2.9 and N4.a;
// native/core/src/mode_content.h): one triangle over the whole target in clip space, and at location 0 the uv the pass's
// fragment names, the same on every backend: the core's vertex buffer carries both quads' uv per vertex (v_uv: the
// Visualizer quad's, y down from the target's top row; vUv: the item quad's, y up), and each pass's pipeline feeds the
// one it reads into `uv` (location 1). A pass that needs the target's pixel takes fragPixel from the conventions include.

layout(location = 0) in vec2 position;
layout(location = 1) in vec2 uv;
layout(location = 0) out vec2 v_uv;

void main()
{
    v_uv = uv;
    gl_Position = vec4(position, 0.0, 1.0);
}
