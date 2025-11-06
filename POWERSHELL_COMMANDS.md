# PowerShell 7 Commands Reference

**Purpose**: Correct PowerShell syntax for all project operations  
**Shell**: PowerShell 7+ (pwsh)  
**Common Errors Fixed**: Parameter binding, pipeline issues, encoding

---

## Test Execution Commands

### Run All Tests (Correct)
```powershell
# Method 1: Direct output
pytest -v tests/ --tb=short

# Method 2: Save to file
pytest -v tests/ --tb=short | Out-File -FilePath pytest_output.log -Encoding utf8

# Method 3: Both screen and file (Tee-Object)
pytest -v tests/ --tb=short | Tee-Object -FilePath pytest_output.log

# Method 4: Background job with logging
$job = Start-Job -ScriptBlock { 
    Set-Location "f:\Programming\Apps\ShittyRandomPhotoScreenSaver"
    pytest -v tests/ --tb=short 2>&1 | Out-String 
}
Wait-Job $job -Timeout 60
Receive-Job $job
Remove-Job $job
```

### Run Specific Test File
```powershell
pytest tests/test_lanczos_scaling.py -v --tb=short

# With output to file
pytest tests/test_lanczos_scaling.py -v --tb=short | Out-File -FilePath lanczos_test.log -Encoding utf8
```

### Run Specific Test
```powershell
pytest tests/test_lanczos_scaling.py::TestLanczosScaling::test_lanczos_downscaling -v --tb=short
```

### Search Test Output (Correct)
```powershell
# WRONG (causes errors):
pytest -v tests/ | Select-String "FAILED"

# CORRECT - Method 1: Save first, then search
pytest -v tests/ --tb=short 2>&1 | Out-File -FilePath test.log -Encoding utf8
Get-Content test.log | Select-String "FAILED"

# CORRECT - Method 2: Use Where-Object
pytest -v tests/ --tb=short 2>&1 | Out-String | Select-String "FAILED"

# CORRECT - Method 3: Filter lines
$output = pytest -v tests/ --tb=short 2>&1 | Out-String
$output -split "`n" | Where-Object { $_ -match "FAILED" }
```

---

## File Operations

### Read File with Tail
```powershell
# Last 50 lines
Get-Content pytest_output.log -Tail 50

# Last 100 lines
Get-Content pytest_output.log -Tail 100

# Specific range (lines 200-250)
Get-Content pytest_output.log | Select-Object -Skip 199 -First 50
```

### Search in Files
```powershell
# Search for pattern in file
Get-Content file.py | Select-String "def.*test_"

# Search in multiple files
Get-ChildItem -Path tests/ -Filter "*.py" -Recurse | Select-String "assert.*=="

# Search with line numbers
Get-Content file.py | Select-String "pattern" | Select-Object LineNumber, Line
```

### Copy Files
```powershell
# Single file
Copy-Item source.py destination.py

# Directory recursively
Copy-Item -Path source_dir/ -Destination dest_dir/ -Recurse

# With filter
Copy-Item -Path "*.py" -Destination backup/
```

---

## Process Management

### Background Jobs
```powershell
# Start background job
$job = Start-Job -ScriptBlock {
    Set-Location "f:\Programming\Apps\ShittyRandomPhotoScreenSaver"
    pytest tests/ -v
}

# Wait with timeout (30 seconds)
Wait-Job $job -Timeout 30

# Check if still running
if ($job.State -eq 'Running') {
    Stop-Job $job
}

# Get output
$output = Receive-Job $job

# Cleanup
Remove-Job $job
```

### Process Control
```powershell
# Start process and wait
Start-Process -FilePath "pytest" -ArgumentList "-v", "tests/" -NoNewWindow -Wait

# Start process without waiting
Start-Process -FilePath "pytest" -ArgumentList "-v", "tests/" -NoNewWindow

