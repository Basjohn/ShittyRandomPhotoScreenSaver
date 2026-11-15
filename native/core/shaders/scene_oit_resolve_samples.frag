#version 440
// The transparency resolve per sample (Current_Plan.md item 8b, N3.4; D17 point 2 and choice C): Python's
// _OIT_RESOLVE_SAMPLES_FRAGMENT (rendering/quick/scene3d/target.py), run once per sample through gl_SampleID (Vulkan's
// sampleRateShading, in the device gate), each sample compositing its own layer over the multisampled owner. Coverage is
// stored inverted (D17 choice B), so it is read as it is.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 FragColor;
layout(binding = 1) uniform sampler2DMS uAccum;
layout(binding = 2) uniform sampler2DMS uCoverage;

void main()
{
    // gl_SampleID runs this once per sample, so each sample composites its own layer.
    ivec2 texel = fragTexel(textureSize(uAccum));
    float coverage = texelFetch(uCoverage, texel, gl_SampleID).r;
    if (coverage <= 1.0 / 1024.0) discard;
    vec4 accum = texelFetch(uAccum, texel, gl_SampleID);
    FragColor = vec4(accum.rgb / max(accum.a, 1e-5) * coverage, coverage);
}
