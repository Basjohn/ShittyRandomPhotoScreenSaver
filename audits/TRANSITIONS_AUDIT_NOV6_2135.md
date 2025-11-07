# Transitions Audit - Nov 6, 2025 21:35

## Scope
- System: Transitioning pipeline in rendering/display_widget.py and transitions/*
- Affected transitions: Diffuse, Block Puzzle Flip, Wipe
- Reference: CURRENT_PLAN.md (confirmed failures at 21:28)

## Symptoms (from CURRENT_PLAN)
- Diffuse: Black boxes instead of transparent holes or next-image pieces
- Block Puzzle: Wrong block sizing, flips only a few blocks, biased to top-left
- Wipe: Wrong size/scaling, sits in top-left with black boxing
- Crossfade/Slide are OK

## Transitioning System Overview
1. display_widget.set_image() creates/starts transition with (old_pixmap, new_pixmap, widget)
2. Transitions are responsible for:
   - Creating child labels/canvases sized to the widget
   - Preparing pixmaps for their canvases
   - Driving animation (timer or AnimationManager)
   - Painting/composing frames and cleanup
3. All transitions must operate in widget coordinates and show a widget-fitted representation of images

## Cross-Cutting Findings
- Inconsistent sizing space: Some transitions use pixmap.size() while painting into widget-sized labels
- Widget geometry not guaranteed to match pixmap composition targets
- Alpha usage fragile: CompositionMode_Clear requires ARGB32/ premultiplied targets and a proper source-over pipeline
- Piece extraction often uses original image coordinates; needs pre-scaled widget-fitted copies first
- Label anchoring/geometry defaults to (0,0); without centering/fit everything “leans” top-left

---

## Diffuse Transition - Root Cause & Plan

### Likely Root Causes
- Painter target missing alpha (e.g., RGB32 instead of ARGB32_Premultiplied)
- Composition order: Clearing on the wrong surface or after setting opaque background
- Old/new pixmaps not pre-scaled to widget size; grid computed in widget space but painted with mismatched pixmap
- Label geometry OK but content not scaled (setScaledContents missing or avoided inconsistently)

### Verification/Instrumentation
- Log QPixmap/QImage formats: ensure ARGB32_Premultiplied for the canvas
- Log label geometry vs target pixmap size
- Assert grid covers widget rect exactly
- Toggle a diagnostic that fills background magenta to detect non-alpha areas

### Fix Plan (Step-by-Step)
1. Precompute `old_fitted`, `new_fitted` as widget-sized ARGB32_Premultiplied QPixmaps
2. Ensure canvas QPixmap is ARGB32_Premultiplied; painter composition:
   - Fill with transparent
   - Draw old_fitted normally
   - Set CompositionMode_Clear and punch block rect(s)
   - Set CompositionMode_SourceOver and draw new_fitted beneath or draw new_fitted first then clear from mask overlay as design requires
3. Ensure grid uses widget.width/height; last row/col clamps to edges
4. Ensure display QLabel covers full widget and has transparent background; avoid forcing opaque styles
5. Cleanup via ResourceManager; no immediate `= None`

### Acceptance Criteria
- Holes reveal the new image (no black boxes) across entire surface
- No top-left bias, no edge gaps; blocks fully align on widget bounds

---

## Block Puzzle Flip - Root Cause & Plan

### Likely Root Causes
- Grid rects computed in widget space; pieces cut from unscaled pixmap → wrong sizes and top-left bias
- Pieces not centered: label/composite scene at (0,0) without considering widget/pixmap scale
- Only a subset flips due to flip order vs timer cadence mismatch or early-complete logic

### Verification/Instrumentation
- Log grid rects and confirm cover (0,0)-(w,h)
- Precompute and log `old_fitted.size()` and `new_fitted.size()` equal to widget size
- Render outlines of each block (debug mode) to validate coverage

### Fix Plan (Step-by-Step)
1. Pre-scale old/new to widget-fitted pixmaps (exact size of widget)
2. Extract pieces using widget-space rects from the pre-scaled pixmaps (no additional scaling when painting)
3. Ensure composite canvas equals widget size; clear transparent background each frame
4. Ensure full grid coverage (rows*cols pieces) and flip order iterates all indices
5. Centering: label geometry set to widget rect; no offsets
6. Validate timers/AnimationManager tick so all blocks progress; do not exit early when some complete

### Acceptance Criteria
- Entire widget area participates; no top-left-only flipping
- Blocks are correct size and cover entire widget
- Old→new flip is visually consistent across grid

---

## Wipe Transition - Root Cause & Plan

### Likely Root Causes
- Reveal rectangle computed in pixmap space but applied to widget; mismatch yields top-left placement
- Labels not sized to widget; new label shows pixmap at (0,0) without scaling

### Verification/Instrumentation
- Log widget rect, label geometry, and reveal rect for each frame
- Overlay debug line/rect for wipe position and width

### Fix Plan (Step-by-Step)
1. Pre-scale new image to widget-fitted pixmap; same for old if needed for cross-wipe
2. Ensure labels are sized to widget and aligned at (0,0)
3. Compute reveal rect in widget space; apply to the fitted pixmap
4. Ensure no letterboxing; fill entire widget during/after wipe

### Acceptance Criteria
- Wipe track aligns to widget; no top-left pegging and no black boxing
- Final image fills the widget exactly

---

## Systemic Improvements
- Introduce `TransitionContext` (in BaseTransition):
  - Provides widget-fitted ARGB32_Premultiplied copies for old/new
  - Exposes widget rect, grid helpers, and debug overlay hooks
  - Centralizes alpha-safe painter setup
- Prefer AnimationManager over per-transition QTimers when feasible
- Standardize cleanup via ResourceManager groups per transition instance

---

## Task Breakdown
- Diffuse: alpha & composition pipeline fix
- Block Puzzle: piece extraction from fitted pixmaps; grid coverage; centering; tick cadence
- Wipe: widget-space reveal rect; label sizing/alignment; fitted pixmap usage
- Add TransitionContext helper (non-blocking refactor)
- Add debug overlays (build-time toggle) to validate geometry and coverage

## Acceptance Test Plan
- Single-monitor and multi-monitor runs (2+ DPR values)
- All three transitions with standardized test images (varied aspect ratios)
- No black boxes; no top-left bias; full coverage; correct sizes
- FPS smoothness ≥ 55fps on test rig; no leaks in repeated runs
