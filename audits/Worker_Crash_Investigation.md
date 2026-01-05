# Worker Crash Investigation & Fixes

**Date:** January 5, 2026  
**Priority:** CRITICAL - Worker crashes affect system stability

---

## Issues Fixed

### 1. EventSystem.publish() Signature Error ✅ FIXED

**Error:**
```
Failed to broadcast health: EventSystem.publish() got an unexpected keyword argument 'worker_type'
```

**Root Cause:**
`ProcessSupervisor._broadcast_health()` was calling `EventSystem.publish()` with kwargs directly instead of using the `data` parameter.

**Fix Applied:**
```python
# BEFORE (incorrect)
self._event_system.publish(
    "worker.health_changed",
    worker_type=worker_type.value,
    state=health.state.name,
    is_healthy=health.is_healthy(),
    pid=health.pid,
)

# AFTER (correct)
self._event_system.publish(
    "worker.health_changed",
    data={
        "worker_type": worker_type.value,
        "state": health.state.name,
        "is_healthy": health.is_healthy(),
        "pid": health.pid,
    },
    source=self,
)
```

**File:** `core/process/supervisor.py:889-908`

**Impact:** This error was logged every time a worker started or restarted, but was silently caught. It didn't cause crashes but indicated improper EventSystem usage.

---

## Remaining Investigation Needed

### FFT Worker Crashes

**Observed Pattern:**
```
22:47:50 - Restarting fft worker after 2000ms backoff (attempt 1)
22:47:52 - Started fft worker (PID: 32108)
[~20 seconds later]
22:48:10 - Restarting fft worker after 4000ms backoff (attempt 2)
```

**Restart Backoff Sequence:**
- Attempt 1: 2s
- Attempt 2: 4s
- Attempt 3: 8s
- Attempt 4: 16s

**Questions to Answer:**
1. **Why is FFT worker crashing?**
   - Audio device disconnection?
   - Spotify stops playing?
   - Memory pressure?
   - IPC queue overflow?

2. **Are other workers crashing?**
   - ImageWorker status?
   - RSSWorker status?

3. **What triggers the crashes?**
   - Specific audio conditions?
   - Time-based pattern?
   - Resource exhaustion?

---

## Investigation Steps

### Step 1: Enable Worker Process Logging

**Goal:** Capture FFT worker internal errors before crash.

**Action Needed:**
1. Check if FFT worker has its own log file
2. If not, add logging to FFT worker process
3. Log exceptions before worker exits

**Files to Check:**
- `core/process/fft_worker.py` (or wherever FFT worker lives)
- Worker process entry point

### Step 2: Add Crash Telemetry

**Goal:** Understand crash patterns.

**Metrics to Track:**
- Time between worker start and crash
- Audio state when crash occurs (playing/paused)
- Memory usage before crash
- Queue sizes before crash

**Implementation:**
```python
# In FFT worker process
try:
    # Worker loop
    while not shutdown:
        # ... work ...
        pass
except Exception as e:
    logger.exception(f"FFT worker crashed: {e}")
    # Log telemetry
    logger.error(f"Crash telemetry: memory={get_memory()}, queue_size={queue.qsize()}")
    raise
```

### Step 3: Add Graceful Degradation

**Goal:** Prevent visualizer stalls during worker restart.

**Implementation in beat_engine.py:**
```python
def tick(self) -> Optional[List[float]]:
    # Check if worker is alive
    if not self._is_worker_healthy():
        # Decay bars smoothly instead of freezing
        self._decay_bars_during_restart()
        return self._latest_bars
    
    # Normal processing...
```

### Step 4: Improve Worker Resilience

**Goal:** Prevent crashes, not just recover from them.

**Changes Needed:**
1. **Audio device error handling**
   - Detect device disconnection
   - Retry audio capture with backoff
   - Fall back to silence instead of crashing

2. **Spotify state awareness**
   - Check if Spotify is playing before capturing
   - Don't crash when Spotify stops
   - Smoothly transition to zero bars

3. **Memory management**
   - Limit FFT buffer sizes
   - Clear old buffers regularly
   - Monitor worker memory usage

---

## Next Actions

### Immediate (Required)
1. ✅ Fix EventSystem.publish() error
2. ⏳ Test visualizer with all anti-flicker solutions
3. ⏳ Verify no more EventSystem errors in logs

### Short Term (High Priority)
1. ⏳ Locate FFT worker source code
2. ⏳ Add comprehensive logging to FFT worker
3. ⏳ Run test session and capture crash logs
4. ⏳ Analyze crash patterns

### Medium Term (Required for Stability)
1. ⏳ Implement graceful degradation in beat_engine
2. ⏳ Add audio device error handling to FFT worker
3. ⏳ Add Spotify state checks to FFT worker
4. ⏳ Add memory monitoring to FFT worker

### Long Term (Nice to Have)
1. ⏳ Add health checks to all workers
2. ⏳ Implement preemptive restart before crash
3. ⏳ Add worker crash telemetry dashboard

---

## Testing Checklist

After implementing fixes:
- [ ] Run visualizer for 5+ minutes with music playing
- [ ] Check logs for worker restart messages
- [ ] Verify no EventSystem errors
- [ ] Confirm visualizer doesn't stall during restarts
- [ ] Test with Spotify paused/stopped
- [ ] Test with audio device changes

---

## Related Files

- `core/process/supervisor.py` - Worker lifecycle management
- `core/process/types.py` - Worker health tracking
- `widgets/spotify_visualizer/beat_engine.py` - Audio processing
- `core/process/fft_worker.py` - FFT worker process (needs investigation)

---

## Status

**EventSystem Error:** ✅ FIXED  
**FFT Worker Crashes:** ⚠️ UNDER INVESTIGATION  
**Visualizer Anti-Flicker:** ✅ IMPLEMENTED (Solutions 1+2+3)  
**Worker Resilience:** ⏳ PENDING IMPLEMENTATION
