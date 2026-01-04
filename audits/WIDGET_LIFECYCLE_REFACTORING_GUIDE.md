# Widget Lifecycle Refactoring Guide (2026 Alignment)

_Role_: companion deep dive for **Phase 4 – Widget & Settings Modularity** from `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md`. Use this guide when touching widget lifecycles, factories, or settings; keep the consolidated plan as the higher-level tracker.

## 1. Current Snapshot (Dec 2025)
- All overlay widgets inherit the unified `BaseOverlayWidget` with lifecycle states defined in `widgets/base_overlay_widget.py` (`CREATED → INITIALIZED → ACTIVE ⇄ HIDDEN → DESTROYED`).
- Widget factories (`rendering/widget_factories.py`) exist but WidgetManager still contains widget-specific branching and lifecycle coordination.
- Overlay timers should come from `widgets/overlay_timers.py` (ThreadManager-first, QTimer fallback) yet some widgets still manage timers manually.
- Settings models (`core/settings/models.py`) exist but random access via `SettingsManager.get()` persists in parts of WidgetManager/DisplayWidget/UI tabs.

#### 2. WeatherWidget (`widgets/weather_widget.py`)
**Current Pattern**:
- Created in `widget_manager._create_weather_widget()`
- Uses `BaseOverlayWidget` base class
- Has update timer for weather refresh
- Cleanup via `deleteLater()`

**Issues**:
- Timer not registered with ResourceManager
- No cleanup verification
- Update cycle not stopped explicitly
- API connections not closed properly

#### 3. MediaWidget (`widgets/media_widget.py`)
**Current Pattern**:
- Created in `widget_manager._create_media_widget()`
- Uses `BaseOverlayWidget` base class
- Has polling timer for media state
- Complex state machine

**Issues**:
- Timer lifecycle unclear
- Media controller not cleaned up
- Volume widget lifecycle tied to parent
- State transitions not validated

#### 4. SpotifyVisualizerWidget (`widgets/spotify_visualizer_widget.py`)
**Current Pattern**:
- Created in `widget_manager._create_spotify_visualizer_widget()`
- Uses `BaseOverlayWidget` base class
- Has audio worker thread
- GL overlay coordination

**Issues**:
- Audio worker cleanup unclear
- GL overlay lifecycle separate
- Beat engine shared state
- Thread safety concerns

#### 5. RedditWidget (`widgets/reddit_widget.py`)
**Current Pattern**:
- Created in `widget_manager._create_reddit_widget()`
- Uses `BaseOverlayWidget` base class
- Has content rotation timer
- URL opening coordination

**Issues**:
- Timer not tracked
- Content state not persisted
- Cleanup incomplete

#### 6. SpotifyVolumeWidget (`widgets/spotify_volume_widget.py`)
**Current Pattern**:
- Created alongside MediaWidget
- Standalone lifecycle
- Has flush timer for volume changes

**Issues**:
- Timer not registered
- Controller cleanup unclear
- Parent widget coordination

---

## 3. Alignment Goals
1. **WidgetManager as Coordinator** – no widget-specific setup logic inside `rendering/widget_manager.py`. It should request widgets from factories, call lifecycle methods, coordinate overlay fades, and manage Z-order.
2. **Factories & Positioner as Single Sources** – all widget creation logic must live in `rendering/widget_factories.py`. `rendering/widget_positioner.py` owns positioning/collision rules. WidgetManager simply wires these pieces.
3. **Thread/Resource Discipline** – timers via `widgets/overlay_timers.py`, background work through ThreadManager, ResourceManager tracking for all Qt objects/timers per widget.
4. **Typed Settings** – `core/settings/models.py` models drive both runtime and UI; the UI tabs should consume dataclasses rather than manual `settings.get`.
5. **Overlay Guidelines** – `Docs/10_WIDGET_GUIDELINES.md` remains canonical for fade synchronization, shadow behaviour, stacking predictions; ensure code+UI stay compliant.

---

## Implementation Checklist

### ✅ Phase 1: Audit Current State (4 hours)

