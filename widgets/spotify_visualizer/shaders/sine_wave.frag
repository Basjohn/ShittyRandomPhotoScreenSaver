#version 330 core
in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;
uniform float u_dpr;
uniform float u_fade;
uniform float u_time;

const float TWO_PI = 6.2831853;

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

// Sensitivity: scales how much energy affects amplitude (default 1.0)
uniform float u_sensitivity;

// Multi-line mode (1 = single, 2-3 = extra lines)
uniform int u_line_count;
uniform vec4 u_line2_color;
uniform vec4 u_line2_glow_color;
uniform vec4 u_line3_color;
uniform vec4 u_line3_glow_color;

// Optional line 2/3 glow dimming (0 = equal glow, 1 = half-strength dim)
uniform int u_sine_line_dim;

// Sine Wave Speed: time multiplier for wave animation
uniform float u_sine_speed;

// Card Adaptation: 0.0-1.0, controls how much of the card height the wave uses
uniform float u_card_adaptation;

// Line Offset Bias: vertical spread between lines in multi-line mode
uniform float u_sine_line_offset_bias;

// Sine Wave Travel: 0 = none, 1 = scroll left, 2 = scroll right
uniform int u_sine_travel;
// Per-line travel overrides for multi-line mode (same encoding: 0/1/2)
uniform int u_sine_travel_line2;
uniform int u_sine_travel_line3;
// Per-line horizontal shifts expressed as cycles (-1.0 .. 1.0)
uniform float u_sine_line1_shift;
uniform float u_sine_line2_shift;
uniform float u_sine_line3_shift;

// Playback state: 1 = playing, 0 = paused
uniform int u_playing;

// Wave Effect: positional wave-like undulation along the line (0.0-1.0)
// Preserves exact sine shape, only shifts line position up/down
uniform float u_wave_effect;

// Micro Wobble: energy-reactive micro distortions / bumps along the line (0.0-1.0)
// Creates small dents/spikes that react to audio without changing core shape
uniform float u_micro_wobble;

// Vertical shift: -50 to 200, controls line spread.
// 0 = all lines on same center, 100 = default spread, 200 = max spread
uniform int u_sine_vertical_shift;
uniform float u_rainbow_hue_offset; // 0..1 hue rotation (0 = disabled)

// Heartbeat: transient-triggered triangular bumps along the line
uniform float u_heartbeat;           // slider amount (0 = off, 1 = max)
uniform float u_heartbeat_intensity; // CPU-side decay envelope (1.0 → 0.0 over ~250ms)

// Width Reaction: bass-driven horizontal stretching of the sine wave (0.0-1.0)
// Encourages all lines to stretch wide in reaction to bass while still resembling a sine
uniform float u_width_reaction;

// Density: cycles per card multiplier (1.0 = default 3 cycles)
uniform float u_sine_density;

// Displacement: transient XY offsets for multi-line mode when multi-line is active
uniform float u_sine_displacement;

float compute_density_cycles() {
    float density_slider = clamp(u_sine_density, 0.25, 3.0);
    float density_t = (density_slider - 0.25) / (3.0 - 0.25);
    density_t = pow(clamp(density_t, 0.0, 1.0), 0.85);
    return mix(0.65, 8.5, density_t);
}

// Heartbeat bump: crest-focused spikes that sharpen PEAKS only.
// Returns a spike strength and reports the normalised DX to the closest crest so the caller
// can build an inverted "V" profile.
float heartbeat_bump(float nx, float sine_freq_local, float phase_local, out float normalised_dx) {
    normalised_dx = 0.0;
    float slider = clamp(u_heartbeat, 0.0, 1.0);
    float env = clamp(u_heartbeat_intensity, 0.0, 1.0);
    if (slider < 0.001 || env < 0.001) {
        return 0.0;
    }

    const int MAX_CREST_SAMPLES = 12;
    float drive = pow(slider, 0.8);
    float density_cycles = compute_density_cycles();
    float crest_spacing = 1.0 / max(density_cycles, 0.001);
    float crest_half_width = crest_spacing * mix(0.22, 0.32, 1.0 - drive);

    float best = 0.0;
    float best_dx = 0.0;
    for (int n = 0; n < MAX_CREST_SAMPLES; n++) {
        float crest_angle = (0.25 + float(n)) * TWO_PI;
        float cx = (crest_angle - phase_local) / sine_freq_local;
        if (cx < -0.2 || cx > 1.2) {
            continue;
        }

        float dx = nx - cx;
        float norm_dx = dx / crest_half_width;
        float taper = max(0.0, 1.0 - abs(norm_dx));
        float crest_score = taper * taper;
        if (crest_score > best) {
            best = crest_score;
            best_dx = clamp(norm_dx, -1.0, 1.0);
        }
    }

    normalised_dx = best_dx;
    float crest_gain = mix(0.16, 0.38, drive);
    return best * crest_gain * env;
}

