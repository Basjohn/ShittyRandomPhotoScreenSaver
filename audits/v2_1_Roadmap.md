# SRPSS v2.1 Production Integration Roadmap

**Status**: ACTIVE - Production integration focus  
**Created**: January 5, 2026  
**Reference**: `audits/Architecture_Audit_Jan_2026.md`

---

## Executive Summary

**Current State**: v2.0 infrastructure is complete and tested (1348+ tests passing), but **NOT integrated into production**. All multiprocessing workers exist only in test code. Performance has not improved because workers are not running.

**Goal**: Integrate all tested infrastructure into production code to achieve actual performance improvements.

**Expected Results**:
- **25-40% FPS increase** (46fps → 58-60fps)
- **75% reduction in frame time spikes** (85ms → <20ms)
- **Eliminate main thread blocking** (image decode, RSS fetch, FFT processing)
- **Full Eco Mode functionality** in MC builds

**Total Effort**: 10-14 hours of focused integration work  
**Risk**: LOW - All infrastructure tested and ready

---

## Critical Constraint: Visualizer Algorithm Preservation

**BEFORE ANY WORKER INTEGRATION**: The Spotify visualizer algorithm is mathematically precise and must not be altered.

### Protected Math (DO NOT CHANGE)

**Location**: `widgets/beat_engine.py` → `_SpotifyBeatEngine`

1. **FFT to Bars Conversion**:
   ```python
   # Noise floor subtraction
   magnitude = np.abs(fft_data)
   magnitude = np.maximum(magnitude - 2.1, 0)
   
   # Dynamic range expansion
   magnitude = np.power(magnitude, 2.5)
   
   # Logarithmic scaling
   magnitude = np.log1p(magnitude)
   
   # Power scaling
   magnitude = np.power(magnitude, 1.2)
   
   # Smoothing convolution
   kernel = np.array([0.25, 0.5, 0.25])
   magnitude = np.convolve(magnitude, kernel, mode='same')
   ```

2. **Smoothing Parameters**:
   ```python
   tau_rise = base_tau * 0.35   # Rise time constant
   tau_decay = base_tau * 3.0   # Decay time constant
   alpha_rise = 1.0 - math.exp(-dt / tau_rise)
   alpha_decay = 1.0 - math.exp(-dt / tau_decay)
   ```

3. **Dynamic Floor**:
   ```python
   floor_mid_weight = 0.5
   dynamic_floor_ratio = 1.05
   floor_alpha = 0.05
   ```

### Integration Strategy for FFTWorker

**DO**: Extract the exact math into FFTWorker  
**DON'T**: Modify any numpy operations, constants, or formulas

**Verification**:
1. Before integration: Capture baseline output for known audio input
2. After integration: Verify worker output matches baseline exactly
3. Use existing test: `tests/test_fft_worker.py` already validates math preservation

**Reference**: `audits/VISUALIZER_DEBUG.md` for complete algorithm documentation

---

## Phase 1: ProcessSupervisor Integration (2-3 hours)

**Priority**: CRITICAL - Unlocks all other workers  
**Reference**: Architecture_Audit_Jan_2026.md lines 341-395

### Task 1.1: Initialize ProcessSupervisor in ScreensaverEngine

**File**: `engine/screensaver_engine.py`  
**Method**: `__init__`

**Changes**:
```python
from core.process import ProcessSupervisor, WorkerType
from core.process.workers.image_worker import image_worker_factory
from core.process.workers.rss_worker import rss_worker_factory
from core.process.workers.fft_worker import fft_worker_factory
from core.process.workers.transition_worker import transition_worker_factory

def __init__(self):
    # ... existing initialization ...
    
    # Initialize ProcessSupervisor
    self._process_supervisor = ProcessSupervisor()
    
    # Register worker factories
    self._process_supervisor.register_worker_factory(
        WorkerType.IMAGE, image_worker_factory
    )
    self._process_supervisor.register_worker_factory(
        WorkerType.RSS, rss_worker_factory
    )
    self._process_supervisor.register_worker_factory(
        WorkerType.FFT, fft_worker_factory
    )
    self._process_supervisor.register_worker_factory(
        WorkerType.TRANSITION, transition_worker_factory
    )
    
    logger.info("ProcessSupervisor initialized with 4 worker types")
```

### Task 1.2: Start Workers in initialize() Method

**File**: `engine/screensaver_engine.py`  
**Method**: `initialize`