- [ ] **Document ClockWidget lifecycle** (30 min)
  - [ ] Map creation points
  - [ ] Map cleanup points
  - [ ] Identify resource leaks
  - [ ] Document timer usage

- [ ] **Document WeatherWidget lifecycle** (30 min)
  - [ ] Map creation points
  - [ ] Map cleanup points
  - [ ] Identify API connection handling
  - [ ] Document timer usage

- [ ] **Document MediaWidget lifecycle** (45 min)
  - [ ] Map creation points
  - [ ] Map cleanup points
  - [ ] Document media controller lifecycle
  - [ ] Document volume widget coordination
  - [ ] Identify timer usage

- [ ] **Document SpotifyVisualizerWidget lifecycle** (1 hour)
  - [ ] Map creation points
  - [ ] Map cleanup points
  - [ ] Document audio worker lifecycle
  - [ ] Document GL overlay coordination
  - [ ] Document beat engine usage
  - [ ] Identify thread safety issues

- [ ] **Document RedditWidget lifecycle** (30 min)
  - [ ] Map creation points
  - [ ] Map cleanup points
  - [ ] Document timer usage
  - [ ] Document URL handling

- [ ] **Document SpotifyVolumeWidget lifecycle** (30 min)
  - [ ] Map creation points
  - [ ] Map cleanup points
  - [ ] Document controller lifecycle
  - [ ] Document timer usage

- [ ] **Create lifecycle flow diagrams** (30 min)
  - [ ] Current state diagram
  - [ ] Target state diagram
  - [ ] Transition diagram

### ✅ Phase 2: Design Unified Lifecycle (6 hours)

- [ ] **Define lifecycle states** (1 hour)
  - [ ] Document state meanings
  - [ ] Define valid transitions
  - [ ] Define invalid transitions
  - [ ] Document state invariants

- [ ] **Design BaseOverlayWidget enhancements** (2 hours)
  - [ ] Add lifecycle state tracking
  - [ ] Add state transition methods
  - [ ] Add ResourceManager integration
  - [ ] Add thread safety with locks
  - [ ] Define abstract methods for subclasses

- [ ] **Specify ResourceManager integration** (1 hour)
  - [ ] Define registration patterns
  - [ ] Define cleanup ordering
  - [ ] Document resource types
  - [ ] Specify error handling

- [ ] **Define cleanup ordering** (1 hour)
  - [ ] Widget internal cleanup first
  - [ ] Child widgets cleanup second
  - [ ] ResourceManager cleanup third
  - [ ] Qt deleteLater last

- [ ] **Document lifecycle contracts** (1 hour)
  - [ ] Pre-conditions for each method
  - [ ] Post-conditions for each method
  - [ ] Thread safety guarantees
  - [ ] Error handling requirements

### ✅ Phase 3: Implement Base Classes (8 hours)

- [ ] **Update BaseOverlayWidget** (4 hours)
  - [ ] Add lifecycle state enum
  - [ ] Add state tracking fields
  - [ ] Implement `initialize()` method
  - [ ] Implement `activate()` method
  - [ ] Implement `deactivate()` method
  - [ ] Implement `cleanup()` method
  - [ ] Add state query methods
  - [ ] Add logging throughout

- [ ] **Integrate ResourceManager** (2 hours)
  - [ ] Add ResourceManager instance
  - [ ] Register in `initialize()`
  - [ ] Cleanup in `cleanup()`
  - [ ] Document usage patterns

- [ ] **Add lifecycle state tracking** (1 hour)
  - [ ] Add state field
  - [ ] Add state lock
  - [ ] Add state transition validation
  - [ ] Add state change logging

- [ ] **Implement automatic cleanup** (1 hour)
  - [ ] Ensure cleanup on state transitions
  - [ ] Handle cleanup errors gracefully
  - [ ] Verify no resource leaks

### ✅ Phase 4: Migrate ClockWidget (2 hours)

- [ ] **Update ClockWidget initialization** (30 min)
  - [ ] Move setup code to `_initialize_impl()`
  - [ ] Register timers with ResourceManager
  - [ ] Remove old initialization code

