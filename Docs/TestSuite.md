# Test Suite Documentation

**Purpose**: Canonical reference for all test modules, test cases, and testing procedures.  
**Last Updated**: Dec 11, 2025 - Architecture audit fixes and test robustness improvements  
**Test Count**: 360+ tests across 26+ modules  
**Pass Rate**: ~98% (known failures in timezone/settings dialog tests)  
**Recent**: 
- Fixed `test_perf_dt_max.py` to use median-based threshold (robust against transient system spikes)
- Fixed `test_settings.py` - all 9 tests now pass after SettingsManager fixes
- Fixed ClockWidget deferred callback crash with Shiboken.isValid guard
- Architecture audit completed 12 items (see `audits/ARCHITECTURE_AUDIT_2024_12.md`)

### Phase 6 Bug Fix Summary
**All 8 Critical Bugs Fixed:**
1. ✅ Bug #13: Lanczos memoryview handling
2. ✅ Bug #14: Transition cleanup race condition
3. ✅ Bug #15: Crossfade transition (complete rewrite)
4. ✅ Bug #16: Different image per display mode
5. ✅ Bug #17: Settings not saving (signal blocking)
6. ✅ Bug #18: Image quality on smaller displays (improved sharpening)
7. ✅ Bug #19: Fill/Fit mode aspect ratio corrections
8. ✅ Bug #20: Z key previous image navigation

**Current Failures (5):**
- `tests/test_settings_dialog.py::test_settings_dialog_creation`
- `tests/test_slide_transition.py::test_slide_cleanup`
- `tests/test_timezone_support.py::TestClockWidgetTimezone::test_clock_time_update_with_timezone`
- `tests/test_timezone_support.py::TestClockWidgetTimezone::test_clock_timezone_display_formats`
- `tests/test_transitions.py::test_crossfade_easing_curves`

**Notes:** Latest run (Nov 14) logged to `logs/tests/pytest_20251114_123452.log`. Failures primarily stem from test harness expecting cleaned Qt objects post-transition; guard now prevents crashes, but logic still needs follow-up adjustments for cleanup and timezone widgets.

---

## Overview

The screensaver test suite uses pytest with pytest-qt for Qt integration testing. All tests follow the logging-first policy with PowerShell execution patterns for Windows reliability.

### Test Execution Pattern

**Standard execution:**
```powershell
pytest -v tests/ --tb=short
```

**Single module:**
```powershell
pytest -v tests/test_events.py --tb=short
```

**With logging output (logging-first policy):**
```powershell
pytest -v tests/ --tb=short -s > test_output.log 2>&1
Get-Content test_output.log -Tail 50
```

---

## Test Modules

### 1. `tests/conftest.py` - Shared Fixtures

**Purpose**: Pytest configuration and shared fixtures for all tests.

**Fixtures:**

- **`qt_app`** (session scope)
  - Creates QApplication instance
  - Reused across all tests
  - Does not quit to avoid pytest issues

- **`settings_manager`** (function scope)
  - Creates test SettingsManager instance
  - Organization: "Test", Application: "ScreensaverTest"
  - Auto-cleanup: Clears settings after test

- **`thread_manager`** (function scope)
  - Creates ThreadManager instance
  - Auto-cleanup: Calls shutdown(wait=True)

- **`resource_manager`** (function scope)
  - Creates ResourceManager instance
  - Auto-cleanup: Calls shutdown()

- **`event_system`** (function scope)
  - Creates EventSystem instance
  - Auto-cleanup: Calls clear()

- **`temp_image`** (function scope)
  - Creates a 100x100 red test image
  - Returns: Path to temp PNG file
  - Auto-cleanup: pytest tmp_path fixture

---

### 2. `tests/test_events.py` - EventSystem Tests

**Module Purpose**: Verify publish-subscribe event system functionality.

**Test Count**: 6 tests  
**Status**: ✅ All passing

#### Tests:

**`test_event_system_initialization()`**
- Verifies EventSystem initializes correctly
- Checks subscription count starts at 0
- **Asserts**: `system is not None`, `get_subscription_count() == 0`

**`test_subscribe_and_publish()`**
- Tests basic subscribe and publish flow
- Verifies event data is passed correctly
- **Asserts**: Event received, `event_type == "test.event"`, `data == "test data"`

**`test_unsubscribe()`**
- Tests unsubscribing from events
- Verifies no events received after unsubscribe
- **Asserts**: Events stop after unsubscribe

**`test_priority_ordering()`**
- Tests that higher priority handlers execute first
- Subscribes with priorities: 10 (low), 90 (high), 50 (normal)
- **Asserts**: Call order is `["high", "normal", "low"]`

**`test_event_filter()`**
- Tests event filtering with filter_fn
- Filter accepts only events with `data == "accept"`
- **Asserts**: Only matching events trigger handler

**`test_event_history()`**
- Tests event history tracking
- Publishes 3 events and retrieves history
- **Asserts**: History contains all 3 events in order

---

### 3. `tests/test_resources.py` - ResourceManager Tests

**Module Purpose**: Verify resource lifecycle management and cleanup.

**Test Count**: 6 tests  
**Status**: ✅ All passing

#### Tests:

**`test_resource_manager_initialization()`**
- Verifies ResourceManager initializes
- Checks `_initialized` flag is True
- **Asserts**: Manager created, initialized

**`test_register_resource()`**
- Tests registering a resource with cleanup method
- Verifies cleanup is called on shutdown
- Uses TestResource class with `cleanup()` method
- **Asserts**: Resource registered, cleanup executed

