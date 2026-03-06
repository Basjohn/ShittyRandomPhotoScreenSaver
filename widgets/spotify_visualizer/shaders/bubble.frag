#version 330 core

in vec2 v_uv;
out vec4 fragColor;

// --- Card / overlay ---
uniform vec2 u_resolution;
uniform float u_dpr;
uniform float u_border_width;
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
// x = specular_size_factor, y = rotation (reserved), z = spec_ox, w = spec_oy
uniform vec4 u_bubbles_extra[110];
// Trail: 3 previous (x,y,strength) samples per bubble, oldest first
uniform vec3 u_bubbles_trail[330];  // 110 * 3
uniform float u_trail_strength;     // 0.0 = off, 1.0 = full
uniform float u_tail_opacity;       // max opacity ceiling for tail gradient (0.0-0.85)

// --- Styling ---
uniform vec2 u_specular_dir;       // normalised direction to light source
uniform vec2 u_gradient_dir;       // gradient direction (light -> dark)
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

    // Card border matches the widget card frame thickness (global control).
    float border_w = max(1.0, u_border_width);
    float card_radius = 8.0;
    // Inner content radius = card radius minus border width
    float inner_radius = max(0.0, card_radius - border_w);

    float inner_w = width - border_w * 2.0;
    float inner_h = height - border_w * 2.0;
    if (inner_w <= 0.0 || inner_h <= 0.0) discard;

    // Map v_uv (0..1 over full overlay) to pixel coords, then to inner UV
    float dpr = max(u_dpr, 1.0);
    float fb_h = height * dpr;
    vec2 fc = vec2(gl_FragCoord.x / dpr, (fb_h - gl_FragCoord.y) / dpr);

    // Discard outside inner content rect (rectangular pre-check)
    if (fc.x < border_w || fc.x > width - border_w ||
        fc.y < border_w || fc.y > height - border_w) {
        discard;
    }

    // Rounded-rect SDF discard: discard pixels in the corner radius zone
    // that fall outside the rounded inner rect
    if (inner_radius > 0.5) {
        // Position relative to inner rect origin
        float ix = fc.x - border_w;
        float iy = fc.y - border_w;
        // Check each corner
        float r = inner_radius;
        vec2 d = vec2(0.0);
        bool in_corner = false;
        if (ix < r && iy < r) { d = vec2(r - ix, r - iy); in_corner = true; }
        else if (ix > inner_w - r && iy < r) { d = vec2(ix - (inner_w - r), r - iy); in_corner = true; }
        else if (ix < r && iy > inner_h - r) { d = vec2(r - ix, iy - (inner_h - r)); in_corner = true; }
        else if (ix > inner_w - r && iy > inner_h - r) { d = vec2(ix - (inner_w - r), iy - (inner_h - r)); in_corner = true; }
        if (in_corner && (d.x * d.x + d.y * d.y) > r * r) discard;
    }

    // Remap to 0..1 within inner rect
    vec2 uv = vec2((fc.x - border_w) / inner_w, (fc.y - border_w) / inner_h);
    float aspect = inner_w / max(inner_h, 1.0);
    
    // Pixel size in normalised coords (for anti-aliasing)
    float px = 1.0 / max(inner_h, 1.0);
    
    // --- Background gradient ---
    // Gradient direction follows dedicated control.
    // Special: (0,0) = center-out radial gradient (light at center, dark at edges).
    vec2 center = vec2(0.5, 0.5);
    vec2 grad_dir = u_gradient_dir;
    float grad_t;
    if (length(grad_dir) < 0.001) {
        // Center-out radial: dark at center, light at edges.
        // Gentle power-curve falloff so the transition feels smooth.
        float radial_dist = length(uv - center);
        float norm = clamp(radial_dist / 0.85, 0.0, 1.0);
        grad_t = pow(norm, 1.65);
    } else {
        grad_t = dot(uv - center, -grad_dir) + 0.5;
        grad_t = clamp(grad_t, 0.0, 1.0);
    }
    
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

    // --- Water ripple wake trail behind each moving bubble ---
    // Each bubble's 3 trail samples become ripple source points at
    // different ages. At each source we draw concentric expanding rings
    // using sin(dist * freq) modulated by a Gaussian decay envelope.
    // Oldest sample = largest rings, most faded.  Newest = tightest, strongest.
    // The result is a subtle watery wake behind moving bubbles.
    if (u_trail_strength > 0.001 && u_tail_opacity > 0.001) {
        float trail_strength = clamp(u_trail_strength, 0.0, 1.5);
        float opacity_cap = clamp(u_tail_opacity, 0.0, 0.85);
        vec2 uv_aspect = vec2(uv.x * aspect, uv.y);

        // Ripple ring parameters
        float ring_freq = 220.0;          // spatial frequency of concentric rings
        float ring_thickness = 0.38;      // how sharp the rings are (0=needle, 1=solid)
        float max_ripple_radius = 0.12;   // max distance ripples extend (normalised)

        for (int i = 0; i < count; i++) {
            vec4 bpos = u_bubbles_pos[i];
            float brad = bpos.z;
            float balpha = bpos.w;
            if (balpha < 0.01 || brad < 2.0 * px) continue;

            // Process each of the 3 trail samples as a ripple source
            // age_factor: 0=oldest (most expanded/faded), 2=newest (tightest)
            for (int s = 0; s < 3; s++) {
                vec3 sample_data = u_bubbles_trail[i * 3 + s];
                float strength = sample_data.z;
                if (strength < 0.001) continue;

                vec2 src = vec2(sample_data.x * aspect, sample_data.y);
                vec2 delta = uv_aspect - src;
                float dist = length(delta);

                // Age determines how far the ripples have expanded:
                // oldest sample (s=0) → age 1.0, newest (s=2) → age 0.15
                float age = mix(1.0, 0.15, float(s) / 2.0);

                // Ripple radius grows with age; scale with bubble size
                float ripple_r = brad * (2.0 + age * 6.0) * trail_strength;
                ripple_r = min(ripple_r, max_ripple_radius);

                // Skip fragments outside the ripple radius (+ soft edge margin)
                if (dist > ripple_r + 2.0 * px) continue;

                // Concentric ring pattern: sin wave creates rings
                float wave = sin(dist * ring_freq - age * 12.0);
                // Sharpen the wave into thin rings
                float ring = smoothstep(1.0 - ring_thickness, 1.0, wave);

                // Gaussian decay: rings fade with distance from source
                float sigma = ripple_r * 0.45;
                float decay = exp(-(dist * dist) / (2.0 * sigma * sigma));

                // Fade out at the very centre (avoid bright dot on top of bubble)
                float centre_fade = smoothstep(brad * 0.3, brad * 0.9, dist);

                // Outer edge fade
                float edge_fade = 1.0 - smoothstep(ripple_r * 0.7, ripple_r, dist);

                // Older ripples are fainter
                float age_fade = mix(0.25, 1.0, float(s) / 2.0);

                float ripple_alpha = ring * decay * centre_fade * edge_fade
                                   * age_fade * strength * balpha
                                   * trail_strength * opacity_cap;
                if (ripple_alpha <= 0.001) continue;

                // Subtle watery colour: mostly outline, slightly brightened
                vec3 ripple_rgb = mix(outline_col.rgb, vec3(1.0), 0.3 + dist / ripple_r * 0.15);

                float blend = clamp(ripple_alpha * u_fade * 0.55, 0.0, opacity_cap * 0.5);
                result.rgb = mix(result.rgb, ripple_rgb, blend);
                result.a = max(result.a, blend * 0.4);
            }
        }
    }

    for (int i = 0; i < count; i++) {
        vec4 bpos = u_bubbles_pos[i];
        vec2 bxy = bpos.xy;       // bubble center (normalised 0..1)
        float brad = bpos.z;      // bubble radius (normalised to card height)
        float balpha = bpos.w;    // bubble alpha (1.0 normal, <1.0 fading/popping)
        
        if (balpha < 0.01) continue;
        
        float spec_size_factor = u_bubbles_extra[i].x;
        float spec_ox = u_bubbles_extra[i].z;
        float spec_oy = u_bubbles_extra[i].w;
        
        // Distance from fragment to bubble center (aspect-corrected)
        vec2 delta = uv - bxy;
        delta.x *= aspect;
        float dist = length(delta);
        
        // Radius in aspect-corrected space
        float r = brad;
        
        // Stroke width scales proportionally to bubble radius
        // Reference: 1.2px at radius 0.04 (mid-range big bubble)
        float ref_radius = 0.04;
        float base_stroke_px = 1.2;
        float stroke_px = base_stroke_px * (r / ref_radius);
        stroke_px = clamp(stroke_px, 0.5, 1.8);
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
        // Offset from bubble center toward light source, with per-bubble mutation
        float spec_offset = r * 0.35;
        vec2 spec_center = bxy + vec2(u_specular_dir.x / aspect, -u_specular_dir.y) * spec_offset
                         + vec2(spec_ox * r, spec_oy * r);
        
        vec2 spec_delta = uv - spec_center;
        spec_delta.x *= aspect;
        float spec_dist = length(spec_delta);
        
        // Specular radius scales with bubble radius and pulse
        float spec_r = r * 0.18 * spec_size_factor;
        
        // Crescent shape: elongate in the light direction for larger bubbles
        // For the crescent effect, use an ellipse stretched perpendicular to light
        // Use aspect-corrected direction matching spec_delta coordinate space
        vec2 adj_dir = vec2(u_specular_dir.x * aspect, -u_specular_dir.y);
        vec2 spec_dir_norm = normalize(adj_dir);
        vec2 spec_perp = vec2(-spec_dir_norm.y, spec_dir_norm.x);
        
        // Project delta onto light dir and perpendicular
        float d_along = dot(spec_delta, spec_dir_norm);
        float d_perp = dot(spec_delta, spec_perp);
        
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
