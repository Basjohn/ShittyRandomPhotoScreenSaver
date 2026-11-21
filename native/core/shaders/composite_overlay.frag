#version 440
// The composite step, form "overlay" (Current_Plan.md item 8b, N3.4; D17 point 5; native/core/src/post_stages.h): a
// scene target onto the surface as rendering/quick/scene3d/target.py's overlay composite (_COMPOSITE_OVERLAY_FRAGMENT):
// the scene as straight colour times the fade, discarded where nothing was drawn and outside the item (Python's
// SceneTarget covers the item's own pixels: u_scene_item, ABI 27), under the core's "alpha" blend (the surface then holds
// premultiplied colour, composite.frag). The scene is read through its resolve when multisampled (D14 point 8; N1.8's
// first use: Python's shader average becomes QRhi's average resolve).
//
// The surface pixel to the scene's texel: the scene's content sits at image rows [H-h, H), columns [0, w) of its
// allocation (D14 point 2), the surface's rows run top first, and vUv is 1 at the surface's top row.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform SceneComposite {
    vec2 u_target_px;    // the core's: the surface's pixels (the scene's content size)
    float u_fade;        // the core's: the content fade (Python's uOpacity)
    vec4 u_scene_item;   // the core's: the item's cover in the surface's pixels (left, top, width, height)
};
layout(binding = 1) uniform sampler2D uScene;

void main()
{
    ivec2 allocation = textureSize(uScene, 0);
    ivec2 content = ivec2(u_target_px + 0.5);
    ivec2 pixel = clamp(ivec2(floor(vec2(vUv.x, 1.0 - vUv.y) * u_target_px)), ivec2(0), content - ivec2(1));
    ivec4 item = ivec4(floor(u_scene_item + 0.5));
    ivec2 local = ivec2(pixel.x - item.x, item.y + item.w - 1 - pixel.y);
    if (any(lessThan(local, ivec2(0))) || any(greaterThanEqual(local, item.zw))) discard;
    ivec2 texel = ivec2(pixel.x, allocation.y - content.y + pixel.y);
    vec4 colour = texelFetch(uScene, texel, 0);
    if (colour.a <= 0.0) discard;
    FragColor = vec4(colour.rgb / colour.a, colour.a * u_fade);
}
