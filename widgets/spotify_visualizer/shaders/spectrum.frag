#version 330 core
in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;   // logical size in QWidget coordinates
uniform float u_dpr;         // device pixel ratio of the backing FBO
uniform int u_bar_count;
uniform int u_segments;
uniform float u_bars[64];
uniform float u_peaks[64];
uniform vec4 u_fill_color;
uniform vec4 u_border_color;
uniform float u_fade;
uniform int u_playing;
uniform float u_ghost_alpha;
uniform float u_bar_height_scale;  // visual boost for taller cards (1.0 = default height)
uniform int u_single_piece;        // 1 = solid bars (no segment gaps)
uniform int u_slanted;             // 1 = diagonal-sliced bar edges facing center
uniform float u_border_radius;     // border radius in px (0 = square, ~6 = rounded)

void main() {
    if (u_fade <= 0.0 || u_bar_count <= 0 || u_segments <= 0) {
        discard;
    }

    float width = u_resolution.x;
    float height = u_resolution.y;
    if (width <= 0.0 || height <= 0.0) {
        discard;
    }

    // Derive logical fragment coordinates from the physical framebuffer
    // position. QOpenGLWidget renders into a device-pixel-scaled FBO, so we
    // map gl_FragCoord (physical) back into QWidget logical space using the
    // current device pixel ratio.
    float dpr = (u_dpr <= 0.0) ? 1.0 : u_dpr;
    float fb_height = height * dpr;
    vec2 fragCoord = vec2(gl_FragCoord.x / dpr, (fb_height - gl_FragCoord.y) / dpr);

    // ========== SPECTRUM MODE ==========
    float margin_x = 8.0;
    float margin_y = 6.0;
    float gap = 2.0;
    float seg_gap = 1.0;
    float bars_inset = 5.0;

    // Match QWidget geometry: inner rect is rect.adjusted(margin_x, margin_y,
    // -margin_x, -margin_y). For a logical rect starting at (0, 0) this
    // gives width = W - 2*margin_x and height = H - 2*margin_y.
    float inner_left = margin_x;
    float inner_top = margin_y;
    float inner_width = width - margin_x * 2.0;
    float inner_height = height - margin_y * 2.0;
    float inner_right = inner_left + inner_width;
    float inner_bottom = inner_top + inner_height;

    if (inner_width <= 0.0 || inner_height <= 0.0) {
        discard;
    }

    // Discard anything outside the bar field vertically so we don't fill
    // the entire card when active_segments is high.
    if (fragCoord.y < inner_top || fragCoord.y > inner_bottom) {
        discard;
    }

    float bar_region_width = inner_width - (bars_inset * 2.0);
    if (bar_region_width <= 0.0) {
        discard;
    }

    int bar_count_int = max(u_bar_count, 1);
    float bar_count = float(bar_count_int);
    float total_gap = gap * float(bar_count_int - 1);
    float usable_width = bar_region_width - total_gap;
    if (usable_width <= 0.0) {
        discard;
    }

    float bar_width = floor(usable_width / bar_count);
    if (bar_width < 1.0) {
        discard;
    }

    float span = bar_width * bar_count + total_gap;
    float remaining = max(0.0, bar_region_width - span);
    float bars_left = inner_left + bars_inset + floor(remaining * 0.5);

    float x_rel = fragCoord.x - bars_left;
    if (x_rel < 0.0) {
        discard;
    }
    if (x_rel >= span) {
        discard;
    }

    float step_x = bar_width + gap;
    int bar_index = int(floor(x_rel / step_x));
    if (bar_index < 0 || bar_index >= u_bar_count) {
        discard;
    }

    // Local X coordinate within the bar; discard the explicit gap region.
    // Use a half-open range [0, bar_width) so that we never classify the
    // gap pixel as part of the bar due to floating-point rounding.
    float bar_local_x = x_rel - float(bar_index) * step_x;
    if (bar_local_x < 0.0 || bar_local_x >= bar_width) {
        discard;
    }

    float value = u_bars[bar_index];
    if (value < 0.0) {
        value = 0.0;
    }
    if (value > 1.0) {
        value = 1.0;
    }

    float peak = u_peaks[bar_index];
    if (peak < 0.0) {
        peak = 0.0;
    }
    if (peak > 1.0) {
        peak = 1.0;
    }

    // Blanket power reduction for Spectrum mode: scale all bars
    // to match the visual intensity of Spotify at lower volumes.
    value *= 0.70;
    peak *= 0.85;

    // Apply height-aware visual boost: the CPU scales bars by 0.55 to prevent
    // pinning at normal volume.  When the card grows beyond its default height,
    // u_bar_height_scale > 1.0 stretches bars to fill the extra space while
    // keeping the anti-pinning behaviour at default card size.
    float height_scale = max(1.0, u_bar_height_scale);
    float boosted = value * 1.2 * height_scale;
    if (boosted > 0.95) {
        boosted = 0.95;
    }

    float boosted_peak = peak * 1.2 * height_scale;
    if (boosted_peak > 0.95) {
        boosted_peak = 0.95;
    }

    // --- Slanted profile: compute diagonal clip for inner bar edge ---
    // The inner edge (facing center) gets a diagonal cut.
    // Center bar gets both edges slanted.
    float slant_clip = 0.0;  // extra x-inset at top of bar (0 at bottom)
    bool slant_active = (u_slanted == 1 && bar_width > 4.0);

    // Determine which side faces center for this bar
    int center_bar = bar_count_int / 2;
    bool bar_left_of_center = (bar_index < center_bar);
    bool bar_right_of_center = (bar_index > center_bar);
    bool bar_is_center = (bar_index == center_bar);

    // Linchpin bars: offset 3 from center (bars 8 and 14 in 21-bar)
    // These get BOTH sides slanted lightly as visual anchors
    int bar_offset = abs(bar_index - center_bar);
    // Hardcoded offset 3 — avoids GLSL float→int truncation issues
    bool bar_is_linchpin = (bar_offset == 3);

    // ========== SINGLE PIECE MODE ==========
    // Render solid continuous bars with no segment gaps.
    if (u_single_piece == 1) {
        float base_bottom = inner_bottom;
        float y_rel = base_bottom - fragCoord.y;
        if (y_rel < 0.0) {
            discard;
        }

        float active_height = boosted * inner_height;
        float peak_height = boosted_peak * inner_height;

        // Ensure at least 1px visible baseline
        if (active_height < 1.0 && (u_playing == 1 || value > 0.0)) {
            active_height = 1.0;
        }

        bool is_bar = (y_rel < active_height);
        bool is_ghost = (!is_bar && peak_height > active_height && y_rel < peak_height);

        if (!is_bar && !is_ghost) {
            discard;
        }

        // Slanted clip for single-piece bars
        if (slant_active && active_height > 4.0) {
            float slant_amount = min(bar_width * 0.35, 8.0);
            float y_frac = clamp(y_rel / max(active_height, 1.0), 0.0, 1.0);
            float clip_px = slant_amount * y_frac;
            if (bar_is_center) {
                // Center bar: both edges slanted
                float half_clip = clip_px * 0.5;
                if (bar_local_x < half_clip || bar_local_x > bar_width - half_clip) discard;
            } else if (bar_is_linchpin) {
                // Linchpin bars: both edges slanted lightly (40% strength)
                float lp_clip = clip_px * 0.4;
                if (bar_local_x < lp_clip || bar_local_x > bar_width - lp_clip) discard;
            } else if (bar_left_of_center) {
                // Right edge (facing center) gets diagonal
                if (bar_local_x > bar_width - clip_px) discard;
            } else if (bar_right_of_center) {
                // Left edge (facing center) gets diagonal
                if (bar_local_x < clip_px) discard;
            }
        }

        // Border radius: each shape (bar / ghost) gets its own independent
        // rounding so all tops look consistent regardless of relative heights.
        float br_max = min(u_border_radius, bar_width * 0.5);
        if (br_max > 0.5) {
            float bx_f = bar_local_x;
            float by_f = y_rel;

            if (is_bar) {
                // Round the TOP two corners of the active bar
                float br_bar = (active_height < br_max * 2.0)
                    ? min(br_max, active_height * 0.5) : br_max;
                if (br_bar > 0.5 && by_f > active_height - br_bar) {
                    if (bx_f < br_bar) {
                        float dx = br_bar - bx_f;
                        float dy = by_f - (active_height - br_bar);
                        if (dx * dx + dy * dy > br_bar * br_bar) discard;
                    }
                    if (bx_f > bar_width - br_bar) {
                        float dx = bx_f - (bar_width - br_bar);
                        float dy = by_f - (active_height - br_bar);
                        if (dx * dx + dy * dy > br_bar * br_bar) discard;
                    }
                }
            }

            if (is_ghost) {
                // Round the TOP two corners of the ghost
                float br_ghost = (peak_height < br_max * 2.0)
                    ? min(br_max, peak_height * 0.5) : br_max;
                if (br_ghost > 0.5 && by_f > peak_height - br_ghost) {
                    if (bx_f < br_ghost) {
                        float dx = br_ghost - bx_f;
                        float dy = by_f - (peak_height - br_ghost);
                        if (dx * dx + dy * dy > br_ghost * br_ghost) discard;
                    }
                    if (bx_f > bar_width - br_ghost) {
                        float dx = bx_f - (bar_width - br_ghost);
                        float dy = by_f - (peak_height - br_ghost);
                        if (dx * dx + dy * dy > br_ghost * br_ghost) discard;
                    }
                }
                // Round ghost BOTTOM corners where ghost meets bar top
                if (active_height > 2.0) {
                    float br_bot = (active_height < br_max * 2.0)
                        ? min(br_max, active_height * 0.5) : br_max;
                    if (br_bot > 0.5 && by_f < active_height + br_bot) {
                        if (bx_f < br_bot) {
                            float dx = br_bot - bx_f;
                            float dy = (active_height + br_bot) - by_f;
                            if (dx * dx + dy * dy > br_bot * br_bot) discard;
                        }
                        if (bx_f > bar_width - br_bot) {
                            float dx = bx_f - (bar_width - br_bot);
                            float dy = (active_height + br_bot) - by_f;
                            if (dx * dx + dy * dy > br_bot * br_bot) discard;
                        }
                    }
                }
            }
        }

        vec4 fill = u_fill_color;
        vec4 border = u_border_color;
        fill.a *= u_fade;
        border.a *= u_fade;

        float bw_px = floor(bar_width);
        float bx = floor(bar_local_x);

        if (is_ghost) {
            float ghost_alpha = clamp(u_ghost_alpha, 0.0, 1.0);
            if (ghost_alpha <= 0.0) {
                discard;
            }
            // Smooth fade from bar top to peak top
            float ghost_dist = y_rel - active_height;
            float ghost_span = max(1.0, peak_height - active_height);
            float t = clamp(ghost_dist / ghost_span, 0.0, 1.0);
            float ghost_factor = mix(1.0, 0.15, t);
            vec4 ghost = border;
            ghost.a *= ghost_alpha * ghost_factor;
            fragColor = ghost;
        } else {
            // Border on left/right edges and top edge of the bar
            bool on_border = false;
            if (bw_px <= 2.0) {
                on_border = true;
            } else {
                bool on_side = (bx <= 0.0 || bx >= bw_px - 1.0);
                bool on_top = (y_rel >= active_height - 1.0);
                bool on_bottom = (y_rel < 1.0);
                on_border = on_side || on_top || on_bottom;
            }
            fragColor = on_border ? border : fill;
        }
        return;
    }

    // ========== SEGMENTED MODE ==========
    float total_seg_gap = seg_gap * float(u_segments - 1);
    float seg_height = (inner_height - total_seg_gap) / float(u_segments);
    seg_height = floor(seg_height);
    if (seg_height < 1.0) {
        discard;
    }

    float base_bottom = inner_bottom;
    float step_y = seg_height + seg_gap;
    float y_rel = base_bottom - fragCoord.y;
    if (y_rel < 0.0) {
        discard;
    }

    int seg_index = int(floor(y_rel / step_y));
    if (seg_index < 0) {
        discard;
    }

    // Local Y coordinate within the segment; discard the vertical gap
    // region using a half-open range [0, seg_height).
    float seg_local_y = y_rel - float(seg_index) * step_y;
    if (seg_local_y < 0.0 || seg_local_y >= seg_height) {
        discard;
    }

    // Slanted clip for segmented bars
    if (slant_active && seg_height > 2.0) {
        float slant_amount = min(bar_width * 0.35, 8.0);
        // Use global y position within the bar (not segment-local) for consistent diagonal
        float total_bar_h = float(u_segments) * step_y;
        float y_global_frac = clamp(y_rel / max(total_bar_h, 1.0), 0.0, 1.0);
        float clip_px = slant_amount * y_global_frac;
        if (bar_is_center) {
            float half_clip = clip_px * 0.5;
            if (bar_local_x < half_clip || bar_local_x > bar_width - half_clip) discard;
        } else if (bar_is_linchpin) {
            float lp_clip = clip_px * 0.4;
            if (bar_local_x < lp_clip || bar_local_x > bar_width - lp_clip) discard;
        } else if (bar_left_of_center) {
            if (bar_local_x > bar_width - clip_px) discard;
        } else if (bar_right_of_center) {
            if (bar_local_x < clip_px) discard;
        }
    }

    // Border radius clip for segmented bars (all 4 corners of each segment)
    float br_seg = clamp(u_border_radius, 0.0, min(bar_width * 0.5, seg_height * 0.5));
    if (br_seg > 0.5) {
        float bx_f = bar_local_x;
        float by_f = seg_local_y;
        // Bottom-left corner
        if (bx_f < br_seg && by_f < br_seg) {
            float dx = br_seg - bx_f;
            float dy = br_seg - by_f;
            if (dx * dx + dy * dy > br_seg * br_seg) discard;
        }
        // Bottom-right corner
        if (bx_f > bar_width - br_seg && by_f < br_seg) {
            float dx = bx_f - (bar_width - br_seg);
            float dy = br_seg - by_f;
            if (dx * dx + dy * dy > br_seg * br_seg) discard;
        }
        // Top-left corner
        if (bx_f < br_seg && by_f > seg_height - br_seg) {
            float dx = br_seg - bx_f;
            float dy = by_f - (seg_height - br_seg);
            if (dx * dx + dy * dy > br_seg * br_seg) discard;
        }
        // Top-right corner
        if (bx_f > bar_width - br_seg && by_f > seg_height - br_seg) {
            float dx = bx_f - (bar_width - br_seg);
            float dy = by_f - (seg_height - br_seg);
            if (dx * dx + dy * dy > br_seg * br_seg) discard;
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
        discard;
    }

    float bw_px = floor(bar_width);
    float sh_px = floor(seg_height);
    float bx = floor(bar_local_x);
    float by = floor(seg_local_y);

    bool on_border = false;
    if (is_bar_frag) {
        if (bw_px <= 2.0 || sh_px <= 2.0) {
            on_border = true;
        } else {
            if (bx <= 0.0 || bx >= bw_px - 1.0 || by <= 0.0 || by >= sh_px - 1.0) {
                on_border = true;
            }
        }
    }

    vec4 fill = u_fill_color;
    vec4 border = u_border_color;
    fill.a *= u_fade;
    border.a *= u_fade;

    if (is_ghost_frag) {
        float ghost_alpha = clamp(u_ghost_alpha, 0.0, 1.0);
        if (ghost_alpha <= 0.0) {
            discard;
        }

        float ghost_factor = 1.0;
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
        }

        vec4 ghost = border;
        ghost.a *= ghost_alpha * ghost_factor;
        fragColor = ghost;
    } else {
        fragColor = on_border ? border : fill;
    }
}
