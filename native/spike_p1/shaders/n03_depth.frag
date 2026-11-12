#version 440
// N0.3 scene 2, second pass: the D32F target sampled at this fragment's texel, through viewDepthFromDepthTexture
// (x) and raw (y).
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions
//@n03_common

layout(binding = 6) uniform sampler2D depthTex;

layout(location = 0) out vec4 outDepth;

void main()
{
    float depth = texelFetch(depthTex, fragTexel(ivec2(targetSize.xy)), 0).r;
    outDepth = vec4(viewDepthFromDepthTexture(depth), depth, 0.0, 1.0 + consumeVaryings());
}