**`test_unregister_resource()`**
- Tests explicit resource unregistration
- Verifies cleanup handler is called
- **Asserts**: `unregister()` returns True, cleanup executed, resource not retrievable

**`test_register_temp_file(tmp_path)`**
- Tests temporary file registration
- Creates temp file, registers for cleanup
- **Asserts**: File exists before shutdown, deleted after shutdown

**`test_get_all_resources()`**
- Tests retrieving all registered resources
- Registers 2 resources
- **Asserts**: `get_all_resources()` returns at least 2 items

**`test_get_stats()`**
- Tests resource statistics
- Checks stats structure
- **Asserts**: Stats contain `total_resources`, `by_type`, `by_group`

---

### 4. `tests/test_settings.py` - SettingsManager Tests

**Module Purpose**: Verify settings persistence and change notifications.

**Test Count**: 6 tests  
**Status**: ✅ All passing  
**Requires**: qt_app fixture

#### Tests:

**`test_settings_manager_initialization(qt_app)`**
- Verifies SettingsManager initializes
- Uses QSettings backend
- **Asserts**: Manager created successfully

**`test_get_set_setting(qt_app)`**
- Tests basic get/set operations
- Sets "test.key" to "test value"
- **Asserts**: Retrieved value matches set value

**`test_default_values(qt_app)`**
- Tests default values are set on initialization
- Checks for `sources.mode`, `display.mode`, `transitions.type`
- **Asserts**: Default keys exist

**`test_on_changed_handler(qt_app)`**
- Tests change notification callbacks
- Registers handler, changes value twice
- **Asserts**: Handler called at least once

**`test_reset_to_defaults(qt_app)`**
- Tests resetting all settings
- Changes a value, then resets
- **Asserts**: Value returns to default ("folders")

**`test_get_all_keys(qt_app)`**
- Tests retrieving all setting keys
- **Asserts**: Keys list is populated, contains expected keys

---

### 5. `tests/test_threading.py` - ThreadManager Tests

**Module Purpose**: Verify thread pool management and task execution.

**Test Count**: 5 tests  
**Status**: ✅ All passing  
**Requires**: qt_app fixture

#### Tests:

**`test_thread_manager_initialization(qt_app)`**
- Verifies ThreadManager initializes both pools
- Checks IO and COMPUTE executors exist
- **Asserts**: Manager created, both pools initialized

**`test_submit_io_task(qt_app)`**
- Tests submitting task to IO pool
- Uses callback pattern for result
- **Asserts**: Task executes, callback receives result

**`test_submit_compute_task(qt_app)`**
- Tests submitting task to COMPUTE pool
- Uses callback pattern for async result
- Computes 5 + 3 = 8
- **Asserts**: Task executes, result is correct

**`test_get_pool_stats(qt_app)`**
- Tests pool statistics retrieval
- Checks stats structure
- **Asserts**: Stats contain 'io' and 'compute' with submitted/completed/failed

**`test_thread_manager_shutdown(qt_app)`**
- Tests graceful shutdown
- Submits task, then shuts down
- **Asserts**: Cannot submit after shutdown (raises RuntimeError)

---

## Test Coverage by Module

| Module | Tests | Status | Coverage |
|--------|-------|--------|----------|
| EventSystem | 6 | ✅ Pass | Subscribe, publish, unsubscribe, priority, filtering, history |
| ResourceManager | 6 | ✅ Pass | Register, unregister, temp files, stats, Qt widgets |
| SettingsManager | 6 | ✅ Pass | Get/set, defaults, persistence, change handlers |
| ThreadManager | 5 | ✅ Pass | Init, IO tasks, compute tasks, stats, shutdown |
| **Total** | **23** | **✅ 100%** | **Core framework complete** |

---

## Testing Strategy

### Unit Tests (Current)
- **EventSystem**: All core functionality
- **ResourceManager**: Lifecycle and cleanup
- **SettingsManager**: Configuration persistence
- **ThreadManager**: Thread pool operations

### Integration Tests (Planned - Day 5+)
- Complete startup → slideshow → exit flow
- Multi-monitor scenarios
- Settings persistence across restarts
- Monitor hotplug events

### Performance Tests (Planned - Day 5+)
- 24-hour stability test
- Memory profiling (target: <500MB)
- CPU profiling (transitions at 60 FPS)
- Image loading performance

### Manual Tests (Planned - Day 6)
- Preview mode (/p argument)
- Visual verification of all transitions
- Clock and weather widget display
- Configuration UI workflows

#### Scenario: Transition Cycling + Manual Overrides (BlockFlip lock-in)

**Goal**: Verify that cycling transitions with `C` and then applying manual overrides in the settings dialog does **not** leave the engine stuck on Block Puzzle Flip (or any prior random choice), and that settings/telemetry stay in sync.

**Prerequisites**:
- Run in debug mode for full logging:
  - `python main.py --debug`
- Ensure at least two displays are active if available (to exercise multi-monitor paths).

**Steps**:
1. Start the screensaver (`RUN` mode, no `/c` or `/p` arguments).
2. While the slideshow is running, press `C` several times:
   - Observe log lines from `rendering.display` / `engine.screensaver` such as:
     - `C key pressed - cycle transition requested`
     - `Transition cycled to: <Type>` (e.g. `Block Puzzle Flip`, `Blinds`, `Crossfade`, `Slide`).
   - Confirm that the visible transition type matches the logged `Transition cycled to:` value on subsequent image changes.
