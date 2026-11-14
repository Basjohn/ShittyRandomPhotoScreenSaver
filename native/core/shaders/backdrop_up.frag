#version 440
// The backdrop pyramid's dual-filter (Kawase) upsample (Current_Plan.md N5.7b; native/core/src/backdrop.h): the Python
// pyramid's _UP (rendering/quick/render/surface_backdrop.py), term for term. uHalfPixel is half a texel of this pass's
// TARGET.

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
    vec3 sum = texture(uSource, vUv + vec2(-h.x * 2.0, 0.0)).rgb;
    sum += texture(uSource, vUv + vec2(-h.x, h.y)).rgb * 2.0;
    sum += texture(uSource, vUv + vec2(0.0, h.y * 2.0)).rgb;
    sum += texture(uSource, vUv + vec2(h.x, h.y)).rgb * 2.0;
    sum += texture(uSource, vUv + vec2(h.x * 2.0, 0.0)).rgb;
    sum += texture(uSource, vUv + vec2(h.x, -h.y)).rgb * 2.0;
    sum += texture(uSource, vUv + vec2(0.0, -h.y * 2.0)).rgb;
    sum += texture(uSource, vUv + vec2(-h.x, -h.y)).rgb * 2.0;
    fragColor = vec4(sum / 12.0, 1.0);
}
