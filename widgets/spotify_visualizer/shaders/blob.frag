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
uniform float u_blob_reactive_deformation;  // 0..2 scales outward energy growth (default 1.0)
uniform float u_blob_intensity_reserve;  // 0..2 hidden headroom held for high-energy spikes
uniform float u_blob_constant_wobble;  // 0..2 base wobble amplitude (default 1.0)
uniform float u_blob_reactive_wobble;  // 0..2 energy-driven wobble with vocal emphasis (default 1.0)
uniform float u_blob_stretch_tendency; // 0..1 how much peak energy juts outward (default 0.0)
uniform int u_playing;                 // 1 = audio playing, 0 = stopped
uniform float u_rainbow_hue_offset;    // 0..1 hue rotation (0 = disabled)

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

// 2D SDF organic blob with audio-reactive deformation
float blob_sdf(vec2 p, float time) {
    float r = 0.44 * clamp(u_blob_size, 0.1, 2.5);  // 10% larger minimum
    // Bass-driven core size boost: ~15% larger base at intense bass (quadratic ramp)
    r += u_bass_energy * u_bass_energy * 0.066;
    // Bass pulse — breathe the radius (+15% drum reactivity: 0.084 → 0.097)
    r += u_bass_energy * 0.077 * u_blob_pulse;
    // Subtle contraction on energy dips (~10% of pulse range, smoothed to avoid flicker)
    float se = clamp(u_blob_smoothed_energy, 0.0, 1.0);
    r -= (1.0 - se) * 0.053 * u_blob_pulse;

    // Headroom reserve — kicks in on high-frequency spikes so reserve=0 is a no-op.
    float reserve = clamp(u_blob_intensity_reserve, 0.0, 2.0);
    if (reserve > 0.0001) {
        float high = clamp(u_high_energy, 0.0, 1.0);
        // Trigger slightly earlier (≈45% hi-hat energy) so the boost is noticeable in busy tracks.
        float spike = max(0.0, high - 0.45);
        float gate = smoothstep(0.0, 0.25, spike);
        // Quadratic response keeps sustain tame while letting spikes expand the core dramatically.
        float reserve_boost = spike * spike * 0.25 * reserve;
        r += reserve_boost * gate;
    }

    // Shrink significantly when playback is stopped (to ~45% of normal)
    if (u_playing == 0) {
        r *= 0.45 + se * 0.25;  // smoothed energy keeps shrink gradual
    }

    float angle = atan(p.y, p.x);
    float dist = length(p);

    // Organic deformation: constant wobble (time-driven) and reactive wobble (energy-driven)
    // are cleanly separated so cw=0 means truly no wobble during silence.
    float rd = clamp(u_blob_reactive_deformation, 0.0, 3.0);
    float cw = clamp(u_blob_constant_wobble, 0.0, 2.0);
    float rw = clamp(u_blob_reactive_wobble, 0.0, 2.0);
    float st = clamp(u_blob_stretch_tendency, 0.0, 1.0);
    float deform = 0.0;

    // Constant wobble: reduced amplitude for rounder shape at silence
    deform += sin(angle * 3.0 + time * 1.5) * 0.045 * 0.3 * cw;
    deform += sin(angle * 5.0 - time * 2.3) * 0.028 * 0.2 * cw;
    deform += sin(angle * 7.0 + time * 3.1) * 0.017 * 0.1 * cw;
    deform += sin(angle * 1.0 + time * 0.2) * 0.013 * cw;

    // Reactive wobble: energy-driven, zero when silent regardless of rw
    deform += sin(angle * 3.0 + time * 1.5) * 0.067 * u_mid_energy * 0.7 * rw;
    deform += sin(angle * 5.0 - time * 2.3) * 0.042 * u_mid_energy * 0.8 * rw;
    deform += sin(angle * 7.0 + time * 3.1) * 0.025 * u_high_energy * 0.9 * rw;
    deform += sin(angle * 11.0 - time * 4.7) * 0.013 * u_high_energy * rw;

    // Vocal-reactive wobble: smooth low-frequency shape change driven by mid (vocal) energy
    float vocal = clamp(u_mid_energy, 0.0, 1.0);
    deform += sin(angle * 2.0 + time * 0.9) * 0.080 * vocal * rw;
    deform += sin(angle * 4.0 - time * 1.1) * 0.050 * vocal * vocal * rw;

    // Stretch tendency: peak energy juts outward as dramatic tendrils
    // At max, loud moments cause long reaching bursts far beyond normal radius
    if (st > 0.01) {
        float peak = max(u_bass_energy, max(u_mid_energy, u_high_energy));
        float peak2 = peak * peak;
        float peak3 = peak2 * peak;  // cubic for explosive spikes
        // Multiple angular frequencies create varied, asymmetric tendrils
        float stretch = 0.0;
        // Dominant tendrils — large amplitude, slow rotation
        stretch += sin(angle * 2.0 + time * 0.7) * peak3 * 1.8;
        stretch += sin(angle * 1.0 + time * 0.15) * peak2 * 1.2;
        // Bass-driven bursts — punchy, fast
        stretch += sin(angle * 3.0 - time * 1.3) * u_bass_energy * u_bass_energy * 1.4;
        // Mid/vocal tendrils — sustained reach
        stretch += sin(angle * 5.0 + time * 2.1) * u_mid_energy * u_mid_energy * 0.9;
        stretch += sin(angle * 7.0 - time * 0.5) * u_mid_energy * u_mid_energy * 0.7;
        // High-frequency filigree
        stretch += sin(angle * 9.0 + time * 3.3) * u_high_energy * 0.5;
        deform += stretch * st;
    }

    // Scale total deformation by reactive deformation factor
    // Cubic scaling above 1.0 for truly dramatic stretching at high values
    float rd_scale = rd <= 1.0 ? rd : 1.0 + (rd - 1.0) * (rd - 1.0) * (rd - 1.0) * 4.0 + (rd - 1.0) * 2.0;
    deform *= rd_scale;

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
        glow_sigma = (1.5 + gi * 5.0) + e * e * (20.0 + gi * 40.0);
        glow_strength = (0.02 + gi * 0.08) + e * (0.40 + gi * 0.8);
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
    vec3 edge_rgb = u_blob_edge_color.rgb;      // EDGE stays exempt
    vec3 glow_rgb = u_blob_glow_color.rgb;
    vec3 outline_rgb = u_blob_outline_color.rgb;
    bool rainbow_active = (u_rainbow_hue_offset > 0.001);
    if (rainbow_active) {
        blob_rgb = apply_rainbow_shift(blob_rgb);
        glow_rgb = apply_rainbow_shift(glow_rgb);
        outline_rgb = apply_rainbow_shift(outline_rgb);
    }
    // Bright core: blend fill toward white
    vec3 core_rgb = mix(blob_rgb, vec3(1.0), 0.55);

    // Outline band colour (the dark/grey area between fill edge and glow)

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
