#version 330 core
// Dev Curve: smooth full-width spline-like filled curves.

in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;
uniform float u_dpr;
uniform float u_border_width;
uniform float u_fade;
uniform int u_playing;
uniform float u_ghost_alpha;
uniform float u_rainbow_hue_offset;

uniform int u_devcurve_sample_count;
uniform float u_devcurve_base_level;

uniform vec4 u_devcurve_layer_bass_color;
uniform vec4 u_devcurve_layer_bass_outline_color;
uniform float u_devcurve_layer_bass_outline_width;
uniform int u_devcurve_layer_bass_enabled;
uniform float u_devcurve_layer_bass_alpha;
uniform float u_devcurve_curve_bass[96];

uniform vec4 u_devcurve_layer_vocals_color;
uniform vec4 u_devcurve_layer_vocals_outline_color;
uniform float u_devcurve_layer_vocals_outline_width;
uniform int u_devcurve_layer_vocals_enabled;
uniform float u_devcurve_layer_vocals_alpha;
uniform float u_devcurve_curve_vocals[96];

uniform vec4 u_devcurve_layer_mids_color;
uniform vec4 u_devcurve_layer_mids_outline_color;
uniform float u_devcurve_layer_mids_outline_width;
uniform int u_devcurve_layer_mids_enabled;
uniform float u_devcurve_layer_mids_alpha;
uniform float u_devcurve_curve_mids[96];

uniform vec4 u_devcurve_layer_transients_color;
uniform vec4 u_devcurve_layer_transients_outline_color;
uniform float u_devcurve_layer_transients_outline_width;
uniform int u_devcurve_layer_transients_enabled;
uniform float u_devcurve_layer_transients_alpha;
uniform float u_devcurve_curve_transients[96];
uniform int u_devcurve_order0;
uniform int u_devcurve_order1;
uniform int u_devcurve_order2;
uniform int u_devcurve_order3;
uniform int u_devcurve_foreground_layer_id;
uniform int u_devcurve_foreground_shadow_enabled;
uniform float u_devcurve_foreground_shadow_alpha;
uniform float u_devcurve_foreground_shadow_darken;
uniform float u_devcurve_foreground_shadow_offset;
uniform int u_devcurve_foreground_specular_enabled;
uniform float u_devcurve_foreground_specular_alpha;
uniform float u_devcurve_foreground_specular_width;
uniform float u_devcurve_foreground_specular_offset;
uniform float u_devcurve_foreground_specular_crest_bias;
uniform vec4 u_devcurve_specular_slot0;
uniform vec4 u_devcurve_specular_slot1;
uniform vec4 u_devcurve_specular_slot2;

float _sample_curve(const float curve[96], float x, int count) {
    int n = clamp(count, 2, 96);
    float p = clamp(x, 0.0, 1.0) * float(n - 1);
    int i0 = int(floor(p));
    int i1 = min(i0 + 1, n - 1);
    float t = p - float(i0);
    float y0 = curve[i0];
    float y1 = curve[i1];
    return mix(y0, y1, t);
}

vec4 _blend_over(vec4 dst, vec4 src) {
    float a = src.a + dst.a * (1.0 - src.a);
    if (a <= 1e-6) return vec4(0.0);
    vec3 c = (src.rgb * src.a + dst.rgb * dst.a * (1.0 - src.a)) / a;
    return vec4(c, a);
}

