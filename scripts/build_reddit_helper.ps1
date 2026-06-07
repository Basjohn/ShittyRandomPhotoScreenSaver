<#
Builds the Reddit helper watcher into a standalone EXE using an isolated persistent virtual environment.

Output:
  release/helpers/SRPSS_RedditHelper.exe

Persistent helper venv:
  build_deps/venv

This avoids global Python pollution while keeping builds fast and repeatable.
Dependencies are pinned in:
  build_deps/requirements_helper.txt

Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\build_reddit_helper.ps1
  powershell -ExecutionPolicy Bypass -File .\scripts\build_reddit_helper.ps1 -Console
  powershell -ExecutionPolicy Bypass -File .\scripts\build_reddit_helper.ps1 -ReinstallVenvDeps
#>

[CmdletBinding()]
param(
    [string]$EntryPoint = "helpers/reddit_helper_worker.py",
    [string]$AppName = "SRPSS_RedditHelper",
    [switch]$Console,
    [switch]$ReinstallVenvDeps
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

function Get-FileSha256 {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        return ""
    }

    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash
}

function Get-PythonVersionText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe
    )

    return (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null).Trim()
}

function Resolve-BasePython {
    Write-Host "[BUILD-HELPER] Locating Python 3.11..."

    $candidates = @()

    try {
        $py311 = (& py -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim()
        if ($py311) {
            $candidates += $py311
        }
    } catch {}

    try {
        $pyDefault = (& python -c "import sys; print(sys.executable)" 2>$null).Trim()
        if ($pyDefault) {
            $candidates += $pyDefault
        }
    } catch {}

    $candidates = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

    foreach ($candidate in $candidates) {
        try {
            $version = (& $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null).Trim()
            if ($version -eq "3.11") {
                Write-Host "[BUILD-HELPER] Using base Python: $candidate"
                return $candidate
            }
        } catch {}
    }

    throw "Python 3.11 was not found. Install Python 3.11 x64, then rerun this script."
}

function Ensure-HelperVenv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [Parameter(Mandatory = $true)]
        [string]$VenvDir,

        [Parameter(Mandatory = $true)]
        [string]$RequirementsFile,

        [switch]$ForceReinstallDeps
    )

    $VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
    $StampPath = Join-Path $VenvDir '.srpss_reddit_helper_deps_stamp.txt'

    if (-not (Test-Path $VenvPython)) {
        $BasePython = Resolve-BasePython

        if (Test-Path $VenvDir) {
            Write-Host "[BUILD-HELPER] Existing helper venv folder is incomplete; removing: $VenvDir"
            Remove-Item -Path $VenvDir -Recurse -Force
        }

        Write-Host "[BUILD-HELPER] Creating persistent helper virtual environment: $VenvDir"
        & $BasePython -m venv $VenvDir
    }

    if (-not (Test-Path $VenvPython)) {
        throw "Virtual environment Python not found: $VenvPython"
    }

    $venvVersion = Get-PythonVersionText -PythonExe $VenvPython
    if (-not $venvVersion.StartsWith("3.11.")) {
        throw "Existing helper venv is Python $venvVersion, but this build expects Python 3.11. Delete '$VenvDir' and rerun."
    }

    Write-Host "[BUILD-HELPER] Using helper venv Python: $VenvPython"
    Write-Host "[BUILD-HELPER] Helper venv Python version: $venvVersion"

    if (-not (Test-Path $RequirementsFile)) {
        throw "Requirements file not found: $RequirementsFile"
    }

    $requirementsHash = Get-FileSha256 -Path $RequirementsFile
    $desiredStamp = @(
        "python=$venvVersion"
        "requirements_sha256=$requirementsHash"
        "requires_pyinstaller=true"
    ) -join "`n"

    $existingStamp = ""
    if (Test-Path $StampPath) {
        $existingStamp = Get-Content $StampPath -Raw -ErrorAction SilentlyContinue
    }

    $pyInstallerAvailable = $false
    try {
        $pyInstallerVersion = (& $VenvPython -m PyInstaller --version 2>$null)
        if ($pyInstallerVersion) {
            $pyInstallerAvailable = $true
        }
    } catch {
        $pyInstallerAvailable = $false
    }

    $needsDeps = $ForceReinstallDeps -or (-not $pyInstallerAvailable) -or ($existingStamp.Trim() -ne $desiredStamp.Trim())

    if ($needsDeps) {
        Write-Host "[BUILD-HELPER] Installing/updating helper venv dependencies..."
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r $RequirementsFile
        $desiredStamp | Out-File -FilePath $StampPath -Encoding utf8 -Force
    } else {
        Write-Host "[BUILD-HELPER] Helper venv dependencies look current; skipping pip install."
    }

    try {
        $finalPyInstallerVersion = (& $VenvPython -m PyInstaller --version 2>$null)
        if (-not $finalPyInstallerVersion) {
            throw "PyInstaller version check returned empty output."
        }

        Write-Host "[BUILD-HELPER] PyInstaller $finalPyInstallerVersion (isolated)"
    } catch {
        throw "PyInstaller not available in helper virtual environment after dependency install."
    }

    return $VenvPython
}

