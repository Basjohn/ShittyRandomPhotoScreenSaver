#version 460 core
// Baked for every target by tools/regen_qrc.py --shaders (its --check says whether the pack is current).
// One shader for every material; they differ only in uniforms (MaterialSurface.qml).
//   blurTint        = (blur level 0..1, tint opacity at theme alpha 0, at alpha 1, saturation)
//   lightNoise      = (luminosity pull, grain, haze toward white, smoke darkening)
//   glassLegibility = (edge highlight, refraction px, legibility shift, contrast floor)
layout(location = 0) in vec2 vLocal;
layout(location = 1) in vec2 vScreen;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 itemSize;
    float cornerRadius;
    float contentInset;
    float borderWidth;
    float opacityAdjust;
    vec4 normalColor;
    vec4 tintColor;
    vec4 textColor;
    vec4 blurTint;
    vec4 lightNoise;
    vec4 glassLegibility;
    vec4 panelLimits;
    float panelCeiling;   // dark ink: the panel's furthest lift toward white (SurfaceContrast.panelCeiling)
    float fillSurfaceEnabled;
    float borderSurfaceEnabled;
    float borderOpacityAdjust;
    vec4 borderNormalColor;
    vec4 borderTintColor;
    vec4 borderBlurTint;
    vec4 borderLightNoise;
    vec4 borderGlassLegibility;
    // The conventions include's values for this card's target (N1.4), set by MaterialSurface.qml from the window
    // that owns the target: a ShaderEffect has only this block, so the include's own block cannot reach it.
    vec4 srpssConventions;   // x 1 flips the fragment row (every backend but OpenGL); y, z, w unused here
    vec2 targetPx;           // the render target's size in pixels
    float borderPixelRatio;  // device pixels per logical unit: a card border snaps to whole device pixels (the content clip's inset rule)
};
layout(binding = 1) uniform sampler2D source;

// The conventions include's fragPixel (native/core/shaders/srpss_conventions.glsl), over this block's values: the
// fragment's pixel centre in the row convention the grain was authored in (OpenGL's), never raw gl_FragCoord.
vec2 fragPixel(vec2 targetSize) {
    return vec2(gl_FragCoord.x, srpssConventions.x > 0.5 ? targetSize.y - gl_FragCoord.y : gl_FragCoord.y);
}

// SURFACE BEGIN (identical in surface_material.frag, text_legibility.frag and
// text_legibility.vert; tests/test_surface_materials.py checks it)
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

vec3 linearRgb(vec3 c) {
    return mix(c / 12.92, pow(max((c + 0.055) / 1.055, vec3(0.0)), vec3(2.4)), step(vec3(0.04045), c));
}
vec3 encodedRgb(vec3 c) {
    c = max(c, vec3(0.0));
    return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), c));
}
float adjustedDensity(float density) {
    float amount = clamp(opacityAdjust, -1.0, 1.0);
    return amount < 0.0 ? density * (1.0 + amount) : mix(density, 1.0, amount);
}

vec3 unpremultiply(vec4 c) { return c.a > 0.0 ? c.rgb / c.a : c.rgb; }

float roundedBox(vec2 p, vec2 halfSize, float r, out vec2 normal) {
    vec2 q = abs(p) - halfSize + vec2(r);
    vec2 s = vec2(p.x < 0.0 ? -1.0 : 1.0, p.y < 0.0 ? -1.0 : 1.0);
    if (q.x > 0.0 && q.y > 0.0)
        normal = normalize(q) * s;
    else
        normal = q.x > q.y ? vec2(s.x, 0.0) : vec2(0.0, s.y);
    return length(max(q, vec2(0.0))) + min(max(q.x, q.y), 0.0) - r;
}

