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

// Helix configuration
uniform int u_helix_turns;
uniform int u_helix_double;
uniform float u_helix_speed;

// Fill / border colours (reused from spectrum for visual consistency)
uniform vec4 u_fill_color;
uniform vec4 u_border_color;

// Glow configuration (user-controllable)
uniform int u_helix_glow_enabled;
uniform float u_helix_glow_intensity;

const float PI = 3.14159265;

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

    if (fc.x < margin_x || fc.x > width - margin_x ||
        fc.y < margin_y || fc.y > height - margin_y) {
        discard;
    }

    float inner_width = width - margin_x * 2.0;
    float inner_height = height - margin_y * 2.0;
    if (inner_width <= 0.0 || inner_height <= 0.0) {
        discard;
    }

    // Normalised position: x in [0, 1], y centred at 0
    float nx = (fc.x - margin_x) / inner_width;
    float ny = ((fc.y - margin_y) / inner_height) - 0.5;

    // Helix parameters
    int turns = max(2, u_helix_turns);
    float rotation_speed = u_helix_speed + u_bass_energy * 2.0;
    float phase = nx * float(turns) * 2.0 * PI + u_time * rotation_speed;

    // Amplitude of the helix (fraction of half-height)
    float amplitude = 0.35 + u_overall_energy * 0.05;

    // Strand radius in normalised Y units
    float base_radius = 0.04 + u_mid_energy * 0.015;

    float min_dist = 999.0;
    float min_z = 0.0;
    int closest_strand = 0;

    // Two strands (or one if double is off)
    int num_strands = (u_helix_double == 1) ? 2 : 1;

    for (int strand = 0; strand < 2; strand++) {
        if (strand >= num_strands) break;

        float strand_phase = phase + float(strand) * PI;
        float y_strand = sin(strand_phase) * amplitude;
        float z_strand = cos(strand_phase);  // -1..1 depth

        // Pseudo-3D: scale radius by depth
        float depth_factor = 0.5 + 0.5 * (z_strand * 0.5 + 0.5);
        float strand_radius = base_radius * depth_factor;

        float dist = abs(ny - y_strand) - strand_radius;
        if (dist < min_dist) {
            min_dist = dist;
            min_z = z_strand;
            closest_strand = strand;
        }
    }

    // Cross-rungs (DNA ladder) — only when double helix is on
    float rung_dist = 999.0;
    float rung_z = 0.0;
    if (u_helix_double == 1) {
        // Place rungs at regular intervals along x
        float rung_spacing = 1.0 / float(turns * 2);
        float rung_x = mod(nx + rung_spacing * 0.5, rung_spacing);
        float rung_center_dist = abs(rung_x - rung_spacing * 0.5);

        // Rung width in normalised X
        float rung_width = 0.004;

        if (rung_center_dist < rung_width) {
            // The rung connects the two strands at this X position
            float rung_phase = nx * float(turns) * 2.0 * PI + u_time * rotation_speed;
            float y_top = sin(rung_phase) * amplitude;
            float y_bot = sin(rung_phase + PI) * amplitude;

            float y_min = min(y_top, y_bot);
            float y_max = max(y_top, y_bot);

            if (ny >= y_min && ny <= y_max) {
                rung_dist = rung_center_dist;
                // Depth at the midpoint
                float mid_phase = rung_phase + PI * 0.5;
                rung_z = cos(mid_phase) * 0.5;
            }
        }
    }

    // Combine strands and rungs
    bool is_strand = (min_dist <= 0.0);
    bool is_rung = (rung_dist < 999.0);

    if (!is_strand && !is_rung) {
        // Glow around strands (user-controllable)
        if (u_helix_glow_enabled == 0) {
            discard;
        }

        float glow_dist_px = min_dist * inner_height;
        float intensity = max(0.01, u_helix_glow_intensity);
        float glow_sigma = (3.0 + intensity * 8.0) + u_overall_energy * 6.0 * intensity;
        float glow_alpha = 0.0;
        if (glow_dist_px > 0.0 && glow_sigma > 0.0) {
            glow_alpha = exp(-(glow_dist_px * glow_dist_px) / (2.0 * glow_sigma * glow_sigma));
            glow_alpha *= 0.3 + intensity * 0.4;
        }

        if (glow_alpha <= 0.001) {
            discard;
        }

        vec3 glow_rgb = u_border_color.rgb;
        fragColor = vec4(glow_rgb, glow_alpha * u_fade);
        return;
    }

    // Depth-based shading: front strands are brighter
    float z_val = is_strand ? min_z : rung_z;
    float depth_shade = 0.5 + 0.5 * (z_val * 0.5 + 0.5);

    // Energy-reactive brightness
    float brightness = 0.7 + u_overall_energy * 0.3;

    vec3 base_rgb;
    if (is_strand) {
        // Alternate strand colours slightly
        if (closest_strand == 0) {
            base_rgb = u_border_color.rgb;
        } else {
            base_rgb = mix(u_border_color.rgb, u_fill_color.rgb, 0.4);
        }
    } else {
        // Rungs use a muted fill colour
        base_rgb = u_fill_color.rgb * 0.7;
    }

    vec3 final_rgb = base_rgb * depth_shade * brightness;

    // Anti-aliased edge
    float edge_aa = 1.0;
    if (is_strand && min_dist > -0.005) {
        edge_aa = smoothstep(0.0, -0.005, min_dist);
    }

    fragColor = vec4(final_rgb, edge_aa * u_fade);
}
