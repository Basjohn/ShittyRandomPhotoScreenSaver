#version 330 core
// Goo Mode -- spline contour ring renderer (vector-smooth, no sharp corners).

in vec2 v_uv;
out vec4 fragColor;

uniform float u_time;
uniform vec2 u_resolution;
uniform float u_dpr;
uniform float u_border_width;
uniform float u_fade;
uniform int u_playing;
uniform float u_ghost_alpha;

uniform float u_overall_energy;
uniform float u_bass_energy;
uniform float u_mid_energy;
uniform float u_high_energy;

uniform vec4 u_goo_color;
uniform vec4 u_goo_outline_color;
uniform vec4 u_goo_shadow_color;
uniform float u_goo_outline_width;
uniform float u_goo_inward_outline_width;
uniform float u_goo_shadow_strength;
uniform float u_goo_specular_density;
uniform float u_goo_void_size;
uniform float u_goo_threshold;

const int GOO_SOURCE_COUNT = 64;
const int CURVE_SUB_STEPS = 4;
uniform vec4 u_goo_sources[GOO_SOURCE_COUNT];

vec3 permute(vec3 x) { return mod(((x * 34.0) + 1.0) * x, 289.0); }

float snoise(vec2 v) {
    const vec4 C = vec4(0.211324865405187, 0.366025403784439,
                       -0.577350269189626, 0.024390243902439);
    vec2 i  = floor(v + dot(v, C.yy));
    vec2 x0 = v - i + dot(i, C.xx);
    vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
    vec4 x12 = x0.xyxy + C.xxzz;
    x12.xy -= i1;
    i = mod(i, 289.0);
    vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
    vec3 m = max(0.5 - vec3(dot(x0, x0), dot(x12.xy, x12.xy), dot(x12.zw, x12.zw)), 0.0);
    m = m * m;
    m = m * m;
    vec3 x_ = 2.0 * fract(p * C.www) - 1.0;
    vec3 h = abs(x_) - 0.5;
    vec3 ox = floor(x_ + 0.5);
    vec3 a0 = x_ - ox;
    m *= 1.79284291400159 - 0.85373472095314 * (a0 * a0 + h * h);
    vec3 g;
    g.x = a0.x * x0.x + h.x * x0.y;
    g.yz = a0.yz * x12.xz + h.yz * x12.yw;
    return 130.0 * dot(m, g);
}

float fbm(vec2 p, float t) {
    float val = 0.0;
    float amp = 0.5;
    vec2 shift = vec2(100.0);
    for (int i = 0; i < 4; i++) {
        val += amp * snoise(p + t * 0.08);
        p = p * 2.05 + shift;
        amp *= 0.48;
        t *= 1.1;
    }
    return val;
}

int wrap_idx(int i, int n) {
    int r = i % n;
    return (r < 0) ? (r + n) : r;
}

vec2 goo_point(int i) {
    return u_goo_sources[i].xy;
}

int goo_point_count() {
    int count = 0;
    for (int i = 0; i < GOO_SOURCE_COUNT; i++) {
        if (u_goo_sources[i].z > 0.001) {
            count += 1;
        }
    }
    return count;
}

float segment_distance(vec2 p, vec2 a, vec2 b, float metric_x) {
    vec2 pm = vec2(p.x * metric_x, p.y);
    vec2 am = vec2(a.x * metric_x, a.y);
    vec2 bm = vec2(b.x * metric_x, b.y);
    vec2 ab = bm - am;
    float h = dot(pm - am, ab) / max(dot(ab, ab), 1e-6);
    h = clamp(h, 0.0, 1.0);
    return length((am + ab * h) - pm);
}