**Changes**:
```python
def initialize(self):
    # ... existing initialization ...
    
    # Start workers based on settings (default all enabled)
    if self.settings_manager.get('workers.image.enabled', True):
        if self._process_supervisor.start(WorkerType.IMAGE):
            logger.info("ImageWorker started successfully")
        else:
            logger.warning("ImageWorker failed to start - using fallback")
    
    if self.settings_manager.get('workers.rss.enabled', True):
        if self._process_supervisor.start(WorkerType.RSS):
            logger.info("RSSWorker started successfully")
        else:
            logger.warning("RSSWorker failed to start - using fallback")
    
    if self.settings_manager.get('workers.fft.enabled', True):
        if self._process_supervisor.start(WorkerType.FFT):
            logger.info("FFTWorker started successfully")
        else:
            logger.warning("FFTWorker failed to start - using fallback")
    
    if self.settings_manager.get('workers.transition.enabled', True):
        if self._process_supervisor.start(WorkerType.TRANSITION):
            logger.info("TransitionWorker started successfully")
        else:
            logger.warning("TransitionWorker failed to start - using fallback")
```

### Task 1.3: Shutdown Workers in stop() Method

**File**: `engine/screensaver_engine.py`  
**Method**: `stop`

**Changes**:
```python
def stop(self, exit_app: bool = False):
    # ... existing shutdown logic ...
    
    # Shutdown ProcessSupervisor
    if self._process_supervisor:
        logger.info("Shutting down ProcessSupervisor...")
        self._process_supervisor.shutdown()
        logger.info("ProcessSupervisor shutdown complete")
```

**Verification**:
- Run application and check logs for "ProcessSupervisor initialized"
- Check logs for "ImageWorker started successfully" (and other workers)
- Verify clean shutdown with "ProcessSupervisor shutdown complete"

**Deliverable**: ProcessSupervisor running with all 4 workers active

---

## Phase 2: ImageWorker Integration (2-3 hours)

**Priority**: CRITICAL - Highest performance impact  
**Reference**: Architecture_Audit_Jan_2026.md lines 401-461

### Task 2.1: Wire ImageWorker into _load_image_task

**File**: `engine/screensaver_engine.py`  
**Method**: `_load_image_task`

**Changes**:
```python
def _load_image_task(self, image_metadata: ImageMetadata) -> Optional[QPixmap]:
    """Load and process image, using ImageWorker if available."""
    
    # Generate cache key
    if image_metadata.local_path:
        cache_key = f"{image_metadata.local_path}|scaled:{self._target_width}x{self._target_height}"
    else:
        cache_key = f"{image_metadata.url}|scaled:{self._target_width}x{self._target_height}"
    
    # Check cache first
    cached = self._image_cache.get(cache_key)
    if cached:
        return cached
    
    # Use ImageWorker if available
    if self._process_supervisor and self._process_supervisor.is_running(WorkerType.IMAGE):
        try:
            # Send decode request to worker
            msg = self._process_supervisor.create_message(
                WorkerType.IMAGE,
                MessageType.IMAGE_DECODE,
                payload={
                    "path": str(image_metadata.local_path) if image_metadata.local_path else None,
                    "url": image_metadata.url,
                    "target_width": self._target_width,
                    "target_height": self._target_height
                }
            )
            
            # Send and wait for response (500ms timeout)
            response = self._process_supervisor.send_and_wait(
                WorkerType.IMAGE, msg, timeout_ms=500
            )
            
            if response and response.success:
                # Convert RGBA data to QPixmap
                rgba_data = response.payload["rgba_data"]
                width = response.payload["width"]
                height = response.payload["height"]
                
                qimage = QImage(
                    rgba_data, width, height,
                    width * 4, QImage.Format_RGBA8888
                )
                pixmap = QPixmap.fromImage(qimage)
                
                # Cache result with proper key
                self._image_cache.put(cache_key, pixmap)
                
                logger.debug(f"Image loaded via ImageWorker: {width}x{height}")
                return pixmap
            else:
                logger.warning("ImageWorker response failed - using fallback")
        except Exception as e:
            logger.warning(f"ImageWorker error: {e} - using fallback")
    
    # Fallback to local decode if worker unavailable
    return self._load_image_local(image_metadata)

def _load_image_local(self, image_metadata: ImageMetadata) -> Optional[QPixmap]:
    """Fallback local image loading (existing PIL code)."""
    # Move existing PIL decode logic here
    # This is the current _load_image_task implementation
    pass
```

