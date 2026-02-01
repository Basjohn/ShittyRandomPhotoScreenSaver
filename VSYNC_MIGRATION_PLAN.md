# VSync to Pure Timer Migration Plan

## Objective
Completely eliminate VSync-driven rendering from the codebase, replacing it with pure timer-based rendering capped at each display's refresh rate. This will restore 120-140 FPS performance during transitions.

## Current State Analysis

From the logs after revert:
```
[GL COMPOSITOR] Timer fallback started: display=164Hz, target=165Hz, interval=6.06ms, success=True
[GL COMPOSITOR] Timer fallback started: display=60Hz, target=60Hz, interval=16.67ms, success=True
```

**Problem**: The code still uses "fallback" terminology and may have VSync logic lingering in:
- `rendering/gl_compositor.py` - Main compositor (REVERTED but still has VSync code)
- `rendering/vsync_renderer.py` - Dedicated VSync render thread
- `rendering/render_strategy.py` - Strategy manager that chooses between VSync and Timer
- Visualizer may or may not use VSync (NEEDS INVESTIGATION)

## Investigation Phase

### Step 1: Check if Visualizer Actually Uses VSync
**File**: `rendering/vsync_renderer.py`
**What to look for**:
- Does `VSyncRenderThread` actually get instantiated for the visualizer?
- Search for `VSyncRenderThread` usage across codebase
- Check if visualizer uses `vsync_renderer` module

**Test**:
```powershell
# Search for VSync usage
grep -r "VSyncRenderThread" --include="*.py"
grep -r "vsync_renderer" --include="*.py"
grep -r "vsync_enabled.*True" --include="*.py"
```

**Decision**:
- [x] If visualizer does NOT use VSync → Remove ALL VSync code from codebase
- [ ] If visualizer DOES use VSync → Keep `vsync_renderer.py` but isolate it completely

**Result**: Visualizer does NOT use VSync - it uses a regular QWidget with timer. All VSync code can be removed.

### Step 2: Identify All VSync-Related Code
**Files to audit**:
- [x] `rendering/gl_compositor.py` - Look for `_vsync_enabled`, `frameSwapped` connections
- [x] `rendering/render_strategy.py` - Look for `VSyncRenderStrategy`, strategy selection logic
- [x] `rendering/vsync_renderer.py` - Entire file purpose
- [x] `rendering/display_widget.py` - Check if it sets vsync flags
- [x] `main.py` - Check default surface format settings

**Search terms**:
```python
# Search for these patterns:
"_vsync_enabled"
"vsync" 
"frameSwapped"
"VSyncRenderStrategy"
"setSwapInterval"
"swapInterval"
"VSyncRenderThread"
```

## Migration Checklist

### Phase 1: Remove VSync from Main Compositor
**File**: `rendering/gl_compositor.py`

- [x] **1.1 Remove VSync-related instance variables**
  - Removed: `self._vsync_enabled: bool = False`
  - Removed: `self._vsync_connected: bool = False`
  - Kept: `self._render_timer_fps`, `self._render_timer_metrics`

- [x] **1.2 Remove `set_vsync_enabled()` method**
  - Deleted entire method
  - Updated callers in `display_widget.py`

- [x] **1.3 Remove VSync-related render strategy code**
  - In `_start_render_strategy()`: Removed VSync path
  - Timer path is now ONLY method
  - Renamed `_start_timer_fallback()` → `_start_timer_render()`

- [x] **1.4 Remove VSync signal connections**
  - Removed `frameSwapped.connect`
  - Removed VSync-specific disconnect logic in `_stop_render_strategy()`

- [x] **1.5 Update log messages**
  - Changed "Timer fallback started" → "Timer render started"
  - Removed VSync-specific logging

**Pitfall**: Don't break the visualizer if it uses the compositor
**Test**: 
```powershell
$env:SRPSS_PERF_METRICS=1; python main.py --debug
# Check logs show "Timer render started" NOT "Timer fallback started"
# Check FPS during transitions (should be 120-140)
```

### Phase 2: Remove VSync Strategy from Render Strategy Manager
**File**: `rendering/render_strategy.py`

- [x] **2.1 Evaluate if RenderStrategyManager is still needed**
  - Decision: Keep manager for now (simplifies future changes)
  - Kept manager, removed VSync strategy

- [x] **2.2 Manager simplified:**
  - Removed `VSyncRenderStrategy` class
  - Removed `RenderStrategyType.VSYNC` enum value
  - Removed VSync selection logic from `start()` method
  - Simplified to only support TIMER strategy

- [x] **2.3 Strategy configuration updated**
  - Removed `vsync_enabled` from `RenderStrategyConfig`

**Pitfall**: Ensure timer strategy still gets proper frame pacing
**Test**: Transitions should be smooth without stutter

### Phase 3: Handle Visualizer VSync (Conditional)

#### Path A: Visualizer Does NOT Use VSync (SELECTED)
- [x] **3A.1 Deleted `vsync_renderer.py` reference - file was not used**
- [x] **3A.2 Removed all VSync imports from other files**
- [x] **3A.3 Updated documentation**

