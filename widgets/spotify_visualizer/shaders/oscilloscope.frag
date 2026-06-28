#version 330 core
in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;
uniform float u_dpr;
uniform float u_fade;
uniform float u_time;

// Waveform data
uniform float u_waveform[256];
uniform int u_waveform_count;

// Energy bands
uniform float u_overall_energy;
uniform float u_bass_energy;
uniform float u_mid_energy;
uniform float u_high_energy;

// Line colour (separate from glow)
uniform vec4 u_line_color;

// Glow configuration
uniform int u_glow_enabled;
uniform float u_glow_intensity;
uniform float u_glow_size;
uniform float u_glow_reactivity;
uniform vec4 u_glow_color;
uniform int u_reactive_glow;

// Sensitivity & smoothing
uniform float u_sensitivity;   // multiplier for waveform values (default 3.0)
uniform float u_smoothing;     // 0 = linear/jagged, 1 = full Catmull-Rom smooth

// Multi-line mode (1 = single, 2-6 = extra lines)
uniform int u_line_count;
uniform vec4 u_line2_color;
uniform vec4 u_line2_glow_color;
uniform vec4 u_line3_color;
uniform vec4 u_line3_glow_color;
uniform vec4 u_line4_color;
uniform vec4 u_line4_glow_color;
uniform vec4 u_line5_color;
uniform vec4 u_line5_glow_color;
uniform vec4 u_line6_color;
uniform vec4 u_line6_glow_color;

// Optional line 2/3 glow dimming (0 = equal glow, 1 = half-strength dim)
uniform int u_osc_line_dim;

// Line Offset Bias: 0 = energy-only spacing, 1 = max base spread + per-band weight (multi-line only)
uniform float u_osc_line_offset_bias;

// Vertical Shift: when 1, disables offset and places lines at fixed top/middle/bottom positions
uniform int u_osc_vertical_shift;
uniform float u_rainbow_hue_offset; // 0..1 hue rotation (0 = disabled)

// Ghost waveform (previous frame trail)
uniform float u_prev_waveform[256];
uniform float u_osc_ghost_alpha; // 0 = no ghost, >0 = ghost trail intensity
uniform int u_ghost_line2_enabled;
uniform int u_ghost_line3_enabled;
uniform int u_ghost_line4_enabled;
uniform int u_ghost_line5_enabled;
uniform int u_ghost_line6_enabled;

float get_waveform_sample(int idx) {
    // Modular wrap so offset lines read valid circular-buffer data
    int n = max(u_waveform_count, 1);
    int wrapped = ((idx % n) + n) % n;
    return u_waveform[wrapped];
}

float get_prev_waveform_sample(int idx) {
    int n = max(u_waveform_count, 1);
    int wrapped = ((idx % n) + n) % n;
    return u_prev_waveform[wrapped];
}

// Apply Taste The Rainbow hue shift to a vec3 while preserving luminance.
vec3 apply_rainbow_shift(vec3 rgb) {
    if (u_rainbow_hue_offset <= 0.001) {
        return rgb;
    }
    float cmax = max(rgb.r, max(rgb.g, rgb.b));
    float cmin = min(rgb.r, min(rgb.g, rgb.b));
    float delta = cmax - cmin;
    float h = 0.0;
    if (delta > 0.0001) {
        if (cmax == rgb.r)      h = mod((rgb.g - rgb.b) / delta, 6.0);
        else if (cmax == rgb.g) h = (rgb.b - rgb.r) / delta + 2.0;
        else                    h = (rgb.r - rgb.g) / delta + 4.0;
        h /= 6.0;
        if (h < 0.0) h += 1.0;
    }
    float s = (cmax > 0.0001) ? delta / cmax : 0.0;
    float v = cmax;
    if (s < 0.05 && v > 0.05) s = 1.0;
    h = fract(h + u_rainbow_hue_offset);
    float c = v * s;
    float x = c * (1.0 - abs(mod(h * 6.0, 2.0) - 1.0));
    float m = v - c;
    vec3 shifted;
    if      (h < 1.0/6.0) shifted = vec3(c, x, 0.0);
    else if (h < 2.0/6.0) shifted = vec3(x, c, 0.0);
    else if (h < 3.0/6.0) shifted = vec3(0.0, c, x);
    else if (h < 4.0/6.0) shifted = vec3(0.0, x, c);
    else if (h < 5.0/6.0) shifted = vec3(x, 0.0, c);
    else                   shifted = vec3(c, 0.0, x);
    return shifted + vec3(m);
}