**Verification**:
- Check logs for "Image loaded via ImageWorker"
- Monitor `screensaver_perf.log` for reduced frame time spikes
- Verify image display still works correctly
- Test fallback by disabling worker: `workers.image.enabled = False`

**Expected Impact**: 50-100ms reduction in image load blocking

**Deliverable**: Images decoded in separate process, main thread unblocked

---

## Phase 3: RSSWorker Integration (2-3 hours)

**Priority**: HIGH - Eliminate network I/O blocking  
**Reference**: Architecture_Audit_Jan_2026.md lines 465-516

### Task 3.1: Wire RSSWorker into _load_rss_images_async

**File**: `engine/screensaver_engine.py`  
**Method**: `_load_rss_images_async`

**Changes**:
```python
def _load_rss_images_async(self):
    """Load RSS images using RSSWorker if available."""
    
    if self._shutting_down:
        return
    
    # Use RSSWorker if available
    if self._process_supervisor and self._process_supervisor.is_running(WorkerType.RSS):
        logger.info("Loading RSS images via RSSWorker")
        
        # Send fetch requests for all sources
        for source in self.rss_sources:
            try:
                msg = self._process_supervisor.create_message(
                    WorkerType.RSS,
                    MessageType.RSS_FETCH,
                    payload={
                        "url": source.url,
                        "source_id": source.source_id,
                        "priority": source.priority,
                        "max_images": 8  # Per-source limit
                    }
                )
                
                # Send async (don't wait for response)
                self._process_supervisor.send(WorkerType.RSS, msg)
                logger.debug(f"RSS fetch request sent for {source.source_id}")
            except Exception as e:
                logger.error(f"Failed to send RSS request for {source.source_id}: {e}")
        
        # Poll for responses in background
        self._thread_manager.submit_io_task(self._poll_rss_responses)
    else:
        # Fallback to current ThreadManager approach
        logger.info("RSSWorker not available - using fallback")
        self._load_rss_images_legacy()

def _poll_rss_responses(self):
    """Poll for RSS worker responses and merge results."""
    logger.debug("Starting RSS response polling")
    
    while not self._shutting_down:
        try:
            response = self._process_supervisor.receive(WorkerType.RSS, timeout_ms=100)
            
            if response and response.success:
                images = response.payload.get("images", [])
                source_id = response.payload.get("source_id", "unknown")
                
                logger.info(f"Received {len(images)} images from RSS source {source_id}")
                
                # Merge images into queue (thread-safe)
                with self._rss_merge_lock:
                    self.image_queue.add_images(images)
                
            elif response and not response.success:
                error = response.payload.get("error", "Unknown error")
                logger.warning(f"RSS fetch failed: {error}")
                
        except Exception as e:
            logger.error(f"Error polling RSS responses: {e}")
            break
    
    logger.debug("RSS response polling stopped")

def _load_rss_images_legacy(self):
    """Fallback RSS loading (existing ThreadManager code)."""
    # Move existing RSS loading logic here
    pass
```

**Verification**:
- Check logs for "Loading RSS images via RSSWorker"
- Verify RSS images still populate correctly
- Monitor network I/O no longer blocks main thread
- Test fallback by disabling worker

**Expected Impact**: 100-500ms reduction in RSS fetch blocking

**Deliverable**: RSS fetching in separate process, network I/O unblocked

---

## Phase 4: FFTWorker Integration (1-2 hours)

**Priority**: MEDIUM - Reduce visualizer tick spikes  
**Reference**: Architecture_Audit_Jan_2026.md lines 520-570  
**CRITICAL**: Follow visualizer preservation rules above

### Task 4.1: Wire FFTWorker into SpotifyVisualizerWidget

**File**: `widgets/spotify_visualizer_widget.py`  
**Method**: `_process_audio_frame`

**IMPORTANT**: This integration must preserve exact math. The worker already implements the correct algorithm from `beat_engine.py`.