float apply_heartbeat_spike(float base_wave, float spike_strength, float spike_dx_norm) {
    if (spike_strength <= 0.0) {
        return base_wave;
    }

    float crest_gate = smoothstep(-0.15, 0.45, base_wave);
    if (crest_gate <= 0.001) {
        return base_wave;
    }

    float cusp_shape = pow(max(0.0, 1.0 - abs(spike_dx_norm)), 0.7);
    float spike_peak = spike_strength * mix(1.05, 2.1, crest_gate);
    float spiked_wave = base_wave + cusp_shape * spike_peak;
    return mix(base_wave, spiked_wave, crest_gate);
}

float hash11(float p) {
    return fract(sin(p) * 43758.5453123);
}

float randSmooth(float seed, float speed) {
    float effectiveSpeed = max(speed, 0.0001);
    float t = u_time * effectiveSpeed + seed;
    float base = floor(t);
    float frac = fract(t);
    float h1 = hash11(base + seed * 1.37);
    float h2 = hash11(base + 1.0 + seed * 1.37);
    float smooth_t = frac * frac * (3.0 - 2.0 * frac);
    return mix(h1, h2, smooth_t);
}

vec2 randomDirection(int line_id, float speed) {
    float base = float(line_id) * 17.1337;
    float rx = randSmooth(base + 0.37, speed);
    float ry = randSmooth(base + 4.11, speed * 0.83 + 0.21);
    return vec2(rx, ry) * 2.0 - 1.0;
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

// Compute line + glow contribution for one sine line.
// mw_displacement: reserved (pass 0.0; micro wobble is now applied to wave_val before calling)
// bass_width_boost: extra line width from width reaction (0.0 = none)
vec4 eval_line(
    float ny, float inner_height, float wave_val, float amplitude,
    vec4 lineCol, vec4 glowCol, float glowSigmaBase, float band_energy,
    float mw_displacement, float bass_width_boost
) {
    float wave_y = clamp(0.5 + wave_val * amplitude + mw_displacement, 0.0, 1.0);
    float dist = abs(ny - wave_y);
    float dist_px = dist * inner_height;

    // Base width 2px, bass reaction can push it up to ~8px while still looking like a sine
    float line_width = 2.0 + bass_width_boost * 6.0;
    float line_alpha = 1.0 - smoothstep(0.0, line_width, dist_px);

    float glow_alpha = 0.0;
    if (u_glow_enabled == 1 && glowSigmaBase > 0.0) {
        float sigma = glowSigmaBase;
        if (u_reactive_glow == 1) {
            // Boosted: reach visible glow at lower energy (+10% min/max)
            sigma *= (0.66 + band_energy * 2.64);
        }
        if (sigma > 0.0) {
            glow_alpha = exp(-(dist_px * dist_px) / (2.0 * sigma * sigma));
            if (u_reactive_glow == 1) {
                glow_alpha *= (0.66 + band_energy * 1.54);
            }
        }
    }

    float glow_mix = 0.0;
    if (glow_alpha > 0.0) {
        float leftover = max(0.0, 1.0 - line_alpha);
        glow_mix = min(glow_alpha * 0.9, leftover);
    }

    float total_alpha = line_alpha + glow_mix;
    if (total_alpha <= 0.001) {
        return vec4(0.0);
    }

    vec3 premult = lineCol.rgb * line_alpha + glowCol.rgb * glow_mix;
    vec3 rgb = premult / total_alpha;
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

    // Keep a slightly larger safety margin so glow/line never overlaps the card border
    float margin_x = 5.0;
    float margin_y = 2.0;
    float inner_width = width - margin_x * 2.0;
    float inner_height = height - margin_y * 2.0;

    if (inner_width <= 0.0 || inner_height <= 0.0) {
        discard;
    }

    if (fc.x < margin_x || fc.x > width - margin_x ||
        fc.y < margin_y || fc.y > height - margin_y) {
        discard;
    }

    float nx = (fc.x - margin_x) / inner_width;
    float ny = (fc.y - margin_y) / inner_height;

    // --- Amplitude: card_adaptation IS the fraction of half-height the wave uses ---
    // adapt=1.0 → wave peaks touch card edges, adapt=0.3 → wave uses 30% of card
    float sens = clamp(u_sensitivity, 0.1, 5.0);

    // Per-line energy: sensitivity only drives amplitude pulse, NOT glow.
    // bass_pulse = sensitivity-scaled bass for amplitude pulsing only.
    float bass_pulse = u_bass_energy * sens * 2.0;

    float adapt = clamp(u_card_adaptation, 0.05, 1.0);
    float base_amp_min = adapt * 0.24;
    float base_amp_max = min(0.48, adapt * 0.62);
    float bass_drive = clamp(u_bass_energy * 1.6 + bass_pulse * 0.5, 0.0, 1.0);
    float base_amplitude = mix(base_amp_min, base_amp_max, bass_drive);
    float glow_sigma_base = u_glow_intensity * 8.0;

    int lines = clamp(u_line_count, 1, 3);

    // Line Offset Bias: declared early — used in energy and wfx/mw blends below.
    float lob = clamp(u_sine_line_offset_bias, 0.0, 1.0);

    // Amplitude energy (includes sensitivity via bass_pulse)
    // All lines share the SAME base energy so they align at LOB=0/VShift=0.
    float e_base = u_bass_energy * 0.4 + bass_pulse + u_mid_energy * 0.15 + u_high_energy * 0.05;
    float e1 = e_base;
    // Lines 2/3: same base energy + slight band tinting scaled by LOB
    // At LOB=0 they are identical to line 1; at LOB=1 they diverge slightly.
    float e2_band = mix(e_base, u_mid_energy * 0.50 + bass_pulse * 0.50, lob * 0.4);
    float e3_band = mix(e_base, u_high_energy * 0.40 + bass_pulse * 0.60, lob * 0.4);

    // Glow energy: raw band energy WITHOUT sensitivity scaling.
    // Reactive glow should respond to actual audio levels, not the sensitivity knob.
    float glow_e1 = (lines == 1)
        ? (u_mid_energy * 0.35 + u_high_energy * 0.10 + u_bass_energy * 0.55)
        : (u_bass_energy * 0.7 + u_mid_energy * 0.2 + u_high_energy * 0.1);
    float glow_e2 = u_mid_energy * 0.70 + u_bass_energy * 0.20 + u_high_energy * 0.10;
    float glow_e3 = u_high_energy * 0.70 + u_bass_energy * 0.15 + u_mid_energy * 0.15;

    // Sine frequency: user slider remapped to a wider visual range (≈0.65–8.5 cycles)
    float density_cycles = compute_density_cycles();
    float sine_freq = TWO_PI * density_cycles;

    // Displacement strength (multi-line transient shove) — audio reactive so loud passages push harder
    float displacement_strength = clamp(u_sine_displacement, 0.0, 1.0);
    float displacement_energy = clamp(u_bass_energy * 0.65 + u_mid_energy * 0.25 + u_high_energy * 0.10, 0.0, 1.0);
    float displacement_drive = displacement_strength * mix(0.045, 0.55, displacement_energy);

    // Speed slider: controls travel rate. Gated on playback.
    float speed = clamp(u_sine_speed, 0.0, 3.0);
    float play_gate = (u_playing == 1) ? 1.0 : 0.0;
    float effective_speed = speed * play_gate;

    // Travel phase per line: ONLY non-zero when direction != NONE (0).
    // 1=left (positive phase shift), 2=right (negative phase shift)
    float phase1 = 0.0;
    if (u_sine_travel == 1) phase1 = u_time * 2.0 * effective_speed;
    if (u_sine_travel == 2) phase1 = u_time * -2.0 * effective_speed;

    float phase2 = 0.0;
    if (u_sine_travel_line2 == 1) phase2 = u_time * 2.0 * effective_speed;
    if (u_sine_travel_line2 == 2) phase2 = u_time * -2.0 * effective_speed;

    float phase3 = 0.0;
    if (u_sine_travel_line3 == 1) phase3 = u_time * 2.0 * effective_speed;
    if (u_sine_travel_line3 == 2) phase3 = u_time * -2.0 * effective_speed;

    // Wave effect amount (positional undulation)
    float wave_fx = clamp(u_wave_effect, 0.0, 1.0);

    // Micro wobble amount (energy-reactive snake lines)
    float micro_wob = clamp(u_micro_wobble, 0.0, 1.0);

    // Width Reaction: bass-driven line width boost (0 = off, 1 = max)
    float wr = clamp(u_width_reaction, 0.0, 1.0);
    float bass_width = 0.0;
    if (wr > 0.001) {
        bass_width = clamp(u_bass_energy * 1.5, 0.0, 1.0) * wr;
    }

    // Vertical shift: purely Y-positioning of lines (does NOT affect amplitude/shape)
    // 0 = no spread, 100 = default spread, 200 = 2x spread, negative = inverted
    float v_shift_pct = float(u_sine_vertical_shift) / 100.0;
    float v_spacing = 0.0;
    if (abs(v_shift_pct) > 0.001 && lines >= 2) {
        float base_spacing_px = clamp(inner_height * 0.25, 20.0, 80.0);
        float raw_spacing = (base_spacing_px * v_shift_pct) / inner_height;
        // Clamp so lines stay within card bounds (max ±0.35 normalized)
        v_spacing = clamp(raw_spacing, -0.35, 0.35);
    }

    vec4 lineColor1 = u_line_color;
    vec4 glowColor1 = u_glow_color;
    vec4 lineColor2 = u_line2_color;
    vec4 glowColor2 = u_line2_glow_color;
    vec4 lineColor3 = u_line3_color;
    vec4 glowColor3 = u_line3_glow_color;
    bool rainbow_active = (u_rainbow_hue_offset > 0.001);
    if (rainbow_active) {
        glowColor1.rgb = apply_rainbow_shift(glowColor1.rgb);
        glowColor2.rgb = apply_rainbow_shift(glowColor2.rgb);
        glowColor3.rgb = apply_rainbow_shift(glowColor3.rgb);
    }

    // =====================================================================
    // LINE 1 (primary) — always centered vertically
    // =====================================================================
    // Energy drives amplitude pulsing. Clamp to 0.48 to stay in card.
    float amp1 = min(base_amplitude * (1.0 + e1 * 0.8), 0.48);
    vec2 rand_line1 = randomDirection(1, 0.55 + displacement_strength * 0.8);
    float phase_jitter1 = displacement_drive * TWO_PI * rand_line1.x;
    float w1 = sin(nx * sine_freq + phase1 + u_sine_line1_shift * TWO_PI + phase_jitter1);

    // Wave effect: vocal-led positional y-offset preserving sine shape
    float wfx1 = 0.0;
    if (wave_fx > 0.001) {
        float we1_raw = u_mid_energy * 0.7 + u_bass_energy * 0.2 + u_high_energy * 0.1;
        float we1 = sqrt(max(we1_raw, 0.0));
        float wfx_raw = sin(nx * 5.3 + u_time * 1.7) * 0.50
                      + sin(nx * 11.1 - u_time * 2.5) * 0.30
                      + sin(nx * 2.1 + u_time * 0.9) * 0.25;
        wfx1 = wfx_raw * we1 * wave_fx * base_amplitude;
    }

    // Micro wobble: snake-like distortions along the line reacting to audio energy.
    // Displacement is in normalised-Y space (0..1) so it is amplitude-independent.
    float mw1 = 0.0;
    if (micro_wob > 0.001 && play_gate > 0.5) {
        float mw_bass = u_bass_energy * 0.55 + u_mid_energy * 0.30 + u_high_energy * 0.15;
        float mw_drive = clamp(mw_bass * 1.8, 0.0, 1.5);
        if (mw_drive > 0.001) {
            float t_fast = u_time * 3.5;
            float t_med  = u_time * 1.8;
            float mw_raw = sin(nx * 18.0 + t_fast) * 0.30
                         + sin(nx * 9.0 - t_med + 1.0) * 0.35
                         + sin(nx * 4.0 + u_time * 0.9) * 0.25
                         + sin(nx * 25.0 - t_fast * 1.3) * 0.15;
            // Convert to normalised-Y displacement (divide by amp so eval_line sees
            // the displacement in wave_val space, which it then multiplies by amp).
            float amp1_safe = max(amp1, 0.01);
            mw1 = (mw_raw * mw_drive * micro_wob * 0.18) / amp1_safe;
        }
    }

    float ny1 = ny + displacement_drive * 0.35 * rand_line1.y;
    float crest_dx1;
    float hb1 = heartbeat_bump(nx, sine_freq, phase1, crest_dx1);
    float w1_pre = w1 + mw1 + wfx1 / max(amp1, 0.001);
    float w1_final = apply_heartbeat_spike(w1_pre, hb1, crest_dx1);
    vec4 c1 = eval_line(ny1, inner_height, w1_final, amp1,
                        lineColor1, glowColor1, glow_sigma_base, glow_e1, 0.0, bass_width);

    vec3 final_rgb = c1.rgb * c1.a;
    float final_a = c1.a;

    // =====================================================================
    // LINE 2 — overlaps line 1 at LOB=0/VShift=0; LOB drives X phase, VShift drives Y
    // Line 2 is affected 70% as much as Line 3
    // =====================================================================
    if (lines >= 2) {
        float amp2 = min(base_amplitude * (1.0 + e2_band * 0.75), 0.48);
        float lob_phase2 = lob * 0.45 * 0.7;  // X-axis separation — tight to line 1
        float add_shift2 = u_sine_line2_shift * TWO_PI;
        vec2 rand_line2 = randomDirection(2, 0.85 + displacement_strength * 1.2);
        float phase_jitter2 = displacement_drive * TWO_PI * 1.35 * rand_line2.x;
        float w2 = sin(nx * sine_freq + lob_phase2 + phase2 + add_shift2 + phase_jitter2);

        // Wave effect: at LOB=0 use line 1's wfx for perfect alignment;
        // as LOB increases, blend toward line 2's unique pattern.
        float wfx2 = 0.0;
        if (wave_fx > 0.001) {
            float we2_raw = u_mid_energy * 0.7 + u_bass_energy * 0.15 + u_high_energy * 0.15;
            float we2 = sqrt(max(we2_raw, 0.0));
            float wfx_raw2_own = sin(nx * 7.7 + u_time * 2.1) * 0.45
                               + sin(nx * 13.3 - u_time * 1.3) * 0.30;
            float wfx2_own = wfx_raw2_own * we2 * wave_fx * base_amplitude;
            wfx2 = mix(wfx1, wfx2_own, lob);
        }

        // Micro wobble: same LOB-blend approach
        float mw2 = 0.0;
        if (micro_wob > 0.001 && play_gate > 0.5) {
            float mw_energy2 = u_bass_energy * 0.50 + u_mid_energy * 0.35 + u_high_energy * 0.15;
            float mw_drive2 = clamp(mw_energy2 * 1.8, 0.0, 1.5);
            if (mw_drive2 > 0.001) {
                float t_fast2 = u_time * 3.2;
                float t_med2  = u_time * 1.6;
                float mw_raw2 = sin(nx * 20.0 + t_fast2 + 1.2) * 0.30
                              + sin(nx * 10.5 - t_med2 + 0.7) * 0.35
                              + sin(nx * 5.0 + u_time * 0.7 + 2.1) * 0.25
                              + sin(nx * 27.0 - t_fast2 * 1.1 + 3.0) * 0.15;
                float amp2_safe = max(amp2, 0.01);
                float mw2_own = (mw_raw2 * mw_drive2 * micro_wob * 0.18) / amp2_safe;
                mw2 = mix(mw1, mw2_own, lob);
            }
        }

        // Y-axis separation: Line 2 at +70% of vertical shift
        // At v_spacing=0 (VShift=0), ny2 == ny — perfectly aligned with Line 1
        float ny2 = ny + v_spacing * 0.7 + displacement_drive * 0.5 * rand_line2.y;

        float sigma2 = (u_sine_line_dim == 1) ? glow_sigma_base * 0.925 : glow_sigma_base;
        float crest_dx2;
        float hb2 = heartbeat_bump(nx, sine_freq, lob_phase2 + phase2, crest_dx2);
        float w2_pre = w2 + mw2 + wfx2 / max(amp2, 0.001);
        float w2_final = apply_heartbeat_spike(w2_pre, hb2, crest_dx2);
        vec4 c2 = eval_line(ny2, inner_height, w2_final, amp2,
                            lineColor2, glowColor2, sigma2, glow_e2, 0.0, bass_width);
        float src_alpha2 = clamp(c2.a, 0.0, 1.0);
        vec3 src_rgb2 = c2.rgb * src_alpha2;
        float keep2 = 1.0 - src_alpha2;
        final_rgb = final_rgb * keep2 + src_rgb2;
        final_a = final_a + src_alpha2 * (1.0 - final_a);
    }

    // =====================================================================
    // LINE 3 — overlaps line 1 at LOB=0/VShift=0; LOB drives X phase, VShift drives Y
    // Line 3 is affected 100% (full factor)
    // =====================================================================
    if (lines >= 3) {
        float amp3 = min(base_amplitude * (1.0 + e3_band * 0.75), 0.48);
        float lob_phase3 = lob * 0.90;  // X-axis separation — tight to line 1
        float add_shift3 = u_sine_line3_shift * TWO_PI;
        vec2 rand_line3 = randomDirection(3, 1.0 + displacement_strength * 1.35);
        float phase_jitter3 = displacement_drive * TWO_PI * 1.65 * rand_line3.x;
        float w3 = sin(nx * sine_freq + lob_phase3 + phase3 + add_shift3 + phase_jitter3);

        // Wave effect: at LOB=0 use line 1's wfx for perfect alignment;
        // as LOB increases, blend toward line 3's unique pattern.
        float wfx3 = 0.0;
        if (wave_fx > 0.001) {
            float we3_raw = u_mid_energy * 0.65 + u_high_energy * 0.25 + u_bass_energy * 0.1;
            float we3 = sqrt(max(we3_raw, 0.0));
            float wfx_raw3_own = sin(nx * 4.3 - u_time * 1.9) * 0.40
                               + sin(nx * 9.7 + u_time * 2.7) * 0.30;
            float wfx3_own = wfx_raw3_own * we3 * wave_fx * base_amplitude;
            wfx3 = mix(wfx1, wfx3_own, lob);
        }

        // Micro wobble: same LOB-blend approach
        float mw3 = 0.0;
        if (micro_wob > 0.001 && play_gate > 0.5) {
            float mw_energy3 = u_bass_energy * 0.45 + u_mid_energy * 0.30 + u_high_energy * 0.25;
            float mw_drive3 = clamp(mw_energy3 * 1.8, 0.0, 1.5);
            if (mw_drive3 > 0.001) {
                float t_fast3 = u_time * 3.8;
                float t_med3  = u_time * 2.0;
                float mw_raw3 = sin(nx * 16.0 - t_fast3 + 2.5) * 0.30
                              + sin(nx * 8.0 + t_med3 + 1.8) * 0.35
                              + sin(nx * 3.5 - u_time * 0.6 + 3.3) * 0.25
                              + sin(nx * 22.0 + t_fast3 * 1.2 + 0.5) * 0.15;
                float amp3_safe = max(amp3, 0.01);
                float mw3_own = (mw_raw3 * mw_drive3 * micro_wob * 0.18) / amp3_safe;
                mw3 = mix(mw1, mw3_own, lob);
            }
        }

        // Y-axis separation: Line 3 at -100% of vertical shift (opposite direction)
        // At v_spacing=0 (VShift=0), ny3 == ny — perfectly aligned with Line 1
        float ny3 = ny - v_spacing + displacement_drive * 0.65 * rand_line3.y;

        float sigma3 = (u_sine_line_dim == 1) ? glow_sigma_base * 0.85 : glow_sigma_base;
        float crest_dx3;
        float hb3 = heartbeat_bump(nx, sine_freq, lob_phase3 + phase3, crest_dx3);
        float w3_pre = w3 + mw3 + wfx3 / max(amp3, 0.001);
        float w3_final = apply_heartbeat_spike(w3_pre, hb3, crest_dx3);
        vec4 c3 = eval_line(ny3, inner_height, w3_final, amp3,
                            lineColor3, glowColor3, sigma3, glow_e3, 0.0, bass_width);
        float src_alpha3 = clamp(c3.a, 0.0, 1.0);
        vec3 src_rgb3 = c3.rgb * src_alpha3;
        float keep3 = 1.0 - src_alpha3;
        final_rgb = final_rgb * keep3 + src_rgb3;
        final_a = final_a + src_alpha3 * (1.0 - final_a);
    }

    if (final_a <= 0.001) {
        discard;
    }

    vec3 out_rgb = clamp(final_rgb / max(final_a, 0.001), 0.0, 1.0);
    fragColor = vec4(out_rgb, final_a * u_fade);
}