Set-ScriptWindowMinimized -Disable:$Console

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$Root = $Root.Path

$ReleaseDir = Join-Path (Join-Path $Root 'release') 'helpers'
$LogDir = Join-Path $Root 'logs'
$BuildDepsDir = Join-Path $Root 'build_deps'
$VenvDir = Join-Path $BuildDepsDir 'venv'
$RequirementsFile = Join-Path $BuildDepsDir 'requirements_helper.txt'
$BuildDir = Join-Path $Root 'build_reddit_helper'

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir ("build_reddit_helper_{0}.log" -f $Timestamp)
$MaxLogFiles = 10

New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
New-Item -ItemType Directory -Force -Path $BuildDepsDir | Out-Null

# Rotate old helper build logs.
$existingLogs = @(Get-ChildItem -Path $LogDir -Filter "build_reddit_helper_*.log" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
if ($existingLogs.Count -ge $MaxLogFiles) {
    $logsToRemove = $existingLogs | Select-Object -Skip ($MaxLogFiles - 1)
    foreach ($log in $logsToRemove) {
        try {
            Remove-Item -Force $log.FullName
        } catch {}
    }
}

# Detect icon.
$IconPath = $null
$PreferredIcon = Join-Path $Root 'SRPSS.ico'
if (Test-Path $PreferredIcon) {
    $IconPath = (Get-Item $PreferredIcon).FullName
    Write-Host "[BUILD-HELPER] Using icon: $IconPath"
}

Write-Host "[BUILD-HELPER] Using isolated persistent helper virtual environment..."

$VenvPython = Ensure-HelperVenv `
    -Root $Root `
    -VenvDir $VenvDir `
    -RequirementsFile $RequirementsFile `
    -ForceReinstallDeps:$ReinstallVenvDeps

$EntryPath = Join-Path $Root $EntryPoint
if (-not (Test-Path $EntryPath)) {
    throw "Helper entry point not found: $EntryPath"
}

# Retrieve app version from central versioning module, if available.
$AppVersion = ""
try {
    Push-Location $Root
    try {
        $AppVersion = & $VenvPython -c "from versioning import APP_VERSION; print(APP_VERSION)"
    } finally {
        Pop-Location
    }

    if ($AppVersion) {
        $AppVersion = $AppVersion.Trim()
    }
} catch {
    $AppVersion = ""
}

if (-not $AppVersion) {
    $AppVersion = "1.0.0"
}

Write-Host "[BUILD-HELPER] App version: $AppVersion"

# PyInstaller args.
$argsList = @(
    "-m", "PyInstaller",
    "--onefile",
    "--clean",
    "--noconfirm",
    "--name", $AppName,
    "--distpath", $ReleaseDir,
    "--workpath", $BuildDir,
    "--specpath", $BuildDir,

    # Exclude heavy packages the helper should not need.
    "--exclude-module", "PySide6",
    "--exclude-module", "PySide2",
    "--exclude-module", "PyQt5",
    "--exclude-module", "PyQt6",
    "--exclude-module", "winrt",
    "--exclude-module", "numpy",
    "--exclude-module", "PIL",
    "--exclude-module", "Pillow",
    "--exclude-module", "sounddevice",
    "--exclude-module", "pycaw",
    "--exclude-module", "pytest"
)

if (-not $Console) {
    $argsList += @("--noconsole")
}

if ($IconPath) {
    $argsList += @("--icon", $IconPath)
}

$argsList += $EntryPath

Write-Host "[BUILD-HELPER] Starting PyInstaller (isolated)..."
Write-Host ("`"$VenvPython`" " + ($argsList -join ' '))

Push-Location $Root
try {
    & $VenvPython @argsList *>&1 | Tee-Object -FilePath $LogFile
} finally {
    Pop-Location
}

# Verify output.
$Exe = Join-Path $ReleaseDir "$AppName.exe"
if (-not (Test-Path $Exe)) {
    Write-Host "[BUILD-HELPER] Helper build failed. See log: $LogFile"
    exit 1
}

$size = (Get-Item $Exe).Length / 1MB
Write-Host "[BUILD-HELPER] Build success: $Exe ($([math]::Round($size, 1)) MB)"

# Clean up intermediate build directory.
try {
    if (Test-Path $BuildDir) {
        Remove-Item -Path $BuildDir -Recurse -Force -ErrorAction Stop
        Write-Host "[BUILD-HELPER] Cleaned build directory: $BuildDir"
    }
} catch {
    Write-Host "[BUILD-HELPER] Warning: Failed to delete build directory $BuildDir - $_"
}

Write-Host "[BUILD-HELPER] Log: $LogFile"
Write-Host "[BUILD-HELPER] Persistent helper virtual environment kept at: $VenvDir"
