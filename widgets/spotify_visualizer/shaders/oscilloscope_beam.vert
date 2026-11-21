#version 460 core
// The Oscilloscope beam (rendering/quick/visualizer/implementations/oscilloscope.py; the native core draws the same
// file): one instanced quad a segment of every trace (a strip of 4, the segment as the instance), its endpoints read
// from the traces' points (the storage buffer at binding 3), laid out in the rotated (logical) content and turned into
// the item's physical space at the end.
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#define srpssInstanceIndex gl_InstanceIndex
#else
#define srpssVertexIndex gl_VertexID
#define srpssInstanceIndex gl_InstanceID
#endif
#include "oscilloscope_beam_block.glsl"
layout(std430, binding = 3) readonly buffer OscPoints { vec2 oscPoint[]; };
// The drawing happens in the rotated (logical) space; only the final position turns into the item's physical space, a
// rigid quarter turn (the shared quad's logicalUvFromPhysicalUv inverted).
vec2 physicalPoint(vec2 p) {
    int q = uContentRotationQuarters & 3;
    if (q == 1) return vec2(u_resolution.y - p.y, p.x);
    if (q == 2) return vec2(u_resolution.x - p.x, u_resolution.y - p.y);
    if (q == 3) return vec2(p.y, u_resolution.x - p.x);
    return p;
}
layout(location = 0) out vec2 vLocal;
layout(location = 1) out vec2 vA;
layout(location = 2) out vec2 vB;
layout(location = 3) flat out float vAlpha;
layout(location = 4) flat out float vLength;
layout(location = 5) flat out float vRadius;   // the segment's distance from the centre (units)
layout(location = 6) flat out float vCore;     // the beam's half width (px)
layout(location = 7) flat out float vFocus;    // the segment length (px) still drawn at full brightness
void main() {
    // The flare widens the beam; the quad reaches two pixels past it, and the Trace runs past the item's edges by the
    // reach and two pixels more (its round caps under the card's clip).
    float core = uCoreBase * u_widen;
    float reach = core + 2.0 * uPixel;
    vec2 scale = uTrace == 1 ? vec2(max(1.0, uLayout.x + (reach + 2.0 * uPixel)), uLayout.y) : uLayout.zz;
    float drawn = uTrace == 1 ? 2.0 * scale.x : uLayout.w;
    int segments = u_points - 1;
    int trace = srpssInstanceIndex / segments;
    int base = trace * u_points + (srpssInstanceIndex - trace * segments);
    // Every read stays inside the points buffer whatever the counts say (no robust buffer access).
    int last = oscPoint.length() - 1;
    vec2 pointA = oscPoint[min(base, last)];
    vec2 pointB = oscPoint[min(base + 1, last)];
    vec2 centre = uField.xy + 0.5 * uField.zw;
    vec2 a = centre + pointA * vec2(scale.x, -scale.y);
    vec2 b = centre + pointB * vec2(scale.x, -scale.y);
    vec2 d = b - a;
    float len = length(d);
    vec2 dir = len > 1e-4 ? d / len : vec2(1.0, 0.0);
    vec2 normal = vec2(-dir.y, dir.x);
    float side = (srpssVertexIndex & 1) == 1 ? 1.0 : -1.0;
    vec2 end = srpssVertexIndex < 2 ? a - dir * reach : b + dir * reach;
    vLocal = end + normal * side * reach;
    vA = a;
    vB = b;
    vAlpha = u_alpha[clamp(trace, 0, 15)];
    vLength = len;
    vRadius = length(0.5 * (pointA + pointB));
    vCore = core;
    vFocus = 2.5 * drawn / float(max(1, segments));
    gl_Position = uMatrix * vec4(physicalPoint(vLocal), 0.0, 1.0);
}
