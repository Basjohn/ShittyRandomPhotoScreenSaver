#version 440
// The composite step, form "overlay_glow" (Current_Plan.md item 8b, N3.4; D17 point 5; native/core/src/post_stages.h):
// rendering/quick/scene3d/target.py's overlay-with-bloom composite (_OVERLAY_BLOOM_GLSL): the scene premultiplied with
// its glow added, under the core's "premultiplied" blend (Python's ONE, ONE_MINUS_SRC_ALPHA). The HDR resolve: with
// u_hdr_exposure above 0 the straight colour is tone mapped (the ACES fit) at that exposure, so the coverage at an
// overlay's edge is kept; 0 draws it as it is. A triangular dither of one output step, from the exact integer hash
// (R-94), only where glow was added.
//
// Python's texel is the item's own pixel (its SceneTarget starts there: item_pixel_rect), x from the item's left, rows
// from its bottom; it discards outside the item and reads its glow at that texel's centre over the allocation (the glow
// covers the allocation at half size). Here the item's place in the surface is u_scene_item (left, top, width, height);
// the scene holds Python's own content (ABI 28, sceneAnchor: the item's pixel at the allocation's bottom left, the
// allocation the bucket of the item), so the scene, the glow (its uv Python's texel centre over the allocation, mirrored
// to the image's top-first rows) and the dither's key are all read at Python's texel: the same values at the same place.
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform SceneComposite {
    vec2 u_target_px;        // the core's: the surface's pixels (the scene's content size)
    float u_fade;            // the core's: the content fade (Python's uOpacity)
    float u_bloom_strength;  // the mode's (a setting, or a record field: the Oscilloscope's changes each frame)
    float u_hdr_exposure;    // the mode's: > 0 an HDR scene tone mapped at this exposure; 0 as drawn
    vec4 u_scene_item;       // the core's: the item's cover in the surface's pixels (left, top, width, height)
};
layout(binding = 1) uniform sampler2D uScene;
layout(binding = 2) uniform sampler2D uBloom;

uint sceneMix(uint x)
{
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}
float sceneRandom(uint key, uint salt, uint seed)
{
    return float(sceneMix(key * 0x9e3779b9u ^ sceneMix(seed * 0x85ebca6bu + salt))) * (1.0 / 4294967295.0);
}
const float SCENE_DITHER_FLOOR = 0.000980392;
vec3 sceneOutputDither(ivec2 pixel)
{
    uint key = uint(pixel.x & 0xffff) | (uint(pixel.y & 0xffff) << 16);
    vec3 a = vec3(sceneRandom(key, 1u, 0u), sceneRandom(key, 2u, 0u), sceneRandom(key, 3u, 0u));
    vec3 b = vec3(sceneRandom(key, 4u, 0u), sceneRandom(key, 5u, 0u), sceneRandom(key, 6u, 0u));
    return (a + b - 1.0) * 0.003921569;
}

vec3 sceneToneMap(vec3 x)
{
    x *= u_hdr_exposure;
    return clamp(x * (2.51 * x + 0.03) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}

void main()
{
    ivec2 allocation = textureSize(uScene, 0);
    ivec2 content = ivec2(u_target_px + 0.5);
    ivec2 pixel = clamp(ivec2(floor(vec2(vUv.x, 1.0 - vUv.y) * u_target_px)), ivec2(0), content - ivec2(1));
    ivec4 item = ivec4(floor(u_scene_item + 0.5));
    // Python's texel: x from the item's left, rows up from its bottom.
    ivec2 local = ivec2(pixel.x - item.x, item.y + item.w - 1 - pixel.y);
    if (any(lessThan(local, ivec2(0))) || any(greaterThanEqual(local, item.zw))) discard;
    // ABI 28: the scene holds Python's SceneTarget content (sceneAnchor): the item's pixel at its allocation's bottom
    // left, so the item's texel is read (Python's texelFetch(uScene, texel)): top-first rows here.
    ivec2 texel = ivec2(local.x, allocation.y - 1 - local.y);
    vec4 scene = texelFetch(uScene, texel, 0);
    vec2 glowUv = vec2(float(local.x) + 0.5, float(allocation.y) - float(local.y) - 0.5) / vec2(allocation);
    vec3 glow = textureLod(uBloom, glowUv, 0.0).rgb * u_bloom_strength;
    if (scene.a <= 0.0 && max(glow.r, max(glow.g, glow.b)) < 1.0 / 512.0) discard;
    vec3 light = scene.rgb + glow;
    if (u_hdr_exposure > 0.0) {
        // Tone map the straight colour, so coverage at an overlay's edge is kept.
        float cover = max(scene.a, 1e-4);
        light = sceneToneMap(light / cover) * cover;
    }
    if (max(glow.r, max(glow.g, glow.b)) >= SCENE_DITHER_FLOOR)
        light += sceneOutputDither(local);
    FragColor = vec4(light * u_fade, scene.a * u_fade);
}