- [ ] **Update ClockWidget activation** (30 min)
  - [ ] Move show logic to `_activate_impl()`
  - [ ] Start timers in activation
  - [ ] Remove old show code

- [ ] **Update ClockWidget deactivation** (30 min)
  - [ ] Move hide logic to `_deactivate_impl()`
  - [ ] Stop timers in deactivation
  - [ ] Remove old hide code

- [ ] **Update ClockWidget cleanup** (30 min)
  - [ ] Move cleanup to `_cleanup_impl()`
  - [ ] Verify ResourceManager cleanup
  - [ ] Remove old cleanup code

### ✅ Phase 5: Migrate WeatherWidget (2 hours)

- [ ] **Update WeatherWidget initialization** (30 min)
  - [ ] Move setup to `_initialize_impl()`
  - [ ] Register update timer
  - [ ] Initialize API connections

- [ ] **Update WeatherWidget activation** (30 min)
  - [ ] Start update timer in `_activate_impl()`
  - [ ] Begin weather updates

- [ ] **Update WeatherWidget deactivation** (30 min)
  - [ ] Stop update timer in `_deactivate_impl()`
  - [ ] Pause weather updates

- [ ] **Update WeatherWidget cleanup** (30 min)
  - [ ] Close API connections in `_cleanup_impl()`
  - [ ] Clear cached data
  - [ ] Verify no leaks

### ✅ Phase 5b: Overlay Geometry & Padding Alignment (weather-first rollout) (4 hours)

_Research summary (Jan 2026)_:
- WeatherWidget applies asymmetric padding (left = 21 px, right = 28 px) but only right anchors compensate, so visual content drifts past configured margins on other anchors.
- BaseOverlayWidget’s `_update_position()` aligns the widget frame, not the “visual card” inside padding, so any widget with interior padding appears offset from margins, and stacking/pixel-shift inherit those errors.
- Clock/Media/Reddit already have custom visual-offset math; Weather duplicates this ad‑hoc and still fails on pixel shift.

**Action Items**
1. **BaseOverlayWidget visual padding helpers**
   - [ ] Add `set_visual_padding(top, right, bottom, left)` (default = 0) stored on the base class.
   - [ ] Update `_update_position()` to subtract/add the appropriate padding deltas when anchoring so that the visible card edge, not the QLabel frame, honors margins.
   - [ ] Ensure pixel shift + stack offsets apply after padding adjustments; notify `PixelShiftManager` of the new “true origin” (see Media/Reddit pattern).
2. **WeatherWidget migration (first adopter)**
   - [ ] Remove custom `_update_position()`; configure padding via the new helper.
   - [ ] Keep separator/forecast logic untouched but confirm cached geometry updates still call into base `_update_position()`.
   - [ ] Validate all nine anchors with pixel shift enabled; capture before/after in `tests/test_widget_layouts.py`.
3. **Other widget adoption plan**
   - [ ] Inventory widgets using internal padding or manual offsets (Media, Reddit, SpotifyVisualizer card, future widgets).
   - [ ] For each, migrate to the helper or document why existing visual-offset routines (e.g., Clock analogue mode) remain custom.
   - [ ] Add regression tests per widget once migrated (geometry assertions with stacking + pixel shift).
4. **Documentation & Guidelines**
   - [ ] Update `Docs/10_WIDGET_GUIDELINES.md` with a “visual padding alignment” rule referencing the helper.
   - [ ] Note the new helper in `Index.md` under `widgets/base_overlay_widget.py`.
   - [ ] Reference this subsection from `audits/v2_0_Roadmap.md` and `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md` so future phases schedule the rollout.

### ✅ Phase 6: Migrate MediaWidget (3 hours)

- [ ] **Update MediaWidget initialization** (45 min)
  - [ ] Move setup to `_initialize_impl()`
  - [ ] Initialize media controller
  - [ ] Register polling timer
  - [ ] Setup volume widget

- [ ] **Update MediaWidget activation** (45 min)
  - [ ] Start polling in `_activate_impl()`
  - [ ] Activate volume widget
  - [ ] Begin media updates