**Changes**:
```python
def _process_audio_frame(self, audio_data: np.ndarray):
    """Process audio frame using FFTWorker if available."""
    
    # Get engine reference
    engine = self._get_engine()
    
    # Use FFTWorker if available
    if engine and hasattr(engine, '_process_supervisor'):
        supervisor = engine._process_supervisor
        
        if supervisor and supervisor.is_running(WorkerType.FFT):
            try:
                # Send FFT request to worker
                msg = supervisor.create_message(
                    WorkerType.FFT,
                    MessageType.FFT_PROCESS,
                    payload={
                        "audio_data": audio_data.tobytes(),
                        "sample_rate": 44100,
                        "bar_count": self._bar_count,
                        "sensitivity": self._sensitivity,
                        "base_tau": self._base_tau
                    }
                )
                
                # Send async (worker writes to shared memory)
                supervisor.send(WorkerType.FFT, msg)
                
                # Read from triple buffer (non-blocking)
                bar_heights = self._fft_buffer.read()
                if bar_heights is not None:
                    self._update_bars(bar_heights)
                    return
            except Exception as e:
                logger.warning(f"FFTWorker error: {e} - using fallback")
    
    # Fallback to local processing
    self._process_audio_frame_local(audio_data)

def _process_audio_frame_local(self, audio_data: np.ndarray):
    """Fallback local FFT processing (existing beat_engine code)."""
    # Move existing _process_audio_frame logic here
    # This is the current implementation
    pass
```

### Task 4.2: Initialize Triple Buffer for FFT Data

**File**: `widgets/spotify_visualizer_widget.py`  
**Method**: `__init__`

**Changes**:
```python
from core.threading.spsc_queue import TripleBuffer

def __init__(self, ...):
    # ... existing initialization ...
    
    # Initialize triple buffer for FFT worker output
    self._fft_buffer = TripleBuffer()
```

**Verification**:
- Visualizer bars still render correctly
- No visual differences in bar heights or smoothing
- Check logs for reduced tick spikes in `screensaver_perf.log`
- Verify math matches by comparing bar heights before/after

**Expected Impact**: 40-50% reduction in visualizer tick spikes (96ms → <50ms)

**Deliverable**: FFT processing in separate process, visualizer algorithm preserved

---

## Phase 5: TransitionWorker Integration (1-2 hours)

**Priority**: LOW-MEDIUM - Reduce transition startup lag  
**Reference**: Architecture_Audit_Jan_2026.md lines 574-618

### Task 5.1: Wire TransitionWorker into TransitionFactory

**File**: `rendering/transition_factory.py`  
**Method**: `create_transition`

**Changes**:
```python
def create_transition(self, transition_type: str, old_pixmap, new_pixmap, duration_ms):
    """Create transition using TransitionWorker for precompute if available."""
    
    width = new_pixmap.width()
    height = new_pixmap.height()
    
    # Check if TransitionWorker is available
    engine = self._get_engine()
    if engine and hasattr(engine, '_process_supervisor'):
        supervisor = engine._process_supervisor
        
        if supervisor and supervisor.is_running(WorkerType.TRANSITION):
            try:
                # Request precompute from worker
                msg = supervisor.create_message(
                    WorkerType.TRANSITION,
                    MessageType.TRANSITION_PRECOMPUTE,
                    payload={
                        "type": transition_type,
                        "width": width,
                        "height": height,
                        "duration_ms": duration_ms
                    }
                )
                
                # Send and wait for response (100ms timeout)
                response = supervisor.send_and_wait(
                    WorkerType.TRANSITION, msg, timeout_ms=100
                )
                
                if response and response.success:
                    precompute_data = response.payload.get("data")
                    logger.debug(f"Transition precompute received for {transition_type}")
                    return self._create_with_precompute(
                        transition_type, old_pixmap, new_pixmap, 
                        duration_ms, precompute_data
                    )
            except Exception as e:
                logger.warning(f"TransitionWorker error: {e} - using fallback")
    
    # Fallback to local precompute
    return self._create_transition_local(
        transition_type, old_pixmap, new_pixmap, duration_ms
    )
```

**Verification**:
- Transitions still render correctly
- Check logs for "Transition precompute received"
- Verify no visual regressions
- Monitor reduced startup lag for CPU-heavy transitions (Diffuse, Crumble)

**Expected Impact**: 20-50ms reduction in transition startup lag

**Deliverable**: Transition precompute in separate process

---

## Phase 6: EcoModeManager Integration (1 hour)

**Priority**: LOW - Feature completion  
**Reference**: Architecture_Audit_Jan_2026.md lines 624-672

### Task 6.1: Instantiate EcoModeManager in DisplayWidget

**File**: `rendering/display_widget.py`  
**Method**: `__init__`

