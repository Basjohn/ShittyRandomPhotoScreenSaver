#version 440
// The defocus step's gather (Current_Plan.md item 8b, N3.4; D17 point 6; native/core/src/post_stages.h):
// rendering/quick/scene3d/defocus.py _GATHER, each pixel of the onto target gathering the near layer's light over the
// circles that reach it (64 taps on a golden-angle disc from the read level, 32 fine taps from level 0), premultiplied
// over the onto target. The layer and the onto target share their allocation (both surface-sized), so a texel is a
// pixel.
//
// fragPixel is the fragment's row in memory on both renderers; the OpenGL renderer's rows run bottom up and the core's
// top first, so Python's tap at +sin(a) (physically up) is the one at -sin(a) here: the same taps at the same places,
// in Python's order. N5.6: a layer that holds OpenGL's rows (u_scene_rows_up 1, the program's composite "scene_rows":
// "up": Extruded Bubble's near layer, drawn as Python's) takes Python's +sin(a) as it is; mirrored there, its circles
// gathered from the mirrored taps and differed from Python's (rule a). Every other read is by texel or at a texel's
// centre, and is Python's text.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 FragColor;

layout(std140, binding = 0) uniform SceneDefocus {
    float u_defocus_radius;     // the mode's: Python's uMaxRadius (pixels)
    float u_defocus_highlight;  // the mode's: Python's uHighlight
    int u_defocus_level;        // the mode's: Python's uLevel (_read_size: the gather's read level for the radius)
    float u_scene_rows_up;      // the core's (N5.6): 1 where the layer holds OpenGL's rows, else 0
};
layout(binding = 1) uniform sampler2D uColour;
layout(binding = 2) uniform sampler2D uCircle;
layout(binding = 3) uniform sampler2D uBelow;

const int TAPS = 64;
const int FINE_TAPS = 32;

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

float circleAt(vec2 uv, float level) {
    vec2 c = textureLod(uCircle, uv, level).rg;
    return c.y > 1e-4 ? c.x / c.y : 0.0;
}
void main() {
    float uMaxRadius = u_defocus_radius;
    float tapRows = u_scene_rows_up > 0.5 ? 1.0 : -1.0;   // the tap's row step: Python's sin(a) in the layer's rows
    vec2 size = vec2(textureSize(uColour, 0));
    ivec2 here = fragTexel(textureSize(uColour, 0));   // the gather draws over a target of the layer's size
    vec4 own = texelFetch(uColour, here, 0);
    vec2 ownCircle = texelFetch(uCircle, here, 0).rg;
    float ownRadius = ownCircle.y > 1e-4 ? ownCircle.x / ownCircle.y : 0.0;
    if (uMaxRadius < 0.5) { FragColor = own; return; }
    vec4 sum = vec4(0.0);
    // Each tap stands for an equal share of the disc of radius uMaxRadius, read at the level whose texels are about
    // that share's width; a source pixel's light spreads evenly over its own circle.
    float tapArea = 3.14159265 * uMaxRadius * uMaxRadius / float(TAPS);
    float level = max(floor(log2(max(sqrt(tapArea), 1.0))), 0.0);
    for (int i = 0; i < TAPS; ++i) {
        float r = sqrt((float(i) + 0.5) / float(TAPS)) * uMaxRadius;
        float a = float(i) * 2.39996323;
        vec2 uv = (fragPixel(size) + vec2(cos(a), tapRows * sin(a)) * r) / size;
        if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) continue;
        float circle = circleAt(uv, level);
        if (circle < 0.5) continue;
        float reach = clamp(circle - r + 0.5, 0.0, 1.0);          // the circle's edge, antialiased
        sum += textureLod(uBelow, uv, 0.0) * (1.0 - fineShare(circle, uMaxRadius))
               * reach * tapArea / (3.14159265 * circle * circle);
    }
    float smallRadius = fineRadius(uMaxRadius);
    float smallArea = 3.14159265 * smallRadius * smallRadius / float(FINE_TAPS);
    for (int i = 0; i < FINE_TAPS; ++i) {
        float r = sqrt((float(i) + 0.5) / float(FINE_TAPS)) * smallRadius;
        float a = float(i) * 2.39996323;
        vec2 uv = (fragPixel(size) + vec2(cos(a), tapRows * sin(a)) * r) / size;
        if (any(lessThan(uv, vec2(0.0))) || any(greaterThan(uv, vec2(1.0)))) continue;
        float circle = circleAt(uv, 0.0);
        if (circle < 0.5) continue;
        float reach = clamp(circle - r + 0.5, 0.0, 1.0);
        sum += textureLod(uColour, uv, 0.0) * fineShare(circle, uMaxRadius)
               * reach * smallArea / (3.14159265 * circle * circle);
    }
    // Sharp pixels (no circle) stay where they are.
    if (ownRadius < 0.5) sum += own;
    FragColor = sum;
}
