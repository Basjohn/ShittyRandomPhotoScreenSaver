<# 
Build script for Nuitka (one-dir) MC variant intended to avoid self-extracting stubs.

Legacy no-venv version:
- Uses the currently active/global Python on PATH
- Installs Nuitka only if missing
- Does not create or manage a project .venv
- Compiles main_mc.py into SRPSS_Media_Center.exe plus dependency folder

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
    param([switch]$Disable)
    if ($Disable) { return }
    try {
        Add-Type -Namespace SRPSS -Name NativeConsole -MemberDefinition @"
[DllImport("kernel32.dll")]
public static extern System.IntPtr GetConsoleWindow();
[DllImport("user32.dll")]
public static extern bool ShowWindowAsync(System.IntPtr hWnd, int nCmdShow);
"@ -ErrorAction SilentlyContinue | Out-Null
        $handle = [SRPSS.NativeConsole]::GetConsoleWindow()
        if ($handle -ne [IntPtr]::Zero) { [void][SRPSS.NativeConsole]::ShowWindowAsync($handle, 2) }
    } catch {}
}

Set-ScriptWindowMinimized -Disable:$Console

$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$Root = $Root.Path
$BuildDir = Join-Path $Root 'build_nuitka_mc_onedir'
$ReleaseDir = Join-Path $Root 'release'
$LogDir = Join-Path $Root 'logs'
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir ("build_nuitka_mc_onedir_{0}.log" -f $Timestamp)
$MaxLogFiles = 10

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$existingLogs = @(Get-ChildItem -Path $LogDir -Filter "build_nuitka_mc_onedir_*.log" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
if ($existingLogs.Count -ge $MaxLogFiles) {
    $logsToRemove = $existingLogs | Select-Object -Skip ($MaxLogFiles - 1)
    foreach ($log in $logsToRemove) {
        try { Remove-Item -Force $log.FullName } catch {}
    }
}

try {
    $nuitkaVersion = python -m nuitka --version
    Write-Host "[BUILD-N-ONEDIR] Nuitka $nuitkaVersion"
} catch {
    Write-Host "[BUILD-N-ONEDIR] Nuitka not found; installing into active/global Python..."
    python -m pip install --upgrade pip
    python -m pip install nuitka
    $nuitkaVersion = python -m nuitka --version
    Write-Host "[BUILD-N-ONEDIR] Nuitka $nuitkaVersion"
}

$Icon = $null
$PreferredIcon = Join-Path $Root 'SRPSS.ico'
if (Test-Path $PreferredIcon) {
    $Icon = Get-Item $PreferredIcon
} else {
    $Icon = Get-ChildItem -Path $Root -Filter *.ico -File -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($Icon) { Write-Host "[BUILD-N-ONEDIR] Using icon: $($Icon.FullName)" }

$Version = ""
$Company = ""
$Description = ""
$ProductName = ""

try {
    Push-Location $Root
    try {
        $RawInfo = python -c "from versioning import APP_VERSION, APP_COMPANY, APP_DESCRIPTION, APP_NAME; print('||'.join((APP_VERSION, APP_COMPANY, APP_DESCRIPTION, APP_NAME)))"
    } finally {
        Pop-Location
    }
    if ($RawInfo) {
        $parts = $RawInfo -split '\|\|'
        if ($parts.Length -ge 1) { $Version = $parts[0].Trim() }
        if ($parts.Length -ge 2) { $Company = $parts[1].Trim() }
        if ($parts.Length -ge 3) { $Description = $parts[2].Trim() }
        if ($parts.Length -ge 4) { $ProductName = ($parts[3].Trim() + " Media Center").Trim() }
    }
    if ($Version) { Write-Host "[BUILD-N-ONEDIR] Version: $Version" } else { Write-Host "[BUILD-N-ONEDIR] Version: (unknown - versioning.py missing APP_VERSION)" }
} catch {
    Write-Host "[BUILD-N-ONEDIR] Version/metadata: (unavailable - versioning.py not accessible)"
}

$EntryPath = Join-Path $Root $EntryPoint
if (-not (Test-Path $EntryPath)) { throw "Entry point not found: $EntryPath" }

if ($Console) {
    if ($AppName -eq "SRPSS_Media_Center") { $AppName = "SRPSS_Media_Center_debug" }
}

$consoleArg = "--windows-console-mode=disable"
if ($Console) { $consoleArg = "--windows-console-mode=force" }

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
if ($Company) { $argsList += "--company-name=$Company" }
if ($Description) { $argsList += "--file-description=$Description" }
if ($ProductName) { $argsList += "--product-name=$ProductName" } else { $argsList += "--product-name=SRPSS - Media Center" }
if ($Icon) { $argsList += @("--windows-icon-from-ico=$($Icon.FullName)") }

$argsList += $EntryPath

Write-Host "[BUILD-N-ONEDIR] Starting Nuitka..."
Write-Host ("python " + ($argsList -join ' '))

Push-Location $Root
try {
    python @argsList *>&1 | Tee-Object -FilePath $LogFile
} finally {
    Pop-Location
}

$Exe = Get-ChildItem -Path $ReleaseDir -Recurse -Filter "$AppName.exe" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Exe) {
    Write-Host "[BUILD-N-ONEDIR] Build failed or no executable produced. See log: $LogFile"
    exit 1
}

$loggingCfgPath = Join-Path $Exe.DirectoryName "$($Exe.BaseName).logging.cfg"
try {
    if ($Console) {
        "1" | Out-File -FilePath $loggingCfgPath -Encoding utf8 -Force
    } else {
        if (Test-Path $loggingCfgPath) { Remove-Item -Force -Path $loggingCfgPath -ErrorAction SilentlyContinue }
    }
} catch {
    Write-Host "[BUILD-N-ONEDIR] Warning: Failed to manage logging config file: $loggingCfgPath"
}

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