3. When `Block Puzzle Flip` is active, note the current type from the log and then **cycle away** using `C` until a different transition is selected (e.g. `Crossfade` or `Slide`).
4. Open the settings dialog with `S` while the screensaver is still running:
   - On the **Transitions** tab, choose a specific non-random transition type (e.g. **Diffuse**), and ensure that any "Random" toggles are disabled.
   - Apply/OK the dialog to return to the slideshow.
5. Observe the next several transitions and the log output:
   - `SettingsManager` should log a single `Setting changed: transitions: {...} -> {...}` with the new `type` and no lingering `transitions.random_choice` / `transitions.last_random_choice` keys.
   - `engine.screensaver` should log `Transition type updated in settings - will apply on next image change` followed by `Transition cycled to: <NewType>` if cycled again.
   - Visually confirm that after moving away from Block Puzzle Flip, subsequent transitions actually use the new type and do **not** revert to Block Puzzle Flip unless explicitly selected again.
6. Optional: repeat steps 2–5 with `display.hw_accel` toggled (OpenGL vs software backend) to ensure behaviour is consistent across backends.

**Pass Criteria**:
- No evidence in logs or visuals of being "locked" into Block Puzzle Flip after cycling away or applying manual overrides.
- `transitions.random_choice` and `transitions.last_random_choice` are cleared whenever a specific type is chosen or cycled to, as reflected in `SettingsManager` DEBUG logs.
- `Transition cycled to:` messages and on-screen transitions remain in sync across multiple cycles and settings changes.

#### Scenario: Multi-Monitor Widgets & UI (Clocks & Weather)

**Goal**: Verify that clock and weather widgets respect per-monitor configuration (enable/disable and target monitor), and that no widgets appear or fetch data on monitors where they are disabled.

**Prerequisites**:
- Run in debug mode: `python main.py --debug`.
- Ideally have at least two physical displays connected.

**Steps**:
1. Open the settings dialog (`S`) from a running slideshow.
2. On the **Widgets** tab, configure:
   - **Clock 1**: `enabled = True`, `monitor = 1`, position any corner.
   - **Clock 2**: `enabled = True`, `monitor = ALL`, position a different corner.
   - **Weather**: `enabled = True`, `monitor = 1`, choose a known location (e.g. `Johannesburg`).
3. Apply/OK and observe each display:
   - On monitor 1: both Clock 1 and Clock 2 should appear, plus the Weather widget.
   - On monitor 2: only Clock 2 should appear; no Weather widget should be visible.
4. In `logs/screensaver.log`, verify startup lines from `rendering.display` and `widgets.weather_widget` / `widgets.clock_widget` match expectations, e.g.:
   - `✅ clock widget started: ...` / `✅ clock2 widget started: ...` on the correct screens.
   - `Weather widget started: <location>, <position>` **only** for the configured monitor.
   - `weather widget disabled in settings` DEBUG lines for monitors where weather is gated off.
5. Change the Widgets tab configuration so that Weather targets `monitor = ALL` and Clock 2 targets `monitor = 2`, then apply again:
   - Confirm visually that Weather appears on both monitors and Clock 2 only on monitor 2.
   - Confirm corresponding log messages reflect the new layout with no stray widget creations on disabled screens.

**Pass Criteria**:
- Widget visibility (clocks, weather) always matches the per-monitor settings for `enabled` + `monitor` in the Widgets tab.
- Logs show weather and clock creation only on the monitors they are configured for, and `... widget disabled in settings` entries for all others.
- No unexpected weather network activity is logged for displays where the Weather widget is disabled.

#### Scenario: Spotify Beat Visualizer (Spotify-only Gating)

**Goal**: Verify that the Spotify Beat Visualizer only animates when Spotify is actively playing, inherits the Spotify/media card styling, and respects per-monitor settings.

**Prerequisites**:
- Run in debug mode: `python main.py --debug`.
- Spotify installed on the system and capable of playing local/streamed audio.

**Steps**:
1. Open the settings dialog (`S`) from a running slideshow and go to the **Widgets → Media** subtab.
2. Enable **Spotify Widget** and **Spotify Beat Visualizer**.
   - Set both `monitor` selectors to `ALL` for a simple first pass.
   - Leave the media widget position at its default (e.g. `Bottom Left`).
3. Apply/OK and return to the slideshow.
4. With Spotify **stopped or paused**, observe the media widget and visualizer:
   - Media card should either be hidden or showing the last-known track state (depending on GSMTC availability).
   - The Beat Visualizer should either remain hidden or show only near-zero-height bars (no visible motion).
5. Start Spotify playback of any track and wait a few seconds:
   - Confirm the media widget updates to the current track.
   - Confirm the Beat Visualizer appears a short distance **above** the Spotify card (about 20px gap), matching its width.
   - Bars should animate in sync with the general energy of the audio (more motion on louder/denser sections).
6. Pause or stop Spotify playback again:
   - Bars should smoothly decay back to an idle state (heights easing towards zero) and remain idle even if other apps play audio.
7. Optional: change **Bar Count**, **Bar Fill Color** and **Bar Border Color/Opacity** in the Widgets tab and re-run steps 4–6:
   - Confirm the new styling applies after settings are saved and the screensaver restarts.

**Pass Criteria**:
- Beat Visualizer only shows meaningful bar motion when Spotify is reported as `playing` by the centralized media controller; pausing/stopping Spotify causes bars to decay to zero.
- Visualizer card background, border, and opacity remain visually locked to the Spotify/media widget card.
- Per-monitor settings (`monitor = 'ALL'|1|2|3`) gate creation on each display: when the visualizer is disabled or targeted away from a monitor, no beat widget is constructed there.

#### Perf Scenario: Prefetch Queue vs Transition Skips

