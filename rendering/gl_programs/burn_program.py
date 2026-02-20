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
uniform int   u_smoke_enabled;  // unused, kept for API compat
uniform float u_smoke_density;  // unused
uniform int   u_ash_enabled;    // unused
uniform float u_ash_density;    // unused
uniform float u_time;           // wall-clock seconds
uniform float u_seed;           // per-transition random seed

// -----------------------------------------------------------------------
// Smooth value noise
// -----------------------------------------------------------------------
float hash21(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    float a = hash21(i);
    float b = hash21(i + vec2(1.0, 0.0));
    float c = hash21(i + vec2(0.0, 1.0));
    float d = hash21(i + vec2(1.0, 1.0));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// 3-octave FBM — enough detail without being too jagged
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 3; i++) {
        v += a * vnoise(p);
        p  = p * 2.1 + vec2(1.7, 9.2 + u_seed * 0.1);
        a *= 0.5;
    }
    return v;
}

// -----------------------------------------------------------------------
// Axis: returns the sweep coordinate [0..1] for this pixel.
// The burn front advances from 0 toward 1 as progress goes 0->1.
// Pixels where axis < front are "burned" (behind the line).
// Pixels where axis > front are "unburned" (ahead of the line = old image).
// -----------------------------------------------------------------------
float burn_axis(vec2 uv) {
    if (u_direction == 1) return 1.0 - uv.x;   // R->L: front starts at right
    if (u_direction == 2) return 1.0 - uv.y;   // T->B: front starts at top (UV y=0=top)
    if (u_direction == 3) return uv.y;          // B->T: front starts at bottom
    return uv.x;                                // 0=L->R (default)
}

// -----------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------
// -----------------------------------------------------------------------
// Spark hash — cheap pseudo-random for spark positions
// -----------------------------------------------------------------------
float spark_hash(vec2 p, float s) {
    return fract(sin(dot(p + s, vec2(127.1, 311.7))) * 43758.5453);
}

void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
    float t = clamp(u_progress, 0.0, 1.0);

    // Hard guards — exact old/new at extremes (policy: no artifacts)
    if (t <= 0.0) { FragColor = texture(uOldTex, uv); return; }
    if (t >= 1.0) { FragColor = texture(uNewTex, uv); return; }

    vec4 old_col = texture(uOldTex, uv);
    vec4 new_col = texture(uNewTex, uv);

    // --- Thermite startup delay ---
    // First 5% of progress: front stays at 0 while glow builds to max.
    // Remaining 95%: front sweeps 0→1 normally.
    float ignition = 0.05;
    float glow_buildup = smoothstep(0.0, ignition, t);  // 0→1 during ignition
    float move_t = (t < ignition) ? 0.0 : (t - ignition) / (1.0 - ignition);

    float axis = burn_axis(uv);

    // Perpendicular coordinate — noise runs ALONG the burn line
    float perp = (u_direction <= 1) ? uv.y : uv.x;
    vec2 noise_uv = vec2(perp * 6.0 + u_seed * 0.07, move_t * 3.0);
    float noise = fbm(noise_uv);

    // Jagged offset: noise only RECEDES the front (never advances it).
    float jag = u_jaggedness * 0.05;
    float front = move_t - noise * jag;

    // Signed distance: positive = ahead of front (old), negative = behind (burned)
    float sd = axis - front;

    // --- Zone widths (very thin) ---
    float glow_half = 0.005 + u_glow_intensity * 0.006;  // ~5-11px at 1080p
    float char_w    = 0.008 + u_char_width * 0.022;

    // Smooth fade-out near completion so the last pixels don't pop
    float tail_fade = smoothstep(0.90, 1.0, move_t);

    // Thermite brightness multiplier: peaks during ignition, stays high
    float thermite = mix(1.4, 1.0, smoothstep(0.0, 0.15, move_t));
    thermite *= glow_buildup;  // ramp up from 0 during ignition

    vec3 out_rgb;

    if (sd > glow_half) {
        // Unburned — old image
        out_rgb = old_col.rgb;

    } else if (sd > 0.0) {
        // Approaching glow — warm tint bleeding into old image
        float f = 1.0 - sd / glow_half;
        f = f * f;
        vec3 warm_tint = mix(u_glow_color.rgb, vec3(1.0, 0.95, 0.8), 0.3);
        vec3 warm = mix(old_col.rgb, warm_tint, f * 0.5 * u_glow_intensity * thermite);
        out_rgb = warm;

    } else if (sd > -glow_half) {
        // Burn line core — thermite white-hot center
        float f = 1.0 - (-sd) / glow_half;  // 1 at front, 0 at edge
        f = f * f;
        // Thermite: white-hot core with orange fringe
        vec3 white_hot = vec3(1.0, 0.98, 0.9);
        vec3 hot = mix(u_glow_color.rgb, white_hot, f * 0.9);
        // Boost beyond 1.0 for HDR-like bloom (clamped at output)
        float intensity = u_glow_intensity * thermite * (0.8 + f * 0.5);
        out_rgb = mix(new_col.rgb, hot, min(intensity, 1.0));
        // Additive bloom for thermite brightness
        out_rgb += hot * max(0.0, intensity - 1.0) * 0.4;

    } else if (sd > -(glow_half + char_w)) {
        // Char zone — dark residue fading to new image
        float behind = (-sd) - glow_half;
        float ct = smoothstep(0.0, 1.0, behind / char_w);
        float dark = mix(0.06, 1.0, ct);
        vec3 charred = new_col.rgb * dark;
        // Faint ember at boundary
        float ember = (1.0 - ct) * 0.3 * u_glow_intensity * thermite;
        charred += u_glow_color.rgb * ember;
        out_rgb = charred;

    } else {
        // Fully burned — new image
        out_rgb = new_col.rgb;
    }

    // --- Optional sparks (reuses u_smoke_enabled as spark toggle) ---
    if (u_smoke_enabled == 1 && move_t > 0.0 && move_t < 0.95) {
        // Scatter sparks near the burn front
        float spark_zone = glow_half * 6.0;
        if (abs(sd) < spark_zone) {
            // Grid of potential spark positions
            vec2 spark_cell = floor(uv * vec2(80.0, 40.0));
            float rnd = spark_hash(spark_cell, u_seed + floor(u_time * 8.0));
            // Only ~8% of cells have a spark at any moment
            if (rnd > 0.92) {
                float spark_life = fract(rnd * 17.3 + u_time * 3.0);
                float spark_bright = (1.0 - spark_life) * (1.0 - spark_life);
                // Sparks closer to front are brighter
                float proximity = 1.0 - abs(sd) / spark_zone;
                proximity = proximity * proximity;
                float spark_intensity = spark_bright * proximity * u_glow_intensity * thermite * u_smoke_density * 2.0;
                vec3 spark_col = mix(u_glow_color.rgb, vec3(1.0, 1.0, 0.9), spark_bright * 0.7);
                out_rgb += spark_col * spark_intensity * 0.6;
            }
        }
    }

    // Near completion: lerp everything toward new image to guarantee clean end
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
