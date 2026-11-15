#version 440
// A scene target's nearest resolve (Current_Plan.md item 8b, N3.1; D14 point 10; native/core/src/scene_targets.h): the
// core's own per-sample resolve of a multisampled single-channel texture (the D32F depth, or an R32F attachment declared
// "resolve": "nearest") into a single-sampled R32F texture: the minimum over every sample, the nearest under the
// project's depth convention (less is nearer). The product's rule is the Python renderer's: SceneTarget.background()
// takes the nearest depth over the samples (rendering/quick/scene3d/target.py). Written texel for texel over the whole
// allocation. uFirstOnly is the harness's negative control (sample 0 alone), never set by a mode.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 Nearest;

layout(std140, binding = 0) uniform SceneNearest {
    int uSamples;
    int uFirstOnly;
};
layout(binding = 1) uniform sampler2DMS uSource;

void main()
{
    ivec2 texel = fragTexel(textureSize(uSource));   // the destination is the source's size
    float nearest = texelFetch(uSource, texel, 0).r;
    if (uFirstOnly == 0) {
        for (int s = 1; s < uSamples; ++s)
            nearest = min(nearest, texelFetch(uSource, texel, s).r);
    }
    Nearest = vec4(nearest, 0.0, 0.0, 1.0);
}
