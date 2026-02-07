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

// Energy
uniform float u_overall_energy;

// Glow configuration
uniform int u_glow_enabled;
uniform float u_glow_intensity;
uniform vec4 u_glow_color;
uniform int u_reactive_glow;

// Catmull-Rom spline interpolation for smooth waveform curves
float catmull_rom(float p0, float p1, float p2, float p3, float t) {
    float t2 = t * t;
    float t3 = t2 * t;
    return 0.5 * ((2.0 * p1) +
                   (-p0 + p2) * t +
                   (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 +
                   (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3);
}

float get_waveform_sample(int idx) {
    int clamped = clamp(idx, 0, u_waveform_count - 1);
    return u_waveform[clamped];
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

    // Margins matching the card inset
    float margin_x = 8.0;
    float margin_y = 6.0;
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

    // Sample waveform with Catmull-Rom interpolation
    int wf_count = max(u_waveform_count, 2);
    float sample_pos = nx * float(wf_count - 1);
    int idx = int(floor(sample_pos));
    float frac = sample_pos - float(idx);

    float s0 = get_waveform_sample(idx - 1);
    float s1 = get_waveform_sample(idx);
    float s2 = get_waveform_sample(idx + 1);
    float s3 = get_waveform_sample(idx + 2);

    float wave_val = catmull_rom(s0, s1, s2, s3, frac);

    // Map waveform value (-1..1) to vertical position (0..1)
    // Amplitude scaling: moderate so the wave fills ~60% of card height
    float amplitude = 0.35;
    float wave_y = 0.5 + wave_val * amplitude;

    // Signed distance from fragment to the waveform curve
    float dist = abs(ny - wave_y);

    // Scale distance by inner_height for pixel-level control
    float dist_px = dist * inner_height;

    // Anti-aliased line (2px base width)
    float line_width = 2.0;
    float line_alpha = 1.0 - smoothstep(0.0, line_width, dist_px);

    // Base line colour: use glow_color if glow is enabled, else white
    vec4 line_color;
    if (u_glow_enabled == 1) {
        line_color = u_glow_color;
    } else {
        line_color = vec4(1.0, 1.0, 1.0, 1.0);
    }

    // Glow effect
    float glow_alpha = 0.0;
    if (u_glow_enabled == 1 && u_glow_intensity > 0.0) {
        float sigma = u_glow_intensity * 8.0;  // spread in pixels

        // Reactive glow: modulate sigma by energy
        if (u_reactive_glow == 1) {
            sigma *= (0.5 + u_overall_energy * 1.5);
        }

        if (sigma > 0.0) {
            glow_alpha = exp(-(dist_px * dist_px) / (2.0 * sigma * sigma));
            // Boost glow brightness with energy when reactive
            if (u_reactive_glow == 1) {
                glow_alpha *= (0.6 + u_overall_energy * 0.8);
            }
        }
    }

    // Combine line + glow
    float total_alpha = max(line_alpha, glow_alpha * 0.7);
    if (total_alpha <= 0.001) {
        discard;
    }

    // Blend line colour with glow colour
    vec3 final_rgb;
    if (line_alpha > 0.0 && glow_alpha > 0.0) {
        // Core line is bright white/glow_color, glow halo uses glow_color
        float blend = line_alpha / max(total_alpha, 0.001);
        vec3 core = vec3(1.0);  // bright white core
        vec3 halo = u_glow_color.rgb;
        final_rgb = mix(halo, core, blend);
    } else if (line_alpha > 0.0) {
        final_rgb = line_color.rgb;
    } else {
        final_rgb = u_glow_color.rgb;
    }

    fragColor = vec4(final_rgb, total_alpha * u_fade);
}
