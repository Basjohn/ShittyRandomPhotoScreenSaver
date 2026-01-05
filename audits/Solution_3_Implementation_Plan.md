# Solution 3: Comprehensive Worker Offloading Implementation Plan
**Date:** Jan 5, 2026  
**Goal:** Move ALL spike-prone operations off main thread to achieve dt_max <20ms

---

## Current Spike Sources (Identified)

### 1. QPixmap.fromImage Conversions
**Location:** `engine/screensaver_engine.py:2136, 2148`  
**Status:** ✅ **ALREADY ON WORKER THREAD** (Qt 6 allows this)  
**Evidence:** Lines 2133-2151 show conversions happening in `_do_load_and_process()` which runs on compute pool

### 2. Prefetch UI Warmup
**Location:** `engine/screensaver_engine.py:1196-1207`  
**Status:** ⚠️ **ON UI THREAD** via `run_on_ui_thread()`  
**Issue:** QPixmap.fromImage called on main thread during prefetch  
**Fix Required:** Move to compute pool, only invoke UI thread for cache storage

### 3. Shadow Rendering
**Location:** `widgets/painter_shadow.py:307-372`  
**Status:** ⚠️ **SYNCHRONOUS** - Creates QImage, applies blur, converts to QPixmap  
**Issue:** Called during widget initialization/resize on main thread  
**Fix Required:** Pre-render shadows on worker thread, cache results

### 4. Image Processor Lanczos Scaling
**Location:** `rendering/image_processor.py:57-175`  
**Status:** ✅ **ALREADY ASYNC** via AsyncImageProcessor  
**Evidence:** ImageProcessor delegates to AsyncImageProcessor.process_qimage

### 5. Pre-scale Computation
**Location:** `engine/screensaver_engine.py:1224-1250`  
**Status:** ✅ **ALREADY ON COMPUTE POOL**  
**Evidence:** Uses `submit_compute_task()` for scaling

---

## Implementation Tasks

### Task 1: Fix Prefetch UI Warmup ⚠️ HIGH PRIORITY
**Problem:** QPixmap.fromImage on main thread during prefetch warmup

**Current Code (screensaver_engine.py:1196-1207):**
```python
def _ui_convert():
    try:
        from PySide6.QtGui import QPixmap, QImage
        cached = self._image_cache.get(first)
        if isinstance(cached, QImage):
            pm = QPixmap.fromImage(cached)  # ← MAIN THREAD BLOCKING
            if not pm.isNull():
                self._image_cache.put(first, pm)
                logger.debug(f"UI warmup: cached QPixmap for {first}")
    except Exception as e:
        logger.debug(f"UI warmup failed for {first}: {e}")
self.thread_manager.run_on_ui_thread(_ui_convert)
```

**Fix:**
```python
def _compute_convert():
    """Compute pool: Convert QImage to QPixmap (Qt 6 allows this)"""
    try:
        from PySide6.QtGui import QPixmap, QImage
        cached = self._image_cache.get(first)
        if isinstance(cached, QImage):
            pm = QPixmap.fromImage(cached)  # ← WORKER THREAD
            if not pm.isNull():
                return (first, pm)
    except Exception as e:
        logger.debug(f"Prefetch convert failed for {first}: {e}")
    return None

def _ui_cache(result):
    """UI thread: Store result in cache"""
    if result and result.success and result.result:
        path, pixmap = result.result
        self._image_cache.put(path, pixmap)
        logger.debug(f"Prefetch warmup: cached QPixmap for {path}")

self.thread_manager.submit_compute_task(
    _compute_convert,
    callback=lambda r: self.thread_manager.run_on_ui_thread(lambda: _ui_cache(r))
)
```

**Files to Modify:**
- `engine/screensaver_engine.py` lines 1196-1207

**Expected Impact:** Eliminate 10-30ms spikes during prefetch

---

### Task 2: Async Shadow Rendering ⚠️ MEDIUM PRIORITY
**Problem:** Shadow rendering blocks main thread during widget init/resize

**Current Code (painter_shadow.py:307-372):**
```python
@classmethod
def _render_shadow_pixmap(cls, size: QSize, config: ShadowConfig, corner_radius: int = 0) -> Optional[QPixmap]:
    # Create QImage
    shadow_img = QImage(img_width, img_height, QImage.Format.Format_ARGB32_Premultiplied)
    # Draw shape
    shape_painter = QPainter(shadow_img)
    # ... drawing code ...
    # Apply blur
    if blur > 0:
        shadow_img = cls._apply_blur(shadow_img, blur)  # ← BLOCKING
    return QPixmap.fromImage(shadow_img)  # ← MAIN THREAD
```

**Fix Strategy:**
1. Add async variant: `_render_shadow_pixmap_async()`
2. Pre-render common shadow sizes on startup
3. Cache results in memory
4. Fall back to sync for uncommon sizes

