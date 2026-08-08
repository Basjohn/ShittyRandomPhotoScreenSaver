<# 
Experimental venv build script for SRPSS Media Center one-dir build.

Intended location:
  scripts\venv\build_nuitka_mc_onedir.ps1

Creates/reuses:
  .venv (repo root)

Uses repo-root:
  requirements.txt

Does not touch the legacy scripts in:
  scripts\build_nuitka_mc_onedir.ps1
#>

[CmdletBinding()]
param(
    [string]$EntryPoint = "main_mc.py",
    [string]$AppName = "SRPSS_Media_Center",
    [switch]$Console,
    [switch]$ReinstallVenvDeps
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
        if ($handle -ne [IntPtr]::Zero) {
            [void][SRPSS.NativeConsole]::ShowWindowAsync($handle, 2)
        }
    } catch {}
}

function Get-FileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path $Path)) { return "" }
    return (Get-FileHash -Path $Path -Algorithm SHA256).Hash
}

function Get-PythonVersionText {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    return (& $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null).Trim()
}

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments 2>&1 | ForEach-Object { Write-Host $_ }

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE`: $FilePath $($Arguments -join ' ')"
    }
}

function Resolve-BasePython {
    Write-Host "[BUILD-VENV] Locating Python 3.11..."

    $candidates = @()

    try {
        $py311 = (& py -3.11 -c "import sys; print(sys.executable)" 2>$null).Trim()
        if ($py311) { $candidates += $py311 }
    } catch {}

    try {
        $pyDefault = (& python -c "import sys; print(sys.executable)" 2>$null).Trim()
        if ($pyDefault) { $candidates += $pyDefault }
    } catch {}

    $candidates = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -Unique

    foreach ($candidate in $candidates) {
        try {
            $version = (& $candidate -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null).Trim()
            if ($version -eq "3.11") {
                Write-Host "[BUILD-VENV] Using base Python: $candidate"
                return $candidate
            }
        } catch {}
    }

    throw "Python 3.11 was not found. Install Python 3.11 x64, then rerun this script."
}

function Ensure-ProjectVenv {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [switch]$ForceReinstallDeps
    )

    $VenvDir = Join-Path $RepoRoot ".venv"
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    $RequirementsPath = Join-Path $RepoRoot "requirements.txt"
    $StampPath = Join-Path $VenvDir ".srpss_requirements_stamp.txt"

    if (-not (Test-Path $RequirementsPath)) {
        throw "requirements.txt not found: $RequirementsPath"
    }

    if (-not (Test-Path $VenvPython)) {
        if (Test-Path $VenvDir) {
            Write-Host "[BUILD-VENV] Existing venv folder is incomplete; deleting: $VenvDir"
            Remove-Item -Recurse -Force $VenvDir
        }

        $BasePython = Resolve-BasePython
        Write-Host "[BUILD-VENV] Creating venv: $VenvDir"
        Invoke-NativeChecked $BasePython "-m" "venv" $VenvDir
    }

    if (-not (Test-Path $VenvPython)) {
        throw "Venv Python was not created correctly: $VenvPython"
    }

    $venvVersion = Get-PythonVersionText -PythonExe $VenvPython
    if (-not $venvVersion.StartsWith("3.11.")) {
        throw "Existing repo-root .venv is Python $venvVersion, but SRPSS expects Python 3.11. Delete .venv and rerun."
    }

    Write-Host "[BUILD-VENV] Using venv Python: $VenvPython"
    Write-Host "[BUILD-VENV] Venv Python version: $venvVersion"

    $requirementsHash = Get-FileSha256 -Path $RequirementsPath
    $desiredStamp = @(
        "python=$venvVersion"
        "requirements_sha256=$requirementsHash"
        "requirements_path=$RequirementsPath"
    ) -join "`n"

    $existingStamp = ""
    if (Test-Path $StampPath) {
        $existingStamp = Get-Content $StampPath -Raw -ErrorAction SilentlyContinue
    }

    $nuitkaAvailable = $false
    try {
        $null = & $VenvPython -m pip show nuitka 2>$null
        if ($LASTEXITCODE -eq 0) { $nuitkaAvailable = $true }
    } catch {
        $nuitkaAvailable = $false
    }

    $needsDeps = $ForceReinstallDeps -or (-not $nuitkaAvailable) -or ($existingStamp.Trim() -ne $desiredStamp.Trim())

    if ($needsDeps) {
        Write-Host "[BUILD-VENV] Installing/updating dependencies from: $RequirementsPath"
        Invoke-NativeChecked $VenvPython "-m" "pip" "install" "--upgrade" "pip"
        Invoke-NativeChecked $VenvPython "-m" "pip" "install" "-r" $RequirementsPath
        $desiredStamp | Out-File -FilePath $StampPath -Encoding utf8 -Force
    } else {
        Write-Host "[BUILD-VENV] Dependencies look current; skipping pip install."
    }

    Write-Host "[BUILD-VENV] Checking Nuitka version..."
    Invoke-NativeChecked $VenvPython "-m" "nuitka" "--version"

    return $VenvPython
}

