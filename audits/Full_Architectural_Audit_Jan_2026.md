# Full Architectural and Optimization Audit
**Date:** Jan 5, 2026  
**Scope:** Complete codebase analysis  
**Goal:** Identify all issues, bottlenecks, and improvement opportunities

---

## Executive Summary

This audit examines the entire SRPSS codebase for:
1. Performance bottlenecks
2. Architectural issues
3. Code quality problems
4. Technical debt
5. Optimization opportunities

**Key Findings:**
- 1723 TODO/FIXME/HACK markers across 144 files
- Several main thread blocking operations identified
- Worker restart loops indicate stability issues
- Memory management patterns need improvement
- Several optimization opportunities identified

---

## 1. Performance Issues

### 1.1 Worker Restart Loops (CRITICAL)
**Location:** `core/process/supervisor.py`  
**Evidence:** Logs show repeated worker restarts with exponential backoff
```
Restarting image worker after 2000ms backoff (attempt 1)
Restarting image worker after 4000ms backoff (attempt 2)
Restarting image worker after 8000ms backoff (attempt 3)
...
Restarting fft worker after 2000ms backoff (attempt 1)
```

**Root Cause:** Workers are crashing or timing out repeatedly  
**Impact:** CPU waste, delayed image loading, potential memory leaks  
**Fix Required:**
1. Add better error handling in workers
2. Investigate why workers are failing
3. Add health monitoring with detailed diagnostics
4. Consider worker pooling instead of single worker

### 1.2 Main Thread Blocking (HIGH)
**Locations Identified:**
- `engine/screensaver_engine.py:1196-1207` - Prefetch UI warmup ✅ FIXED
- `widgets/painter_shadow.py:307-372` - Shadow rendering ✅ FIXED (async added)
- `widgets/reddit_widget.py:1232` - Logo loading (one-time, acceptable)
- `widgets/media_widget.py:895` - Artwork loading (small images, acceptable)

### 1.3 Timer Jitter (MEDIUM)
**Location:** `rendering/gl_compositor.py`  
**Issue:** QTimer-based rendering causes 50-60ms spikes  
**Solution:** VSync-driven rendering (see Solution 1 document)

### 1.4 Texture Upload Blocking (MEDIUM)
**Location:** `rendering/gl_compositor.py:_pre_upload_textures`  
**Issue:** Synchronous texture upload blocks main thread  
**Current Status:** Disabled, but could be optimized with PBOs

---

## 2. Architectural Issues

### 2.1 Eco Mode Integration Incomplete
**Location:** `core/eco_mode.py`, `rendering/display_widget.py`  
**Issues Found:**
1. ✅ FIXED: `set_always_on_top()` not called on toggle
2. ⚠️ Workers not paused during eco mode
3. ⚠️ No integration with ProcessSupervisor

**Fix Required:**
```python
# In EcoModeManager._activate_eco_mode():
if self._process_supervisor:
    self._process_supervisor.stop(WorkerType.IMAGE)
    self._process_supervisor.stop(WorkerType.FFT)

# In EcoModeManager._deactivate_eco_mode():
if self._process_supervisor:
    self._process_supervisor.start(WorkerType.IMAGE)
    self._process_supervisor.start(WorkerType.FFT)
```

### 2.2 Global State in Modules
**Locations:**
- `widgets/painter_shadow.py` - `_global_shadow_caches`, `_GLOBAL_PRERENDER_CACHE`
- `core/logging/logger.py` - Global logger instances
- `core/threading/manager.py` - Singleton pattern

**Issue:** Global state makes testing difficult and can cause issues  
**Recommendation:** Use dependency injection where possible

### 2.3 Circular Import Risks
**Pattern Found:**
```python
if TYPE_CHECKING:
    from rendering.display_widget import DisplayWidget
```
**Assessment:** Properly handled with TYPE_CHECKING guards. No action needed.

### 2.4 Large File Sizes
**Files over 2000 lines:**
- `rendering/display_widget.py` - 3707 lines
- `engine/screensaver_engine.py` - 2817 lines
- `widgets/spotify_visualizer_widget.py` - 2500+ lines
- `rendering/gl_compositor.py` - 3100+ lines

**Recommendation:** Consider splitting into smaller modules:
- `display_widget.py` → `display_widget_core.py`, `display_widget_overlays.py`, `display_widget_context_menu.py`
- `screensaver_engine.py` → `engine_core.py`, `engine_image_loading.py`, `engine_transitions.py`

---

## 3. Code Quality Issues

### 3.1 Exception Handling
**Pattern Found (Multiple Files):**
```python
except Exception:
    pass
```

**Locations with bare except:**
- `engine/screensaver_engine.py` - 50+ instances
- `rendering/display_widget.py` - 40+ instances
- `widgets/spotify_visualizer_widget.py` - 30+ instances

**Recommendation:** 
1. Log exceptions even if swallowed
2. Use specific exception types
3. Add context to error messages

