
#ifndef SRPSS_GEOMETRY
#define SRPSS_GEOMETRY
// The geometry include (D15 points 5 and 6; rendering/gl_programs/conventions.py SRPSS_GEOMETRY_GLSL, the core's
// native/core/shaders/srpss_geometry.glsl holds the same text). It follows the conventions include (its block's z: 1
// where the drawn target's top row lies at clip NDC -Y, the native core's OpenGL and Vulkan targets; 0 in the OpenGL
// renderer's window and targets).
// Instanced quads in place of point sprites: a strip of 4 vertices a sprite (draw(4, n), the sprite as the instance), or a
// list of 6 where the instance is taken. The unit corner has gl_PointCoord's orientation: x right, y down, (0, 0) the
// sprite's top-left.
vec2 srpssSpriteCorner(int vertexIndex) { return vec2(float(vertexIndex & 1), float((vertexIndex >> 1) & 1)); }
vec2 srpssSpriteCornerList(int vertexIndex) {
    int c = vertexIndex % 6;
    return srpssSpriteCorner(c < 3 ? c : (c == 3 ? 2 : (c == 4 ? 1 : 3)));
}
// The clip position of `corner` of a sprite `sizePx` target pixels across, centred on `clipCentre`: the same square of
// pixel centres on every backend.
vec4 srpssSpriteClip(vec4 clipCentre, vec2 corner, float sizePx, vec2 targetPx) {
    vec2 d = vec2(corner.x - 0.5, 0.5 - corner.y) * (2.0 * sizePx) / targetPx;
    if (srpssConventions.z > 0.5) d.y = -d.y;
    return vec4(clipCentre.xy + d * clipCentre.w, clipCentre.zw);
}
// A culled sprite: every corner outside the clip volume, a degenerate quad.
vec4 srpssSpriteCulled() { return vec4(2.0, 2.0, 2.0, 1.0); }
// A batched draw's batch (D15 point 6): gl_DrawID in the pass's draw-parameters pack (one multi-draw indirect call;
// #version 460), else the core's per-batch block member u_srpss_batch (one draw a batch at its dynamic offset).
#ifdef SRPSS_DRAW_PARAMETERS
#define srpssBatchIndex gl_DrawID
#else
#define srpssBatchIndex u_srpss_batch
#endif
#endif
