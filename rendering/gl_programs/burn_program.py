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
uniform int   u_direction;      // 0=L→R, 1=R→L, 2=T→B, 3=B→T, 4=center→out
uniform float u_jaggedness;     // 0.0–1.0  edge noise amplitude
uniform float u_glow_intensity; // 0.0–1.0
uniform vec4  u_glow_color;     // RGBA primary glow colour
uniform float u_char_width;     // 0.1–1.0 normalised char zone width
uniform int   u_smoke_enabled;  // 1=on
uniform float u_smoke_density;  // 0.0–1.0
uniform int   u_ash_enabled;    // 1=on
uniform float u_ash_density;    // 0.0–1.0
uniform float u_time;           // wall-clock seconds for animation
uniform float u_seed;           // per-transition random seed

// -----------------------------------------------------------------------
// Hash / noise helpers
// -----------------------------------------------------------------------
float hash11(float p) {
    p = fract(p * 0.1031);
    p *= p + 33.33;
    p *= p + p;
    return fract(p);
}

float hash21(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
    vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
    p3 += dot(p3, p3.yzx + 33.33);
    return fract((p3.xx + p3.yz) * p3.zy);
}

// Value noise 2D
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

// 3-octave FBM
float fbm(vec2 p) {
    float v = 0.0;
    float a = 0.5;
    for (int i = 0; i < 3; i++) {
        v += a * vnoise(p);
        p  = p * 2.1 + vec2(1.7, 9.2);
        a *= 0.5;
    }
    return v;
}

// -----------------------------------------------------------------------
// Axis: maps UV → 0..1 progress coordinate for the chosen direction
// -----------------------------------------------------------------------
float burn_axis(vec2 uv) {
    if (u_direction == 0) return uv.x;               // L→R
    if (u_direction == 1) return 1.0 - uv.x;         // R→L
    if (u_direction == 2) return uv.y;               // T→B
    if (u_direction == 3) return 1.0 - uv.y;         // B→T
    // center→out: radial distance from 0.5,0.5 scaled so corners = 1.0
    vec2 d = abs(uv - 0.5) * 1.4142;
    return max(d.x, d.y);
}

// -----------------------------------------------------------------------
// Smoke puffs (Gaussian blobs near burn front)
// -----------------------------------------------------------------------
float smoke_contribution(vec2 uv, float front_axis, float axis_val) {
    if (u_smoke_enabled == 0) return 0.0;

    // Only evaluate within a narrow band behind the burn front
    float behind = front_axis - axis_val;
    if (behind < 0.0 || behind > 0.18) return 0.0;

    float total = 0.0;
    const int PUFFS = 24;
    for (int i = 0; i < PUFFS; i++) {
        float fi = float(i);
        // Seed puff position along the burn front
        float seed2 = u_seed + fi * 0.137;
        vec2 puff_uv_base;
        if (u_direction == 0 || u_direction == 1) {
            puff_uv_base = vec2(front_axis, hash11(seed2 * 3.7));
        } else if (u_direction == 2 || u_direction == 3) {
            puff_uv_base = vec2(hash11(seed2 * 3.7), front_axis);
        } else {
            vec2 rnd = hash22(vec2(seed2, seed2 * 1.3));
            puff_uv_base = vec2(0.5) + (rnd - 0.5) * 0.8;
        }

        // Drift upward (opposite to burn direction) over time
        float lifetime = hash11(seed2 * 7.3) * 2.0 + 0.5;
        float age = mod(u_time * 0.4 + hash11(seed2 * 2.1) * lifetime, lifetime);
        float drift = age / lifetime;

        vec2 drift_dir;
        if (u_direction == 0) drift_dir = vec2(-1.0,  0.0);
        else if (u_direction == 1) drift_dir = vec2( 1.0,  0.0);
        else if (u_direction == 2) drift_dir = vec2( 0.0, -1.0);
        else if (u_direction == 3) drift_dir = vec2( 0.0,  1.0);
        else drift_dir = vec2(0.0, -1.0);

        vec2 puff_pos = puff_uv_base + drift_dir * drift * 0.12;
        // Lateral wobble
        puff_pos += vec2(sin(u_time * 1.3 + fi), cos(u_time * 0.9 + fi)) * 0.008;

        float sigma = (0.025 + hash11(seed2 * 5.1) * 0.02) * (1.0 + drift * 1.5);
        float dist2 = dot(uv - puff_pos, uv - puff_pos);
        float alpha = exp(-dist2 / (sigma * sigma));
        alpha *= (1.0 - drift);  // fade out over lifetime
        total += alpha;
    }
    return clamp(total * u_smoke_density * 0.35, 0.0, 0.6);
}

