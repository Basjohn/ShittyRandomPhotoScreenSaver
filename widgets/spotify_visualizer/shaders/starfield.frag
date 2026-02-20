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
uniform vec3  u_nebula_tint1;
uniform vec3  u_nebula_tint2;
uniform float u_nebula_cycle_speed;
uniform float u_rainbow_hue_offset; // 0..1 hue rotation (0 = disabled)

const int   NUM_LAYERS = 5;
const float PI         = 3.14159265;

// ─── Hash functions ──────────────────────────────────────────
float hash21(vec2 p) {
    p = fract(p * vec2(443.897, 441.423));
    p += dot(p, p + 19.19);
    return fract(p.x * p.y);
}
vec2 hash22(vec2 p) {
    return vec2(hash21(p), hash21(p + 73.17));
}

// ─── Value noise + FBM for nebula ────────────────────────────
float value_noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
    float v = 0.0, amp = 0.5;
    mat2 rot = mat2(0.8, 0.6, -0.6, 0.8);
    for (int i = 0; i < 5; i++) {
        v += amp * value_noise(p);
        p = rot * p * 2.0;
        amp *= 0.5;
    }
    return v;
}

// ─── Star rendering ──────────────────────────────────────────
// Most stars: bright round point + soft glow halo.
// Only rare bright stars get subtle thin diffraction spikes.
vec3 render_star(vec2 diff, float sz, float bright, float hue,
                 float glow_boost, bool has_spikes) {
    float d = length(diff);

    // Hard bright core — the CENTER is the brightest part
    float core_r = sz * 0.25;
    float core = exp(-(d * d) / (2.0 * core_r * core_r)) * 2.5;

    // Soft circular glow halo
    float glow_r = sz * (1.5 + glow_boost * 3.0);
    float glow = exp(-(d * d) / (2.0 * glow_r * glow_r));
    glow *= (0.35 + glow_boost * 0.5);

    // Thin 4-point spikes — only on bright/big stars
    float spikes = 0.0;
    if (has_spikes) {
        float spike_len = sz * (3.0 + glow_boost * 5.0);
        float spike_w   = sz * 0.06;
        float sx = exp(-(diff.x * diff.x) / (2.0 * spike_len * spike_len))
                 * exp(-(diff.y * diff.y) / (2.0 * spike_w * spike_w));
        float sy = exp(-(diff.y * diff.y) / (2.0 * spike_len * spike_len))
                 * exp(-(diff.x * diff.x) / (2.0 * spike_w * spike_w));
        spikes = (sx + sy) * (0.25 + glow_boost * 0.35);
    }

    float total = core + glow + spikes;
    if (total < 0.004) return vec3(0.0);

    // Vivid star colours
    vec3 cool = vec3(0.55, 0.7, 1.0);   // blue-white
    vec3 warm = vec3(1.0, 0.82, 0.5);   // golden
    vec3 hot  = vec3(0.9, 0.92, 1.0);   // white-blue
    vec3 col;
    if (hue < 0.4)      col = mix(hot, cool, hue / 0.4);
    else if (hue < 0.7) col = mix(cool, warm, (hue - 0.4) / 0.3);
    else                 col = mix(warm, hot, (hue - 0.7) / 0.3);

    // Core bleaches toward white
    float core_frac = core / max(total, 0.001);
    col = mix(col, vec3(1.0), core_frac * 0.85);

    return col * total * bright;
}

