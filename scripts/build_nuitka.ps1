<# 
Build script for Nuitka (single-file) with AV-friendly defaults.

Legacy no-venv version:
- Uses the currently active/global Python on PATH
- Installs Nuitka only if missing
- Does not create or manage a project .venv
- Stages Nuitka output under /build/normal/screensaver and publishes /release/screensaver
- Auto-detects an .ico in project root for --windows-icon-from-ico
- Keeps optimizations reasonable to avoid AV false positives

Usage:
powershell -ExecutionPolicy Bypass -File .\scripts\build_nuitka.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build_nuitka.ps1 -Console
#>

[CmdletBinding()]
param(
    [string]$EntryPoint = "main.py",
    [string]$AppName = "SRPSS",
    [switch]$Console,
    [switch]$KeepExe,
    [switch]$SkipScrRename
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
$BuildRoot = Join-Path $Root 'build'
$BuildDir = Join-Path $BuildRoot 'normal\screensaver'
$BuildOutputDir = Join-Path $BuildDir 'output'
$PackageDir = Join-Path $BuildDir 'package'
$ReleaseRoot = Join-Path $Root 'release'
$DistributionDir = Join-Path $ReleaseRoot 'screensaver'
$LogDir = Join-Path $Root 'logs'
$BuildLayoutScript = Join-Path $Root 'tools\build_layout.ps1'
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir ("build_nuitka_{0}.log" -f $Timestamp)
$MaxLogFiles = 10

if (-not (Test-Path -LiteralPath $BuildLayoutScript -PathType Leaf)) {
    throw "Shared build layout helper not found: $BuildLayoutScript"
}
. $BuildLayoutScript

foreach ($RequiredBuildCommand in @(
    'Reset-SRPSSBuildDirectory',
    'Remove-SRPSSBuildDirectory',
    'Publish-SRPSSDirectory'
)) {
    if (-not (Get-Command $RequiredBuildCommand -CommandType Function -ErrorAction SilentlyContinue)) {
        throw "Shared build layout did not load required function: $RequiredBuildCommand"
    }
}

Reset-SRPSSBuildDirectory -Path $BuildDir -BuildRoot $BuildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $BuildOutputDir | Out-Null
New-Item -ItemType Directory -Force -Path $ReleaseRoot | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$existingLogs = @(Get-ChildItem -Path $LogDir -Filter "build_nuitka_*.log" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
if ($existingLogs.Count -ge $MaxLogFiles) {
    $logsToRemove = $existingLogs | Select-Object -Skip ($MaxLogFiles - 1)
    foreach ($log in $logsToRemove) {
        try { Remove-Item -Force $log.FullName } catch {}
    }
}

try {
    $nuitkaVersion = python -m nuitka --version
    Write-Host "[BUILD-N] Nuitka $nuitkaVersion"
} catch {
    Write-Host "[BUILD-N] Nuitka not found; installing into active/global Python..."
    python -m pip install --upgrade pip
    python -m pip install nuitka
    $nuitkaVersion = python -m nuitka --version
    Write-Host "[BUILD-N] Nuitka $nuitkaVersion"
}

$Icon = $null
$PreferredIcon = Join-Path $Root 'SRPSS.ico'
if (Test-Path $PreferredIcon) {
    $Icon = Get-Item $PreferredIcon
} else {
    $Icon = Get-ChildItem -Path $Root -Filter *.ico -File -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($Icon) { Write-Host "[BUILD-N] Using icon: $($Icon.FullName)" }

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
        if ($parts.Length -ge 4) { $ProductName = $parts[3].Trim() }
    }
    if ($Version) { Write-Host "[BUILD-N] Version: $Version" } else { Write-Host "[BUILD-N] Version: (unknown - versioning.py missing APP_VERSION)" }
} catch {
    Write-Host "[BUILD-N] Version/metadata: (unavailable - versioning.py not accessible)"
}

if (-not $ProductName) { $ProductName = "ShittyRandomPhotoScreenSaver" }
if (-not $Description) { $Description = "ShittyRandomPhotoScreenSaver" }

$EntryPath = Join-Path $Root $EntryPoint
if (-not (Test-Path $EntryPath)) { throw "Entry point not found: $EntryPath" }

if ($Console) {
    if ($AppName -eq "SRPSS") { $AppName = "SRPSS_debug" }
}

$consoleArg = "--windows-console-mode=disable"
if ($Console) { $consoleArg = "--windows-console-mode=force" }

$argsList = @(
    "-m", "nuitka",
    "--mingw64",
    "--jobs=2",
    "--onefile",
    "--standalone",
    "--remove-output",
    $consoleArg,
    "--output-dir=$BuildOutputDir",
    "--output-filename=$AppName",
    "--enable-plugin=pyside6",
    "--include-data-dir=presets=presets",
    "--include-data-dir=themes=themes",
    "--include-data-dir=images=images",
    "--include-data-files=resources/tutuogg.ogg=resources/tutuogg.ogg",
    "--include-data-dir=widgets/spotify_visualizer/shaders=widgets/spotify_visualizer/shaders",
    "--include-data-dir=rendering/quick/qml=rendering/quick/qml",
    "--include-package=rendering.quick",
    "--include-package=ui.tabs",
    "--include-qt-plugins=multimedia",
    "--include-qt-plugins=qml",
    "--include-module=PySide6.QtMultimedia",
    "--include-module=PySide6.QtQuick",
    "--include-module=PySide6.QtQml",
    "--include-module=winrt.windows.media.control",
    "--include-module=winrt.windows.storage.streams",
    "--include-module=winrt.windows.foundation",
    "--include-module=winrt.windows.foundation.collections",
    "--noinclude-default-mode=error"
)

$argsList += "--onefile-tempdir-spec={CACHE_DIR}/SRPSS/onefile"

if ($Icon) { $argsList += @("--windows-icon-from-ico=$($Icon.FullName)") }
if ($Version) {
    $argsList += "--product-version=$Version"
    $argsList += "--file-version=$Version"
}
if ($Company) { $argsList += "--company-name=$Company" }
if ($Description) { $argsList += "--file-description=$Description" }
if ($ProductName) { $argsList += "--product-name=$ProductName" }

$argsList += $EntryPath

Write-Host "[BUILD-N] Starting Nuitka..."
Write-Host ("python " + ($argsList -join ' '))

$CompilerTempDir = Join-Path $BuildDir 'compiler-temp'
New-Item -ItemType Directory -Force -Path $CompilerTempDir | Out-Null

# Keep GCC/ld response files out of C:\WINDOWS\TEMP. This remains local
# to this worker and does not require any new build_layout.ps1 functions.
$PreviousCompilerTempEnvironment = [ordered]@{}
foreach ($EnvironmentName in @('TEMP', 'TMP', 'TMPDIR')) {
    $PreviousCompilerTempEnvironment[$EnvironmentName] =
        [System.Environment]::GetEnvironmentVariable(
            $EnvironmentName,
            [System.EnvironmentVariableTarget]::Process
        )
    [System.Environment]::SetEnvironmentVariable(
        $EnvironmentName,
        $CompilerTempDir,
        [System.EnvironmentVariableTarget]::Process
    )
}
Write-Host "[BUILD-N] Compiler temporary directory: $CompilerTempDir"

$BuildExit = 1
try {
    Push-Location $Root
    try {
        python @argsList *>&1 | Tee-Object -FilePath $LogFile
        $BuildExit = $LASTEXITCODE
    } finally {
        Pop-Location
    }
} finally {
    foreach ($EnvironmentName in @('TEMP', 'TMP', 'TMPDIR')) {
        [System.Environment]::SetEnvironmentVariable(
            $EnvironmentName,
            $PreviousCompilerTempEnvironment[$EnvironmentName],
            [System.EnvironmentVariableTarget]::Process
        )
    }
}

if ($BuildExit -ne 0) {
    Write-Host "[BUILD-N] Build failed with exit code $BuildExit. See log: $LogFile"
    exit $BuildExit
}

$Exe = Get-ChildItem -Path $BuildOutputDir -Recurse -Filter "$AppName.exe" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Exe) {
    Write-Host "[BUILD-N] Build failed or no executable produced. See log: $LogFile"
    exit 1
}

