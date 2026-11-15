#version 440
// The bloom chain's later downsamples (Current_Plan.md item 8b, N3.4; D17 point 4): rendering/quick/scene3d/post.py
// _DOWNSAMPLE_FRAGMENT with uFirst 0, the 13-tap filter from the level above into the next at half its size. The taps
// are mirrored to the core's top-first rows as in bloom_down_first.frag.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;
layout(binding = 1) uniform sampler2D uSource;

vec3 tap(vec2 offset)
{
    vec2 texel = 1.0 / vec2(textureSize(uSource, 0));
    return textureLod(uSource, vec2(vUv.x, 1.0 - vUv.y) + vec2(offset.x, -offset.y) * texel, 0.0).rgb;
}

void main()
{
    // A 13-tap filter: a smooth downsample that neither flickers nor boxes.
    vec3 centre = tap(vec2(0.0)) * 0.125;
    vec3 inner = (tap(vec2(-1.0, -1.0)) + tap(vec2(1.0, -1.0)) + tap(vec2(-1.0, 1.0)) + tap(vec2(1.0, 1.0))) * 0.125;
    vec3 outer = (tap(vec2(-2.0, -2.0)) + tap(vec2(2.0, -2.0)) + tap(vec2(-2.0, 2.0)) + tap(vec2(2.0, 2.0))) * 0.03125;
    vec3 sides = (tap(vec2(-2.0, 0.0)) + tap(vec2(2.0, 0.0)) + tap(vec2(0.0, -2.0)) + tap(vec2(0.0, 2.0))) * 0.0625;
    FragColor = vec4(centre + inner + outer + sides, 1.0);
}
