"""Burn transition shader program.

Simulates a burning-paper effect: a noisy jagged edge eats across the screen,
leaving a warm glow zone and a charred black zone before revealing the new image.
Optional smoke puffs and falling ash particles add to the effect, and optionally (both off by
default) flames licking up from the burning edge and glowing ember veins crawling through the char.
"""

from __future__ import annotations

from rendering.gl_programs.base_program import BaseGLProgram


class BurnProgram(BaseGLProgram):
    """Shader program for the Burn transition effect."""

    @property
    def name(self) -> str:
        return "Burn"

    @property
    def vertex_source(self) -> str:
        return """#version 460 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;

layout(location = 0) out vec2 vUv;

void main() {
    vUv = aUv;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

    @property
    def fragment_source(self) -> str:
        return """#version 460 core
layout(location = 0) in vec2 vUv;
layout(location = 0) out vec4 FragColor;

layout(binding = 0) uniform sampler2D uOldTex;
layout(binding = 1) uniform sampler2D uNewTex;
// The pass block (N1.6): the item quad's values and this program's, one std140 block at the pass-block binding
// (SCENE3D_PASS_BLOCK_BINDING); the quad's vertex stage declares the same block (quick/transitions/fullscreen_pass).
layout(std140, binding = 18) uniform BurnPass {
    mat4  uMatrix;
    vec2  uItemSize;
    float u_progress;
    int   u_direction;      // 0=L->R, 1=R->L, 2=T->B, 3=B->T
    float u_jaggedness;     // 0.0-1.0 edge waviness amplitude
    float u_glow_intensity; // 0.0-1.0
    vec4  u_glow_color;     // RGBA primary glow colour
    vec4  u_ember_color;    // RGBA ember/char ramp colour
    float u_char_width;     // 0.1-1.0 controls dark zone width
    int   u_smoke_enabled;  // 1 = sparks + smoke on
    float u_smoke_density;  // smoke/spark intensity multiplier
    int   u_ash_enabled;    // 1 = falling ash on
    float u_ash_density;    // ash quantity multiplier
    int   u_flames;         // 1 = flames rise from the burning edge
    int   u_ember_veins;    // 1 = glowing veins crawl through the char
    float u_time;           // wall-clock seconds
    float u_seed;           // per-transition random seed
};

// =====================================================================
//  Noise primitives
// =====================================================================
float hash21(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);   // Hermite smoothstep
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// 4-octave FBM for richer edge detail
float fbm4(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; i++) {
        v += a * vnoise(p);
        p = p * 2.03 + vec2(1.7, 9.2 + u_seed * 0.1);
        a *= 0.5;
    }
    return v;
}

// Domain-warped FBM — organic, paper-like irregularity
float warped_fbm(vec2 p) {
    vec2 q = vec2(fbm4(p + vec2(0.0, 0.0)),
                  fbm4(p + vec2(5.2, 1.3)));
    return fbm4(p + 3.0 * q);
}

// =====================================================================
//  Burn axis — sweep coordinate [0..1]
// =====================================================================
float burn_axis(vec2 uv) {
    if (u_direction == 1) return 1.0 - uv.x;
    // uv is the texture coordinate: v grows down the screen.
    if (u_direction == 2) return uv.y;
    if (u_direction == 3) return 1.0 - uv.y;
    if (u_direction == 4) return (uv.x + uv.y) * 0.5;                // TL->BR
    if (u_direction == 5) return ((1.0 - uv.x) + uv.y) * 0.5;        // TR->BL
    return uv.x;
}

// =====================================================================
//  Spark / ember hash
// =====================================================================
float spark_hash(vec2 p, float s) {
    return fract(sin(dot(p + s, vec2(127.1, 311.7))) * 43758.5453);
}

