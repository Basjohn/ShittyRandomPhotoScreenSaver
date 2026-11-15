#version 440
// The defocus step's highlight sprites, vertex stage (Current_Plan.md item 8b, N3.4; D17 point 6;
// native/core/src/post_stages.h): rendering/quick/scene3d/defocus.py _SPRITE_VERTEX, one instanced quad (a strip of 4)
// per texel of the read level holding light above its surroundings, its disc the texel's circle and its light the excess
// the clip took out. The core draws exactly the read level's texels (D17 choice I: the count is the core's, from the
// level's size). The disc is placed from the texel in memory rows into raw clip space, which lands on the same memory
// row on every backend (clip -1 is row 0 on OpenGL and on Vulkan), so the text is Python's; its size is the layer's
// (Python's uSize), read from the texture, and the core draws the sprites over the layer's whole allocation.
layout(std140, binding = 0) uniform SceneDefocus {
    float u_defocus_radius;     // the mode's: Python's uMaxRadius (pixels)
    float u_defocus_highlight;  // the mode's: Python's uHighlight
    int u_defocus_level;        // the mode's: Python's uLevel (_read_size)
};
layout(binding = 1) uniform sampler2D uColour;
layout(binding = 2) uniform sampler2D uCircle;

layout(location = 0) out vec2 vOffset;
layout(location = 1) flat out float vCircle;
layout(location = 2) flat out vec3 vLight;

float fineRadius(float maximum) {
    float tapSpacing = sqrt(3.14159265 * maximum * maximum / 64.0);
    float wideTexel = exp2(max(floor(log2(max(tapSpacing, 1.0))), 0.0));
    return min(maximum, max(wideTexel, max(4.0, maximum * sqrt(0.5 / 64.0) + 0.5)));
}
float spriteShare(float circle, float maximum, int level) {
    float resolved = max(fineRadius(maximum), float(1 << level));
    return smoothstep(resolved, 2.0 * resolved, circle);
}
// A highlight is light above its surroundings (the mean two levels coarser) and above the floor.
float sceneHighlightAt(sampler2D colour, ivec2 texel, int level, float floorLevel) {
    vec2 uv = (vec2(texel) + 0.5) / vec2(textureSize(colour, level));
    float local = dot(textureLod(colour, uv, float(level + 2)).rgb, vec3(0.2126, 0.7152, 0.0722));
    return max(floorLevel, local);
}
void main() {
    int uLevel = u_defocus_level;
    vec2 uSize = vec2(textureSize(uColour, 0));
    ivec2 grid = textureSize(uColour, uLevel);
    ivec2 texel = ivec2(gl_InstanceIndex % grid.x, gl_InstanceIndex / grid.x);
    vec4 c = texelFetch(uColour, texel, uLevel);
    vec2 circleData = texelFetch(uCircle, texel, uLevel).rg;
    float circle = circleData.y > 1e-4 ? circleData.x / circleData.y : 0.0;
    float l = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
    vec2 corner = vec2(float(gl_VertexIndex & 1), float((gl_VertexIndex >> 1) & 1)) * 2.0 - 1.0;
    float limit = sceneHighlightAt(uColour, texel, uLevel, u_defocus_highlight);
    float share = spriteShare(circle, u_defocus_radius, uLevel);
    vOffset = vec2(0.0);
    vCircle = 0.0;
    vLight = vec3(0.0);
    if (l <= limit || share <= 0.0) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
    float texelPx = float(1 << uLevel);
    // The texel's excess light, in pixel units, spread over its circle's area.
    vLight = c.rgb * (1.0 - limit / l) * share * texelPx * texelPx / (3.14159265 * circle * circle);
    vCircle = circle;
    vOffset = corner * (circle + 1.0);
    vec2 centre = (vec2(texel) + 0.5) * texelPx;
    gl_Position = vec4((centre + vOffset) / uSize * 2.0 - 1.0, 0.0, 1.0);
}