**Goal**: Use existing telemetry to confirm that the prefetch queue and the single-skip policy in `DisplayWidget.set_image` work together without harming pacing, and that `transition_skip_count` remains bounded for normal runs.

**Telemetry Reference**:
- `DisplayWidget.set_image(...)`:
  - When a transition is still running, increments `self._transition_skip_count` and logs:
    - `Transition in progress - skipping image request (skip_count=...)`
- `DisplayWidget.get_screen_info()`:
  - Includes `transition_skip_count` in the per-display info dict.
- `ScreensaverEngine.cleanup()`:
  - Logs a concise engine summary at shutdown:
    - `[PERF] Engine summary: queue={...}, displays=[{...}]`
  - `queue` comes from `ImageQueue.get_stats()` (fields like `total_images`, `remaining`, `current_index`, `wrap_count`).
  - `displays` is a list of `DisplayWidget.get_screen_info()` dicts, including `transition_skip_count` per display.

**Prerequisites**:
- Run with debug logging enabled, e.g.:
  - `python main.py --debug`
- Configure a realistic rotation interval in the **Display** tab (e.g. 10–30 seconds per image).
- Optional: enable a mix of heavier transitions (Diffuse, Block Puzzle Flip) and lighter ones (Crossfade, Slide) to exercise both GPU and software paths.

**Steps**:
1. Start the screensaver in normal run mode and let it run uninterrupted for at least a few dozen image changes (5–10 minutes on a typical interval).
2. Avoid excessive manual skipping (`Z`/`X`) to keep the workload representative of a normal unattended slideshow.
3. Exit the screensaver with `Esc`.
4. Open the most recent log file (e.g. `logs/screensaver.log` or the latest rotated file) and search for:
   - `[PERF] Engine summary:`
5. Inspect the `queue={...}` portion:
   - Note `total_images`, `remaining`, `current_index`, and `wrap_count` as a rough measure of how many images were cycled.
6. Inspect the `displays=[{...}]` portion:
   - For each display dict, note `transition_skip_count` along with basic screen info.
7. Optionally, also grep within the same log for:
   - `Transition in progress - skipping image request (skip_count=`
   - Confirm that skip messages appear occasionally rather than continuously.

**Interpretation / Pass Criteria**:
- For a typical run (tens to hundreds of images shown):
  - `transition_skip_count` per display should be **non-zero but bounded**—skips should be rare events, not the dominant path.
  - `transition_skip_count` should be noticeably smaller than `current_index` from `queue` stats for the same session; if they are of the same order of magnitude, prefetch + rotation timing may be too aggressive.
- Visual pacing during the run should feel even:
  - No long pauses where multiple consecutive images are silently skipped because transitions never finish in time.
  - No obvious “stutter” caused by repeated skip retries on heavy transitions.
- If skip counts appear excessively high relative to images shown, record the log and configuration and adjust:
  - Rotation interval (slightly longer gaps between images), and/or
  - Mix of very heavy transitions, then re-run this scenario and compare `transition_skip_count` and `[PERF] Engine summary` output.

#### Scenario: Deferred Reddit Helper (Scheduler Path)
**Goal**: Validate the ProgramData queue helper on Winlogon builds using the scheduler-first flow shared by both SCR and standard frozen builds.

1. Build either `scripts\build_nuitka_scr.ps1` or the standard `scripts\build_nuitka.ps1` so the frozen helper payload is embedded.
2. Run the diagnostic harness:  
   `powershell -ExecutionPolicy Bypass -File .\scripts\diagnose_reddit_helper.ps1`
   - Ensures the helper payload is installed under `%ProgramData%\SRPSS\helper`, runs the helper in `--register-only` mode to refresh the `SRPSS\RedditHelper` scheduled task, triggers `trigger_helper_run()`, and tails `%ProgramData%\SRPSS\logs\scr_helper.log` plus `reddit_helper.log`.
3. Confirm the console output and `scr_helper.log` include `Helper triggered via scheduled task`. If privileges are missing, the log will explicitly list the failing privilege (e.g. `SeTcbPrivilege`).
4. Confirm `reddit_helper.log` shows `Scheduled task ensured (SRPSS\RedditHelper)` and (if queue entries exist) `Helper started` / `Launch succeeded ...`.
5. Queue a dummy URL for validation:  
   `python -c "from core.windows import reddit_helper_bridge as b; b.enqueue_url('https://example.com/helper-smoke')"`
6. Re-run the diagnostic script; the helper log should show the queued URL being launched and the JSON entry removed from `%ProgramData%\SRPSS\url_queue`.

**Pass Criteria**:
- Scheduled task registration succeeds (`Scheduled task ensured`) and `trigger_helper_run` reports `True`.
- `%ProgramData%\SRPSS\logs\scr_helper.log` contains `Helper triggered via scheduled task` for the most recent run.
- Queued URLs are drained (no lingering `.json` files) after the helper runs, and the browser opens the queued link on the interactive desktop.

---

## PowerShell Test Patterns

### Standard Pattern
```powershell
pytest -v tests/test_module.py --tb=short
```

### With Logging (Logging-First Policy)
```powershell
# Direct output (works for most tests)
pytest -v tests/ --tb=short

# If terminal output is unreliable:
pytest -v tests/ --tb=short -s > test_output.log 2>&1
Get-Content test_output.log -Tail 50
```

### Individual Test
```powershell
pytest -v tests/test_events.py::test_subscribe_and_publish --tb=short
```

### Python Helper Script (`scripts/run_tests.py`)

To avoid PowerShell syntax issues, use the helper script which wraps the
logging-first workflow and writes output to timestamped log files:

