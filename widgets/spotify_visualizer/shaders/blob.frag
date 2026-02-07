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
uniform float u_high_energy;
uniform float u_overall_energy;

// Blob configuration
uniform vec4 u_blob_color;
uniform vec4 u_blob_glow_color;
uniform vec4 u_blob_edge_color;
uniform float u_blob_pulse;
uniform float u_blob_width;  // (legacy, no longer used in shader — card width is widget-level)
uniform float u_blob_size;   // 0.3..2.0  relative blob scale (default 1.0)
uniform float u_blob_glow_intensity;  // 0..1  glow size/strength (default 0.5)
uniform int u_blob_reactive_glow;  // 0 = static glow, 1 = energy-reactive
uniform vec4 u_blob_outline_color;  // colour for the dark band between fill and glow
uniform float u_blob_smoothed_energy;  // CPU-side smoothed energy (reduces flicker)

// 2D SDF organic blob with audio-reactive deformation
float blob_sdf(vec2 p, float time) {
    float r = 0.28 * clamp(u_blob_size, 0.3, 2.0);
    // Bass pulse — breathe the radius (+15% drum reactivity: 0.084 → 0.097)
    r += u_bass_energy * 0.097 * u_blob_pulse;
    // Subtle contraction on energy dips (~10% of pulse range, smoothed to avoid flicker)
    float se = clamp(u_blob_smoothed_energy, 0.0, 1.0);
    r -= (1.0 - se) * 0.010 * u_blob_pulse;

    float angle = atan(p.y, p.x);
    float dist = length(p);

    // Organic deformation: layered sine waves driven by energy bands
    float deform = 0.0;
    deform += sin(angle * 3.0 + time * 1.5) * 0.067 * (0.3 + u_mid_energy * 0.7);
    deform += sin(angle * 5.0 - time * 2.3) * 0.042 * (0.2 + u_mid_energy * 0.8);
    deform += sin(angle * 7.0 + time * 3.1) * 0.025 * (0.1 + u_high_energy * 0.9);
    deform += sin(angle * 11.0 - time * 4.7) * 0.013 * u_high_energy;

    // Overall energy wobble
    deform += sin(angle * 2.0 + time * 0.8) * 0.034 * u_overall_energy;

    // Vocal-reactive wobble: smooth low-frequency shape change driven by mid (vocal) energy
    // Uses slow angular frequencies and time evolution to preserve organic smoothness
    float vocal = clamp(u_mid_energy, 0.0, 1.0);
    deform += sin(angle * 2.0 + time * 0.7) * 0.038 * vocal;
    deform += sin(angle * 4.0 - time * 1.1) * 0.022 * vocal * vocal;

    return dist - r - deform;
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

    float margin_x = 8.0;
    float margin_y = 6.0;

    if (fc.x < margin_x || fc.x > width - margin_x ||
        fc.y < margin_y || fc.y > height - margin_y) {
        discard;
    }

    float inner_width = width - margin_x * 2.0;
    float inner_height = height - margin_y * 2.0;
    if (inner_width <= 0.0 || inner_height <= 0.0) {
        discard;
    }

    // Normalised position centered at (0, 0), aspect-corrected
    vec2 uv = vec2(
        (fc.x - margin_x) / inner_height - (inner_width / inner_height) * 0.5,
        (fc.y - margin_y) / inner_height - 0.5
    );

    float d = blob_sdf(uv, u_time);

    // Multi-layer colouring from the SDF distance
    // Inner core: bright, slightly shifted hue
    // Edge: blob_color
    // Glow: soft falloff outside the blob

    // Inner fill
    float fill_alpha = 1.0 - smoothstep(-0.02, 0.0, d);

    // Edge highlight (respects edge colour alpha channel)
    float edge_alpha = 1.0 - smoothstep(0.0, 0.008, abs(d));
    edge_alpha *= 0.8 * u_blob_edge_color.a;

    float outline_a = u_blob_outline_color.a;

    // Outer glow
    // Reactive: dramatic range from barely visible (silence) to intense (loud)
    // Static: fixed moderate glow
    float glow_sigma;
    float glow_strength;
    float gi = clamp(u_blob_glow_intensity, 0.0, 1.0);
    if (u_blob_reactive_glow == 1) {
        // Use CPU-smoothed energy to prevent glow flickering
        float e = u_blob_smoothed_energy;
        // Low base (barely visible at silence) → dramatic at full energy
        glow_sigma = (1.5 + gi * 6.0) + e * e * (25.0 + gi * 45.0);
        glow_strength = (0.02 + gi * 0.08) + e * (0.45 + gi * 0.8);
    } else {
        glow_sigma = 4.0 + gi * 25.0;
        glow_strength = 0.15 + gi * 0.6;
    }
    float d_px = d * inner_height;
    float glow_alpha = 0.0;
    if (d > 0.0 && glow_sigma > 0.0) {
        glow_alpha = exp(-(d_px * d_px) / (2.0 * glow_sigma * glow_sigma));
        glow_alpha *= glow_strength;
    }

    // Outline band alpha: ensures the outline zone has solid coverage
    // so there's no transparent gap between the fill edge and glow
    float outline_band_alpha = 0.0;
    if (d >= 0.0 && d < 0.015 && outline_a > 0.01) {
        outline_band_alpha = (1.0 - smoothstep(0.0, 0.015, d)) * outline_a;
    }

    float total_alpha = max(fill_alpha, max(edge_alpha, max(glow_alpha, outline_band_alpha)));
    if (total_alpha <= 0.001) {
        discard;
    }

    // Colour blending using configurable colours
    vec3 blob_rgb = u_blob_color.rgb;
    vec3 edge_rgb = u_blob_edge_color.rgb;
    vec3 glow_rgb = u_blob_glow_color.rgb;
    // Bright core: blend fill toward white
    vec3 core_rgb = mix(blob_rgb, vec3(1.0), 0.55);

    // Outline band colour (the dark/grey area between fill edge and glow)
    vec3 outline_rgb = u_blob_outline_color.rgb;

    vec3 final_rgb;
    if (d < -0.02) {
        // Deep inside: core colour with energy-reactive brightening
        float depth = clamp(-d / 0.15, 0.0, 1.0);
        final_rgb = mix(blob_rgb, core_rgb, depth * (0.3 + u_blob_smoothed_energy * 0.4));
    } else if (d < 0.0) {
        // Near edge: transition from fill to edge highlight colour
        float t = 1.0 - clamp(-d / 0.02, 0.0, 1.0);
        final_rgb = mix(blob_rgb, edge_rgb, t);
    } else if (d < 0.015 && outline_a > 0.01) {
        // Outline band: thin region just outside the fill, before glow takes over
        float band_t = clamp(d / 0.015, 0.0, 1.0);
        final_rgb = mix(edge_rgb, outline_rgb, band_t * outline_a);
    } else {
        // Outside: glow colour
        final_rgb = glow_rgb;
    }

    fragColor = vec4(final_rgb, total_alpha * u_fade);
}
