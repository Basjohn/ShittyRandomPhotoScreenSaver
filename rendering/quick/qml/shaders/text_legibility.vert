#version 460 core
// Baked for every target by tools/regen_qrc.py --shaders (its --check says whether the pack is current).
// One rounded legibility row on a card surface material (Docs/Architecture/
// Card_Surface_Materials.md, 3.3). The row's tone is the same for every fragment, so it is
// computed here, once per vertex (four per row), not per pixel: the surface (the SURFACE block,
// identical to surface_material.frag's) at a grid of points across the row, the worst of them,
// the side to push toward and the overlay that brings every run colour to the floor there.
// The backdrop coordinate comes from the row's own position in the render target, so it
// follows pixel shift, Edit drags and CUSTOM scale with no binding.
layout(location = 0) in vec4 qt_Vertex;
layout(location = 1) in vec2 qt_MultiTexCoord0;
layout(location = 0) out vec2 vLocal;
layout(location = 1) out vec2 vScreen;
// x = the row's overlay, y = 1 lift (toward white) / 0 darken, z = the worst point's WCAG luminance.
layout(location = 2) flat out vec3 vRow;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 itemSize;
    vec2 cardSize;
    vec2 cardOffset;
    float cornerRadius;
    float contentInset;
    float borderWidth;
    float opacityAdjust;
    float rowRadius;
    float floorRatio;
    vec4 tintColor;
    vec4 textColor;
    vec4 runColor;
    vec4 secondaryRunColor;
    vec4 tertiaryRunColor;
    vec4 underlayColor;
    vec4 blurTint;
    vec4 lightNoise;
    vec4 glassLegibility;
    vec4 panelLimits;
    float panelCeiling;   // dark ink: the panel's furthest lift toward white (SurfaceContrast.panelCeiling)
    float ownOpacity;     // a run plate's own text opacity, which its overlay must not take (else 1)
    float edgeSoftness;   // px over which the plate fades in from its edge (a row: 1.5, its antialiasing)
};
layout(binding = 1) uniform sampler2D source;

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

float grain(vec2 pixel) {
    vec3 p3 = fract(vec3(pixel.xyx) * 0.1031);
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

// The card surface at card-local point p (origin at the card centre), sampled through the
// shared backdrop at this point's screen coordinate. rgb = surface, a = backdrop validity.
// grainValue is the static grain at this pixel (grain(gl_FragCoord.xy)); 0.5 = none.
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

float wcag(vec3 c) {
    vec3 l = mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.03928), c));
    return dot(l, vec3(0.2126, 0.7152, 0.0722));
}

// WCAG contrast of a run over bg; a translucent run (alpha < 1) is composited over bg first.
float contrastOver(vec3 bg, vec4 run) {
    float b = wcag(bg);
    float t = wcag(mix(bg, run.rgb, run.a));
    return (max(b, t) + 0.05) / (min(b, t) + 0.05);
}

// The overlay amount toward the pole that brings `run` to the floor over c (eight bisection
// steps, < 0.5 %; a 10 % margin covers the glyphs' own antialiasing). 0 when c already meets
// it, and 0 when even the full pole cannot (that run is on the other side of the surface).
// A translucent run too faint to reach the floor anywhere is held to its opaque colour's
// floor instead (the theme chose the fade; the row still does all it reasonably can).
float overlayFor(vec3 c, vec4 run, bool lift) {
    float ratio = floorRatio * 1.10;
    vec3 pole = lift ? vec3(1.0) : vec3(0.0);
    if (run.a < 1.0 && contrastOver(pole, run) < ratio)
        run.a = 1.0;
    if (contrastOver(c, run) >= ratio)
        return 0.0;
    if (contrastOver(pole, run) < ratio)
        return 0.0;
    float lo = 0.0;
    float hi = 1.0;
    for (int i = 0; i < 8; ++i) {
        float mid = 0.5 * (lo + hi);
        if (contrastOver(mix(c, pole, mid), run) >= ratio)
            hi = mid;
        else
            lo = mid;
    }
    return hi;
}

vec4 straight(vec4 c) { return vec4(unpremultiply(c), c.a); }

// The row's own panel fill (a stats panel, a tile, a capsule) drawn between the card
// surface and this row; premultiplied, transparent when the row sits on the card itself.
vec3 underPanel(vec3 c) { return c * (1.0 - underlayColor.a) + underlayColor.rgb; }

float rowOverlay(vec3 c, bool lift) {
    return max(overlayFor(c, straight(runColor), lift),
               max(overlayFor(c, straight(secondaryRunColor), lift),
                   overlayFor(c, straight(tertiaryRunColor), lift)));
}

vec2 screenOf(vec2 local) {
    vec4 clip = qt_Matrix * vec4(local, 0.0, 1.0);
    return clip.xy / clip.w * 0.5 + 0.5;
}

const int ROW_COLUMNS = 9;
const int ROW_LINES = 2;

out gl_PerVertex { vec4 gl_Position; };
void main() {
    vLocal = qt_MultiTexCoord0;
    gl_Position = qt_Matrix * qt_Vertex;
    vScreen = gl_Position.xy / gl_Position.w * 0.5 + 0.5;

    vec2 toCard = cardOffset - cardSize * 0.5;
    vec2 origin = screenOf(vec2(0.0));
    vec2 perUnit = screenOf(vec2(1.0)) - origin;
    vec3 samples[ROW_COLUMNS * ROW_LINES];
    float meanL = 0.0;
    for (int j = 0; j < ROW_LINES; ++j) {
        for (int i = 0; i < ROW_COLUMNS; ++i) {
            vec2 at = vec2((float(i) + 0.5) / float(ROW_COLUMNS), (float(j) + 1.0) / float(ROW_LINES + 1))
                * itemSize;
            vec3 c = underPanel(surfaceAt(toCard + at, cardSize, origin + at * perUnit, perUnit, 0.5).rgb);
            samples[j * ROW_COLUMNS + i] = c;
            meanL += wcag(c) / float(ROW_COLUMNS * ROW_LINES);
        }
    }
    // Side: away from the primary run, on the side the row's surface already is, unless the
    // floor cannot be reached there.
    float runL = wcag(unpremultiply(runColor));
    float ratio = floorRatio * 1.10;
    bool lift = meanL >= runL ? ratio * (runL + 0.05) - 0.05 <= 1.0 : (runL + 0.05) / ratio - 0.05 < 0.0;
    vec3 worst = samples[0];
    float worstL = wcag(worst);
    for (int k = 1; k < ROW_COLUMNS * ROW_LINES; ++k) {
        float l = wcag(samples[k]);
        if (lift ? l < worstL : l > worstL) {
            worst = samples[k];
            worstL = l;
        }
    }
    vRow = vec3(rowOverlay(worst, lift), lift ? 1.0 : 0.0, worstL);
}
