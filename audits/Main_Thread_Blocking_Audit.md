# Main Thread Blocking Operations Audit
**Date:** Jan 5, 2026  
**Goal:** Identify ALL operations that could cause frame spikes on main thread

---

## Critical Findings (Production Code)

### 1. ⚠️ Prefetch UI Warmup - QPixmap.fromImage on Main Thread
**File:** `engine/screensaver_engine.py`  
**Lines:** 1196-1207  
**Severity:** HIGH - Causes 10-30ms spikes during prefetch  
**Current Code:**
```python
def _ui_convert():
    cached = self._image_cache.get(first)
    if isinstance(cached, QImage):
        pm = QPixmap.fromImage(cached)  # ← MAIN THREAD BLOCKING
        if not pm.isNull():
            self._image_cache.put(first, pm)
self.thread_manager.run_on_ui_thread(_ui_convert)
```
**Status:** 🔴 **NEEDS FIX** - Move to compute pool

---

### 2. ⚠️ Shadow Rendering - Synchronous QImage Creation + Blur
**File:** `widgets/painter_shadow.py`  
**Lines:** 307-372  
**Severity:** MEDIUM - Causes 5-15ms spikes during widget init/resize  
**Operations:**
- `QImage()` creation (line 340)
- `QPainter` drawing on QImage (lines 344-362)
- `_apply_blur()` - Gaussian blur (line 366)
- `QPixmap.fromImage()` (line 368)

**Status:** 🔴 **NEEDS FIX** - Add async variant with caching

---

### 3. ⚠️ Image Prefetcher - Direct QImage Load
**File:** `utils/image_prefetcher.py`  
**Lines:** 69-74  
**Severity:** LOW - Already on IO thread, but could use ImageWorker  
**Current Code:**
```python
def _load_qimage(p: str) -> Optional[QImage]:
    img = QImage(p)  # ← Blocking decode
    if img.isNull():
        logger.warning(f"Prefetch decode failed for: {p}")
        return None
```
**Status:** 🟡 **ACCEPTABLE** - Already on IO thread via `submit_io_task()`

---

### 4. ✅ Main Image Loading - Already Async
**File:** `engine/screensaver_engine.py`  
**Lines:** 2023-2251  
**Status:** ✅ **GOOD** - Uses ImageWorker process, QPixmap.fromImage on worker thread

---

### 5. ✅ Image Processing - Already Async
**File:** `rendering/image_processor_async.py`  
**Status:** ✅ **GOOD** - All operations on QImage, runs on compute pool

---

## Non-Critical Findings (UI/Test Code)

### Reddit Logo Loading
**File:** `widgets/reddit_widget.py:1232`  
**Status:** 🟢 **ACCEPTABLE** - One-time load during init, small image

### Media Widget Artwork
**File:** `widgets/media_widget.py:895`  
**Status:** 🟢 **ACCEPTABLE** - Small artwork images, infrequent updates

### Settings Dialog Logos
**File:** `ui/settings_dialog.py:916, 931`  
**Status:** 🟢 **ACCEPTABLE** - One-time load during dialog open

### Test Fixtures
**Files:** Multiple test files  
**Status:** 🟢 **ACCEPTABLE** - Test code only

---

## Operations Already Optimized

### ✅ Main Image Pipeline
1. **ImageWorker** - Separate process for decode/prescale
2. **AsyncImageProcessor** - QImage operations on compute pool
3. **QPixmap.fromImage** - On worker thread (Qt 6 allows this)
4. **Pre-scale computation** - On compute pool

### ✅ Threading Architecture
- **ThreadManager** - Centralized async operations
- **IO Pool** - File operations
- **Compute Pool** - CPU-intensive work
- **UI Thread** - Only final GL operations

---

## Summary

| Issue | Severity | Location | Status |
|-------|----------|----------|--------|
| Prefetch UI warmup | HIGH | screensaver_engine.py:1196-1207 | 🔴 Fix Required |
| Shadow rendering | MEDIUM | painter_shadow.py:307-372 | 🔴 Fix Required |
| Image prefetcher | LOW | image_prefetcher.py:69-74 | 🟡 Acceptable |
| Reddit logo | LOW | reddit_widget.py:1232 | 🟢 Acceptable |
| Media artwork | LOW | media_widget.py:895 | 🟢 Acceptable |
| Settings logos | LOW | settings_dialog.py:916,931 | 🟢 Acceptable |

---

## Recommended Fixes

### Priority 1: Prefetch UI Warmup
**Impact:** 10-30ms spike reduction  
**Effort:** Low (30 minutes)  
**Risk:** Low

### Priority 2: Shadow Rendering
**Impact:** 5-15ms spike reduction  
**Effort:** Medium (2 hours)  
**Risk:** Medium (caching strategy)

### Priority 3: Image Prefetcher Enhancement
**Impact:** 5-10ms spike reduction  
**Effort:** Medium (1 hour)  
**Risk:** Low

---

## Expected Results After Fixes

| Metric | Current | After P1 | After P1+P2 | Target |
|--------|---------|----------|-------------|--------|
| dt_max | 65-69ms | 55-59ms | 45-50ms | <20ms |
| Spike frequency | Occasional | Rare | Very Rare | None |

**Note:** These fixes alone may not reach <20ms target. Solution 1 (VSync-driven) may be required for final push.
