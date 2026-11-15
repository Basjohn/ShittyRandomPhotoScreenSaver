#version 440
// A scene target's capture (Current_Plan.md item 8b, N3.1; D14 point 5; native/core/src/scene_targets.h): what the
// target's passes drew so far, copied texel for texel over the whole allocation into the capture's two textures, as the
// Python renderer's SceneTarget.background() does (rendering/quick/scene3d/target.py _BACKGROUND_FRAGMENT): the colour
// (attachment 0, or its resolve when multisampled) and the nearest window depth through viewDepthFromDepthTexture (the
// depth, or its resolve: one sample's depth, D14 point 8), the far plane (1) for a target without depth. The capture
// target is the scene's allocation, so a texel's own pixel is its source's.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 Colour;
layout(location = 1) out vec4 Depth;

layout(std140, binding = 0) uniform SceneCapture {
    int uHasDepth;
};
layout(binding = 1) uniform sampler2D uColour;
layout(binding = 2) uniform sampler2D uDepth;

void main()
{
    ivec2 texel = fragTexel(textureSize(uColour, 0));   // the capture is the scene's size
    Colour = texelFetch(uColour, texel, 0);
    Depth = vec4(uHasDepth == 1 ? viewDepthFromDepthTexture(texelFetch(uDepth, texel, 0).r) : 1.0);
}
