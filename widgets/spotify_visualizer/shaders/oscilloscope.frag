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

float get_waveform_sample(int idx) {
    // Modular wrap so offset lines read valid circular-buffer data
    int n = max(u_waveform_count, 1);
    int wrapped = ((idx % n) + n) % n;
    return u_waveform[wrapped];
}

// Gaussian-weighted multi-tap smoothing around a sample index.
// The smoothing uniform controls the kernel radius: 0 = single sample, 1 = wide blur.
float smoothed_sample(int center) {
    if (u_smoothing <= 0.01) {
        return get_waveform_sample(center);
    }
    // Kernel half-width scales from 1 to 12 taps based on smoothing
    int half_w = int(1.0 + u_smoothing * 11.0);
    float sigma = max(0.5, float(half_w) * 0.45);
    float total = 0.0;
    float weight_sum = 0.0;
    for (int i = -12; i <= 12; i++) {
        if (i < -half_w || i > half_w) continue;
        float w = exp(-float(i * i) / (2.0 * sigma * sigma));
        total += get_waveform_sample(center + i) * w;
        weight_sum += w;
    }
    return total / max(weight_sum, 0.001);
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

// Compute line + glow contribution for one waveform line.
// Returns vec4(rgb, alpha).
vec4 eval_line(
    float ny, float inner_height, float wave_val, float amplitude,
    vec4 lineCol, vec4 glowCol, float glowSigmaBase
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
            sigma *= (0.5 + u_overall_energy * 1.5);
        }
        if (sigma > 0.0) {
            glow_alpha = exp(-(dist_px * dist_px) / (2.0 * sigma * sigma));
            if (u_reactive_glow == 1) {
                glow_alpha *= (0.6 + u_overall_energy * 0.8);
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

    // Primary line (always present)
    float w1 = sample_waveform(nx, 0);
    vec4 c1 = eval_line(ny, inner_height, w1, amplitude,
                        u_line_color, u_glow_color, glow_sigma_base);

    vec3 final_rgb = c1.rgb * c1.a;
    float final_a = c1.a;

    int lines = clamp(u_line_count, 1, 3);

    if (lines >= 2) {
        // Line 2: large phase offset and slightly reduced amplitude
        int wf_count = max(u_waveform_count, 2);
        int offset2 = max(1, wf_count / 3);  // ~33% phase shift
        float w2 = sample_waveform(nx, offset2);
        vec4 c2 = eval_line(ny, inner_height, w2, amplitude * 0.88,
                            u_line2_color, u_line2_glow_color, glow_sigma_base * 0.8);
        // Additive-style blend (back-to-front)
        final_rgb = final_rgb * (1.0 - c2.a * 0.5) + c2.rgb * c2.a * 0.7;
        final_a = max(final_a, c2.a * 0.7);
    }

    if (lines >= 3) {
        // Line 3: even larger offset, moderately reduced amplitude
        int wf_count = max(u_waveform_count, 2);
        int offset3 = max(1, wf_count * 2 / 3);  // ~66% phase shift
        float w3 = sample_waveform(nx, offset3);
        vec4 c3 = eval_line(ny, inner_height, w3, amplitude * 0.72,
                            u_line3_color, u_line3_glow_color, glow_sigma_base * 0.6);
        final_rgb = final_rgb * (1.0 - c3.a * 0.4) + c3.rgb * c3.a * 0.6;
        final_a = max(final_a, c3.a * 0.6);
    }

    if (final_a <= 0.001) {
        discard;
    }

    // Normalise RGB by alpha to prevent over-brightening
    if (final_a > 0.001) {
        final_rgb = clamp(final_rgb / final_a, 0.0, 1.0);
    }

    fragColor = vec4(final_rgb, final_a * u_fade);
}
