<#
Builds the Reddit helper watcher into a standalone EXE using an isolated virtual environment.

The resulting SRPSS_RedditHelper.exe is placed in release/helpers/ so both
Inno Setup installers can include it.

Uses a local virtual environment to avoid dependency conflicts with system Python.
Dependencies are pinned in build_deps/requirements_helper.txt.

Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\build_reddit_helper.ps1
#>

[CmdletBinding()]
param(
    [string]$EntryPoint = "helpers/reddit_helper_worker.py",
    [string]$AppName = "SRPSS_RedditHelper",
    [switch]$Console
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Set-ScriptWindowMinimized {
    param(
        [switch]$Disable
    )

    if ($Disable) {
        return
    }

    try {
        Add-Type -Namespace SRPSS -Name NativeConsole -MemberDefinition @"
[DllImport("kernel32.dll")]
public static extern System.IntPtr GetConsoleWindow();

[DllImport("user32.dll")]
public static extern bool ShowWindowAsync(System.IntPtr hWnd, int nCmdShow);
"@ -ErrorAction SilentlyContinue | Out-Null

        $handle = [SRPSS.NativeConsole]::GetConsoleWindow()
        if ($handle -ne [IntPtr]::Zero) {
            [void][SRPSS.NativeConsole]::ShowWindowAsync($handle, 2)
        }
    } catch {
        # Best-effort only; build behavior should not depend on window state changes.
    }
}

Set-ScriptWindowMinimized -Disable:$Console

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$ReleaseDir = Join-Path $Root 'release' 'helpers'
$LogDir = Join-Path $Root 'logs'
$BuildDepsDir = Join-Path $Root 'build_deps'
$VenvDir = Join-Path $BuildDepsDir 'venv'
$RequirementsFile = Join-Path $BuildDepsDir 'requirements_helper.txt'
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir ("build_reddit_helper_{0}.log" -f $Timestamp)

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Detect icon
$IconPath = $null
$PreferredIcon = Join-Path $Root 'SRPSS.ico'
if (Test-Path $PreferredIcon) {
    $IconPath = (Get-Item $PreferredIcon).FullName
}

# Verify requirements file exists
if (-not (Test-Path $RequirementsFile)) {
    throw "Requirements file not found: $RequirementsFile"
}

Write-Host "[BUILD-HELPER] Using isolated virtual environment..."

# Create/update virtual environment if needed
if (-not (Test-Path $VenvDir)) {
    Write-Host "[BUILD-HELPER] Creating virtual environment..."
    python -m venv $VenvDir --clear
}

# Get Python and pip paths from venv
$VenvPython = Join-Path $VenvDir 'Scripts' 'python.exe'
$VenvPip = Join-Path $VenvDir 'Scripts' 'pip.exe'

if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment Python not found: $VenvPython"
}

# Install/update dependencies in venv
Write-Host "[BUILD-HELPER] Installing pinned dependencies..."
& $VenvPip install --upgrade pip | Out-Null
& $VenvPip install -r $RequirementsFile | Out-Null

# Verify PyInstaller is available in venv
try {
    $ver = & $VenvPython -m PyInstaller --version 2>$null
    if (-not $ver) { throw "not found" }
    Write-Host "[BUILD-HELPER] PyInstaller $ver (isolated)"
} catch {
    throw "PyInstaller not available in virtual environment"
}

$EntryPath = Join-Path $Root $EntryPoint
if (-not (Test-Path $EntryPath)) {
    throw "Helper entry point not found: $EntryPath"
}

# Retrieve version
$AppVersion = ""
try {
    $AppVersion = & $VenvPython -c "from versioning import APP_VERSION; print(APP_VERSION)"
    if ($AppVersion) { $AppVersion = $AppVersion.Trim() }
} catch { $AppVersion = "" }
if (-not $AppVersion) { $AppVersion = "1.0.0" }

# PyInstaller args
$argsList = @(
    "-m", "PyInstaller",
    "--onefile",
    "--clean",
    "--noconfirm",
    "--name", $AppName,
    "--distpath", $ReleaseDir,
    "--workpath", (Join-Path $Root "build_reddit_helper"),
    "--specpath", (Join-Path $Root "build_reddit_helper"),
    # Exclude heavy packages the helper doesn't need
    "--exclude-module", "PySide6",
    "--exclude-module", "PySide2",
    "--exclude-module", "PyQt5",
    "--exclude-module", "winrt",
    "--exclude-module", "numpy",
    "--exclude-module", "PIL"
)

if (-not $Console) {
    $argsList += @("--noconsole")
}

if ($IconPath) {
    $argsList += @("--icon", $IconPath)
}

$argsList += $EntryPath

Write-Host "[BUILD-HELPER] Starting PyInstaller (isolated)..."
Write-Host ("$VenvPython " + ($argsList -join ' '))

Push-Location $Root
try {
    & $VenvPython @argsList *>&1 | Tee-Object -FilePath $LogFile
} finally {
    Pop-Location
}

# Verify output
$Exe = Join-Path $ReleaseDir "$AppName.exe"
if (-not (Test-Path $Exe)) {
    Write-Host "[BUILD-HELPER] Helper build failed. See log: $LogFile"
    exit 1
}

$size = (Get-Item $Exe).Length / 1MB
Write-Host "[BUILD-HELPER] Build success: $Exe ($([math]::Round($size, 1)) MB)"

# Clean up intermediate build directory
$BuildDir = Join-Path $Root "build_reddit_helper"
try {
    if (Test-Path $BuildDir) {
        Remove-Item -Path $BuildDir -Recurse -Force -ErrorAction Stop
        Write-Host "[BUILD-HELPER] Cleaned build directory: $BuildDir"
    }
} catch {
    Write-Host "[BUILD-HELPER] Warning: Failed to delete build directory $BuildDir - $_"
}

Write-Host "[BUILD-HELPER] Log: $LogFile"
Write-Host "[BUILD-HELPER] Virtual environment kept at: $VenvDir"
