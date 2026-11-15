#version 440
// A scene target's core resolve (Current_Plan.md item 8b, N3.1; D14 points 10 and 12; native/core/src/scene_targets.h):
// the core's own per-sample resolve of a multisampled texture into a single-sampled one, written texel for texel over
// the whole allocation. uMode 0 (D14 point 10): the minimum of the first channel over every sample, the nearest under
// the project's depth convention (less is nearer), for the D32F depth or an R32F attachment declared "resolve":
// "nearest"; the product's rule is the Python renderer's (SceneTarget.background() takes the nearest depth over the
// samples, rendering/quick/scene3d/target.py). uMode 2 (D14 point 12): the average of every channel, for a colour
// attachment of a fast-cleared target that a later run loads (QRhi's resolve would drop its samples). uMode 1: sample 0
// alone, the harness's negative control, never set by a mode.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 Resolved;

layout(std140, binding = 0) uniform SceneNearest {
    int uSamples;
    int uMode;
};
layout(binding = 1) uniform sampler2DMS uSource;

void main()
{
    ivec2 texel = fragTexel(textureSize(uSource));   // the destination is the source's size
    vec4 first = texelFetch(uSource, texel, 0);
    if (uMode == 2) {
        vec4 sum = first;
        for (int s = 1; s < uSamples; ++s)
            sum += texelFetch(uSource, texel, s);
        Resolved = sum / float(uSamples);
        return;
    }
    float nearest = first.r;
    if (uMode == 0) {
        for (int s = 1; s < uSamples; ++s)
            nearest = min(nearest, texelFetch(uSource, texel, s).r);
    }
    Resolved = vec4(nearest, 0.0, 0.0, 1.0);
}
