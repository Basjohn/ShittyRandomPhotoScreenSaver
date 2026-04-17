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
uniform vec4 u_blob_inward_liquid_color;
uniform float u_blob_pulse;
uniform float u_blob_width;  // (legacy, no longer used in shader — card width is widget-level)
uniform float u_blob_size;   // 0.3..2.0  relative blob scale (default 1.0)
uniform float u_blob_glow_intensity;  // 0..1  glow size/strength (default 0.5)
uniform int u_blob_reactive_glow;  // 0 = static glow, 1 = energy-reactive
uniform int u_blob_inward_liquid_enabled;  // 0 = off, 1 = on
uniform float u_blob_inward_liquid_reactivity;  // 0..2 interior edge response strength
uniform float u_blob_inward_liquid_max_size;  // 0.05..0.45 max inward depth fraction
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
uniform float u_blob_stretch_inner;  // 0..1 how deep inward dents can go (default 0.0 for non-shaped Blob)
uniform float u_blob_stretch_outer;  // 0..1 how far outward protrusions extend (default 0.5)
uniform vec3 u_blob_stage_progress_override;  // (-1,-1,-1) when unused
const int BLOB_POCKET_COUNT = 6;
uniform vec4 u_blob_pockets[BLOB_POCKET_COUNT];    // angle_frac, amplitude, width, phase
uniform vec4 u_blob_pocket_mix[BLOB_POCKET_COUNT]; // bass, mid, high, transient
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
uniform float u_blob_runtime_profile[SHAPER_N]; // CPU-solved runtime contour multipliers
uniform float u_blob_energy_bass[SHAPER_N];     // per-sector bass routing weight
uniform float u_blob_energy_mid[SHAPER_N];      // per-sector mid routing weight
uniform float u_blob_energy_vocals[SHAPER_N];   // per-sector vocal routing weight
uniform float u_blob_energy_treble[SHAPER_N];   // per-sector treble routing weight
uniform float u_blob_energy_transient[SHAPER_N]; // per-sector transient routing weight

const float SHAPER_ANGLE_SMOOTH_STEP = 1.0 / float(SHAPER_N);

float sample_profile(float angle_frac, float profile[SHAPER_N]) {
    float idx_f = angle_frac * float(SHAPER_N);
    int i1 = int(floor(idx_f)) % SHAPER_N;
    int i0 = (i1 - 1 + SHAPER_N) % SHAPER_N;
    int i2 = (i1 + 1) % SHAPER_N;
    int i3 = (i1 + 2) % SHAPER_N;
    float t = fract(idx_f);
    float t2 = t * t;
    float t3 = t2 * t;
    float raw = 0.5 * (
        (2.0 * profile[i1])
        + (-profile[i0] + profile[i2]) * t
        + (2.0 * profile[i0] - 5.0 * profile[i1] + 4.0 * profile[i2] - profile[i3]) * t2
        + (-profile[i0] + 3.0 * profile[i1] - 3.0 * profile[i2] + profile[i3]) * t3
    );
    float lo = min(min(profile[i0], profile[i1]), min(profile[i2], profile[i3]));
    float hi = max(max(profile[i0], profile[i1]), max(profile[i2], profile[i3]));
    return clamp(raw, max(0.08, lo), hi);
}

float sample_linear_series(float angle_frac, float profile[SHAPER_N]) {
    float idx_f = angle_frac * float(SHAPER_N);
    int i0 = int(floor(idx_f)) % SHAPER_N;
    int i1 = (i0 + 1) % SHAPER_N;
    float t = fract(idx_f);
    return mix(profile[i0], profile[i1], t);
}

float sample_smoothed_linear_series(float angle_frac, float profile[SHAPER_N]) {
    return
        sample_linear_series(angle_frac, profile) * 0.50 +
        sample_linear_series(angle_frac - SHAPER_ANGLE_SMOOTH_STEP, profile) * 0.25 +
        sample_linear_series(angle_frac + SHAPER_ANGLE_SMOOTH_STEP, profile) * 0.25;
}

