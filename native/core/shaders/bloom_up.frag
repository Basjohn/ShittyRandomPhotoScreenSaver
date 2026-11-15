#version 440
// The bloom chain's upsample (Current_Plan.md item 8b, N3.4; D17 point 4): rendering/quick/scene3d/post.py
// _UPSAMPLE_FRAGMENT, a 3x3 tent of the smaller level added onto the next larger one by the pipeline's blend (colour
// ONE, ONE; alpha ZERO, ONE: passes.py blend_scope). Python's taps in its own order, mirrored to the core's top-first
// rows (a tap Python takes at +y is the one at -y here); uTexel is one texel of the smaller level.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;
layout(binding = 1) uniform sampler2D uSource;

void main()
{
    vec2 texel = 1.0 / vec2(textureSize(uSource, 0));
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    // A 3x3 tent, added onto the next larger level by the blend state.
    vec3 sum = textureLod(uSource, uv, 0.0).rgb * 4.0;
    sum += (textureLod(uSource, uv + vec2(texel.x, 0.0), 0.0).rgb + textureLod(uSource, uv - vec2(texel.x, 0.0), 0.0).rgb
          + textureLod(uSource, uv - vec2(0.0, texel.y), 0.0).rgb + textureLod(uSource, uv + vec2(0.0, texel.y), 0.0).rgb)
         * 2.0;
    sum += textureLod(uSource, uv + vec2(texel.x, -texel.y), 0.0).rgb
         + textureLod(uSource, uv + vec2(-texel.x, texel.y), 0.0).rgb
         + textureLod(uSource, uv + vec2(texel.x, texel.y), 0.0).rgb
         + textureLod(uSource, uv + vec2(-texel.x, -texel.y), 0.0).rgb;
    FragColor = vec4(sum / 16.0, 1.0);
}