// -----------------------------------------------------------------------
// Ash specks (tiny bright dots falling from burn front)
// -----------------------------------------------------------------------
float ash_contribution(vec2 uv, float front_axis, float axis_val) {
    if (u_ash_enabled == 0) return 0.0;

    float behind = front_axis - axis_val;
    if (behind < 0.0 || behind > 0.30) return 0.0;

    float total = 0.0;
    const int SPECKS = 30;
    for (int i = 0; i < SPECKS; i++) {
        float fi = float(i);
        float seed2 = u_seed + fi * 0.271 + 100.0;

        vec2 speck_base;
        if (u_direction == 0 || u_direction == 1) {
            speck_base = vec2(front_axis, hash11(seed2 * 4.1));
        } else if (u_direction == 2 || u_direction == 3) {
            speck_base = vec2(hash11(seed2 * 4.1), front_axis);
        } else {
            vec2 rnd = hash22(vec2(seed2, seed2 * 1.7));
            speck_base = vec2(0.5) + (rnd - 0.5) * 0.9;
        }

        float lifetime = hash11(seed2 * 3.3) * 1.5 + 0.5;
        float age = mod(u_time * 0.6 + hash11(seed2 * 1.9) * lifetime, lifetime);
        float drift = age / lifetime;

        // Ash falls downward with slight lateral drift
        vec2 fall_dir = vec2(
            (hash11(seed2 * 6.7) - 0.5) * 0.06,
            0.12
        );
        vec2 speck_pos = speck_base + fall_dir * drift;

        float dist = length(uv - speck_pos);
        float r = 0.003 + hash11(seed2 * 2.9) * 0.003;
        float alpha = smoothstep(r, 0.0, dist);
        alpha *= (1.0 - drift * 0.8);
        total += alpha;
    }
    return clamp(total * u_ash_density * 0.9, 0.0, 1.0);
}

// -----------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------
void main() {
    vec2 uv = vec2(vUv.x, 1.0 - vUv.y);

    float t = clamp(u_progress, 0.0, 1.0);

    // Hard guarantees at boundaries
    if (t <= 0.0) { FragColor = texture(uOldTex, uv); return; }
    if (t >= 1.0) { FragColor = texture(uNewTex, uv); return; }

    vec4 old_color = texture(uOldTex, uv);
    vec4 new_color = texture(uNewTex, uv);

    // Compute axis value for this pixel
    float axis_val = burn_axis(uv);

    // Noise-displaced burn front
    // The noise coordinates evolve with progress so the edge shape changes as it burns
    vec2 noise_uv = uv * 4.5 + vec2(u_seed * 0.1, t * 0.4);
    float noise_val = fbm(noise_uv);

    // Effective jaggedness amplitude (max ~15% of screen width)
    float jag = u_jaggedness * 0.15;
    float front = t - noise_val * jag;

    // Signed distance from burn front: positive = revealed (new image side)
    float dist = axis_val - front;

    // Zone widths (normalised to screen axis)
    float glow_w = 0.04 + u_glow_intensity * 0.03;
    float char_w = u_char_width * 0.06;

    vec4 out_color;

    if (dist > 0.0) {
        // New image zone
        out_color = new_color;
    } else if (dist > -glow_w) {
        // Glow zone: warm incandescent edge
        float glow_t = 1.0 - (-dist / glow_w);  // 1.0 at edge, 0.0 at glow_w
        float glow_falloff = exp(-(-dist / glow_w) * 3.0);
        vec3 glow_rgb = u_glow_color.rgb * u_glow_intensity * glow_falloff;
        // Blend: at the very edge, mostly glow; further in, mix with old image
        out_color = vec4(mix(old_color.rgb, glow_rgb, glow_falloff * glow_t), 1.0);
    } else if (dist > -(glow_w + char_w)) {
        // Char zone: old image darkens to near-black
        float char_t = (-dist - glow_w) / char_w;  // 0 at glow boundary, 1 at char end
        char_t = smoothstep(0.0, 1.0, char_t);
        vec3 char_color = mix(old_color.rgb * 0.3, vec3(0.01, 0.005, 0.0), char_t);
        // Add faint orange ember glow at char/glow boundary
        float ember = (1.0 - char_t) * 0.25 * u_glow_intensity;
        char_color += u_glow_color.rgb * ember;
        out_color = vec4(char_color, 1.0);
    } else {
        // Old image zone
        out_color = old_color;
    }

    // Smoke overlay (grey-white puffs behind burn front)
    float smoke = smoke_contribution(uv, front, axis_val);
    if (smoke > 0.001) {
        vec3 smoke_color = vec3(0.75, 0.72, 0.70);
        out_color.rgb = mix(out_color.rgb, smoke_color, smoke);
    }

    // Ash overlay (bright orange-to-dark specks falling from burn front)
    float ash = ash_contribution(uv, front, axis_val);
    if (ash > 0.001) {
        // Ash colour: bright orange near front, fades to dark
        float behind = front - axis_val;
        float ash_fade = clamp(behind / 0.30, 0.0, 1.0);
        vec3 ash_color = mix(vec3(1.0, 0.55, 0.1), vec3(0.05, 0.02, 0.0), ash_fade);
        out_color.rgb = mix(out_color.rgb, ash_color, ash);
    }

    FragColor = out_color;
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
