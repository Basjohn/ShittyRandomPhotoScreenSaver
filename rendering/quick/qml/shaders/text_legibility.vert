#version 460 core
// Bake with PySide6 qsb: --glsl "460" -o text_legibility.vert.qsb text_legibility.vert
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
};
layout(binding = 1) uniform sampler2D source;

// SURFACE BEGIN (identical in surface_material.frag, text_legibility.frag and
// text_legibility.vert; tests/test_surface_materials.py checks it)
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

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
    c += (luma(tint) - luma(c)) * lightNoise.x;
    c = mix(c, vec3(1.0), lightNoise.z);
    c *= 1.0 - lightNoise.w;
    float tintOpacity = mix(blurTint.y, blurTint.z, clamp(tintColor.a, 0.0, 1.0));
    c = mix(c, tint, tintOpacity);

    if (glassLegibility.x > 0.0) {
        float edge = 1.0 - smoothstep(0.0, 6.0, -d);
        float facing = clamp(dot(-n, normalize(vec2(-0.55, -0.85))) * 0.5 + 0.5, 0.0, 1.0);
        float sheen = clamp(1.0 - (cardUnit.x + cardUnit.y) * 0.6, 0.0, 1.0);
        c += vec3(glassLegibility.x) * (edge * edge * (0.35 + 0.65 * facing) + 0.10 * sheen);
    }

    // Legibility layer: the card interior 2.5 px inside the border, its corners concentric
    // with the card's (radius minus the inset) and a 2 px soft edge, so it reads as one
    // deliberate inner panel. Shift away from the text colour, then hold a
    // luminance-contrast floor against it where the backdrop is busy.
    float plateInset = max(0.0, borderWidth) + 2.5;
    vec2 plateHalf = max(halfSize - vec2(plateInset), vec2(1.0));
    vec2 plateNormal;
    float pd = roundedBox(p, plateHalf, max(0.0, r - plateInset), plateNormal);
    float plate = 1.0 - smoothstep(-1.0, 1.0, pd);
    float textL = luma(text);
    float floorRatioCard = max(1.0, glassLegibility.w);
    if (textL >= 0.5) {
        c *= 1.0 - glassLegibility.z * plate;
        float maxL = (textL + 0.05) / floorRatioCard - 0.05;
        float cl = luma(c);
        if (cl > maxL && cl > 0.0)
            c *= mix(1.0, max(maxL, 0.0) / cl, plate);
    } else {
        c = mix(c, vec3(1.0), glassLegibility.z * plate);
        float minL = floorRatioCard * (textL + 0.05) - 0.05;
        float cl = luma(c);
        if (cl < minL)
            c = mix(c, vec3(1.0), plate * clamp((minL - cl) / max(1.0 - cl, 1e-3), 0.0, 1.0));
    }

    // Light themes only: a defined edge over busy wallpaper. A dark hairline right inside
    // the border and a soft highlight below it. Zero for dark tints (their look is kept).
    float edgeAmount = smoothstep(0.55, 0.7, luma(tint));
    if (edgeAmount > 0.0) {
        float inner = -d - max(0.0, borderWidth);
        float hairline = 1.0 - smoothstep(0.0, 1.25, abs(inner - 0.6));
        float highlight = (1.0 - smoothstep(1.5, 4.5, inner)) * step(1.2, inner);
        c = mix(c, c * 0.55, 0.55 * hairline * edgeAmount);
        c = mix(c, vec3(1.0), 0.35 * highlight * edgeAmount);
    }

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
