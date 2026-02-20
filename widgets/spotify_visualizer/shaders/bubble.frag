#version 330 core

in vec2 v_uv;
out vec4 fragColor;

// --- Card / overlay ---
uniform vec2 u_resolution;
uniform float u_dpr;
uniform float u_fade;
uniform float u_time;
uniform float u_playing;

// --- Energy bands ---
uniform float u_overall_energy;
uniform float u_bass_energy;
uniform float u_mid_energy;
uniform float u_high_energy;

// --- Bubble data (max 110 bubbles) ---
// xy = normalised position (0..1), z = radius (normalised), w = alpha
uniform int u_bubble_count;
uniform vec4 u_bubbles_pos[110];
// x = specular_size_factor, y = rotation (unused in SDF but reserved)
uniform vec2 u_bubbles_extra[110];

// --- Styling ---
uniform vec2 u_specular_dir;       // normalised direction to light source
uniform vec4 u_outline_color;      // bubble outline colour (RGBA 0-1)
uniform vec4 u_specular_color;     // specular highlight colour
uniform vec4 u_gradient_light;     // gradient light end
uniform vec4 u_gradient_dark;      // gradient dark end
uniform vec4 u_pop_color;          // pop flash colour
uniform float u_rainbow_hue_offset;

// =====================================================================
// Helpers
// =====================================================================

