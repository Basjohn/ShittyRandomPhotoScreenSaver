#version 460 core
// The conventions include (N1.4; spliced at the marker by the loader here and by the native core's bake): the fragment's
// pixel comes from fragPixel, never raw gl_FragCoord, so both renderers read it in their target's row convention.
#define SRPSS_CONVENTIONS_FRAGMENT
//@srpss_conventions
layout(location = 0) in vec2 v_uv;
layout(location = 0) out vec4 fragColor;

// Spectrum's pass block (N1.6): every value the renderer sets, one std140 block at the pass-block binding
// (SCENE3D_PASS_BLOCK_BINDING). The quad's vertex stage declares the same block, taken from this file
// (rendering.quick.visualizer.implementations.spectrum), and the renderer packs it from this declaration
// (rendering.gl_programs.portable.block_layout_from_glsl), so the stages and the packing never disagree.
layout(std140, binding = 18) uniform SpectrumDraw {
    mat4 uMatrix;                 // the quad: Qt's item matrix
    vec2 uItemSize;
    int uContentRotationQuarters;
    vec2 u_resolution;            // logical size in QWidget coordinates
    float u_dpr;                  // device pixel ratio of the backing FBO
    // Framebuffer-pixel origin of this visualizer's viewport. The fragment's pixel is WINDOW space, so when the compositor
    // draws the visualizer into the whole-display framebuffer at a non-zero viewport origin the raw value is not
    // card-local. Subtracting this origin restores card-local pixels. A card-sized, origin-zero target passes (0, 0).
    vec2 u_viewport_origin_px;
    // Qt Quick uses interpolated item-local coordinates. The old compositor keeps the framebuffer-coordinate branch
    // until Phase-I deletion.
    int u_quick_item_coords;
    // 1: item-local coordinates from the fragment's pixel (fragPixel) through the item's affine map (rows x and y of a
    // 2 x 3 matrix, resolved by the renderer from its matrix, viewport and rotation, R-197). One continuous coordinate
    // over the whole full-field quad: the interpolated v_uv is rounded differently in its two triangles, so a bar edge
    // on a pixel centre stepped by a pixel along their shared diagonal. 0: the interpolated v_uv (a matrix that is not
    // affine). The rows map the WINDOW's pixel: a target that is not the window (the native core's composite) first
    // rebuilds it through u_window_from_target (whole-pixel offsets and a sign: exact), so the bar, cap and peak
    // arithmetic runs in the Python renderer's own space and precision (N2.5). The Python renderer's target is the
    // window: identity rows.
    int u_item_from_frag;
    vec3 u_item_from_frag_x;
    vec3 u_item_from_frag_y;
    vec3 u_window_from_target_x;
    vec3 u_window_from_target_y;
    vec2 u_target_px;             // the render target's size in pixels (fragPixel's row convention)
    vec4 u_content_rect;          // item-local x, y, width, height
    float u_visual_scale;
    int u_bar_count;
    int u_segments;
    float u_bars[64];
    float u_peaks[64];
    vec4 u_fill_color;
    vec4 u_border_color;
    float u_fade;
    int u_playing;
    float u_ghost_alpha;
    float u_bar_height_scale;     // visual boost for taller cards (1.0 = default height)
    int u_single_piece;           // 1 = solid bars (no segment gaps)
    float u_border_radius;        // border radius in px (0 = square, ~6 = rounded)
    int u_spectrum_glow_enabled;
    float u_spectrum_glow_intensity;
    vec4 u_spectrum_glow_color;
    float u_rainbow_hue_offset;   // 0..1 hue rotation (0 = disabled)
    int u_rainbow_per_bar;        // 1 = unique colour per bar, 0 = single shifting colour
    int u_rainbow_fill;           // 1 = bar fill participates, 0 = preserve configured fill
    int u_rainbow_border;         // 1 = borders participate in rainbow, 0 = borders keep base colour
    int u_rainbow_ghost;          // independent spectral peak-trail colour
    float u_ghost_hue_offset;     // existing Spectrum animation clock, no independent timer
    float u_bars_left;
    float u_bar_width_px;
    float u_bar_gap_px;
    float u_bar_span_px;
    // Optional decoration (all default off: every branch is skipped at 0). Mixes are the presentation owner's fade
    // envelopes, so a toggled decoration fades instead of popping.
    float u_ghost_custom_mix;     // 0 = ghosts in the border colour, 1 = the custom ghost colour
    vec4 u_ghost_color;
    float u_ghost_fill_mix;       // 0 = the colour above, 1 = Bar Fill: the bar's own fill surface under the ghost
    float u_ghost_gradient_mix;   // ghost shades toward the tip colour at the peak
    vec4 u_ghost_tip_color;
    float u_gloss;                // glassy highlight across each bar
    float u_fill_gradient_mix;    // fill shades toward the tip colour at the top of the field
    vec4 u_fill_tip_color;
    float u_peak_cap_mix;
    vec4 u_peak_cap_color;
    float u_peak_cap_thickness;   // item px
    int u_pattern;                // SPECTRUM_PATTERNS index (0 = Off)
    int u_pattern_shared;         // 1 = one sheet over the whole bar field (SPECTRUM_PATTERN_ANCHORS "Shared")
    float u_pattern_mix;          // strength x fade
    vec4 u_pattern_color;
    float u_pattern_scale;
    float u_time;                 // Spectrum's animation clock (seconds); only the flag sheets' wave reads it
};

// One framebuffer pixel in item coordinates, taken where control flow is still uniform (before any discard), so
// the decoration's filters never see the derivative jumps at bar and segment boundaries.
float g_px_x = 1.0;
float g_px_y = 1.0;
// Height of the bar field a bar can fill (0.95 of the inner height): the flag sheets' vertical extent.
float g_field_h = 1.0;

// SPECTRUM_PATTERNS from this index are flag sheets: one flag laid over the whole bar field in its own colours.
const int FLAG_FIRST = 7;

// Apply rainbow hue shift to a colour. Returns the shifted colour.
// Called from both single-piece and segmented code paths.
vec4 apply_spectrum_rainbow(vec4 col, int bidx) {
    if (u_rainbow_hue_offset <= 0.001) return col;
    // Per-bar: each bar gets a unique hue based on position + temporal rotation.
    // Uniform: all bars share the same temporally-shifting hue.
    float bar_frac = (u_rainbow_per_bar == 1)
        ? float(bidx) / max(float(u_bar_count - 1), 1.0)
        : 0.0;
    vec3 rc = col.rgb;
    float cmax = max(rc.r, max(rc.g, rc.b));
    float cmin = min(rc.r, min(rc.g, rc.b));
    float rb_d = cmax - cmin;
    float h = 0.0;
    if (rb_d > 0.0001) {
        if (cmax == rc.r) h = mod((rc.g - rc.b) / rb_d, 6.0);
        else if (cmax == rc.g) h = (rc.b - rc.r) / rb_d + 2.0;
        else h = (rc.r - rc.g) / rb_d + 4.0;
        h /= 6.0;
        if (h < 0.0) h += 1.0;
    }
    float s = (cmax > 0.0001) ? rb_d / cmax : 0.0;
    float v = cmax;
    if (s < 0.05 && v > 0.05) s = 1.0;
    h = fract(bar_frac + u_rainbow_hue_offset);
    float c = v * s;
    float rb_x = c * (1.0 - abs(mod(h * 6.0, 2.0) - 1.0));
    float m = v - c;
    vec3 rgb;
    if      (h < 1.0/6.0) rgb = vec3(c, rb_x, 0.0);
    else if (h < 2.0/6.0) rgb = vec3(rb_x, c, 0.0);
    else if (h < 3.0/6.0) rgb = vec3(0.0, c, rb_x);
    else if (h < 4.0/6.0) rgb = vec3(0.0, rb_x, c);
    else if (h < 5.0/6.0) rgb = vec3(rb_x, 0.0, c);
    else                  rgb = vec3(c, 0.0, rb_x);
    return vec4(rgb + m, col.a);
}