- [ ] **Update MediaWidget deactivation** (45 min)
  - [ ] Stop polling in `_deactivate_impl()`
  - [ ] Deactivate volume widget
  - [ ] Pause media updates

- [ ] **Update MediaWidget cleanup** (45 min)
  - [ ] Clean up controller in `_cleanup_impl()`
  - [ ] Clean up volume widget
  - [ ] Verify no leaks

### ✅ Phase 7: Migrate SpotifyVisualizerWidget (4 hours)

- [ ] **Update SpotifyVisualizerWidget initialization** (1 hour)
  - [ ] Move setup to `_initialize_impl()`
  - [ ] Initialize audio worker
  - [ ] Setup GL overlay
  - [ ] Register beat engine

- [ ] **Update SpotifyVisualizerWidget activation** (1 hour)
  - [ ] Start audio worker in `_activate_impl()`
  - [ ] Activate GL overlay
  - [ ] Begin visualizer updates

- [ ] **Update SpotifyVisualizerWidget deactivation** (1 hour)
  - [ ] Stop audio worker in `_deactivate_impl()`
  - [ ] Deactivate GL overlay
  - [ ] Pause visualizer updates

- [ ] **Update SpotifyVisualizerWidget cleanup** (1 hour)
  - [ ] Clean up audio worker in `_cleanup_impl()`
  - [ ] Clean up GL overlay
  - [ ] Clean up beat engine
  - [ ] Verify thread safety
  - [ ] Verify no leaks

### ✅ Phase 8: Migrate RedditWidget (2 hours)

- [ ] **Update RedditWidget initialization** (30 min)
  - [ ] Move setup to `_initialize_impl()`
  - [ ] Register rotation timer

- [ ] **Update RedditWidget activation** (30 min)
  - [ ] Start rotation in `_activate_impl()`
  - [ ] Begin content updates

- [ ] **Update RedditWidget deactivation** (30 min)
  - [ ] Stop rotation in `_deactivate_impl()`
  - [ ] Pause content updates

- [ ] **Update RedditWidget cleanup** (30 min)
  - [ ] Clear content in `_cleanup_impl()`
  - [ ] Verify no leaks

### ✅ Phase 9: Migrate SpotifyVolumeWidget (2 hours)

- [ ] **Update SpotifyVolumeWidget initialization** (30 min)
  - [ ] Move setup to `_initialize_impl()`
  - [ ] Initialize controller
  - [ ] Register flush timer

- [ ] **Update SpotifyVolumeWidget activation** (30 min)
  - [ ] Start monitoring in `_activate_impl()`

- [ ] **Update SpotifyVolumeWidget deactivation** (30 min)
  - [ ] Stop monitoring in `_deactivate_impl()`

- [ ] **Update SpotifyVolumeWidget cleanup** (30 min)
  - [ ] Clean up controller in `_cleanup_impl()`
  - [ ] Flush pending changes
  - [ ] Verify no leaks

### ✅ Phase 10: Update Widget Manager (6 hours)

- [ ] **Update widget creation** (2 hours)
  - [ ] Call `initialize()` after creation
  - [ ] Handle initialization failures
  - [ ] Log initialization status

- [ ] **Update widget activation** (2 hours)
  - [ ] Call `activate()` when showing
  - [ ] Handle activation failures
  - [ ] Log activation status

- [ ] **Update widget cleanup** (2 hours)
  - [ ] Call `cleanup()` on all widgets
  - [ ] Ensure proper ordering
  - [ ] Handle cleanup errors
  - [ ] Verify no leaks

### ✅ Phase 11: Update Display Widget (2 hours)

- [ ] **Update widget setup** (1 hour)
  - [ ] Use new lifecycle methods
  - [ ] Handle initialization failures
  - [ ] Log setup status

- [ ] **Update widget teardown** (1 hour)
  - [ ] Use new lifecycle methods
  - [ ] Ensure proper cleanup ordering
  - [ ] Verify no leaks

### ✅ Phase 12: Testing (8 hours)