vec3 _rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    float e = 1e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 _hsv2rgb(vec3 c) {
    vec3 p = abs(fract(c.xxx + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
    vec3 rgb = clamp(p - 1.0, 0.0, 1.0);
    return c.z * mix(vec3(1.0), rgb, c.y);
}

vec3 _apply_rainbow(vec3 rgb) {
    if (u_rainbow_hue_offset <= 0.001) return rgb;
    vec3 hsv = _rgb2hsv(rgb);
    if (hsv.y < 0.01) hsv.y = 1.0;
    hsv.x = fract(hsv.x + u_rainbow_hue_offset);
    return _hsv2rgb(hsv);
}

vec4 _draw_layer(float yCurve, vec4 color, vec4 outlineColor, int enabled, float alphaScale, float x, float y, float aa, float ow) {
    if (enabled == 0) return vec4(0.0);
    // Fill below the curve (liquid body sits under the spline line).
    float inside = smoothstep(-aa, aa, y - yCurve);
    float edge = 1.0 - smoothstep(ow, ow + aa, abs(y - yCurve));
    float fillA = inside * clamp(alphaScale, 0.0, 1.0) * clamp(color.a, 0.0, 1.0);
    float lineA = edge * clamp(outlineColor.a, 0.0, 1.0);
    vec3 rgb = _apply_rainbow(color.rgb);
    vec4 outColor = vec4(rgb, fillA);
    outColor = _blend_over(outColor, vec4(outlineColor.rgb, lineA));
    return outColor;
}

float _sample_curve_by_id(int layerId, float x, int sampleCount) {
    float y = 0.5;
    if (layerId == 0) y = _sample_curve(u_devcurve_curve_bass, x, sampleCount);
    else if (layerId == 1) y = _sample_curve(u_devcurve_curve_vocals, x, sampleCount);
    else if (layerId == 2) y = _sample_curve(u_devcurve_curve_mids, x, sampleCount);
    else y = _sample_curve(u_devcurve_curve_transients, x, sampleCount);
    // Curves are authored in bottom-origin space (0=bottom, 1=top).
    // Shader UV.y is top-origin, so invert once here.
    return clamp(1.0 - y, 0.0, 1.0);
}

vec4 _layer_color_by_id(int layerId) {
    if (layerId == 0) return u_devcurve_layer_bass_color;
    if (layerId == 1) return u_devcurve_layer_vocals_color;
    if (layerId == 2) return u_devcurve_layer_mids_color;
    return u_devcurve_layer_transients_color;
}

int _layer_enabled_by_id(int layerId) {
    if (layerId == 0) return u_devcurve_layer_bass_enabled;
    if (layerId == 1) return u_devcurve_layer_vocals_enabled;
    if (layerId == 2) return u_devcurve_layer_mids_enabled;
    return u_devcurve_layer_transients_enabled;
}

float _layer_alpha_by_id(int layerId) {
    if (layerId == 0) return u_devcurve_layer_bass_alpha;
    if (layerId == 1) return u_devcurve_layer_vocals_alpha;
    if (layerId == 2) return u_devcurve_layer_mids_alpha;
    return u_devcurve_layer_transients_alpha;
}

vec4 _layer_outline_color_by_id(int layerId) {
    if (layerId == 0) return u_devcurve_layer_bass_outline_color;
    if (layerId == 1) return u_devcurve_layer_vocals_outline_color;
    if (layerId == 2) return u_devcurve_layer_mids_outline_color;
    return u_devcurve_layer_transients_outline_color;
}

float _layer_outline_width_by_id(int layerId) {
    if (layerId == 0) return u_devcurve_layer_bass_outline_width;
    if (layerId == 1) return u_devcurve_layer_vocals_outline_width;
    if (layerId == 2) return u_devcurve_layer_mids_outline_width;
    return u_devcurve_layer_transients_outline_width;
}

float _sample_curve_slope(int layerId, float x, int sampleCount) {
    float dx = max(1.0 / float(sampleCount), 0.004);
    float yL = _sample_curve_by_id(layerId, x - dx, sampleCount);
    float yR = _sample_curve_by_id(layerId, x + dx, sampleCount);
    return (yR - yL) / max(2.0 * dx, 1e-4);
}

float _sample_curve_curvature(int layerId, float x, int sampleCount) {
    float dx = max(1.0 / float(sampleCount), 0.004);
    float yL = _sample_curve_by_id(layerId, x - dx, sampleCount);
    float yC = _sample_curve_by_id(layerId, x, sampleCount);
    float yR = _sample_curve_by_id(layerId, x + dx, sampleCount);
    return (yL - 2.0 * yC + yR) / max(dx * dx, 1e-4);
}

float _specular_visibility(float x) {
    float inLeft = smoothstep(-0.16, 0.02, x);
    float inRight = 1.0 - smoothstep(1.00, 1.24, x);
    return clamp(inLeft * inRight, 0.0, 1.0);
}

float _hash11(float n) {
    return fract(sin(n) * 43758.5453123);
}

float _specular_blob(vec2 uv, vec4 slot, int layerId, int sampleCount, float width, float yOffset, float crestBias, float aa) {
    float amp = clamp(slot.z, 0.0, 1.0);
    if (amp <= 1e-4) return 0.0;
    float x = slot.x;
    float variant = clamp(slot.w, 0.0, 1.0);
    float r1 = _hash11(variant * 31.7 + 1.3);
    float r2 = _hash11(variant * 47.1 + 2.9);
    float r3 = _hash11(variant * 59.4 + 4.1);
    float xCurve = clamp(uv.x, 0.0, 1.0);
    float yCurve = _sample_curve_by_id(layerId, xCurve, sampleCount);
    float slope = _sample_curve_slope(layerId, xCurve, sampleCount);
    float curvature = _sample_curve_curvature(layerId, xCurve, sampleCount);
    float widthScale = mix(0.92, 1.58, r1) * mix(0.92, 1.18, amp);
    float rx = max(0.009, width * widthScale);
    float u = (uv.x - x) / max(rx, 1e-4);
    float absU = abs(u);
    float ry = max(0.0042, rx * mix(0.26, 0.40, r2));
    float crest = clamp(abs(curvature) * max(crestBias, 0.1) * 0.08, 0.0, 1.0);
    float offset = max(0.010, yOffset) * mix(0.82, 1.18, r3);
    float centerBend = ry * (
        0.034 * sin((u + variant * 0.73) * 3.14159)
        + 0.018 * sin((u * 2.0 + variant) * 3.14159)
        + crest * 0.020 * sin((u * 1.5 + r1) * 3.14159)
    );
    float yScale = 1.0
        + 0.035 * sin((u + variant) * 6.28318)
        + crest * 0.025 * sin((u * 1.5 + r1) * 3.14159);
    float curveNormalScale = inversesqrt(1.0 + slope * slope);
    float dy = (uv.y - (yCurve + offset + centerBend)) * curveNormalScale;
    float v = dy / max(ry * clamp(yScale, 0.94, 1.07), 1e-4);
    float shape = pow(absU, 2.85) + pow(abs(v), 2.35) - 1.0;
    float edge = max(fwidth(shape) * 0.45, 0.0008);
    float mask = 1.0 - smoothstep(-edge, edge, shape);
    float vis = _specular_visibility(x);
    return clamp(mask * vis * smoothstep(0.05, 0.22, amp), 0.0, 1.0);
}

void main() {
    float width = max(1.0, u_resolution.x);
    float height = max(1.0, u_resolution.y);
    float dpr = max(1.0, u_dpr);
    float fb_h = height * dpr;
    vec2 fc = vec2(gl_FragCoord.x / dpr, (fb_h - gl_FragCoord.y) / dpr);

    float border_w = max(1.0, u_border_width);
    float card_radius = 8.0;
    float inner_radius = max(0.0, card_radius - border_w);
    float inner_w = width - border_w * 2.0;
    float inner_h = height - border_w * 2.0;
    if (inner_w <= 0.0 || inner_h <= 0.0) { discard; }
    if (fc.x < border_w || fc.x > width - border_w || fc.y < border_w || fc.y > height - border_w) { discard; }

    if (inner_radius > 0.5) {
        float ix = fc.x - border_w;
        float iy = fc.y - border_w;
        float r = inner_radius;
        vec2 d = vec2(0.0);
        bool in_corner = false;
        if (ix < r && iy < r) { d = vec2(r - ix, r - iy); in_corner = true; }
        else if (ix > inner_w - r && iy < r) { d = vec2(ix - (inner_w - r), r - iy); in_corner = true; }
        else if (ix < r && iy > inner_h - r) { d = vec2(r - ix, iy - (inner_h - r)); in_corner = true; }
        else if (ix > inner_w - r && iy > inner_h - r) { d = vec2(ix - (inner_w - r), iy - (inner_h - r)); in_corner = true; }
        if (in_corner && (d.x * d.x + d.y * d.y) > r * r) { discard; }
    }

    vec2 uv = vec2((fc.x - border_w) / inner_w, (fc.y - border_w) / inner_h);
    float aa = max(1.15 / max(inner_h, 1.0), 0.0010);
    int sampleCount = clamp(u_devcurve_sample_count, 2, 96);

    vec4 col = vec4(0.0);

    int layer0 = clamp(u_devcurve_order0, 0, 3);
    int layer1 = clamp(u_devcurve_order1, 0, 3);
    int layer2 = clamp(u_devcurve_order2, 0, 3);
    int layer3 = clamp(u_devcurve_order3, 0, 3);
    float y0 = _sample_curve_by_id(layer0, uv.x, sampleCount);
    float y1 = _sample_curve_by_id(layer1, uv.x, sampleCount);
    float y2 = _sample_curve_by_id(layer2, uv.x, sampleCount);
    float y3 = _sample_curve_by_id(layer3, uv.x, sampleCount);
    float ow0 = clamp(_layer_outline_width_by_id(layer0), 0.0004, 0.015);
    float ow1 = clamp(_layer_outline_width_by_id(layer1), 0.0004, 0.015);
    float ow2 = clamp(_layer_outline_width_by_id(layer2), 0.0004, 0.015);
    float ow3 = clamp(_layer_outline_width_by_id(layer3), 0.0004, 0.015);
    col = _blend_over(col, _draw_layer(y0, _layer_color_by_id(layer0), _layer_outline_color_by_id(layer0), _layer_enabled_by_id(layer0), _layer_alpha_by_id(layer0), uv.x, uv.y, aa, ow0));
    col = _blend_over(col, _draw_layer(y1, _layer_color_by_id(layer1), _layer_outline_color_by_id(layer1), _layer_enabled_by_id(layer1), _layer_alpha_by_id(layer1), uv.x, uv.y, aa, ow1));
    col = _blend_over(col, _draw_layer(y2, _layer_color_by_id(layer2), _layer_outline_color_by_id(layer2), _layer_enabled_by_id(layer2), _layer_alpha_by_id(layer2), uv.x, uv.y, aa, ow2));
    col = _blend_over(col, _draw_layer(y3, _layer_color_by_id(layer3), _layer_outline_color_by_id(layer3), _layer_enabled_by_id(layer3), _layer_alpha_by_id(layer3), uv.x, uv.y, aa, ow3));

    int fgId = clamp(u_devcurve_foreground_layer_id, -1, 3);
    if (fgId >= 0 && _layer_enabled_by_id(fgId) != 0) {
        float yFg = _sample_curve_by_id(fgId, uv.x, sampleCount);
        float fgInside = smoothstep(-aa, aa, uv.y - yFg);
        vec4 fgColor = _layer_color_by_id(fgId);
        float fgAlpha = clamp(_layer_alpha_by_id(fgId), 0.0, 1.0) * clamp(fgColor.a, 0.0, 1.0);

        if (u_devcurve_foreground_shadow_enabled != 0) {
            float shadowY = yFg + clamp(u_devcurve_foreground_shadow_offset, 0.0, 0.45);
            float shadowInside = smoothstep(-aa, aa, uv.y - shadowY);
            float shadowA = shadowInside * clamp(u_devcurve_foreground_shadow_alpha, 0.0, 1.0) * fgAlpha;
            vec3 shadowRgb = fgColor.rgb * (1.0 - clamp(u_devcurve_foreground_shadow_darken, 0.0, 1.0));
            col = _blend_over(col, vec4(shadowRgb, shadowA));
        }

        if (u_devcurve_foreground_specular_enabled != 0) {
            float specW = clamp(u_devcurve_foreground_specular_width, 0.002, 0.120);
            float yOffset = max(0.010, clamp(u_devcurve_foreground_specular_offset, -0.20, 0.20));
            float crestBias = clamp(u_devcurve_foreground_specular_crest_bias, 0.0, 2.0);
            float slot0 = _specular_blob(uv, u_devcurve_specular_slot0, fgId, sampleCount, specW, yOffset, crestBias, aa);
            float slot1 = _specular_blob(uv, u_devcurve_specular_slot1, fgId, sampleCount, specW, yOffset, crestBias, aa);
            float slot2 = _specular_blob(uv, u_devcurve_specular_slot2, fgId, sampleCount, specW, yOffset, crestBias, aa);
            float sparkleMask = max(max(slot0, slot1), slot2) * fgInside;
            float clearAt = max(0.006, yOffset * 0.42);
            float clearanceMask = smoothstep(clearAt, clearAt + aa * 0.65, uv.y - yFg);
            float specA = sparkleMask * clearanceMask * clamp(u_devcurve_foreground_specular_alpha, 0.0, 1.0);
            col = _blend_over(col, vec4(vec3(1.0), specA));
        }
    }

    col.a *= u_fade;
    fragColor = col;
}
