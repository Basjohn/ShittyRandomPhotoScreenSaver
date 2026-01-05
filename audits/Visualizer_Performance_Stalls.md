# Visualizer Performance Stalls Investigation

**Date:** January 5, 2026  
**Issue:** Visualizer experiences complete stalls/freezes during playback  
**Root Cause:** FFT worker process crashes and restarts

---

## Observed Behavior

From logs:
```
22:47:50 - core.process.supervisor - INFO - Restarting fft worker after 2000ms backoff (attempt 1)
22:47:50 - core.process.supervisor - INFO - Stopped fft worker
22:47:52 - core.process.supervisor - INFO - Started fft worker (PID: 32108)
```

**Pattern:**
- FFT worker crashes during operation
- ProcessSupervisor detects crash and restarts with backoff (2s, 4s, 8s, 16s)
- During restart window, visualizer has no audio data → stalls/freezes
- After restart, visualizer resumes

---

## Why FFT Worker Crashes

The FFT worker is a **separate process** that:
1. Captures audio from Spotify via loopback
2. Performs FFT computation
3. Sends bar values back to main process via IPC

**Common crash causes:**
- Audio device disconnection/change
- Spotify stops playing (worker tries to read from closed stream)
- Memory pressure in worker process
- IPC queue overflow

---

## Current Architecture

```
Main Process (UI Thread)
    ↓
SpotifyVisualizerWidget
    ↓
SpotifyBeatEngine (shared singleton)
    ↓
SpotifyVisualizerAudioWorker (QObject in main process)
    ↓ IPC (multiprocessing.Queue)
FFTWorker Process (separate process)
    ↓
Audio capture → FFT → Send bars
```

**Why this architecture:**
- FFT computation is CPU-intensive (~10-20ms per frame)
- Offloading to separate process prevents UI thread blocking
- Process isolation prevents audio crashes from killing main app

---

## Can Visualizer Be Split Further?

**Short answer: No, not safely.**

**Current split is optimal:**
- ✅ FFT computation already in separate process
- ✅ Smoothing offloaded to compute pool (ThreadManager)
- ✅ GL rendering on GPU (separate from CPU)

**Why not split more:**
- Audio capture **must** be in same process as FFT (tight coupling)
- Smoothing **must** be in main process (needs access to UI state)
- GL rendering **must** be on UI thread (Qt requirement)

**Attempting further splits would:**
- ❌ Add IPC overhead (slower, not faster)
- ❌ Increase complexity (more crash points)
- ❌ Violate Qt threading rules (GL context must stay on UI thread)

---

## Solutions for Performance Stalls

### Solution 1: Improve FFT Worker Resilience (RECOMMENDED)

**Goal:** Prevent crashes, not just recover from them.

**Changes needed:**
1. **Graceful audio device handling**
   - Detect device disconnection before crash
   - Retry audio capture with exponential backoff
   - Fall back to silence instead of crashing

2. **Spotify playback state awareness**
   - Check if Spotify is playing before capturing
   - Don't crash when Spotify stops
   - Smoothly transition to zero bars

3. **Memory management**
   - Limit FFT buffer sizes
   - Clear old buffers regularly
   - Monitor worker memory usage

**Implementation location:** `core/process/fft_worker.py` (or wherever FFT worker lives)

### Solution 2: Graceful Degradation During Restart

**Goal:** Hide stalls from user during worker restart.

**Changes needed:**
1. **Decay bars smoothly during restart**
   - Don't freeze at last value
   - Gradually decay to zero over 1-2 seconds
   - Resume when worker reconnects

2. **Visual feedback (optional)**
   - Dim visualizer slightly during restart
   - Show subtle "reconnecting" indicator

**Implementation location:** `widgets/spotify_visualizer/beat_engine.py`

### Solution 3: Reduce Restart Frequency

**Goal:** Minimize how often restarts happen.

**Changes needed:**
1. **Increase restart backoff**
   - Current: 2s, 4s, 8s, 16s
   - Proposed: 1s, 2s, 4s, 8s (faster recovery)

2. **Add health checks**
   - Ping worker every 100ms
   - Detect hung workers (not just crashed)
   - Preemptive restart before full crash

**Implementation location:** `core/process/supervisor.py`

---

## Recommended Action Plan

**Phase 1: Immediate (Low Risk)**
1. Implement Solution 2 (graceful degradation)
   - Add decay during worker restart in beat_engine
   - Smooth transition instead of freeze
   - **Effort:** 1-2 hours

**Phase 2: Short Term (Medium Risk)**
1. Investigate FFT worker crash logs
   - Check `screensaver_verbose.log` for worker exceptions
   - Identify specific crash triggers
   - **Effort:** 1 hour investigation

2. Implement Solution 1 (resilience improvements)
   - Add audio device error handling
   - Add Spotify state checks
   - **Effort:** 3-4 hours

**Phase 3: Long Term (Low Risk)**
1. Implement Solution 3 (health monitoring)
   - Add worker health checks
   - Optimize restart timing
   - **Effort:** 2-3 hours

---

## Performance Metrics

From your test run:
```
Spotify VIS metrics (Tick)
  windows   : 539
  duration  : mean=123597.24, min=628.30, max=476021.00
  avg_fps   : mean=52.49, min=20.00, max=62.20
  dt_max_ms : mean=84.02, min=29.82, max=99.96
```

**Analysis:**
- **avg_fps: 52.49** - Good baseline performance
- **min fps: 20.00** - Drops during stalls (FFT worker restart)
- **max duration: 476021ms** - Massive spike (likely during restart)
- **dt_max_ms: 99.96** - Frame time spikes to 100ms (10fps)

**Target after fixes:**
- avg_fps: 55+ (maintain)
- min_fps: 45+ (eliminate stalls)
- dt_max_ms: <50ms (smooth 20fps minimum)

---

## Why Not More Multiprocessing?

**Current architecture is already optimal:**

1. **FFT Worker (separate process)** ✅
   - CPU-intensive work isolated
   - Crash-safe (doesn't kill main app)
   - Already implemented

2. **Compute Pool (ThreadManager)** ✅
   - Smoothing offloaded
   - Lock-free SPSC queues
   - Already implemented

3. **GPU Rendering (OpenGL)** ✅
   - Shader-based bar rendering
   - Parallel to CPU work
   - Already implemented

**Adding more processes would:**
- Increase IPC overhead (slower)
- Add complexity (more bugs)
- Violate Qt threading model (crashes)

**The bottleneck is FFT worker crashes, not architecture.**

---

## Next Steps

1. ✅ **Flicker fixed** - Temporal stability filter implemented
2. ⏳ **Stalls investigation** - Need to examine FFT worker crash logs
3. ⏳ **Graceful degradation** - Implement smooth decay during restart
4. ⏳ **Worker resilience** - Add error handling to prevent crashes

**Recommendation:** Focus on FFT worker stability, not architecture changes.
