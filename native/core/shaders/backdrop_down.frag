#version 440
// The backdrop pyramid's dual-filter (Kawase) downsample (Current_Plan.md N5.7b; native/core/src/backdrop.h): the
// Python pyramid's _DOWN (rendering/quick/render/surface_backdrop.py), term for term, so each level equals its level.
// uHalfPixel is half a texel of this pass's TARGET, as the Python pass is given.

layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform BackdropPass {
    vec4 uHalfPixel;
    vec4 uSeedWindow;
    vec4 uSeedLayer;
};

layout(binding = 1) uniform sampler2D uSource;

void main()
{
    vec2 h = uHalfPixel.xy;
    vec3 sum = texture(uSource, vUv).rgb * 4.0;
    sum += texture(uSource, vUv - h).rgb;
    sum += texture(uSource, vUv + h).rgb;
    sum += texture(uSource, vUv + vec2(h.x, -h.y)).rgb;
    sum += texture(uSource, vUv - vec2(h.x, -h.y)).rgb;
    fragColor = vec4(sum / 8.0, 1.0);
}
