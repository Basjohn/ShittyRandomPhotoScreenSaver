"""Burn transition shader program.

Simulates a burning-paper effect: a noisy jagged edge eats across the screen,
leaving a warm glow zone and a charred black zone before revealing the new image.
Optional smoke puffs and falling ash particles add to the effect.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from rendering.gl_programs.base_program import BaseGLProgram

logger = logging.getLogger(__name__)

try:
    from OpenGL import GL as gl
except ImportError:
    gl = None  # type: ignore


class BurnProgram(BaseGLProgram):
    """Shader program for the Burn transition effect."""

    @property
    def name(self) -> str:
        return "Burn"

    @property
    def vertex_source(self) -> str:
        return """#version 410 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUv;

out vec2 vUv;

void main() {
    vUv = aUv;
    gl_Position = vec4(aPos, 0.0, 1.0);
}
"""

    @property
    def fragment_source(self) -> str:
        return """#version 410 core
in vec2 vUv;
out vec4 FragColor;

uniform sampler2D uOldTex;
uniform sampler2D uNewTex;
uniform float u_progress;
uniform int   u_direction;      // 0=L->R, 1=R->L, 2=T->B, 3=B->T
uniform float u_jaggedness;     // 0.0-1.0 edge waviness amplitude
uniform float u_glow_intensity; // 0.0-1.0
uniform vec4  u_glow_color;     // RGBA primary glow colour (warm orange)
uniform float u_char_width;     // 0.1-1.0 controls dark zone width
uniform int   u_smoke_enabled;  // 1 = sparks + smoke on
uniform float u_smoke_density;  // smoke/spark intensity multiplier
uniform int   u_ash_enabled;    // 1 = falling ash on
uniform float u_ash_density;    // ash quantity multiplier
uniform float u_time;           // wall-clock seconds
uniform float u_seed;           // per-transition random seed

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
    if (u_direction == 2) return 1.0 - uv.y;
    if (u_direction == 3) return uv.y;
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
    float front = move_t * 1.12 - edge_noise * jag_amount;

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

    // Smooth fade to new image near completion
    float tail_fade = smoothstep(0.88, 1.0, move_t);

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

        // Ember gradient: deep red → dark brown → charred black
        vec3 ember_hot  = vec3(0.9, 0.25, 0.05);
        vec3 ember_cool = vec3(0.15, 0.04, 0.01);
        vec3 charred    = vec3(0.02, 0.01, 0.005);

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

        out_rgb = ember_col;

    } else {
        // ---- Fully burned: new image ----
        out_rgb = new_col.rgb;
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
            ash_uv.y += u_time * 0.02;
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

    def cache_uniforms(self, program: int) -> Dict[str, int]:
        if gl is None:
            return {}
        names = [
            "u_progress", "uOldTex", "uNewTex",
            "u_direction", "u_jaggedness", "u_glow_intensity",
            "u_glow_color", "u_char_width",
            "u_smoke_enabled", "u_smoke_density",
            "u_ash_enabled", "u_ash_density",
            "u_time", "u_seed",
        ]
        return {n: gl.glGetUniformLocation(program, n) for n in names}

    def render(
        self,
        program: int,
        uniforms: Dict[str, int],
        viewport: Tuple[int, int],
        old_tex: int,
        new_tex: int,
        state: Any,
        quad_vao: int,
    ) -> None:
        if gl is None:
            return

        import time as _time

        vp_w, vp_h = viewport
        progress = max(0.0, min(1.0, float(getattr(state, "progress", 0.0))))
        direction = int(getattr(state, "direction", 0))
        jaggedness = float(getattr(state, "jaggedness", 0.5))
        glow_intensity = float(getattr(state, "glow_intensity", 0.7))
        glow_color = getattr(state, "glow_color", (1.0, 0.55, 0.12, 1.0))
        char_width = float(getattr(state, "char_width", 0.5))
        smoke_enabled = int(getattr(state, "smoke_enabled", True))
        smoke_density = float(getattr(state, "smoke_density", 0.5))
        ash_enabled = int(getattr(state, "ash_enabled", True))
        ash_density = float(getattr(state, "ash_density", 0.5))
        seed = float(getattr(state, "seed", 0.0))
        wall_time = float(_time.monotonic())

        gl.glViewport(0, 0, vp_w, vp_h)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glUseProgram(program)

        def _set(name: str, fn, *args):
            loc = uniforms.get(name, -1)
            if loc != -1:
                fn(loc, *args)

        try:
            _set("u_progress",      gl.glUniform1f, float(progress))
            _set("u_direction",     gl.glUniform1i, direction)
            _set("u_jaggedness",    gl.glUniform1f, jaggedness)
            _set("u_glow_intensity",gl.glUniform1f, glow_intensity)
            _set("u_char_width",    gl.glUniform1f, char_width)
            _set("u_smoke_enabled", gl.glUniform1i, smoke_enabled)
            _set("u_smoke_density", gl.glUniform1f, smoke_density)
            _set("u_ash_enabled",   gl.glUniform1i, ash_enabled)
            _set("u_ash_density",   gl.glUniform1f, ash_density)
            _set("u_time",          gl.glUniform1f, wall_time)
            _set("u_seed",          gl.glUniform1f, seed)

            loc_gc = uniforms.get("u_glow_color", -1)
            if loc_gc != -1:
                r, g, b, a = (float(c) for c in glow_color)
                gl.glUniform4f(loc_gc, r, g, b, a)

            loc_old = uniforms.get("uOldTex", -1)
            if loc_old != -1:
                gl.glActiveTexture(gl.GL_TEXTURE0)
                gl.glBindTexture(gl.GL_TEXTURE_2D, old_tex)
                gl.glUniform1i(loc_old, 0)

            loc_new = uniforms.get("uNewTex", -1)
            if loc_new != -1:
                gl.glActiveTexture(gl.GL_TEXTURE1)
                gl.glBindTexture(gl.GL_TEXTURE_2D, new_tex)
                gl.glUniform1i(loc_new, 1)

            self._draw_fullscreen_quad(quad_vao)

        finally:
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glUseProgram(0)


burn_program = BurnProgram()
