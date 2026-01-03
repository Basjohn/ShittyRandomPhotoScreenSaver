# SRPSS v2.0 Development Roadmap (Live Checklist)

**Status**: Active development roadmap integrating Minor Tasks, AAMP2026 phases, and architectural improvements.

**Policy**: Document-first, test-driven, centralized managers, no regressions. Follow checkbox order unless explicitly redirected.

---

## Phase 0: Foundation & Quick Wins (Week 1-2)

### 0.1 Critical Performance Fix - Visualizer Gating
**Priority**: CRITICAL (Immediate resource savings)
**Dependencies**: None
**Reference**: `audits/Minor Tasks.md #1`, `audits/VISUALIZER_DEBUG.md`

- [x] **Snapshot current visualizer logic**: Create `/bak/widgets/spotify_visualizer_widget.py` & Beat Engine before changes
- [x] **Implement playback state detection**: Add Spotify state monitoring to `_SpotifyBeatEngine`
- [x] **Gate FFT calculations**: Halt processing when `state != PLAYING` (preserve 1-bar floor)
- [x] **Add sparse polling**: Leverage existing media widget polling/events to feed `handle_media_update` (no separate visualizer poll loop required)
- [x] **Preserve dynamic floor pipeline**: Ensure exact preservation of current logic (VISUALIZER_DEBUG.md lines 31-94)
- [x] **Create synthetic test**: `tests/test_spotify_visualizer_integration.py` to verify no visual fidelity loss
- [x] **Performance validation**: Measure CPU savings with `SRPSS_PERF_METRICS=1`
- [x] **Update documentation**: Record changes in VISUALIZER_DEBUG.md

**Critical Logic to Preserve**:
```python
# From VISUALIZER_DEBUG.md - MUST preserve exactly:
np.log1p(mag, out=mag)
np.power(mag, 1.2, out=mag)
# Dynamic floor with adaptive sensitivity
base_noise_floor = max(self._min_floor, min(self._max_floor, noise_floor_base / auto_multiplier))
expansion = expansion_base * max(0.55, auto_multiplier ** 0.35)
# Smoothing with rise/decay tau
alpha_rise = 1.0 - math.exp(-dt / (base_tau * 0.35))
alpha_decay = 1.0 - math.exp(-dt / (base_tau * 3.0))
```

### 0.2 Widget Positioning System Audit
**Priority**: High (User experience fixes)
**Dependencies**: None
**Reference**: `audits/Minor Tasks.md #2`

- [ ] **Audit WidgetPositioner**: Review all 9 anchor positions for accuracy *(tests were missing coverage for TOP_CENTER/MIDDLE anchors – see `tests/test_widget_positioner.py` updates)*
- [ ] **Test Reddit 2 specifically**: Verify middle/center positioning works correctly
- [ ] **Check collision detection**: Validate multi-widget stacking scenarios
- [ ] **Verify stack predictor**: Ensure `ui/widget_stack_predictor.py` alignment accuracy
- [ ] **Detect positioning system conflicts**: Keep `PositionAnchor`, `RedditPosition`, and predictor position keys in sync
- [x] **Create comprehensive test**: `tests/test_widget_positioning_comprehensive.py` (multi-widget stacking + enum sync)
- [ ] **Document edge cases**: Record any limitations or special cases found
- [ ] **Fix identified issues**: Address any positioning problems discovered

### 0.3 Settings Dialog Window State Persistence
**Priority**: Medium (Quality of life)
**Dependencies**: None
**Reference**: `audits/Minor Tasks.md #3`

- **Risks & Guidance**: Touches SettingsManager schema, dialog lifecycle, and multi-monitor detection. Need typed settings migration, defensive fallbacks when saved displays disappear, and isolation between MC/normal profiles. Plan thorough manual validation on systems with changing monitor layouts before shipping.

- [ ] **Add geometry settings**: Extend SettingsManager models for window state
- [ ] **Implement save/restore**: Save geometry on close, restore on open
- [ ] **Handle multi-monitor**: Add fallback if saved display unavailable
- [ ] **Test MC vs normal**: Ensure profile separation works correctly
- [ ] **Create test**: `tests/test_settings_dialog_persistence.py`

### 0.4 Double-Click Navigation
**Priority**: Medium (User interaction)
**Dependencies**: None
**Reference**: `audits/Minor Tasks.md #4`

- **Risks & Guidance**: `InputHandler` changes affect global shortcuts; must gate strictly (Ctrl-held/hard-exit), perform widget hit-testing to avoid accidental skips, and add visual feedback without extra timers. Requires regression passes for existing key/mouse flows and overlay interaction, plus careful unit + manual testing before enabling.

