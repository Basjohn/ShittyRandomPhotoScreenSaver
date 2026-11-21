#version 460 core
// The Oscilloscope graticule (rendering/quick/visualizer/implementations/oscilloscope.py; the native core draws the same
// file): one quad over the scope's screen, drawn before the beam.
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#else
#define srpssVertexIndex gl_VertexID
#endif
#include "oscilloscope_graticule_block.glsl"
// The drawing happens in the rotated (logical) space; only the final position turns into the item's physical space, a
// rigid quarter turn (the shared quad's logicalUvFromPhysicalUv inverted).
vec2 physicalPoint(vec2 p) {
    int q = uContentRotationQuarters & 3;
    if (q == 1) return vec2(u_resolution.y - p.y, p.x);
    if (q == 2) return vec2(u_resolution.x - p.x, u_resolution.y - p.y);
    if (q == 3) return vec2(p.y, u_resolution.x - p.x);
    return p;
}
layout(location = 0) out vec2 vUnit;
void main() {
    vec2 corner = vec2(float(srpssVertexIndex & 1), float(srpssVertexIndex >> 1));
    vUnit = corner * 2.0 - 1.0;
    gl_Position = uMatrix * vec4(physicalPoint(uScreen.xy + corner * uScreen.zw), 0.0, 1.0);
}
