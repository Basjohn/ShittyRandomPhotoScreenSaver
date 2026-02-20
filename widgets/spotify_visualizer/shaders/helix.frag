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

// Fill / border colours
uniform vec4 u_fill_color;
uniform vec4 u_border_color;

// Glow configuration
uniform int u_helix_glow_enabled;
uniform float u_helix_glow_intensity;
uniform vec4 u_helix_glow_color;
uniform int u_helix_reactive_glow;
uniform float u_rainbow_hue_offset; // 0..1 hue rotation (0 = disabled)

const float PI  = 3.14159265;
const float TAU = 6.28318530;

// ── Analytical 3D DNA helix with cylindrical tube shading ───────
// The helix extends horizontally across the card.  For each pixel
// we analytically compute the 3D position of each strand, project
// to screen space, then render with cylindrical cross-section
// normals and Blinn-Phong lighting for a true 3D tube appearance.

// Shade a tube cross-section.  Returns vec4(rgb, alpha).
// h      = normalised offset within tube (-1..1, from bottom to top)
// z_norm = depth of tube centre (-1..1, +1 = toward viewer)
// base_col = material colour
// bright = overall brightness multiplier
vec4 shade_tube(float h, float z_norm, vec3 base_col, float bright) {
    // Cylindrical surface normal at this point on the cross-section
    float ny = h;
    float nz = sqrt(max(0.0, 1.0 - h * h));
    vec3 normal = vec3(0.0, ny, nz);

    // Light direction (upper-right, toward viewer)
    vec3 light_dir = normalize(vec3(0.3, 0.6, 0.8));
    vec3 view_dir  = vec3(0.0, 0.0, 1.0);

    // Diffuse
    float diff = max(dot(normal, light_dir), 0.0);

    // Specular (Blinn-Phong)
    vec3 half_v = normalize(light_dir + view_dir);
    float spec = pow(max(dot(normal, half_v), 0.0), 48.0) * 0.7;

    // Depth shading: back strands darker, front strands brighter
    float depth_shade = 0.3 + 0.7 * (z_norm * 0.5 + 0.5);

    // Ambient + diffuse + specular
    vec3 col = base_col * (0.18 + diff * 0.72) * depth_shade * bright;
    col += vec3(spec) * depth_shade;

    return vec4(col, 1.0);
}