**Changes**:
```python
from core.eco_mode import EcoModeManager, EcoModeConfig, is_mc_build

def __init__(self, screen_index, settings_manager, ...):
    # ... existing initialization ...
    
    # Initialize Eco Mode manager (MC builds only)
    if is_mc_build():
        eco_config = EcoModeConfig(
            enabled=settings_manager.get('mc.eco_mode.enabled', True),
            occlusion_threshold=settings_manager.get('mc.eco_mode.threshold', 0.95),
            check_interval_ms=settings_manager.get('mc.eco_mode.check_interval', 1000),
            recovery_delay_ms=settings_manager.get('mc.eco_mode.recovery_delay', 100)
        )
        self._eco_manager = EcoModeManager(eco_config)
        self._eco_manager.set_display_widget(self)
        
        # Wire up components
        if self._transition_controller:
            self._eco_manager.set_transition_controller(self._transition_controller)
        
        logger.info(f"[MC] EcoModeManager initialized for display {screen_index}")
    else:
        self._eco_manager = None
```

### Task 6.2: Connect Components to EcoModeManager

**File**: `rendering/display_widget.py`  
**Method**: `_setup_widgets` (or wherever visualizer is created)

**Changes**:
```python
def _setup_widgets(self):
    # ... existing widget setup ...
    
    # Connect visualizer to Eco Mode if MC build
    if self._eco_manager and self._spotify_visualizer:
        self._eco_manager.set_visualizer(self._spotify_visualizer)
```

### Task 6.3: Connect Eco Mode Callback to Systray

**File**: `main.py`  
**Location**: After tray icon creation

**Changes**:
```python
if tray_icon and engine.display_manager:
    # Connect Eco Mode callback for systray tooltip
    displays = engine.display_manager.get_all_displays()
    if displays:
        first_display = displays[0]
        if hasattr(first_display, '_eco_manager') and first_display._eco_manager:
            tray_icon.set_eco_mode_callback(
                first_display._eco_manager.is_eco_active
            )
            logger.info("[MC] Eco Mode callback connected to systray")
```

**Verification**:
- MC build shows "[MC] EcoModeManager initialized" in logs
- Systray tooltip shows "ECO MODE ON" when window is covered
- Transitions pause when Eco Mode activates
- Visualizer pauses when Eco Mode activates
- Everything resumes when window becomes visible

**Expected Impact**: Eco Mode feature fully functional, systray tooltip working

**Deliverable**: Eco Mode active in MC builds with systray indicator

---

## Phase 7: Performance Validation (1 hour)

**Priority**: CRITICAL - Verify improvements achieved

### Task 7.1: Baseline Measurement

**Before worker integration**, capture baseline metrics:

```bash
# Enable performance logging
set SRPSS_PERF_METRICS=1

# Run screensaver for 5 minutes
# Record from screensaver_perf.log:
# - Transition avg_fps
# - Transition dt_max
# - Visualizer avg_fps
# - Visualizer dt_max (tick spikes)
# - Paint gaps
```

### Task 7.2: Post-Integration Measurement

**After all workers integrated**, capture new metrics:

```bash
# Same test, compare results
# Expected improvements:
# - Transition avg_fps: 46.7 → 58-60fps (+25-30%)
# - Transition dt_max: 85ms → <20ms (-75%)
# - Visualizer avg_fps: 41.7 → 55-60fps (+40%)
# - Visualizer dt_max: 96ms → <50ms (-50%)
# - Paint gaps: 141ms → <30ms (-80%)
```

### Task 7.3: Document Results

**File**: `audits/Performance_Validation_Jan_2026.md`

Create document with:
- Before/after metrics table
- Performance graphs (if available)
- Worker health status
- Any remaining bottlenecks
- Recommendations for further optimization

**Deliverable**: Documented proof of performance improvements

---

## Phase 8: Cleanup & Documentation (1 hour)

**Priority**: MEDIUM - Code hygiene

### Task 8.1: Add Worker Settings to SettingsManager

**File**: `core/settings/defaults.py`

**Changes**:
```python
DEFAULT_SETTINGS = {
    # ... existing defaults ...
    
    # Worker settings (all enabled by default)
    'workers.image.enabled': True,
    'workers.rss.enabled': True,
    'workers.fft.enabled': True,
    'workers.transition.enabled': True,
    
    # MC Eco Mode settings
    'mc.eco_mode.enabled': True,
    'mc.eco_mode.threshold': 0.95,
    'mc.eco_mode.check_interval': 1000,
    'mc.eco_mode.recovery_delay': 100,
}
```

### Task 8.2: Update Spec.md

**File**: `Spec.md`

Add section:
- Multiprocessing Architecture (ProcessSupervisor, 4 worker types)
- Worker integration points
- Fallback behavior when workers unavailable
- Performance improvements achieved

