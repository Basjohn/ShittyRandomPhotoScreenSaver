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

// Wobble: music-reactive positional wobble along the line (0.0-1.0)
// Preserves exact sine shape, only shifts line position up/down
uniform float u_wobble_amount;

// Vertical shift: when 1, spreads lines to fixed top/center/bottom positions
// (same behaviour as oscilloscope vertical shift)
uniform int u_osc_vertical_shift;

// Compute line + glow contribution for one sine line.
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
    float amplitude = (0.5 - 1.0 / max(inner_height, 2.0)) * adapt;
    float glow_sigma_base = u_glow_intensity * 8.0;

    int lines = clamp(u_line_count, 1, 3);

    // Per-line energy: single mode uses overall, multi-line splits by band
    float e1 = (lines == 1) ? u_overall_energy : u_bass_energy * 1.15;
    float e2_band = u_mid_energy * 1.15;
    float e3_band = u_high_energy * 1.15;

    // Sensitivity scales energy contribution
    float sens = clamp(u_sensitivity, 0.1, 5.0);

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

    // Wobble amount
    float wobble = clamp(u_wobble_amount, 0.0, 1.0);

    // Vertical shift: compute spacing once (same as oscilloscope)
    float v_spacing = 0.0;
    if (u_osc_vertical_shift == 1 && lines >= 2) {
        float spacing_px = clamp(inner_height * 0.25, 20.0, 80.0);
        v_spacing = spacing_px / inner_height;
    }

    // =====================================================================
    // LINE 1 (primary) — always centered vertically
    // =====================================================================
    // wave_val is raw sine in [-1, 1]. amplitude is the SOLE vertical scaler.
    // Energy adds a small boost to amplitude, NOT to the wave value itself.
    float amp1 = amplitude * (1.0 + e1 * 0.15 * sens);
    float w1 = sin(nx * sine_freq + phase1);

    // Wobble: positional y-offset in NORMALIZED space (added to wave_y after scaling)
    // This preserves the exact sine shape — only shifts the line up/down organically
    float wob1 = 0.0;
    if (wobble > 0.001) {
        float we1 = (lines == 1) ? u_overall_energy : u_bass_energy;
        float wob_raw = sin(nx * 5.3 + u_time * 1.7) * 0.50
                      + sin(nx * 11.1 - u_time * 2.5) * 0.30
                      + sin(nx * 2.1 + u_time * 0.9) * 0.25;
        wob1 = wob_raw * (0.3 + we1 * 0.7) * wobble * amplitude;
    }

    float ny1 = ny;
    vec4 c1 = eval_line(ny1, inner_height, w1 + wob1 / max(amp1, 0.001), amp1,
                        u_line_color, u_glow_color, glow_sigma_base, e1);

    vec3 final_rgb = c1.rgb * c1.a;
    float final_a = c1.a;

    // =====================================================================
    // LINE 2 — shifted above center when vertical shift enabled
    // =====================================================================
    if (lines >= 2) {
        float amp2 = amplitude * (1.0 + e2_band * 0.15 * sens);
        float w2 = sin(nx * sine_freq + 2.094 + phase2);

        float wob2 = 0.0;
        if (wobble > 0.001) {
            float wob_raw2 = sin(nx * 7.7 + u_time * 2.1) * 0.45
                           + sin(nx * 13.3 - u_time * 1.3) * 0.30;
            wob2 = wob_raw2 * (0.3 + u_mid_energy * 0.7) * wobble * amplitude;
        }

        float ny2;
        if (u_osc_vertical_shift == 1) {
            ny2 = ny + v_spacing;
            amp2 = amplitude * (0.7 + e2_band * 0.15);
        } else {
            ny2 = ny - lob * 0.12;
        }

        float sigma2 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.925 : glow_sigma_base;
        vec4 c2 = eval_line(ny2, inner_height, w2 + wob2 / max(amp2, 0.001), amp2,
                            u_line2_color, u_line2_glow_color, sigma2, e2_band);
        final_rgb = final_rgb * (1.0 - c2.a * 0.5) + c2.rgb * c2.a;
        final_a = max(final_a, c2.a);
    }

    // =====================================================================
    // LINE 3 — shifted below center when vertical shift enabled
    // =====================================================================
    if (lines >= 3) {
        float amp3 = amplitude * (1.0 + e3_band * 0.15 * sens);
        float w3 = sin(nx * sine_freq + 4.189 + phase3);

        float wob3 = 0.0;
        if (wobble > 0.001) {
            float wob_raw3 = sin(nx * 4.3 - u_time * 1.9) * 0.40
                           + sin(nx * 9.7 + u_time * 2.7) * 0.30;
            wob3 = wob_raw3 * (0.3 + u_high_energy * 0.7) * wobble * amplitude;
        }

        float ny3;
        if (u_osc_vertical_shift == 1) {
            ny3 = ny - v_spacing;
            amp3 = amplitude * (0.6 + e3_band * 0.18);
        } else {
            ny3 = ny + lob * 0.12;
        }

        float sigma3 = (u_osc_line_dim == 1) ? glow_sigma_base * 0.85 : glow_sigma_base;
        vec4 c3 = eval_line(ny3, inner_height, w3 + wob3 / max(amp3, 0.001), amp3,
                            u_line3_color, u_line3_glow_color, sigma3, e3_band);
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
