#version 460 core
// Bake with PySide6 qsb: --glsl "460" -o surface_material.frag.qsb surface_material.frag
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
    vec4 normalColor;
    vec4 tintColor;
    vec4 textColor;
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

// Local units -> backdrop uv per unit (axis-aligned; the signs carry the y flip).
vec2 backdropPerUnit(vec2 p, vec2 screen) {
    float dx = dFdx(p.x);
    float dy = dFdy(p.y);
    return vec2(abs(dx) > 1e-6 ? dFdx(screen.x) / dx : 0.0,
                abs(dy) > 1e-6 ? dFdy(screen.y) / dy : 0.0);
}

void main() {
    vec2 p = (vLocal - vec2(0.5)) * itemSize;
    vec2 halfSize = itemSize * 0.5;
    vec2 n;
    float d = roundedBox(p, halfSize, clamp(cornerRadius, 0.0, min(halfSize.x, halfSize.y)), n);
    float aa = max(fwidth(d), 0.001);
    float inside = 1.0 - smoothstep(-aa, aa, d);
    vec4 surface = surfaceAt(p, itemSize, vScreen, backdropPerUnit(p, vScreen), grain(gl_FragCoord.xy));
    vec4 material = vec4(surface.rgb, 1.0);
    vec4 normal = normalColor;   // ShaderEffect passes colours premultiplied
    fragColor = mix(normal, material, surface.a) * (inside * qt_Opacity);
}