// An integer hash of the pixel (R-94's class; N5.2b's way): exact on every GPU, compiler and backend, where the float
// hash (fract of a product of the pixel) flipped by backend at the fract's wrap. Uniform in [0, 1), 24 bits, so the
// float is exact and the mean stays 0.5.
float grain(vec2 pixel) {
    uvec2 q = uvec2(ivec2(floor(pixel)));
    uint x = q.x * 0x9e3779b9u ^ (q.y * 0x85ebca6bu + 0x27d4eb2fu);
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return float(x >> 8) * (1.0 / 16777216.0);
}

// The card surface at card-local point p (origin at the card centre), sampled through the
// shared backdrop at this point's screen coordinate. rgb = surface, a = backdrop validity.
// grainValue is the static grain at this pixel (grain(fragPixel(targetPx))); 0.5 = none.
vec4 surfaceAt(vec2 p, vec2 cardSize, vec2 screen, vec2 uvPerUnit, float grainValue) {
    vec2 halfSize = cardSize * 0.5;
    vec2 cardUnit = p / max(cardSize, vec2(1.0)) + vec2(0.5);
    float r = clamp(cornerRadius, 0.0, min(halfSize.x, halfSize.y));
    vec2 n;
    float d = roundedBox(p, halfSize, r, n);
    float rim = 1.0 - smoothstep(0.0, max(1.0, glassLegibility.y * 3.0), -d);
    vec2 uv = screen - n * uvPerUnit * (glassLegibility.y * rim * rim);

    vec4 b = textureLod(source, uv, blurTint.x);
    float valid = clamp(b.a, 0.0, 1.0);
    vec3 c = b.a > 0.0 ? b.rgb / b.a : vec3(0.0);

    vec3 tint = unpremultiply(tintColor);
    vec3 text = unpremultiply(textColor);
    float l = luma(c);
    c = max(mix(vec3(l), c, blurTint.w), vec3(0.0));
    c += (luma(tint) - luma(c)) * (lightNoise.x > 0.0 ? adjustedDensity(lightNoise.x) : 0.0);
    c = mix(c, vec3(1.0), lightNoise.z > 0.0 ? adjustedDensity(lightNoise.z) : 0.0);
    c *= 1.0 - (lightNoise.w > 0.0 ? adjustedDensity(lightNoise.w) : 0.0);
    float tintOpacity = mix(blurTint.y, blurTint.z, clamp(tintColor.a, 0.0, 1.0));
    c = mix(c, tint, adjustedDensity(tintOpacity));

    // The edge highlight (Glass, faintly Frosted/Smoked) is added after the legibility layer
    // below, so it stays at the real border; the diagonal sheen is part of the face.
    float edgeHighlight = 0.0;
    if (glassLegibility.x > 0.0) {
        float edge = 1.0 - smoothstep(0.0, 6.0, -d);
        float facing = clamp(dot(-n, normalize(vec2(-0.55, -0.85))) * 0.5 + 0.5, 0.0, 1.0);
        float sheen = clamp(1.0 - (cardUnit.x + cardUnit.y) * 0.6, 0.0, 1.0);
        float edgeTerm = edge * edge * (0.35 + 0.65 * facing);
        // A child control (negative border width: its own outline is its border) keeps its
        // highlight under its face, as before: only a card's real border gains it.
        if (borderWidth < 0.0) {
            c += vec3(glassLegibility.x) * (edgeTerm + 0.10 * sheen);
        } else {
            c += vec3(glassLegibility.x) * (0.10 * sheen);
            edgeHighlight = glassLegibility.x * edgeTerm;
        }
    }

    vec3 unplated = c;

    // Legibility layer: the whole face, up to and under the real border (no inset panel, no
    // inner rim; Card_Surface_Materials.md 3.3). Shift away from the text colour, then hold a
    // luminance-contrast floor against it where the backdrop is busy.
    float plate = 1.0;
    float floorRatioCard = max(1.0, glassLegibility.w);
    // Work in linear light: encoded-RGB luma made the contrast floor excessively
    // dense (especially on Acrylic/Frosted). Encode only after the least adjustment.
    // Semantic density is composed in the same encoded colour space as Qt's
    // source-over surfaces. This anchor preserves the material family while its
    // relief reveals the requested fraction of the unplated material. The WCAG
    // ink guard is separate, in linear light below. Textless controls bypass it.
    if (floorRatioCard > 1.0) {
        float anchor = panelLimits.x;
        bool lightInk = panelLimits.y > 0.5;
        float currentL = luma(c);
        vec3 dense = c;
        if (lightInk && currentL > anchor && currentL > 0.0)
            dense *= max(anchor, 0.0) / currentL;
        else if (!lightInk && currentL < anchor)
            dense = mix(dense, vec3(1.0), clamp((anchor - currentL) / max(1.0 - currentL, 1e-3), 0.0, 1.0));
        float relief = 1.0 - adjustedDensity(1.0 - glassLegibility.z);
        c = mix(c, mix(dense, c, relief), plate);
    }
    // Uniform limits come from the existing style/ink solver. A channel-wise
    // encoded bound rejects already-readable pixels without pow; textless controls
    // do no linear conversion. Encode only when the linear guard changes colour.
    if (floorRatioCard > 1.0 && plate > 0.0) {
        bool lightInk = panelLimits.y > 0.5;
        bool mayNeedGuard = lightInk ? max(c.r, max(c.g, c.b)) > panelLimits.w
                                     : min(c.r, min(c.g, c.b)) < panelLimits.w;
        if (mayNeedGuard) {
            vec3 linearSurface = linearRgb(clamp(c, 0.0, 1.0));
            float cl = luma(linearSurface);
            if (lightInk && cl > panelLimits.z && cl > 0.0) {
                linearSurface *= mix(1.0, panelLimits.z / cl, plate);
                c = encodedRgb(linearSurface);
            } else if (!lightInk && cl < panelLimits.z) {
                linearSurface = mix(linearSurface, vec3(1.0), plate * clamp((panelLimits.z - cl) / max(1.0 - cl, 1e-3), 0.0, 1.0));
                c = encodedRgb(linearSurface);
            }
        }
    }
    // Dark ink (light themes): the panel moves toward its anchor only as far as the bounded
    // surface, the Settings-variant shell density (never less than the reference ink needs
    // over black); faint runs correct their own ink instead (OverlayCard.surfaceInkSolution).
    if (floorRatioCard > 1.0 && panelLimits.y <= 0.5)
        c = min(c, mix(unplated, vec3(1.0), panelCeiling * plate));
    c += vec3(edgeHighlight);

    c += (grainValue - 0.5) * lightNoise.y;
    return vec4(clamp(c, 0.0, 1.0), valid);
}
// SURFACE END

