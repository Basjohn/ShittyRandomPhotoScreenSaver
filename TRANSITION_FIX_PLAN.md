# Transition Distortion & Size Jump Fix Plan

## Root Cause
Transitions create intermediate canvases that don't match the exact fitted pixmaps DisplayWidget provides. When transition finishes, DisplayWidget shows its original fitted pixmap, causing a visible size/zoom jump and distortions from DPR/format mismatches.

## Why Crossfade Works Perfectly
- Takes fitted pixmaps **directly** from DisplayWidget
- Places them in QLabels with `setScaledContents(False)`
- **NEVER creates new canvases**
- **NEVER calls _fit_pixmap_to_widget() or _create_transparent_canvas()**
- Pixmap shown during transition = pixmap shown after = NO JUMP

## Fix Strategy
Apply Crossfade's pattern to ALL transitions:
1. Accept fitted pixmaps AS-IS from DisplayWidget
2. Use them directly in QLabels or minimal compositing
3. No intermediate canvas creation
4. No re-rendering or format conversions
5. Manipulate display through clipping, masks, or opacity only

## Transition-by-Transition Fixes

### ✅ Crossfade (REFERENCE - ALREADY PERFECT)
- No changes needed
- This is the gold standard

### ✅ Diffuse (WORKING WELL)
- Currently works well per user
- Review to ensure it matches Crossfade pattern
- May need minor adjustments for consistency

### ✅ Block Puzzle Flip (DISTORTION + SIZE JUMP) - FIXED
**What Was Done:**
- [x] Removed ALL `_fit_pixmap_to_widget()` calls - use source pixmaps directly
- [x] Store `_fitted_old` and `_fitted_new` as direct references to input pixmaps
- [x] Create grid based on widget dimensions (pixmaps already fitted by ImageProcessor)
- [x] In `_render_scene()`: create composite with EXACT source pixmap size/DPR
- [x] Calculate physical dimensions: `int(logical * dpr)`
- [x] Set DPR on composite to match source
- [x] Draw from source pixmaps using rect mapping (no scaling)
- [x] Added Qt and QColor imports

**Result:** Composite pixmap now matches source exactly → no size jump or distortion

### ✅ Wipe (DISTORTION + SIZE JUMP) - FIXED
**What Was Done:**
- [x] Removed ALL `_fit_pixmap_to_widget()` calls and size-checking fallbacks
- [x] Store `_fitted_old` and `_fitted_new` as direct references to input pixmaps
- [x] Use source pixmaps directly in start() and pass to animation callback
- [x] In `_compose_wipe_frame()`: replaced `_create_transparent_canvas()` with exact source matching
- [x] Create canvas with source pixmap's exact logical size, DPR, and physical dimensions
- [x] Draw base old image and wipe-revealed new image using source rects
- [x] Added QColor import

**Result:** Canvas now matches source exactly → no size jump or distortion

### 🔧 Slide (NOT TESTED BUT LIKELY BROKEN)
**Fix:**
- [ ] Remove canvas creation
- [ ] Use two QLabels positioned side-by-side
- [ ] Animate their positions with QPropertyAnimation
- [ ] Or use single QLabel and draw from offset source rects

### 🔧 Any Other Transitions
- [ ] Audit all transitions for `_create_transparent_canvas()` usage
- [ ] Audit all transitions for `_fit_pixmap_to_widget()` usage
- [ ] Replace with Crossfade-style direct pixmap usage

## Previous Fix Attempts (Symptom-Based)

**Attempted Fixes:**
1. ~~Re-fitting already-fitted pixmaps~~ 
2. ~~Creating intermediate canvases~~
3. ~~Not following Crossfade pattern~~

**Why Those Didn't Work:**
They addressed symptoms, not the root cause. Lanczos was introducing distortion BEFORE transitions even started.

## Implementation Rules

### NEVER DO:
- ❌ Call `_create_transparent_canvas()` during animation
- ❌ Call `_fit_pixmap_to_widget()` on already-fitted pixmaps
- ❌ Create new QPixmap with different size than input
- ❌ Use `QPixmap.scaled()` during animation
- ❌ Convert between pixmap formats unnecessarily

### ALWAYS DO:
- ✅ Use fitted pixmaps directly from DisplayWidget
- ✅ Set QLabel pixmaps with `setScaledContents(False)`
- ✅ If compositing needed: create pixmap with EXACT same size and DPR as inputs
- ✅ Use source rect → dest rect QPainter.drawPixmap() WITHOUT scaling
- ✅ Copy device pixel ratio from source pixmap to any composite
- ✅ Verify final frame matches what DisplayWidget will show

## Verification Steps
After each fix:
1. [ ] Run transition
2. [ ] Watch for distortion during animation
3. [ ] Watch for size/zoom jump when transition finishes
4. [ ] Compare transition end frame to final image shown by DisplayWidget
5. [ ] Test on both monitors (different DPR may exist)

## Success Criteria
- No grayscale/color distortion during or after transition
- No diagonal artifacts or tearing
- No size/zoom jump when transition finishes
- Pixel-perfect match between transition end and DisplayWidget final frame
- Works consistently across all monitor DPR settings