// =====================================================================
//  Main
// =====================================================================
void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);

    // Hard guards — exact old/new at extremes (transition policy)
    if (t <= 0.0) { FragColor = texture(uOldTex, uv); return; }
    if (t >= 1.0) { FragColor = texture(uNewTex, uv); return; }

    // --- Ignition phase (first 5%): glow builds before front moves ---
    float ignition = 0.05;
    float glow_buildup = smoothstep(0.0, ignition, t);
    float move_t = (t < ignition) ? 0.0 : (t - ignition) / (1.0 - ignition);

    float axis = burn_axis(uv);

    // Perpendicular coordinate for noise sampling along burn edge
    float perp = (u_direction <= 1) ? uv.y : uv.x;

    // --- Domain-warped noise for jagged, organic burn edge ---
    // The noise field is 2D: perpendicular position + slow time drift
    vec2 noise_coord = vec2(perp * 5.0 + u_seed * 0.13,
                            axis * 3.5 + move_t * 1.2);
    float edge_noise = warped_fbm(noise_coord);

    // Jaggedness controls how much the noise deforms the burn front
    // Range: 0.0 = nearly straight line, 1.0 = very wild/organic edge
    float jag_amount = u_jaggedness * 0.22;
    float front = move_t * 1.35 - edge_noise * jag_amount;

    // Signed distance: positive = ahead of front (old), negative = behind (burned)
    float sd = axis - front;

    // --- Heat distortion: warp UVs near the burn front ---
    float dist_strength = 0.006 * u_glow_intensity * glow_buildup;
    float dist_zone = 0.08;
    float dist_factor = smoothstep(dist_zone, 0.0, abs(sd));
    vec2 distort_offset = vec2(
        vnoise(uv * 30.0 + u_time * 1.5) - 0.5,
        vnoise(uv * 30.0 + u_time * 1.5 + 100.0) - 0.5
    ) * dist_strength * dist_factor;
    vec2 uv_distorted = uv + distort_offset;

    vec4 old_col = texture(uOldTex, uv_distorted);
    vec4 new_col = texture(uNewTex, uv);

    // --- Zone widths (wider for dramatic effect) ---
    float glow_w  = 0.015 + u_glow_intensity * 0.035;  // warm glow bleed ahead of front
    float core_w  = 0.005 + u_glow_intensity * 0.010;  // white-hot burn line
    float char_w  = 0.025 + u_char_width * 0.08;       // charred zone behind front

    // Smooth fade to new image near completion (delayed so burn reaches far edge)
    float tail_fade = smoothstep(0.92, 1.0, move_t);

    // Thermite intensity: peaks at ignition, stays warm
    float thermite = mix(1.5, 1.0, smoothstep(0.0, 0.20, move_t));
    thermite *= glow_buildup;

    // Secondary noise for ember/char detail
    float detail_noise = vnoise(uv * 20.0 + u_seed);

    vec3 out_rgb;

    if (sd > glow_w) {
        // ---- Unburned: old image ----
        out_rgb = old_col.rgb;

    } else if (sd > 0.0) {
        // ---- Heat glow zone: warm tint bleeding into old image ----
        float f = 1.0 - sd / glow_w;
        f = f * f * f;  // cubic falloff for soft bleed

        // Warm tint shifts from user color toward yellow-white at the edge
        vec3 warm_tint = mix(u_glow_color.rgb, vec3(1.0, 0.9, 0.7), f * 0.4);

        // Additive warm glow on old image
        float glow_str = f * u_glow_intensity * thermite * 0.75;
        out_rgb = old_col.rgb + warm_tint * glow_str;

        // Slight desaturation near the front (paper scorching)
        float lum = dot(out_rgb, vec3(0.299, 0.587, 0.114));
        out_rgb = mix(out_rgb, vec3(lum), f * 0.25);

    } else if (sd > -core_w) {
        // ---- White-hot burn line: thermite core ----
        float f = 1.0 - (-sd) / core_w;  // 1 at front, 0 at edge
        f = f * f;

        // Color ramp: orange fringe → white-hot center
        vec3 white_hot = vec3(1.0, 0.97, 0.85);
        vec3 hot = mix(u_glow_color.rgb, white_hot, f * 0.92);

        // HDR-like intensity with additive bloom
        float intensity = u_glow_intensity * thermite * (1.0 + f * 0.6);
        out_rgb = hot * min(intensity, 1.0);
        // Additive bloom overshoot
        out_rgb += hot * max(0.0, intensity - 1.0) * 0.5;

        // Flicker: subtle pulsing from noise
        float flicker = 0.92 + 0.08 * vnoise(vec2(perp * 40.0, u_time * 6.0));
        out_rgb *= flicker;

    } else if (sd > -(core_w + char_w)) {
        // ---- Char zone: burnt residue with ember gradient ----
        float behind = (-sd) - core_w;
        float ct = smoothstep(0.0, 1.0, behind / char_w);

        // Ember gradient is independently themeable from the front glow.
        // The per-channel darkening factors reproduce the historical default
        // ramp exactly while allowing non-orange hues to carry through the
        // hot/cooling/charred zones instead of leaking fixed red/orange.
        vec3 ember_hot  = u_ember_color.rgb;
        vec3 ember_cool = u_ember_color.rgb * vec3(1.0 / 6.0, 0.16, 0.20);
        vec3 charred    = u_ember_color.rgb * vec3(1.0 / 45.0, 0.04, 0.10);

        vec3 ember_col;
        if (ct < 0.3) {
            // Near the front: hot embers
            float ef = ct / 0.3;
            ember_col = mix(ember_hot, ember_cool, ef);
        } else if (ct < 0.7) {
            // Mid zone: cooling embers
            float ef = (ct - 0.3) / 0.4;
            ember_col = mix(ember_cool, charred, ef);
        } else {
            // Far zone: charred, revealing new image
            float ef = (ct - 0.7) / 0.3;
            ember_col = mix(charred, new_col.rgb, ef * ef);
        }

        // Detail noise breaks up the char for papery crackle
        float crackle = smoothstep(0.3, 0.7, detail_noise);
        ember_col = mix(ember_col, ember_col * 1.3, crackle * (1.0 - ct) * 0.4);

        // Ember glow pulsing with time (smouldering)
        float smoulder = (1.0 - ct) * u_glow_intensity * thermite * 0.4;
        smoulder *= 0.8 + 0.2 * sin(u_time * 3.0 + perp * 20.0);
        ember_col += u_glow_color.rgb * smoulder;

        // Ember veins: thin glowing cracks through the fresh char, cooling as it chars.
        if (u_ember_veins == 1) {
            float ridge = 1.0 - abs(2.0 * fbm4(uv * 16.0 + vec2(u_seed * 0.37, 3.1)) - 1.0);
            float vein = smoothstep(0.9, 0.985, ridge) * pow(1.0 - ct, 1.5) * thermite;
            ember_col += mix(u_ember_color.rgb, u_glow_color.rgb, 0.55) * vein * 1.7;
        }

        out_rgb = ember_col;

    } else {
        // ---- Fully burned: new image ----
        out_rgb = new_col.rgb;
    }

    // =================================================================
    //  Flames licking up from the burning edge (rising in screen space)
    // =================================================================
    if (u_flames == 1 && move_t < 0.97) {
        // uv.y grows down the screen. How fast the sweep coordinate changes going down:
        // the burning edge lies below this point at height -sd / slope.
        float slope = u_direction == 2 ? 1.0 : (u_direction == 3 ? -1.0
                    : (u_direction >= 4 ? 0.5 : 0.0));
        float height = abs(slope) > 0.01 ? -sd / slope : abs(sd) * 3.0;
        float reach = 0.07 + 0.09 * u_glow_intensity;
        if (height > -0.01 && height < reach * 1.3) {
            // Tongues: noise scrolling up the screen, cut off by height above the edge.
            float n = fbm4(vec2(uv.x * 14.0, uv.y * 7.0 + u_time * 1.7) + u_seed);
            float tongue = n * 1.3 - max(height, 0.0) / reach;
            float body = smoothstep(0.0, 0.35, tongue);
            vec3 fire = mix(u_ember_color.rgb, u_glow_color.rgb, smoothstep(0.1, 0.5, tongue));
            fire = mix(fire, vec3(1.0, 0.95, 0.8), smoothstep(0.55, 0.95, tongue));
            out_rgb += fire * body * thermite * (1.0 - tail_fade) * 0.9;
        }
    }

    // =================================================================
    //  Sparks / embers (rising hot particles near burn front)
    // =================================================================
    if (u_smoke_enabled == 1 && move_t > 0.01 && move_t < 0.96) {
        float spark_zone = glow_w * 5.0 + 0.04;
        if (abs(sd) < spark_zone) {
            // Staggered grid with per-cell jitter for organic placement
            vec2 cell_size = vec2(120.0, 60.0);
            vec2 cell_id = floor(uv * cell_size);
            float rnd = spark_hash(cell_id, u_seed);

            // ~12% of cells have a spark at any moment
            if (rnd > 0.88) {
                // Spark lifecycle: born, rises, fades
                float phase = fract(rnd * 23.7 + u_time * 2.5);
                float spark_life = 1.0 - phase;
                spark_life *= spark_life;  // quadratic decay

                // Spark drifts upward (in screen space)
                float rise = phase * 0.03;
                vec2 spark_uv = fract(uv * cell_size) - 0.5;
                spark_uv.y += rise * cell_size.y;

                // Soft circular spark shape
                float spark_r = length(spark_uv) * 3.0;
                float spark_shape = exp(-spark_r * spark_r * 8.0);

                // Proximity: sparks closer to the front are brighter
                float prox = 1.0 - abs(sd) / spark_zone;
                prox = prox * prox;

                float spark_i = spark_life * spark_shape * prox
                              * u_glow_intensity * thermite
                              * u_smoke_density * 2.5;

                // Color: white-hot → orange → red as spark cools
                vec3 spark_col = mix(u_glow_color.rgb, vec3(1.0, 0.95, 0.8),
                                     spark_life * 0.8);
                out_rgb += spark_col * spark_i;
            }
        }
    }

    // =================================================================
    //  Falling ash (dark specks drifting down from burn zone)
    // =================================================================
    if (u_ash_enabled == 1 && move_t > 0.05 && move_t < 0.97) {
        float ash_zone = char_w * 2.0 + 0.06;
        // Ash appears behind the burn front
        if (sd < 0.0 && sd > -ash_zone) {
            vec2 ash_cell_size = vec2(60.0, 30.0);
            // Ash drifts downward and slightly sideways
            vec2 ash_uv = uv;
            ash_uv.y -= u_time * 0.02;
            ash_uv.x += sin(u_time * 0.8 + uv.y * 15.0) * 0.003;
            vec2 ash_cell = floor(ash_uv * ash_cell_size);
            float ash_rnd = spark_hash(ash_cell, u_seed + 77.0);

            if (ash_rnd > (1.0 - u_ash_density * 0.15)) {
                float ash_phase = fract(ash_rnd * 31.1 + u_time * 1.5);
                float ash_alpha = (1.0 - ash_phase) * (1.0 - ash_phase);

                // Proximity to burn front
                float ash_prox = 1.0 - abs(sd) / ash_zone;
                ash_prox *= ash_prox;

                // Small dark speck
                vec2 ash_frac = fract(ash_uv * ash_cell_size) - 0.5;
                float ash_r = length(ash_frac) * 4.0;
                float ash_shape = exp(-ash_r * ash_r * 12.0);

                float ash_i = ash_alpha * ash_shape * ash_prox * u_ash_density * 0.5;
                vec3 ash_col = vec3(0.08, 0.05, 0.03);  // dark grey-brown
                out_rgb = mix(out_rgb, ash_col, ash_i);
            }
        }
    }

    // =================================================================
    //  Smoke wisps (semi-transparent haze ahead of burn front)
    // =================================================================
    if (u_smoke_enabled == 1 && move_t > 0.02 && move_t < 0.95) {
        float smoke_zone = glow_w * 3.0 + 0.05;
        if (sd > 0.0 && sd < smoke_zone) {
            float smoke_f = 1.0 - sd / smoke_zone;
            smoke_f = smoke_f * smoke_f;

            // Animated smoke noise (drifts perpendicular to burn direction)
            vec2 smoke_uv = vec2(perp * 8.0 + u_time * 0.4,
                                 axis * 6.0 - u_time * 0.15);
            float smoke_n = fbm4(smoke_uv + u_seed);
            smoke_n = smoothstep(0.35, 0.75, smoke_n);

            float smoke_alpha = smoke_f * smoke_n * u_smoke_density * 0.3 * thermite;
            vec3 smoke_col = vec3(0.25, 0.22, 0.20);  // warm grey
            out_rgb = mix(out_rgb, smoke_col, smoke_alpha);
        }
    }

    // Near completion: lerp toward new image to guarantee clean final frame
    out_rgb = mix(out_rgb, new_col.rgb, tail_fade);

    FragColor = vec4(clamp(out_rgb, 0.0, 1.0), 1.0);
}
"""


burn_program = BurnProgram()