- [ ] **Add double-click handler**: Implement in `InputHandler`
- [ ] **Filter widget areas**: Don't trigger when clicking widgets
- [ ] **Respect interaction gating**: Only work in Ctrl-held or hard-exit modes
- [ ] **Add visual feedback**: Optional halo half opacity flash on double-click
- [ ] **Create test**: `tests/test_double_click_navigation.py`

---

## Phase 1: Process Isolation Foundations (Week 3-4)

### 1.1 Architecture Design & Contracts
**Priority**: High (Foundation for multiprocessing)
**Dependencies**: Phase 0 complete
**Reference**: `audits/AAMP2026_Phase_1_Detailed.md`

- [ ] **Worker Contract RFC**: Finalize worker roles and responsibilities
  - [ ] ImageWorker: decode/prescale with `path|scaled:WxH` cache keys
  - [ ] RSSWorker: fetch/parse/mirror with validated ImageMetadata
  - [ ] FFTWorker: loopback ingest + smoothing + ghost envelopes
  - [ ] TransitionPrepWorker: CPU precompute payloads
- [ ] **Message Schemas**: Define immutable request/response formats
  - [ ] Common fields: seq_no, correlation_id, timestamps, payload_size
  - [ ] Size caps per channel with rejection logic
  - [ ] No Qt objects across process boundaries
- [ ] **Shared Memory Schema**: RGBA/FFT headers with generation tracking
- [ ] **Process Supervisor Skeleton**: `core/process/` API surface
  - [ ] start/stop/restart methods
  - [ ] Health monitoring with heartbeat/backoff
  - [ ] Settings gates for worker enable/disable
- [ ] **Queue & Backpressure Rules**: Non-blocking poll, drop-old policy
- [ ] **Testing Strategy Design**: Worker simulators with failure injection

### 1.2 Visualizer Logic Preservation
**Priority**: CRITICAL (No regression)
**Dependencies**: Phase 0.1 complete
**Reference**: `audits/VISUALIZER_DEBUG.md`, `audits/AAMP2026_Phase_2_Detailed.md` lines 25-94

- [ ] **Create visualizer baseline test**: Capture current `_fft_to_bars` behavior
- [ ] **Document exact FFT pipeline**: Preserve all mathematical operations
- [ ] **Snapshot beat engine**: `/bak/widgets/beat_engine.py` before worker migration
- [ ] **Verify synthetic test**: Ensure `tests/test_visualizer_distribution.py` passes
- [ ] **Create preservation test**: Assert FFT output matches current implementation

---

## Phase 2: Pipeline Offload Implementation (Week 5-6)

### 2.1 Image Worker Implementation
**Priority**: High (Performance foundation)
**Dependencies**: Phase 1 complete
**Reference**: `audits/AAMP2026_Phase_2_Detailed.md`

- [ ] **Port decode/prescale**: Move to worker with shared-memory output
- [ ] **Preserve cache semantics**: Maintain `path|scaled:WxH` key strategy
- [ ] **Ratio policy enforcement**: Local vs RSS mix preserved
- [ ] **Integration tests**: End-to-end latency validation
- [ ] **Performance baselines**: Record before/after metrics

### 2.2 RSS Worker Implementation
**Priority**: High (Content pipeline)
**Dependencies**: Phase 1 complete
**Reference**: `audits/AAMP2026_Phase_2_Detailed.md`

- [ ] **Move fetch/parse**: RSS/JSON processing in worker
- [ ] **Disk mirror integration**: Maintain rotation rules and TTL
- [ ] **Metadata validation**: Ensure ImageMetadata integrity
- [ ] **Error handling**: Non-blocking with graceful degradation

### 2.3 FFT/Beat Worker Migration
**Priority**: CRITICAL (Preserve visualizer fidelity)
**Dependencies**: Phase 1 complete, visualizer baseline captured
**Reference**: `audits/AAMP2026_Phase_2_Detailed.md` lines 25-94

- [ ] **Extract FFT pipeline**: Move `_SpotifyBeatEngine` compute to worker
- [ ] **Preserve exact math**: All operations from VISUALIZER_DEBUG.md must match
- [ ] **Maintain smoothing**: Rise/decay tau, dynamic floor, adaptive sensitivity
- [ ] **Triple buffer integration**: Non-blocking UI consumption
- [ ] **Synthetic test rerun**: Verify worker output matches baseline exactly
- [ ] **Performance validation**: Ensure dt_max independence

### 2.4 Transition Precompute Worker
**Priority**: Medium (Transition performance)
**Dependencies**: Phase 1 complete
**Reference**: `audits/AAMP2026_Phase_2_Detailed.md`

