#version 330 core
in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;
uniform float u_dpr;
uniform float u_fade;
uniform float u_time;

// Energy bands
uniform float u_bass_energy;
uniform float u_mid_energy;
uniform float u_overall_energy;

// Starfield configuration
uniform float u_star_density;
uniform float u_travel_speed;
uniform float u_star_reactivity;

// CPU-side accumulated travel (monotonic — never reverses)
uniform float u_travel_time;

// Nebula tint
uniform vec3  u_nebula_tint1;    // first colour (RGB 0-1)
uniform vec3  u_nebula_tint2;    // second colour (RGB 0-1)
uniform float u_nebula_cycle_speed;  // 0..1

// ─── Constants ───────────────────────────────────────────────
const int   NUM_LAYERS   = 6;
const float PI           = 3.14159265;

// ─── Hash functions ──────────────────────────────────────────
float hash21(vec2 p) {
    p = fract(p * vec2(443.897, 441.423));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}
vec2 hash22(vec2 p) {
    return vec2(hash21(p), hash21(p + 73.17));
}
float hash11(float p) {
    p = fract(p * 443.897);
    p += p * (p + 19.19);
    return fract(p);
}

// ─── Simplex-ish noise for nebula ────────────────────────────
float value_noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);  // smoothstep
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0;
    float amp = 0.5;
    mat2 rot = mat2(0.8, 0.6, -0.6, 0.8);
    for (int i = 0; i < 5; i++) {
        v += amp * value_noise(p);
        p = rot * p * 2.0;
        amp *= 0.5;
    }
    return v;
}

// ─── 4-point cross star shape ────────────────────────────────
// Creates a bright core with 4 tapering rays extending along
// the X and Y axes, mimicking real star diffraction spikes.
vec3 star_cross(vec2 diff, float sz, float bright, float hue, float glow_boost) {
    float d = length(diff);

    // Bright saturated core
    float core = smoothstep(sz * 0.5, 0.0, d) * 1.6;

    // 4-point diffraction spikes along axes
    // Each spike: narrow Gaussian along one axis, long along the other
    float spike_len = sz * (4.0 + glow_boost * 8.0);
    float spike_width = sz * (0.12 + glow_boost * 0.08);
    float sx = exp(-(diff.x * diff.x) / (2.0 * spike_len * spike_len))
             * exp(-(diff.y * diff.y) / (2.0 * spike_width * spike_width));
    float sy = exp(-(diff.y * diff.y) / (2.0 * spike_len * spike_len))
             * exp(-(diff.x * diff.x) / (2.0 * spike_width * spike_width));
    float spikes = (sx + sy) * (0.6 + glow_boost * 0.6);

    // Soft circular glow halo around the core
    float glow_r = sz * (2.0 + glow_boost * 4.0);
    float glow = exp(-(d * d) / (2.0 * glow_r * glow_r));
    glow *= (0.25 + glow_boost * 0.35);

    float total = core + spikes + glow;
    if (total < 0.003) return vec3(0.0);

    // Colour: warm ↔ cool variation
    vec3 cool = vec3(0.7, 0.82, 1.0);
    vec3 warm = vec3(1.0, 0.9, 0.75);
    vec3 col = mix(cool, warm, hue);

    // Bright core bleaches toward white
    float core_ratio = core / max(total, 0.001);
    col = mix(col, vec3(1.0), core_ratio * 0.7);

    return col * total * bright;
}

// ─── Nebula background ───────────────────────────────────────
vec3 nebula(vec2 uv, float t) {
    // Slowly drifting FBM clouds
    float n1 = fbm(uv * 2.5 + vec2(t * 0.02, t * 0.015));
    float n2 = fbm(uv * 3.8 + vec2(-t * 0.018, t * 0.025) + 50.0);

    // Colour cycling between tint1 and tint2
    float cycle = sin(t * max(0.01, u_nebula_cycle_speed) * 0.3) * 0.5 + 0.5;
    vec3 tint1 = u_nebula_tint1;
    vec3 tint2 = u_nebula_tint2;
    // Ensure minimum visibility even with black tint inputs
    tint1 = max(tint1, vec3(0.02, 0.03, 0.06));
    tint2 = max(tint2, vec3(0.04, 0.02, 0.05));

    vec3 neb_col = mix(tint1, tint2, cycle);

    // Shape the nebula: combine noise octaves for cloud-like wisps
    float density = smoothstep(0.3, 0.7, n1) * smoothstep(0.25, 0.65, n2);
    density *= 0.22;  // keep it subtle, not overpowering

    // Audio-reactive nebula brightness
    density *= (0.8 + u_overall_energy * u_star_reactivity * 0.5);

    return neb_col * density;
}

