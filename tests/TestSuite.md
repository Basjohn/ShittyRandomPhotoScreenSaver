# Test Suite

Living reference for testing architecture, policies, and practices.

## Goals

- Fast, reliable test feedback during development.
- Clear separation between unit, integration, and policy enforcement tests.
- Documented exceptions for flaky tests with manual validation paths.
- Static analysis tests that catch architectural policy violations early.

## Test Architecture

### Directory Layout

```
tests/
├── unit/                    # Fast, isolated tests (no Qt dependencies)
│   ├── core/               # Core module unit tests
│   └── test_policy_compliance.py  # Static analysis policy tests
├── conftest.py             # Shared fixtures (qt_app, settings_manager)
├── pytest.ini              # pytest configuration
└── test_*.py               # Integration tests (may have Qt dependencies)
```

### Test Categories

**Unit Tests** (`tests/unit/`)
- No Qt event loop dependencies
- Fast execution (< 1s per test file)
- Mock external dependencies
- Run in CI on every commit

**Integration Tests** (`tests/test_*.py`)
- Test component interactions
- May require Qt event loop
- May test real I/O (with mocks for external services)
- Run in CI with pytest-qt plugin

**Policy Enforcement Tests** (`tests/unit/test_policy_compliance.py`)
- Static analysis of codebase
- Verify architectural compliance
- No runtime dependencies
- Run in CI to catch policy violations

### Fixtures

**qt_app**
- Provides QApplication instance for Qt tests
- Auto-cleanup after test completion
- Use for any QWidget/QObject tests

**settings_manager**
- Isolated SettingsManager with temp profile
- Auto-cleanup after test
- Use for any settings-related tests

## Testing Policies

### Skip Markers

Tests may be skipped when:
1. **Flaky in CI**: Qt event loop cleanup issues, timing-dependent tests
2. **Platform-specific**: Windows-only or non-Windows tests
3. **Manual validation required**: Tests that require visual confirmation

**Required documentation**: Every skip must have a clear reason and manual run instructions.

### Threading in Tests

Raw `threading.Thread` is permitted in tests **only** for:
1. Simulating external library callbacks (pycaw, Windows hooks)
2. Testing ThreadManager's cross-thread dispatch
3. Testing UI thread safety from worker threads

Production code must use `ThreadManager` exclusively.

### Qt Test Stability

To minimize flaky Qt tests:
1. Always use `qt_app.processEvents()` after async operations
2. Use timeouts instead of infinite waits
3. Clean up widgets with `deleteLater()` in finally blocks
4. Avoid nested event loops

## Current Skip Markers

| Test | Reason | Manual Run Command |
|------|--------|-------------------|
| `test_thread_manager.py::test_overlay_timer_stop_is_safe_from_other_threads` | Qt event loop cleanup causes access violations in CI | `pytest tests/test_thread_manager.py::TestOverlayTimerIntegration::test_overlay_timer_stop_is_safe_from_other_threads -v` |
| `test_qt_timer_threading.py::test_overlay_timer_stop_is_safe_from_other_threads` | Qt event loop cleanup causes access violations in CI | `pytest tests/test_qt_timer_threading.py::test_overlay_timer_stop_is_safe_from_other_threads -v` |

## Policy Enforcement Tests

Located in `tests/unit/test_policy_compliance.py`:

**test_no_raw_threading_in_production_code**
- Verifies no `threading.Thread` usage outside exempted modules
- Exemptions: ThreadManager impl, external wrappers, pre-policy code

**test_no_threadpoolexecutor_in_production_code**
- Verifies no `ThreadPoolExecutor` outside ThreadManager

**test_no_deleteLater_without_resource_manager**
- Flags manual `deleteLater()` calls (informational only)
- Some cleanup code legitimately uses direct deletion

**test_settings_keys_use_dot_notation**
- Verifies settings use `category.subkey` format
- Flags unknown categories for review

**test_no_print_statements_in_production_code**
- Verifies no `print()` in production code
- Use logging with proper categories instead

### Exemptions (Pre-Policy Code)

The following modules are exempt from threading policy due to pre-policy implementation:
- `core/process/supervisor.py` - Pre-policy threading
- `rendering/adaptive_timer.py` - Pre-policy threading

## Running Tests

### Default (CI mode)
```bash
python -m pytest tests/ -v
```

### Include skipped tests
```bash
python -m pytest tests/ -v --run-skipped
```

### Only unit tests
```bash
python -m pytest tests/unit/ -v
```

### Specific test file
```bash
python -m pytest tests/unit/test_policy_compliance.py -v
```

### With coverage
```bash
python -m pytest tests/ --cov=core --cov=rendering --cov=ui --cov=widgets -v
```

## Common Patterns

### Testing Qt Widgets
```python
def test_widget_creation(qt_app, settings_manager):
    widget = MyWidget(settings_manager)
    assert widget is not None
    widget.deleteLater()
```

### Testing ThreadManager
```python
def test_task_submission(qt_app):
    manager = ThreadManager()
    result = []
    
    def task():
        return "done"
    
    def callback(res):
        result.append(res.result)
    
    manager.submit_task(ThreadPoolType.IO, task, callback=callback)
    time.sleep(0.1)  # Wait for completion
    
    assert result == ["done"]
    manager.shutdown()
```

### Testing Cross-Thread Safety
```python
def test_ui_dispatch_from_worker(qt_app):
    called = []
    
    def worker():
        ThreadManager.run_on_ui_thread(lambda: called.append(True))
    
    t = threading.Thread(target=worker)
    t.start()
    
    # Pump event loop until callback runs
    deadline = time.time() + 2.0
    while not called and time.time() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    
    t.join(timeout=1.0)
    assert called == [True]
```

## Troubleshooting

### Qt Tests Hang
- Check for infinite loops without `processEvents()`
- Add timeout to `t.join()` calls
- Ensure widgets are properly parented

### Access Violations on Teardown
- Use `pytest.mark.skip` for known flaky tests
- Run manually for validation
- Check for double-delete scenarios

### Import Errors
- Ensure `tests/__init__.py` exists
- Check PYTHONPATH includes project root
- Verify no circular imports in test files

## Test Maintenance

When adding new tests:
1. Place unit tests in `tests/unit/`
2. Add integration tests in `tests/`
3. Document any skip markers with reason
4. Run full suite before committing

When deprecating tests:
1. Rename with `_deprecated` suffix
2. Do not delete immediately (historical reference)
3. Remove from CI if problematic

When policy exemptions change:
1. Update `EXCLUDED_PATHS` in `test_policy_compliance.py`
2. Document reason for exemption
3. Plan migration path if applicable