```powershell
python scripts/run_tests.py --suite core
```

Key options:
- `--suite {all,core,transitions,flicker}` – predefined groups (default: `all`).
- `--test tests/test_file.py::test_name` – run an explicit pytest node.
- `--pytest-args ...` – forward extra arguments after the suite selection.
- `--dry-run` – print the pytest command without executing.
- Logs: `logs/tests/pytest_YYYYMMDD_HHMMSS.log` (rotated, default keep=10).

After execution the script prints the last 20 log lines and the full log path.
On PowerShell follow up with `Get-Content <log> -Tail 100` if more context is
needed.

### With Coverage (Future)

```powershell
pytest --cov=core --cov=engine --cov=sources tests/
```

---

## Common Test Issues and Solutions

### Issue: QApplication Already Exists
**Solution**: Use session-scoped `qt_app` fixture from conftest.py

### Issue: Tests Hang
**Solution**: Ensure all background threads are shut down in fixtures

### Issue: Temp File Not Deleted
**Solution**: ResourceManager now uses strong references for temp files

### Issue: Race Condition in Threading Tests
**Solution**: Use callback pattern instead of `get_task_result()` for async operations

### Issue: Settings Persist Between Tests
**Solution**: Each test gets fresh SettingsManager with unique org/app name, cleared after test

---

## Adding New Tests

### 1. Create Test File
```python
# tests/test_newmodule.py
import pytest
from module import NewModule

def test_initialization():
    """Test NewModule initializes correctly."""
    module = NewModule()
    assert module is not None
```

### 2. Use Fixtures
```python
def test_with_qt(qt_app):
    """Test that needs Qt application."""
    # qt_app is available
    pass

def test_with_settings(settings_manager):
    """Test that needs settings."""
    # settings_manager is available and will be cleaned up
    pass
```

### 3. Follow Naming Convention
- Test files: `test_*.py`
- Test functions: `test_*`
- Use descriptive names: `test_subscribe_and_publish` not `test_1`

### 4. Update This Document
- Add test count to module section
- Document what the test verifies
- Update total count in overview
- Add to coverage table

---

## CI/CD Integration (Future)

### GitHub Actions Pattern
```yaml
- name: Run tests
  run: |
    pytest -v tests/ --tb=short --junitxml=test-results.xml
```

### Pre-commit Hook
```bash
#!/bin/bash
pytest tests/ --tb=short || exit 1
```

---

## Test Maintenance

### Before Each Implementation Session
1. Run full test suite: `pytest -v tests/`
2. Verify all tests pass
3. Check test output logs if using logging-first policy

### After Adding New Module
1. Create corresponding `test_*.py` file
2. Add minimum 3 tests (init, basic operation, error case)
3. Update TestSuite.md with new tests
4. Run full suite to ensure no regressions

### After Refactoring
1. Run affected tests first
2. Run full suite
3. Update test documentation if behavior changed

---

## Test Statistics

---

## Integration Tests (NEW - Nov 6, 2025)

### 19. `tests/test_transition_integration.py` - Transition System Integration

**Module Purpose**: End-to-end testing of transition system in DisplayWidget.

**Test Count**: 10 tests  
**Status**: ✅ All passing

**Critical Tests:**
- `test_crossfade_transition_runs()` - Crossfade actually executes
- `test_slide_transition_runs()` - Slide transition executes
- `test_diffuse_transition_runs()` - Diffuse transition executes
- `test_block_puzzle_flip_transition_runs()` - Block puzzle flip executes
- `test_wipe_transition_runs()` - Wipe transition executes
- `test_transition_cleanup_on_stop()` - Transitions clean up properly
- `test_transition_settings_respected()` - Settings properly applied
- `test_transition_fallback_on_error()` - Graceful fallback on errors
- `test_random_slide_direction()` - Random direction selection works

**Purpose**: Validate Bug #11 and #12 fixes don't reoccur.

---

### 20. `tests/test_clock_integration_regression.py` - Clock Widget Regression

**Module Purpose**: Regression tests for 9 clock bugs fixed in Phase 1.

**Test Count**: 13 tests  
**Status**: ✅ All passing

**Bug Regression Tests:**
- `test_bug1_clock_widget_created()` - Clock created when enabled
- `test_bug2_set_text_color_method_exists()` - set_text_color() exists
- `test_bug3_color_array_to_qcolor_conversion()` - Color array → QColor
- `test_bug4_z_order_clock_on_top()` - Clock Z-order correct
- `test_bug5_settings_retrieval_no_crash()` - Settings load without crash
- `test_bug6_boolean_type_conversion()` - Boolean vs string handling
- `test_bug7_position_string_to_enum()` - Position string conversion
- `test_bug8_format_string_to_enum()` - Format string conversion
- `test_bug9_missing_raise_call()` - raise_() called for Z-order

**Additional Tests:**
- `test_clock_widget_visibility_after_setup()`
- `test_clock_widget_size_and_position()`
- `test_clock_settings_complete_integration()`

**Purpose**: Ensure all 9 clock bugs from Phase 1 don't reoccur.

---

### 21. `tests/test_lanczos_scaling.py` - Lanczos Image Scaling

**Module Purpose**: Integration tests for PIL/Pillow Lanczos scaling.

**Test Count**: 16 tests  
**Status**: ✅ All passing (some skip if PIL unavailable)

