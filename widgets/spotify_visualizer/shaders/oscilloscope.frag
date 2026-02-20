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
uniform vec4 u_glow_color;
uniform int u_reactive_glow;

// Sensitivity & smoothing
uniform float u_sensitivity;   // multiplier for waveform values (default 3.0)
uniform float u_smoothing;     // 0 = linear/jagged, 1 = full Catmull-Rom smooth

// Multi-line mode (1 = single, 2-3 = extra lines)
uniform int u_line_count;
uniform vec4 u_line2_color;
uniform vec4 u_line2_glow_color;
uniform vec4 u_line3_color;
uniform vec4 u_line3_glow_color;

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
// Returns vec4(rgb, alpha).
vec4 eval_line(
    float ny, float inner_height, float wave_val, float amplitude,
    vec4 lineCol, vec4 glowCol, float glowSigmaBase, float band_energy
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
            // Use per-line band energy for reactive glow
            sigma *= (0.5 + band_energy * 1.8);
        }
        if (sigma > 0.0) {
            glow_alpha = exp(-(dist_px * dist_px) / (2.0 * sigma * sigma));
            if (u_reactive_glow == 1) {
                glow_alpha *= (0.5 + band_energy * 1.0);
            }
        }
    }

    float total_alpha = max(line_alpha, glow_alpha * 0.7);
    if (total_alpha <= 0.001) {
        return vec4(0.0);
    }

    vec3 rgb;
    if (line_alpha > 0.0 && glow_alpha > 0.0) {
        float blend = line_alpha / max(total_alpha, 0.001);
        vec3 core = lineCol.rgb;
        vec3 halo = glowCol.rgb;
        rgb = mix(halo, core, blend);
    } else if (line_alpha > 0.0) {
        rgb = lineCol.rgb;
    } else {
        rgb = glowCol.rgb;
    }

    return vec4(rgb, total_alpha);
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

    // Margins matching the card inset (tight X, minimal Y for full waveform)
    float margin_x = 3.0;
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
    float glow_sigma_base = u_glow_intensity * 8.0;

    int lines = clamp(u_line_count, 1, 3);

    // Per-line energy: single mode uses overall, multi-line splits by band
    // Bass boosted 15% for kick/drum punch, mids/highs boosted 15% for vocal response
    float e1 = (lines == 1) ? u_overall_energy : u_bass_energy * 1.15;
    float e2_band = u_mid_energy * 1.15;
    float e3_band = u_high_energy * 1.15;

    // Line Offset Bias: base vertical spread + per-band energy weight (multi-line)
    float lob = clamp(u_osc_line_offset_bias, 0.0, 1.0);
    float band_boost = 1.0 + lob * 1.5;  // up to 2.5x per-band reliance

    // --- Ghost lines (previous frame trail, rendered first/behind) ---
    vec3 ghost_rgb = vec3(0.0);
    float ghost_a = 0.0;
    if (u_osc_ghost_alpha > 0.001) {
        float ga = u_osc_ghost_alpha;
        float gamp1 = amplitude * (1.0 + e1 * 0.13);
        float gw1 = sample_prev_waveform(nx, 0);
        vec4 gc1 = eval_line(ny, inner_height, gw1, gamp1,
                             u_line_color, u_glow_color, glow_sigma_base * 0.6, e1);
        ghost_rgb = gc1.rgb * gc1.a * ga;
        ghost_a = gc1.a * ga;

        if (lines >= 2) {
            int gwf_count = max(u_waveform_count, 2);
            int goffset2 = max(1, gwf_count / 3);
            float gamp2 = amplitude * (0.88 + e2_band * 0.22 * band_boost);
            float gw2 = sample_prev_waveform(nx, goffset2);
            float gny2 = ny - lob * 0.18;
            float gsigma2 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.55 : glow_sigma_base * 0.6;
            vec4 gc2 = eval_line(gny2, inner_height, gw2, gamp2,
                                 u_line2_color, u_line2_glow_color, gsigma2, e2_band);
            ghost_rgb = ghost_rgb * (1.0 - gc2.a * ga * 0.5) + gc2.rgb * gc2.a * ga;
            ghost_a = max(ghost_a, gc2.a * ga);
        }
        if (lines >= 3) {
            int gwf_count3 = max(u_waveform_count, 2);
            int goffset3 = max(1, gwf_count3 * 2 / 3);
            float gamp3 = amplitude * (0.75 + e3_band * 0.28 * band_boost);
            float gw3 = sample_prev_waveform(nx, goffset3);
            float gny3 = ny + lob * 0.18;
            float gsigma3 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.5 : glow_sigma_base * 0.6;
            vec4 gc3 = eval_line(gny3, inner_height, gw3, gamp3,
                                 u_line3_color, u_line3_glow_color, gsigma3, e3_band);
            ghost_rgb = ghost_rgb * (1.0 - gc3.a * ga * 0.4) + gc3.rgb * gc3.a * ga;
            ghost_a = max(ghost_a, gc3.a * ga);
        }
    }

    // Primary line — bass-reactive in multi-line, overall in single
    float amp1 = amplitude * (1.0 + e1 * 0.13);
    float w1 = sample_waveform(nx, 0);
    vec4 c1 = eval_line(ny, inner_height, w1, amp1,
                        u_line_color, u_glow_color, glow_sigma_base, e1);

    // Composite: ghost behind, current on top
    vec3 final_rgb = ghost_rgb * (1.0 - c1.a) + c1.rgb * c1.a;
    float final_a = max(ghost_a, c1.a);

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
        vec4 c2 = eval_line(ny2, inner_height, w2, amp2,
                            u_line2_color, u_line2_glow_color,
                            sigma2, e2_band);
        final_rgb = final_rgb * (1.0 - c2.a * 0.5) + c2.rgb * c2.a;
        final_a = max(final_a, c2.a);
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
        vec4 c3 = eval_line(ny3, inner_height, w3, amp3,
                            u_line3_color, u_line3_glow_color,
                            sigma3, e3_band);
        final_rgb = final_rgb * (1.0 - c3.a * 0.4) + c3.rgb * c3.a;
        final_a = max(final_a, c3.a);
    }

    if (final_a <= 0.001) {
        discard;
    }

    // Normalise RGB by alpha to prevent over-brightening
    if (final_a > 0.001) {
        final_rgb = clamp(final_rgb / final_a, 0.0, 1.0);
    }

    // Rainbow hue shift (Taste The Rainbow mode)
    if (u_rainbow_hue_offset > 0.001) {
        float cmax = max(final_rgb.r, max(final_rgb.g, final_rgb.b));
        float cmin = min(final_rgb.r, min(final_rgb.g, final_rgb.b));
        float delta = cmax - cmin;
        float h = 0.0;
        if (delta > 0.0001) {
            if (cmax == final_rgb.r) h = mod((final_rgb.g - final_rgb.b) / delta, 6.0);
            else if (cmax == final_rgb.g) h = (final_rgb.b - final_rgb.r) / delta + 2.0;
            else h = (final_rgb.r - final_rgb.g) / delta + 4.0;
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
        final_rgb = rgb + m;
    }

    fragColor = vec4(final_rgb, final_a * u_fade);
}