void main() {
    if (u_fade <= 0.0) discard;

    float width = u_resolution.x;
    float height = u_resolution.y;
    if (width <= 0.0 || height <= 0.0) discard;

    float dpr = max(u_dpr, 1.0);
    float fb_height = height * dpr;
    vec2 fc = vec2(gl_FragCoord.x / dpr, (fb_height - gl_FragCoord.y) / dpr);

    float margin_x = 8.0;
    float margin_y = 6.0;
    if (fc.x < margin_x || fc.x > width - margin_x ||
        fc.y < margin_y || fc.y > height - margin_y) discard;

    float inner_w = width - margin_x * 2.0;
    float inner_h = height - margin_y * 2.0;
    if (inner_w <= 0.0 || inner_h <= 0.0) discard;

    // Centred UV, aspect-corrected, range ~ -0.5..0.5
    vec2 uv = vec2(
        (fc.x - margin_x) / inner_h - (inner_w / inner_h) * 0.5,
        (fc.y - margin_y) / inner_h - 0.5
    );

    // ── Travel time (monotonic, CPU-accumulated) ─────────────
    // This NEVER reverses because the CPU integrates speed*dt
    float t = u_travel_time * 0.12;

    // Audio-driven glow boost for star cross-spikes
    float glow_boost = u_overall_energy * u_star_reactivity;

    // ── Nebula background ────────────────────────────────────
    vec3 col = nebula(uv, u_time);

    // ── Accumulate stars across depth layers ─────────────────
    for (int i = 0; i < NUM_LAYERS; i++) {
        // Depth cycles 0→1 (far→near) then wraps
        float z = fract(float(i) / float(NUM_LAYERS) + t);

        // Fade in from far, fade out as stars pass camera
        float fade = smoothstep(0.0, 0.2, z) * smoothstep(1.0, 0.75, z);
        if (fade < 0.01) continue;

        // Perspective: near stars expand outward, far stars cluster near centre
        float depth = mix(0.9, 0.03, z * z);

        // Star apparent size grows as z approaches (near camera = larger)
        float sz = mix(0.004, 0.055, z * z);

        // Brightness ramp: dim when far, bright when near
        float bright = mix(0.2, 1.5, z * z) * fade;

        // Grid scale: far layers = denser grid, near = coarser
        float grid_scale = mix(10.0, 2.0, z * z);
        grid_scale *= (0.5 + u_star_density * 0.8);

        vec2 scaled_uv = uv / depth;
        vec2 grid_uv = scaled_uv * grid_scale;
        vec2 cell = floor(grid_uv);
        vec2 fuv = fract(grid_uv) - 0.5;

        // Check 3×3 neighbourhood so spikes/glow aren't clipped at cell edges
        for (int cy = -1; cy <= 1; cy++) {
            for (int cx = -1; cx <= 1; cx++) {
                vec2 offset = vec2(float(cx), float(cy));
                vec2 n = cell + offset;
                vec2 seed = n + float(i) * 331.7;

                // Density gate: ~35-55% of cells have a star
                float density_gate = 0.50 - u_star_density * 0.15;
                if (hash21(seed) < density_gate) continue;

                // Star position within cell (jittered)
                vec2 star_pos = hash22(seed * 1.37) - 0.5;
                star_pos *= 0.6;

                vec2 diff = fuv - offset - star_pos;
                float d = length(diff);

                // Early-out: skip if clearly outside max spike reach
                float max_r = sz * (4.0 + glow_boost * 8.0) * 2.0;
                if (d > max_r) continue;

                // Per-star variation
                float star_bright = 0.35 + hash21(seed * 3.1) * 0.65;
                float hue = hash21(seed * 5.7);

                // Some stars are "big" stars with enhanced spikes
                float big_star = step(0.85, hash21(seed * 7.3));
                float this_sz = sz * (1.0 + big_star * 1.2);
                float this_bright = bright * star_bright * (1.0 + big_star * 0.5);

                col += star_cross(diff, this_sz, this_bright, hue, glow_boost);
            }
        }
    }

    // ── Tiny background pinpoint stars (static, no travel) ───
    // Adds depth: many faint dots that don't move, like very distant stars
    {
        vec2 bg_uv = uv * 25.0;
        vec2 bg_cell = floor(bg_uv);
        vec2 bg_fuv = fract(bg_uv) - 0.5;
        for (int by = -1; by <= 1; by++) {
            for (int bx = -1; bx <= 1; bx++) {
                vec2 boff = vec2(float(bx), float(by));
                vec2 bn = bg_cell + boff;
                vec2 bseed = bn + 999.0;
                if (hash21(bseed) < 0.55) continue;  // ~45% of cells
                vec2 bp = hash22(bseed * 1.37) - 0.5;
                bp *= 0.6;
                float bd = length(bg_fuv - boff - bp);
                float pinpoint = smoothstep(0.04, 0.0, bd) * 0.25;
                // Subtle twinkle
                float twinkle = 0.7 + 0.3 * sin(u_time * (1.5 + hash21(bseed * 2.1) * 3.0) + hash21(bseed * 4.3) * 6.28);
                float bri = pinpoint * twinkle;
                float hue = hash21(bseed * 5.7);
                vec3 star_col = mix(vec3(0.7, 0.8, 1.0), vec3(1.0, 0.9, 0.8), hue);
                col += star_col * bri;
            }
        }
    }

    // Reinhard tone-map to prevent clipping
    col = col / (col + vec3(1.0));

    fragColor = vec4(col, u_fade);
}