$primaryArtifact = $Exe

if (-not $SkipScrRename) {
    $scrPath = [System.IO.Path]::ChangeExtension($Exe.FullName, ".scr")
    try {
        if (Test-Path $scrPath) { Remove-Item -Force -Path $scrPath }
    } catch {
        Write-Host "[BUILD-N] Warning: failed to delete existing SCR $scrPath"
    }

    try {
        if ($KeepExe) {
            Copy-Item -Force -Path $Exe.FullName -Destination $scrPath
            $primaryArtifact = Get-Item $scrPath
            Write-Host "[BUILD-N] SCR copy created; original EXE retained due to -KeepExe."
        } else {
            Move-Item -Force -Path $Exe.FullName -Destination $scrPath
            $primaryArtifact = Get-Item $scrPath
        }
    } catch {
        Write-Host "[BUILD-N] Error: failed to create SCR at $scrPath"
        exit 1
    }
} else {
    Write-Host "[BUILD-N] SkipScrRename enabled; SCR copy not produced."
}

if (Test-Path -LiteralPath $PackageDir) {
    Remove-Item -LiteralPath $PackageDir -Recurse -Force
}
New-Item -ItemType Directory -Path $PackageDir | Out-Null
Copy-Item -LiteralPath $primaryArtifact.FullName -Destination $PackageDir -Force
if (
    $KeepExe -and
    ($primaryArtifact.Extension -ieq ".scr") -and
    (Test-Path -LiteralPath $Exe.FullName -PathType Leaf)
) {
    Copy-Item -LiteralPath $Exe.FullName -Destination $PackageDir -Force
}