- [ ] **Write lifecycle unit tests** (3 hours)
  - [ ] Test state transitions for each widget
  - [ ] Test invalid transitions
  - [ ] Test error handling
  - [ ] Test thread safety

- [ ] **Write integration tests** (3 hours)
  - [ ] Test widget manager coordination
  - [ ] Test full lifecycle cycles
  - [ ] Test repeated start/stop
  - [ ] Test error recovery

- [ ] **Memory leak testing** (2 hours)
  - [ ] Run 100+ lifecycle cycles
  - [ ] Monitor memory usage
  - [ ] Verify ResourceManager cleanup
  - [ ] Check for Qt object leaks

---

## Test Requirements

### Unit Tests

```python
# test_widget_lifecycle.py

def test_clock_widget_lifecycle():
    """Test ClockWidget lifecycle"""
    widget = ClockWidget()
    assert widget.get_lifecycle_state() == WidgetLifecycleState.CREATED
    
    assert widget.initialize()
    assert widget.get_lifecycle_state() == WidgetLifecycleState.INITIALIZED
    
    assert widget.activate()
    assert widget.get_lifecycle_state() == WidgetLifecycleState.ACTIVE
    
    assert widget.deactivate()
    assert widget.get_lifecycle_state() == WidgetLifecycleState.HIDDEN
    
    widget.cleanup()
    assert widget.get_lifecycle_state() == WidgetLifecycleState.DESTROYED

def test_invalid_state_transition():
    """Test invalid state transitions are rejected"""
    widget = ClockWidget()
    assert not widget.activate()  # Can't activate from CREATED
    assert widget.get_lifecycle_state() == WidgetLifecycleState.CREATED

def test_lifecycle_no_memory_leaks():
    """Test 100 lifecycle cycles don't leak memory"""
    import gc
    import tracemalloc
    
    tracemalloc.start()
    baseline = tracemalloc.get_traced_memory()[0]
    
    for i in range(100):
        widget = ClockWidget()
        widget.initialize()
        widget.activate()
        widget.deactivate()
        widget.cleanup()
        del widget
        gc.collect()
    
    current = tracemalloc.get_traced_memory()[0]
    growth = current - baseline
    
    # Allow 1MB growth for 100 cycles
    assert growth < 1024 * 1024, f"Memory grew by {growth} bytes"
```

### Integration Tests

```python
# test_widget_manager_lifecycle.py

def test_widget_manager_creates_and_cleans_widgets():
    """Test widget manager handles full lifecycle"""
    manager = WidgetManager(settings)
    
    # Create widgets
    manager.create_all_widgets()
    assert all(w.is_initialized() for w in manager.get_all_widgets())
    
    # Activate widgets
    manager.activate_all_widgets()
    assert all(w.is_active() for w in manager.get_all_widgets())
    
    # Deactivate widgets
    manager.deactivate_all_widgets()
    assert all(not w.is_active() for w in manager.get_all_widgets())
    
    # Cleanup widgets
    manager.cleanup_all_widgets()
    assert all(w.get_lifecycle_state() == WidgetLifecycleState.DESTROYED 
              for w in manager.get_all_widgets())
```

---

## 5. Success Criteria
- WidgetManager acts purely as coordinator; factories/positioner/settings models own logic.
- Every widget honours lifecycle state machine with ResourceManager tracking and ThreadManager-backed timers.
- Typed settings usage documented in Spec + UI; no lingering raw `settings.get` in runtime paths.
- Overlay guidelines met across all widgets; no regressions in fade/shadow behaviour.
- Tests (unit + integration) cover new behaviour; Docs/TestSuite/Index and consolidated plan updated.

---

## 6. References
- `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md` – Phase 0/4/5 tasks
- `Spec.md` – Widget lifecycle summary, settings schema, overlay policies
- `Index.md` – Module ownership (WidgetManager, factories, positioner, shadow utils, overlay timers)
- `Docs/10_WIDGET_GUIDELINES.md` – Canonical overlay behaviour/style guide
- `Docs/TestSuite.md` – Lifecycle + factory test documentation