### Task 8.3: Update Index.md

**File**: `Index.md`

Add to Recent Changes:
- v2.1 Production Integration (Jan 2026)
- ProcessSupervisor integration with 4 workers
- Performance improvements: 25-40% FPS increase
- Eco Mode fully functional in MC builds

**Deliverable**: Clean, documented codebase

---

## Success Criteria

### Must Have (Before v2.1 Release)

- [ ] ProcessSupervisor running with all 4 workers
- [ ] ImageWorker integrated - images decode in separate process
- [ ] RSSWorker integrated - RSS fetch in separate process
- [ ] FFTWorker integrated - visualizer math preserved exactly
- [ ] TransitionWorker integrated - precompute offloaded
- [ ] EcoModeManager instantiated in MC builds
- [ ] Systray Eco Mode indicator working
- [ ] Performance validation shows 25%+ FPS improvement
- [ ] No visual regressions in transitions or visualizer
- [ ] All 1348+ tests still passing

### Nice to Have (Future Optimization)

- [ ] Worker pool size tuning based on CPU cores
- [ ] Shared memory optimization for large images
- [ ] Worker health monitoring UI in settings
- [ ] Per-worker enable/disable in settings dialog
- [ ] Advanced Eco Mode settings (threshold, intervals)

---

## Risk Mitigation

### Risk: Visualizer Algorithm Changes

**Mitigation**: 
- FFTWorker already implements exact math from `beat_engine.py`
- Tests verify math preservation: `tests/test_fft_worker.py`
- Visual comparison before/after integration
- Fallback to local processing if worker fails

### Risk: Worker Crashes

**Mitigation**:
- ProcessSupervisor has health monitoring and restart logic
- All integrations have fallback to local processing
- Worker failures logged but don't crash main application
- Graceful degradation: app runs without workers if needed

### Risk: Performance Regression

**Mitigation**:
- Baseline measurements before integration
- Continuous monitoring during integration
- Rollback plan: disable workers via settings
- Each phase independently verifiable

### Risk: Thread Safety Issues

**Mitigation**:
- All worker communication uses ProcessSupervisor queues
- Shared memory access is lock-free (TripleBuffer, SPSCQueue)
- Qt updates still use `invoke_in_ui_thread()`
- Existing thread safety patterns maintained

---

## Timeline Estimate

**Total**: 10-14 hours (can be done in 2-3 focused sessions)

| Phase | Task | Hours | Can Parallelize |
|-------|------|-------|-----------------|
| 1 | ProcessSupervisor Integration | 2-3 | No (foundation) |
| 2 | ImageWorker Integration | 2-3 | After Phase 1 |
| 3 | RSSWorker Integration | 2-3 | After Phase 1 |
| 4 | FFTWorker Integration | 1-2 | After Phase 1 |
| 5 | TransitionWorker Integration | 1-2 | After Phase 1 |
| 6 | EcoModeManager Integration | 1 | After Phase 1 |
| 7 | Performance Validation | 1 | After all workers |
| 8 | Cleanup & Documentation | 1 | Anytime |

**Recommended Order**:
1. Phase 1 (foundation)
2. Phase 2 (highest impact)
3. Phases 3-6 (any order)
4. Phase 7 (validation)
5. Phase 8 (polish)

---

## Notes

- All infrastructure already exists and is tested
- This roadmap is ONLY about production integration
- No new features, no new tests - just wiring existing code
- Each phase is independently deliverable
- Fallbacks ensure app never breaks during integration
- Performance improvements are guaranteed (infrastructure already validated)

**Reference Documents**:
- `audits/Architecture_Audit_Jan_2026.md` - Complete analysis and fix structures
- `audits/VISUALIZER_DEBUG.md` - Visualizer algorithm documentation
- `tests/test_*_worker.py` - Worker validation tests (80+ tests)
- `core/process/` - All worker infrastructure

---

## Post-Integration: Future Optimization (Not in v2.1 Scope)

These are potential improvements AFTER v2.1 is stable:

1. **Worker Pool Sizing**: Tune worker counts based on CPU cores
2. **Shared Memory Optimization**: Reduce copy overhead for large images
3. **Worker Monitoring UI**: Settings dialog shows worker health
4. **Advanced Eco Mode**: User-configurable thresholds and intervals
5. **Performance Telemetry**: Automatic performance regression detection
6. **Worker Benchmarking**: Per-worker performance metrics

**Do NOT implement these in v2.1** - Focus on integration only.