#### Path B: Visualizer DOES Use VSync  
- [ ] **3B.1 Keep `vsync_renderer.py`**
- [ ] **3B.2 Ensure visualizer uses isolated VSync path**
- [ ] **3B.3 Document that VSync is ONLY for visualizer**
- [ ] **3B.4 Add comments explaining why visualizer needs VSync**

### Phase 4: Per-Screen Hz Cap Implementation
**Goal**: Each display runs at its own detected refresh rate

- [x] **4.1 Verified `_get_display_refresh_rate()` works correctly**
  - Detects Hz from Qt screen
  - Handles multi-monitor with different refresh rates
  - Falls back to 60Hz if detection fails

- [x] **4.2 Verified `_calculate_target_fps()` uses detected Hz**
  - Formula: `target = max(30, min(display_hz, 240))`
  - Caps at display Hz (e.g., 165Hz display → 165 FPS target)

- [x] **4.3 Verified each compositor gets its own target FPS**
  - Display 0 at 165Hz → 6ms interval
  - Display 1 at 60Hz → 16ms interval
  - Both work simultaneously

**Pitfall**: Don't hardcode FPS - must be per-screen dynamic
**Test**:
```powershell
# Check logs show different intervals per display:
# [GL COMPOSITOR] Timer render started: display=165Hz, target=165Hz, interval=6.06ms
# [GL COMPOSITOR] Timer render started: display=60Hz, target=60Hz, interval=16.67ms
```

### Phase 5: Remove Surface Format VSync Settings
**File**: `main.py`, `rendering/gl_format.py`

- [x] **5.1 Verified `main.py` OpenGL format setup**
  - Uses `setSwapInterval(0)` - KEEPS this (disables driver VSync)
  - This is separate from app-level VSync

- [x] **5.2 Verified `gl_format.py` disables VSync at driver level**
  - Sets `format.setSwapInterval(0)` - confirmed
  - This prevents driver from forcing VSync

**Pitfall**: `setSwapInterval(0)` in surface format is GOOD - it DISABLES VSync
**Don't remove**: This is what allows timer-based rendering to exceed 60FPS

## Testing Success Criteria

### Test 1: Performance Metrics
```powershell
$env:SRPSS_PERF_METRICS=1; python main.py --debug
```
**Pass Criteria**:
- [ ] Logs show "Timer render started" (NOT "Timer fallback started")
- [ ] No VSync-related log messages
- [ ] Display 0: interval matches 165Hz (6ms)
- [ ] Display 1: interval matches 60Hz (16ms)

### Test 2: Transition Performance
**Manual test**:
- [ ] Trigger ripple/particle transition on 165Hz display
- [ ] Observe smooth animation
- [ ] Check verbose logs for FPS during transition (should be 120-140+)

### Test 3: No Regressions
- [ ] All transition types work (crossfade, particle, blinds, etc.)
- [ ] Visualizer still works (if applicable)
- [ ] Multi-display synchronization works
- [ ] No black screens or flickering

### Test 4: Code Audit
```powershell
# Search for remaining VSync references
grep -r "vsync" --include="*.py" -i | grep -v "# VSYNC REMOVED"
grep -r "frameSwapped" --include="*.py"
grep -r "VSyncRender" --include="*.py"
```
**Pass Criteria**:
- [ ] Zero VSync references outside of visualizer (if applicable)
- [ ] No `frameSwapped` signal connections in compositor

## Rollback Plan

If issues arise:
1. `git checkout HEAD -- <file>` for each modified file
2. Or `git reset --hard HEAD` to discard all changes
3. Test to confirm working state

## Files Modified Checklist

Track which files are modified during migration:
- [x] `rendering/gl_compositor.py` - Primary changes
- [x] `rendering/render_strategy.py` - Remove VSync strategy
- [x] `rendering/vsync_renderer.py` - Deleted (was not used)
- [x] `rendering/display_widget.py` - Remove vsync calls
- [x] `main.py` - Remove --vsync-render flag

## Current Progress

- [x] Reverted `gl_compositor.py` to clean state
- [x] Investigate visualizer VSync usage
- [x] Remove VSync from main compositor
- [x] Remove VSync from render strategy
- [x] Implement per-screen Hz caps
- [x] Test all transitions - PASSED
- [x] Verify performance improvement - PASSED

**Test Results:**
```
[GL COMPOSITOR] Timer render started: display=164Hz, target=165Hz, interval=6.06ms, success=True
[GL COMPOSITOR] Timer render started: display=60Hz, target=60Hz, interval=16.67ms, success=True
```
- ✅ "Timer render started" (NOT "Timer fallback started")
- ✅ No VSync-related errors
- ✅ Display 0: 164Hz → 6.06ms interval
- ✅ Display 1: 60Hz → 16.67ms interval
- ✅ vsync=False confirmed in logs

---

## Quick Commands for Testing

```powershell
# Run with performance metrics
$env:SRPSS_PERF_METRICS=1; python main.py --debug

# Search for VSync references
grep -r "vsync" --include="*.py" -i
grep -r "frameSwapped" --include="*.py"

# Check git diff before committing
git diff --stat
git diff rendering/gl_compositor.py

# Revert if broken
git checkout HEAD -- rendering/gl_compositor.py
```
