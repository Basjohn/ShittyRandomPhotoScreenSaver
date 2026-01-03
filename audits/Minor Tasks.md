# Minor Tasks & Quick Wins (v2.0)

**Priority**: High-impact, low-complexity improvements that can be completed independently of the main AAMP2026 phases.

---

## High Priority Tasks (Immediate Impact)

### 1. Visualizer Animation Gating (CRITICAL)
**Problem**: Visualizer calculates FFT with dynamic flooring and adaptive sensitivity 24/7, wasting resources when Spotify isn't playing.

**Solution**: Gate the entire calculation system, not just animation updates.
- [x] Implement playback state detection in `_SpotifyBeatEngine`
- [x] Halt FFT processing when `state != PLAYING` (show 1-bar floor only)
- [x] Add sparse polling for Spotify state changes (reuse MediaWidget polling/events feeding `handle_media_update`; no standalone visualizer poller)
- [x] Preserve current dynamic floor pipeline exactly (see VISUALIZER_DEBUG.md)
- [x] Add synthetic test to verify calculation gating doesn't affect visual fidelity
- [x] Update performance metrics to track CPU savings

**Files**: `widgets/spotify_visualizer_widget.py`, `widgets/beat_engine.py`
**Test**: `tests/test_visualizer_playback_gating.py`

### 2. Widget Positioning System Audit
**Problem**: Potential stacking issues and middle/center positions not applying correctly (especially Reddit 2).

**Solution**: Comprehensive positioning system review.
- [ ] Audit `WidgetPositioner` for all 9 anchor positions
- [ ] Test Reddit 2 positioning specifically with middle/center anchors
- [ ] Verify collision detection and stacking logic for multi-widget scenarios
- [ ] Check `ui/widget_stack_predictor.py` alignment accuracy
- [ ] Add positioning regression tests for all widget combinations
- [ ] Document any edge cases or limitations found

**Files**: `rendering/widget_positioner.py`, `ui/widget_stack_predictor.py`
**Test**: `tests/test_widget_positioning_comprehensive.py`

### 3. Settings Dialog Window State Persistence
**Problem**: Settings dialog doesn't remember display, size, or positioning between sessions.

**Solution**: Implement window state persistence.
- [ ] Add window geometry (size, position, display) to SettingsManager
- [ ] Save geometry on dialog close, restore on open
- [ ] Handle multi-monitor scenarios (display may not be available on restore)
- [ ] Persist tab/subsection/scroll state (already works)
- [ ] Add fallback logic if saved display is unavailable
- [ ] Test with MC vs normal build profiles

**Files**: `ui/settings_dialog.py`, `core/settings/models.py`
**Test**: `tests/test_settings_dialog_persistence.py`

### 4. Double-Click Next Image Trigger
**Problem**: No way to advance images without using keyboard or context menu.

**Solution**: Add double-click handler to compositor.
- [ ] Implement double-click detection in `InputHandler`
- [ ] Filter out widget areas (don't trigger when clicking widgets)
- [ ] Trigger "next image" action on double-click
- [ ] Respect interaction gating (only work in Ctrl-held or hard-exit modes)
- [ ] Add visual feedback (optional cursor flash)
- [ ] Test with various widget configurations

**Files**: `rendering/input_handler.py`
**Test**: `tests/test_double_click_navigation.py`

### 5. Global Volume Key Passthrough (MC Mode)
**Problem**: Global volume keys are disabled in MC mode, preventing normal system volume control.

**Solution**: Allow volume keys to pass through to system while blocking Spotify volume interaction.
- [ ] Detect volume key presses in `InputHandler`
- [ ] In MC mode, allow system volume keys to pass through unchanged
- [ ] Ensure Spotify volume widget doesn't interfere with system volume
- [ ] Test with various media players and system states
- [ ] Document behavior difference between normal and MC builds

**Files**: `rendering/input_handler.py`, `core/media/spotify_volume.py`
**Test**: `tests/test_volume_key_passthrough.py`

### 6. Visualizer Intelligent Positioning for Top Anchors
**Problem**: Visualizer appears above media widget even when using top positions, should appear below.

**Solution**: Smart positioning relative to media widget.
- [ ] Detect when visualizer and media widget use top positions
- [ ] Calculate offset to place visualizer below media widget with same padding
- [ ] Maintain current behavior for non-top positions
- [ ] Handle edge cases (media disabled, different monitors, etc.)
- [ ] Update positioning logic in `WidgetPositioner`
- [ ] Test all top position combinations

**Files**: `rendering/widget_positioner.py`, `widgets/spotify_visualizer_widget.py`
**Test**: `tests/test_visualizer_smart_positioning.py`

---

## Long Term Tasks (Require More Planning)

### 7. MC Build "On Top/On Bottom" Mode
**Problem**: MC builds always stay on top; users want ability to place behind other apps.

**Solution**: Add window layering control with automatic Eco Mode.
- [ ] Add context menu item "On Top / On Bottom" (MC builds only)
- [ ] Implement window layering toggle (maintain Z-order hierarchy)
- [ ] Add visibility detection (95% coverage threshold)
- [ ] Implement Eco Mode: pause transitions and visualizer when covered
- [ ] Log Eco Mode activation/deactivation
- [ ] Ensure Eco Mode never triggers in On Top mode
- [ ] Add graceful recovery when visibility restored
- [ ] Test with various window configurations and multi-monitor setups

**Files**: `rendering/display_widget.py`, `widgets/context_menu.py`
**Test**: `tests/test_mc_layering_mode.py`

**Notes**: 
- Disable in normal builds (grey out or hide option)
- No GUI toggle for Eco Mode (fully automatic)
- Must preserve internal Z-order when switching layers
- Consider adding performance telemetry for Eco Mode effectiveness

---

## Implementation Notes

### Dependencies
- Tasks 2 & 6 should be done sequentially (positioning context)
- Task 1 should reference current visualizer logic in VISUALIZER_DEBUG.md
- All tasks should follow centralized manager policies (ThreadManager, ResourceManager, etc.)

### Testing Strategy
- Each task should include comprehensive unit tests
- Integration tests for multi-widget scenarios
- Performance tests for visualizer gating
- Regression tests to prevent future breakage

### Documentation Updates
- Update Spec.md for any new settings or behaviors
- Update Index.md for new modules or significant changes
- Add entries to Docs/TestSuite.md for new tests
- Consider updating Docs/10_WIDGET_GUIDELINES.md for positioning changes