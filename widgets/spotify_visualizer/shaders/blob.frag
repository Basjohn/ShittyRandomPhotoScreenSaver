// Shared Blob shader body. Concrete programs are blob_mighty.frag and
// blob_shaped.frag, which define BLOB_VARIANT_SHAPED before including this
// source.
#ifndef BLOB_VARIANT_SHAPED
#define BLOB_VARIANT_SHAPED 0
#endif
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
uniform float u_transient_bass;
uniform float u_transient_mid;
uniform float u_transient_high;

// Blob configuration
uniform vec4 u_blob_color;
uniform vec4 u_blob_glow_color;
uniform vec4 u_blob_edge_color;
uniform vec4 u_blob_outline_color;
uniform vec4 u_blob_inward_liquid_color;
uniform float u_blob_pulse;
uniform float u_blob_size;   // 0.3..2.0  relative blob scale (default 1.0)
uniform float u_blob_glow_intensity;  // 0..1  glow size/strength (default 0.5)
uniform int u_blob_reactive_glow;  // 0 = static glow, 1 = energy-reactive
uniform int u_blob_inward_liquid_enabled;  // 0 = off, 1 = on
uniform float u_blob_inward_liquid_reactivity;  // 0..2 interior edge response strength
uniform float u_blob_inward_liquid_max_size;  // 0.05..0.45 max inward depth fraction
uniform float u_blob_smoothed_energy;  // CPU-side smoothed energy (reduces flicker)
uniform float u_blob_glow_energy;  // CPU-side smoothed glow drive (bass or vocal depending on mode)
uniform float u_blob_stage_gain;  // 0..2 multiplier for staged core sizing
uniform float u_blob_core_scale;  // 0.25..2.5 post-stage scaling of the core radius
uniform float u_blob_stage_bias;  // -0.60..0.60 shifts stage thresholds up/down before smoothing
uniform vec3 u_blob_stage_progress_override;  // (-1,-1,-1) when unused
uniform float u_rainbow_hue_offset;    // 0..1 hue rotation (0 = disabled)
uniform float u_ghost_alpha;           // 0 = no ghost, >0 = ghost outline intensity
uniform float u_blob_peak_energy;      // CPU-tracked peak energy for ghost outline
uniform float u_blob_peak_bass;        // per-band peak for SDF ghost shape
uniform float u_blob_peak_mid;
uniform float u_blob_peak_high;
uniform float u_blob_peak_overall;
uniform float u_blob_glow_reactivity;  // 0..2 how strongly glow responds to energy (default 1.0)
uniform float u_blob_glow_max_size;    // 0.1..3.0 maximum glow spread multiplier (default 1.0)

// Shaped Blob topology. Authored contour solving is CPU-owned; the shader
// receives only the final runtime profile.
uniform int u_blob_ring_mode;            // 0 = circle (filled), 1 = ring (hollow)
uniform float u_blob_ring_thickness;     // 0.05..1.0 ring wall thickness as fraction of radius

const int SHAPER_N = 128;
uniform float u_blob_runtime_profile[SHAPER_N]; // CPU-solved runtime contour multipliers

// True 2D goo limbs. The CPU owns their musical birth/release envelopes and
// bounded anchor families; the GPU owns curved, tapered distance geometry.
// This is deliberately Blob-local and is absent from every other visualizer.
const int BLOB_TENDRIL_N = 12;
uniform int u_blob_tendril_count;
// angle fraction, reach, root radius, tip radius
uniform vec4 u_blob_tendril_geometry[BLOB_TENDRIL_N];
// bend, hook, activity, pale-tip drive (negative w marks an inward groove)
uniform vec4 u_blob_tendril_motion[BLOB_TENDRIL_N];
uniform float u_blob_vocal_wobble_strength;

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

float sample_profile_gradient(float angle_frac, float profile[SHAPER_N]) {
    float prev = sample_linear_series(angle_frac - SHAPER_ANGLE_SMOOTH_STEP, profile);
    float next = sample_linear_series(angle_frac + SHAPER_ANGLE_SMOOTH_STEP, profile);
    return (next - prev) * 0.5;
}

