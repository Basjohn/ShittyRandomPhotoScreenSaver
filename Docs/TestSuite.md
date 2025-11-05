# Test Suite Documentation

**Purpose**: Canonical reference for all test modules, test cases, and testing procedures.  
**Last Updated**: Day 1 Implementation Complete  
**Test Count**: 23 tests across 4 modules  
**Pass Rate**: 100% (23/23 passing)

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

**Current Status** (Day 1 Complete):
- Total Tests: 23
- Passing: 23 (100%)
- Failing: 0
- Skipped: 0
- Coverage: Core framework (threading, resources, events, settings)

**Target** (End of Project):
- Total Tests: ~50-60
- Unit Tests: ~35
- Integration Tests: ~15
- Performance Tests: ~5
- Manual Tests: ~5

---

## Notes

- All tests follow logging-first policy (use file-based logging)
- PowerShell is the primary test runner environment (Windows 11)
- Tests are designed to be independent (no inter-test dependencies)
- Fixtures handle setup and teardown automatically
- Test output should be minimal (use `-v` for verbose only when needed)

---

**This document is the canonical reference for all testing. Update after adding, modifying, or removing tests.**
