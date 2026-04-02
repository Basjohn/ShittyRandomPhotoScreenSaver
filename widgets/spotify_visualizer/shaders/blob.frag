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
uniform float u_blob_shaper_bass_energy;
uniform float u_blob_shaper_mid_energy;
uniform float u_blob_shaper_high_energy;
uniform float u_blob_shaper_overall_energy;

// Blob configuration
uniform vec4 u_blob_color;
uniform vec4 u_blob_glow_color;
uniform vec4 u_blob_edge_color;
uniform vec4 u_blob_outline_color;
uniform float u_blob_pulse;
uniform float u_blob_width;  // (legacy, no longer used in shader — card width is widget-level)
uniform float u_blob_size;   // 0.3..2.0  relative blob scale (default 1.0)
uniform float u_blob_glow_intensity;  // 0..1  glow size/strength (default 0.5)
uniform int u_blob_reactive_glow;  // 0 = static glow, 1 = energy-reactive
uniform float u_blob_smoothed_energy;  // CPU-side smoothed energy (reduces flicker)
uniform float u_blob_glow_energy;  // CPU-side smoothed glow drive (bass or vocal depending on mode)
uniform float u_blob_reactive_deformation;  // 0..2 scales outward energy growth (default 1.0)
uniform float u_blob_stage_gain;  // 0..2 multiplier for staged core sizing
uniform float u_blob_core_scale;  // 0.25..2.5 post-stage scaling of the core radius
uniform float u_blob_core_floor_bias; // 0..0.6 fraction of staged radius preserved during deformations
uniform float u_blob_stage_bias;  // -0.60..0.60 shifts stage thresholds up/down before smoothing
uniform float u_blob_constant_wobble;  // 0..2 base wobble amplitude (default 1.0)
uniform float u_blob_reactive_wobble;  // 0..2 energy-driven wobble with vocal emphasis (default 1.0)
uniform float u_blob_stretch_tendency; // 0..1 how much peak energy juts outward (default 0.35)
uniform float u_blob_stretch_inner;  // 0..1 how deep inward dents can go (default 0.5)
uniform float u_blob_stretch_outer;  // 0..1 how far outward protrusions extend (default 0.5)
uniform vec3 u_blob_stage_progress_override;  // (-1,-1,-1) when unused
uniform int u_playing;                 // 1 = audio playing, 0 = stopped
uniform float u_rainbow_hue_offset;    // 0..1 hue rotation (0 = disabled)
uniform float u_ghost_alpha;           // 0 = no ghost, >0 = ghost outline intensity
uniform float u_blob_peak_energy;      // CPU-tracked peak energy for ghost outline
uniform float u_blob_peak_bass;        // per-band peak for SDF ghost shape
uniform float u_blob_peak_mid;
uniform float u_blob_peak_high;
uniform float u_blob_peak_overall;
uniform float u_blob_glow_reactivity;  // 0..2 how strongly glow responds to energy (default 1.0)
uniform float u_blob_glow_max_size;    // 0.1..3.0 maximum glow spread multiplier (default 1.0)

// Blob Shaper
uniform int u_blob_shaper_enabled;       // 0 = off, 1 = on
uniform float u_blob_shaper_base_strength;   // 0..1 how strongly base profile shapes the blob
uniform float u_blob_shaper_react_strength;  // 0..1 how strongly reaction profile limits deformation
uniform int u_blob_ring_mode;            // 0 = circle (filled), 1 = ring (hollow)
uniform float u_blob_ring_thickness;     // 0.05..1.0 ring wall thickness as fraction of radius

const int SHAPER_N = 64;
uniform float u_blob_base_profile[SHAPER_N];    // angular base radius multipliers
uniform float u_blob_react_profile[SHAPER_N];   // angular reaction limit multipliers
uniform float u_blob_energy_bass[SHAPER_N];     // per-sector bass routing weight
uniform float u_blob_energy_mid[SHAPER_N];      // per-sector mid routing weight
uniform float u_blob_energy_vocals[SHAPER_N];   // per-sector vocal routing weight
uniform float u_blob_energy_treble[SHAPER_N];   // per-sector treble routing weight
uniform float u_blob_energy_transient[SHAPER_N]; // per-sector transient routing weight

const float SHAPER_REST_DEADZONE = 0.12;
const float SHAPER_DRIVE_GAIN = 2.4;

