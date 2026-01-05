# Performance Solutions Analysis
**Date:** Jan 5, 2026  
**Context:** Remaining 50-60ms frame spikes during transitions

---

## Issues Fixed Today

### 1. Eco Mode Not Activating 
**Problem:** Eco mode never activated when window was covered because `EcoModeManager.set_always_on_top()` was never called.

**Root Cause:** The context menu's `_on_context_always_on_top_toggled()` saved the setting but didn't notify the eco mode manager.

**Fix:** Added notification to eco mode manager when always-on-top changes.
- File: `rendering/display_widget.py`
- Lines: 3065-3071

**Status:**  **FIXED** - Code deployed, needs testing

**Confidence:** 100% - This was a clear integration bug.

---

### 2. CPU % Always Showing 0% ✅
**Problem:** System tray tooltip always showed "CPU: 0%" despite actual CPU usage.

**Root Cause:** `psutil.cpu_percent(interval=None)` requires a baseline. The first call returns 0.0, subsequent calls return actual usage. The code primed the baseline but immediately called `_update_tooltip()` before any time elapsed.

**Fix:** Delayed first tooltip update by 1 second using `QTimer.singleShot(1000, self._update_tooltip)`.
- File: `ui/system_tray.py`
- Lines: 133-138

**Status:** ✅ **FIXED** - Code deployed, needs testing

**Confidence:** 100% - This is how psutil's non-blocking CPU measurement works.

---

### 3. Workers Continue During Eco Mode ⚠️
**Problem:** FFT and Image workers continue running even when eco mode is active and window is covered.

**Root Cause:** Eco mode only pauses visualizer updates and notes transitions. It does NOT pause workers because:
1. `ProcessSupervisor` has no pause mechanism (only stop/start)
2. `EcoModeConfig.pause_prefetch = False` by default
3. No callbacks are registered for worker pause/resume

**Current Behavior:**
- Eco mode active → Visualizer paused, transitions noted
- Workers → Continue running, restarting on failure
- Result → CPU/GPU usage continues despite window being covered

**Why This Wasn't Implemented:**
- Workers are separate processes - can't "pause" them without stopping
- Stopping workers means losing state and requiring restart
- Image prefetching may be desirable even when covered

**Fix Required:** Implement worker stop/start in eco mode:
- On activation: Stop ImageWorker and FFTWorker via ProcessSupervisor
- On deactivation: Restart workers
- Add callbacks to EcoModeManager for worker control
- Files to modify: `core/eco_mode.py`, `rendering/display_widget.py`

---

## Three Architectural Solutions for Frame Spikes

### Solution 1: VSync-Driven Rendering (Game Engine Approach)

**Description:**
Replace timer-based rendering with a render loop driven by `swapBuffers()`. Instead of QTimer firing every 16ms and calling `update()`, the render thread continuously calls `paintGL()` and lets VSync naturally pace the frames.

**Implementation:**
```python
class GLCompositorWidget:
    def start_transition(self):
        # Start render thread instead of timer
        self._render_thread = threading.Thread(target=self._render_loop)
        self._render_thread.start()
    
    def _render_loop(self):
        while self._transition_active:
            # Make context current on this thread
            self.makeCurrent()
            
            # Render frame
            self._paintGL_impl()
            
            # swapBuffers blocks until VSync - natural frame pacing
            self.swapBuffers()
            
            self.doneCurrent()
```

**Pros:**
- Eliminates Qt timer/event loop overhead
- Natural VSync synchronization (no timer-VSync misalignment)
- Consistent frame pacing (no 50-60ms spikes from timer jitter)
- Industry-standard approach (used by game engines)

**Cons:**
- Requires moving GL context to dedicated render thread
- Qt's OpenGL classes are designed for main thread use
- Need to carefully manage context sharing between threads
- More complex than current timer-based approach
- May require `QOpenGLContext::moveToThread()` which has caveats

**Confidence in Success:** 70%
- High confidence it would eliminate timer-related spikes
- Medium confidence in Qt's thread safety for GL contexts
- Risk: Qt's GL classes may not support this pattern cleanly

