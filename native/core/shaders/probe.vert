#version 440
// The frame driver's probe pass (Current_Plan.md item 8b, N2.2): a trivial core pass that proves the frame edge, the
// upload correction and the readback orientation end to end against N0.3's conventions. Geometry is authored in item
// pixels (x right, y down, origin top-left) and reaches clip space through an OpenGL-form matrix that the core
// corrected once, at upload (rule 1, F1).

layout(location = 0) in vec4 position;   // item pixels (z 0, w 1)
layout(location = 1) in vec4 color;      // a < 0: the background, coloured from the include; else this colour

layout(location = 0) out vec4 v_color;
layout(location = 1) out vec2 v_ndc;     // the clip NDC the rasterizer uses (the corrected matrix's)

layout(std140, binding = 0) uniform Probe {
    mat4 uploaded;       // the corrected matrix
    vec4 targetSize;     // xy: the target in pixels
};

void main()
{
    vec4 clip = uploaded * position;
    v_color = color;
    v_ndc = clip.xy / clip.w;
    gl_Position = clip;
}
