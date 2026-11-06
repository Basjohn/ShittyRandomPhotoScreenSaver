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
    vec4 normalColor;
    vec4 tintColor;
    vec4 textColor;
    vec4 blurTint;
    vec4 lightNoise;
    vec4 glassLegibility;
};
layout(binding = 1) uniform sampler2D source;

float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

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

void main() {
    vec2 halfSize = itemSize * 0.5;
    vec2 p = (vLocal - vec2(0.5)) * itemSize;
    float r = clamp(cornerRadius, 0.0, min(halfSize.x, halfSize.y));
    vec2 n;
    float d = roundedBox(p, halfSize, r, n);
    float aa = max(fwidth(d), 0.001);
    float inside = 1.0 - smoothstep(-aa, aa, d);

    // Local units -> backdrop uv (axis-aligned cards; the signs carry the y flip).
    float dx = dFdx(p.x);
    float dy = dFdy(p.y);
    vec2 uvPerUnit = vec2(abs(dx) > 1e-6 ? dFdx(vScreen.x) / dx : 0.0,
                          abs(dy) > 1e-6 ? dFdy(vScreen.y) / dy : 0.0);
    float rim = 1.0 - smoothstep(0.0, max(1.0, glassLegibility.y * 3.0), -d);
    vec2 uv = vScreen - n * uvPerUnit * (glassLegibility.y * rim * rim);

    vec4 b = textureLod(source, uv, blurTint.x);
    float valid = clamp(b.a, 0.0, 1.0);
    vec3 c = b.a > 0.0 ? b.rgb / b.a : vec3(0.0);

    float l = luma(c);
    c = max(mix(vec3(l), c, blurTint.w), vec3(0.0));
    vec3 tint = tintColor.a > 0.0 ? tintColor.rgb / tintColor.a : tintColor.rgb;
    c += (luma(tint) - luma(c)) * lightNoise.x;
    c = mix(c, vec3(1.0), lightNoise.z);
    c *= 1.0 - lightNoise.w;
    float tintOpacity = mix(blurTint.y, blurTint.z, clamp(tintColor.a, 0.0, 1.0));
    c = mix(c, tint, tintOpacity);

    if (glassLegibility.x > 0.0) {
        float edge = 1.0 - smoothstep(0.0, 6.0, -d);
        float facing = clamp(dot(-n, normalize(vec2(-0.55, -0.85))) * 0.5 + 0.5, 0.0, 1.0);
        float sheen = clamp(1.0 - (vLocal.x + vLocal.y) * 0.6, 0.0, 1.0);
        c += vec3(glassLegibility.x) * (edge * edge * (0.35 + 0.65 * facing) + 0.10 * sheen);
    }

    // Legibility layer inside the padded content area: shift away from the text colour,
    // then hold a luminance-contrast floor against it where the backdrop is busy.
    vec2 plateHalf = max(halfSize - vec2(contentInset), vec2(1.0));
    vec2 plateNormal;
    float pd = roundedBox(p, plateHalf, max(0.0, r - contentInset * 0.5), plateNormal);
    float plate = 1.0 - smoothstep(-6.0, 6.0, pd);
    vec3 text = textColor.a > 0.0 ? textColor.rgb / textColor.a : textColor.rgb;
    float textL = luma(text);
    float floorRatio = max(1.0, glassLegibility.w);
    if (textL >= 0.5) {
        c *= 1.0 - glassLegibility.z * plate;
        float maxL = (textL + 0.05) / floorRatio - 0.05;
        float cl = luma(c);
        if (cl > maxL && cl > 0.0)
            c *= mix(1.0, max(maxL, 0.0) / cl, plate);
    } else {
        c = mix(c, vec3(1.0), glassLegibility.z * plate);
        float minL = floorRatio * (textL + 0.05) - 0.05;
        float cl = luma(c);
        if (cl < minL)
            c = mix(c, vec3(1.0), plate * clamp((minL - cl) / max(1.0 - cl, 1e-3), 0.0, 1.0));
    }

    c += (grain(gl_FragCoord.xy) - 0.5) * lightNoise.y;
    vec4 material = vec4(clamp(c, 0.0, 1.0), 1.0);
    vec4 normal = normalColor;   // ShaderEffect passes colours premultiplied
    fragColor = mix(normal, material, valid) * (inside * qt_Opacity);
}
