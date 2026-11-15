#version 460 core
// Bubble's ambient points (bubble_ambient_gl.py; the native core draws the same file): one instanced quad a point
// (D15 point 5: a strip of 4, the point as the instance), drawn into the ambient target in content coordinates.
#ifdef VULKAN
#define srpssVertexIndex gl_VertexIndex
#define srpssInstanceIndex gl_InstanceIndex
#else
#define srpssVertexIndex gl_VertexID
#define srpssInstanceIndex gl_InstanceID
#endif
//@srpss_conventions
//@srpss_geometry
layout(std140, binding = 18) uniform BubbleAmbientPoints {
    float uTexelScale;
    float uSpriteScale;
    float uGlowSpread;
    vec4 uMicroColor;
    vec4 uParticleColor;
    vec2 u_target_px;    // the ambient target's content size in texels (the native core's member for the drawn target)
};
layout(location=0) in vec4 aPoint;  // per instance: normalized x/y, logical diameter px, opacity
layout(location=1) in vec2 aOther;  // per instance: glow, class 0 microbubble / 1 particle
layout(location = 0) out float vOpacity;
layout(location = 1) out float vGlow;
layout(location = 2) out float vClass;
layout(location = 3) out float vCoreRatio;
layout(location = 4) out float vSpriteRadius;  // texels
layout(location = 5) out float vCoreRadius;    // texels, the authored physical core
layout(location = 6) out float vHaloRadius;    // texels, where the light reaches zero
layout(location = 7) out vec2 vSpriteCoord;    // gl_PointCoord's orientation: (0, 0) the sprite's top-left
void main() {
    // The target is in the unrotated *content* coordinate system. Sampling from
    // Bubble's logical UV maps the decoration through the same physical camera,
    // including quarter turns and extreme CUSTOM viewport shape changes.
    vec4 centre = vec4(srpssTopDownClip(aPoint.xy), 0.0, 1.0);
    float coreDiameterPx = aPoint.z * uTexelScale * uSpriteScale;
    float size = coreDiameterPx;
    vHaloRadius = 0.0;
    if (aOther.y > 0.5) {
        // The core's drawn extent: at least 2.2 texels across (spread below
        // that), plus its filter edge (>= 1 texel each side) and a texel margin.
        float coreExtent = 2.0 * max(0.3875 * coreDiameterPx, 1.1) + 2.0 * max(1.0, 0.1375 * coreDiameterPx) + 2.0;
        // Light-only footprint, explicitly tunable. It follows the light (the
        // glow strength and Glow Spread) and never the musical core size, and
        // a sub-texel core keeps a legible halo (sized from its 2-texel floor).
        float haloDiameter = aOther.x > 0.001
            ? max(coreDiameterPx, 2.0) * mix(8.0, 12.0, clamp(aOther.x / 6.0, 0.0, 1.0))
                * clamp(uGlowSpread, 0.6, 2.0)
            : 0.0;
        size = max(coreExtent, haloDiameter);
        vHaloRadius = 0.5 * min(haloDiameter, 128.0);
    }
    // The point's size limit stays this consumer's (D15 point 5).
    float spriteSize = clamp(size, 1.0, 128.0);
    vec2 corner = srpssSpriteCorner(srpssVertexIndex);
    gl_Position = srpssSpriteClip(centre, corner, spriteSize, u_target_px);
    vSpriteCoord = corner;
    vSpriteRadius = 0.5 * spriteSize;
    vCoreRadius = 0.5 * coreDiameterPx;
    vCoreRatio = min(1.0, coreDiameterPx / spriteSize);
    vOpacity = aPoint.w;
    vGlow = aOther.x;
    vClass = aOther.y;
}
