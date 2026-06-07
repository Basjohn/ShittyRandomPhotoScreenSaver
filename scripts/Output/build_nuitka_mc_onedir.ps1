<#
Build script for Nuitka (one-dir) MC variant intended to avoid self-extracting stubs.
- Compiles main_mc.py into SRPSS_MC_onedir.exe plus dependency folder.
- Designed to reduce AV heuristics compared to --onefile bundles.

Usage:
  powershell -ExecutionPolicy Bypass -File .\scripts\build_nuitka_mc_onedir.ps1
  powershell -ExecutionPolicy Bypass -File .\scripts\build_nuitka_mc_onedir.ps1 -Console
#>

[CmdletBinding()]
param(
    [string]$EntryPoint = "main_mc.py",
    [string]$AppName = "SRPSS_Media_Center",
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

# Paths
$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$BuildDir = Join-Path $Root 'build_nuitka_mc_onedir'
$ReleaseDir = Join-Path $Root 'release'
$LogDir = Join-Path $Root 'logs'
$LogFile = Join-Path $LogDir 'build_nuitka_mc_onedir.log'

# Ensure dirs
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Detect icon in project root, preferring SRPSS.ico when present
$Icon = $null
$PreferredIcon = Join-Path $Root 'SRPSS.ico'
if (Test-Path $PreferredIcon) {
    $Icon = Get-Item $PreferredIcon
} else {
    $Icon = Get-ChildItem -Path $Root -Filter *.ico -File -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($Icon) {
    Write-Host "[BUILD-N-ONEDIR] Using icon: $($Icon.FullName)"
}

function Test-Nuitka {
    try {
        $ver = python -m nuitka --version 2>$null
        if (-not $ver) { throw "not found" }
        Write-Host "[BUILD-N-ONEDIR] Nuitka $ver"
    } catch {
        Write-Host "[BUILD-N-ONEDIR] Installing Nuitka..."
        python -m pip install --upgrade pip | Out-Null
        python -m pip install nuitka | Out-Null
        $ver2 = python -m nuitka --version
        Write-Host "[BUILD-N-ONEDIR] Nuitka $ver2"
    }
}
Test-Nuitka

# Retrieve version/metadata from central versioning module (if available)
$Version = ""
$Company = ""
$Description = ""
$ProductName = ""
try {
    $RawInfo = python -c "from versioning import APP_VERSION, APP_COMPANY, APP_DESCRIPTION, APP_NAME; print('||'.join((APP_VERSION, APP_COMPANY, APP_DESCRIPTION, APP_NAME)))"
    if ($RawInfo) {
        $parts = $RawInfo -split '\|\|'
        if ($parts.Length -ge 1) { $Version = $parts[0].Trim() }
        if ($parts.Length -ge 2) { $Company = $parts[1].Trim() }
        if ($parts.Length -ge 3) { $Description = $parts[2].Trim() }
        if ($parts.Length -ge 4) { $ProductName = ($parts[3].Trim() + " Media Center").Trim() }
    }
    if ($Version) {
        Write-Host "[BUILD-N-ONEDIR] Version: $Version"
    } else {
        Write-Host "[BUILD-N-ONEDIR] Version: (unknown - versioning.py missing APP_VERSION)"
    }
} catch {
    Write-Host "[BUILD-N-ONEDIR] Version/metadata: (unavailable - versioning.py not accessible)"
}

# Compose arguments for Nuitka
$EntryPath = Join-Path $Root $EntryPoint
if (-not (Test-Path $EntryPath)) { throw "Entry point not found: $EntryPath" }

if ($Console) {
    if ($AppName -eq "SRPSS_Media_Center") {
        $AppName = "SRPSS_Media_Center_debug"
    }
}

$consoleArg = "--windows-console-mode=disable" # No console window (release default)
if ($Console) {
    $consoleArg = "--windows-console-mode=force" # Always show console window
}

# Standalone/onedir bundle (no --onefile)
$argsList = @(
    "-m", "nuitka",
    "--standalone",
    "--remove-output",
    "--output-dir=$ReleaseDir",
    "--output-filename=$AppName",
    $consoleArg,
    "--enable-plugin=pyside6",
    "--include-data-dir=presets=presets",
    "--include-data-dir=themes=themes",
    "--include-data-dir=images=images",
    "--include-data-files=resources/tutuogg.ogg=resources/tutuogg.ogg",
    "--include-data-dir=widgets/spotify_visualizer/shaders=widgets/spotify_visualizer/shaders",
    "--include-package=ui.tabs",
    "--include-qt-plugins=multimedia",
    "--include-module=PySide6.QtMultimedia",
    "--include-module=winrt.windows.media.control",
    "--include-module=winrt.windows.storage.streams",
    "--include-module=winrt.windows.foundation",
    "--include-module=winrt.windows.foundation.collections",
    "--noinclude-default-mode=error"
)

if ($Version) {
    $argsList += "--product-version=$Version"
    $argsList += "--file-version=$Version"
}
if ($Company) {
    $argsList += "--company-name=$Company"
}
if ($Description) {
    $argsList += "--file-description=$Description"
}
if ($ProductName) {
    $argsList += "--product-name=$ProductName"
} else {
    $argsList += "--product-name=SRPSS - Media Center"
}

if ($Icon) {
    $argsList += @("--windows-icon-from-ico=$($Icon.FullName)")
}

$argsList += $EntryPath

Write-Host "[BUILD-N-ONEDIR] Starting Nuitka..."
Write-Host ("python " + ($argsList -join ' '))

Push-Location $Root
try {
    python @argsList *>&1 | Tee-Object -FilePath $LogFile
} finally {
    Pop-Location
}

# Verify outputs (standalone folder contains the exe)
$Exe = Get-ChildItem -Path $ReleaseDir -Recurse -Filter "$AppName.exe" -File -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $Exe) {
    Write-Host "[BUILD-N-ONEDIR] Build failed or no executable produced. See log: $LogFile"
    exit 1
}

$loggingCfgPath = Join-Path $Exe.DirectoryName "$($Exe.BaseName).logging.cfg"
try {
    if ($Console) {
        "1" | Out-File -FilePath $loggingCfgPath -Encoding utf8 -Force
    } else {
        if (Test-Path $loggingCfgPath) {
            Remove-Item -Force -Path $loggingCfgPath -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-Host "[BUILD-N-ONEDIR] Warning: Failed to manage logging config file: $loggingCfgPath"
}

# Clean up the intermediate Nuitka build folder now that the bundle is ready.
try {
    if (Test-Path $BuildDir) {
        Remove-Item -Path $BuildDir -Recurse -Force -ErrorAction Stop
        Write-Host "[BUILD-N-ONEDIR] Cleaned build directory: $BuildDir"
    }
} catch {
    Write-Host "[BUILD-N-ONEDIR] Warning: Failed to delete build directory $BuildDir - $_"
}

Write-Host "[BUILD-N-ONEDIR] Build success (one-dir root): $($Exe.DirectoryName)"
Write-Host "[BUILD-N-ONEDIR] Release directory: $ReleaseDir"
Write-Host "[BUILD-N-ONEDIR] Log: $LogFile"
