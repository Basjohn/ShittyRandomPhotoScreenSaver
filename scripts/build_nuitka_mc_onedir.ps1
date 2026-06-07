<# 
Build script for Nuitka (one-dir) MC variant intended to avoid self-extracting stubs.

Persistent venv version:
- Creates/reuses project-local .venv
- Installs requirements.txt + Nuitka inside .venv only
- Runs all Python/Nuitka/versioning commands through .venv\Scripts\python.exe
- Does not install project packages globally
- Compiles main_mc.py into SRPSS_Media_Center.exe plus dependency folder
- Designed to reduce AV heuristics compared to --onefile bundles

Usage:
powershell -ExecutionPolicy Bypass -File .\scripts\build_nuitka_mc_onedir.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build_nuitka_mc_onedir.ps1 -Console
powershell -ExecutionPolicy Bypass -File .\scripts\build_nuitka_mc_onedir.ps1 -ReinstallVenvDeps
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
    Write-Host "[BUILD-N-ONEDIR] Locating Python 3.11..."

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
                Write-Host "[BUILD-N-ONEDIR] Using base Python: $candidate"
                return $candidate
            }
        } catch {}
    }

    throw "Python 3.11 was not found. Install Python 3.11 x64, then rerun this script."
}

function Ensure-BuildVenv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Root,

        [switch]$ForceReinstallDeps
    )

    $VenvDir = Join-Path $Root ".venv"
    $VenvPython = Join-Path $VenvDir "Scripts\python.exe"
    $RequirementsPath = Join-Path $Root "requirements.txt"
    $StampPath = Join-Path $VenvDir ".srpss_build_deps_stamp.txt"

    if (-not (Test-Path $VenvPython)) {
        $BasePython = Resolve-BasePython
        Write-Host "[BUILD-N-ONEDIR] Creating persistent venv: $VenvDir"
        & $BasePython -m venv $VenvDir
    }

    if (-not (Test-Path $VenvPython)) {
        throw "Venv Python was not created correctly: $VenvPython"
    }

    $venvVersion = Get-PythonVersionText -PythonExe $VenvPython
    if (-not $venvVersion.StartsWith("3.11.")) {
        throw "Existing .venv is Python $venvVersion, but this project build expects Python 3.11. Delete .venv and rerun."
    }

    Write-Host "[BUILD-N-ONEDIR] Using venv Python: $VenvPython"
    Write-Host "[BUILD-N-ONEDIR] Venv Python version: $venvVersion"

    if (-not (Test-Path $RequirementsPath)) {
        throw "requirements.txt not found: $RequirementsPath"
    }

    $requirementsHash = Get-FileSha256 -Path $RequirementsPath
    $desiredStamp = @(
        "python=$venvVersion"
        "requirements_sha256=$requirementsHash"
        "requires_nuitka=true"
    ) -join "`n"

    $existingStamp = ""
    if (Test-Path $StampPath) {
        $existingStamp = Get-Content $StampPath -Raw -ErrorAction SilentlyContinue
    }

    $nuitkaAvailable = $false
    try {
        $nuitkaVersion = (& $VenvPython -m nuitka --version 2>$null)
        if ($nuitkaVersion) {
            $nuitkaAvailable = $true
        }
    } catch {
        $nuitkaAvailable = $false
    }

    $needsDeps = $ForceReinstallDeps -or (-not $nuitkaAvailable) -or ($existingStamp.Trim() -ne $desiredStamp.Trim())

    if ($needsDeps) {
        Write-Host "[BUILD-N-ONEDIR] Installing/updating venv build dependencies..."
        & $VenvPython -m pip install --upgrade pip
        & $VenvPython -m pip install -r $RequirementsPath
        & $VenvPython -m pip install nuitka
        $desiredStamp | Out-File -FilePath $StampPath -Encoding utf8 -Force
    } else {
        Write-Host "[BUILD-N-ONEDIR] Venv dependencies look current; skipping pip install."
    }

    $finalNuitkaVersion = (& $VenvPython -m nuitka --version)
    Write-Host "[BUILD-N-ONEDIR] Nuitka $finalNuitkaVersion"

    return $VenvPython
}

Set-ScriptWindowMinimized -Disable:$Console

# Paths
$Root = Resolve-Path (Join-Path $PSScriptRoot '..')
$Root = $Root.Path

$BuildDir = Join-Path $Root 'build_nuitka_mc_onedir'
$ReleaseDir = Join-Path $Root 'release'
$LogDir = Join-Path $Root 'logs'
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir ("build_nuitka_mc_onedir_{0}.log" -f $Timestamp)
$MaxLogFiles = 10

# Ensure dirs.
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

# Rotate old MC one-dir build logs.
$existingLogs = @(Get-ChildItem -Path $LogDir -Filter "build_nuitka_mc_onedir_*.log" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending)
if ($existingLogs.Count -ge $MaxLogFiles) {
    $logsToRemove = $existingLogs | Select-Object -Skip ($MaxLogFiles - 1)
    foreach ($log in $logsToRemove) {
        try {
            Remove-Item -Force $log.FullName
        } catch {}
    }
}

# Create/reuse venv and install dependencies there only.
$VenvPython = Ensure-BuildVenv -Root $Root -ForceReinstallDeps:$ReinstallVenvDeps

# Detect icon in project root, preferring SRPSS.ico when present.
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

# Retrieve version/metadata from central versioning module, if available.
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

    if ($Version) {
        Write-Host "[BUILD-N-ONEDIR] Version: $Version"
    } else {
        Write-Host "[BUILD-N-ONEDIR] Version: (unknown - versioning.py missing APP_VERSION)"
    }
} catch {
    Write-Host "[BUILD-N-ONEDIR] Version/metadata: (unavailable - versioning.py not accessible)"
}

# Compose arguments for Nuitka.
$EntryPath = Join-Path $Root $EntryPoint
if (-not (Test-Path $EntryPath)) {
    throw "Entry point not found: $EntryPath"
}

if ($Console) {
    if ($AppName -eq "SRPSS_Media_Center") {
        $AppName = "SRPSS_Media_Center_debug"
    }
}

$consoleArg = "--windows-console-mode=disable"
if ($Console) {
    $consoleArg = "--windows-console-mode=force"
}

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
Write-Host ("`"$VenvPython`" " + ($argsList -join ' '))

Push-Location $Root
try {
    & $VenvPython @argsList *>&1 | Tee-Object -FilePath $LogFile
} finally {
    Pop-Location
}

# Verify outputs.
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
        if (Test-Path $loggingCfgPath) {
            Remove-Item -Force -Path $loggingCfgPath -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-Host "[BUILD-N-ONEDIR] Warning: Failed to manage logging config file: $loggingCfgPath"
}

# Clean up intermediate Nuitka build folder now that the bundle is ready.
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
Write-Host "[BUILD-N-ONEDIR] Persistent venv: $(Join-Path $Root '.venv')"
