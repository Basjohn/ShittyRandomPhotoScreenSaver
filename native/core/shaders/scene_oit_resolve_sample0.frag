#version 440
// Harness only (N3.4, D17 choice C's negative control, post_stages.h setTransparencyFirstSample): the per-sample resolve
// reading sample 0's layer for every sample, as an averaged or single read would. Wrong exactly where a transparent
// layer covers some samples of a pixel and not others; never drawn in the product.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 FragColor;
layout(binding = 1) uniform sampler2DMS uAccum;
layout(binding = 2) uniform sampler2DMS uCoverage;

void main()
{
    ivec2 texel = fragTexel(textureSize(uAccum));
    int sampleIndex = gl_SampleID * 0;   // per-sample shading kept (the product's pipeline), sample 0 read
    float coverage = texelFetch(uCoverage, texel, sampleIndex).r;
    if (coverage <= 1.0 / 1024.0) discard;
    vec4 accum = texelFetch(uAccum, texel, sampleIndex);
    FragColor = vec4(accum.rgb / max(accum.a, 1e-5) * coverage, coverage);
}
