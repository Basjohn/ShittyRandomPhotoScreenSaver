# Running Tests in SRPSS

This workflow documents how to properly run tests in the ShittyRandomPhotoScreenSaver project.

## Quick Test Run

// turbo
Run specific test file with verbose output and check exit code:
```powershell
python -m pytest tests/test_widget_positioning_comprehensive.py -v --tb=short; echo "Exit code: $LASTEXITCODE"
```

## Full Test Suite (positioning only)

// turbo
Run all positioning-related tests:
```powershell
python -m pytest tests/test_widget_positioner.py tests/test_widget_positioning_comprehensive.py -v --tb=short; echo "Exit code: $LASTEXITCODE"
```

## Logging Test Output

If you need to capture output to a log file:
```powershell
python -m pytest tests/<test_file>.py -v --tb=short > logs/<testname>.log 2>&1
type logs/<testname>.log
```

Note: Output piping in PowerShell may not display inline - use `type` or `Get-Content` after.

## Exit Code Interpretation

- `0` = All tests passed
- `1` = Some tests failed
- `5` = No tests collected (check test file path)

## Syntax Check Only

// turbo
Quick syntax validation without running tests:
```powershell
python -c "import py_compile; py_compile.compile(r'path/to/file.py'); print('Syntax OK')"
```

## pytest.ini markers

The project uses these markers (defined in `pytest.ini`):
- `@pytest.mark.qt` - Qt-dependent tests
- `@pytest.mark.rss` - RSS-related tests (skipped by default)
- `@pytest.mark.hybrid` - Hybrid tests (skipped by default)
- `@pytest.mark.slow` - Slow tests
