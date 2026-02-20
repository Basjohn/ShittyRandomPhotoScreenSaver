#version 330 core
in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;
uniform float u_dpr;
uniform float u_fade;
uniform float u_time;

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

// Heartbeat bump: localised triangular spikes at sine ZERO-CROSSINGS (slopes).
// Spikes appear on the slopes of the wave, not at peaks/troughs.
// The same bump positions are used for ALL lines so they fire in unison.
// sine_freq_local: the sine frequency used for the wave (needed to find zero-crossings)
// phase_local: the phase offset of this particular line
float heartbeat_bump(float nx, float sine_freq_local, float phase_local) {
    if (u_heartbeat < 0.001 || u_heartbeat_intensity < 0.001) return 0.0;

    // Find the 6 zero-crossing x-positions of sin(x * freq + phase) in [0,1].
    // Zero crossings occur at x*freq+phase = n*PI, so x = (n*PI - phase) / freq.
    float bump = 0.0;
    float intensity = u_heartbeat_intensity;
    float half_w = 0.025;  // narrow spike width (2.5% of card width)

    for (int n = 0; n < 8; n++) {
        float zx = (float(n) * 3.14159265 - phase_local) / sine_freq_local;
        if (zx < 0.02 || zx > 0.98) continue;  // skip edges

        float dx = nx - zx;
        float tri = 1.0 - clamp(abs(dx) / half_w, 0.0, 1.0);
        tri = tri * tri;  // sharpen to triangular point

        // Direction: alternate up/down based on which zero-crossing
        float sign_dir = (n % 2 == 0) ? 1.0 : -1.0;
        bump += tri * sign_dir;
    }

    // Moderate multiplier — visible spikes but not gross distortion
    return bump * u_heartbeat * intensity * 0.35;
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

    float total_alpha = max(line_alpha, glow_alpha * 0.7);
    if (total_alpha <= 0.001) {
        return vec4(0.0);
    }

    vec3 rgb;
    if (line_alpha > 0.0 && glow_alpha > 0.0) {
        float blend = line_alpha / max(total_alpha, 0.001);
        rgb = mix(glowCol.rgb, lineCol.rgb, blend);
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

    float margin_x = 3.0;
    float margin_y = 1.0;
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
    float adapt = clamp(u_card_adaptation, 0.05, 1.0);
    float base_amplitude = (0.5 - 1.0 / max(inner_height, 2.0)) * adapt;
    float glow_sigma_base = u_glow_intensity * 8.0;

    int lines = clamp(u_line_count, 1, 3);

    // Sensitivity: controls how much BASS drives pulsing amplitude
    float sens = clamp(u_sensitivity, 0.1, 5.0);

    // Per-line energy: sensitivity only drives amplitude pulse, NOT glow.
    // bass_pulse = sensitivity-scaled bass for amplitude pulsing only.
    float bass_pulse = u_bass_energy * sens * 2.0;

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

    // Sine frequency: 3 full cycles across the card width
    float sine_freq = 6.2831853 * 3.0;

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

    // =====================================================================
    // LINE 1 (primary) — always centered vertically
    // =====================================================================
    // Energy drives amplitude pulsing. Clamp to 0.48 to stay in card.
    float amp1 = min(base_amplitude * (1.0 + e1 * 1.5), 0.48);
    float w1 = sin(nx * sine_freq + phase1);

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

    float ny1 = ny;
    float hb1 = heartbeat_bump(nx, sine_freq, phase1);
    float w1_final = w1 + mw1 + hb1 + wfx1 / max(amp1, 0.001);
    vec4 c1 = eval_line(ny1, inner_height, w1_final, amp1,
                        u_line_color, u_glow_color, glow_sigma_base, glow_e1, 0.0, bass_width);

    vec3 final_rgb = c1.rgb * c1.a;
    float final_a = c1.a;

    // =====================================================================
    // LINE 2 — overlaps line 1 at LOB=0/VShift=0; LOB drives X phase, VShift drives Y
    // Line 2 is affected 70% as much as Line 3
    // =====================================================================
    if (lines >= 2) {
        float amp2 = min(base_amplitude * (1.0 + e2_band * 1.5), 0.48);
        float lob_phase2 = lob * 0.45 * 0.7;  // X-axis separation — tight to line 1
        float w2 = sin(nx * sine_freq + lob_phase2 + phase2);

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
        float ny2 = ny + v_spacing * 0.7;

        float sigma2 = (u_sine_line_dim == 1) ? glow_sigma_base * 0.925 : glow_sigma_base;
        float hb2 = heartbeat_bump(nx, sine_freq, lob_phase2 + phase2);
        float w2_final = w2 + mw2 + hb2 + wfx2 / max(amp2, 0.001);
        vec4 c2 = eval_line(ny2, inner_height, w2_final, amp2,
                            u_line2_color, u_line2_glow_color, sigma2, glow_e2, 0.0, bass_width);
        final_rgb = final_rgb * (1.0 - c2.a * 0.5) + c2.rgb * c2.a;
        final_a = max(final_a, c2.a);
    }

    // =====================================================================
    // LINE 3 — overlaps line 1 at LOB=0/VShift=0; LOB drives X phase, VShift drives Y
    // Line 3 is affected 100% (full factor)
    // =====================================================================
    if (lines >= 3) {
        float amp3 = min(base_amplitude * (1.0 + e3_band * 1.5), 0.48);
        float lob_phase3 = lob * 0.90;  // X-axis separation — tight to line 1
        float w3 = sin(nx * sine_freq + lob_phase3 + phase3);

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
        float ny3 = ny - v_spacing;

        float sigma3 = (u_sine_line_dim == 1) ? glow_sigma_base * 0.85 : glow_sigma_base;
        float hb3 = heartbeat_bump(nx, sine_freq, lob_phase3 + phase3);
        float w3_final = w3 + mw3 + hb3 + wfx3 / max(amp3, 0.001);
        vec4 c3 = eval_line(ny3, inner_height, w3_final, amp3,
                            u_line3_color, u_line3_glow_color, sigma3, glow_e3, 0.0, bass_width);
        final_rgb = final_rgb * (1.0 - c3.a * 0.4) + c3.rgb * c3.a;
        final_a = max(final_a, c3.a);
    }

    if (final_a <= 0.001) {
        discard;
    }

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
