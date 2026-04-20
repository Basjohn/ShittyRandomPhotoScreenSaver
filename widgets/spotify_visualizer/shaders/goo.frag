#version 330 core
// Goo Mode — unified liquid field with noise-perturbed organic edges.

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
uniform float u_goo_shadow_strength;
uniform float u_goo_specular_density;
uniform float u_goo_void_size;
uniform float u_goo_threshold;


const int GOO_SOURCE_COUNT = 64;
uniform vec4 u_goo_sources[GOO_SOURCE_COUNT];


// ---- Simplex-like 2D noise for organic edge perturbation ----
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

// Fractal Brownian Motion for multi-octave organic noise
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

// ---- Metaball field ----
float metaball_influence(float r2) {
    float q = max(r2, 0.0);
    // Broad falloff for generous merging + tight peak for definition
    float broad = exp(-q * 0.65);
    float tight = exp(-q * 2.8);
    return broad * 0.50 + tight * 0.60;
}

float sample_field(vec2 p) {
    float f = 0.0;
    for (int i = 0; i < GOO_SOURCE_COUNT; i++) {
        vec4 src = u_goo_sources[i];
        float rad = max(src.z, 0.0001);
        float energy = clamp(src.w, 0.0, 1.6);
        if (rad < 0.001 && energy < 0.001) continue;
        vec2 d = p - src.xy;
        float r2 = dot(d, d) / (rad * rad);
        f += metaball_influence(r2) * (0.45 + 0.70 * energy);
    }
    return f;
}

void main() {
    float width = max(1.0, u_resolution.x);
    float height = max(1.0, u_resolution.y);
    float dpr = max(1.0, u_dpr);
    float fb_h = height * dpr;
    vec2 fc = vec2(gl_FragCoord.x / dpr, (fb_h - gl_FragCoord.y) / dpr);

    // Card interior clipping (same family as bubble shader).
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
    float aa = max(1.5 / max(inner_h, 1.0), 0.0015);
    float threshold = clamp(u_goo_threshold * 0.55, 0.16, 0.38);
    float ow = max(0.003, u_goo_outline_width * 2.0);

    // Energy drive for noise amplitude
    float drive = clamp(u_bass_energy * 0.40 + u_overall_energy * 0.35 + u_mid_energy * 0.25, 0.0, 1.3);

    // Noise-based coordinate warp for organic tendril edges
    float noise_scale = 6.0 + drive * 3.0;
    float noise_amp = 0.018 + drive * 0.022;
    vec2 warp = vec2(
        fbm(uv * noise_scale, u_time * 0.7),
        fbm(uv * noise_scale + vec2(43.0, 17.0), u_time * 0.7 + 100.0)
    ) * noise_amp;

    vec2 warped_uv = uv + warp;

    // Sample the unified metaball field
    float field = sample_field(warped_uv);

    // Edge sheet: ensures liquid always touches card edges (no floating islands)
    float d_edge = min(min(uv.x, 1.0 - uv.x), min(uv.y, 1.0 - uv.y));
    float sheet_w = 0.04 + drive * 0.02;
    float edge_boost = (1.0 - smoothstep(0.0, sheet_w, d_edge)) * (threshold + 0.15);
    field = max(field, edge_boost);

    float liquid = smoothstep(threshold - aa, threshold + aa, field);

    // Shadow: offset field sample (flat 2D silhouette)
    vec2 shadow_offset = vec2(0.012, -0.014);
    float shadow_field = sample_field(warped_uv - shadow_offset);
    shadow_field = max(shadow_field, (1.0 - smoothstep(0.0, sheet_w, d_edge + 0.02)) * (threshold + 0.15));
    float shadow_liquid = smoothstep(threshold - aa, threshold + aa, shadow_field);
    float shadow_band = shadow_liquid * (1.0 - liquid);

    // Outline: band around the threshold
    float outline = smoothstep(threshold - ow * 1.8, threshold - ow * 0.15, field)
                   * (1.0 - smoothstep(threshold + ow * 0.15, threshold + ow * 1.8, field));

    // Specular: thin streak marks along the liquid interior near edges
    // Uses field gradient direction + noise for organic streak placement
    float spec_density = clamp(u_goo_specular_density * 1.6, 0.0, 1.0);
    float field_interior = smoothstep(threshold, threshold + 0.12, field);  // only inside liquid
    float field_near_edge = 1.0 - smoothstep(threshold + 0.01, threshold + 0.18, field);  // near liquid edge
    float spec_noise = snoise(uv * 28.0 + u_time * 0.15);
    float spec_noise2 = snoise(uv * 45.0 - u_time * 0.22 + vec2(77.0, 33.0));
    // Thin streaks: high threshold on noise product
    float spec_raw = smoothstep(0.55, 0.80, spec_noise * 0.5 + 0.5)
                   * smoothstep(0.50, 0.75, spec_noise2 * 0.5 + 0.5);
    float specular = spec_raw * field_interior * field_near_edge * spec_density;

    // Composite: shadow → fill → outline → specular
    vec3 col = vec3(0.0);
    float alpha = 0.0;

    float shadow_alpha = clamp(shadow_band * u_goo_shadow_strength * 0.85, 0.0, 1.0);
    col = mix(col, u_goo_shadow_color.rgb, shadow_alpha);
    alpha = max(alpha, shadow_alpha * u_goo_shadow_color.a);

    col = mix(col, u_goo_color.rgb, liquid);
    alpha = max(alpha, liquid * u_goo_color.a);

    float outline_alpha = clamp(outline, 0.0, 1.0) * u_goo_outline_color.a;
    col = mix(col, u_goo_outline_color.rgb, outline_alpha);
    alpha = max(alpha, outline_alpha);

    col = mix(col, vec3(1.0), specular);
    alpha = max(alpha, specular);

    alpha *= u_fade;
    fragColor = vec4(col, alpha);
}