**Critical Tests:**
- `test_lanczos_downscaling()` - Correct dimensions after downscale
- `test_bug10_no_image_tripling()` - Regression test for Bug #10
- `test_lanczos_with_alpha_channel()` - RGBA images handled
- `test_lanczos_with_sharpening()` - Sharpening filter works
- `test_fallback_when_lanczos_disabled()` - Qt fallback works
- `test_fallback_when_pil_unavailable()` - Graceful PIL unavailable handling
- `test_lanczos_fill_mode()` - FILL mode correct
- `test_lanczos_fit_mode()` - FIT mode correct
- `test_lanczos_shrink_mode_downscale()` - SHRINK downscale correct
- `test_lanczos_shrink_mode_no_upscale()` - SHRINK no upscale
- `test_lanczos_aspect_ratio_preserved()` - Aspect ratio maintained
- `test_aggressive_downscale()` - 4x downscale handled

**Purpose**: Validate Bug #10 fix and Lanczos quality improvements.

---

### 22. `tests/test_display_tab.py` - Display Tab UI

**Module Purpose**: Integration tests for new Display tab (Phase 1).

**Test Count**: 14 tests  
**Status**: ✅ All passing

**Tests:**
- `test_display_tab_creation()` - Tab creates without errors
- `test_display_tab_loads_settings()` - Settings load correctly
- `test_display_tab_saves_monitor_selection()` - Monitor setting persists
- `test_display_tab_saves_display_mode()` - Display mode persists
- `test_display_tab_saves_timing()` - Rotation interval persists
- `test_display_tab_boolean_conversion()` - Boolean/string conversion
- `test_display_tab_lanczos_setting()` - Lanczos setting works
- `test_display_tab_sharpen_setting()` - Sharpen setting works
- `test_display_tab_same_image_monitors()` - Multi-monitor setting
- `test_display_tab_all_settings_persist()` - Full roundtrip test
- `test_display_tab_default_values()` - Correct defaults
- `test_display_tab_invalid_mode_handling()` - Graceful error handling
- `test_display_tab_invalid_interval_handling()` - Invalid values handled

**Purpose**: Ensure Display tab settings work correctly.

---

### 23. `tests/test_media_widget.py` - Spotify Media Widget & Media Controller

**Module Purpose**: Validate the centralized media controller abstraction and the Spotify-specific overlay widget, including visibility semantics, artwork handling, and interaction routing.

**Test Count**: ~12 tests  
**Status**: ✅ All passing (Qt + GSMTC integration mocked where needed)

**Critical Tests:**
- `test_noop_media_controller_safe_calls` – NoOp controller is safe to call and always returns `None`.
- `test_create_media_controller_falls_back_to_noop` – Factory falls back to NoOp when the Windows controller is unavailable.
- `test_windows_media_controller_selects_spotify_session` – Selector prefers Spotify GSMTC sessions by `source_app_user_model_id`.
- `test_windows_media_controller_returns_none_when_no_spotify` – Non‑Spotify sessions are treated as "no media".
- `test_media_widget_placeholder_when_no_media` – Widget stays hidden when no media is available.
- `test_media_widget_displays_metadata` – Metadata (title/artist/album) and playback state text render correctly.
- `test_media_widget_hides_again_when_media_disappears` – Widget hides again once media stops.
- `test_media_widget_decodes_artwork_and_adjusts_margins` – Artwork bytes decode into a pixmap and margins adjust to make room.
- `test_media_widget_starts_fade_in_when_artwork_appears` – First artwork appearance triggers a short fade‑in animation.
- `test_media_widget_transport_delegates_to_controller` – Transport methods (play/pause/next/previous) delegate to the underlying controller.
- `test_display_widget_ctrl_click_routes_to_media_widget` – Ctrl‑held clicks over the widget invoke play/pause instead of exiting.
- `test_display_widget_hard_exit_click_routes_to_media_widget` – Hard‑exit mode allows transport interaction without exit.

**Purpose**: Lock in Spotify‑only session selection, hide‑on‑no‑media behaviour, artwork handling, and Ctrl/hard‑exit interaction gating for the Spotify MediaWidget.

---

### 24. `tests/test_spotify_visualizer_widget.py` – Spotify Beat Visualiser

**Module Purpose**: Guard the architecture and basic performance characteristics of the Spotify Beat Visualiser after the GL compositor move and beat‑pipeline refactor, including the shared beat engine and adaptive FPS limiting.

**Test Count**: 5 tests  
**Status**: ✅ All passing

**Critical Tests:**
- `test_spotify_visualizer_tick_uses_compute_bars` – Confirms `SpotifyVisualizerWidget._on_tick` consumes `_AudioFrame` objects from the shared `TripleBuffer` and delegates bar computation to `SpotifyVisualizerAudioWorker.compute_bars_from_samples`, enforcing that FFT/band mapping lives in the measured UI tick path rather than the high‑frequency audio callback (or its shared compute equivalent).
- `test_spotify_visualizer_compute_bars_reasonable_runtime` – Coarse runtime regression guard for `compute_bars_from_samples`: repeatedly computes bars for random audio samples and asserts the batch finishes within a generous time bound, catching accidental GIL‑heavy work migrating into per‑sample Python loops.
- `test_spotify_visualizer_widgets_share_audio_engine` – Verifies that multiple `SpotifyVisualizerWidget` instances share a single underlying `SpotifyVisualizerAudioWorker` and `TripleBuffer`, ensuring there is only one audio capture/FFT pipeline per process.
- `test_spotify_visualizer_tick_respects_fps_cap` – Verifies that the visualiser’s tick path honours the configured FPS cap and does not repaint more often than allowed when called rapidly, so the widget cannot flood the UI event loop during transitions.
- `test_spotify_visualizer_emits_perf_metrics` – Asserts that the visualiser emits `[PERF] [SPOTIFY_VIS] Tick metrics` via `_log_perf_snapshot` when PERF metrics are enabled, so its effective FPS and dt jitter are always recorded alongside `[PERF] [ANIM]` and `[PERF] [GL COMPOSITOR]` in the dedicated PERF log.