float cyclic_diff_frac(float a, float b) {
    float diff = abs(a - b);
    return min(diff, 1.0 - diff);
}

float compute_blob_pocket_component(
    float angle_frac,
    float time_seconds,
    float bass_energy,
    float mid_energy,
    float high_energy,
    float overall_energy,
    float smoothed_e)
{
    float total = 0.0;
    for (int i = 0; i < BLOB_POCKET_COUNT; ++i) {
        vec4 pocket = u_blob_pockets[i];
        vec4 mixv = u_blob_pocket_mix[i];
        float amplitude = pocket.y;
        if (amplitude <= 0.001) {
            continue;
        }
        float width = max(0.05, pocket.z);
        float diff = cyclic_diff_frac(angle_frac, pocket.x);
        float diff_norm = clamp(diff / max(width, 0.001), 0.0, 1.0);
        float lobe = 1.0 - smoothstep(0.18, 1.0, diff_norm);
        lobe *= lobe;
        if (lobe <= 0.0) {
            continue;
        }
        float drive = clamp(
            bass_energy * mixv.x +
            mid_energy * mixv.y +
            high_energy * mixv.z +
            smoothed_e * mixv.w +
            overall_energy * 0.10,
            0.0,
            1.8
        );
        float pocket_age = max(0.0, time_seconds - pocket.w);
        float attack_boost = 1.0 + 0.42 * exp(-pocket_age / 0.085);
        float ripple_phase = pocket_age * 12.0 + diff_norm * 2.0 + float(i) * 0.7;
        float ripple = 0.94 + 0.06 * sin(ripple_phase);
        float shoulder_fill = 1.0 - diff_norm * 0.26;
        total += amplitude * drive * lobe * ripple * attack_boost * shoulder_fill;
    }
    return total;
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

vec4 compute_inward_liquid_profile(
    float angle_frac,
    float time_seconds,
    float local_radius,
    float local_depth,
    float bass_energy,
    float mid_energy,
    float high_energy,
    float overall_energy,
    float smoothed_energy,
    float stage1_t,
    float stage2_t,
    float stage3_t,
    float transient_energy,
    float reactivity,
    float max_size,
    int ring_mode,
    int enabled)
{
    float local_r = max(local_radius, 0.0001);
    float local_d = max(local_depth, 0.0);
    if (enabled == 0 || ring_mode == 1) {
        return vec4(0.0, 0.0, 0.0, local_r);
    }

    float angle = angle_frac * 6.2831853;
    float bass = clamp(bass_energy, 0.0, 1.0);
    float mid = clamp(mid_energy, 0.0, 1.0);
    float high = clamp(high_energy, 0.0, 1.0);
    float overall = clamp(overall_energy, 0.0, 1.0);
    float se = clamp(smoothed_energy, 0.0, 1.0);
    float stage1 = clamp(stage1_t, 0.0, 1.0);
    float stage2 = clamp(stage2_t, 0.0, 1.0);
    float stage3 = clamp(stage3_t, 0.0, 1.0);
    float transient = clamp(transient_energy, 0.0, 1.0);
    float react = clamp(reactivity, 0.0, 2.0);
    float max_fraction = clamp(max_size, 0.05, 0.45);

    float base_drift = 0.20;
    base_drift += sin(time_seconds * 0.82 + angle * 1.8) * 0.08;
    base_drift += sin(time_seconds * 1.31 - angle * 2.7 + 0.90) * 0.06;
    base_drift = clamp(base_drift, 0.08, 0.34);

    float audio_pressure = clamp(
        se * 0.22 +
        overall * 0.25 +
        mid * 0.24 +
        bass * 0.11 +
        high * 0.08 +
        transient * 0.10,
        0.0,
        1.4
    );
    float ripple_wave = sin(time_seconds * (2.0 + audio_pressure * 2.2) + angle * 3.5);
    float contour_ripple = 0.5 + 0.5 * ripple_wave;
    float tangential_slide = (contour_ripple - 0.5) * (0.08 + 0.06 * min(react, 1.0));

    float advance_drive = clamp(
        base_drift +
        audio_pressure * (0.12 + 0.10 * react) +
        tangential_slide,
        0.06,
        0.92
    );
    float hard_cap = local_r * max_fraction;
    float retained_band_floor = max(local_r * (0.070 + max_fraction * 0.06), 0.018);
    float requested_depth = hard_cap * advance_drive;

    float body_pressure = clamp(
        se * 0.18 +
        overall * 0.20 +
        mid * 0.10 +
        stage1 * 0.10 +
        stage2 * 0.18 +
        stage3 * 0.28 +
        transient * 0.08,
        0.0,
        1.3
    );
    float local_bias = 0.5 + 0.5 * sin(time_seconds * 0.64 - angle * 2.1 + 1.2);
    float crowding = clamp(requested_depth / max(hard_cap, 0.0001), 0.0, 1.0);
    float thin_region = smoothstep(0.58, 0.28, local_r);
    float retreat_signal = clamp(
        body_pressure * (0.48 + 0.34 * local_bias) +
        crowding * 0.58 +
        thin_region * 0.24,
        0.0,
        1.4
    );
    float retreat_weight = smoothstep(0.45, 1.02, retreat_signal);
    float retreat_depth = hard_cap * retreat_weight * (0.10 + body_pressure * 0.14 + thin_region * 0.08);

    float redistribution = retreat_weight * (0.03 + 0.05 * audio_pressure) * sin(
        time_seconds * 1.45 + angle * 4.4 - 0.6
    );
    float final_depth = requested_depth - retreat_depth + redistribution * hard_cap;
    final_depth = clamp(final_depth, retained_band_floor, hard_cap);

    float front_softness = max(final_depth * 0.56, 0.010);
    float front_mask = 1.0 - smoothstep(max(final_depth - front_softness, 0.0), final_depth, local_d);
    float source_anchor = 1.0 - smoothstep(0.0, max(final_depth * 0.95, 0.018), local_d);
    float body_preserve = smoothstep(0.0, max(local_r * 0.58, 0.035), local_d);
    float retained_mix_floor = 0.24 + source_anchor * 0.08;
    float mix_amount = front_mask * (0.56 + source_anchor * 0.30 + audio_pressure * 0.18) * (1.0 - body_preserve * 0.22);
    mix_amount = max(mix_amount, front_mask * retained_mix_floor);
    mix_amount = clamp(mix_amount, 0.0, 0.96);

    return vec4(final_depth, mix_amount, retreat_depth, max(local_r - final_depth, max(local_r * (1.0 - max_fraction), retained_band_floor)));
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

    float weighted = clamp(bass * 0.60 + overall * 0.28 + mid * 0.08 + high * 0.04, 0.0, 1.0);
    float stage1_drive = max(
        weighted,
        clamp(
            overall * 0.62 +
            min(mid, overall * 0.50) * 0.16 +
            min(high, overall * 0.35) * 0.12,
            0.0,
            1.0
        )
    );
    float weighted_stage1 = clamp(stage1_drive * 0.84 + se * 0.16, 0.0, 1.0);
    float base_stage2_drive = clamp(weighted * 0.56 + bass * 0.12 + mid * 0.22 + high * 0.10, 0.0, 1.0);
    float stage2_drive = clamp(base_stage2_drive * 0.74 + se * 0.26, 0.0, 1.0);
    float chorus_drive = clamp(max(stage2_drive, bass * 0.28 + overall * 0.24 + mid * 0.29 + high * 0.19), 0.0, 1.0);
    chorus_drive = clamp(max(chorus_drive, se * 0.28 + overall * 0.34 + mid * 0.26 + high * 0.12), 0.0, 1.0);

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
    float stage1_t = smoothstep(0.035, 0.59, weighted_stage1);
    float stage2_t = smoothstep(0.13, 0.54, stage2_drive);
    float stage3_t = smoothstep(0.18, 0.60, chorus_drive);
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

    float stage_unit = base_size * 0.11 + 0.012;
    float stage1_amt = stage_unit * 0.58;
    float stage2_amt = stage_unit * 1.22;
    float stage3_amt = stage_unit * 2.10;

    float offset = stage1_t * stage1_amt;
    offset += stage2_t * max(0.0, stage2_amt - stage1_amt);
    offset += stage3_t * max(0.0, stage3_amt - stage2_amt);

    return offset * gain * scale;
}

float compute_unshaped_organic_base_mult(float angle_frac, float time_seconds, float smoothed_e, float overall_e) {
    float angle = angle_frac * 6.2831853;
    float slow_t = time_seconds * 0.12;
    float drift = 0.60 + clamp(smoothed_e, 0.0, 1.0) * 0.28 + clamp(overall_e, 0.0, 1.0) * 0.12;

    float shape = 1.0;
    shape += cos(angle * 1.0 + slow_t * 0.41 + 0.70) * 0.054;
    shape += cos(angle * 2.0 - slow_t * 0.29 + 1.85) * 0.031;
    shape += cos(angle * 3.0 + slow_t * 0.23 + 3.05) * 0.017;
    shape += cos(angle * 1.0 - slow_t * 0.17 + 2.45) * 0.016 * drift;

    return clamp(shape, 0.88, 1.16);
}

vec2 compute_unshaped_motion_offsets(
    float angle_frac,
    float time_seconds,
    float bass_energy,
    float mid_energy,
    float high_energy,
    float overall_energy,
    float smoothed_energy,
    float reactive_deformation,
    float constant_wobble,
    float reactive_wobble,
    float stretch_tendency,
    float stretch_inner,
    float stretch_outer,
    float pocket_component)
{
    float angle = angle_frac * 6.2831853;
    float e_bass = clamp(bass_energy, 0.0, 1.0);
    float e_mid = clamp(mid_energy, 0.0, 1.0);
    float e_high = clamp(high_energy, 0.0, 1.0);
    float e_overall = clamp(overall_energy, 0.0, 1.0);
    float se = clamp(smoothed_energy, 0.0, 1.0);
    float rd = clamp(reactive_deformation, 0.0, 3.0);
    float cw = clamp(constant_wobble, 0.0, 2.0);
    float rw = clamp(reactive_wobble, 0.0, 3.0);
    float st = clamp(stretch_tendency, 0.0, 1.0);
    float s_inner = clamp(stretch_inner, 0.0, 1.0);
    float s_outer = clamp(stretch_outer, 0.0, 1.0);

    float base_mult = compute_unshaped_organic_base_mult(angle_frac, time_seconds, se, e_overall);
    float base_bias = clamp((base_mult - 1.0) / 0.16, -1.0, 1.0);

    float slow_sway = 0.0;
    slow_sway += sin(angle * 1.0 + time_seconds * 0.20 + 0.25) * 0.020;
    slow_sway += sin(angle * 2.0 - time_seconds * 0.34 + 1.05) * 0.011;
    slow_sway += sin(angle * 3.0 + time_seconds * 0.27 + 2.10) * 0.005;
    slow_sway *= 1.0 - abs(base_bias) * 0.18;

    float reactive_mid = clamp(e_mid * 0.92 + e_overall * 0.08, 0.0, 1.0);
    float reactive_high = clamp(e_high * 0.82 + e_mid * 0.12, 0.0, 1.0);
    float vocal = clamp(e_mid * 1.02 + e_high * 0.18, 0.0, 1.0);

    float reactive_sway = 0.0;
    reactive_sway += sin(angle * 1.0 + time_seconds * 0.48 + 0.30) * 0.040 * vocal;
    reactive_sway += sin(angle * 2.0 - time_seconds * 0.56 + 1.80) * 0.026 * reactive_mid;
    reactive_sway += sin(angle * 3.0 + time_seconds * 0.44 + 2.55) * 0.010 * reactive_high;
    reactive_sway += base_bias * vocal * 0.015;

    float wobble_component = slow_sway * cw + reactive_sway * rw;

    float pocket_pressure = clamp(pocket_component, 0.0, 1.8);
    float pocket_soft = 1.0 - exp(-pocket_pressure * 0.92);
    float pocket_shoulder = pocket_soft * (1.0 - pocket_soft * 0.24);

    float stretch_component = 0.0;
    if (st > 0.01) {
        float vocal_impact = clamp(e_mid * 1.02 + e_high * 0.20 + se * 0.10, 0.0, 1.0);
        float bass_support = clamp(e_bass * 0.18 + e_overall * 0.14, 0.0, 1.0);
        float impact = clamp(vocal_impact * 0.84 + bass_support * 0.24, 0.0, 1.0);
        float impact2 = impact * impact;
        float impact3 = impact2 * impact;
        float stretch = 0.0;
        stretch += sin(angle * 1.0 + time_seconds * 0.16 + 0.95) * impact2 * 0.082;
        stretch += sin(angle * 2.0 - time_seconds * 0.31 + 2.20) * impact3 * 0.058;
        stretch += base_bias * impact2 * 0.046;
        stretch += base_bias * max(0.0, vocal_impact - 0.18) * 0.024;
        stretch += pocket_shoulder * 0.138;
        stretch += pocket_soft * max(0.0, 0.35 - abs(base_bias)) * 0.022;
        stretch_component = stretch * st;
    }

    wobble_component += pocket_shoulder * 0.010;
    wobble_component += pocket_soft * base_bias * 0.008;

    float rd_scale = rd <= 1.0 ? rd : 1.0 + (rd - 1.0) * (rd - 1.0) * (rd - 1.0) * 4.0 + (rd - 1.0) * 2.0;
    wobble_component *= rd_scale;
    stretch_component *= rd_scale;

    if (stretch_component < 0.0) {
        stretch_component *= 0.04 + s_inner * 0.48;
    } else {
        stretch_component *= 0.10 + s_outer * 0.90;
    }

    return vec2(stretch_component, wobble_component);
}

// 2D SDF organic blob with audio-reactive deformation.
// Accepts per-band energies + smoothed so it can be called with current OR
// peak energies (for ghost shape reconstruction).
float blob_sdf_ex(vec2 p, float time,
                  float e_bass, float e_mid, float e_high, float e_overall,
                  float smoothed_e) {
    float r = 0.285 * clamp(u_blob_size, 0.1, 2.5);
    float pulse_amt = clamp(u_blob_pulse, 0.0, 2.0);
    r += e_bass * e_bass * 0.016 * pulse_amt;
    r += e_bass * 0.018 * pulse_amt;
    float se = clamp(smoothed_e, 0.0, 1.0);
    float breath = max(e_bass, se * 0.82);
    r += max(0.02, breath) * 0.007 * pulse_amt;
    r -= (1.0 - se) * 0.010 * pulse_amt;

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

    // Both Blob types now upload one solved runtime contour profile. Blob
    // Shaper authors it from user contours; unshaped Blob authors it from the
    // procedural fluid solver on the CPU.
    float angle_frac = fract(angle / 6.2831853 + 0.25);
    float runtime_mult =
        sample_profile(angle_frac, u_blob_runtime_profile) * 0.50 +
        sample_profile(angle_frac - SHAPER_ANGLE_SMOOTH_STEP, u_blob_runtime_profile) * 0.25 +
        sample_profile(angle_frac + SHAPER_ANGLE_SMOOTH_STEP, u_blob_runtime_profile) * 0.25;
    float support_floor = mix(0.52, 0.60, clamp(stage_progress.z * 0.65 + stage_progress.y * 0.20, 0.0, 1.0));
    float final_radius = max(staged_r * runtime_mult, staged_r * support_floor);

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

    vec3 stage_progress_main = compute_stage_progress_values(
        u_bass_energy,
        u_mid_energy,
        u_high_energy,
        u_overall_energy
    );
    if (u_blob_stage_progress_override.x >= 0.0 &&
        u_blob_stage_progress_override.y >= 0.0 &&
        u_blob_stage_progress_override.z >= 0.0) {
        stage_progress_main = clamp(u_blob_stage_progress_override, vec3(0.0), vec3(1.0));
    }

    float d_signed = blob_sdf(uv, u_time);
    float d_base = d_signed;
    float d_glow = d_signed;
    float ring_thickness = 0.0;

    // Ring topology — carve out interior to create a hollow ring.
    // Works independently of shaper; ring_mode is set by topology combo.
    if (u_blob_ring_mode == 1) {
        // Ring thickness is a fraction of the blob's visual radius (~0.44 * blob_size)
        float ring_r = 0.44 * clamp(u_blob_size, 0.1, 2.5);
        ring_thickness = clamp(u_blob_ring_thickness, 0.05, 1.0) * ring_r * 0.5;
        d_base = abs(d_signed) - ring_thickness;
        d_glow = d_signed - ring_thickness;
    }

    float d_fill = d_base;
    float d_shell = d_fill;
    float radial_dist = length(uv);
    float local_radius = max(radial_dist - d_signed, 0.0001);

    // Multi-layer colouring from the SDF distance
    // Inner core: bright, slightly shifted hue
    // Edge: blob_color
    // Glow: soft falloff outside the blob

    // Inner fill
    float fill_alpha = 1.0 - smoothstep(-0.02, 0.0, d_fill);

    // Edge highlight (respects edge colour alpha channel)
    float edge_alpha = 1.0 - smoothstep(0.0, 0.008, abs(d_shell));
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
    float d_px = d_glow * inner_height;
    float glow_alpha = 0.0;
    if (d_glow > 0.0 && glow_sigma > 0.0) {
        glow_alpha = exp(-(d_px * d_px) / (2.0 * glow_sigma * glow_sigma));
        glow_alpha *= glow_strength;
    }

    // Outline band alpha: ensures the outline zone has solid coverage
    // so there's no transparent gap between the fill edge and glow
    float outline_band_alpha = 0.0;
    if (d_shell >= 0.0 && d_shell < 0.015 && outline_a > 0.01) {
        outline_band_alpha = (1.0 - smoothstep(0.0, 0.015, d_shell)) * outline_a;
    }

    // Ghost shape: re-evaluate blob SDF at peak per-band energies so the
    // ghost captures the actual deformed shape (tendrils, warping, stretch).
    // CPU side enforces a minimum peak offset so ghost is always visible.
    float ghost_ring_alpha = 0.0;
    if (u_ghost_alpha > 0.001) {
        float ghost_signed_d = blob_sdf_ex(uv, u_time,
            u_blob_peak_bass, u_blob_peak_mid, u_blob_peak_high,
            u_blob_peak_overall, u_blob_peak_energy);
        float ghost_d = ghost_signed_d;
        if (u_blob_ring_mode == 1) {
            ghost_d = abs(ghost_signed_d) - ring_thickness;
        }

        // outside_current: 1.0 when pixel is outside the current blob
        // Wide transition zone so ghost fill extends well past the edge
        float outside_current = smoothstep(-0.01, 0.02, d_fill);
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
    vec3 inward_liquid_rgb = u_blob_inward_liquid_color.rgb;
    bool rainbow_active = (u_rainbow_hue_offset > 0.001);
    if (rainbow_active) {
        blob_rgb = apply_rainbow_shift(blob_rgb);
        glow_rgb = apply_rainbow_shift(glow_rgb);
        outline_rgb = apply_rainbow_shift(outline_rgb);
        inward_liquid_rgb = apply_rainbow_shift(inward_liquid_rgb);
    }
    float angle_frac_main = fract(atan(uv.y, uv.x) / 6.2831853 + 0.25);
    float local_depth_main = max(-d_fill, 0.0);
    float normalized_depth = clamp(local_depth_main / max(local_radius, 0.0001), 0.0, 1.0);
    float surface_band = smoothstep(0.28, 0.05, normalized_depth) * smoothstep(-0.16, -0.004, d_fill);
    float streak_center_a = fract(0.83 + sin(u_time * 0.13) * 0.05);
    float streak_center_b = fract(streak_center_a + 0.08 + sin(u_time * 0.09 + 0.8) * 0.03);
    float streak_diff_a = cyclic_diff_frac(angle_frac_main, streak_center_a);
    float streak_diff_b = cyclic_diff_frac(angle_frac_main, streak_center_b);
    float streak_arc_a = exp(-pow(streak_diff_a / 0.11, 2.0));
    float streak_arc_b = exp(-pow(streak_diff_b / 0.07, 2.0));
    float streak_breakup =
        0.72 + 0.28 * sin(u_time * 1.05 + angle_frac_main * 23.0 + normalized_depth * 6.0);
    float slime_highlight = clamp(
        (streak_arc_a * 0.88 + streak_arc_b * 0.44) * streak_breakup * surface_band,
        0.0,
        1.0
    );

    float inward_liquid_mix = 0.0;
    if (u_blob_inward_liquid_enabled == 1 && u_blob_ring_mode == 0 && d_fill < 0.0) {
        vec4 inward_profile = compute_inward_liquid_profile(
            angle_frac_main,
            u_time,
            local_radius,
            local_depth_main,
            u_bass_energy,
            u_mid_energy,
            u_high_energy,
            u_overall_energy,
            u_blob_smoothed_energy,
            stage_progress_main.x,
            stage_progress_main.y,
            stage_progress_main.z,
            u_high_energy,
            u_blob_inward_liquid_reactivity,
            u_blob_inward_liquid_max_size,
            u_blob_ring_mode,
            u_blob_inward_liquid_enabled
        );
        float front_band = 1.0 - smoothstep(
            max(inward_profile.x * 0.22, 0.002),
            max(inward_profile.x * 0.96, 0.010),
            local_depth_main
        );
        float retained_visibility = smoothstep(0.0, max(inward_profile.x * 0.85, 0.012), local_depth_main);
        inward_liquid_mix = inward_profile.y * max(front_band, retained_visibility * 0.38) * clamp(u_blob_inward_liquid_color.a, 0.0, 1.0);
    }

    // Outline band colour (the dark/grey area between fill edge and glow)

    vec3 final_rgb;
    if (d_fill < -0.02) {
        // Deep inside: mostly stable fill colour with a soft ooze highlight.
        float depth = clamp(-d_fill / 0.15, 0.0, 1.0);
        float highlight_mask = slime_highlight * depth * (0.22 + u_blob_smoothed_energy * 0.10);
        final_rgb = mix(blob_rgb, vec3(1.0), highlight_mask);
    } else if (d_fill < 0.0) {
        // Near edge: transition from fill to edge highlight colour
        float t = 1.0 - clamp(-d_fill / 0.02, 0.0, 1.0);
        final_rgb = mix(blob_rgb, edge_rgb, t);
    } else if (ghost_ring_alpha > 0.01 && ghost_ring_alpha >= glow_alpha) {
        // Ghost shape zone: use glow colour blended toward outline for depth
        final_rgb = mix(glow_rgb, outline_rgb, 0.5);
    } else if (d_shell < 0.015 && outline_a > 0.01) {
        // Outline band: thin region just outside the fill, before glow takes over
        float band_t = clamp(d_shell / 0.015, 0.0, 1.0);
        final_rgb = mix(edge_rgb, outline_rgb, band_t * outline_a);
    } else {
        // Outside: glow colour
        final_rgb = glow_rgb;
    }

    if (inward_liquid_mix > 0.001 && d_fill < 0.0) {
        vec3 inward_liquid_tint = mix(inward_liquid_rgb, vec3(1.0), 0.12);
        final_rgb *= 1.0 - inward_liquid_mix * 0.28;
        final_rgb = mix(final_rgb, inward_liquid_tint, clamp(inward_liquid_mix * 2.10, 0.0, 0.98));
    }

    fragColor = vec4(final_rgb, total_alpha * u_fade);
}