float sample_profile(float angle_frac, float profile[SHAPER_N]) {
    float idx_f = angle_frac * float(SHAPER_N);
    int i1 = int(floor(idx_f)) % SHAPER_N;
    int i0 = (i1 - 1 + SHAPER_N) % SHAPER_N;
    int i2 = (i1 + 1) % SHAPER_N;
    int i3 = (i1 + 2) % SHAPER_N;
    float t = fract(idx_f);
    float t2 = t * t;
    float t3 = t2 * t;
    return 0.5 * (
        (2.0 * profile[i1])
        + (-profile[i0] + profile[i2]) * t
        + (2.0 * profile[i0] - 5.0 * profile[i1] + 4.0 * profile[i2] - profile[i3]) * t2
        + (-profile[i0] + 3.0 * profile[i1] - 3.0 * profile[i2] + profile[i3]) * t3
    );
}

float sample_linear_series(float angle_frac, float profile[SHAPER_N]) {
    float idx_f = angle_frac * float(SHAPER_N);
    int i0 = int(floor(idx_f)) % SHAPER_N;
    int i1 = (i0 + 1) % SHAPER_N;
    float t = fract(idx_f);
    return mix(profile[i0], profile[i1], t);
}

float sample_energy_at_angle(float angle_frac, float bass, float mid, float high, float overall) {
    float bass_w = sample_linear_series(angle_frac, u_blob_energy_bass);
    float mid_w = sample_linear_series(angle_frac, u_blob_energy_mid);
    float vocal_w = sample_linear_series(angle_frac, u_blob_energy_vocals);
    float treble_w = sample_linear_series(angle_frac, u_blob_energy_treble);
    float transient_w = sample_linear_series(angle_frac, u_blob_energy_transient);
    float total_w = abs(bass_w) + abs(mid_w) + abs(vocal_w) + abs(treble_w) + abs(transient_w);
    if (total_w < 0.001) return 0.0;
    return (
        bass * bass_w +
        mid * mid_w +
        mid * vocal_w +
        high * treble_w +
        overall * transient_w
    ) / total_w;
}