### 3.2 Magic Numbers
**Examples Found:**
```python
timeout_ms=3000  # Why 3000?
stagger_ms = 100  # Why 100?
MAX_CACHE_AGE_MS = 60000  # Document reasoning
```

**Recommendation:** Extract to named constants with documentation

### 3.3 Inconsistent Logging Tags
**Found Tags:**
- `[ASYNC]`, `[WORKER]`, `[FALLBACK]`, `[PERF]`
- `[GL COMPOSITOR]`, `[GL ANIM]`
- `[MC]`, `[ECO MODE]`
- `[SHADOW_ASYNC]`

**Recommendation:** Standardize logging tag format:
```python
# Standard format: [MODULE] [SUBSYSTEM] message
logger.info("[ENGINE] [IMAGE] Loading image: %s", path)
logger.debug("[RENDER] [GL] Texture uploaded in %.1fms", elapsed)
```

### 3.4 Duplicate Code
**Pattern Found:** Similar image loading logic in multiple places
- `engine/screensaver_engine.py:_load_image_task`
- `engine/screensaver_engine.py:_do_load_and_process`
- `utils/image_prefetcher.py:_load_qimage`

**Recommendation:** Consolidate into single `ImageLoader` class

---

## 4. Memory Management Issues

### 4.1 Pixmap/QImage Lifecycle
**Pattern Found:**
```python
pixmap = QPixmap.fromImage(qimage)
# qimage still in memory, pixmap also in memory
# No explicit cleanup
```

**Recommendation:** 
1. Clear source images after conversion
2. Use ResourceManager for tracking
3. Add memory pressure monitoring

### 4.2 Cache Size Limits
**Caches Without Limits:**
- `_GLOBAL_PRERENDER_CACHE` in `painter_shadow.py` - No size limit
- `_image_cache` in `screensaver_engine.py` - Has limit but not enforced consistently

**Recommendation:** Add LRU eviction to all caches

### 4.3 Worker Process Memory
**Issue:** Workers may accumulate memory over time  
**Evidence:** Worker restarts suggest memory issues  
**Recommendation:** 
1. Add memory monitoring to workers
2. Periodic worker restart (every N images)
3. Explicit garbage collection in workers

---

## 5. Thread Safety Issues

### 5.1 Potential Race Conditions
**Location:** `engine/screensaver_engine.py`
```python
self._loading_in_progress = False  # Set without lock
```

**Recommendation:** Use `threading.Lock()` for all shared state

### 5.2 Qt Object Access from Threads
**Pattern Found:**
```python
def _on_complete(result):
    # Called from thread callback
    display.set_image(pixmap)  # Qt object access
```

**Assessment:** Properly using `run_on_ui_thread()` in most places. Verify all callbacks.

### 5.3 Global Cache Thread Safety
**Location:** `widgets/painter_shadow.py`
**Status:** ✅ FIXED - Added `_GLOBAL_PRERENDER_LOCK`

---

## 6. Optimization Opportunities

### 6.1 Image Loading Pipeline
**Current Flow:**
1. ImageWorker decodes image (separate process)
2. QImage transferred via shared memory
3. QPixmap.fromImage on main thread
4. Texture upload on main thread

**Optimized Flow:**
1. ImageWorker decodes + prescales (separate process)
2. QImage transferred via shared memory
3. QPixmap.fromImage on compute thread ✅ IMPLEMENTED
4. Texture data prepared on compute thread
5. Only final GL upload on main thread

### 6.2 Transition Pre-computation
**Current:** Transitions compute state each frame  
**Optimization:** Pre-compute keyframes, interpolate at runtime

### 6.3 Overlay Rendering
**Current:** Each overlay renders independently  
**Optimization:** Batch overlay rendering, use texture atlas

### 6.4 Settings Access
**Current:** `settings_manager.get()` called frequently  
**Optimization:** Cache settings values, invalidate on change

---

## 7. Specific Fixes Required

### Fix 1: Worker Health Monitoring
**File:** `core/process/supervisor.py`
**Change:** Add detailed health diagnostics
```python
def _check_worker_health(self, worker_type: WorkerType) -> HealthStatus:
    # Add memory usage tracking
    # Add message queue depth
    # Add processing time statistics
    # Log detailed diagnostics on failure
```

### Fix 2: Eco Mode Worker Control
**File:** `core/eco_mode.py`
**Change:** Add ProcessSupervisor integration
```python
def set_process_supervisor(self, supervisor: "ProcessSupervisor") -> None:
    self._process_supervisor = supervisor

def _activate_eco_mode(self, occlusion_ratio: float) -> None:
    # ... existing code ...
    # Stop workers to save CPU
    if self._process_supervisor:
        self._process_supervisor.stop(WorkerType.IMAGE)
        self._process_supervisor.stop(WorkerType.FFT)
```