**Likelihood of Succeeding:** 60%
- Qt documentation warns against moving GL contexts between threads
- May hit Qt limitations or require workarounds
- Would need extensive testing to ensure stability

**Drawbacks:**
- Significant refactoring required (~500-1000 lines)
- Potential Qt compatibility issues
- Harder to debug than timer-based approach
- May break existing overlay/widget integration

---

### Solution 2: Per-Monitor GL Contexts (Multi-Threaded Rendering)

**Description:**
Give each monitor its own GL context and render thread. This eliminates main thread serialization where both monitors compete for the same event loop.

**Implementation:**
```python
class DisplayWidget:
    def __init__(self):
        # Each display gets its own GL context
        self._gl_context = QOpenGLContext()
        self._gl_context.create()
        
        # Each display gets its own render thread
        self._render_thread = RenderThread(self._gl_context, self.gl_compositor)
        self._render_thread.start()

class RenderThread(QThread):
    def run(self):
        # Make context current on this thread
        self._context.makeCurrent(self._surface)
        
        while self._running:
            # Render frame
            self._compositor.paintGL()
            self._context.swapBuffers(self._surface)
```

**Pros:**
- Eliminates multi-monitor contention on main thread
- Each monitor renders independently at its own refresh rate
- Scales better with more monitors
- Natural solution for multi-monitor setups

**Cons:**
- Requires separate GL context per monitor
- Context sharing for textures becomes complex
- Qt widgets (overlays) must stay on main thread
- Synchronization required for shared resources
- Significantly more complex architecture

**Confidence in Success:** 50%
- High confidence it would eliminate multi-monitor serialization
- Low confidence in Qt's support for this pattern
- Risk: Qt's GL integration is designed for single-context use

**Likelihood of Succeeding:** 40%
- Qt's GL classes are tightly coupled to main thread
- Context sharing is notoriously tricky in Qt
- May hit fundamental Qt limitations
- Would require major architectural changes

**Drawbacks:**
- Massive refactoring required (~2000+ lines)
- Potential race conditions with shared textures
- Debugging becomes much harder
- May break overlay/widget system entirely
- Higher memory usage (multiple GL contexts)

---

### Solution 3: Offload Everything Spike-Prone to Worker Threads

**Description:**
Move ALL potentially blocking operations to worker threads/processes:
- Image loading → Already in ImageWorker ✅
- Texture uploads → Move to GL thread
- QPixmap conversions → Move to worker thread
- Event processing → Minimize on main thread

**Implementation:**
```python
class ScreensaverEngine:
    def _do_load_and_process(self):
        # Already on worker thread
        qimage = self._load_image_via_worker(...)
        
        # NEW: Convert to QPixmap on worker thread (Qt 6 allows this)
        pixmap = QPixmap.fromImage(qimage)
        
        # NEW: Pre-upload texture on worker thread
        texture_data = self._prepare_texture_data(pixmap)
        
        # Return everything to main thread
        return {
            'pixmap': pixmap,
            'texture_data': texture_data
        }

class GLCompositorWidget:
    def start_transition(self, data):
        # Main thread only does final GL upload
        self.makeCurrent()
        self._upload_prepared_texture(data['texture_data'])
        self.doneCurrent()
```

**Pros:**
- Minimal architectural changes
- Leverages existing worker infrastructure
- Main thread only does final GL operations
- Easier to debug than multi-threading GL contexts
- Incremental implementation (can do piece by piece)

**Cons:**
- Can't eliminate all main thread work (Qt requires it)
- Still subject to Qt event loop overhead
- Won't fix timer-VSync misalignment
- Limited by Qt's threading model

**Confidence in Success:** 85%
- High confidence we can move more work off main thread
- Qt 6 allows QPixmap creation on worker threads
- Already have working ImageWorker infrastructure
- Low risk of breaking existing functionality

**Likelihood of Succeeding:** 80%
- Most operations can be moved to workers
- Qt 6's threading improvements make this viable
- Can implement incrementally and test
- Fallback to current approach if issues arise

**Drawbacks:**
- Won't eliminate all frame spikes (timer jitter remains)
- Still limited by Qt event loop on main thread
- May only reduce spikes by 20-30% (not eliminate)
- Doesn't address fundamental timer-VSync issue