vec2 catmull(vec2 p0, vec2 p1, vec2 p2, vec2 p3, float t) {
    float t2 = t * t;
    float t3 = t2 * t;
    return 0.5 * (
        (2.0 * p1) +
        (-p0 + p2) * t +
        (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 +
        (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
    );
}

float contour_distance(vec2 p, int count, float metric_x) {
    float d = 10.0;
    for (int i = 0; i < GOO_SOURCE_COUNT; i++) {
        if (i >= count) break;
        vec2 p0 = goo_point(wrap_idx(i - 1, count));
        vec2 p1 = goo_point(i);
        vec2 p2 = goo_point(wrap_idx(i + 1, count));
        vec2 p3 = goo_point(wrap_idx(i + 2, count));
        vec2 prev = p1;
        for (int s = 1; s <= CURVE_SUB_STEPS; s++) {
            float t = float(s) / float(CURVE_SUB_STEPS);
            vec2 cur = catmull(p0, p1, p2, p3, t);
            d = min(d, segment_distance(p, prev, cur, metric_x));
            prev = cur;
        }
    }
    return d;
}

bool point_in_polygon(vec2 p, int count) {
    bool inside = false;
    for (int i = 0; i < GOO_SOURCE_COUNT; i++) {
        if (i >= count) break;
        vec2 a = goo_point(i);
        vec2 b = goo_point(wrap_idx(i + 1, count));
        bool crosses = ((a.y > p.y) != (b.y > p.y));
        if (!crosses) continue;
        float denom = b.y - a.y;
        if (abs(denom) < 1e-6) continue;
        float x_at_y = ((b.x - a.x) * (p.y - a.y) / denom) + a.x;
        if (p.x < x_at_y) inside = !inside;
    }
    return inside;
}

float contour_signed_distance(vec2 p, int count, float metric_x) {
    float d = contour_distance(p, count, metric_x);
    bool inside = point_in_polygon(p, count);
    return inside ? -d : d;
}

float sd_round_rect_px(vec2 p, vec2 half_size, float radius) {
    vec2 q = abs(p) - (half_size - vec2(radius));
    return length(max(q, vec2(0.0))) + min(max(q.x, q.y), 0.0) - radius;
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

    if (fc.x < border_w || fc.x > width - border_w ||
        fc.y < border_w || fc.y > height - border_w) {
        discard;
    }

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
    float ow = clamp(u_goo_outline_width, 0.00035, 0.010);
    float inward_ow = clamp(u_goo_inward_outline_width, 0.00025, 0.010);

    int count = goo_point_count();
    if (count < 3) {
        fragColor = vec4(0.0);
        return;
    }

    float drive = clamp(u_bass_energy * 0.40 + u_overall_energy * 0.34 + u_mid_energy * 0.19 + u_high_energy * 0.07, 0.0, 1.3);
    float metric_x = inner_w / max(inner_h, 1.0);
    float sd = contour_signed_distance(uv, count, metric_x);

    // Keep threshold meaningful for contour scale bias.
    float threshold_bias = (clamp(u_goo_threshold, 0.0, 1.0) - 0.5) * 0.07;
    sd += threshold_bias;

    float center_fill = 1.0 - smoothstep(-aa, aa, sd);
    // Center outline follows the exact same spline contour as fill.
    float outline = 1.0 - smoothstep(ow, ow + aa, abs(sd));

    // Outer reactive base layer: rounded and even on all four sides.
    vec2 inner_center = vec2(inner_w * 0.5, inner_h * 0.5);
    vec2 p_px = vec2(fc.x - border_w, fc.y - border_w) - inner_center;
    float min_dim = min(inner_w, inner_h);
    float aa_px = max(aa * min_dim, 1.0);
    float inset_px = (0.028 + drive * 0.010) * min_dim + clamp(u_goo_void_size, 0.0, 0.10) * min_dim * 0.55;
    float corner_r = max(10.0, min_dim * 0.16);
    vec2 half_inner = vec2(inner_w * 0.5 - inset_px, inner_h * 0.5 - inset_px);
    float sd_outer_inner = sd_round_rect_px(p_px, half_inner, corner_r);
    float outer_fill = smoothstep(-aa_px, aa_px, sd_outer_inner);
    float inward_ow_px = max(1.0, inward_ow * min_dim);
    float outer_outline = 1.0 - smoothstep(inward_ow_px, inward_ow_px + aa_px, abs(sd_outer_inner));

    // Subtle shadow on the center boundary only.
    float shadow = (1.0 - smoothstep(0.0, 0.020, sd)) * smoothstep(-0.030, -0.004, sd) * 0.45;
    shadow *= clamp(u_goo_shadow_strength, 0.0, 1.0);

    // Specular streaks only on filled center near the inner border.
    float spec_density = clamp(u_goo_specular_density * 1.35, 0.0, 1.0);
    float edge_center = center_fill * smoothstep(-0.020, -0.002, sd);
    float spec_noise = fbm(uv * 8.5 + vec2(17.0, 31.0), u_time * 0.18 + drive * 0.3) * 0.5 + 0.5;
    float spec_mask = smoothstep(0.69, 0.87, spec_noise);
    float specular = edge_center * spec_mask * spec_density * (0.65 + drive * 0.35);

    vec3 col = vec3(0.0);
    float alpha = 0.0;

    vec3 outer_base = mix(u_goo_shadow_color.rgb, u_goo_color.rgb, 0.78);
    float outer_alpha = outer_fill * (0.58 + drive * 0.16) * clamp(u_goo_color.a, 0.0, 1.0);
    col = mix(col, outer_base, outer_alpha);
    alpha = max(alpha, outer_alpha);

    float outer_outline_alpha = outer_outline * u_goo_outline_color.a * 0.95;
    col = mix(col, u_goo_outline_color.rgb, outer_outline_alpha);
    alpha = max(alpha, outer_outline_alpha);

    col = mix(col, u_goo_shadow_color.rgb, shadow);
    alpha = max(alpha, shadow * u_goo_shadow_color.a);

    col = mix(col, u_goo_color.rgb, center_fill);
    alpha = max(alpha, center_fill * u_goo_color.a);

    float outline_alpha = outline * u_goo_outline_color.a;
    col = mix(col, u_goo_outline_color.rgb, outline_alpha);
    alpha = max(alpha, outline_alpha);

    col = mix(col, vec3(1.0), specular);
    alpha = max(alpha, specular);

    alpha *= u_fade;
    fragColor = vec4(col, alpha);
}