float smooth_min_blob(float a, float b, float softness) {
    float k = max(softness, 0.0001);
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

float smooth_max_blob(float a, float b, float softness) {
    return -smooth_min_blob(-a, -b, softness);
}

float sd_tapered_segment(vec2 p, vec2 a, vec2 b, float radius_a, float radius_b) {
    vec2 pa = p - a;
    vec2 ba = b - a;
    float denom = max(dot(ba, ba), 0.000001);
    float h = clamp(dot(pa, ba) / denom, 0.0, 1.0);
    return length(pa - ba * h) - mix(radius_a, radius_b, h);
}

float resolved_profile_radius(
    float angle_frac,
    float calm_radius,
    float staged_radius,
    vec3 stage_progress)
{
    float runtime_mult = sample_profile(fract(angle_frac), u_blob_runtime_profile);
    float contour_radius = calm_radius * runtime_mult + max(staged_radius - calm_radius, 0.0) * 0.18;
    if (BLOB_VARIANT_SHAPED == 0) {
        return contour_radius;
    }
    float shaped_support_floor = mix(
        0.52,
        0.60,
        clamp(stage_progress.z * 0.65 + stage_progress.y * 0.20, 0.0, 1.0)
    );
    return max(staged_radius * runtime_mult, staged_radius * shaped_support_floor);
}

float blob_tendril_sdf(
    vec2 p,
    float calm_radius,
    float staged_radius,
    vec3 stage_progress)
{
    float result = 1000.0;
    for (int idx = 0; idx < BLOB_TENDRIL_N; ++idx) {
        if (idx >= u_blob_tendril_count) {
            break;
        }
        vec4 geometry = u_blob_tendril_geometry[idx];
        vec4 motion = u_blob_tendril_motion[idx];
        float reach = max(geometry.y, 0.0);
        float activity = clamp(motion.z, 0.0, 1.25);
        if (reach <= 0.0015 || activity <= 0.015 || motion.w < 0.0) {
            continue;
        }

        float angle = (fract(geometry.x) - 0.25) * 6.2831853;
        vec2 direction = vec2(cos(angle), sin(angle));
        vec2 tangent = vec2(-direction.y, direction.x);
        float anchor_radius = resolved_profile_radius(
            geometry.x,
            calm_radius,
            staged_radius,
            stage_progress
        );
        float root_radius = clamp(geometry.z, 0.008, 0.075);
        float tip_radius = clamp(geometry.w, 0.006, root_radius);

        // The root begins safely inside the living radial body. Two tapered
        // segments then bend independently and terminate in a true round cap;
        // smooth union removes the old radial-fan shoulder completely.
        vec2 p0 = direction * max(calm_radius * 0.58, anchor_radius - root_radius * 0.72);
        vec2 p1 = direction * (anchor_radius + reach * 0.43)
            + tangent * motion.x * reach * 0.62;
        vec2 p2 = direction * (anchor_radius + reach)
            + tangent * (motion.x * 0.34 + motion.y * 0.78) * reach;
        float mid_radius = mix(root_radius, tip_radius, 0.52) * (0.96 + activity * 0.05);
        float first = sd_tapered_segment(p, p0, p1, root_radius, mid_radius);
        float second = sd_tapered_segment(p, p1, p2, mid_radius, tip_radius);
        float limb = smooth_min_blob(first, second, min(0.014, mid_radius * 0.48));
        result = smooth_min_blob(result, limb, min(0.016, root_radius * 0.52));
    }
    return result;
}

float blob_groove_sdf(
    vec2 p,
    float calm_radius,
    float staged_radius,
    vec3 stage_progress)
{
    float result = 1000.0;
    for (int idx = 0; idx < BLOB_TENDRIL_N; ++idx) {
        if (idx >= u_blob_tendril_count) {
            break;
        }
        vec4 geometry = u_blob_tendril_geometry[idx];
        vec4 motion = u_blob_tendril_motion[idx];
        float reach = max(geometry.y, 0.0);
        float activity = clamp(motion.z, 0.0, 1.25);
        if (reach <= 0.0015 || activity <= 0.015 || motion.w >= 0.0) {
            continue;
        }

        float angle = (fract(geometry.x) - 0.25) * 6.2831853;
        vec2 direction = vec2(cos(angle), sin(angle));
        vec2 tangent = vec2(-direction.y, direction.x);
        float anchor_radius = resolved_profile_radius(
            geometry.x,
            calm_radius,
            staged_radius,
            stage_progress
        );
        float root_radius = clamp(geometry.z * 1.10, 0.010, 0.078);
        float inner_radius = clamp(max(geometry.w, root_radius * 0.62), 0.008, root_radius);
        float core_guard = calm_radius * 0.46;
        if (BLOB_VARIANT_SHAPED == 1 && u_blob_ring_mode == 1) {
            core_guard = calm_radius * 0.06;
        }
        float inward_end = max(core_guard, anchor_radius - reach * 0.92);
        vec2 p0 = direction * (anchor_radius + root_radius * 1.20);
        vec2 p1 = direction * (anchor_radius - reach * 0.38)
            + tangent * motion.x * reach * 0.48;
        vec2 p2 = direction * inward_end
            + tangent * (motion.x * 0.28 + motion.y * 0.68) * reach;
        float mid_radius = mix(root_radius, inner_radius, 0.48);
        float first = sd_tapered_segment(p, p0, p1, root_radius, mid_radius);
        float second = sd_tapered_segment(p, p1, p2, mid_radius, inner_radius);
        float channel = smooth_min_blob(first, second, min(0.014, mid_radius * 0.46));
        result = smooth_min_blob(result, channel, min(0.016, root_radius * 0.50));
    }
    return result;
}

void blob_detail_sdfs(
    vec2 p,
    float calm_radius,
    float staged_radius,
    vec3 stage_progress,
    out float limb_result,
    out float groove_result)
{
    limb_result = 1000.0;
    groove_result = 1000.0;
    for (int idx = 0; idx < BLOB_TENDRIL_N; ++idx) {
        if (idx >= u_blob_tendril_count) {
            break;
        }
        vec4 geometry = u_blob_tendril_geometry[idx];
        vec4 motion = u_blob_tendril_motion[idx];
        float reach = max(geometry.y, 0.0);
        float activity = clamp(motion.z, 0.0, 1.25);
        if (reach <= 0.0015 || activity <= 0.015) {
            continue;
        }
        float angle = (fract(geometry.x) - 0.25) * 6.2831853;
        vec2 direction = vec2(cos(angle), sin(angle));
        vec2 tangent = vec2(-direction.y, direction.x);
        float anchor_radius = resolved_profile_radius(
            geometry.x,
            calm_radius,
            staged_radius,
            stage_progress
        );

        if (motion.w >= 0.0) {
            float root_radius = clamp(geometry.z, 0.008, 0.075);
            float tip_radius = clamp(geometry.w, 0.006, root_radius);
            vec2 p0 = direction * max(calm_radius * 0.58, anchor_radius - root_radius * 0.72);
            vec2 p1 = direction * (anchor_radius + reach * 0.43)
                + tangent * motion.x * reach * 0.62;
            vec2 p2 = direction * (anchor_radius + reach)
                + tangent * (motion.x * 0.34 + motion.y * 0.78) * reach;
            float mid_radius = mix(root_radius, tip_radius, 0.52) * (0.96 + activity * 0.05);
            float first = sd_tapered_segment(p, p0, p1, root_radius, mid_radius);
            float second = sd_tapered_segment(p, p1, p2, mid_radius, tip_radius);
            float limb = smooth_min_blob(first, second, min(0.014, mid_radius * 0.48));
            limb_result = smooth_min_blob(
                limb_result,
                limb,
                min(0.016, root_radius * 0.52)
            );
        } else {
            float root_radius = clamp(geometry.z * 1.10, 0.010, 0.078);
            float inner_radius = clamp(max(geometry.w, root_radius * 0.62), 0.008, root_radius);
            float core_guard = calm_radius * 0.46;
            if (BLOB_VARIANT_SHAPED == 1 && u_blob_ring_mode == 1) {
                core_guard = calm_radius * 0.06;
            }
            float inward_end = max(core_guard, anchor_radius - reach * 0.92);
            vec2 p0 = direction * (anchor_radius + root_radius * 1.20);
            vec2 p1 = direction * (anchor_radius - reach * 0.38)
                + tangent * motion.x * reach * 0.48;
            vec2 p2 = direction * inward_end
                + tangent * (motion.x * 0.28 + motion.y * 0.68) * reach;
            float mid_radius = mix(root_radius, inner_radius, 0.48);
            float first = sd_tapered_segment(p, p0, p1, root_radius, mid_radius);
            float second = sd_tapered_segment(p, p1, p2, mid_radius, inner_radius);
            float channel = smooth_min_blob(first, second, min(0.014, mid_radius * 0.46));
            groove_result = smooth_min_blob(
                groove_result,
                channel,
                min(0.016, root_radius * 0.50)
            );
        }
    }
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
    float edge_distance,
    float blob_clearance,
    float perimeter_pos,
    float time_seconds,
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
    float edge_d = max(edge_distance, 0.0);
    float clearance = max(blob_clearance, 0.0);
    if (enabled == 0) {
        return vec4(0.0, 0.0, 0.0, clearance);
    }

    float angle = perimeter_pos * 6.2831853;
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

    float hard_cap = 0.014 + max_fraction * 0.22;
    float retained_front_floor = max(0.010, hard_cap * (0.22 + max_fraction * 0.08));

    float base_drift = 0.18;
    base_drift += sin(time_seconds * 0.74 + angle * 1.7) * 0.05;
    base_drift += sin(time_seconds * 1.19 - angle * 2.4 + 0.90) * 0.04;
    base_drift = clamp(base_drift, 0.07, 0.36);

    float audio_pressure = clamp(
        se * 0.24 +
        overall * 0.22 +
        mid * 0.20 +
        bass * 0.10 +
        high * 0.08 +
        transient * 0.12,
        0.0,
        1.4
    );
    float pressure_balance = 0.5 + 0.5 * sin(time_seconds * (1.8 + audio_pressure * 1.8) + angle * 3.1);
    float tangential_slide = (pressure_balance - 0.5) * (0.10 + 0.08 * min(react, 1.0));

    float advance_drive = clamp(
        base_drift +
        audio_pressure * (0.18 + 0.14 * react) +
        tangential_slide,
        0.06,
        0.92
    );
    float requested_depth = retained_front_floor + hard_cap * advance_drive;

    float body_pressure = clamp(
        se * 0.12 +
        overall * 0.10 +
        mid * 0.08 +
        stage1 * 0.12 +
        stage2 * 0.18 +
        stage3 * 0.26 +
        transient * 0.12,
        0.0,
        1.3
    );
    float local_bias = 0.5 + 0.5 * sin(time_seconds * 0.58 - angle * 1.9 + 1.2);
    float no_contact_gap = 0.010 + max_fraction * 0.020 + min(react, 1.0) * 0.006 + body_pressure * 0.010;
    float crowding = 1.0 - smoothstep(
        no_contact_gap,
        no_contact_gap + requested_depth * 1.35 + 0.015,
        clearance
    );
    float retreat_signal = clamp(
        body_pressure * (0.30 + 0.28 * local_bias) +
        crowding * (0.82 + 0.14 * react),
        0.0,
        1.4
    );
    float retreat_weight = smoothstep(0.16, 0.96, retreat_signal);
    float retreat_depth = requested_depth * retreat_weight * (0.28 + body_pressure * 0.26);

    float redistribution = retreat_weight * (0.03 + 0.05 * audio_pressure) * sin(
        time_seconds * 1.36 + angle * 4.2 - 0.6
    );
    float final_depth = requested_depth - retreat_depth + redistribution * hard_cap;
    final_depth = clamp(final_depth, retained_front_floor, hard_cap);

    float front_mask = 1.0 - smoothstep(
        max(final_depth * 0.12, retained_front_floor * 0.50),
        max(final_depth, retained_front_floor + 0.003),
        edge_d
    );
    float source_anchor = 1.0 - smoothstep(
        0.0,
        max(final_depth * 0.55, retained_front_floor + 0.003),
        edge_d
    );
    float gap_guard = smoothstep(
        no_contact_gap,
        no_contact_gap + max(final_depth * 0.30, 0.006),
        clearance
    );
    float retained_mix_floor = 0.14 + source_anchor * 0.04;
    float mix_amount = front_mask * gap_guard * (0.28 + source_anchor * 0.24 + audio_pressure * 0.12);
    mix_amount = max(mix_amount, front_mask * gap_guard * retained_mix_floor);
    mix_amount = clamp(mix_amount, 0.0, 0.96);

    return vec4(final_depth, mix_amount, retreat_depth, no_contact_gap);
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

// 2D SDF organic blob with audio-reactive deformation.
// Accepts per-band energies + smoothed so it can be called with current OR
// peak energies (for ghost shape reconstruction).
float blob_sdf_ex(vec2 p, float time,
                  float e_bass, float e_mid, float e_high, float e_overall,
                  float smoothed_e) {
    float r = 0.31 * clamp(u_blob_size, 0.1, 2.5);
    float pulse_amt = clamp(u_blob_pulse, 0.0, 2.0);
    // Whole-body pulse is deliberately secondary to contour motion.  The old
    // coefficients could move the radius by ~90 px while tendrils moved only
    // a few pixels, making every control look like a size slider.
    r += e_bass * e_bass * 0.008 * pulse_amt;
    r += e_bass * 0.009 * pulse_amt;
    float se = clamp(smoothed_e, 0.0, 1.0);
    float breath = max(e_bass, se * 0.82);
    r += max(0.02, breath) * 0.004 * pulse_amt;
    r -= (1.0 - se) * 0.004 * pulse_amt;

    float calm_r = r;
    vec3 stage_progress = vec3(0.0);
    r += compute_stage_offset(
        clamp(u_blob_size, 0.1, 2.5),
        e_bass, e_mid, e_high, e_overall,
        u_blob_stage_gain,
        u_blob_core_scale,
        stage_progress
    ) * pulse_amt;

    float staged_r = r;
    if (BLOB_VARIANT_SHAPED == 0) {
        // Unshaped Blob should read as contour pressure first and scalar
        // breathing second. Keep some staged support, but stop letting the
        // stage ladder dominate the final silhouette.
        staged_r = mix(calm_r, staged_r, 0.46);
    }

    float angle = atan(p.y, p.x);
    float dist = length(p);

    // Both Blob types now upload one solved runtime contour profile. Blob
    // Shaper authors it from user contours; unshaped Blob authors it from the
    // procedural fluid solver on the CPU.
    float angle_frac = fract(angle / 6.2831853 + 0.25);
    // The CPU profile remains the living body and vocal contour. Curved GPU
    // limbs are then smooth-unioned in true 2D, allowing bends, hooks, narrow
    // necks, and deep gaps that no one-radius-per-angle profile can express.
    float final_radius = resolved_profile_radius(
        angle_frac,
        calm_r,
        staged_r,
        stage_progress
    );
    // Per-paint vocal contour wobble stays analytically smooth and visibly
    // independent from glow, scalar pulse, and the slower CPU morphology
    // cadence. Bounded phase modulation flexes fixed angles instead of
    // rotating one ripple around the body.
    float vocal_drive = clamp(e_mid * 0.84 + e_high * 0.30, 0.0, 1.25);
    float vocal_gate = smoothstep(0.06, 0.78, vocal_drive);
    float vocal_strength = clamp(u_blob_vocal_wobble_strength, 0.0, 1.25);
    float vocal_ripple =
        sin(angle * 7.0 + sin(time * 2.13 + 0.60) * 1.18) * 0.58 +
        sin(angle * 11.0 + sin(time * 2.87 + 2.40) * 0.92) * 0.28 +
        sin(angle * 5.0 + sin(time * 1.61 + 4.10) * 1.34) * 0.14;
    float vocal_wobble = vocal_ripple
        * vocal_gate
        * (0.003 + vocal_gate * 0.009)
        * vocal_strength;
    final_radius += vocal_wobble;
    float body_sdf = dist - final_radius;
    float tendril_sdf;
    float groove_sdf;
    blob_detail_sdfs(
        p,
        calm_r,
        staged_r,
        stage_progress,
        tendril_sdf,
        groove_sdf
    );
    float goo_sdf = smooth_min_blob(body_sdf, tendril_sdf, 0.012);
    return smooth_max_blob(goo_sdf, -groove_sdf, 0.010);
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

    // Shaped topology — carve out interior to create a hollow ring.
    // Mighty never uploads ring authority, so its concrete program remains
    // a filled organic body.
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
    float left_edge_dist = (fc.x - margin_x) / inner_height;
    float right_edge_dist = (width - margin_x - fc.x) / inner_height;
    float top_edge_dist = (fc.y - margin_y) / inner_height;
    float bottom_edge_dist = (height - margin_y - fc.y) / inner_height;
    float card_edge_distance = top_edge_dist;
    float perimeter_phase = 0.25 * clamp((fc.x - margin_x) / max(inner_width, 1.0), 0.0, 1.0);
    if (right_edge_dist < card_edge_distance) {
        card_edge_distance = right_edge_dist;
        perimeter_phase = 0.25 + 0.25 * clamp((fc.y - margin_y) / max(inner_height, 1.0), 0.0, 1.0);
    }
    if (bottom_edge_dist < card_edge_distance) {
        card_edge_distance = bottom_edge_dist;
        perimeter_phase = 0.50 + 0.25 * clamp((width - margin_x - fc.x) / max(inner_width, 1.0), 0.0, 1.0);
    }
    if (left_edge_dist < card_edge_distance) {
        card_edge_distance = left_edge_dist;
        perimeter_phase = 0.75 + 0.25 * clamp((height - margin_y - fc.y) / max(inner_height, 1.0), 0.0, 1.0);
    }
    float angle_frac_main = fract(atan(uv.y, uv.x) / 6.2831853 + 0.25);
    float profile_gradient = sample_profile_gradient(angle_frac_main, u_blob_runtime_profile);
    float profile_gradient_abs = abs(profile_gradient);
    float local_depth_main = max(-d_fill, 0.0);
    float normalized_depth = clamp(local_depth_main / max(local_radius, 0.0001), 0.0, 1.0);
    float surface_band = smoothstep(0.30, 0.04, normalized_depth) * smoothstep(-0.16, -0.003, d_fill);
    // Body paint is a real music-reactive layer, not a nearly static white
    // streak. Continuous energy brightens it, while transients accelerate and
    // shift the liquid streak without changing contour geometry.
    float paint_drive = clamp(
        u_blob_smoothed_energy * 0.48 +
        u_mid_energy * 0.28 +
        u_high_energy * 0.14 +
        u_transient_mid * 0.24 +
        u_transient_high * 0.16,
        0.0,
        1.35
    );
    float paint_pulse = clamp(
        u_bass_energy * 0.58 + u_transient_bass * 0.42,
        0.0,
        1.25
    );
    // Shaped Blob's outward mutations have their own pale, music-reactive
    // tip light.  Broad authored bulges remain coloured normally; only local
    // protrusions and tendril crests acquire this lighter identity.
    float shaped_tendril_light = 0.0;
    if (BLOB_VARIANT_SHAPED == 1) {
        float shaped_local_profile = sample_profile(angle_frac_main, u_blob_runtime_profile);
        float shaped_neighbor_profile = (
            sample_profile(angle_frac_main - SHAPER_ANGLE_SMOOTH_STEP * 3.0, u_blob_runtime_profile) +
            sample_profile(angle_frac_main + SHAPER_ANGLE_SMOOTH_STEP * 3.0, u_blob_runtime_profile)
        ) * 0.5;
        float shaped_tip_prominence = max(shaped_local_profile - shaped_neighbor_profile, 0.0);
        float shaped_extension = max(shaped_local_profile - 1.0, 0.0);
        float shaped_tendril_drive = clamp(
            u_mid_energy * 0.42 +
            u_high_energy * 0.24 +
            u_overall_energy * 0.14 +
            u_transient_mid * 0.30 +
            u_transient_high * 0.18,
            0.0,
            1.35
        );
        shaped_tendril_light = clamp(
            (shaped_tip_prominence * 5.2 + shaped_extension * 0.34) *
            surface_band * (0.16 + shaped_tendril_drive * 0.84),
            0.0,
            0.74
        );
    }
    float paint_phase = u_time * (0.16 + paint_drive * 0.82);
    float paint_turn = sin(paint_phase * 0.43 + u_mid_energy * 1.7) * (0.08 + paint_drive * 0.14);
    vec2 highlight_axis = normalize(vec2(-0.46 + paint_turn, 0.89 + paint_turn * 0.35));
    vec2 highlight_cross = vec2(-highlight_axis.y, highlight_axis.x);
    vec2 local_uv = uv / max(local_radius, 0.0001);
    float streak_main = dot(local_uv, highlight_axis);
    float streak_cross = dot(local_uv, highlight_cross);
    float streak_arc_a = exp(
        -pow((streak_main - 0.12 - sin(paint_phase) * (0.025 + paint_drive * 0.035) - profile_gradient * 1.8) / 0.15, 2.0)
        -pow((streak_cross + 0.03) / 0.40, 2.0)
    );
    float streak_arc_b = exp(
        -pow((streak_main + 0.01 + sin(paint_phase * 0.73 + 0.8) * (0.018 + paint_pulse * 0.028) + profile_gradient * 1.1) / 0.12, 2.0)
        -pow((streak_cross - 0.10) / 0.28, 2.0)
    );
    float streak_breakup =
        0.72 + 0.28 * sin(
            u_time * (0.72 + paint_drive * 1.85) +
            angle_frac_main * (15.0 + paint_pulse * 5.0) +
            normalized_depth * 4.0
        );
    float slime_highlight = clamp(
        (streak_arc_a * 1.10 + streak_arc_b * 0.62) * streak_breakup * surface_band *
        (0.54 + paint_drive * 0.92 + paint_pulse * 0.22),
        0.0,
        1.0
    );
    float contour_line = exp(
        -pow(max(abs(d_fill) - 0.003, 0.0) / 0.0045, 2.0)
    ) * smoothstep(-0.050, -0.004, d_fill);
    float inner_contour_line = exp(
        -pow(max(abs(d_fill + 0.014) - 0.0025, 0.0) / 0.0050, 2.0)
    ) * smoothstep(-0.080, -0.016, d_fill);
    float vector_rim_line = exp(
        -pow(d_fill / 0.0032, 2.0)
    ) * (0.66 + profile_gradient_abs * 4.0);
    float vector_specular = clamp(
        slime_highlight * (0.85 + profile_gradient_abs * 3.2) +
        vector_rim_line * 0.42,
        0.0,
        1.2
    );

    float border_liquid_alpha = 0.0;
    float border_liquid_line = 0.0;
    if (u_blob_inward_liquid_enabled == 1) {
        vec4 inward_profile = compute_inward_liquid_profile(
            card_edge_distance,
            max(d_fill, 0.0),
            perimeter_phase,
            u_time,
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
        float front_depth = inward_profile.x;
        float front_mix = inward_profile.y;
        float front_width = max(front_depth * 0.10, 0.0032);
        float front_fill = 1.0 - smoothstep(max(front_depth * 0.06, 0.0018), front_depth, card_edge_distance);
        float front_line = exp(-pow((card_edge_distance - front_depth) / front_width, 2.0));
        float front_inner_line = exp(-pow((card_edge_distance - max(front_depth - front_width * 1.6, 0.0)) / max(front_width * 1.4, 0.0035), 2.0));
        float front_ripple = 0.72 + 0.28 * sin(u_time * 1.4 + perimeter_phase * 25.0);
        border_liquid_line = front_line * front_ripple * front_mix;
        border_liquid_alpha =
            clamp((front_fill * 0.18 + border_liquid_line * 1.25 + front_inner_line * 0.44) * front_mix, 0.0, 0.99) *
            clamp(u_blob_inward_liquid_color.a, 0.0, 1.0);
    }

    // Outline band colour (the dark/grey area between fill edge and glow)

    vec3 final_rgb;
    if (d_fill < -0.02) {
        // Deep inside: mostly stable fill colour with a soft ooze highlight.
        float depth = clamp(-d_fill / 0.15, 0.0, 1.0);
        float core_reaction = clamp(0.20 + paint_drive * 0.42 + paint_pulse * 0.10, 0.20, 0.76);
        float highlight_mask = clamp(
            (vector_specular * 0.88 + contour_line * 0.80 + inner_contour_line * 0.46 + vector_rim_line * 0.36) *
            depth * core_reaction,
            0.0,
            0.88
        );
        final_rgb = mix(blob_rgb, vec3(1.0), highlight_mask);
    } else if (d_fill < 0.0) {
        // Near edge: transition from fill to edge highlight colour
        float t = 1.0 - clamp(-d_fill / 0.02, 0.0, 1.0);
        final_rgb = mix(blob_rgb, edge_rgb, clamp(t + contour_line * 0.55 + vector_rim_line * 0.35, 0.0, 1.0));
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

    float blob_total_alpha = max(fill_alpha, max(edge_alpha, max(glow_alpha, max(outline_band_alpha, ghost_ring_alpha))));
    if (blob_total_alpha <= 0.001 && border_liquid_alpha <= 0.001) {
        discard;
    }

    if (blob_total_alpha > 0.001) {
        float deep_fill = smoothstep(-0.22, -0.02, d_fill);
        float paint_reaction = clamp(0.12 + paint_drive * 0.34 + paint_pulse * 0.08, 0.12, 0.62);
        float highlight_mask = clamp(
            (vector_specular * 0.72 + contour_line * 0.58 + inner_contour_line * 0.34 + vector_rim_line * 0.26) *
            deep_fill * paint_reaction,
            0.0,
            0.78
        );
        final_rgb = mix(final_rgb, vec3(1.0), highlight_mask);
        vec3 shaped_tendril_rgb = mix(edge_rgb, vec3(1.0), 0.76);
        final_rgb = mix(final_rgb, shaped_tendril_rgb, shaped_tendril_light);
    }

    vec3 border_liquid_rgb = mix(inward_liquid_rgb, vec3(1.0), 0.16 + border_liquid_line * 0.42);
    float total_alpha = border_liquid_alpha + blob_total_alpha * (1.0 - border_liquid_alpha);
    vec3 composed_rgb = border_liquid_rgb;
    if (blob_total_alpha > 0.001) {
        float blob_weight = blob_total_alpha / max(total_alpha, 0.0001);
        composed_rgb = mix(border_liquid_rgb, final_rgb, blob_weight);
    }

    fragColor = vec4(composed_rgb, total_alpha * u_fade);
}