// Gaussian-weighted multi-tap smoothing around a sample index.
// The smoothing uniform controls the kernel radius: 0 = single sample, 1 = wide blur.
// use_prev: false = current waveform, true = previous (ghost) waveform
float smoothed_sample_impl(int center, bool use_prev) {
    float eff_smooth = u_smoothing;
    if (eff_smooth <= 0.01) {
        return use_prev ? get_prev_waveform_sample(center) : get_waveform_sample(center);
    }
    // Kernel half-width scales from 1 to 12 taps based on smoothing
    int half_w = int(1.0 + eff_smooth * 11.0);
    float sigma = max(0.5, float(half_w) * 0.45);
    float total = 0.0;
    float weight_sum = 0.0;
    for (int i = -12; i <= 12; i++) {
        if (i < -half_w || i > half_w) continue;
        float w = exp(-float(i * i) / (2.0 * sigma * sigma));
        float s = use_prev ? get_prev_waveform_sample(center + i) : get_waveform_sample(center + i);
        total += s * w;
        weight_sum += w;
    }
    return total / max(weight_sum, 0.001);
}

float smoothed_sample(int center) {
    return smoothed_sample_impl(center, false);
}

float smoothed_sample_prev(int center) {
    return smoothed_sample_impl(center, true);
}

// Catmull-Rom spline for sub-sample interpolation between smoothed values.
float catmull_rom(float p0, float p1, float p2, float p3, float t) {
    float t2 = t * t;
    float t3 = t2 * t;
    return 0.5 * ((2.0 * p1) +
                   (-p0 + p2) * t +
                   (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 +
                   (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3);
}

// Sample waveform at position with an index offset for multi-line distribution.
float sample_waveform(float nx, int offset) {
    int wf_count = max(u_waveform_count, 2);
    float sample_pos = nx * float(wf_count - 1);
    int idx = int(floor(sample_pos)) + offset;
    float frac = sample_pos - floor(sample_pos);

    // Get Gaussian-smoothed samples for Catmull-Rom interpolation
    float s0 = smoothed_sample(idx - 1);
    float s1 = smoothed_sample(idx);
    float s2 = smoothed_sample(idx + 1);
    float s3 = smoothed_sample(idx + 2);

    // Always use Catmull-Rom for sub-sample interpolation (smooth between taps)
    float val = catmull_rom(s0, s1, s2, s3, frac);

    // Apply sensitivity as amplitude multiplier — soft saturation
    // instead of hard clamp, preserving smooth curve shape
    // Manual tanh since GLSL 330 doesn't have it
    float sv = val * u_sensitivity;
    float e2 = exp(2.0 * sv);
    return (e2 - 1.0) / (e2 + 1.0);
}

// Sample previous (ghost) waveform
float sample_prev_waveform(float nx, int offset) {
    int wf_count = max(u_waveform_count, 2);
    float sample_pos = nx * float(wf_count - 1);
    int idx = int(floor(sample_pos)) + offset;
    float frac = sample_pos - floor(sample_pos);
    float s0 = smoothed_sample_prev(idx - 1);
    float s1 = smoothed_sample_prev(idx);
    float s2 = smoothed_sample_prev(idx + 1);
    float s3 = smoothed_sample_prev(idx + 2);
    float val = catmull_rom(s0, s1, s2, s3, frac);
    float sv = val * u_sensitivity;
    float e2p = exp(2.0 * sv);
    return (e2p - 1.0) / (e2p + 1.0);
}

// Compute line + glow contribution for one waveform line.
// Returns vec4(rgb, alpha) and exposes separate premultiplied components
// so we can clamp glow overlap during composition.
vec4 eval_line(
    float ny, float inner_height, float wave_val, float amplitude,
    vec4 lineCol, vec4 glowCol, float glowSigmaBase, float band_energy,
    out vec3 premult_line_rgb, out vec3 premult_glow_rgb,
    out float line_alpha_out, out float glow_alpha_out
) {
    float wave_y = 0.5 + wave_val * amplitude;
    float dist = abs(ny - wave_y);
    float dist_px = dist * inner_height;

    float line_width = 2.0;
    float line_alpha = 1.0 - smoothstep(0.0, line_width, dist_px);

    float glow_alpha = 0.0;
    if (u_glow_enabled == 1 && glowSigmaBase > 0.0) {
        float sigma = glowSigmaBase;
        if (u_reactive_glow == 1) {
            float react = clamp(u_glow_reactivity, 0.0, 2.0);
            // Reactivity should primarily widen/shape the glow. If alpha also
            // surges too hard, Oscilloscope reads as brightness strobe instead
            // of waveform motion.
            sigma *= (0.94 + band_energy * (0.55 * react));
        }
        if (sigma > 0.0) {
            glow_alpha = exp(-(dist_px * dist_px) / (2.0 * sigma * sigma));
            glow_alpha *= clamp(u_glow_intensity, 0.0, 2.0);
            if (u_reactive_glow == 1) {
                float react = clamp(u_glow_reactivity, 0.0, 2.0);
                glow_alpha *= (0.96 + band_energy * (0.10 * react));
            }
        }
    }

    float glow_mix = 0.0;
    if (glow_alpha > 0.0) {
        float leftover = max(0.0, 1.0 - line_alpha);
        glow_mix = min(glow_alpha * 0.7, leftover);
    }

    float total_alpha = line_alpha + glow_mix;
    if (total_alpha <= 0.001) {
        premult_line_rgb = vec3(0.0);
        premult_glow_rgb = vec3(0.0);
        line_alpha_out = 0.0;
        glow_alpha_out = 0.0;
        return vec4(0.0);
    }

    premult_line_rgb = lineCol.rgb * line_alpha;
    premult_glow_rgb = glowCol.rgb * glow_mix;
    vec3 premult = premult_line_rgb + premult_glow_rgb;
    vec3 rgb = premult / total_alpha;
    line_alpha_out = line_alpha;
    glow_alpha_out = glow_mix;
    return vec4(rgb, total_alpha);
}

void composite_ghost_line(
    float ny, float inner_height, float wave_val, float amplitude,
    vec4 ghost_line_color, vec4 ghost_glow_color,
    float ghost_glow_sigma, float ghost_band_energy,
    float ghost_alpha,
    inout vec3 dst_rgb, inout float dst_a
) {
    vec3 ghost_line_rgb;
    vec3 ghost_glow_rgb;
    float ghost_line_alpha;
    float ghost_glow_alpha;
    eval_line(
        ny, inner_height, wave_val, amplitude,
        ghost_line_color, ghost_glow_color, ghost_glow_sigma, ghost_band_energy,
        ghost_line_rgb, ghost_glow_rgb, ghost_line_alpha, ghost_glow_alpha
    );
    float ga = (ghost_line_alpha + ghost_glow_alpha) * ghost_alpha;
    if (ga <= 0.001) {
        return;
    }
    float inv = 1.0 - ga;
    vec3 premult = (ghost_line_rgb + ghost_glow_rgb) * ghost_alpha;
    dst_rgb = premult + dst_rgb * inv;
    dst_a = ga + dst_a * inv;
}

void composite_line(
    vec3 line_rgb, vec3 glow_rgb, float line_alpha, float glow_alpha,
    inout vec3 dst_rgb, inout float dst_a, inout float glow_accum
) {
    float available_glow = max(0.0, 1.0 - glow_accum);
    float glow_scale = (glow_alpha > 0.0001)
        ? min(1.0, available_glow / glow_alpha)
        : 1.0;
    vec3 adj_glow_rgb = glow_rgb * glow_scale;
    float adj_glow_alpha = glow_alpha * glow_scale;
    float combined_alpha = line_alpha + adj_glow_alpha;
    if (combined_alpha <= 0.0) {
        return;
    }
    vec3 combined_premult = line_rgb + adj_glow_rgb;
    float inv_src = 1.0 - combined_alpha;
    dst_rgb = combined_premult + dst_rgb * inv_src;
    dst_a = combined_alpha + dst_a * inv_src;
    glow_accum = adj_glow_alpha + glow_accum * (1.0 - adj_glow_alpha);
}

void main() {
    if (u_fade <= 0.0) {
        discard;
    }

    float width = u_resolution.x;
    float height = u_resolution.y;
    if (width <= 0.0 || height <= 0.0) {
        discard;
    }

    float dpr = (u_dpr <= 0.0) ? 1.0 : u_dpr;
    float fb_height = height * dpr;
    vec2 fc = vec2(gl_FragCoord.x / dpr, (fb_height - gl_FragCoord.y) / dpr);

    // Margins matching the card inset — enough to prevent glow bleeding past frame
    float margin_x = 5.0;
    float margin_y = 1.0;
    float inner_width = width - margin_x * 2.0;
    float inner_height = height - margin_y * 2.0;

    if (inner_width <= 0.0 || inner_height <= 0.0) {
        discard;
    }

    // Discard outside card area
    if (fc.x < margin_x || fc.x > width - margin_x ||
        fc.y < margin_y || fc.y > height - margin_y) {
        discard;
    }

    // Normalise fragment position within the inner rect
    float nx = (fc.x - margin_x) / inner_width;   // 0..1 horizontal
    float ny = (fc.y - margin_y) / inner_height;   // 0..1 vertical

    // Dynamic amplitude: wave peaks reach within 1px of card edges
    float amplitude = 0.5 - 1.0 / max(inner_height, 2.0);
    // Size controls spread radius only; intensity controls visible strength.
    float glow_sigma_base = 8.0 * max(u_glow_size, 0.1);

    int lines = clamp(u_line_count, 1, 6);

    // Per-line energy: single mode uses overall, multi-line splits by band
    // Bass boosted 15% for kick/drum punch, mids/highs boosted 15% for vocal response
    float e1 = (lines == 1) ? u_overall_energy : u_bass_energy * 1.15;
    float e2_band = u_mid_energy * 1.15;
    float e3_band = u_high_energy * 1.15;
    float e4_band = u_mid_energy * 1.10;
    float e5_band = u_high_energy * 1.05;
    float e6_band = u_bass_energy * 1.10;

    // Line Offset Bias: base vertical spread + per-band energy weight (multi-line)
    float lob = clamp(u_osc_line_offset_bias, 0.0, 1.0);
    float band_boost = 1.0 + lob * 1.5;  // up to 2.5x per-band reliance

    vec4 glowColor1 = u_glow_color;
    vec4 glowColor2 = u_line2_glow_color;
    vec4 glowColor3 = u_line3_glow_color;
    vec4 glowColor4 = u_line4_glow_color;
    vec4 glowColor5 = u_line5_glow_color;
    vec4 glowColor6 = u_line6_glow_color;
    bool rainbow_active = (u_rainbow_hue_offset > 0.001);
    if (rainbow_active) {
        glowColor1.rgb = apply_rainbow_shift(glowColor1.rgb);
        glowColor2.rgb = apply_rainbow_shift(glowColor2.rgb);
        glowColor3.rgb = apply_rainbow_shift(glowColor3.rgb);
        glowColor4.rgb = apply_rainbow_shift(glowColor4.rgb);
        glowColor5.rgb = apply_rainbow_shift(glowColor5.rgb);
        glowColor6.rgb = apply_rainbow_shift(glowColor6.rgb);
    }

    // --- Ghost lines (previous frame trail, rendered first/behind) ---
    vec3 ghost_rgb = vec3(0.0);
    float ghost_a = 0.0;
    if (u_osc_ghost_alpha > 0.001) {
        float ga = u_osc_ghost_alpha;
        float gamp1 = amplitude * (1.0 + e1 * 0.13);
        float gw1 = sample_prev_waveform(nx, 0);
        vec3 gc1_line_rgb;
        vec3 gc1_glow_rgb;
        float gc1_line_alpha;
        float gc1_glow_alpha;
        vec4 gc1 = eval_line(ny, inner_height, gw1, gamp1,
                             u_line_color, glowColor1, glow_sigma_base * 0.6, e1,
                             gc1_line_rgb, gc1_glow_rgb, gc1_line_alpha, gc1_glow_alpha);
        ghost_rgb = gc1.rgb * gc1.a * ga;
        ghost_a = gc1.a * ga;

        if (lines >= 2 && u_ghost_line2_enabled == 1) {
            int gwf_count = max(u_waveform_count, 2);
            int goffset2 = max(1, gwf_count / 3);
            float gamp2 = amplitude * (0.88 + e2_band * 0.22 * band_boost);
            float gw2 = sample_prev_waveform(nx, goffset2);
            float gny2;
            float gv_shift_pct2 = float(u_osc_vertical_shift) / 100.0;
            if (abs(gv_shift_pct2) > 0.001) {
                float gbase_sp2 = clamp(inner_height * 0.25, 20.0, 80.0);
                float gshift2 = (gbase_sp2 * gv_shift_pct2) / inner_height;
                gny2 = ny + gshift2;
                gamp2 = amplitude * (0.7 + e2_band * 0.15);
            } else {
                gny2 = ny - lob * 0.18;
            }
            float ghost_sigma2 = ((u_osc_line_dim == 1) ? glow_sigma_base * 0.925 : glow_sigma_base) * 0.70;
            composite_ghost_line(
                gny2 + 0.010, inner_height, gw2, gamp2,
                vec4(glowColor2.rgb, 1.0), glowColor2, ghost_sigma2, e2_band,
                ga,
                ghost_rgb, ghost_a
            );
        }
        if (lines >= 3 && u_ghost_line3_enabled == 1) {
            int gwf_count3 = max(u_waveform_count, 2);
            int goffset3 = max(1, gwf_count3 * 2 / 3);
            float gamp3 = amplitude * (0.75 + e3_band * 0.28 * band_boost);
            float gw3 = sample_prev_waveform(nx, goffset3);
            float gny3;
            float gv_shift_pct3 = float(u_osc_vertical_shift) / 100.0;
            if (abs(gv_shift_pct3) > 0.001) {
                float gbase_sp3 = clamp(inner_height * 0.25, 20.0, 80.0);
                float gshift3 = (gbase_sp3 * gv_shift_pct3) / inner_height;
                gny3 = ny - gshift3;
                gamp3 = amplitude * (0.6 + e3_band * 0.18);
            } else {
                gny3 = ny + lob * 0.18;
            }
            float ghost_sigma3 = ((u_osc_line_dim == 1) ? glow_sigma_base * 0.85 : glow_sigma_base) * 0.70;
            composite_ghost_line(
                gny3 + 0.010, inner_height, gw3, gamp3,
                vec4(glowColor3.rgb, 1.0), glowColor3, ghost_sigma3, e3_band,
                ga,
                ghost_rgb, ghost_a
            );
        }
        if (lines >= 4 && u_ghost_line4_enabled == 1) {
            int gwf_count4 = max(u_waveform_count, 2);
            int goffset4 = max(1, gwf_count4 * 3 / 4);
            float gamp4 = amplitude * (0.65 + e4_band * 0.25 * band_boost);
            float gw4 = sample_prev_waveform(nx, goffset4);
            float gny4;
            float gv_shift_pct4 = float(u_osc_vertical_shift) / 100.0;
            if (abs(gv_shift_pct4) > 0.001) {
                float gbase_sp4 = clamp(inner_height * 0.25, 20.0, 80.0);
                float gshift4 = (gbase_sp4 * gv_shift_pct4 * 1.4) / inner_height;
                gny4 = ny + gshift4;
                gamp4 = amplitude * (0.55 + e4_band * 0.12);
            } else {
                gny4 = ny - lob * 0.25;
            }
            float ghost_sigma4 = ((u_osc_line_dim == 1) ? glow_sigma_base * 0.875 : glow_sigma_base) * 0.70;
            composite_ghost_line(
                gny4 + 0.010, inner_height, gw4, gamp4,
                vec4(glowColor4.rgb, 1.0), glowColor4, ghost_sigma4, e4_band,
                ga,
                ghost_rgb, ghost_a
            );
        }
        if (lines >= 5 && u_ghost_line5_enabled == 1) {
            int gwf_count5 = max(u_waveform_count, 2);
            int goffset5 = max(1, gwf_count5 * 4 / 5);
            float gamp5 = amplitude * (0.60 + e5_band * 0.22 * band_boost);
            float gw5 = sample_prev_waveform(nx, goffset5);
            float gny5;
            float gv_shift_pct5 = float(u_osc_vertical_shift) / 100.0;
            if (abs(gv_shift_pct5) > 0.001) {
                float gbase_sp5 = clamp(inner_height * 0.25, 20.0, 80.0);
                float gshift5 = (gbase_sp5 * gv_shift_pct5 * 1.8) / inner_height;
                gny5 = ny - gshift5;
                gamp5 = amplitude * (0.50 + e5_band * 0.10);
            } else {
                gny5 = ny + lob * 0.30;
            }
            float ghost_sigma5 = ((u_osc_line_dim == 1) ? glow_sigma_base * 0.825 : glow_sigma_base) * 0.70;
            composite_ghost_line(
                gny5 + 0.010, inner_height, gw5, gamp5,
                vec4(glowColor5.rgb, 1.0), glowColor5, ghost_sigma5, e5_band,
                ga,
                ghost_rgb, ghost_a
            );
        }
        if (lines >= 6 && u_ghost_line6_enabled == 1) {
            int gwf_count6 = max(u_waveform_count, 2);
            int goffset6 = max(1, gwf_count6 * 5 / 6);
            float gamp6 = amplitude * (0.55 + e6_band * 0.28 * band_boost);
            float gw6 = sample_prev_waveform(nx, goffset6);
            float gny6;
            float gv_shift_pct6 = float(u_osc_vertical_shift) / 100.0;
            if (abs(gv_shift_pct6) > 0.001) {
                float gbase_sp6 = clamp(inner_height * 0.25, 20.0, 80.0);
                float gshift6 = (gbase_sp6 * gv_shift_pct6 * 2.2) / inner_height;
                gny6 = ny + gshift6;
                gamp6 = amplitude * (0.45 + e6_band * 0.08);
            } else {
                gny6 = ny - lob * 0.35;
            }
            float ghost_sigma6 = ((u_osc_line_dim == 1) ? glow_sigma_base * 0.80 : glow_sigma_base) * 0.70;
            composite_ghost_line(
                gny6 + 0.010, inner_height, gw6, gamp6,
                vec4(glowColor6.rgb, 1.0), glowColor6, ghost_sigma6, e6_band,
                ga,
                ghost_rgb, ghost_a
            );
        }
    }

    vec3 lines_rgb = vec3(0.0);
    float lines_a = 0.0;
    float glow_accum = 0.0;

    // Primary line — bass-reactive in multi-line, overall in single
    float amp1 = amplitude * (1.0 + e1 * 0.13);
    float w1 = sample_waveform(nx, 0);
    vec3 line_rgb1;
    vec3 glow_rgb1;
    float line_alpha1;
    float glow_alpha1;
    eval_line(ny, inner_height, w1, amp1,
              u_line_color, glowColor1, glow_sigma_base, e1,
              line_rgb1, glow_rgb1, line_alpha1, glow_alpha1);
    composite_line(line_rgb1, glow_rgb1, line_alpha1, glow_alpha1,
                   lines_rgb, lines_a, glow_accum);

    if (lines >= 2) {
        // Line 2: mid-frequency reactive — responds to vocals, guitars, keys
        int wf_count = max(u_waveform_count, 2);
        int offset2 = max(1, wf_count / 3);
        // Line Offset Bias: increase mid-energy reliance and add vertical spread
        float amp2 = amplitude * (0.88 + e2_band * 0.22 * band_boost);
        float w2 = sample_waveform(nx, offset2);
        float ny2;
        float v_shift_pct = float(u_osc_vertical_shift) / 100.0;
        if (abs(v_shift_pct) > 0.001) {
            float base_sp = clamp(inner_height * 0.25, 20.0, 80.0);
            float shift = (base_sp * v_shift_pct) / inner_height;
            ny2 = ny + shift;
            amp2 = amplitude * (0.7 + e2_band * 0.15);
        } else {
            ny2 = ny - lob * 0.18;
        }
        float sigma2 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.925 : glow_sigma_base;
        vec3 line_rgb2;
        vec3 glow_rgb2;
        float line_alpha2;
        float glow_alpha2;
        eval_line(ny2, inner_height, w2, amp2,
                  u_line2_color, glowColor2,
                  sigma2, e2_band,
                  line_rgb2, glow_rgb2, line_alpha2, glow_alpha2);
        composite_line(line_rgb2, glow_rgb2, line_alpha2, glow_alpha2,
                       lines_rgb, lines_a, glow_accum);
    }

    if (lines >= 3) {
        // Line 3: high-frequency reactive — responds to hi-hats, cymbals, sibilance
        int wf_count = max(u_waveform_count, 2);
        int offset3 = max(1, wf_count * 2 / 3);
        // Line Offset Bias: increase high-energy reliance and add vertical spread
        float amp3 = amplitude * (0.75 + e3_band * 0.28 * band_boost);
        float w3 = sample_waveform(nx, offset3);
        float ny3;
        float v_shift_pct3 = float(u_osc_vertical_shift) / 100.0;
        if (abs(v_shift_pct3) > 0.001) {
            float base_sp3 = clamp(inner_height * 0.25, 20.0, 80.0);
            float shift3 = (base_sp3 * v_shift_pct3) / inner_height;
            ny3 = ny - shift3;
            amp3 = amplitude * (0.6 + e3_band * 0.18);
        } else {
            ny3 = ny + lob * 0.18;
        }
        float sigma3 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.85 : glow_sigma_base;
        vec3 line_rgb3;
        vec3 glow_rgb3;
        float line_alpha3;
        float glow_alpha3;
        eval_line(ny3, inner_height, w3, amp3,
                  u_line3_color, glowColor3,
                  sigma3, e3_band,
                  line_rgb3, glow_rgb3, line_alpha3, glow_alpha3);
        composite_line(line_rgb3, glow_rgb3, line_alpha3, glow_alpha3,
                       lines_rgb, lines_a, glow_accum);
    }

    if (lines >= 4) {
        // Line 4: mid-frequency reactive — additional variety
        int wf_count4 = max(u_waveform_count, 2);
        int offset4 = max(1, wf_count4 * 3 / 4);
        float amp4 = amplitude * (0.65 + e4_band * 0.25 * band_boost);
        float w4 = sample_waveform(nx, offset4);
        float ny4;
        float v_shift_pct4 = float(u_osc_vertical_shift) / 100.0;
        if (abs(v_shift_pct4) > 0.001) {
            float base_sp4 = clamp(inner_height * 0.25, 20.0, 80.0);
            float shift4 = (base_sp4 * v_shift_pct4 * 1.4) / inner_height;
            ny4 = ny + shift4;
            amp4 = amplitude * (0.55 + e4_band * 0.12);
        } else {
            ny4 = ny - lob * 0.25;
        }
        float sigma4 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.875 : glow_sigma_base;
        vec3 line_rgb4;
        vec3 glow_rgb4;
        float line_alpha4;
        float glow_alpha4;
        eval_line(ny4, inner_height, w4, amp4,
                  u_line4_color, glowColor4,
                  sigma4, e4_band,
                  line_rgb4, glow_rgb4, line_alpha4, glow_alpha4);
        composite_line(line_rgb4, glow_rgb4, line_alpha4, glow_alpha4,
                       lines_rgb, lines_a, glow_accum);
    }

    if (lines >= 5) {
        // Line 5: high-frequency reactive — additional variety
        int wf_count5 = max(u_waveform_count, 2);
        int offset5 = max(1, wf_count5 * 4 / 5);
        float amp5 = amplitude * (0.60 + e5_band * 0.22 * band_boost);
        float w5 = sample_waveform(nx, offset5);
        float ny5;
        float v_shift_pct5 = float(u_osc_vertical_shift) / 100.0;
        if (abs(v_shift_pct5) > 0.001) {
            float base_sp5 = clamp(inner_height * 0.25, 20.0, 80.0);
            float shift5 = (base_sp5 * v_shift_pct5 * 1.8) / inner_height;
            ny5 = ny - shift5;
            amp5 = amplitude * (0.50 + e5_band * 0.10);
        } else {
            ny5 = ny + lob * 0.30;
        }
        float sigma5 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.825 : glow_sigma_base;
        vec3 line_rgb5;
        vec3 glow_rgb5;
        float line_alpha5;
        float glow_alpha5;
        eval_line(ny5, inner_height, w5, amp5,
                  u_line5_color, glowColor5,
                  sigma5, e5_band,
                  line_rgb5, glow_rgb5, line_alpha5, glow_alpha5);
        composite_line(line_rgb5, glow_rgb5, line_alpha5, glow_alpha5,
                       lines_rgb, lines_a, glow_accum);
    }

    if (lines >= 6) {
        // Line 6: bass-frequency reactive — additional variety
        int wf_count6 = max(u_waveform_count, 2);
        int offset6 = max(1, wf_count6 * 5 / 6);
        float amp6 = amplitude * (0.55 + e6_band * 0.28 * band_boost);
        float w6 = sample_waveform(nx, offset6);
        float ny6;
        float v_shift_pct6 = float(u_osc_vertical_shift) / 100.0;
        if (abs(v_shift_pct6) > 0.001) {
            float base_sp6 = clamp(inner_height * 0.25, 20.0, 80.0);
            float shift6 = (base_sp6 * v_shift_pct6 * 2.2) / inner_height;
            ny6 = ny + shift6;
            amp6 = amplitude * (0.45 + e6_band * 0.08);
        } else {
            ny6 = ny - lob * 0.35;
        }
        float sigma6 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.80 : glow_sigma_base;
        vec3 line_rgb6;
        vec3 glow_rgb6;
        float line_alpha6;
        float glow_alpha6;
        eval_line(ny6, inner_height, w6, amp6,
                  u_line6_color, glowColor6,
                  sigma6, e6_band,
                  line_rgb6, glow_rgb6, line_alpha6, glow_alpha6);
        composite_line(line_rgb6, glow_rgb6, line_alpha6, glow_alpha6,
                       lines_rgb, lines_a, glow_accum);
    }

    float ghost_visibility = 1.0 - lines_a * 0.35;
    vec3 final_rgb = lines_rgb + ghost_rgb * ghost_visibility;
    float final_a = lines_a + ghost_a * ghost_visibility;

    if (final_a <= 0.001) {
        discard;
    }

    // Normalise RGB by alpha to prevent over-brightening
    if (final_a > 0.001) {
        final_rgb = clamp(final_rgb / final_a, 0.0, 1.0);
    }

    fragColor = vec4(final_rgb, final_a * u_fade);
}