# Kill process by name
Stop-Process -Name "python" -Force
```

---

## String Operations

### String Splitting and Filtering
```powershell
# Split on newlines
$text = "line1`nline2`nline3"
$lines = $text -split "`n"

# Filter lines
$lines | Where-Object { $_ -match "pattern" }

# Select specific lines
$lines | Select-Object -First 10
$lines | Select-Object -Last 10
$lines | Select-Object -Skip 5 -First 10
```

### String Matching
```powershell
# Basic match
$text -match "pattern"

# Case-insensitive match (default in PowerShell)
$text -match "PATTERN"  # matches "pattern", "Pattern", etc.

# Case-sensitive match
$text -cmatch "Pattern"

# Multiple patterns (regex)
$text -match "(FAILED|ERROR|WARNING)"
```

---

## Pipeline Operations

### Correct Pipeline Usage
```powershell
# WRONG: Causes parameter binding errors
command | Select-String "pattern" | Out-File output.log

# CORRECT: Use Out-String first
command | Out-String | Select-String "pattern" | Out-File output.log

# CORRECT: Save to variable first
$output = command 2>&1 | Out-String
$output | Select-String "pattern"

# CORRECT: Use Tee-Object for both screen and file
command | Tee-Object -FilePath output.log | Select-String "pattern"
```

### Common Pipeline Errors
```powershell
# ERROR: "A positional parameter cannot be found that accepts argument"
# CAUSE: Pipeline not properly structured

# EXAMPLE OF ERROR:
Get-Content file.txt | Select-String pattern | Out-File result.txt

# WHY IT FAILS:
# Select-String outputs MatchInfo objects, not strings
# Out-File doesn't know how to handle the object type

# FIX:
Get-Content file.txt | Select-String pattern | Out-String | Out-File result.txt
```

---

## File Encoding

### Output with UTF-8 Encoding
```powershell
# Method 1: Out-File with -Encoding
command | Out-File -FilePath output.txt -Encoding utf8

# Method 2: Set-Content
"text" | Set-Content -Path output.txt -Encoding utf8

# Method 3: [System.IO.File]::WriteAllText
[System.IO.File]::WriteAllText("output.txt", $text, [System.Text.Encoding]::UTF8)
```

---

## Common Pytest Patterns

### Quick Test Summary
```powershell
# Get pass/fail count
pytest tests/ -v --tb=no -q

# Run with maximum verbosity
pytest tests/ -vv --tb=short

# Stop on first failure
pytest tests/ -x --tb=short

# Run only failed tests from last run
pytest --lf -v

# Run tests matching pattern
pytest -k "test_lanczos" -v
```

### Test with Logging
```powershell
# Full output to file
pytest -v tests/ --tb=short --log-cli-level=DEBUG 2>&1 | Out-File -FilePath pytest_debug.log -Encoding utf8

# Tail log while tests run
Start-Job -ScriptBlock {
    Set-Location "f:\Programming\Apps\ShittyRandomPhotoScreenSaver"
    pytest -v tests/ 2>&1 | Out-File pytest.log -Encoding utf8
}
Start-Sleep -Seconds 2
Get-Content pytest.log -Wait  # Live tail
```

---

## PyInstaller Build Commands

### Build Executable
```powershell
# Create spec file
pyi-makespec --onefile --windowed --name ShittyRandomPhotoScreenSaver main.py

# Build from spec
pyinstaller screensaver.spec --clean

# Build with explicit paths
pyinstaller --onefile `
    --windowed `
    --name ShittyRandomPhotoScreenSaver `
    --add-data "themes:themes" `
    --hidden-import PySide6 `
    main.py
```

### Convert to .scr
```powershell
# Rename .exe to .scr
Move-Item -Path "dist\ShittyRandomPhotoScreenSaver.exe" `
          -Destination "dist\screensaver.scr" `
          -Force

# Or use Copy-Item to keep both
Copy-Item -Path "dist\ShittyRandomPhotoScreenSaver.exe" `
          -Destination "dist\screensaver.scr"