void main() {
    if (u_fade <= 0.0) discard;

    float width  = u_resolution.x;
    float height = u_resolution.y;
    if (width <= 0.0 || height <= 0.0) discard;

    float dpr = max(u_dpr, 1.0);
    float fb_height = height * dpr;
    vec2 fc = vec2(gl_FragCoord.x / dpr, (fb_height - gl_FragCoord.y) / dpr);

    float margin_x = 8.0;
    float margin_y = 6.0;
    if (fc.x < margin_x || fc.x > width - margin_x ||
        fc.y < margin_y || fc.y > height - margin_y) discard;

    float inner_w = width  - margin_x * 2.0;
    float inner_h = height - margin_y * 2.0;
    if (inner_w <= 0.0 || inner_h <= 0.0) discard;

    // Normalised pixel coordinates
    float nx = (fc.x - margin_x) / inner_w;            // 0..1 across card
    float ny = (fc.y - margin_y) / inner_h - 0.5;      // -0.5..+0.5, centred

    // ── Helix parameters ────────────────────────────────────────
    int   turns     = max(2, u_helix_turns);
    float speed     = u_helix_speed * 1.2 + u_bass_energy * 1.5;
    float amplitude = 0.30 + u_bass_energy * 0.04;     // coil radius (norm)
    float tube_r    = 0.038 + u_mid_energy * 0.008;    // tube radius (norm)
    float rung_r_px = 1.8 + u_high_energy * 0.4;       // rung half-width (px)

    // Phase at this horizontal position
    float theta = nx * float(turns) * TAU + u_time * speed;

    // ── Strand 3D positions ─────────────────────────────────────
    //  Y = vertical on screen,  Z = depth (+1 toward viewer)
    float yA =  amplitude * sin(theta);
    float zA =  amplitude * cos(theta);
    float yB = -yA;    // strand B is PI-offset: sin(t+PI) = -sin(t)
    float zB = -zA;    // cos(t+PI) = -cos(t)

    // Depth-dependent tube radius (pseudo-perspective)
    float perspA = 0.65 + 0.35 * (zA / amplitude + 1.0) * 0.5;
    float perspB = 0.65 + 0.35 * (zB / amplitude + 1.0) * 0.5;
    float tubeA = tube_r * perspA;
    float tubeB = tube_r * perspB;

    // Screen-space distance from pixel to each strand centre
    float distA = abs(ny - yA);
    float distB = abs(ny - yB);

    // Anti-aliased tube edge (half-pixel softness)
    float aa = 0.7 / inner_h;

    // ── Depth sorting ───────────────────────────────────────────
    // Higher Z = closer to viewer = rendered on top
    bool a_in_front = (zA >= zB);

    // Back strand properties
    float dist_back  = a_in_front ? distB : distA;
    float tube_back  = a_in_front ? tubeB : tubeA;
    float y_back     = a_in_front ? yB    : yA;
    float z_back     = a_in_front ? zB    : zA;
    vec3  col_back   = a_in_front ? u_fill_color.rgb : u_border_color.rgb;

    // Front strand properties
    float dist_front = a_in_front ? distA : distB;
    float tube_front = a_in_front ? tubeA : tubeB;
    float y_front    = a_in_front ? yA    : yB;
    float z_front    = a_in_front ? zA    : zB;
    vec3  col_front  = a_in_front ? u_border_color.rgb : u_fill_color.rgb;

    float bright = 0.78 + u_overall_energy * 0.3;

    vec3  out_rgb = vec3(0.0);
    float out_a   = 0.0;

    // ── Layer 1: Back strand ────────────────────────────────────
    if (u_helix_double == 1 && dist_back < tube_back + aa) {
        float h = clamp((ny - y_back) / tube_back, -1.0, 1.0);
        float z_n = z_back / amplitude;   // normalised depth -1..+1
        vec4 shaded = shade_tube(h, z_n, col_back, bright);
        float alpha = smoothstep(tube_back + aa, tube_back - aa, dist_back);
        out_rgb = mix(out_rgb, shaded.rgb, alpha);
        out_a   = max(out_a, alpha);
    }

    // ── Layer 2: Rungs (base pairs) ─────────────────────────────
    if (u_helix_double == 1) {
        float rungs_per_turn = 5.0;
        float rung_total = float(turns) * rungs_per_turn;
        float rung_period = 1.0 / rung_total;
        float rung_local = mod(nx + rung_period * 0.5, rung_period)
                         - rung_period * 0.5;
        float rung_px = abs(rung_local) * inner_w;

        if (rung_px < rung_r_px + 0.5) {
            // Y bounds: between the two strand centres (inset by tube radius)
            float y_lo = min(yA, yB) + tube_r * 0.6;
            float y_hi = max(yA, yB) - tube_r * 0.6;

            if (ny > y_lo && ny < y_hi) {
                // Interpolate depth along the rung
                float t_rung = clamp((ny - yA) / (yB - yA), 0.0, 1.0);
                float z_rung = mix(zA, zB, t_rung);
                float depth_shade = 0.3 + 0.7 * (z_rung / amplitude + 1.0) * 0.5;

                // Two-tone base pairs (different colour each half)
                float mid_y = (y_lo + y_hi) * 0.5;
                vec3 pair_a = u_fill_color.rgb * 0.65;
                vec3 pair_b = u_border_color.rgb * 0.65;
                vec3 rung_col = (ny < mid_y) ? pair_a : pair_b;
                rung_col *= depth_shade * bright;

                // Anti-alias rung edges
                float rung_aa = smoothstep(rung_r_px + 0.5, rung_r_px - 0.5, rung_px);
                float edge_fade = smoothstep(0.0, 0.008, ny - y_lo)
                                * smoothstep(0.0, 0.008, y_hi - ny);
                rung_aa *= edge_fade;

                // Only composite rung behind the front strand
                float front_mask = smoothstep(tube_front - aa, tube_front + aa, dist_front);
                rung_aa *= front_mask;

                out_rgb = mix(out_rgb, rung_col, rung_aa);
                out_a   = max(out_a, rung_aa);
            }
        }
    }

    // ── Layer 3: Front strand (always drawn) ────────────────────
    if (dist_front < tube_front + aa) {
        float h = clamp((ny - y_front) / tube_front, -1.0, 1.0);
        float z_n = z_front / amplitude;
        vec4 shaded = shade_tube(h, z_n, col_front, bright);
        float alpha = smoothstep(tube_front + aa, tube_front - aa, dist_front);
        out_rgb = mix(out_rgb, shaded.rgb, alpha);
        out_a   = max(out_a, alpha);
    }

    // ── Glow (emitted around strands when nothing else drawn) ───
    if (out_a < 0.01 && u_helix_glow_enabled == 1) {
        float closest_px = min(
            u_helix_double == 1 ? dist_back : 999.0,
            dist_front
        ) * inner_h;

        float inten = max(0.01, u_helix_glow_intensity);
        float sigma = 4.0 + inten * 12.0;
        if (u_helix_reactive_glow == 1) {
            sigma += u_overall_energy * 14.0 * inten;
        }
        float ga = exp(-(closest_px * closest_px) / (2.0 * sigma * sigma));
        ga *= 0.25 + inten * 0.5;
        if (u_helix_reactive_glow == 1) {
            ga *= 0.35 + u_overall_energy * 0.95;
        }
        if (ga > 0.003) {
            fragColor = vec4(u_helix_glow_color.rgb, ga * u_fade);
            return;
        }
    }

    if (out_a < 0.001) discard;

    // Rainbow hue shift (Taste The Rainbow mode)
    if (u_rainbow_hue_offset > 0.001) {
        float cmax = max(out_rgb.r, max(out_rgb.g, out_rgb.b));
        float cmin = min(out_rgb.r, min(out_rgb.g, out_rgb.b));
        float delta = cmax - cmin;
        float h = 0.0;
        if (delta > 0.0001) {
            if (cmax == out_rgb.r) h = mod((out_rgb.g - out_rgb.b) / delta, 6.0);
            else if (cmax == out_rgb.g) h = (out_rgb.b - out_rgb.r) / delta + 2.0;
            else h = (out_rgb.r - out_rgb.g) / delta + 4.0;
            h /= 6.0;
            if (h < 0.0) h += 1.0;
        }
        float s = (cmax > 0.0001) ? delta / cmax : 0.0;
        float v = cmax;
        // Force saturation on greyscale so rainbow colouring is visible
        if (s < 0.05 && v > 0.05) s = 1.0;
        h = fract(h + u_rainbow_hue_offset);
        float c = v * s;
        float x = c * (1.0 - abs(mod(h * 6.0, 2.0) - 1.0));
        float m = v - c;
        vec3 rgb;
        if      (h < 1.0/6.0) rgb = vec3(c, x, 0.0);
        else if (h < 2.0/6.0) rgb = vec3(x, c, 0.0);
        else if (h < 3.0/6.0) rgb = vec3(0.0, c, x);
        else if (h < 4.0/6.0) rgb = vec3(0.0, x, c);
        else if (h < 5.0/6.0) rgb = vec3(x, 0.0, c);
        else                  rgb = vec3(c, 0.0, x);
        out_rgb = rgb + m;
    }

    fragColor = vec4(out_rgb, out_a * u_fade);
}