// ─── Nebula background ───────────────────────────────────────
vec3 nebula(vec2 uv, float t, float energy) {
    float n1 = fbm(uv * 2.5 + vec2(t * 0.02, t * 0.015));
    float n2 = fbm(uv * 3.8 + vec2(-t * 0.018, t * 0.025) + 50.0);

    float cycle = sin(t * max(0.01, u_nebula_cycle_speed) * 0.3) * 0.5 + 0.5;
    vec3 tint1 = max(u_nebula_tint1, vec3(0.03, 0.04, 0.08));
    vec3 tint2 = max(u_nebula_tint2, vec3(0.06, 0.03, 0.07));

    vec3 neb_col = mix(tint1, tint2, cycle);
    // Boost saturation: push tints further from grey
    neb_col = mix(vec3(dot(neb_col, vec3(0.333))), neb_col, 1.6);

    float density = smoothstep(0.28, 0.72, n1) * smoothstep(0.22, 0.68, n2);
    density *= 0.35;

    // Audio-reactive nebula brightness
    density *= (0.7 + energy * 0.8);

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

    vec2 uv = vec2(
        (fc.x - margin_x) / inner_h - (inner_w / inner_h) * 0.5,
        (fc.y - margin_y) / inner_h - 0.5
    );

    // ── Travel (NEGATED so stars fly toward camera = forward) ──
    float t = -u_travel_time * 0.12;

    float energy = u_overall_energy * u_star_reactivity;
    float glow_boost = energy;

    // ── Nebula background ────────────────────────────────────
    vec3 col = nebula(uv, u_time, energy);

    // ── Travelling stars across depth layers ─────────────────
    for (int i = 0; i < NUM_LAYERS; i++) {
        float z = fract(float(i) / float(NUM_LAYERS) + t);

        // Fade: appear far, vanish near
        float fade = smoothstep(0.0, 0.15, z) * smoothstep(1.0, 0.8, z);
        if (fade < 0.01) continue;

        // Perspective depth
        float depth = mix(1.0, 0.04, z * z);
        float sz    = mix(0.003, 0.04, z * z);
        float bright = mix(0.15, 1.8, z * z) * fade;

        // Sparser grids — much less density than before
        float grid_scale = mix(8.0, 1.8, z * z);
        grid_scale *= (0.4 + u_star_density * 0.6);

        vec2 scaled_uv = uv / depth;
        vec2 grid_uv = scaled_uv * grid_scale;
        vec2 cell = floor(grid_uv);
        vec2 fuv  = fract(grid_uv) - 0.5;

        for (int cy = -1; cy <= 1; cy++) {
            for (int cx = -1; cx <= 1; cx++) {
                vec2 offset = vec2(float(cx), float(cy));
                vec2 n = cell + offset;
                vec2 seed = n + float(i) * 331.7;

                // High density gate = fewer stars (was 0.50, now 0.65+)
                float density_gate = 0.65 - u_star_density * 0.12;
                if (hash21(seed) < density_gate) continue;

                vec2 star_pos = hash22(seed * 1.37) - 0.5;
                star_pos *= 0.65;

                vec2 diff = fuv - offset - star_pos;
                float d = length(diff);

                float max_r = sz * (3.0 + glow_boost * 5.0) * 2.0;
                if (d > max_r) continue;

                float star_bright = 0.3 + hash21(seed * 3.1) * 0.7;
                float hue = hash21(seed * 5.7);

                // ~10% are "big stars" that get diffraction spikes
                bool big = hash21(seed * 7.3) > 0.90;
                float this_sz = sz * (big ? 1.8 : 1.0);
                float this_bright = bright * star_bright * (big ? 1.4 : 1.0);

                // Audio-reactive glow: stars pulse brighter with energy
                this_bright *= (0.6 + glow_boost * 1.2);

                col += render_star(diff, this_sz, this_bright, hue,
                                   glow_boost, big);
            }
        }
    }

    // ── Static background pinpoints (very distant, no travel) ──
    {
        vec2 bg_uv = uv * 20.0;
        vec2 bg_cell = floor(bg_uv);
        vec2 bg_fuv  = fract(bg_uv) - 0.5;
        for (int by = -1; by <= 1; by++) {
            for (int bx = -1; bx <= 1; bx++) {
                vec2 boff = vec2(float(bx), float(by));
                vec2 bn = bg_cell + boff;
                vec2 bseed = bn + 999.0;
                if (hash21(bseed) < 0.60) continue;
                vec2 bp = hash22(bseed * 1.37) - 0.5;
                bp *= 0.6;
                float bd = length(bg_fuv - boff - bp);
                float pinpoint = smoothstep(0.035, 0.0, bd) * 0.3;
                float twinkle = 0.7 + 0.3 * sin(
                    u_time * (1.5 + hash21(bseed * 2.1) * 3.0)
                    + hash21(bseed * 4.3) * 6.28);
                float hue = hash21(bseed * 5.7);
                vec3 star_col = mix(vec3(0.6, 0.75, 1.0), vec3(1.0, 0.85, 0.65), hue);
                col += star_col * pinpoint * twinkle;
            }
        }
    }

    // Gentle tone-map — preserve brightness, just prevent hard clipping
    col = 1.0 - exp(-col * 1.4);

    // Rainbow hue shift (Taste The Rainbow mode)
    if (u_rainbow_hue_offset > 0.001) {
        float cmax = max(col.r, max(col.g, col.b));
        float cmin = min(col.r, min(col.g, col.b));
        float delta = cmax - cmin;
        float h = 0.0;
        if (delta > 0.0001) {
            if (cmax == col.r) h = mod((col.g - col.b) / delta, 6.0);
            else if (cmax == col.g) h = (col.b - col.r) / delta + 2.0;
            else h = (col.r - col.g) / delta + 4.0;
            h /= 6.0;
            if (h < 0.0) h += 1.0;
        }
        float s = (cmax > 0.0001) ? delta / cmax : 0.0;
        float v = cmax;
        // Force saturation on greyscale so rainbow colouring is visible
        if (s < 0.05 && v > 0.05) s = 1.0;
        h = fract(h + u_rainbow_hue_offset);
        float c = v * s;
        float x = c * (1.0 - abs(mod(h * 6.0, 2.0) - 1.0));
        float m = v - c;
        vec3 rgb;
        if      (h < 1.0/6.0) rgb = vec3(c, x, 0.0);
        else if (h < 2.0/6.0) rgb = vec3(x, c, 0.0);
        else if (h < 3.0/6.0) rgb = vec3(0.0, c, x);
        else if (h < 4.0/6.0) rgb = vec3(0.0, x, c);
        else if (h < 5.0/6.0) rgb = vec3(x, 0.0, c);
        else                  rgb = vec3(c, 0.0, x);
        col = rgb + m;
    }

    fragColor = vec4(col, u_fade);
}