function Rotate-Logs {
    param(
        [Parameter(Mandatory = $true)][string]$LogDir,
        [Parameter(Mandatory = $true)][string]$Filter,
        [int]$MaxLogFiles = 10
    )

    $existingLogs = @(Get-ChildItem -Path $LogDir -Filter $Filter -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
    if ($existingLogs.Count -ge $MaxLogFiles) {
        $logsToRemove = $existingLogs | Select-Object -Skip ($MaxLogFiles - 1)
        foreach ($log in $logsToRemove) {
            try { Remove-Item -Force $log.FullName } catch {}
        }
    }
}


Set-ScriptWindowMinimized -Disable:$Console

$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$Root = $Root.Path

$VenvDir = Join-Path $Root '.venv'
$VenvPython = Ensure-ProjectVenv -RepoRoot $Root -ForceReinstallDeps:$ReinstallVenvDeps

$BuildRoot = Join-Path $Root 'build'
$BuildDir = Join-Path $BuildRoot 'venv\media_center'
$BuildOutputDir = Join-Path $BuildDir 'output'
$ReleaseRoot = Join-Path $Root 'release'
$DistributionDir = Join-Path $ReleaseRoot 'media_center'
$LogDir = Join-Path $Root 'logs'
$BuildLayoutScript = Join-Path $Root 'tools\build_layout.ps1'
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir ("build_nuitka_mc_onedir_{0}.log" -f $Timestamp)

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
Rotate-Logs -LogDir $LogDir -Filter "build_nuitka_mc_onedir_*.log"

$Icon = $null
$PreferredIcon = Join-Path $Root 'SRPSS.ico'
if (Test-Path $PreferredIcon) {
    $Icon = Get-Item $PreferredIcon
} else {
    $Icon = Get-ChildItem -Path $Root -Filter *.ico -File -ErrorAction SilentlyContinue | Select-Object -First 1
}
if ($Icon) { Write-Host "[BUILD-VENV] Using icon: $($Icon.FullName)" }

$Version = ""
$Company = ""
$Description = ""
$ProductName = ""

try {
    Push-Location $Root
    try {
        $RawInfo = & $VenvPython -c "from versioning import APP_VERSION, APP_COMPANY, APP_DESCRIPTION, APP_NAME; print('||'.join((APP_VERSION, APP_COMPANY, APP_DESCRIPTION, APP_NAME)))"
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

    if ($Version) { Write-Host "[BUILD-VENV] Version: $Version" } else { Write-Host "[BUILD-VENV] Version: (unknown)" }
} catch {
    Write-Host "[BUILD-VENV] Version/metadata unavailable: $($_.Exception.Message)"
}

if (-not $ProductName) { $ProductName = "SRPSS - Media Center" }
if (-not $Description) { $Description = "ShittyRandomPhotoScreenSaver Media Center" }

$EntryPath = Join-Path $Root $EntryPoint
if (-not (Test-Path $EntryPath)) { throw "Entry point not found: $EntryPath" }

if ($Console) {
    if ($AppName -eq "SRPSS_Media_Center") { $AppName = "SRPSS_Media_Center_debug" }
}

$consoleArg = "--windows-console-mode=disable"
if ($Console) { $consoleArg = "--windows-console-mode=force" }

$argsList = @(
    "-m", "nuitka",
    "--mingw64",
    "--standalone",
    "--remove-output",
    "--output-dir=$BuildOutputDir",
    "--output-filename=$AppName",
    $consoleArg,
    "--enable-plugin=pyside6",
    "--include-data-dir=presets=presets",
    "--include-data-dir=themes=themes",
    "--include-data-dir=images=images",
    "--include-data-files=resources/tutuogg.ogg=resources/tutuogg.ogg",
    "--include-data-dir=widgets/spotify_visualizer/shaders=widgets/spotify_visualizer/shaders",
    "--include-package=ui.tabs",
    "--include-package=widgets.spotify_visualizer",
    "--include-package=widgets.spotify_visualizer.renderers",
    "--include-package=rendering.gl_programs",
    "--include-package=rendering.gl_compositor_pkg",
    "--include-package=pyaudiowpatch",
    "--include-package=sounddevice",
    "--include-qt-plugins=multimedia",
    "--include-module=PySide6.QtMultimedia",
    "--include-module=winrt.windows.media.control",
    "--include-module=winrt.windows.storage.streams",
    "--include-module=winrt.windows.foundation",
    "--include-module=winrt.windows.foundation.collections",
    "--noinclude-default-mode=error"
)

if ($Icon) { $argsList += @("--windows-icon-from-ico=$($Icon.FullName)") }
if ($Version) {
    $argsList += "--product-version=$Version"
    $argsList += "--file-version=$Version"
}
if ($Company) { $argsList += "--company-name=$Company" }
if ($Description) { $argsList += "--file-description=$Description" }
if ($ProductName) { $argsList += "--product-name=$ProductName" }

$argsList += $EntryPath

Write-Host "[BUILD-VENV] Starting Nuitka..."
Write-Host ("`"$VenvPython`" " + ($argsList -join ' '))

$CompilerTempDir = Join-Path $BuildDir 'compiler-temp'
New-Item -ItemType Directory -Force -Path $CompilerTempDir | Out-Null

# Keep GCC/ld response files out of C:\WINDOWS\TEMP. This is deliberately
# local to the worker so it does not depend on a newer build_layout.ps1.
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
Write-Host "[BUILD-VENV] Compiler temporary directory: $CompilerTempDir"

$BuildExit = 1
try {
    Push-Location $Root
    try {
        & $VenvPython @argsList *>&1 | Tee-Object -FilePath $LogFile
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
    Write-Host "[BUILD-VENV] Build failed with exit code $BuildExit. See log: $LogFile"
    exit $BuildExit
}

$Exe = Get-ChildItem -Path $BuildOutputDir -Recurse -Filter "$AppName.exe" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $Exe) {
    Write-Host "[BUILD-VENV] Build failed or no executable produced. See log: $LogFile"
    exit 1
}

# Validate the onedir payload against the current source shader set.
try {
    $PackagedShaders = @(
        Assert-SRPSSOnedirVisualizerShaders `
            -RepoRoot $Root `
            -DistributionRoot $Exe.DirectoryName
    )
    Write-Host "[BUILD-VENV] Visualizer shaders present in onedir payload: $($PackagedShaders -join ', ')"
} catch {
    Write-Host "[BUILD-VENV] Shader payload validation failed - $($_.Exception.Message)"
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
    Write-Host "[BUILD-VENV] Warning: Failed to manage logging config file: $loggingCfgPath"
}

try {
    $publishedDir = Publish-SRPSSDirectory `
        -SourcePath $Exe.DirectoryName `
        -TargetPath $DistributionDir `
        -ReleaseRoot $ReleaseRoot `
        -RequiredRelativePaths @("$AppName.exe")
    $Exe = Get-Item -LiteralPath (Join-Path $publishedDir "$AppName.exe")

    foreach ($legacyPath in @(
        (Join-Path $ReleaseRoot 'main_mc.build'),
        (Join-Path $ReleaseRoot 'main_mc.dist')
    )) {
        Remove-SRPSSLegacyReleasePath -Path $legacyPath -ReleaseRoot $ReleaseRoot
    }
} catch {
    Write-Host "[BUILD-VENV] Error: failed to publish Media Center payload - $($_.Exception.Message)"
    exit 1
}

try {
    Remove-SRPSSBuildDirectory -Path $BuildDir -BuildRoot $BuildRoot
    Write-Host "[BUILD-VENV] Cleaned build directory: $BuildDir"
} catch {
    Write-Host "[BUILD-VENV] Warning: Failed to delete build directory $BuildDir - $_"
}

Write-Host "[BUILD-VENV] Build success (one-dir root): $($Exe.DirectoryName)"
Write-Host "[BUILD-VENV] Release directory: $DistributionDir"
Write-Host "[BUILD-VENV] Log: $LogFile"
Write-Host "[BUILD-VENV] Venv: $VenvDir"