- [ ] **CPU precompute offload**: Lookup tables, block sequences
- [ ] **Settings integration**: Honor duration/direction overrides
- [ ] **Deterministic seeding**: Preserve randomization behavior

---

## Phase 3: GL Compositor & Transition Reliability (Week 7-8)

### 3.1 GLStateManager Rollout
**Priority**: High (GL stability)
**Dependencies**: Phase 2 complete
**Reference**: `audits/AAMP2026_Phase_3_Detailed.md`

- [ ] **Apply to overlays**: `widgets/spotify_bars_gl_overlay.py`, GL warmup paths
- [ ] **State transitions**: READY→ERROR→DESTROYING validation
- [ ] **Centralized error handling**: GLStateManager emits, compositor responds
- [ ] **Integration tests**: GL demotion scenarios (Group A→B→C)

### 3.2 Transition Controller Alignment
**Priority**: High (Transition reliability)
**Dependencies**: Phase 3.1 complete
**Reference**: `audits/AAMP2026_Phase_3_Detailed.md`

- [ ] **TransitionStateManager integration**: CPU + GL parity
- [ ] **Enforce snap_to_new=True**: All cleanup paths
- [ ] **Watchdog standardization**: Per-transition telemetry
- [ ] **Visual regression tests**: Final frame correctness

### 3.3 Visualizer Smart Positioning
**Priority**: Medium (User experience)
**Dependencies**: Phase 0.2 complete
**Reference**: `audits/Minor Tasks.md #6`

- [ ] **Detect top position conflicts**: Visualizer + media widget using top anchors
- [ ] **Calculate smart offset**: Place visualizer below media with same padding
- [ ] **Handle edge cases**: Media disabled, different monitors
- [ ] **Update WidgetPositioner**: Integrate smart positioning logic
- [ ] **Test all combinations**: All top position scenarios

---

## Phase 4: Widget & Settings Modularity (Week 9-10)

### 4.1 WidgetManager Slim-Down
**Priority**: High (Architectural cleanup)
**Dependencies**: Phase 3 complete
**Reference**: `audits/AAMP2026_Phase_4_Detailed.md`

- [ ] **Remove widget-specific logic**: Delegate to factories + positioner
- [ ] **Minimal API**: fade/raise/start/stop coordination only
- [ ] **Factory integration**: WidgetFactoryRegistry for creation
- [ ] **ResourceManager lifecycle**: Centralized cleanup
- [ ] **Lock-free patterns**: Document any unavoidable locks

### 4.2 Modal Settings Conversion
**Priority**: High (User experience)
**Dependencies**: Phase 4.1 complete
**Reference**: `audits/AAMP2026_Phase_4_Detailed.md`, `audits/setting manager defaults/Setting Defaults Guide.txt`

- [ ] **Canonical defaults sweep**: Apply SST guide checklist
  - [ ] Import both SST files and verify SettingsManager parity
  - [ ] Ensure MC defaults fall back to available monitor
  - [ ] Confirm auto geo detection for weather location
  - [ ] Add "no sources" popup with Just Make It Work/Ehhhh
- [ ] **Convert to modal workflow**: Preserve custom title bar/theme
- [ ] **Live updates integration**: SettingsManager signals for instant changes
- [ ] **Non-destructive refresh**: Monitor toggles without engine restart
- [ ] **Profile separation**: MC vs Screensaver isolation maintained

### 4.3 Volume Key Passthrough (MC Mode)
**Priority**: Medium (System integration)
**Dependencies**: Phase 4.1 complete
**Reference**: `audits/Minor Tasks.md #5`

- [ ] **Detect volume keys**: InputHandler recognition
- [ ] **MC mode passthrough**: Allow system volume control
- [ ] **Spotify volume isolation**: Prevent interference
- [ ] **Test media players**: Various apps and states
- [ ] **Document behavior**: Build-specific differences

---

## Phase 5: MC Build Enhancements (Week 11-12)

### 5.1 Window Layering Control
**Priority**: Medium (MC feature)
**Dependencies**: Phase 4 complete
**Reference**: `audits/Minor Tasks.md #7`

- [ ] **Context menu item**: "On Top / On Bottom" (MC only)
- [ ] **Window layering toggle**: Maintain Z-order hierarchy
- [ ] **Visibility detection**: 95% coverage threshold
- [ ] **Eco Mode implementation**: Pause transitions/visualizer when covered
- [ ] **Automatic recovery**: Restore when visibility regained
- [ ] **Logging integration**: Eco Mode activation/deactivation events
- [ ] **Multi-monitor testing**: Various configurations