float remap_shaper_drive(float signed_energy) {
    if (u_playing == 0) {
        return 0.0;
    }
    signed_energy = clamp(signed_energy * SHAPER_DRIVE_GAIN, -1.0, 1.0);
    float magnitude = abs(signed_energy);
    if (magnitude <= SHAPER_REST_DEADZONE) {
        return 0.0;
    }
    float t = clamp(
        (magnitude - SHAPER_REST_DEADZONE) / max(0.0001, 1.0 - SHAPER_REST_DEADZONE),
        0.0,
        1.0
    );
    float eased = t * t * (3.0 - 2.0 * t);
    return sign(signed_energy) * eased;
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

float clampf(float value, float lo, float hi) {
    return clamp(value, lo, hi);
}

vec3 compute_stage_progress_values(
    float bass_energy,
    float mid_energy,
    float high_energy,
    float overall_energy)
{
    float bass = clamp(bass_energy, 0.0, 1.0);
    float mid = clamp(mid_energy, 0.0, 1.0);
    float high = clamp(high_energy, 0.0, 1.0);
    float overall = clamp(overall_energy, 0.0, 1.0);
    float se = clamp(u_blob_smoothed_energy, 0.0, 1.0);

    float weighted = clamp(bass * 0.56 + overall * 0.28 + high * 0.10 + mid * 0.06, 0.0, 1.0);
    float weighted_stage1 = clamp(weighted * 0.88 + se * 0.12, 0.0, 1.0);
    float base_stage2_drive = clamp(weighted * 0.74 + bass * 0.10 + mid * 0.12 + high * 0.04, 0.0, 1.0);
    float stage2_drive = clamp(base_stage2_drive * 0.84 + se * 0.16, 0.0, 1.0);
    float chorus_drive = clamp(max(stage2_drive, bass * 0.38 + overall * 0.30 + mid * 0.18 + high * 0.14), 0.0, 1.0);
    chorus_drive = clamp(max(chorus_drive, se * 0.34 + overall * 0.44 + mid * 0.22), 0.0, 1.0);

    float bias = clamp(u_blob_stage_bias, -0.60, 0.60);
    if (abs(bias) > 0.00001) {
        weighted_stage1 = clamp(weighted_stage1 + bias * 0.12, 0.0, 1.0);
        stage2_drive = clamp(stage2_drive + bias * 0.10, 0.0, 1.0);
        chorus_drive = clamp(chorus_drive + bias * 0.08, 0.0, 1.0);
    }

    // Blob should climb a ladder, not park on stage 1 forever.
    // Keep stage 1 reachable on ordinary musical support, but leave room for
    // stage 2/3 to appear on stronger passages instead of making the first rung
    // saturate immediately while the later rungs stay effectively unreachable.
    float stage1_t = smoothstep(0.08, 0.34, weighted_stage1);
    float stage2_t = smoothstep(0.16, 0.42, stage2_drive);
    float stage3_t = smoothstep(0.24, 0.52, chorus_drive);
    stage2_t = min(stage2_t, stage1_t);
    stage3_t = min(stage3_t, stage2_t);

    return vec3(stage1_t, stage2_t, stage3_t);
}

float compute_stage_floor_fraction(float bias, vec3 stage_progress) {
    float core_bias = clamp(bias, 0.0, 0.95);
    float stage_floor = core_bias;
    stage_floor += stage_progress.x * 0.05;
    stage_floor += stage_progress.y * 0.08;
    stage_floor += stage_progress.z * 0.12;
    return clamp(stage_floor, 0.0, 0.9);
}

float compute_stage_offset(
    float blob_size,
    float bass_energy,
    float mid_energy,
    float high_energy,
    float overall_energy,
    float stage_gain,
    float core_scale,
    out vec3 stage_progress)
{
    float base_size = clamp(blob_size, 0.1, 2.5);
    float gain = clamp(stage_gain, 0.0, 2.0);
    float scale = clamp(core_scale, 0.25, 2.5);

    if (gain <= 0.0001 || scale <= 0.0) {
        stage_progress = vec3(0.0);
        return 0.0;
    }

    stage_progress = compute_stage_progress_values(bass_energy, mid_energy, high_energy, overall_energy);
    if (u_blob_stage_progress_override.x >= 0.0 &&
        u_blob_stage_progress_override.y >= 0.0 &&
        u_blob_stage_progress_override.z >= 0.0) {
        stage_progress = clamp(u_blob_stage_progress_override, vec3(0.0), vec3(1.0));
    }
    float stage1_t = stage_progress.x;
    float stage2_t = stage_progress.y;
    float stage3_t = stage_progress.z;

    float stage_unit = base_size * 0.18 + 0.02;
    float stage1_amt = stage_unit * 0.58;
    float stage2_amt = stage_unit * 1.22;
    float stage3_amt = stage_unit * 2.10;

    float offset = stage1_t * stage1_amt;
    offset += stage2_t * max(0.0, stage2_amt - stage1_amt);
    offset += stage3_t * max(0.0, stage3_amt - stage2_amt);

    return offset * gain * scale;
}

// 2D SDF organic blob with audio-reactive deformation.
// Accepts per-band energies + smoothed so it can be called with current OR
// peak energies (for ghost shape reconstruction).
float blob_sdf_ex(vec2 p, float time,
                  float e_bass, float e_mid, float e_high, float e_overall,
                  float smoothed_e) {
    float r = 0.44 * clamp(u_blob_size, 0.1, 2.5);
    float pulse_amt = clamp(u_blob_pulse, 0.0, 2.0);
    r += e_bass * e_bass * 0.066 * pulse_amt;
    r += e_bass * 0.077 * pulse_amt;
    float se = clamp(smoothed_e, 0.0, 1.0);
    float breath = max(e_bass, se * 0.82);
    r += max(0.03, breath) * 0.020 * pulse_amt;
    r -= (1.0 - se) * 0.028 * pulse_amt;

    vec3 stage_progress = vec3(0.0);
    r += compute_stage_offset(
        clamp(u_blob_size, 0.1, 2.5),
        e_bass, e_mid, e_high, e_overall,
        u_blob_stage_gain,
        u_blob_core_scale,
        stage_progress
    ) * pulse_amt;

    if (u_playing == 0 && u_blob_shaper_enabled == 0) {
        r *= 0.45 + se * 0.25;
    }

    float staged_r = r;

    float angle = atan(p.y, p.x);
    float dist = length(p);

    // Blob Shaper: base profile modulates radius, energy routing drives per-angle energy
    float angle_frac = fract(angle / 6.2831853 + 0.25);
    float shaper_drive = 0.0;
    if (u_blob_shaper_enabled == 1) {
        float base_mult = sample_profile(angle_frac, u_blob_base_profile);
        float base_str = clamp(u_blob_shaper_base_strength, 0.0, 1.0);
        float react_mult = sample_profile(angle_frac, u_blob_react_profile);
        float react_str = clamp(u_blob_shaper_react_strength, 0.0, 1.0);
        float shaped_base_r = staged_r * mix(1.0, base_mult, base_str);
        float shaped_react_r = staged_r * mix(1.0, react_mult, react_str);
        shaper_drive = remap_shaper_drive(
            clamp(
                sample_energy_at_angle(
                    angle_frac,
                    u_blob_shaper_bass_energy,
                    u_blob_shaper_mid_energy,
                    u_blob_shaper_high_energy,
                    u_blob_shaper_overall_energy
                ),
                -1.0,
                1.0
            )
        );
        r = shaped_base_r + (shaped_react_r - shaped_base_r) * shaper_drive;
        // The authored shaper contour is the runtime silhouette source.
        // Keeping staged_r on shaped_base_r would park runtime on the base
        // contour forever even while shaper_drive changes.
        staged_r = r;
    }

    float rd = clamp(u_blob_reactive_deformation, 0.0, 3.0);
    float cw = clamp(u_blob_constant_wobble, 0.0, 2.0);
    float rw = clamp(u_blob_reactive_wobble, 0.0, 3.0);
    if (u_blob_shaper_enabled == 1) {
        float shaper_motion = abs(shaper_drive);
        // Authored shaper contours should own the silhouette. Keep wobble
        // subordinate and let it disappear entirely at rest/paused.
        cw *= shaper_motion * 0.03;
        rw *= shaper_motion * 0.12;
    }
    // When shaper is enabled, it owns the shape — suppress stretch controls
    // so they don't fight with the shaper's base/reaction profiles.
    // Wobble is kept: it adds organic deformation that complements shaping.
    float st = (u_blob_shaper_enabled == 1) ? 0.0 : clamp(u_blob_stretch_tendency, 0.0, 1.0);
    float s_inner = (u_blob_shaper_enabled == 1) ? 0.0 : clamp(u_blob_stretch_inner, 0.0, 1.0);
    float s_outer = (u_blob_shaper_enabled == 1) ? 0.0 : clamp(u_blob_stretch_outer, 0.0, 1.0);
    float wobble_component = 0.0;

    // Constant wobble — always-present amorphous distortion.
    // Low harmonics give broad lobes, high harmonics add fine detail.
    wobble_component += sin(angle * 2.0 + time * 0.4)  * 0.035 * cw;
    wobble_component += sin(angle * 3.0 + time * 1.5)  * 0.030 * cw;
    wobble_component += sin(angle * 5.0 - time * 2.3)  * 0.020 * cw;
    wobble_component += sin(angle * 7.0 + time * 3.1)  * 0.012 * cw;
    wobble_component += sin(angle * 1.0 + time * 0.2)  * 0.040 * cw;

    // Reactive wobble — energy-driven shape distortion.
    wobble_component += sin(angle * 3.0 + time * 1.5)  * 0.090 * e_mid * rw;
    wobble_component += sin(angle * 5.0 - time * 2.3)  * 0.060 * e_mid * rw;
    wobble_component += sin(angle * 7.0 + time * 3.1)  * 0.008 * e_high * rw;
    wobble_component += sin(angle * 11.0 - time * 4.7) * 0.004 * e_high * rw;

    // Vocal emphasis — mid-range creates broad amorphous lobes.
    float vocal = clamp(e_mid, 0.0, 1.0);
    wobble_component += sin(angle * 2.0 + time * 0.9)  * 0.132 * vocal * rw;
    wobble_component += sin(angle * 4.0 - time * 1.1)  * 0.092 * vocal * vocal * rw;

    float stretch_component = 0.0;
    if (st > 0.01) {
        // Stretch is now primarily vocal-driven with a light bass assist so it
        // stays alive on musical passages without turning every kick into a
        // whole-body spear.
        float vocal_impact = clamp(e_mid * 1.08 + e_high * 0.22, 0.0, 1.0);
        float bass_support = clamp(e_bass * 0.22 + e_overall * 0.10, 0.0, 1.0);
        float impact = clamp(vocal_impact * 0.90 + bass_support * 0.25, 0.0, 1.0);
        float impact2 = impact * impact;
        float impact3 = impact2 * impact;
        float stretch = 0.0;
        stretch += sin(angle * 2.0 + time * 0.7)  * impact3 * 1.18;
        stretch += sin(angle * 1.0 + time * 0.15) * impact2 * 0.82;
        stretch += sin(angle * 4.0 - time * 1.0)  * vocal_impact * vocal_impact * 1.02;
        stretch += sin(angle * 5.0 + time * 2.1)  * vocal_impact * 0.62;
        stretch += sin(angle * 3.0 - time * 1.3)  * bass_support * bass_support * 0.26;
        stretch += sin(angle * 7.0 - time * 0.5)  * e_high * 0.10;
        stretch_component += stretch * st;
    }

    // Scale total deformation by reactive deformation factor
    // Cubic scaling above 1.0 for truly dramatic stretching at high values
    float rd_scale = rd <= 1.0 ? rd : 1.0 + (rd - 1.0) * (rd - 1.0) * (rd - 1.0) * 4.0 + (rd - 1.0) * 2.0;
    wobble_component *= rd_scale;
    stretch_component *= rd_scale;

    // Asymmetric inner/outer scaling on stretch ONLY (not wobble), AFTER rd_scale.
    // Inner controls depth of inward stretch dents, outer controls outward protrusions.
    // Applied after rd_scale so the suppression is final and cannot be amplified back.
    if (stretch_component < 0.0) {
        stretch_component *= mix(0.05, 1.0, s_inner);
    } else {
        stretch_component *= mix(0.05, 1.0, s_outer);
    }

    // Stage-aware core floor clamp: preserve a minimum fraction of staged radius
    float stage_floor = compute_stage_floor_fraction(u_blob_core_floor_bias, stage_progress);
    float min_radius = staged_r * stage_floor;
    float stretch_floor = min_radius - staged_r;
    stretch_floor = min(stretch_floor, 0.0);
    stretch_component = max(stretch_component, stretch_floor);
    float core_radius = staged_r + stretch_component;
    // Wobble always applies in full — the blob must NEVER be a circle.
    float final_radius = core_radius + wobble_component;

    return dist - final_radius;
}

// Convenience wrapper using current uniforms.
float blob_sdf(vec2 p, float time) {
    return blob_sdf_ex(p, time,
        u_bass_energy, u_mid_energy, u_high_energy, u_overall_energy,
        u_blob_smoothed_energy);
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

    // Ring topology — carve out interior to create a hollow ring.
    // Works independently of shaper; ring_mode is set by topology combo.
    if (u_blob_ring_mode == 1) {
        // Ring thickness is a fraction of the blob's visual radius (~0.44 * blob_size)
        float ring_r = 0.44 * clamp(u_blob_size, 0.1, 2.5);
        float thickness = clamp(u_blob_ring_thickness, 0.05, 1.0) * ring_r * 0.5;
        d = abs(d) - thickness;
    }

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
    float g_react = clamp(u_blob_glow_reactivity, 0.0, 2.0);
    float g_max = clamp(u_blob_glow_max_size, 0.1, 3.0);
    if (u_blob_reactive_glow == 1) {
        // Use CPU-smoothed energy to prevent glow flickering
        float e = clamp(u_blob_glow_energy, 0.0, 1.5);
        // Reactivity scales the energy contribution; max_size scales the sigma cap.
        float e_scaled = e * g_react;
        glow_sigma = ((1.5 + gi * 5.0) + e_scaled * e_scaled * (20.0 + gi * 40.0)) * g_max;
        glow_strength = (0.02 + gi * 0.08) + e_scaled * (0.40 + gi * 0.8);
    } else {
        glow_sigma = (4.0 + gi * 25.0) * g_max;
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

    // Ghost shape: re-evaluate blob SDF at peak per-band energies so the
    // ghost captures the actual deformed shape (tendrils, warping, stretch).
    // CPU side enforces a minimum peak offset so ghost is always visible.
    float ghost_ring_alpha = 0.0;
    if (u_ghost_alpha > 0.001) {
        float ghost_d = blob_sdf_ex(uv, u_time,
            u_blob_peak_bass, u_blob_peak_mid, u_blob_peak_high,
            u_blob_peak_overall, u_blob_peak_energy);

        // outside_current: 1.0 when pixel is outside the current blob
        // Wide transition zone so ghost fill extends well past the edge
        float outside_current = smoothstep(-0.01, 0.02, d);
        // inside_peak: 1.0 when pixel is inside the peak shape
        // Wide fade so the ghost doesn't clip abruptly at the peak boundary
        float inside_peak = 1.0 - smoothstep(-0.02, 0.04, ghost_d);

        // Ghost fill = outside current blob AND inside peak blob shape
        float ghost_fill = outside_current * inside_peak;

        // Soft outer glow halo around the peak shape boundary
        float ghost_d_px = ghost_d * inner_height;
        float edge_glow = exp(-ghost_d_px * ghost_d_px * 0.005) * outside_current;
        edge_glow *= smoothstep(0.06, -0.02, ghost_d);

        ghost_ring_alpha = (ghost_fill * 0.7 + edge_glow * 0.4) * u_ghost_alpha;
    }

    float total_alpha = max(fill_alpha, max(edge_alpha, max(glow_alpha, max(outline_band_alpha, ghost_ring_alpha))));
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
    } else if (ghost_ring_alpha > 0.01 && ghost_ring_alpha >= glow_alpha) {
        // Ghost shape zone: use glow colour blended toward outline for depth
        final_rgb = mix(glow_rgb, outline_rgb, 0.5);
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
