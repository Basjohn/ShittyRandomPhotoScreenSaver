#version 440
// The composite step, form "opaque_glow" (Current_Plan.md item 8b, N3.4; D17 point 5; native/core/src/post_stages.h):
// rendering/quick/scene3d/target.py's opaque composite (_COMPOSITE_FRAGMENT, the transitions' scenes): the scene's colour
// with its glow added at u_bloom_strength (0: none), opaque, blending off ("replace"). The texel and the glow's uv as in
// composite_overlay_glow.frag (the core's top-first rows, the same physical texel as Python's).
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform SceneComposite {
    vec2 u_target_px;        // the core's: the surface's pixels (the scene's content size)
    float u_bloom_strength;  // the mode's: 0 without bloom
};
layout(binding = 1) uniform sampler2D uScene;
layout(binding = 2) uniform sampler2D uBloom;

void main()
{
    ivec2 allocation = textureSize(uScene, 0);
    ivec2 content = ivec2(u_target_px + 0.5);
    ivec2 pixel = clamp(ivec2(floor(vec2(vUv.x, 1.0 - vUv.y) * u_target_px)), ivec2(0), content - ivec2(1));
    ivec2 texel = ivec2(pixel.x, allocation.y - content.y + pixel.y);
    vec3 colour = texelFetch(uScene, texel, 0).rgb;
    if (u_bloom_strength > 0.0)
        colour += textureLod(uBloom, (vec2(texel) + 0.5) / vec2(allocation), 0.0).rgb * u_bloom_strength;
    // The target's alpha may carry emissive light for the bloom; the surface gets opaque pixels.
    FragColor = vec4(colour, 1.0);
}