### 5.2 Performance Optimization
**Priority**: Medium (Performance refinement)
**Dependencies**: Phase 2 complete
**Reference**: `Docs/PERFORMANCE_BASELINE.md`

- [ ] **Worker latency tuning**: Optimize queue sizes and backpressure
- [ ] **GL texture streaming**: PBO optimization if needed
- [ ] **Memory pressure reduction**: Object pooling enhancements
- [ ] **Perf baseline update**: Record final v2.0 metrics

---

## Phase 6: Integration & Polish (Week 13-14)

### 6.1 Comprehensive Testing
**Priority**: CRITICAL (Quality assurance)
**Dependencies**: All previous phases complete

- [ ] **Full integration tests**: End-to-end workflow validation
- [ ] **Performance regression tests**: Ensure dt_max < 100ms maintained
- [ ] **Multi-monitor scenarios**: All display configurations
- [ ] **Widget interaction tests**: All widget combinations
- [ ] **Settings migration tests**: Legacy config compatibility
- [ ] **MC vs normal build tests**: Feature parity validation

### 6.2 Documentation Updates
**Priority**: High (Documentation discipline)
**Dependencies**: All code changes complete

- [ ] **Update Spec.md**: Current architecture and features
- [ ] **Update Index.md**: Module map and ownership
- [ ] **Update Docs/TestSuite.md**: Complete test coverage
- [ ] **Update Docs/PERFORMANCE_BASELINE.md**: v2.0 baselines
- [ ] **Update Docs/10_WIDGET_GUIDELINES.md**: Any positioning changes
- [ ] **Archive phase docs**: Move completed phase docs to archive/

### 6.3 Release Preparation
**Priority**: High (Release readiness)
**Dependencies**: Phase 6.1-6.2 complete

- [ ] **Final backups**: `/bak` snapshots of all major modules
- [ ] **Version bump**: Update versioning.py for v2.0
- [ ] **Changelog preparation**: Summary of changes and improvements
- [ ] **Build testing**: Verify both normal and MC builds
- [ ] **Installation testing**: Fresh install and upgrade scenarios

---

## Testing Requirements Per Phase

### Unit Tests (Required for each phase)
- [ ] All new modules have comprehensive unit tests
- [ ] Existing tests still pass (no regressions)
- [ ] Coverage maintained or improved
- [ ] Performance tests for critical paths

### Integration Tests (Required for each phase)
- [ ] End-to-end workflow validation
- [ ] Multi-display scenarios tested
- [ ] Error handling and recovery verified
- [ ] Settings persistence and migration

### Performance Tests (Required for performance-sensitive changes)
- [ ] `SRPSS_PERF_METRICS=1` baselines recorded
- [ ] dt_max < 100ms maintained
- [ ] Memory usage within acceptable bounds
- [ ] No new blocking operations on UI thread

### Visual Regression Tests (Required for UI changes)
- [ ] Widget positioning verified
- [ ] Transition correctness validated
- [ ] Visualizer fidelity maintained
- [ ] Settings dialog behavior consistent

---

## Success Criteria

### Performance Targets
- [ ] Visualizer CPU usage reduced by 70%+ when not playing
- [ ] dt_max < 100ms maintained across all operations
- [ ] Memory usage stable (no leaks)
- [ ] Startup time < 3 seconds on typical hardware

### Feature Completeness
- [ ] All Minor Tasks implemented and tested
- [ ] AAMP2026 phases 1-4 complete
- [ ] MC build enhancements functional
- [ ] Settings modal workflow operational

### Quality Assurance
- [ ] 236+ unit tests passing
- [ ] Integration test coverage complete
- [ ] Documentation updated and accurate
- [ ] No known regressions from v1.x

### Architecture Goals
- [ ] Centralized managers used throughout
- [ ] Thread safety violations eliminated
- [ ] Process isolation foundations in place
- [ ] Widget and settings modularity achieved

---

## Risk Mitigation

### High-Risk Items
1. **Visualizer FFT worker migration**: Risk of visual fidelity loss
   - **Mitigation**: Comprehensive synthetic tests, exact math preservation
2. **GLStateManager rollout**: Risk of GL instability
   - **Mitigation**: Extensive testing, fallback paths maintained
3. **Settings modal conversion**: Risk of configuration loss
   - **Mitigation**: Migration shims, extensive backup testing

### Rollback Plans
- [ ] `/bak` snapshots for all major changes
- [ ] Feature flags for critical new functionality
- [ ] Automated rollback testing
- [ ] Documentation of rollback procedures

---

**Last Updated**: 2026-01-03
**Next Review**: After Phase 0 completion
**Owner**: Development Team
**Status**: Ready for execution
