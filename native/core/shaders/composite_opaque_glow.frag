#version 440
// The composite step, form "opaque_glow" (Current_Plan.md item 8b, N3.4; D17 point 5; native/core/src/post_stages.h):
// rendering/quick/scene3d/target.py's opaque composite (_COMPOSITE_FRAGMENT, the transitions' scenes): the scene's colour
// with its glow added at u_bloom_strength (0: none), opaque, blending off ("replace"). The texel, the item's place
// (u_scene_item: Python discards outside the item) and the glow's uv as in composite_overlay_glow.frag (the core's
// top-first rows, the same physical texel as Python's, the glow read at Python's texel from the item's own pixel).
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform SceneComposite {
    vec2 u_target_px;        // the core's: the surface's pixels (the scene's content size)
    float u_bloom_strength;  // the mode's: 0 without bloom
    vec4 u_scene_item;       // the core's: the item's cover in the surface's pixels (left, top, width, height)
    vec3 u_scene_from_target_x; // the core's (ABI 29): the surface's pixel to the scene's texel (as the glow form's)
    vec3 u_scene_from_target_y;
};
layout(binding = 1) uniform sampler2D uScene;
layout(binding = 2) uniform sampler2D uBloom;

void main()
{
    ivec2 allocation = textureSize(uScene, 0);
    ivec2 content = ivec2(u_target_px + 0.5);
    ivec2 pixel = clamp(ivec2(floor(vec2(vUv.x, 1.0 - vUv.y) * u_target_px)), ivec2(0), content - ivec2(1));
    ivec4 item = ivec4(floor(u_scene_item + 0.5));
    ivec2 shown = ivec2(pixel.x - item.x, item.y + item.w - 1 - pixel.y);
    if (any(lessThan(shown, ivec2(0))) || any(greaterThanEqual(shown, item.zw))) discard;
    // Python's texel in the scene's frame (composite_overlay_glow.frag).
    vec3 centre = vec3(vec2(pixel) + 0.5, 1.0);
    ivec2 local = ivec2(floor(vec2(dot(u_scene_from_target_x, centre), dot(u_scene_from_target_y, centre))));
    // ABI 28: the scene holds Python's SceneTarget content (sceneAnchor): the item's pixel at its allocation's bottom
    // left, so the item's texel is read (Python's texelFetch(uScene, texel)): top-first rows here.
    ivec2 texel = ivec2(local.x, allocation.y - 1 - local.y);
    vec3 colour = texelFetch(uScene, texel, 0).rgb;
    if (u_bloom_strength > 0.0) {
        vec2 glowUv = vec2(float(local.x) + 0.5, float(allocation.y) - float(local.y) - 0.5) / vec2(allocation);
        colour += textureLod(uBloom, glowUv, 0.0).rgb * u_bloom_strength;
    }
    // The target's alpha may carry emissive light for the bloom; the surface gets opaque pixels.
    FragColor = vec4(colour, 1.0);
}