**Purpose**: Provide a focused regression harness for the Spotify beat pipeline (including the shared beat engine and adaptive FPS cap) so future refactors cannot silently reintroduce the "Spotify playing → transitions collapse to ~20–40 FPS" choke.

---

### 25. `tests/test_overlay_timers.py` – Overlay Timer Helpers

**Module Purpose**: Validate centralised overlay timer creation for widgets using `widgets.overlay_timers`.

**Test Count**: 2 tests  
**Status**: ✅ All passing

**Critical Tests:**
- `test_overlay_timer_uses_thread_manager_when_available` – Ensures `create_overlay_timer` calls `ThreadManager.schedule_recurring(...)` when a `_thread_manager` is present and that `OverlayTimerHandle` correctly reflects active/stop state.
- `test_overlay_timer_falls_back_to_qtimer_without_thread_manager` – Ensures a widget-local `QTimer` is used when no `ThreadManager` is available and that the timer fires at least once before being stopped via the handle.

**Purpose**: Lock in the centralised timer architecture for overlay widgets so future refactors cannot silently reintroduce orphan QTimers that bypass ThreadManager/ResourceManager tracking.

---

### 26. `tests/test_logging_console_encoding.py` – Console Encoding Robustness

**Module Purpose**: Guard against `UnicodeEncodeError` from console handlers on narrow encodings while preserving rich Unicode output in file logs.

**Test Count**: 2 tests  
**Status**: ✅ All passing

**Critical Tests:**
- `test_console_handler_replaces_unencodable_characters_narrow_encodings` – Simulates cp1252/latin-1 console streams and asserts that `SuppressingStreamHandler` degrades arrows/emoji into replacement characters instead of raising when the console encoding cannot represent them.
- `test_console_handler_preserves_unicode_on_utf8_console` – Asserts that UTF-8 console streams still display the full Unicode message with no replacement, keeping debug readability high on modern terminals.

**Purpose**: Provide a regression harness for the console encoding roadmap item so future logging changes cannot reintroduce cp1252 `UnicodeEncodeError` issues during interactive debug sessions. Combined with the dedicated rotating `screensaver_perf.log` (which captures all `[PERF]` lines via a PERF-only filter), this keeps both console and file-based diagnostics robust while making performance metrics easy to inspect across rotated logs.

---

### 27. `tests/test_reddit_exit_logic.py` - Reddit Exit Logic Regression Tests

**Purpose**: Verify the A/B/C Reddit exit policy (primary covered vs MC mode), ensure InputHandler exposes deferred URLs, and confirm DisplayManager cleanup opens stored links.

**Test Classes:**

- **`TestRedditExitLogic`** (3 tests)
  - `test_primary_covered_detection_same_screen` – Validates case A detection when the active display is the primary.
  - `test_primary_covered_detection_different_screen` – Validates coordinator lookup path when another display covers the primary.
  - `test_mc_mode_detection` – Validates MC mode detection when no widget covers the primary screen.

- **`TestRedditClickRouting`** (2 tests)
  - `test_reddit_click_returns_handled_tuple` – Ensures InputHandler routes Reddit clicks and flags them as handled in Ctrl/hard-exit modes.
  - `test_reddit_click_returns_deferred_url` – Ensures the tuple includes the resolved URL for deferred handling paths.

- **`TestCacheInvalidationMitigation`** (1 test)
  - `test_primary_covered_path_exits_before_foreground` – Confirms ordering (exit signal precedes delayed foregrounding) to avoid the Phase E corruption.

- **`TestDisplayManagerDeferredUrls`** (1 test)
  - `test_cleanup_opens_pending_reddit_urls` – Verifies DisplayManager collects `_pending_reddit_url` entries and opens them after windows close.
- **`TestRedditHelperLauncher`** (2 tests)
  - `test_flush_prefers_helper_when_available` – Forces the Windows helper shim to claim availability and confirms `flush_deferred_reddit_urls` routes URLs through the helper without touching `QDesktopServices`.
  - `test_flush_falls_back_when_helper_rejects` – Simulates the helper declining launch so the code path falls back to `QDesktopServices`, ensuring frost-proof behavior even if the helper cannot spawn.

**Status**: ✅ All passing
**Critical Tests**:
- `test_reddit_click_returns_deferred_url` – Locks in the deferred URL signal path feeding DisplayWidget.
- `test_cleanup_opens_pending_reddit_urls` – Ensures Firefox/DDE-safe behavior when running as a native screensaver.
- `test_flush_prefers_helper_when_available` – Confirms native Winlogon builds reach the helper launcher so URLs open on the user desktop instead of failing inside Winlogon.

---

### 28. `tests/test_dimming_and_interaction_fixes.py` - Dimming & Interaction Regression Tests

**Purpose**: Regression tests for dimming overlay, halo interaction, deferred Reddit URL, media widget click detection, settings dot notation, and Z-order management fixes.

**Test Classes:**

- **`TestDimmingOverlayAttributes`** (3 tests)
  - `test_dimming_overlay_uses_translucent_background` – Verifies legacy/fallback `DimmingOverlay` widget uses `WA_TranslucentBackground` for correct alpha compositing when used
  - `test_dimming_overlay_opacity_calculation` – Verifies opacity percentage (0-100) is correctly converted to alpha (0-255)
  - `test_dimming_overlay_opacity_clamping` – Verifies opacity is clamped to valid 0-100 range

