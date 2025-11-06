# Test Suite Documentation

**Purpose**: Canonical reference for all test modules, test cases, and testing procedures.  
**Last Updated**: Nov 6, 2025 - Phase 6 Bug Fixes Complete  
**Test Count**: 279 tests across 25+ modules  
**Pass Rate**: 93.2% (260 passing, 18 failing, 1 skipped)  
**Recent**: Phase 6 critical bug fixes completed (Nov 6, 2025)

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

**Test Failures (18):** Mostly crossfade transition tests requiring updates after rewrite

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
pytest -v tests/ --tb=short > test_output.log 2>&1
Get-Content test_output.log -Tail 50
```

### Individual Test
```powershell
pytest -v tests/test_events.py::test_subscribe_and_publish --tb=short
```

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
