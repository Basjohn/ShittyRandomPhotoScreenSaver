#version 440
// The transparency resolve, single-sampled (Current_Plan.md item 8b, N3.4; D17 point 2; native/core/src/post_stages.h):
// the transparency target's weighted average composited over its owner's colour 0, premultiplied, as the Python
// renderer's SceneTarget._resolve_transparent does (rendering/quick/scene3d/target.py _OIT_RESOLVE_FRAGMENT). The one
// difference is the read: the target stores coverage (1 - revealage: D17 choice B, blended ONE, ONE_MINUS_SRC_COLOR from
// a clear of 0) where Python stores revealage, so `coverage` is read as it is instead of as 1 - revealage.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 FragColor;
layout(binding = 1) uniform sampler2D uAccum;
layout(binding = 2) uniform sampler2D uCoverage;

void main()
{
    ivec2 texel = fragTexel(textureSize(uAccum, 0));   // drawn over the owner, the accumulation's size
    float coverage = texelFetch(uCoverage, texel, 0).r;
    if (coverage <= 1.0 / 1024.0) discard;
    vec4 accum = texelFetch(uAccum, texel, 0);
    FragColor = vec4(accum.rgb / max(accum.a, 1e-5) * coverage, coverage);
}
