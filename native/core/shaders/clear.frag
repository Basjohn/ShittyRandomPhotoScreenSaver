#version 440
// A content's first draw over the whole target with blending off (Current_Plan.md item 8b, N2.5): every texel
// transparent, so the target is cleared by a draw and never by an UNDEFINED load (native/core/src/targets.h rule B).
// Spectrum's pass draws it before its bars.

layout(location = 0) out vec4 fragColor;

void main()
{
    fragColor = vec4(0.0);
}
