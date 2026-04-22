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
uniform float u_devcurve_outline_width;
uniform float u_devcurve_outline_alpha;
uniform float u_devcurve_base_level;

uniform vec4 u_devcurve_layer_bass_color;
uniform int u_devcurve_layer_bass_enabled;
uniform float u_devcurve_layer_bass_alpha;
uniform float u_devcurve_curve_bass[96];

uniform vec4 u_devcurve_layer_vocals_color;
uniform int u_devcurve_layer_vocals_enabled;
uniform float u_devcurve_layer_vocals_alpha;
uniform float u_devcurve_curve_vocals[96];

uniform vec4 u_devcurve_layer_mids_color;
uniform int u_devcurve_layer_mids_enabled;
uniform float u_devcurve_layer_mids_alpha;
uniform float u_devcurve_curve_mids[96];

uniform vec4 u_devcurve_layer_transients_color;
uniform int u_devcurve_layer_transients_enabled;
uniform float u_devcurve_layer_transients_alpha;
uniform float u_devcurve_curve_transients[96];
uniform int u_devcurve_order0;
uniform int u_devcurve_order1;
uniform int u_devcurve_order2;
uniform int u_devcurve_order3;

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

vec4 _draw_layer(float yCurve, vec4 color, int enabled, float alphaScale, float outlineAlpha, float x, float y, float aa, float ow) {
    if (enabled == 0) return vec4(0.0);
    // Fill below the curve (liquid body sits under the spline line).
    float inside = smoothstep(-aa, aa, y - yCurve);
    float edge = 1.0 - smoothstep(ow, ow + aa, abs(y - yCurve));
    float fillA = inside * clamp(alphaScale, 0.0, 1.0) * clamp(color.a, 0.0, 1.0);
    float lineA = edge * clamp(outlineAlpha, 0.0, 1.0);
    vec3 rgb = _apply_rainbow(color.rgb);
    vec4 outColor = vec4(rgb, fillA);
    outColor = _blend_over(outColor, vec4(vec3(1.0), lineA));
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
    float ow = clamp(u_devcurve_outline_width, 0.0004, 0.015);
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
    col = _blend_over(col, _draw_layer(y0, _layer_color_by_id(layer0), _layer_enabled_by_id(layer0), _layer_alpha_by_id(layer0), u_devcurve_outline_alpha, uv.x, uv.y, aa, ow));
    col = _blend_over(col, _draw_layer(y1, _layer_color_by_id(layer1), _layer_enabled_by_id(layer1), _layer_alpha_by_id(layer1), u_devcurve_outline_alpha, uv.x, uv.y, aa, ow));
    col = _blend_over(col, _draw_layer(y2, _layer_color_by_id(layer2), _layer_enabled_by_id(layer2), _layer_alpha_by_id(layer2), u_devcurve_outline_alpha, uv.x, uv.y, aa, ow));
    col = _blend_over(col, _draw_layer(y3, _layer_color_by_id(layer3), _layer_enabled_by_id(layer3), _layer_alpha_by_id(layer3), u_devcurve_outline_alpha, uv.x, uv.y, aa, ow));

    col.a *= u_fade;
    fragColor = col;
}
