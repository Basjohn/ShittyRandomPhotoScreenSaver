#version 440
// The composite's fragment stage (Current_Plan.md item 8b, N2.4; native/core/src/composite.h).
//
// One to one: the fragment's device pixel inside the item is the integer floor(uv x the item's device size), whose
// thresholds lie on pixel edges, never on a centre (R-197). The content is read whole with texelFetch at that pixel,
// turned by the quarter turn (widgets/spotify_visualizer/presentation_orientation.py logical_uv_from_physical_uv:
// physical (u, v) reads logical (v, 1 - u) for one clockwise turn).
//
// The card's coverage (plan 1C.4): the rounded rectangle's signed distance at the pixel's centre, in device pixels; the
// pixel is content when it is <= 0 (rendering/quick/visualizer/clip_host.py's rule, the stencil the Python path
// writes). One function of the integer pixel, so both triangles of the quad decide every pixel alike.

layout(location = 0) in vec2 v_uv;

layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float coverageOn;
    float coverageRadius;
    float quarters;
    vec4 coverageRect;
    vec4 sizes;
};

layout(binding = 1) uniform sampler2D content;

void main()
{
    ivec2 outputSize = ivec2(sizes.xy + 0.5);
    ivec2 pixel = clamp(ivec2(floor(v_uv * sizes.xy)), ivec2(0), outputSize - ivec2(1));
    if (coverageOn > 0.5) {
        vec2 halfSize = coverageRect.zw * 0.5;
        vec2 centre = coverageRect.xy + halfSize;
        float radius = min(coverageRadius, min(halfSize.x, halfSize.y));
        vec2 q = abs(vec2(pixel) + 0.5 - centre) - (halfSize - vec2(radius));
        float distanceToEdge = length(max(q, vec2(0.0))) + min(max(q.x, q.y), 0.0) - radius;
        if (distanceToEdge > 0.0)
            discard;
    }
    int turns = int(quarters + 0.5);
    ivec2 texel = pixel;
    if (turns == 1)
        texel = ivec2(pixel.y, outputSize.x - 1 - pixel.x);
    else if (turns == 2)
        texel = outputSize - ivec2(1) - pixel;
    else if (turns == 3)
        texel = ivec2(outputSize.y - 1 - pixel.y, pixel.x);
    fragColor = texelFetch(content, texel, 0) * qt_Opacity;
}
