#version 460 core
// Bake with PySide6 qsb: --glsl "460" -o text_legibility.frag.qsb text_legibility.frag
// Per-text-run legibility plate (Docs/Architecture/Card_Surface_Materials.md, 3.3). It
// evaluates the card surface exactly as surface_material.frag does (the SURFACE block is
// identical; tests/test_surface_materials.py checks it) at this pixel's card-local point,
// then outputs the smallest overlay (away from the text, on the side the surface is
// already on) that brings this run's own colour to `floorRatio` WCAG contrast. Where the
// surface already meets it the output is exactly transparent.
layout(location = 0) in vec2 vLocal;
layout(location = 1) in vec2 vScreen;
layout(location = 0) out vec4 fragColor;
layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    vec2 itemSize;
    vec2 cardSize;
    vec2 cardOffset;
    float cornerRadius;
    float contentInset;
    float borderWidth;
    float feather;
    float floorRatio;
    vec4 tintColor;
    vec4 textColor;
    vec4 runColor;
    vec4 blurTint;
    vec4 lightNoise;
    vec4 glassLegibility;
};
layout(binding = 1) uniform sampler2D source;

// SURFACE BEGIN (identical in surface_material.frag and text_legibility.frag;
// tests/test_surface_materials.py checks it)
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
// shared backdrop at this fragment's screen coordinate. rgb = surface, a = backdrop validity.
vec4 surfaceAt(vec2 p, vec2 cardSize, vec2 screen, vec2 uvPerUnit) {
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

    // Legibility layer inside the padded content area: shift away from the text colour,
    // then hold a luminance-contrast floor against it where the backdrop is busy.
    vec2 plateHalf = max(halfSize - vec2(contentInset), vec2(1.0));
    vec2 plateNormal;
    float pd = roundedBox(p, plateHalf, max(0.0, r - contentInset * 0.5), plateNormal);
    float plate = 1.0 - smoothstep(-6.0, 6.0, pd);
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

    c += (grain(gl_FragCoord.xy) - 0.5) * lightNoise.y;
    return vec4(clamp(c, 0.0, 1.0), valid);
}

// Local units -> backdrop uv per unit (axis-aligned; the signs carry the y flip).
vec2 backdropPerUnit(vec2 p, vec2 screen) {
    float dx = dFdx(p.x);
    float dy = dFdy(p.y);
    return vec2(abs(dx) > 1e-6 ? dFdx(screen.x) / dx : 0.0,
                abs(dy) > 1e-6 ? dFdy(screen.y) / dy : 0.0);
}
// SURFACE END

float wcag(vec3 c) {
    vec3 l = mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.03928), c));
    return dot(l, vec3(0.2126, 0.7152, 0.0722));
}

void main() {
    vec2 local = vLocal * itemSize;
    vec2 p = cardOffset + local - cardSize * 0.5;
    vec4 surface = surfaceAt(p, cardSize, vScreen, backdropPerUnit(local, vScreen));
    vec3 c = surface.rgb;

    // Bisection on the overlay amount t (monotonic), eight steps (< 0.5 %). The small
    // margin covers the glyphs' own antialiasing against the floor.
    vec3 run = unpremultiply(runColor);
    float runL = wcag(run);
    float base = wcag(c);
    float ratio = floorRatio * 1.10;
    float lighter = ratio * (runL + 0.05) - 0.05;
    float darker = (runL + 0.05) / ratio - 0.05;
    bool lift = base >= runL ? lighter <= 1.0 : darker < 0.0;
    vec3 pole = lift ? vec3(1.0) : vec3(0.0);
    float need = lift ? lighter : darker;
    float t = 0.0;
    if (lift ? base < need : base > need) {
        float lo = 0.0;
        float hi = 1.0;
        for (int i = 0; i < 8; ++i) {
            float mid = 0.5 * (lo + hi);
            float m = wcag(mix(c, pole, mid));
            if (lift ? m >= need : m <= need)
                hi = mid;
            else
                lo = mid;
        }
        t = hi;
    }

    // Soft rounded plate around the glyph box: full inside, feathered to zero at its edge.
    vec2 plateHalf = itemSize * 0.5;
    vec2 q = local - plateHalf;
    vec2 unused;
    float pr = min(feather * 2.0, min(plateHalf.x, plateHalf.y));
    float pd = roundedBox(q, plateHalf, pr, unused);
    float mask = 1.0 - smoothstep(-feather, 0.0, pd);

    float a = t * mask * surface.a * qt_Opacity;
    fragColor = vec4(pole * a, a);
}