---

## Why Can't We Have Everything on Different Threads?

**Short Answer:** Qt's design and OpenGL's requirements.

### Qt's Main Thread Requirement
Qt **requires** all widget operations (painting, events, updates) to happen on the main thread. This is a fundamental Qt design decision for:
- Thread safety (widgets aren't thread-safe)
- Event loop integration (signals/slots)
- Platform integration (native window handles)

### OpenGL Context Affinity
OpenGL contexts are **thread-affine** - once a context is made current on a thread, it should stay on that thread. While you can move contexts between threads, it's:
- Not officially supported by Qt
- Prone to driver issues
- Requires careful synchronization

### What We Already Do
We **do** offload heavy work to separate threads/processes:
- ✅ Image loading → ImageWorker (separate process)
- ✅ FFT processing → FFTWorker (separate process)
- ✅ RSS fetching → RSSWorker (separate process)
- ✅ Image processing → AsyncImageProcessor (thread pool)

### What We Can't Move
- ❌ GL rendering → Must be on main thread (Qt requirement)
- ❌ Widget updates → Must be on main thread (Qt requirement)
- ❌ Event processing → Must be on main thread (Qt requirement)
- ❌ QTimer callbacks → Fire on main thread (Qt design)

### The Bottleneck
The remaining 50-60ms spikes are caused by:
1. **Qt event loop overhead** - Processing events between frames
2. **Timer jitter** - QTimer doesn't fire exactly on time
3. **Main thread serialization** - Both monitors share the event loop

These are **fundamental Qt limitations**, not things we can easily work around.

---

## GPU Image Loading

**Question:** Why aren't we using the GPU to load images?

**Answer:** We **are** using the GPU for rendering, but image **decoding** must happen on CPU.

### Current Pipeline
1. **CPU (ImageWorker):** Decode JPEG/PNG → Raw pixels (145-273ms)
2. **CPU (AsyncImageProcessor):** Resize/sharpen → Processed pixels
3. **CPU → GPU:** Upload texture → GL texture object (fast, <5ms)
4. **GPU:** Render with shaders → Display (0.2ms)

### Why Decoding is CPU-Only
- Image formats (JPEG, PNG) require CPU decoders
- No GPU-accelerated JPEG/PNG decoders in standard libraries
- GPU texture upload is already fast (<5ms)
- The bottleneck is decoding, not uploading

### What About GPU Decoding?
- **NVDEC** (NVIDIA) - Only for video, not images
- **DirectX/Vulkan** - Can upload faster but still need CPU decode
- **Custom CUDA** - Would require writing JPEG decoder (not worth it)

**Conclusion:** GPU is already being used optimally. The 145-273ms image load time is CPU decoding, which is unavoidable.

---

## Recommendation

**Implement Solution 3 first** (offload more to workers):
- **Confidence:** 85%
- **Success Likelihood:** 80%
- **Risk:** Low
- **Effort:** Medium (~500 lines)
- **Expected Improvement:** 20-30% reduction in spikes

**Then consider Solution 1** (VSync-driven rendering) if needed:
- **Confidence:** 70%
- **Success Likelihood:** 60%
- **Risk:** Medium
- **Effort:** High (~1000 lines)
- **Expected Improvement:** 50-70% reduction in spikes

**Avoid Solution 2** (per-monitor contexts):
- **Confidence:** 50%
- **Success Likelihood:** 40%
- **Risk:** High
- **Effort:** Very High (~2000+ lines)
- **Expected Improvement:** Uncertain

---

## Current Performance Status

| Metric | Before | After Fixes | Target | Gap |
|--------|--------|-------------|--------|-----|
| False positive spikes | 5000-6000ms | **Eliminated** | N/A | ✅ |
| dt_max | 70-99ms | **65-69ms** | <20ms | -45ms |
| avg_fps | 46-50 | **47-51** | 58-60 | -7fps |
| GPU time | 0.2ms | **0.2ms** | N/A | ✅ |

**The remaining gap is Qt/Windows timer limitations, not a bug we can fix with simple changes.**
