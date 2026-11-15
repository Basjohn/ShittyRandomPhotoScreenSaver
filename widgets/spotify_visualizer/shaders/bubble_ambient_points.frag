#version 460 core
layout(std140, binding = 18) uniform BubbleAmbientPoints {
    float uTexelScale;
    float uSpriteScale;
    float uGlowSpread;
    vec4 uMicroColor;
    vec4 uParticleColor;
};
layout(location = 0) in float vOpacity;
layout(location = 1) in float vGlow;
layout(location = 2) in float vClass;
layout(location = 3) in float vCoreRatio;
layout(location = 4) in float vSpriteRadius;
layout(location = 5) in float vCoreRadius;
layout(location = 6) in float vHaloRadius;


layout(location=0) out vec4 fragColor;   // premultiplied sRGB coverage (8-bit)
layout(location=1) out vec4 fragLight;   // linear-light radiance (half float .rgb), additive

vec3 srgbToLinear(vec3 c) {
    return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

void main() {
    vec2 p = 2.0 * (gl_PointCoord - vec2(0.5));
    float d = length(p);
    if (d > 1.0) discard;
    float alpha;
    vec3 rgb;
    vec3 light = vec3(0.0);
    if (vClass < 0.5) {
        float ring = smoothstep(0.43,0.68,d) * (1.0-smoothstep(0.68,0.96,d));
        float glass = (1.0-smoothstep(0.10,0.90,d))*0.10;
        float glint = (1.0-smoothstep(0.0,0.30,length(p-vec2(-0.38,0.32))))*0.60;
        alpha = clamp(ring + glass + glint,0.0,1.0) * uMicroColor.a;
        rgb = mix(uMicroColor.rgb,vec3(1.0),glint*0.28);
    } else {
        // Distances in texels from the true (sub-pixel) centre: gl_PointCoord is
        // exact, so the profile is shift-invariant as the particle drifts.
        float r = d * vSpriteRadius;
        // Fixed physical core, never breathing. It keeps the accepted edge
        // (half coverage at 0.775 of the authored radius, softening with size),
        // but a core too small to sample is spread to a 1.1-texel radius with
        // its area share of the light and an edge of at least one texel, so
        // its total light no longer depends on where it falls between pixel
        // centres (sub-pixel cores used to twinkle and vanish). Coverage blends
        // in sRGB, so its share takes the display-gamma inverse: on dark water
        // the spread core keeps the same total light.
        float edgeRadius = 0.775 * vCoreRadius;
        float coreRadius = max(edgeRadius, 1.1);
        float coreEnergy = min(1.0, (edgeRadius * edgeRadius) / (coreRadius * coreRadius));
        float edge = max(1.0, 0.275 * vCoreRadius);
        float coreShape = 1.0 - smoothstep(coreRadius - edge, coreRadius + edge, r);
        alpha = pow(coreEnergy, 1.0 / 2.2) * coreShape * uParticleColor.a;
        rgb = uParticleColor.rgb;
        float response = clamp(max(0.0, vGlow) / 3.0, 0.0, 1.0);
        if (response > 0.0 && vHaloRadius > 0.0) {
            // Emitted light in LINEAR light: a hot core (the core itself shining,
            // so it can exceed its own surface colour) and one smooth halo that
            // falls monotonically from the core (no dark moat), with a tight bloom
            // and a soft inverse-square-like tail, in the particle's own hue with
            // its chroma deepened (neutral colours stay neutral).
            vec3 lin = srgbToLinear(uParticleColor.rgb);
            float luma = dot(lin, vec3(0.2126, 0.7152, 0.0722));
            vec3 hue = max(mix(vec3(luma), lin, 1.6), vec3(0.0));
            float x = r / vHaloRadius;
            float bloom = exp(-x * x * 30.0);
            float tail = 1.0 / (1.0 + 25.0 * x * x);
            float fade = 1.0 - smoothstep(0.5, 1.0, x);
            float halo = (0.5 * bloom + 0.5 * tail) * fade;
            light = (lin * coreEnergy * coreShape * 1.6 + hue * halo) * response * uParticleColor.a;
        }
    }
    alpha = clamp(alpha*vOpacity,0.0,1.0);
    light *= vOpacity;
    if (alpha < 0.002 && max(max(light.r, light.g), light.b) <= 0.0) discard;
    // Coverage keeps the accepted premultiplied over-blend; light is additive
    // radiance that may exceed 1 where halos overlap (the Bubble shader maps it).
    fragColor = vec4(rgb * alpha, alpha);
    fragLight = vec4(light, 0.0);
}