// Local units -> backdrop uv per unit (axis-aligned; the signs carry the y flip).
vec2 backdropPerUnit(vec2 p, vec2 screen) {
    float dx = dFdx(p.x);
    float dy = dFdy(p.y);
    return vec2(abs(dx) > 1e-6 ? dFdx(screen.x) / dx : 0.0,
                abs(dy) > 1e-6 ? dFdy(screen.y) / dy : 0.0);
}

// The border's material is computed only for fragments in its rounded SDF ring.
// It is not another quad, mask, scene capture or material pass. Its no-legibility
// coefficients deliberately omit the card text guard and its panel entirely.
float adjustedBorderDensity(float density) {
    float amount = clamp(borderOpacityAdjust, -1.0, 1.0);
    return amount < 0.0 ? density * (1.0 + amount) : mix(density, 1.0, amount);
}

vec4 borderAt(vec2 p, vec2 screen, vec2 uvPerUnit, float grainValue, float d, vec2 normal) {
    float rim = 1.0 - smoothstep(0.0, max(1.0, borderGlassLegibility.y * 3.0), -d);
    vec2 uv = screen - normal * uvPerUnit * (borderGlassLegibility.y * rim * rim);
    vec4 backdrop = textureLod(source, uv, borderBlurTint.x);
    float valid = clamp(backdrop.a, 0.0, 1.0);
    vec3 c = backdrop.a > 0.0 ? backdrop.rgb / backdrop.a : vec3(0.0);
    vec3 tint = unpremultiply(borderTintColor);
    float l = luma(c);
    c = max(mix(vec3(l), c, borderBlurTint.w), vec3(0.0));
    if (borderLightNoise.x > 0.0)
        c += (luma(tint) - luma(c)) * adjustedBorderDensity(borderLightNoise.x);
    if (borderLightNoise.z > 0.0)
        c = mix(c, vec3(1.0), adjustedBorderDensity(borderLightNoise.z));
    if (borderLightNoise.w > 0.0)
        c *= 1.0 - adjustedBorderDensity(borderLightNoise.w);
    float tintOpacity = mix(borderBlurTint.y, borderBlurTint.z, clamp(borderTintColor.a, 0.0, 1.0));
    c = mix(c, tint, adjustedBorderDensity(tintOpacity));
    // A restrained edge/specular response uses the authored border tint; no ink plate.
    if (borderGlassLegibility.x > 0.0) {
        float edge = 1.0 - smoothstep(0.0, 6.0, -d);
        float facing = clamp(dot(-normal, normalize(vec2(-0.55, -0.85))) * 0.5 + 0.5, 0.0, 1.0);
        c += vec3(borderGlassLegibility.x * edge * edge * (0.35 + 0.65 * facing));
    }
    c += (grainValue - 0.5) * borderLightNoise.y;
    return vec4(clamp(c, 0.0, 1.0), valid);
}

