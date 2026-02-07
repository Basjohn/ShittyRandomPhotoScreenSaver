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
uniform float u_overall_energy;

// Starfield configuration
uniform float u_star_density;
uniform float u_travel_speed;
uniform float u_star_reactivity;

// Based on "Star Nest" by Kali (https://www.shadertoy.com/view/4dfGDM)
// Adapted for small card resolution and audio reactivity.

const int VOLSTEPS = 8;
const int ITERATIONS = 10;
const float FORMUPARAM = 0.53;
const float STEPSIZE = 0.19;
const float TILE = 0.85;

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

    // Normalised UV within the card
    vec2 uv = vec2(
        (fc.x - margin_x) / inner_width - 0.5,
        (fc.y - margin_y) / inner_height - 0.5
    );
    // Correct aspect ratio
    uv.x *= inner_width / inner_height;

    // Audio-reactive speed
    float speed = u_travel_speed + u_bass_energy * u_star_reactivity * 3.0;

    // Camera direction — travel along Z
    vec3 dir = vec3(uv * 1.8, 1.0);
    dir = normalize(dir);

    float time_val = u_time * speed * 0.15;

    vec3 from = vec3(0.0, 0.0, time_val);
    // Slight drift
    from.x += sin(time_val * 0.3) * 0.3;
    from.y += cos(time_val * 0.2) * 0.2;

    // Density parameter affected by u_star_density
    float density = u_star_density;

    // Volumetric rendering
    float s = 0.1;
    float fade_vol = 1.0;
    vec3 v_col = vec3(0.0);

    for (int r = 0; r < VOLSTEPS; r++) {
        vec3 p = from + s * dir * 0.5;

        // Tiling
        p = abs(vec3(TILE) - mod(p, vec3(TILE * 2.0)));

        float pa = 0.0;
        float a = 0.0;
        for (int i = 0; i < ITERATIONS; i++) {
            p = abs(p) / dot(p, p) - FORMUPARAM;
            float d = abs(length(p) - pa);
            a += d;
            pa = length(p);
        }

        // Star colouring
        a *= a * a;
        float dm = max(0.0, density - a * a * 0.001);

        if (r > 3) {
            fade_vol *= 1.0 - dm;
        }

        // Audio-reactive brightness
        float brightness = 0.6 + u_overall_energy * 0.8;

        v_col += vec3(s, s * s, s * s * s * s) * a * 0.00125 * fade_vol * brightness;

        s += STEPSIZE;
    }

    // Colour adjustment — slightly blue-shifted for a cool starfield look
    v_col = mix(v_col, vec3(length(v_col)) * vec3(0.7, 0.8, 1.0), 0.4);

    // Energy-reactive saturation boost
    v_col *= 1.0 + u_mid_energy * 0.5;

    // Tone mapping
    v_col = clamp(v_col, 0.0, 1.0);

    float alpha = max(v_col.r, max(v_col.g, v_col.b));
    alpha = clamp(alpha * 2.5, 0.0, 1.0);

    if (alpha <= 0.001) {
        discard;
    }

    fragColor = vec4(v_col, alpha * u_fade);
}