- **`TestCtrlHaloAttributes`** (1 test)
  - `test_halo_code_uses_styled_background` – Verifies ctrl cursor halo uses `WA_StyledBackground` (not `WA_TranslucentBackground`) to avoid punching through dimming overlay

- **`TestDeferredRedditUrl`** (2 tests)
  - `test_open_pending_reddit_url_method_exists` – Verifies `_open_pending_reddit_url` method exists on DisplayWidget
  - `test_pending_reddit_url_attribute_exists` – Verifies `_pending_reddit_url` attribute is initialized in DisplayWidget

- **`TestMediaWidgetClickDetection`** (2 tests)
  - `test_click_detection_checks_y_coordinate` – Verifies media widget click detection checks Y coordinate for controls row
  - `test_controls_row_height_is_reasonable` – Verifies controls row height constant is 60px

- **`TestCrumbleShaderPerformance`** (1 test)
  - `test_crumble_search_range_is_reduced` – Verifies Crumble shader search range is reduced for performance (not -10 to +4)

- **`TestSettingsDotNotation`** (3 tests)
  - `test_dimming_settings_use_dot_notation` – Verifies dimming settings are read with dot notation (not nested dict access)
  - `test_pixel_shift_settings_use_dot_notation` – Verifies pixel shift settings are read with dot notation
  - `test_context_menu_dimming_uses_dot_notation` – Verifies context menu reads dimming state with dot notation

- **`TestDimmingOverlayZOrder`** (2 tests)
  - `test_raise_overlay_includes_dimming` – Verifies `raise_overlay` includes dimming overlay and ctrl halo in Z-order
  - `test_raise_overlay_zorder_documented` – Verifies Z-order is documented in `raise_overlay`

- **`TestDeferredRedditUrlAllExitPaths`** (3 tests)
  - `test_key_press_exit_opens_reddit_url` – Verifies keyPressEvent calls `_open_pending_reddit_url` before exit
  - `test_mouse_click_exit_opens_reddit_url` – Verifies mousePressEvent calls `_open_pending_reddit_url` before exit
  - `test_mouse_move_exit_opens_reddit_url` – Verifies mouseMoveEvent calls `_open_pending_reddit_url` before exit

**Critical Tests:**
- `test_dimming_overlay_uses_translucent_background` – Prevents regression where the legacy/fallback dimming overlay appears invisible due to wrong widget attributes
- `test_halo_code_uses_styled_background` – Prevents regression where halo punches holes through dimming overlay
- `test_crumble_search_range_is_reduced` – Prevents regression where Crumble transition causes severe performance degradation
- `test_dimming_settings_use_dot_notation` – Prevents regression where dimming opacity is always 30% regardless of settings
- `test_raise_overlay_includes_dimming` – Prevents regression where dimming disappears around widget edges after transitions

---

### 28. `tests/test_particle_transition.py` - Particle Transition Tests

**Module Purpose**: Verify particle transition shader program, state, and settings integration.

**Test Count**: 14 tests  
**Status**: 🆕 New (Dec 17, 2025)

#### Test Classes:

- **`TestParticleProgram`** (5 tests)
  - `test_particle_program_import` – Verifies ParticleProgram can be imported
  - `test_particle_program_instantiation` – Verifies program can be instantiated
  - `test_particle_program_has_vertex_source` – Verifies vertex shader source exists
  - `test_particle_program_has_fragment_source` – Verifies fragment shader source exists
  - `test_particle_program_uniform_names` – Verifies expected uniforms are defined

- **`TestParticleState`** (3 tests)
  - `test_particle_state_import` – Verifies ParticleState can be imported
  - `test_particle_state_creation` – Verifies state can be created with defaults
  - `test_particle_state_with_values` – Verifies state accepts custom values

- **`TestParticleTransition`** (4 tests)
  - `test_particle_transition_import` – Verifies transition class can be imported
  - `test_particle_transition_creation` – Verifies transition can be created
  - `test_particle_transition_modes` – Verifies all modes (Directional, Swirl, Converge)
  - `test_particle_transition_directions` – Verifies all 10 directions
  - `test_particle_transition_swirl_orders` – Verifies swirl orders (Typical, Center Outward, Edges Inward)

- **`TestSettingsDefaults`** (2 tests)
  - `test_settings_manager_has_particle_defaults` – Verifies particle defaults in SettingsManager
  - `test_settings_manager_has_particle_in_pool` – Verifies Particle in transition pool

---

## Test Summary

**Current Status** (Nov 6, 2025 - Integration Tests Added):
- Total Tests: ~170 across 22 modules
- Unit Tests: ~120 (95% coverage of core modules)
- Integration Tests: ~50 (transitions, clock, Lanczos, display tab)
- Passing: 100%
- Coverage: Core framework + Integration + Regression

**Previous Status** (Day 1):
- Total Tests: 23
- Passing: 23 (100%)
- Coverage: Core framework only

**Improvement**:
- +147 tests added
- +4 integration test modules
- Integration coverage increased from 0% to ~50%
- Regression tests added for all critical bugs

---

## Notes

- All tests follow logging-first policy (use file-based logging)
- PowerShell is the primary test runner environment (Windows 11)
- Tests are designed to be independent (no inter-test dependencies)
- Fixtures handle setup and teardown automatically
- Test output should be minimal (use `-v` for verbose only when needed)

---

**This document is the canonical reference for all testing. Update after adding, modifying, or removing tests.**
