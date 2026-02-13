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
uniform int u_osc_line_dim;

// Sine Wave Speed: time multiplier for wave animation
uniform float u_osc_speed;

// Card Adaptation: 0.0-1.0, controls how much of the card height the wave uses
uniform float u_card_adaptation;

// Line Offset Bias: vertical spread between lines in multi-line mode
uniform float u_osc_line_offset_bias;

// Sine Wave Travel: 0 = none, 1 = scroll left, 2 = scroll right
uniform int u_osc_sine_travel;
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
uniform int u_osc_vertical_shift;

// Compute line + glow contribution for one sine line.
// mw_displacement: reserved (pass 0.0; micro wobble is now applied to wave_val before calling)
vec4 eval_line(
    float ny, float inner_height, float wave_val, float amplitude,
    vec4 lineCol, vec4 glowCol, float glowSigmaBase, float band_energy,
    float mw_displacement
) {
    float wave_y = clamp(0.5 + wave_val * amplitude + mw_displacement, 0.0, 1.0);
    float dist = abs(ny - wave_y);
    float dist_px = dist * inner_height;

    float line_width = 2.0;
    float line_alpha = 1.0 - smoothstep(0.0, line_width, dist_px);

    float glow_alpha = 0.0;
    if (u_glow_enabled == 1 && glowSigmaBase > 0.0) {
        float sigma = glowSigmaBase;
        if (u_reactive_glow == 1) {
            // Boosted: reach visible glow at lower energy (20%+ more noticeable)
            sigma *= (0.6 + band_energy * 2.4);
        }
        if (sigma > 0.0) {
            glow_alpha = exp(-(dist_px * dist_px) / (2.0 * sigma * sigma));
            if (u_reactive_glow == 1) {
                glow_alpha *= (0.6 + band_energy * 1.4);
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

    // Per-line energy: base mix + bass pulsing scaled by sensitivity
    // Single mode: modest base + bass*sens for reactive pulsing
    // Multi-line: each line driven by its own band + bass*sens
    float bass_pulse = u_bass_energy * sens * 0.85;
    float e1 = (lines == 1)
        ? (u_mid_energy * 0.35 + u_high_energy * 0.10 + bass_pulse)
        : (u_bass_energy * 0.4 + bass_pulse);
    float e2_band = u_mid_energy * 0.5 + bass_pulse * 0.5;
    float e3_band = u_high_energy * 0.5 + bass_pulse * 0.3;

    // Line Offset Bias: base vertical spread between lines (multi-line)
    float lob = clamp(u_osc_line_offset_bias, 0.0, 1.0);

    // Sine frequency: 3 full cycles across the card width
    float sine_freq = 6.2831853 * 3.0;

    // Speed slider: controls travel rate. Gated on playback.
    float speed = clamp(u_osc_speed, 0.0, 3.0);
    float play_gate = (u_playing == 1) ? 1.0 : 0.0;
    float effective_speed = speed * play_gate;

    // Travel phase per line: ONLY non-zero when direction != NONE (0).
    // 1=left (positive phase shift), 2=right (negative phase shift)
    float phase1 = 0.0;
    if (u_osc_sine_travel == 1) phase1 = u_time * 2.0 * effective_speed;
    if (u_osc_sine_travel == 2) phase1 = u_time * -2.0 * effective_speed;

    float phase2 = 0.0;
    if (u_sine_travel_line2 == 1) phase2 = u_time * 2.0 * effective_speed;
    if (u_sine_travel_line2 == 2) phase2 = u_time * -2.0 * effective_speed;

    float phase3 = 0.0;
    if (u_sine_travel_line3 == 1) phase3 = u_time * 2.0 * effective_speed;
    if (u_sine_travel_line3 == 2) phase3 = u_time * -2.0 * effective_speed;

    // Wave effect amount (positional undulation)
    float wave_fx = clamp(u_wave_effect, 0.0, 1.0);

    // Micro wobble amount (energy-reactive micro distortions)
    float micro_wob = clamp(u_micro_wobble, 0.0, 1.0);

    // Vertical shift: purely Y-positioning of lines (does NOT affect amplitude/shape)
    // 0 = no spread, 100 = default spread, 200 = 2x spread, negative = inverted
    float v_shift_pct = float(u_osc_vertical_shift) / 100.0;
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
    // wave_val is raw sine in [-1, 1]. amplitude is the SOLE vertical scaler.
    // Energy adds a significant boost to amplitude so wave reacts to vocals.
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

    // Micro wobble: high-frequency energy-reactive bumps/dents along the line
    // Bass-driven so it reacts to kick/bass hits. Higher scale for visible small bursts.
    // Added to wave_val BEFORE amplitude scaling so they distort the shape itself
    float mw1 = 0.0;
    if (micro_wob > 0.001 && play_gate > 0.5) {
        // Bass-dominant energy drive for reactive wobble
        float mw_energy = u_bass_energy * 0.65 + u_mid_energy * 0.25 + u_high_energy * 0.10;
        float mw_drive = clamp(mw_energy * 2.5, 0.0, 1.0);
        if (mw_drive > 0.01) {
            // HIGH spatial frequencies for visible jagged bumps
            // Moderate time speeds for smooth-ish motion (not choppy)
            float mw_raw = sin(nx * 127.0 + u_time * 1.8) * 0.28
                         + sin(nx * 197.0 - u_time * 2.5) * 0.24
                         + sin(nx * 283.0 + u_time * 1.4) * 0.20
                         + sin(nx * 89.0 - u_time * 3.0) * 0.16
                         + sin(nx * 163.0 + u_time * 1.1) * 0.12;
            // Scale: at full slider, bumps are ~0.25 of wave amplitude for visible bursts
            mw1 = mw_raw * mw_drive * micro_wob * 0.25;
        }
    }

    float ny1 = ny;
    // Micro wobble added to wave value (distorts shape), wave effect added as position shift
    float w1_final = w1 + mw1 + wfx1 / max(amp1, 0.001);
    vec4 c1 = eval_line(ny1, inner_height, w1_final, amp1,
                        u_line_color, u_glow_color, glow_sigma_base, e1, 0.0);

    vec3 final_rgb = c1.rgb * c1.a;
    float final_a = c1.a;

    // =====================================================================
    // LINE 2 — shifted above center when vertical shift enabled
    // =====================================================================
    if (lines >= 2) {
        float amp2 = min(base_amplitude * (1.0 + e2_band * 1.5), 0.48);
        float w2 = sin(nx * sine_freq + 2.094 + phase2);

        float wfx2 = 0.0;
        if (wave_fx > 0.001) {
            float we2_raw = u_mid_energy * 0.7 + u_bass_energy * 0.15 + u_high_energy * 0.15;
            float we2 = sqrt(max(we2_raw, 0.0));
            float wfx_raw2 = sin(nx * 7.7 + u_time * 2.1) * 0.45
                           + sin(nx * 13.3 - u_time * 1.3) * 0.30;
            wfx2 = wfx_raw2 * we2 * wave_fx * base_amplitude;
        }

        float mw2 = 0.0;
        if (micro_wob > 0.001 && play_gate > 0.5) {
            float mw_energy2 = u_bass_energy * 0.65 + u_mid_energy * 0.25 + u_high_energy * 0.10;
            float mw_drive2 = clamp(mw_energy2 * 2.5, 0.0, 1.0);
            if (mw_drive2 > 0.01) {
                float mw_raw2 = sin(nx * 139.0 + u_time * 2.0) * 0.28
                              + sin(nx * 211.0 - u_time * 2.3) * 0.24
                              + sin(nx * 271.0 + u_time * 1.6) * 0.20
                              + sin(nx * 97.0 - u_time * 3.2) * 0.16
                              + sin(nx * 173.0 + u_time * 1.3) * 0.12;
                mw2 = mw_raw2 * mw_drive2 * micro_wob * 0.25;
            }
        }

        float ny2;
        if (abs(v_shift_pct) > 0.001) {
            // Vertical shift is purely positional — do NOT override amplitude
            ny2 = ny + v_spacing;
        } else {
            ny2 = ny - lob * 0.12;
        }

        float sigma2 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.925 : glow_sigma_base;
        float w2_final = w2 + mw2 + wfx2 / max(amp2, 0.001);
        vec4 c2 = eval_line(ny2, inner_height, w2_final, amp2,
                            u_line2_color, u_line2_glow_color, sigma2, e2_band, 0.0);
        final_rgb = final_rgb * (1.0 - c2.a * 0.5) + c2.rgb * c2.a;
        final_a = max(final_a, c2.a);
    }

    // =====================================================================
    // LINE 3 — shifted below center when vertical shift enabled
    // =====================================================================
    if (lines >= 3) {
        float amp3 = min(base_amplitude * (1.0 + e3_band * 1.5), 0.48);
        float w3 = sin(nx * sine_freq + 4.189 + phase3);

        float wfx3 = 0.0;
        if (wave_fx > 0.001) {
            float we3_raw = u_mid_energy * 0.65 + u_high_energy * 0.25 + u_bass_energy * 0.1;
            float we3 = sqrt(max(we3_raw, 0.0));
            float wfx_raw3 = sin(nx * 4.3 - u_time * 1.9) * 0.40
                           + sin(nx * 9.7 + u_time * 2.7) * 0.30;
            wfx3 = wfx_raw3 * we3 * wave_fx * base_amplitude;
        }

        float mw3 = 0.0;
        if (micro_wob > 0.001 && play_gate > 0.5) {
            float mw_energy3 = u_bass_energy * 0.65 + u_mid_energy * 0.20 + u_high_energy * 0.15;
            float mw_drive3 = clamp(mw_energy3 * 2.5, 0.0, 1.0);
            if (mw_drive3 > 0.01) {
                float mw_raw3 = sin(nx * 151.0 - u_time * 2.2) * 0.28
                              + sin(nx * 223.0 + u_time * 2.4) * 0.24
                              + sin(nx * 293.0 - u_time * 1.5) * 0.20
                              + sin(nx * 107.0 + u_time * 3.3) * 0.16
                              + sin(nx * 181.0 - u_time * 1.0) * 0.12;
                mw3 = mw_raw3 * mw_drive3 * micro_wob * 0.25;
            }
        }

        float ny3;
        if (abs(v_shift_pct) > 0.001) {
            // Vertical shift is purely positional — do NOT override amplitude
            ny3 = ny - v_spacing;
        } else {
            ny3 = ny + lob * 0.12;
        }

        float sigma3 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.85 : glow_sigma_base;
        float w3_final = w3 + mw3 + wfx3 / max(amp3, 0.001);
        vec4 c3 = eval_line(ny3, inner_height, w3_final, amp3,
                            u_line3_color, u_line3_glow_color, sigma3, e3_band, 0.0);
        final_rgb = final_rgb * (1.0 - c3.a * 0.4) + c3.rgb * c3.a;
        final_a = max(final_a, c3.a);
    }

    if (final_a <= 0.001) {
        discard;
    }

    if (final_a > 0.001) {
        final_rgb = clamp(final_rgb / final_a, 0.0, 1.0);
    }

    fragColor = vec4(final_rgb, final_a * u_fade);
}
