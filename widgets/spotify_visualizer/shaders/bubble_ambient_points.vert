#version 460 core
layout(std140, binding = 18) uniform BubbleAmbientPoints {
    float uTexelScale;
    float uSpriteScale;
    float uGlowSpread;
    vec4 uMicroColor;
    vec4 uParticleColor;
};
layout(location=0) in vec4 aPoint;  // normalized x/y, logical diameter px, opacity
layout(location=1) in vec2 aOther;  // glow, class 0 microbubble / 1 particle



layout(location = 0) out float vOpacity;
layout(location = 1) out float vGlow;
layout(location = 2) out float vClass;
layout(location = 3) out float vCoreRatio;
layout(location = 4) out float vSpriteRadius;  // texels
layout(location = 5) out float vCoreRadius;    // texels, the authored physical core
layout(location = 6) out float vHaloRadius;    // texels, where the light reaches zero
void main() {
    // The FBO is in the unrotated *content* coordinate system. Sampling from
    // Bubble's logical UV maps the decoration through the same physical camera,
    // including quarter turns and extreme CUSTOM viewport shape changes.
    gl_Position = vec4(aPoint.x * 2.0 - 1.0, 1.0 - aPoint.y * 2.0, 0.0, 1.0);
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
    gl_PointSize = clamp(size, 1.0, 128.0);
    vSpriteRadius = 0.5 * gl_PointSize;
    vCoreRadius = 0.5 * coreDiameterPx;
    vCoreRatio = min(1.0, coreDiameterPx / gl_PointSize);
    vOpacity = aPoint.w;
    vGlow = aOther.x;
    vClass = aOther.y;
}