### Fix 3: Cache Size Limits
**File:** `widgets/painter_shadow.py`
**Change:** Add LRU eviction
```python
MAX_CACHE_SIZE = 50  # Maximum cached shadows

@classmethod
def _evict_if_needed(cls):
    with _GLOBAL_PRERENDER_LOCK:
        if len(_GLOBAL_PRERENDER_CACHE) > cls.MAX_CACHE_SIZE:
            # Remove oldest entries (FIFO for simplicity)
            keys = list(_GLOBAL_PRERENDER_CACHE.keys())
            for key in keys[:len(keys) - cls.MAX_CACHE_SIZE]:
                del _GLOBAL_PRERENDER_CACHE[key]
```

### Fix 4: Exception Logging
**All Files:** Replace bare `except:` with logged exceptions
```python
# Before
except Exception:
    pass

# After
except Exception as e:
    logger.debug("[MODULE] Operation failed: %s", e)
```

### Fix 5: Settings Caching
**File:** `core/settings/settings_manager.py`
**Change:** Add in-memory cache with change invalidation
```python
class SettingsManager:
    def __init__(self):
        self._cache = {}
        self._cache_valid = False
    
    def get(self, key, default=None):
        if self._cache_valid and key in self._cache:
            return self._cache[key]
        value = self._load_from_file(key, default)
        self._cache[key] = value
        return value
    
    def set(self, key, value):
        self._cache[key] = value
        self._cache_valid = True
        self._save_to_file(key, value)
```

---

## 8. Test Coverage Gaps

### Missing Tests
1. **Worker restart behavior** - No tests for exponential backoff
2. **Eco mode integration** - No tests for worker pause/resume
3. **Multi-monitor transitions** - Limited coverage
4. **Memory pressure scenarios** - No tests
5. **Thread safety** - Limited concurrent access tests

### Recommended New Tests
```python
# test_worker_restart.py
class TestWorkerRestart:
    def test_exponential_backoff(self):
        """Verify backoff timing is correct."""
    
    def test_max_restart_attempts(self):
        """Verify worker stops restarting after max attempts."""
    
    def test_restart_resets_on_success(self):
        """Verify backoff resets after successful operation."""

# test_eco_mode_integration.py
class TestEcoModeWorkerControl:
    def test_workers_stop_on_eco_activate(self):
        """Workers should stop when eco mode activates."""
    
    def test_workers_restart_on_eco_deactivate(self):
        """Workers should restart when eco mode deactivates."""

# test_memory_pressure.py
class TestMemoryPressure:
    def test_cache_eviction_under_pressure(self):
        """Caches should evict entries under memory pressure."""
    
    def test_worker_memory_limits(self):
        """Workers should not exceed memory limits."""
```

---

## 9. Documentation Gaps

### Missing Documentation
1. **Architecture overview** - No high-level architecture doc
2. **Worker protocol** - Message format not documented
3. **Transition system** - Group A/B/C not explained in code
4. **Performance tuning** - No guide for optimization

### Recommended Documentation
1. `Docs/ARCHITECTURE.md` - System overview
2. `Docs/WORKER_PROTOCOL.md` - IPC message format
3. `Docs/TRANSITIONS.md` - Transition system design
4. `Docs/PERFORMANCE.md` - Tuning guide

---

## 10. Priority Matrix

| Issue | Severity | Effort | Priority |
|-------|----------|--------|----------|
| Worker restart loops | Critical | High | P0 |
| Eco mode worker control | High | Low | P1 |
| Cache size limits | Medium | Low | P1 |
| Exception logging | Medium | Medium | P2 |
| Settings caching | Low | Medium | P2 |
| File splitting | Low | High | P3 |
| Documentation | Low | Medium | P3 |

---

## 11. Implementation Checklist

### Immediate (P0-P1)
- [ ] Investigate worker restart root cause
- [ ] Add worker health diagnostics
- [ ] Implement eco mode worker control
- [ ] Add cache size limits to shadow cache
- [ ] Add cache size limits to image cache

### Short-term (P2)
- [ ] Replace bare except with logged exceptions
- [ ] Add settings caching
- [ ] Add missing tests for worker restart
- [ ] Add missing tests for eco mode

### Long-term (P3)
- [ ] Split large files into modules
- [ ] Create architecture documentation
- [ ] Standardize logging tags
- [ ] Consolidate duplicate image loading code

---

## 12. Conclusion

The codebase is generally well-structured with good use of centralized managers (ThreadManager, ResourceManager, SettingsManager). The main issues are:

1. **Worker stability** - Needs immediate investigation
2. **Eco mode incomplete** - Easy fix, high impact
3. **Cache management** - Needs size limits
4. **Code quality** - Exception handling needs improvement

The performance optimizations implemented (async shadow rendering, prefetch fix) should help, but the worker restart issue is the most critical problem to address.

**Recommended Next Steps:**
1. Investigate worker restart root cause (check worker logs)
2. Implement eco mode worker control
3. Add cache size limits
4. Run full test suite to verify stability
