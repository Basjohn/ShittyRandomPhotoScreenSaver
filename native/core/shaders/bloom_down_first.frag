#version 440
// The bloom chain's first downsample (Current_Plan.md item 8b, N3.4; D17 point 4; native/core/src/post_stages.h):
// rendering/quick/scene3d/post.py _DOWNSAMPLE_FRAGMENT with uFirst 1 (keep only the emitted light: colour scaled to
// alpha's brightness), a 13-tap filter from the source into level 0 at half its size. One texture a level, never levels
// of one texture (D17: QRhi tracks a whole texture); never generateMips (its linear blit is not this filter).
//
// Python reads texture(uSource, vUv + offset * uTexel) in the OpenGL renderer's rows (y up). The core's images run top
// first, so the same physical tap is (vUv.x, 1 - vUv.y) + (offset.x, -offset.y) * texel: the taps are summed in Python's
// order over the same texels. uTexel is one source texel, from the source's own size (Python: 1 / that size).
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;
layout(binding = 1) uniform sampler2D uSource;

vec3 tap(vec2 offset)
{
    vec2 texel = 1.0 / vec2(textureSize(uSource, 0));
    vec4 value = textureLod(uSource, vec2(vUv.x, 1.0 - vUv.y) + vec2(offset.x, -offset.y) * texel, 0.0);
    float brightness = dot(value.rgb, vec3(0.2126, 0.7152, 0.0722));
    return value.rgb * clamp(value.a / max(brightness, 1e-3), 0.0, 1.0);
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