$packagedPrimaryPath = Join-Path $PackageDir $primaryArtifact.Name
$loggingCfgPath = [System.IO.Path]::ChangeExtension($packagedPrimaryPath, ".logging.cfg")
try {
    if ($Console) {
        "1" | Out-File -FilePath $loggingCfgPath -Encoding utf8 -Force
    } else {
        if (Test-Path $loggingCfgPath) { Remove-Item -Force -Path $loggingCfgPath -ErrorAction SilentlyContinue }
    }
} catch {
    Write-Host "[BUILD-N] Warning: Failed to manage logging config file: $loggingCfgPath"
}

try {
    $publishedDir = Publish-SRPSSDirectory `
        -SourcePath $PackageDir `
        -TargetPath $DistributionDir `
        -ReleaseRoot $ReleaseRoot `
        -RequiredRelativePaths @($primaryArtifact.Name)
    $primaryArtifact = Get-Item -LiteralPath (Join-Path $publishedDir $primaryArtifact.Name)

    foreach ($legacyPath in @(
        (Join-Path $ReleaseRoot "$AppName.exe"),
        (Join-Path $ReleaseRoot "$AppName.scr"),
        (Join-Path $ReleaseRoot "$AppName.logging.cfg"),
        (Join-Path $ReleaseRoot 'main.build'),
        (Join-Path $ReleaseRoot 'main.dist'),
        (Join-Path $ReleaseRoot 'main.onefile-build')
    )) {
        Remove-SRPSSLegacyReleasePath -Path $legacyPath -ReleaseRoot $ReleaseRoot
    }
} catch {
    Write-Host "[BUILD-N] Error: failed to publish screensaver payload - $($_.Exception.Message)"
    exit 1
}

try {
    Remove-SRPSSBuildDirectory -Path $BuildDir -BuildRoot $BuildRoot
    Write-Host "[BUILD-N] Cleaned build directory: $BuildDir"
} catch {
    Write-Host "[BUILD-N] Warning: Failed to delete build directory $BuildDir - $_"
}

Write-Host "[BUILD-N] Build success: $($primaryArtifact.FullName)"
Write-Host "[BUILD-N] Release directory: $DistributionDir"
Write-Host "[BUILD-N] Log: $LogFile"