vec3 rgb2hsv(vec3 c) {
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

vec3 apply_rainbow(vec3 rgb, float hue_offset) {
    if (hue_offset < 0.001) return rgb;
    vec3 hsv = rgb2hsv(rgb);
    hsv.x = fract(hsv.x + hue_offset);
    return hsv2rgb(hsv);
}

// =====================================================================
// Main
// =====================================================================

void main() {
    float width = u_resolution.x;
    float height = u_resolution.y;
    if (width <= 0.0 || height <= 0.0) discard;

    // Card margins — keep bubble content inside the card border
    float margin_x = 8.0;
    float margin_y = 6.0;
    float inner_w = width - margin_x * 2.0;
    float inner_h = height - margin_y * 2.0;
    if (inner_w <= 0.0 || inner_h <= 0.0) discard;

    // Map v_uv (0..1 over full overlay) to pixel coords, then to inner UV
    float dpr = max(u_dpr, 1.0);
    float fb_h = height * dpr;
    vec2 fc = vec2(gl_FragCoord.x / dpr, (fb_h - gl_FragCoord.y) / dpr);

    // Discard outside inner card rect
    if (fc.x < margin_x || fc.x > width - margin_x ||
        fc.y < margin_y || fc.y > height - margin_y) {
        discard;
    }

    // Remap to 0..1 within inner rect
    vec2 uv = vec2((fc.x - margin_x) / inner_w, (fc.y - margin_y) / inner_h);
    float aspect = inner_w / max(inner_h, 1.0);
    
    // Pixel size in normalised coords (for anti-aliasing)
    float px = 1.0 / max(inner_h, 1.0);
    
    // --- Background gradient ---
    // Gradient direction follows specular direction: lightest where light is,
    // darkest opposite. u_specular_dir is normalised (e.g. (-0.707, 0.707) for top-left).
    // Project UV onto specular direction to get gradient factor.
    vec2 center = vec2(0.5, 0.5);
    float grad_t = dot(uv - center, -u_specular_dir) + 0.5;
    grad_t = clamp(grad_t, 0.0, 1.0);
    
    vec4 bg_light = u_gradient_light;
    vec4 bg_dark = u_gradient_dark;
    
    // Apply rainbow hue shift to gradient
    bg_light.rgb = apply_rainbow(bg_light.rgb, u_rainbow_hue_offset);
    bg_dark.rgb = apply_rainbow(bg_dark.rgb, u_rainbow_hue_offset);
    
    vec4 bg = mix(bg_dark, bg_light, grad_t);
    
    // --- Accumulate bubble contributions ---
    vec4 result = bg;
    
    // Outline and specular colours (with rainbow)
    vec4 outline_col = u_outline_color;
    outline_col.rgb = apply_rainbow(outline_col.rgb, u_rainbow_hue_offset);
    vec4 spec_col = u_specular_color;
    spec_col.rgb = apply_rainbow(spec_col.rgb, u_rainbow_hue_offset);
    vec4 pop_col = u_pop_color;
    pop_col.rgb = apply_rainbow(pop_col.rgb, u_rainbow_hue_offset);
    
    int count = min(u_bubble_count, 110);
    
    for (int i = 0; i < count; i++) {
        vec4 bpos = u_bubbles_pos[i];
        vec2 bxy = bpos.xy;       // bubble center (normalised 0..1)
        float brad = bpos.z;      // bubble radius (normalised to card height)
        float balpha = bpos.w;    // bubble alpha (1.0 normal, <1.0 fading/popping)
        
        if (balpha < 0.01) continue;
        
        float spec_size_factor = u_bubbles_extra[i].x;
        
        // Distance from fragment to bubble center (aspect-corrected)
        vec2 delta = uv - bxy;
        delta.x *= aspect;
        float dist = length(delta);
        
        // Radius in aspect-corrected space
        float r = brad;
        
        // Pixel-size stroke width: ~1.5px for big bubbles, ~1.0px for small
        float stroke_px = mix(1.0, 1.5, smoothstep(0.01, 0.04, r));
        float stroke = stroke_px * px;
        
        // --- Tiny bubble shortcut (< ~4px radius) ---
        float tiny_threshold = 4.0 * px;
        if (r < tiny_threshold) {
            // Simple filled dot
            float dot_alpha = smoothstep(r + px, r - px, dist) * balpha;
            // Pop flash: tint with pop colour when fading
            vec4 dot_col = (balpha < 0.9) ? pop_col : outline_col;
            result = mix(result, dot_col, dot_alpha * u_fade);
            continue;
        }
        
        // --- Outline ring (SDF) ---
        float ring_dist = abs(dist - r);
        float ring_alpha = smoothstep(stroke + px, stroke - px * 0.5, ring_dist);
        ring_alpha *= balpha;
        
        // Pop flash: when alpha < 0.9, bubble is popping — tint outline
        vec4 ring_col = (balpha < 0.9) ? mix(outline_col, pop_col, 1.0 - balpha) : outline_col;
        result = mix(result, ring_col, ring_alpha * u_fade);
        
        // --- Specular highlight (small filled ellipse) ---
        // Offset from bubble center toward light source
        float spec_offset = r * 0.35;
        vec2 spec_center = bxy + vec2(-u_specular_dir.x / aspect, -u_specular_dir.y) * spec_offset;
        
        vec2 spec_delta = uv - spec_center;
        spec_delta.x *= aspect;
        float spec_dist = length(spec_delta);
        
        // Specular radius scales with bubble radius and pulse
        float spec_r = r * 0.18 * spec_size_factor;
        
        // Crescent shape: elongate in the light direction for larger bubbles
        // For the crescent effect, use an ellipse stretched perpendicular to light
        vec2 spec_dir_norm = normalize(u_specular_dir);
        vec2 spec_perp = vec2(-spec_dir_norm.y, spec_dir_norm.x);
        
        // Project delta onto light dir and perpendicular
        float d_along = dot(spec_delta, vec2(-spec_dir_norm.x, -spec_dir_norm.y));
        float d_perp = dot(spec_delta, vec2(-spec_perp.x, -spec_perp.y));
        
        // Elliptical distance (stretched along perpendicular for crescent look)
        float crescent_stretch = mix(1.0, 1.6, smoothstep(0.02, 0.06, r));
        float spec_ell_dist = sqrt(d_along * d_along + (d_perp * d_perp) / (crescent_stretch * crescent_stretch));
        
        float spec_alpha = smoothstep(spec_r + px, spec_r - px * 0.5, spec_ell_dist);
        // Only draw specular inside the bubble
        spec_alpha *= smoothstep(r + px, r - px, dist);
        spec_alpha *= balpha;
        
        result = mix(result, spec_col, spec_alpha * u_fade);
    }
    
    // Final alpha
    result.a *= u_fade;
    
    fragColor = result;
}