void main() {
    vec2 p = (vLocal - vec2(0.5)) * itemSize;
    vec2 halfSize = itemSize * 0.5;
    float radius = clamp(cornerRadius, 0.0, min(halfSize.x, halfSize.y));
    vec2 n;
    float d = roundedBox(p, halfSize, radius, n);
    float aa = max(fwidth(d), 0.001);
    float inside = 1.0 - smoothstep(-aa, aa, d);
    float ringCoverage = 0.0;
    if (borderSurfaceEnabled > 0.5 && borderWidth > 0.0) {
        vec2 innerNormal;
        float snappedBorder = floor(borderWidth * borderPixelRatio + 0.5) / borderPixelRatio;
        float thickness = min(snappedBorder, min(halfSize.x, halfSize.y));
        float innerD = roundedBox(p, max(halfSize - vec2(thickness), vec2(0.0)),
                                  max(0.0, radius - thickness), innerNormal);
        float innerAa = max(fwidth(innerD), 0.001);
        float innerCoverage = 1.0 - smoothstep(-innerAa, innerAa, innerD);
        ringCoverage = clamp(inside - innerCoverage, 0.0, inside);
    }

    // Border-only Visualizer: skip backdrop mapping/noise/sampling over its
    // transparent interior. Zero alpha must mean zero material work here.
    if (fillSurfaceEnabled < 0.5 && ringCoverage <= 0.0001) {
        fragColor = vec4(0.0);
        return;
    }
    vec2 uvPerUnit = backdropPerUnit(p, vScreen);
    float grainValue = grain(fragPixel(targetPx));
    vec4 face = vec4(0.0);
    // Skip fill samples entirely on border-only cards and in fully opaque border pixels.
    if (fillSurfaceEnabled > 0.5 && inside > ringCoverage + 0.0001) {
        vec4 surface = surfaceAt(p, itemSize, vScreen, uvPerUnit, grainValue);
        vec4 material = vec4(surface.rgb, 1.0);
        face = mix(normalColor, material, surface.a);
    }

    vec4 border = vec4(0.0);
    if (ringCoverage > 0.0001) {
        vec4 sampled = borderAt(p, vScreen, uvPerUnit, grainValue, d, n);
        border = mix(borderNormalColor, vec4(sampled.rgb, 1.0), sampled.a);
    }
    // Both colour values are premultiplied. The round SDF coverage is calculated
    // once for the face and the ring, including thin 1 px borders and curved corners.
    fragColor = (face * max(0.0, inside - ringCoverage) + border * ringCoverage) * qt_Opacity;
}
