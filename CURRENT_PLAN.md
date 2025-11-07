# CURRENT PLAN

**Updated**: Nov 7, 2025 02:59  
**Status**: ⚠️ LANCZOS DISABLED - NEEDS TESTING

---

## 🔥 CRITICAL: TRANSITION SIZE/ZOOM JUMP - ROOT CAUSE ANALYSIS

**Problem:**
- Crossfade and Diffuse work perfectly
- Block Puzzle, Wipe, Slide all have size/zoom jump when transition finishes
- Lanczos causes distortion artifacts

**Theories Tested:**
1. ❌ DPR handling (physical vs logical dimensions) - Code was already correct
2. ✅ Lanczos distortion - Disabled, but doesn't fix zoom jump
3. ❓ **Possible**: Transition composite creation during animation differs from final pixmap

**Fixes Applied:**
- [x] Disabled Lanczos scaling globally (prevents distortion artifacts)
- [x] Fixed QTimer cleanup error in screensaver_engine.py
- [x] Removed unused ImageEnhance import
- [x] Verified DPR handling is correct (physical dimensions + setDevicePixelRatio)

**Why Crossfade/Diffuse Work:**
- **Crossfade**: QLabel with direct pixmap, no compositing during animation
- **Diffuse**: QLabel with mask/transparency, no size changes during animation
- **Block/Wipe/Slide**: Create new composites each frame → may have subtle size differences

**Next Investigation Needed:**
- Compare exact pixel dimensions of transition composites vs DisplayWidget.current_pixmap
- Check if QLabel centering with setScaledContents(False) causes sub-pixel shifts
- Verify all transitions receive same fitted pixmap from DisplayWidget

**Test Checklist:**
- [ ] Block Puzzle Flip: No zoom/size jump after transition
- [ ] Wipe: No zoom/size jump after transition
- [ ] Slide: No zoom/size jump after transition (should already work)
- [ ] All transitions: Final frame matches exactly
- [ ] No QTimer cleanup errors on exit

---

## 🧪 PREVIOUS TRANSITIONS WORK – NEEDS RE-TESTING

### AUDIT WORK (Nov 6, 21:00-21:30) - 48/63 Issues Fixed
**What Was Fixed:**
- ✅ Memory leaks (20+ locations)
- ✅ Thread safety (ImageQueue, loading flags)
- ✅ Undefined attributes (3 transitions)
- ✅ ResourceManager integration (all transitions)
- ✅ Import organization (10 files)
- ✅ Code quality (unused variables, f-strings)
- ✅ Division by zero (10 locations)
- ✅ Lambda closures (3 files)
- ✅ Python 3.7+ compatibility

**What Was Changed (pending verification):**
- Diffuse uses AnimationManager + widget-fitted pixmaps, alpha-safe clear composition, DPI-aware canvases.
- Block Puzzle Flip uses AnimationManager + fitted pixmaps, full grid coverage, DPI-aware composite.
- Wipe uses AnimationManager + fitted pixmaps, widget-space clip on DPI-aware canvas.

**Test Checklist:**
- [ ] Diffuse shows across full widget, no top-left quadrant bias, no black boxing.
- [ ] Block Puzzle blocks cover entire widget, flips not biased to top-left, ends on full image.
- [ ] Wipe reveals in correct direction, no letterbox/black box, final frame is fitted_new.
- [ ] No diagonal skew/colour distortion or grayscale frames during/after transitions.

### Original Root Cause Theory (Nov 6, 19:45)
**Problem**: Transitions received **130% pan-scaled pixmaps** but operated on **screen-sized widgets**

**Previous Fix Attempt**: 
- Removed pan-scaled pixmap handoff to transitions
- Pan & scan scaling happens AFTER transition finishes

**RESULT**: ❌ **VISUAL BUGS STILL PRESENT** - Fix did not resolve issues

---

## ✅ ALSO FIXED

1. **Mouse Movement Error**
   - Added missing `_initial_mouse_pos` initialization
   - Lines 71-72 in display_widget.py

2. **C Key Cycling**
   - Now syncs with current transition in settings
   - Pressing C will cycle from current → next
   - File: `engine/screensaver_engine.py` lines 88-93

---

## ⚠️ PRIOR TEST RESULT (21:28)
- These were the last observed issues before refactor: Diffuse black boxes, Block Puzzle sizing + top-left bias, Wipe size/top-left bias. Crossfade/Slide OK.

**Architecture is solid, visuals are broken**

---

## 📝 Changes Made

### Architecture Fixes (Nov 6, 21:00-21:30)
**13 Files Modified:**
- engine/screensaver_engine.py - Memory leaks, thread safety, unused code
- engine/image_queue.py - Full thread safety, O(1) previous(), removed unused
- rendering/display_widget.py - ResourceManager, hotkey policy
- rendering/image_processor.py - Division by zero, imports
- rendering/pan_and_scan.py - Division by zero, imports, memory leak
- transitions/* (5 files) - ResourceManager integration, memory leaks, imports
- core/animation/animator.py - Lambda closure, cleanup method
- core/threading/manager.py - Python 3.7+, logging, unused imports
- sources/rss_source.py - Import organization

### Transition Runtime Policy
- ✅ Single-skip policy: if a transition is running, incoming set_image during that window is skipped.

### Previous Changes (Nov 6, 19:45)
**rendering/display_widget.py**
- Removed pan-scaled pixmap handoff to transitions (lines 310-322)
- Added `_initial_mouse_pos` and `_mouse_move_threshold` initialization (lines 71-72)

**engine/screensaver_engine.py**
- Sync transition cycle index with settings on startup (lines 88-93)

---

## 🔍 Known Issues

### Lint Warnings (Cleaned Up)
- ✅ Fixed most lint warnings during audit work
- ✅ Removed unused imports across 10 files
- ✅ Fixed f-strings without placeholders

### CRITICAL: Transition Visual Bugs
- ❌ **Diffuse** - Black boxes rendering issue
- ❌ **Block Puzzle** - Sizing calculation broken
- ❌ **Wipe** - Size/scale issues

**These require separate investigation of rendering logic, not architecture**

---

## ☑️ Remaining Non‑Critical Issues (15)

### image_queue.py (6)
- [ ] History path matching edge case (line 147)
- [ ] History growth (bounded by maxlen but verify policy)
- [ ] Rebuild logic duplication (106-108 vs 191-198)
- [ ] Empty images after clear edge case (239-250)
- [ ] Method naming inconsistency (cosmetic)
- [ ] Current index stat accuracy (315-322, 334)

### settings_manager.py (3)
- [ ] Change handler exceptions (122-127) — currently logged only
- [ ] Defaults not updated (88-90) — clarify intended behavior
- [ ] Value types validation (116) — tighten if needed

### image_processor.py (4)
- [ ] PIL data buffer lifetime (132-138)
- [ ] FIT rounding guard (265-272) — confirm correctness
- [ ] Duplicate division in scale calc — reduce repetition
- [ ] Null checks around pixmap ops (177-232)

### display_widget.py (1)
- [ ] Transition cleanup race (330-337, 507-514)

### base_provider.py / folder_source.py (1)
- [ ] Path existence check (base_provider:72) / timer note in folder_source
