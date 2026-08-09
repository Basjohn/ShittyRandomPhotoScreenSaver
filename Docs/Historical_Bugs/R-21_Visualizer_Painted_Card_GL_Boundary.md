# R-21 — 2026-05-04 — Visualizer Painted-Card GL Content Escaping Card Boundary (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] ACTIVE
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Symptom:** When painted-card shadows are enabled, GL-rendered visualizer content (all real modes: Spectrum, DevCurve, Sine, Blob, Bubble, Oscilloscope) visibly escapes the painted card boundary at the right, bottom, and rounded-corner edges. The bleed was ~1px on sides/corners and ~1.5px on right/bottom, with the top-right corner being the worst.

- **Surface-level root cause (2026-05-03):** The `SpotifyBarsGLOverlay` receives the full `vis.geometry()` rect. The painted card is inset by `card_shrink_right/bottom` (11px each), but the GL overlay renders into the full widget rect, extending past the visible card edge.

- **True root cause (2026-05-04):** The initial stencil mask matched the card *fill* rect (inset by 1 logical px via `.adjusted(1.0, 1.0, -1.0, -1.0)`). However, the card border is drawn with a centred pen stroke (`border_width = 3px` from `BaseOverlayWidget.get_global_border_width()`). The mask was therefore bleeding over the inner ~1.5px of the border stroke. The apparent "all sides" bleed was the stencil mask being exactly flush with the card path instead of inside it.

- **Failed approaches (DO NOT REATTEMPT):**
  1. **Rect shrink in `display_image_ops.py`** (2026-05-03/04): Adjusted `geom` with `geom.adjusted(0, 0, -shrink_r, -shrink_b)` before passing to the GL overlay. **Why it failed:** This shrinks the visualizer *content* instead of *clipping* it. The content is rendered at a smaller size, which changes authored mode behavior (amplitude, curve scale, bar widths). It also only covered the prewarm path, not the per-tick `push_spotify_visualizer_frame` path. **Reverted 2026-05-04.**
  2. **QPainter clip path in `SpotifyVisualizerWidget.paintEvent`** (2026-05-03): Added a `QPainterPath` rounded-rect clip before CPU bar painting. **Why it failed:** Only affects `QPainter`-drawn content. GL overlay renders via `QOpenGLWidget.paintGL()` in a separate pipeline — the `QPainter` clip path has zero effect on GL output. The majority of real modes are GL-rendered. **Reverted 2026-05-04.**
  3. **QPainter in `resizeEvent`** (2026-05-03): Attempted to draw the shadow pixmap from `resizeEvent`. **Why it failed:** Painting outside `paintEvent` is invalid in Qt and produces `QPainter::paintEngine: Should no longer be called` errors. **Reverted 2026-05-03.**

- **Side effects of failed fixes:**
  - The combined shrink + clip changes caused the media control bar to shift lower when in bottom-right position. Traced to `MediaWidget._update_stylesheet()` not being painted-card-shadow-aware, causing double-painting of card background. This was a separate bug exposed during investigation but NOT caused by the shrink/clip code itself. Fixed separately.

- **Fix implemented (2026-05-04):**
  - Rounded-rect **stencil mask** in `SpotifyBarsGLOverlay.paintGL()` clips GL fragments to the visible card boundary (including rounded corners).
  - Two-pass approach per frame:
    1. Mask pass: color writes disabled, stencil writes 1 inside the card rounded rect via a dedicated SDF shader (`roundedRectSDF`).
    2. Visualizer pass: stencil test `GL_EQUAL 1` so only fragments inside the card shape are drawn.
  - Card bounds derived from `PAINTED_FRAME_SHADOW_TUNING` (`card_shrink_right`, `card_shrink_bottom`) plus corner radius `8 + radius_extra`.
  - **Critical correction:** The mask receives an additional inset of `border_width_px * 0.5 * dpr` so the visualizer stays inside the inner edge of the centred pen stroke, not flush with the card path. The radius uniform is reduced by the same amount.
  - `rendering/display_image_ops.py` now passes `border_width_px=vis._border_width` to `set_state` so the mask can compute the correct inset.
  - No content size, amplitude, curve scale, or authored mode behavior changes. Visualizer shaders untouched.
  - The QPainter fallback path (`_render_with_qpainter`) was removed as dead code.

- **Verification:**
  - `tests/test_stencil_mask_alignment.py` passes: zero bleed, correct corner rounding, zero-radius rectangle parity, and documented bleed when inset is omitted.
  - Runtime validation confirmed no visible bleed at card edges or corners across all modes.

- **Guardrails:**
  - Do not attempt rect-shrink or QPainter-clip approaches for this bug family again.
  - The mask inset must account for both the 1-px painted-frame shadow inset (`inset=1.0`) AND the centred card border width (`border_width/2`).

## Record Provenance

This standalone file preserves the complete former inline `R-21` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
