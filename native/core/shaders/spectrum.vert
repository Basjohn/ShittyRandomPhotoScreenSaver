#version 440
// The native Spectrum's vertex stage (Current_Plan.md item 8b, N2.5; native/core/src/spectrum.h): one triangle over the
// whole target in clip space. The fragment stage is the product's own spectrum.frag, which takes its coordinate from
// the target's pixel (fragPixel through u_item_from_frag); v_uv is its declared input and only its fallback reads it
// (a non-affine item, which the core's target never is).

layout(location = 0) in vec2 position;
layout(location = 0) out vec2 v_uv;

void main()
{
    v_uv = position * 0.5 + 0.5;
    gl_Position = vec4(position, 0.0, 1.0);
}
