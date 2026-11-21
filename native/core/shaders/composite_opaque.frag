#version 440
// The composite step, form "opaque" (Current_Plan.md N5.2c; D17 point 5; native/core/src/post_stages.h):
// rendering/quick/scene3d/target.py's opaque composite of a 3D transition's scene without bloom (_COMPOSITE_FRAGMENT,
// and _COMPOSITE_SAMPLES_FRAGMENT whose shader average becomes QRhi's average resolve: D5.6 row 7): the scene's colour,
// opaque, blending off ("replace"), nothing drawn outside the item. composite_opaque_glow.frag without its glow: the
// texel and the item's place exactly as there (the core's top-first rows, the same physical texel as Python's).
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform SceneComposite {
    vec2 u_target_px;        // the core's: the surface's pixels (the scene's content size)
    vec4 u_scene_item;       // the core's: the item's cover in the surface's pixels (left, top, width, height)
    vec3 u_scene_from_target_x; // the core's (ABI 29): the surface's pixel to the scene's texel
    vec3 u_scene_from_target_y;
};
layout(binding = 1) uniform sampler2D uScene;

void main()
{
    ivec2 allocation = textureSize(uScene, 0);
    ivec2 content = ivec2(u_target_px + 0.5);
    ivec2 pixel = clamp(ivec2(floor(vec2(vUv.x, 1.0 - vUv.y) * u_target_px)), ivec2(0), content - ivec2(1));
    ivec4 item = ivec4(floor(u_scene_item + 0.5));
    ivec2 shown = ivec2(pixel.x - item.x, item.y + item.w - 1 - pixel.y);
    if (any(lessThan(shown, ivec2(0))) || any(greaterThanEqual(shown, item.zw))) discard;
    vec3 centre = vec3(vec2(pixel) + 0.5, 1.0);
    ivec2 local = ivec2(floor(vec2(dot(u_scene_from_target_x, centre), dot(u_scene_from_target_y, centre))));
    ivec2 texel = ivec2(local.x, allocation.y - 1 - local.y);
    // The target's alpha is the scene's own; the surface gets opaque pixels (Python's FragColor alpha 1).
    FragColor = vec4(texelFetch(uScene, texel, 0).rgb, 1.0);
}