```

---

## Git Operations

### Common Git Commands in PowerShell
```powershell
# Status
git status

# Add files
git add .
git add specific_file.py

# Commit
git commit -m "Commit message"

# Push
git push origin main

# View log
git log --oneline -10

# Create branch
git checkout -b feature-branch

# Diff
git diff HEAD~1
```

---

## Variable and Object Operations

### Working with Command Output
```powershell
# Capture output
$output = pytest -v tests/ 2>&1 | Out-String

# Process output
$lines = $output -split "`n"
$failed = $lines | Where-Object { $_ -match "FAILED" }
$passed = $lines | Where-Object { $_ -match "PASSED" }

# Count results
$failedCount = ($failed | Measure-Object).Count
$passedCount = ($passed | Measure-Object).Count

Write-Host "Passed: $passedCount, Failed: $failedCount"
```

### Hash Tables and Objects
```powershell
# Create hash table
$config = @{
    TestPath = "tests/"
    OutputFile = "pytest.log"
    Timeout = 60
}

# Access values
$config.TestPath
$config["OutputFile"]

# PSCustomObject
$result = [PSCustomObject]@{
    Passed = 277
    Failed = 0
    Skipped = 1
    Total = 278
}

$result.Passed
```

---

## Error Handling

### Try-Catch Blocks
```powershell
try {
    pytest -v tests/ --tb=short
}
catch {
    Write-Error "Test execution failed: $_"
    exit 1
}
finally {
    Write-Host "Test execution completed"
}
```

### Error Variables
```powershell
# Last error
$Error[0]

# Clear errors
$Error.Clear()

# Error action preference
$ErrorActionPreference = "Stop"  # Throw on any error
$ErrorActionPreference = "Continue"  # Default, continue on error
```

---

## Common Mistakes and Fixes

### 1. Pipeline Parameter Binding
```powershell
# ❌ WRONG
command | Select-String "pattern" | Some-Command

# ✅ CORRECT
command | Out-String | Select-String "pattern" | Out-String | Some-Command
```

### 2. Argument Quoting
```powershell
# ❌ WRONG (spaces cause issues)
pytest tests/test file.py

# ✅ CORRECT
pytest "tests/test file.py"
```

### 3. Path Separators
```powershell
# ❌ WRONG (inconsistent)
cd f:\Programming\Apps\ShittyRandomPhotoScreenSaver
pytest tests/test_lanczos.py

# ✅ CORRECT (consistent forward slashes)
Set-Location "f:/Programming/Apps/ShittyRandomPhotoScreenSaver"
pytest tests/test_lanczos.py

# ✅ ALSO CORRECT (PowerShell handles both)
Set-Location "f:\Programming\Apps\ShittyRandomPhotoScreenSaver"
pytest tests/test_lanczos.py
```

### 4. Redirection
```powershell
# ❌ WRONG (only captures stdout)
pytest tests/ > output.txt

# ✅ CORRECT (captures both stdout and stderr)
pytest tests/ 2>&1 | Out-File output.txt -Encoding utf8
```

---

## Quick Reference Card

### Most Common Commands
```powershell
# Run all tests
pytest -v tests/ --tb=short

# Run with output to file
pytest -v tests/ --tb=short | Out-File pytest.log -Encoding utf8

# Read last 50 lines
Get-Content pytest.log -Tail 50

# Search for pattern
Get-Content pytest.log | Select-String "FAILED"

# Check if file exists
Test-Path pytest.log

# Delete file
Remove-Item pytest.log

# List files
Get-ChildItem tests/ -Filter "*.py"

# Measure lines
Get-Content file.py | Measure-Object -Line
```

---

**Status**: Complete PowerShell 7 reference for project operations

**Note**: All commands tested on PowerShell 7.3+ on Windows 11