vec4 spectrum_ghost_colour(int bidx, float alpha) {
    if (u_rainbow_ghost != 1) {
        if (u_ghost_custom_mix <= 0.0) return vec4(u_border_color.rgb, alpha);
        // Custom ghost colour: its alpha scales Ghost Opacity.
        float k = clamp(u_ghost_custom_mix, 0.0, 1.0);
        return vec4(mix(u_border_color.rgb, u_ghost_color.rgb, k), alpha * mix(1.0, u_ghost_color.a, k));
    }
    // Independent per-bar spectral hue, even when the authored fill/border are black
    // or global Rainbow is off. This does not alter ordinary bar colour/alpha.
    float hue = fract(float(bidx) / max(float(u_bar_count - 1), 1.0) + u_ghost_hue_offset);
    vec3 rgb = clamp(abs(mod(hue * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return vec4(rgb, alpha);
}

vec3 spectrum_rgb2hsv(vec3 c) {
    vec4 k = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
    vec4 p = mix(vec4(c.bg, k.wz), vec4(c.gb, k.xy), step(c.b, c.g));
    vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
    float d = q.x - min(q.w, q.y);
    return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + 1e-10)), d / (q.x + 1e-10), q.x);
}

vec3 spectrum_hsv2rgb(vec3 c) {
    vec3 p = abs(fract(c.xxx + vec3(1.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
    return c.z * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

// A colour blend that keeps its saturation: hue turns along the shorter arc while saturation and value ramp, so green
// to red passes through yellow (an RGB mix passes through olive). A grey, white or black end takes the other end's hue.
vec3 spectrum_hue_mix(vec3 a, vec3 b, float t) {
    vec3 ha = spectrum_rgb2hsv(a);
    vec3 hb = spectrum_rgb2hsv(b);
    if (ha.y < 0.02) ha.x = hb.x;
    if (hb.y < 0.02) hb.x = ha.x;
    float dh = hb.x - ha.x;
    dh -= floor(dh + 0.5);
    return spectrum_hsv2rgb(vec3(fract(ha.x + dh * t), mix(ha.y, hb.y, t), mix(ha.z, hb.z, t)));
}

// Ghost Gradient: ``t`` runs 0 at the bar top to 1 at the peak; the tip colour's alpha sets how far it turns.
vec4 spectrum_ghost_tip(vec4 ghost, float t) {
    if (u_ghost_gradient_mix <= 0.0) return ghost;
    // sqrt: the trail fades toward its top, so the tip colour takes over early enough to read.
    float k = sqrt(clamp(t, 0.0, 1.0)) * clamp(u_ghost_gradient_mix, 0.0, 1.0)
              * clamp(u_ghost_tip_color.a, 0.0, 1.0);
    return vec4(spectrum_hue_mix(ghost.rgb, u_ghost_tip_color.rgb, k), ghost.a);
}

// Fill Gradient: ``h`` is the height in the bar field (0 base, 1 the tallest a bar reaches).
vec4 spectrum_fill_gradient(vec4 fill, float h) {
    if (u_fill_gradient_mix <= 0.0) return fill;
    vec4 tip = u_fill_tip_color;
    tip.a *= u_fade;
    float k = clamp(h, 0.0, 1.0) * clamp(u_fill_gradient_mix, 0.0, 1.0);
    return vec4(spectrum_hue_mix(fill.rgb, tip.rgb, k), mix(fill.a, tip.a, k));
}

// ---- Flag sheets ------------------------------------------------------------------------------------------------
// One flag over the whole bar field (``uv``: 0..1 across the field, 0 at the baseline to 1 at the field top), seen
// through the bars as they rise. ``px`` is one framebuffer pixel in uv units: every edge is box-filtered over it.

float spectrum_box_stripe(float t, float w, float d);           // defined with the patterns below

float flag_cover(float signed_distance, float pixel) {          // signed distance < 0 inside
    return clamp(0.5 - signed_distance / max(pixel, 1e-5), 0.0, 1.0);
}

// Inigo Quilez's five-point star (point up), ``r`` outer radius, ``rf`` inner/outer ratio.
float flag_star(vec2 p, float r, float rf) {
    const vec2 k1 = vec2(0.809016994375, -0.587785252292);
    const vec2 k2 = vec2(-k1.x, k1.y);
    p.x = abs(p.x);
    p -= 2.0 * max(dot(k1, p), 0.0) * k1;
    p -= 2.0 * max(dot(k2, p), 0.0) * k2;
    p.x = abs(p.x);
    p.y -= r;
    vec2 ba = rf * vec2(-k1.y, k1.x) - vec2(0.0, 1.0);
    float h = clamp(dot(p, ba) / dot(ba, ba), 0.0, r);
    return length(p - ba * h) * sign(p.y * ba.x - p.x * ba.y);
}

// Distance from ``p`` to the nearer diagonal of a ``w`` x ``h`` flag (a saltire's centre lines), in flag units.
float flag_saltire_distance(vec2 p, float w, float h) {
    float n = inversesqrt(w * w + h * h);
    return min(abs(p.x * h - p.y * w), abs(p.x * h + p.y * w - w * h)) * n;
}

vec3 flag_usa(vec2 uv, vec2 px) {
    vec3 red = vec3(0.698, 0.133, 0.204);
    vec3 blue = vec3(0.235, 0.231, 0.431);
    // Thirteen stripes, red at the top and the bottom.
    float s = (1.0 - uv.y) * 13.0;
    vec3 col = mix(vec3(1.0), red, spectrum_box_stripe(0.5 * s, 0.5 * 13.0 * px.y, 0.5));
    // The canton: the top seven stripes, 0.4 of the fly, with 50 stars in rows of six and five.
    float cw = 0.4;
    float ch = 7.0 / 13.0;
    float canton = clamp((cw - uv.x) / px.x + 0.5, 0.0, 1.0) * clamp((uv.y - (1.0 - ch)) / px.y + 0.5, 0.0, 1.0);
    if (canton <= 0.0) return col;
    vec2 lattice = vec2(uv.x / cw * 12.0, (uv.y - (1.0 - ch)) / ch * 10.0);
    vec2 centre = clamp(floor(lattice + 0.5), vec2(1.0), vec2(11.0, 9.0));
    vec3 field = blue;
    if (mod(centre.x + centre.y, 2.0) < 0.5) {
        vec2 cell_px = vec2(cw / 12.0 / px.x, ch / 10.0 / px.y);           // one lattice step in pixels
        vec2 p = (lattice - centre) * cell_px;
        float star = flag_star(p, 0.62 * min(cell_px.x, cell_px.y), 0.42);
        field = mix(blue, vec3(1.0), flag_cover(star, 1.0));
    }
    return mix(col, field, canton);
}

vec3 flag_japan(vec2 uv, vec2 px) {
    // A crimson disc three fifths of the height across, at the centre (round in pixels whatever the field's shape).
    vec2 p = (uv - 0.5) / px;
    float radius = 0.3 / px.y;
    return mix(vec3(1.0), vec3(0.737, 0.0, 0.176), flag_cover(length(p) - radius, 1.0));
}

vec3 flag_uk(vec2 uv, vec2 px) {
    vec3 blue = vec3(0.004, 0.129, 0.412);
    vec3 red = vec3(0.784, 0.063, 0.180);
    vec2 p = uv * vec2(2.0, 1.0);                     // the 1:2 flag, height 1
    float pix = max(px.x * 2.0, px.y);
    float diag = flag_saltire_distance(p, 2.0, 1.0);
    vec3 col = mix(blue, vec3(1.0), flag_cover(diag - 3.0 / 30.0, pix));
    col = mix(col, red, flag_cover(diag - 1.0 / 30.0, pix));
    float cross = min(abs(p.x - 1.0), abs(p.y - 0.5));
    col = mix(col, vec3(1.0), flag_cover(cross - 5.0 / 30.0, pix));
    return mix(col, red, flag_cover(cross - 3.0 / 30.0, pix));
}

vec3 flag_jamaica(vec2 uv, vec2 px) {
    vec2 p = uv * vec2(2.0, 1.0);
    float pix = max(px.x * 2.0, px.y);
    vec2 d = abs(p - vec2(1.0, 0.5));
    // Green triangles at the top and bottom, black at the hoist and the fly, split by the diagonals.
    vec3 col = mix(vec3(0.0), vec3(0.0, 0.608, 0.227), flag_cover((d.x * 1.0 - d.y * 2.0) * 0.4472, pix));
    return mix(col, vec3(0.996, 0.82, 0.0), flag_cover(flag_saltire_distance(p, 2.0, 1.0) - 0.085, pix));
}

vec3 flag_brazil(vec2 uv, vec2 px) {
    vec2 p = uv * vec2(20.0, 14.0);                   // the 10:7 flag in its own 20 x 14 units
    float pix = max(px.x * 20.0, px.y * 14.0);
    vec2 d = abs(p - vec2(10.0, 7.0));
    vec3 col = vec3(0.0, 0.612, 0.231);
    // The yellow rhombus, 1.7 units in from each edge; its distance scaled to flag units along its edge normal.
    float rhombus = (d.x / 8.3 + d.y / 5.3 - 1.0) * 4.49;
    col = mix(col, vec3(1.0, 0.875, 0.0), flag_cover(rhombus, pix));
    // The blue globe with its white band.
    float globe = length(p - vec2(10.0, 7.0)) - 3.5;
    vec3 sky = vec3(0.0, 0.153, 0.463);
    // The band: an arc between radii 8 and 8.5 centred 2 units left of the globe's vertical diameter, on the base.
    float band = abs(length(p - vec2(8.0, 0.0)) - 8.25) - 0.25;
    sky = mix(sky, vec3(1.0), flag_cover(band, pix));
    return mix(col, sky, flag_cover(globe, pix));
}

// The cloth: the hoist (left edge) stays put while folds travel toward the fly, shifting the flag's design a little
// and shading it light and dark across each fold.
vec3 spectrum_flag(vec2 uv, vec2 px) {
    float fly = clamp(uv.x, 0.0, 1.0);
    float phase = 6.2831853 * (1.15 * uv.x - 0.22 * u_time) + 2.0 * uv.y;
    vec2 waved = uv + vec2(0.0, 0.016 * fly * sin(phase));
    vec3 col;
    if (u_pattern == FLAG_FIRST) col = flag_usa(waved, px);
    else if (u_pattern == FLAG_FIRST + 1) col = flag_japan(waved, px);
    else if (u_pattern == FLAG_FIRST + 2) col = flag_uk(waved, px);
    else if (u_pattern == FLAG_FIRST + 3) col = flag_jamaica(waved, px);
    else col = flag_brazil(waved, px);
    return col * (1.0 + 0.11 * (0.3 + 0.7 * fly) * cos(phase));
}

// Box-filtered periodic stripes: the share of the pixel footprint [t - w/2, t + w/2] (in periods) lying on the
// 'on' part [0, d) of each period. Exact for any footprint, so a pattern finer than a pixel settles to its mean
// coverage instead of shimmering.
float spectrum_stripe_integral(float t, float d) {
    return floor(t) * d + min(fract(t), d);
}

float spectrum_box_stripe(float t, float w, float d) {
    w = max(w, 1e-4);
    return (spectrum_stripe_integral(t + 0.5 * w, d) - spectrum_stripe_integral(t - 0.5 * w, d)) / w;
}

// Pattern coverage (0..1) at bar-local x ``lx`` of a bar ``bw`` wide, height ``y`` above the baseline and field x
// ``fx``. Every pattern is fixed to the baseline (and to each bar's own width or the field), so moving bars only
// reveal more or less of it; columns fit a whole number into each bar so it reads at every bar width. Shared: the
// horizontal frame is the whole bar field (columns fitted across it, chevrons centred on it): one sheet running
// through bars and gaps alike, seen only through the fills.
float spectrum_pattern_coverage(float lx, float bw, float y, float fx, float scale) {
    if (u_pattern_shared == 1) {
        lx = fx;
        bw = u_bar_span_px;
    }
    float cell = 6.0 * scale * clamp(u_pattern_scale, 0.25, 4.0);
    if (u_pattern == 1) {                       // Horizontal Bands
        float period = 2.0 * cell;
        return spectrum_box_stripe(y / period, g_px_y / period, 0.5);
    }
    if (u_pattern == 2) {                       // Scanlines
        float period = 0.5 * cell;
        return spectrum_box_stripe(y / period, g_px_y / period, 0.4);
    }
    if (u_pattern == 3) {                       // Dots
        float columns = max(1.0, floor(bw / cell + 0.5));
        float cw = bw / columns;
        vec2 local = vec2((fract(lx / cw) - 0.5) * cw, (fract(y / cell) - 0.5) * cell);
        float radius = 0.3 * min(cw, cell);
        float px = max(g_px_x, g_px_y);
        float edge = clamp((radius - length(local)) / px + 0.5, 0.0, 1.0);
        float mean = 3.14159265 * radius * radius / (cw * cell);
        return mix(edge, mean, smoothstep(0.5, 1.5, px / max(radius, 1e-4)));
    }
    if (u_pattern == 4) {                       // Diagonal Stripes (continuous across the field)
        float period = 1.5 * cell * 1.41421356;
        return spectrum_box_stripe((fx + y) / period, (g_px_x + g_px_y) / period, 0.5);
    }
    if (u_pattern == 5) {                       // Grid
        float period = 1.5 * cell;
        float d = 0.16;
        float columns = max(2.0, floor(bw / period + 0.5));   // at least the centre line in a narrow bar
        float cw = bw / columns;
        float rows = spectrum_box_stripe(y / period - 0.5 * d, g_px_y / period, d);
        float cols = spectrum_box_stripe(lx / cw - 0.5 * d, g_px_x / cw, d);
        return rows + cols - rows * cols;
    }
    if (u_pattern == 6) {                       // Chevrons, pointing up, centred on each bar
        float period = 1.5 * cell;
        return spectrum_box_stripe((y + abs(lx - 0.5 * bw)) / period, (g_px_x + g_px_y) / period, 0.45);
    }
    return 0.0;
}

// Gloss: a soft specular stripe and side shading across the bar (bar-local, so it never moves). A bar only a few
// pixels wide shows the profile's mean instead of an aliased highlight.
vec3 spectrum_gloss(vec3 rgb, float lx, float bw) {
    float g = clamp(u_gloss, 0.0, 1.0);
    float width = max(bw, 1e-4);
    float u = clamp(lx / width, 0.0, 1.0);
    float detail = 1.0 - smoothstep(0.15, 0.5, g_px_x / width);
    float spec = exp(-pow((u - 0.32) / 0.13, 2.0));
    float side = pow(abs(u - 0.5) * 2.0, 2.5);
    float lift = g * 0.6 * mix(0.23, spec, detail);
    float shade = g * 0.45 * mix(0.286, side, detail);
    rgb = rgb + (vec3(1.0) - rgb) * lift;
    return rgb * (1.0 - shade);
}

// The bar body's surface (fill pixels only): the pattern composited over it, then gloss.
vec4 spectrum_bar_surface(vec4 c, float lx, float bw, float y, float fx, float scale) {
    if (u_pattern_mix > 0.0 && u_pattern >= FLAG_FIRST) {
        // A flag sheet replaces the fill colour (Strength and the fade blend it in); the fill's alpha stays.
        vec2 uv = vec2(fx / max(u_bar_span_px, 1e-4), y / max(g_field_h, 1e-4));
        vec2 px = vec2(g_px_x / max(u_bar_span_px, 1e-4), g_px_y / max(g_field_h, 1e-4));
        c.rgb = mix(c.rgb, clamp(spectrum_flag(uv, px), 0.0, 1.0), clamp(u_pattern_mix * u_fade, 0.0, 1.0));
    } else if (u_pattern_mix > 0.0 && u_pattern > 0) {
        float a = clamp(u_pattern_color.a * u_pattern_mix * u_fade
                        * spectrum_pattern_coverage(lx, bw, y, fx, scale), 0.0, 1.0);
        float out_a = a + c.a * (1.0 - a);
        vec3 rgb = (u_pattern_color.rgb * a + c.rgb * c.a * (1.0 - a)) / max(out_a, 1e-5);
        c = vec4(rgb, out_a);
    }
    if (u_gloss > 0.0) {
        c.rgb = spectrum_gloss(c.rgb, lx, bw);
    }
    return c;
}

// The Bar Fill ghost's blur: the bar's surface averaged over a box ``blur`` tall (item px) and half as wide, centred
// on this pixel. GHOST_TAPS_X x GHOST_TAPS_Y samples, each box-filtered over its own share of the box (every pattern,
// flag sheet and gloss filters over the pixel footprint g_px_x / g_px_y, widened here), so stripes, stars and
// pattern edges dissolve into the bar's own colours. Only Bar Fill ghost pixels pay for it.
const int GHOST_TAPS_X = 2;
const int GHOST_TAPS_Y = 4;

vec4 spectrum_blurred_surface(vec4 surface, float lx, float bw, float y, float fx, float scale, float blur) {
    float keep_x = g_px_x;
    float keep_y = g_px_y;
    float span_x = 0.5 * blur;
    g_px_x = max(keep_x, span_x / float(GHOST_TAPS_X));
    g_px_y = max(keep_y, blur / float(GHOST_TAPS_Y));
    vec4 sum = vec4(0.0);
    for (int i = 0; i < GHOST_TAPS_X; ++i) {
        float ox = ((float(i) + 0.5) / float(GHOST_TAPS_X) - 0.5) * span_x;
        for (int j = 0; j < GHOST_TAPS_Y; ++j) {
            float oy = ((float(j) + 0.5) / float(GHOST_TAPS_Y) - 0.5) * blur;
            sum += spectrum_bar_surface(surface, lx + ox, bw, y + oy, fx + ox, scale);
        }
    }
    g_px_x = keep_x;
    g_px_y = keep_y;
    return sum / float(GHOST_TAPS_X * GHOST_TAPS_Y);
}

// Ghost Colour Bar Fill: the ghost is a soft, blurred, fading trail of its own bar's surface. Inside the bar's border
// it shows the fill (``fill`` already carries the Fill Gradient at this height; Rainbow Fill, a pattern or flag sheet
// and gloss follow), blurred more as it rises (``t``: 0 at the bar top, 1 at the peak); on the bar's side border
// (and, in Segments, each segment's border ring) it shows the border colour at the border's own opacity, so a
// transparent or dark outline stays one on the ghost. Its body is more transparent than a plain ghost and fades out
// sooner toward its top (operator, 8 Nov 2026: Bar Fill ghosts were "too solid and not blurred" beside Preset 1's).
// The ghost never takes the bar's top stroke: nothing draws a line over its fading top. Rainbow Ghost, when on,
// colours it instead.
vec4 spectrum_ghost_fill(vec4 ghost, vec4 fill, bool on_border, int bidx, float lx, float bw, float y, float fx,
                         float scale, float t) {
    if (u_rainbow_ghost == 1 || u_ghost_fill_mix <= 0.0) return ghost;
    float k = clamp(u_ghost_fill_mix, 0.0, 1.0);
    float rise = clamp(t, 0.0, 1.0);
    float body = mix(1.0, 0.85 * (1.0 - 0.45 * smoothstep(0.0, 1.0, rise)), k);
    if (on_border) {
        vec4 edge = (u_rainbow_border == 1) ? apply_spectrum_rainbow(u_border_color, bidx) : u_border_color;
        return vec4(mix(ghost.rgb, edge.rgb, k), ghost.a * mix(1.0, clamp(u_border_color.a, 0.0, 1.0), k) * body);
    }
    vec4 surface = (u_rainbow_fill == 1) ? apply_spectrum_rainbow(fill, bidx) : fill;
    float blur = k * mix(0.08, 0.2, smoothstep(0.0, 0.35, rise)) * g_field_h;
    surface = spectrum_blurred_surface(surface, lx, bw, y, fx, scale, blur);
    // A light surface (white stripes, a white field) reads far brighter than a saturated hue at the same opacity, so
    // it is made more transparent toward the brightness of a hue ghost like Preset 1's.
    float luma = dot(surface.rgb, vec3(0.2126, 0.7152, 0.0722));
    body *= mix(1.0, clamp(0.55 / max(luma, 1e-3), 0.6, 1.0), k);
    return vec4(mix(ghost.rgb, surface.rgb, k), ghost.a * body);
}

// Peak cap coverage: a band ``thickness`` tall a small gap above ``top``, box-filtered over the pixel so a
// moving cap never loses its coverage at fractional heights.
float spectrum_cap_coverage(float y, float top, float scale) {
    float px = max(g_px_y, 1e-4);
    float low = top + max(scale, px);
    float high = low + max(u_peak_cap_thickness, px);
    return clamp((min(y + 0.5 * px, high) - max(y - 0.5 * px, low)) / px, 0.0, 1.0);
}

float spectrum_rim_alpha_at(float side_dist_px, float top_dist_px, float coverage_px) {
    if (u_spectrum_glow_enabled != 1) return 0.0;
    float glow_strength = clamp(u_spectrum_glow_intensity, 0.0, 1.5);
    if (glow_strength <= 0.001) return 0.0;
    float edge_dist = min(side_dist_px, top_dist_px);
    // Inward rim glow: bright core near the edge that fades deeper into the
    // bar interior.  Thresholds sized so bars of 8-15px width get a clearly
    // visible tinted band (roughly the outer 40-60% of the bar).
    float authored_scale = (u_quick_item_coords == 1)
        ? max(u_visual_scale, 0.01) : 1.0;
    // A rim, never a recolour: at most 30% of the bar's width in from each side (37 bars at card size are ~11 px
    // wide, so any intensity above ~0.3 used to tint the whole bar).
    float spread = min((3.0 + glow_strength * 4.0) * authored_scale, max(0.3 * u_bar_width_px, authored_scale));
    // ``u_visual_scale`` controls authored styling, but it can make the
    // styled rim narrower than one framebuffer pixel.  Keep the authored
    // spread and derive only the coverage feather from actual fragment
    // derivatives.  In particular, do not impose a 1.5px authored core:
    // below that scale it exceeds ``spread`` and reverses smoothstep's edges,
    // which is undefined and can wash the entire black Organs fill white.
    // ``coverage_px`` is that feather (spectrum_rim_coverage, taken in main's prologue).
    float core_end = spread * 0.35;
    float inner_core = 1.0 - smoothstep(0.0, max(core_end, coverage_px), edge_dist);
    float inner_falloff = 1.0 - smoothstep(core_end, spread + coverage_px, edge_dist);
    float rim = max(inner_core * 0.90, inner_falloff * 0.55);
    float color_alpha = clamp(u_spectrum_glow_color.a, 0.0, 1.0);
    return rim * clamp(color_alpha * (0.55 + glow_strength * 0.40), 0.0, 0.95);
}

// The rim's coverage feather: the fine derivative of its edge distance (a min() of two distances, so a 2x2 quad's
// coarse difference differs from the per-pixel one at a bar's corner; named Fine for Vulkan, OpenGL's is fine on the
// rig). Called only from main's prologue: derivatives must be taken before any discard (or return), while every lane
// of the quad is alive. A discarded neighbour is a helper on OpenGL but ended on Vulkan (SPIR-V OpKill), so the
// feather taken after the discards differed by up to 15 levels beside every discarded corner pixel (N2.5 rule (b):
// all 5,652 Vulkan pixels more than a level off shared a quad with a discarded one).
float spectrum_rim_coverage(float side_dist_px, float top_dist_px) {
    return max(fwidthFine(min(side_dist_px, top_dist_px)), 0.0001);
}

// The border band of a bar (x) or a segment (y): one authored unit in from each edge, never under one logical pixel
// (the bar top's stroke rule: a narrower band holds no pixel centre at small visual scales), on the continuous
// coordinate the fragment's pixel centre has, the same test on both edges (``local`` is half-open, [0, extent)). The
// old test floored the coordinate and took ``<=`` on the low edge: two units on the left and bottom against one plus
// the extent's fraction on the right and top, so the left border covered the rim glow's brightest columns (1D.14).
bool spectrum_in_border_band(float local, float extent, float scale) {
    float band = max(scale, 1.0);
    return local < band || local >= extent - band;
}

vec4 blend_spectrum_rim_glow(vec4 base_color, float rim_alpha) {
    if (rim_alpha <= 0.001) return base_color;
    vec3 glow_rgb = u_spectrum_glow_color.rgb;
    float color_alpha = clamp(u_spectrum_glow_color.a, 0.0, 1.0);
    // Tint replacement: mix the glow colour into the fill.  The strength
    // scales with rim_alpha so the core band is strongly tinted while the
    // falloff region blends gently.
    float stripe_mix = clamp(rim_alpha * (1.20 + color_alpha * 0.60), 0.0, 0.85);
    vec3 tinted = mix(base_color.rgb, glow_rgb, stripe_mix);
    // Additive lift so the glow pops even on bright/white fills.
    vec3 lifted = min(vec3(1.0), tinted + glow_rgb * rim_alpha * (0.30 + color_alpha * 0.15));
    return vec4(lifted, base_color.a);
}

void main() {
    // Every derivative is taken in this prologue, before the first discard or return: a derivative after one is
    // undefined in GLSL (non-uniform control flow) and differs by driver. OpenGL keeps a discarded neighbour running
    // as a helper; Vulkan's discard (SPIR-V OpKill) ends it, so the rim's feather differed by up to 15 levels beside
    // every discarded corner pixel (N2.5 rule (b)). The prologue computes the geometry the derivatives read for every
    // pixel, in the bar field or not (array reads clamped); the discards after it are the original tests, in order.
    // tests/test_shader_derivatives.py refuses a derivative after a discard or a return in main.
    float width = u_resolution.x;
    float height = u_resolution.y;

    // Derive logical fragment coordinates from the physical framebuffer
    // position. QOpenGLWidget renders into a device-pixel-scaled FBO, so we
    // map the fragment's pixel (physical) back into QWidget logical space using the
    // current device pixel ratio.
    vec2 fragCoord;
    if (u_quick_item_coords == 1 && u_item_from_frag == 1) {
        vec3 target = vec3(fragPixel(u_target_px), 1.0);
        vec3 window = vec3(dot(u_window_from_target_x, target), dot(u_window_from_target_y, target), 1.0);
        fragCoord = vec2(dot(u_item_from_frag_x, window), dot(u_item_from_frag_y, window));
    } else if (u_quick_item_coords == 1) {
        fragCoord = v_uv * u_resolution;
    } else {
        float dpr = (u_dpr <= 0.0) ? 1.0 : u_dpr;
        float fb_height = height * dpr;
        vec2 localFrag = fragPixel(u_target_px) - u_viewport_origin_px;
        fragCoord = vec2(localFrag.x / dpr, (fb_height - localFrag.y) / dpr);
    }
    g_px_x = max(abs(dFdx(fragCoord.x)) + abs(dFdy(fragCoord.x)), 1e-4);
    g_px_y = max(abs(dFdx(fragCoord.y)) + abs(dFdy(fragCoord.y)), 1e-4);

    // ========== SPECTRUM MODE ==========
    float authored_scale = (u_quick_item_coords == 1)
        ? max(u_visual_scale, 0.01) : 1.0;
    vec4 content_rect = (u_quick_item_coords == 1)
        ? u_content_rect : vec4(0.0, 0.0, width, height);
    float margin_y = 6.0 * authored_scale;
    float gap = u_bar_gap_px;
    float seg_gap = 1.0 * authored_scale;

    float inner_top = content_rect.y + margin_y;
    float inner_height = content_rect.w - margin_y * 2.0;
    float inner_bottom = inner_top + inner_height;
    g_field_h = 0.95 * inner_height;

    int bar_count_int = max(u_bar_count, 1);
    float bar_count = float(bar_count_int);
    float bar_width = u_bar_width_px;
    float span = u_bar_span_px;
    float bars_left = u_bars_left;
    float x_rel = fragCoord.x - bars_left;
    float step_x = bar_width + gap;
    int bar_index = int(floor(x_rel / step_x));
    // Local X coordinate within the bar (the gap region is discarded below).
    float bar_local_x = x_rel - float(bar_index) * step_x;
    // The bar read: a pixel outside the bar field (discarded below) reads its nearest bar, so its derivative lanes
    // never index out of range.
    int bar_slot = clamp(bar_index, 0, bar_count_int - 1);

    float value = u_bars[bar_slot];
    if (value < 0.0) {
        value = 0.0;
    }
    if (value > 1.0) {
        value = 1.0;
    }

    float peak = u_peaks[bar_slot];
    if (peak < 0.0) {
        peak = 0.0;
    }
    if (peak > 1.0) {
        peak = 1.0;
    }

    // Mild power curve: pushes quiet bars slightly down, loud bars reach top.
    // pow(1.15): bar 0.3 → 0.26, bar 0.7 → 0.65, bar 1.0 → 1.0
    float curved = pow(value, 1.15);
    float curved_peak = pow(peak, 1.15);

    // u_bar_height_scale is already the capped presentation transfer computed
    // by Python (compute_spectrum_height_scale). Consume it exactly once here.
    // Quick previously square-rooted that resolved boost a second time, making
    // tall viewports react less strongly than the authored transfer specifies.
    float height_scale = clamp(max(1.0, u_bar_height_scale), 1.0, 1.85);
    float boosted = curved * height_scale;
    if (boosted > 0.95) {
        boosted = 0.95;
    }

    float boosted_peak = curved_peak * height_scale;
    if (boosted_peak > 0.95) {
        boosted_peak = 0.95;
    }

    float y_rel = inner_bottom - fragCoord.y;
    // Single piece: the bar's and its ghost's heights.
    float active_height = boosted * inner_height;
    float peak_height = boosted_peak * inner_height;
    bool is_bar = (y_rel < active_height);
    // Suppress ghost when bar is silent (active_height < 1px) to prevent
    // a white border flash from a decaying peak on a zero-height bar.
    bool is_ghost = (!is_bar && active_height >= authored_scale && peak_height > active_height && y_rel < peak_height);
    // Segmented: the segment grid.
    float total_seg_gap = seg_gap * float(u_segments - 1);
    float seg_height = (inner_height - total_seg_gap) / float(u_segments);
    seg_height = floor(seg_height / authored_scale) * authored_scale;
    float step_y = seg_height + seg_gap;
    int seg_index = int(floor(y_rel / step_y));
    float seg_local_y = y_rel - float(seg_index) * step_y;
    // The rim's distances and its derivative (spectrum_rim_coverage), from every lane of the quad.
    float rim_side_dist_px = min(bar_local_x, bar_width - bar_local_x);
    float rim_top_dist_px = (u_single_piece == 1)
        ? abs((is_ghost ? peak_height : active_height) - y_rel) : abs(seg_height - seg_local_y);
    float rim_coverage_px = spectrum_rim_coverage(rim_side_dist_px, rim_top_dist_px);

    // ---------- No derivative below this line (the prologue's comment). ----------
    if (u_fade <= 0.0 || u_bar_count <= 0 || u_segments <= 0) {
        discard;
    }
    if (width <= 0.0 || height <= 0.0) {
        discard;
    }
    if (inner_height <= 0.0) {
        discard;
    }
    // Discard anything outside the bar field vertically so we don't fill
    // the entire card when active_segments is high.
    if (fragCoord.y < inner_top || fragCoord.y > inner_bottom) {
        discard;
    }
    if (bar_width < authored_scale) {
        discard;
    }
    if (bars_left < 0.0 || span <= 0.0 || gap < 0.0) {
        discard;
    }
    if (x_rel < 0.0) {
        discard;
    }
    if (x_rel >= span) {
        discard;
    }
    if (bar_index < 0 || bar_index >= u_bar_count) {
        discard;
    }
    // The explicit gap region. Use a half-open range [0, bar_width) so that we never classify the
    // gap pixel as part of the bar due to floating-point rounding.
    if (bar_local_x < 0.0 || bar_local_x >= bar_width) {
        discard;
    }

    // ========== SINGLE PIECE MODE ==========
    // Render solid continuous bars with no segment gaps.
    if (u_single_piece == 1) {
        if (y_rel < 0.0) {
            discard;
        }

        if (!is_bar && !is_ghost) {
            if (u_peak_cap_mix > 0.0) {
                float cap = spectrum_cap_coverage(y_rel, max(active_height, peak_height), authored_scale);
                if (cap > 0.0) {
                    vec4 cap_color = u_peak_cap_color;
                    cap_color.a *= cap * clamp(u_peak_cap_mix, 0.0, 1.0) * u_fade;
                    fragColor = cap_color;
                    return;
                }
            }
            discard;
        }

        // Border radius: each shape (bar / ghost) gets its own independent
        // rounding so all tops look consistent regardless of relative heights.
        // A Bar Fill ghost begins at the bar's fill top and wraps it: it fills the bar's rounded top corners and its
        // own bottom stays square, so the two roundings never pinch the junction into a dark gap row. ``fill_k`` is
        // the Bar Fill fade envelope, ``lift`` ramps the ghost in as its peak lifts off the bar (no pop).
        float fill_k = (u_rainbow_ghost != 1) ? clamp(u_ghost_fill_mix, 0.0, 1.0) : 0.0;
        bool fill_ghost_above = fill_k > 0.0 && active_height >= authored_scale && peak_height > active_height;
        float lift = clamp((peak_height - active_height) / max(authored_scale, 1.0), 0.0, 1.0);
        float corner_ghost = 0.0;   // > 0: a bar top corner outside its arc, shown as the ghost's start
        float ghost_cover = 1.0;    // the ghost's own bottom corners fade out of their rounding with fill_k
        // The rounded corners' inside test is computed `precise` (no fused multiply-add): a pixel centre on
        // the arc decided otherwise by Vulkan's compiler than by OpenGL's (N2.5 rule (b)).
        float br_max = min(u_border_radius, bar_width * 0.5);
        if (br_max > 0.5 * authored_scale) {
            float bx_f = bar_local_x;
            float by_f = y_rel;

            if (is_bar) {
                // Round the TOP two corners of the active bar
                float br_bar = (active_height < br_max * 2.0)
                    ? min(br_max, active_height * 0.5) : br_max;
                if (br_bar > 0.5 * authored_scale && by_f > active_height - br_bar) {
                    bool outside = false;
                    if (bx_f < br_bar) {
                        precise float dx = br_bar - bx_f;
                        precise float dy = by_f - (active_height - br_bar);
                        precise float d2 = dx * dx + dy * dy;
                        precise float r2 = br_bar * br_bar;
                        outside = outside || (d2 > r2);
                    }
                    if (bx_f > bar_width - br_bar) {
                        precise float dx = bx_f - (bar_width - br_bar);
                        precise float dy = by_f - (active_height - br_bar);
                        precise float d2 = dx * dx + dy * dy;
                        precise float r2 = br_bar * br_bar;
                        outside = outside || (d2 > r2);
                    }
                    if (outside) {
                        if (!fill_ghost_above) discard;
                        corner_ghost = fill_k * lift;
                    }
                }
            }

            if (is_ghost) {
                // Round the TOP two corners of the ghost
                float br_ghost = (peak_height < br_max * 2.0)
                    ? min(br_max, peak_height * 0.5) : br_max;
                if (br_ghost > 0.5 * authored_scale && by_f > peak_height - br_ghost) {
                    if (bx_f < br_ghost) {
                        precise float dx = br_ghost - bx_f;
                        precise float dy = by_f - (peak_height - br_ghost);
                        precise float d2 = dx * dx + dy * dy;
                        precise float r2 = br_ghost * br_ghost;
                        if (d2 > r2) discard;
                    }
                    if (bx_f > bar_width - br_ghost) {
                        precise float dx = bx_f - (bar_width - br_ghost);
                        precise float dy = by_f - (peak_height - br_ghost);
                        precise float d2 = dx * dx + dy * dy;
                        precise float r2 = br_ghost * br_ghost;
                        if (d2 > r2) discard;
                    }
                }
                // Round ghost BOTTOM corners where ghost meets bar top
                if (active_height > 2.0 * authored_scale) {
                    float br_bot = (active_height < br_max * 2.0)
                        ? min(br_max, active_height * 0.5) : br_max;
                    if (br_bot > 0.5 * authored_scale && by_f < active_height + br_bot) {
                        if (bx_f < br_bot) {
                            precise float dx = br_bot - bx_f;
                            precise float dy = (active_height + br_bot) - by_f;
                            precise float d2 = dx * dx + dy * dy;
                            precise float r2 = br_bot * br_bot;
                            if (d2 > r2) {
                                if (fill_k <= 0.0) discard;
                                ghost_cover = fill_k;
                            }
                        }
                        if (bx_f > bar_width - br_bot) {
                            precise float dx = bx_f - (bar_width - br_bot);
                            precise float dy = (active_height + br_bot) - by_f;
                            precise float d2 = dx * dx + dy * dy;
                            precise float r2 = br_bot * br_bot;
                            if (d2 > r2) {
                                if (fill_k <= 0.0) discard;
                                ghost_cover = fill_k;
                            }
                        }
                    }
                }
            }
        }

        vec4 fill = u_fill_color;
        vec4 border = u_border_color;
        fill.a *= u_fade;
        border.a *= u_fade;
        fill = spectrum_fill_gradient(fill, y_rel / (0.95 * inner_height));

        float bw_px = floor(bar_width);
        bool in_side_band = spectrum_in_border_band(bar_local_x, bar_width, authored_scale);

        vec4 sp_color;
        bool sp_is_border = false;
        // A Bar Fill ghost begins at the bar's fill top: the bar's top stroke lies over the ghost's start (the border
        // composited over it), so a transparent or translucent top border never opens a dark seam between the lit
        // fill and its ghost. ``band_ghost`` is that stroke's share of the ghost (0 with no Bar Fill ghost above).
        float band_ghost = 0.0;
        if (is_bar && corner_ghost <= 0.0 && fill_ghost_above && bw_px > 2.0 * authored_scale
                && !in_side_band && y_rel >= authored_scale
                && y_rel >= active_height - max(authored_scale, 1.0)) {
            band_ghost = fill_k * lift;
        }
        if (is_ghost || band_ghost > 0.0 || corner_ghost > 0.0) {
            float ghost_alpha = clamp(u_ghost_alpha, 0.0, 1.0);
            if (ghost_alpha <= 0.0 && is_ghost) {
                discard;
            }
            // Smooth fade from bar top to peak top
            float ghost_dist = y_rel - active_height;
            float ghost_span = max(authored_scale, peak_height - active_height);
            float t = clamp(ghost_dist / ghost_span, 0.0, 1.0);
            float ghost_factor = mix(1.0, 0.15, t);
            // Ghost visibility is owned by its opacity, not border alpha. An
            // author may deliberately use fully transparent or black borders.
            bool ghost_side = (bw_px <= 2.0 * authored_scale) || in_side_band;
            vec4 ghost_base = spectrum_ghost_tip(spectrum_ghost_fill(spectrum_ghost_colour(bar_index, u_fade), fill,
                ghost_side, bar_index, bar_local_x, bar_width, y_rel, x_rel, authored_scale, t), t);
            ghost_base.a *= ghost_alpha * ghost_factor * ghost_cover;
            sp_color = ghost_base;
            if (corner_ghost > 0.0) {
                sp_color.a *= corner_ghost;
            } else if (!is_ghost) {
                // The bar's top stroke over the ghost's start (straight alpha, as the render host blends).
                vec4 edge = (u_rainbow_border == 1) ? apply_spectrum_rainbow(border, bar_index) : border;
                float under = ghost_base.a * band_ghost * (1.0 - edge.a);
                float out_a = edge.a + under;
                sp_color = vec4((edge.rgb * edge.a + ghost_base.rgb * under) / max(out_a, 1e-5), out_a);
            }
            sp_is_border = true;
        } else {
            // Border on left/right edges and top edge of the bar
            bool on_border = false;
            if (bw_px <= 2.0 * authored_scale) {
                on_border = true;
            } else {
                bool on_side = in_side_band;
                // The moving horizontal cap is finished pixel chrome, not world
                // thickness. A sub-pixel interval can contain no fragment centre
                // at some fractional bar heights, which is the observed top-edge
                // disappearance. Keep authored growth above one pixel, but never
                // let the cap's coverage interval fall below one logical pixel.
                float top_stroke = max(authored_scale, 1.0);
                bool on_top = (y_rel >= active_height - top_stroke);
                bool on_bottom = (y_rel < authored_scale);
                on_border = on_side || on_top || on_bottom;
            }
            sp_is_border = on_border;
            sp_color = on_border ? border : fill;
        }
        float rim_alpha = spectrum_rim_alpha_at(rim_side_dist_px, rim_top_dist_px, rim_coverage_px) * u_fade;
        if (!sp_is_border) {
            sp_color = blend_spectrum_rim_glow(sp_color, rim_alpha);
        }
        // The independent ghost colour is complete. Do not reapply Rainbow
        // Borders to it (double-hue shift) or recolour its authored opacity.
        bool sp_apply_rainbow = !is_ghost && band_ghost <= 0.0 && corner_ghost <= 0.0 && (sp_is_border
            ? (u_rainbow_border == 1)
            : (u_rainbow_fill == 1));
        fragColor = sp_apply_rainbow ? apply_spectrum_rainbow(sp_color, bar_index) : sp_color;
        if (!is_ghost && !sp_is_border) {
            fragColor = spectrum_bar_surface(fragColor, bar_local_x, bar_width, y_rel, x_rel, authored_scale);
        }
        return;
    }

    // ========== SEGMENTED MODE ==========
    // (The segment grid is the prologue's.)
    if (seg_height < authored_scale) {
        discard;
    }
    if (y_rel < 0.0) {
        discard;
    }
    if (seg_index < 0) {
        discard;
    }
    // Discard the vertical gap region using a half-open range [0, seg_height).
    if (seg_local_y < 0.0 || seg_local_y >= seg_height) {
        discard;
    }

    // Border radius clip for segmented bars (all 4 corners of each segment)
    float br_seg = clamp(u_border_radius, 0.0, min(bar_width * 0.5, seg_height * 0.5));
    if (br_seg > 0.5 * authored_scale) {
        float bx_f = bar_local_x;
        float by_f = seg_local_y;
        // Bottom-left corner
        if (bx_f < br_seg && by_f < br_seg) {
            precise float dx = br_seg - bx_f;
            precise float dy = br_seg - by_f;
            precise float d2 = dx * dx + dy * dy;
            precise float r2 = br_seg * br_seg;
            if (d2 > r2) discard;
        }
        // Bottom-right corner
        if (bx_f > bar_width - br_seg && by_f < br_seg) {
            precise float dx = bx_f - (bar_width - br_seg);
            precise float dy = br_seg - by_f;
            precise float d2 = dx * dx + dy * dy;
            precise float r2 = br_seg * br_seg;
            if (d2 > r2) discard;
        }
        // Top-left corner
        if (bx_f < br_seg && by_f > seg_height - br_seg) {
            precise float dx = br_seg - bx_f;
            precise float dy = by_f - (seg_height - br_seg);
            precise float d2 = dx * dx + dy * dy;
            precise float r2 = br_seg * br_seg;
            if (d2 > r2) discard;
        }
        // Top-right corner
        if (bx_f > bar_width - br_seg && by_f > seg_height - br_seg) {
            precise float dx = bx_f - (bar_width - br_seg);
            precise float dy = by_f - (seg_height - br_seg);
            precise float d2 = dx * dx + dy * dy;
            precise float r2 = br_seg * br_seg;
            if (d2 > r2) discard;
        }
    }

    int active_segments = int(round(boosted * float(u_segments)));
    if (active_segments <= 0) {
        active_segments = 1;
    }

    // Determine whether this fragment belongs to the main bar body
    // or to a trailing ghost segment derived from the decaying peak.
    int peak_segments = active_segments;
    bool is_ghost_frag = false;
    if (peak > value) {
        float delta = peak - value;
        if (delta < 0.0) {
            delta = 0.0;
        }

        float boosted_delta = delta * 1.2 * height_scale;
        if (boosted_delta > 0.95) {
            boosted_delta = 0.95;
        }
        int extra_segments = int(ceil(boosted_delta * float(u_segments)));
        if (extra_segments <= 0 && delta > 0.01 && active_segments < u_segments) {
            extra_segments = 1;
        }

        peak_segments = active_segments + extra_segments;
        if (peak_segments > u_segments) {
            peak_segments = u_segments;
        }
        if (peak_segments > active_segments && seg_index >= active_segments && seg_index < peak_segments) {
            is_ghost_frag = true;
        }
    }

    bool is_bar_frag = (active_segments > 0) && (seg_index < active_segments);
    if (!is_bar_frag && !is_ghost_frag) {
        // Peak cap: the first free segment above the bar and its ghost lights in the cap colour.
        if (u_peak_cap_mix > 0.0 && seg_index == peak_segments && peak_segments < u_segments) {
            vec4 cap_color = u_peak_cap_color;
            cap_color.a *= clamp(u_peak_cap_mix, 0.0, 1.0) * u_fade;
            fragColor = cap_color;
            return;
        }
        discard;
    }

    float bw_px = floor(bar_width);
    float sh_px = floor(seg_height);

    bool on_border = false;
    if (is_bar_frag || is_ghost_frag) {
        if (bw_px <= 2.0 * authored_scale || sh_px <= 2.0 * authored_scale) {
            on_border = true;
        } else {
            if (spectrum_in_border_band(bar_local_x, bar_width, authored_scale)
                    || spectrum_in_border_band(seg_local_y, seg_height, authored_scale)) {
                on_border = true;
            }
        }
    }

    vec4 fill = u_fill_color;
    vec4 border = u_border_color;
    fill.a *= u_fade;
    border.a *= u_fade;
    // LED-meter shading: each segment takes the gradient at its own centre.
    fill = spectrum_fill_gradient(fill, (float(seg_index) * step_y + 0.5 * seg_height) / (0.95 * inner_height));

    vec4 out_color;
    bool seg_is_border = false;
    if (is_ghost_frag) {
        float ghost_alpha = clamp(u_ghost_alpha, 0.0, 1.0);
        if (ghost_alpha <= 0.0) {
            discard;
        }

        float ghost_factor = 1.0;
        float ghost_t = 0.0;
        if (peak_segments > active_segments) {
            float ghost_idx = float(seg_index - active_segments);
            float ghost_len = float(max(1, peak_segments - active_segments));
            float t = 0.0;
            if (ghost_len > 1.0) {
                t = clamp(ghost_idx / (ghost_len - 1.0), 0.0, 1.0);
            }
            float start = 1.0;
            float end = 0.25;
            ghost_factor = mix(start, end, t);
            ghost_t = t;
        }

        vec4 ghost = spectrum_ghost_tip(spectrum_ghost_fill(spectrum_ghost_colour(bar_index, u_fade), fill,
            on_border, bar_index, bar_local_x, bar_width, y_rel, x_rel, authored_scale, ghost_t), ghost_t);
        ghost.a *= ghost_alpha * ghost_factor;
        out_color = ghost;
        seg_is_border = true;
    } else {
        seg_is_border = on_border;
        out_color = on_border ? border : fill;
    }
    float seg_rim_alpha = spectrum_rim_alpha_at(rim_side_dist_px, rim_top_dist_px, rim_coverage_px) * u_fade;
    if (!seg_is_border) {
        out_color = blend_spectrum_rim_glow(out_color, seg_rim_alpha);
    }

    // Same independent fill/border participation contract as solid bars.
    bool seg_apply_rainbow = !is_ghost_frag && (seg_is_border
        ? (u_rainbow_border == 1)
        : (u_rainbow_fill == 1));
    fragColor = seg_apply_rainbow ? apply_spectrum_rainbow(out_color, bar_index) : out_color;
    if (!is_ghost_frag && !seg_is_border) {
        fragColor = spectrum_bar_surface(fragColor, bar_local_x, bar_width, y_rel, x_rel, authored_scale);
    }
}