**Implementation:**
```python
# Add to PainterShadow class
_shadow_cache: Dict[Tuple[QSize, int, int], QPixmap] = {}  # (size, blur, corner) -> pixmap
_shadow_cache_lock = threading.Lock()

@classmethod
def render_shadow_async(
    cls,
    size: QSize,
    config: ShadowConfig,
    corner_radius: int = 0,
    callback: Optional[Callable[[QPixmap], None]] = None
) -> Optional[QPixmap]:
    """Async shadow rendering with cache.
    
    Returns cached shadow immediately if available, otherwise
    submits to worker thread and calls callback when ready.
    """
    cache_key = (size, int(config.blur_radius), corner_radius)
    
    # Check cache first
    with cls._shadow_cache_lock:
        if cache_key in cls._shadow_cache:
            return cls._shadow_cache[cache_key]
    
    # Not cached - render async
    def _render_worker():
        pixmap = cls._render_shadow_pixmap(size, config, corner_radius)
        if pixmap:
            with cls._shadow_cache_lock:
                cls._shadow_cache[cache_key] = pixmap
        return pixmap
    
    # Submit to compute pool
    from core.threading.manager import ThreadManager
    thread_mgr = ThreadManager()
    
    def _on_complete(result):
        if result and result.success and callback:
            callback(result.result)
    
    thread_mgr.submit_compute_task(_render_worker, callback=_on_complete)
    return None  # Will be available via callback
```

**Files to Modify:**
- `widgets/painter_shadow.py` - Add async rendering + cache
- Widget classes using shadows - Update to use async variant

**Expected Impact:** Eliminate 5-15ms spikes during widget creation/resize

---

### Task 3: Audit All Main Thread Operations ⚠️ HIGH PRIORITY
**Goal:** Find ANY remaining blocking operations on main thread

**Search Targets:**
1. All `QPixmap(path)` direct loads
2. All `QImage(path)` direct loads
3. All `QPixmap.fromImage()` on main thread
4. All PIL operations on main thread
5. All file I/O on main thread
6. All network operations on main thread

**Method:**
```bash
# Search for direct QPixmap loads
rg "QPixmap\(['\"]" --type py

# Search for direct QImage loads
rg "QImage\(['\"]" --type py

# Search for fromImage not in worker context
rg "fromImage" --type py -A 5 -B 5

# Search for file operations
rg "open\(|Path\(.*\)\.read|\.read_text" --type py

# Search for network operations
rg "requests\.|urllib|http\." --type py
```

**Action:** Create audit document listing ALL findings with line numbers

---

### Task 4: Event Loop Optimization 🔶 LOW PRIORITY
**Goal:** Minimize event processing overhead between frames

**Strategies:**
1. Batch Qt events where possible
2. Defer non-critical updates during transitions
3. Use `QCoreApplication.processEvents()` sparingly
4. Consolidate timer callbacks

**Investigation Required:** Profile event loop to identify hot spots

---

### Task 5: Texture Upload Optimization 🔶 RESEARCH NEEDED
**Goal:** Investigate if texture uploads can be moved to worker thread

**Current:** Texture uploads happen in `paintGL()` on main thread  
**Question:** Can we use PBOs (Pixel Buffer Objects) for async upload?

**Research:**
- Qt's QOpenGLPixelTransferOptions
- OpenGL PBO for async texture upload
- Whether Qt's GL wrapper supports this

**Risk:** High complexity, may not be compatible with Qt's GL abstraction

---

## Testing Plan

### Test 1: Baseline Measurement
**Before any changes:**
- Run with `SRPSS_PERF_METRICS=1`
- Record 10 transitions
- Calculate: avg dt_max, max dt_max, spike count

### Test 2: After Task 1 (Prefetch Fix)
**Expected:** 10-30ms reduction in spikes during prefetch  
**Measure:** Same metrics as baseline

### Test 3: After Task 2 (Shadow Async)
**Expected:** 5-15ms reduction in spikes during widget init  
**Measure:** Same metrics as baseline

### Test 4: After Task 3 (Audit Fixes)
**Expected:** Eliminate any remaining main thread blocking  
**Measure:** Same metrics as baseline

### Test 5: Final Validation
**Target:** dt_max <20ms, avg_fps 58-60  
**Method:** 50 transitions across multiple sessions

---

## Success Criteria

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| dt_max during transitions | 65-69ms | <20ms | 🔴 Not Met |
| avg_fps | 47-51 | 58-60 | 🔴 Not Met |
| Spike count per transition | 0-1 | 0 | 🟡 Close |
| Main thread blocking ops | Unknown | 0 | ⚠️ To Audit |

---

## Risk Assessment

### Low Risk (Safe to Implement)
- ✅ Task 1: Prefetch fix (Qt 6 supports QPixmap on worker threads)
- ✅ Task 3: Audit (information gathering only)

### Medium Risk (Requires Testing)
- ⚠️ Task 2: Shadow async (caching strategy needs validation)

### High Risk (Research Required)
- 🔴 Task 5: Texture upload (may not be feasible with Qt)

---

## Implementation Order

1. **Task 3** - Audit (find all issues first)
2. **Task 1** - Prefetch fix (high impact, low risk)
3. **Task 2** - Shadow async (medium impact, medium risk)
4. **Task 4** - Event loop (if needed after 1-3)
5. **Task 5** - Texture upload (only if still not meeting target)

---

## Notes

- Qt 6 allows QPixmap creation on worker threads (unlike Qt 5)
- All QImage operations are thread-safe
- QPainter can be used on QImage in worker threads
- Only final GL operations must be on main thread
- Cache aggressively to avoid repeated work

---

**Status:** Ready for implementation  
**Next Step:** Execute Task 3 (Audit) to find all remaining issues
