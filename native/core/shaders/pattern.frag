#version 440
// The surface pattern pass (Current_Plan.md item 8b, N2.4; native/core/src/surfaces.h): N2.4's harness content. Each
// texel writes its own index (fragTexel of a target the core owns: texel (0,0) is the top-left in memory on every
// backend, N0.3 F1), so a composite that maps texels one to one shows every index exactly once; or opaque white, the
// brightest content touching every edge and corner of the target.
#define SRPSS_NATIVE_CORE
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions

layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform Pattern {
    vec4 targetSize;   // xy: the target in pixels
    vec4 pattern;      // x: 0 the texel's index, 1 opaque white, 2 transparent (the surface's clear, N29 round 2 M4)
};

void main()
{
    if (pattern.x > 1.5) {
        fragColor = vec4(0.0);
        return;
    }
    if (pattern.x > 0.5) {
        fragColor = vec4(1.0);
        return;
    }
    ivec2 texel = fragTexel(ivec2(targetSize.xy));
    int high = ((texel.x >> 8) & 15) | (((texel.y >> 8) & 15) << 4);
    fragColor = vec4(float(texel.x & 255), float(texel.y & 255), float(high), 255.0) / 255.0;
}
