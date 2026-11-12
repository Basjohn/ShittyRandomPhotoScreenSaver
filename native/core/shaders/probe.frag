#version 440
// The probe pass's colour (probe.vert says what the pass proves). The background writes what the conventions include
// says about this fragment: fragUv (from the block's x) in r and g, ndcToUv of the clip NDC (from the block's y) in b
// and a; on every backend the two agree and equal the memory texel's centre over the target size. The triangles write
// their own colour.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) in vec4 v_color;
layout(location = 1) in vec2 v_ndc;

layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform Probe {
    mat4 uploaded;
    vec4 targetSize;
};

void main()
{
    if (v_color.a < 0.0)
        fragColor = vec4(fragUv(targetSize.xy), ndcToUv(v_ndc));
    else
        fragColor = v_color;
}
