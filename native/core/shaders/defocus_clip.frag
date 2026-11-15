#version 440
// The defocus step's clip (Current_Plan.md item 8b, N3.4; D17 point 6; native/core/src/post_stages.h):
// rendering/quick/scene3d/defocus.py _CLIP, the near layer's read level with each texel clipped at the highlight
// threshold (what the gather spreads), drawn into the step's texture of that level's size. The layer's mips are QRhi's
// generateMips (D17 choice G: the defocus layer only; Python's own glGenerateTextureMipmap). Every read here is by texel
// (memory rows on every backend), so the text is Python's but for the block and the bindings.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform SceneDefocus {
    float u_defocus_radius;     // the mode's: Python's uMaxRadius (pixels)
    float u_defocus_highlight;  // the mode's: Python's uHighlight
    int u_defocus_level;        // the mode's: Python's uLevel (_read_size: the gather's read level for the radius)
};
layout(binding = 1) uniform sampler2D uColour;
layout(binding = 2) uniform sampler2D uCircle;

// The first wide-disc tap is several pixels from the destination at large budgets.
// Circles smaller than that gap need a full-resolution gather of their own.
float fineRadius(float maximum) {
    // A circle smaller than the wide gather's mip texel is unresolved there.
    // Keep that whole band in the full-resolution gather, not merely circles
    // smaller than the first wide tap's distance.
    float tapSpacing = sqrt(3.14159265 * maximum * maximum / 64.0);
    float wideTexel = exp2(max(floor(log2(max(tapSpacing, 1.0))), 0.0));
    return min(maximum, max(wideTexel, max(4.0, maximum * sqrt(0.5 / 64.0) + 0.5)));
}
float fineShare(float circle, float maximum) {
    float radius = fineRadius(maximum);
    return 1.0 - smoothstep(0.75 * radius, radius, circle);
}
// A mip texel is not a point source when its circle is smaller than the texel.
// Only resolved highlights may move from the gather into texel-centred discs.
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
    ivec2 here = fragTexel(textureSize(uColour, u_defocus_level));   // the clip draws the read level at its own size
    vec4 c = texelFetch(uColour, here, u_defocus_level);
    float l = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
    float limit = sceneHighlightAt(uColour, here, u_defocus_level, u_defocus_highlight);
    vec2 circleData = texelFetch(uCircle, here, u_defocus_level).rg;
    float circle = circleData.y > 1e-4 ? circleData.x / circleData.y : 0.0;
    float share = spriteShare(circle, u_defocus_radius, u_defocus_level);
    FragColor = l > limit ? vec4(c.rgb * mix(1.0, limit / l, share), c.a) : c;
}
