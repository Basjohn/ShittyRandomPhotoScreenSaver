<#
The native core's frozen probe (Current_Plan.md item 8b, N2.1): a separate Nuitka standalone build of
native\core\python\frozen_probe.py with the product's Qt includes and the shared QML prune
(tools\build_layout.ps1), carrying the module the product build placed in release\native_module\ as
rendering.native._srpss_native_core (where the product will load it from). The probe executable is then run and its
JSON report must say ok. The product itself is not touched: nothing in it imports the module yet.

Run by .github/workflows/windows-build.yml after the product worker and `github_remote_build.py place-native`, on
GitHub's runner only (frozen builds are GitHub's; never on this machine). Uses the repo-root .venv the worker made.

  build_native_core_probe.ps1 -Report logs\native_core_frozen_probe_<token>.json
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Report
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) { throw "The repo-root venv is missing: $VenvPython" }
. (Join-Path $Root 'tools\build_layout.ps1')

$ModuleName = '_srpss_native_core'
$Module = Join-Path $Root "release\native_module\$ModuleName.pyd"
if (-not (Test-Path -LiteralPath $Module -PathType Leaf)) {
    throw "The product build placed no native core at $Module (github_remote_build.py place-native)"
}
$PackageCopy = Join-Path $Root "rendering\native\$ModuleName.pyd"
$Entry = Join-Path $Root 'native\core\python\frozen_probe.py'
$BuildDir = Join-Path $Root 'build\native_core_probe'
$AppName = 'SRPSS_NativeCoreProbe'
$ReportPath = if ([System.IO.Path]::IsPathRooted($Report)) { $Report } else { Join-Path $Root $Report }

# The product's Qt includes (scripts\venv\build_nuitka.ps1) that bear on the module's Qt binding, and the shared prune.
$argsList = @(
    '-m', 'nuitka',
    '--msvc=latest',
    '--assume-yes-for-downloads',
    '--jobs=4',
    '--standalone',
    '--remove-output',
    '--windows-console-mode=force',
    "--output-dir=$BuildDir",
    "--output-filename=$AppName",
    '--enable-plugin=pyside6',
    '--include-qt-plugins=qml',
    '--include-module=PySide6.QtQuick',
    '--include-module=PySide6.QtOpenGL',
    '--include-module=PySide6.QtQml',
    '--include-package=rendering.native',
    "--include-module=rendering.native.$ModuleName"
)
$argsList += @(Get-SRPSSNuitkaQmlPruneArguments -RepoRoot $Root)
$argsList += $Entry

if (Test-Path -LiteralPath $BuildDir) { Remove-Item -LiteralPath $BuildDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $ReportPath) | Out-Null
Copy-Item -LiteralPath $Module -Destination $PackageCopy -Force
try {
    Push-Location $Root
    try {
        Write-Host "[NATIVE-PROBE] Freezing $Entry with the product's Qt includes and QML prune"
        & $VenvPython @argsList
        if ($LASTEXITCODE -ne 0) { throw "Nuitka failed with exit code $LASTEXITCODE" }
    } finally {
        Pop-Location
    }
} finally {
    Remove-Item -LiteralPath $PackageCopy -Force -ErrorAction SilentlyContinue
}

$Exe = Get-ChildItem -Path $BuildDir -Recurse -Filter "$AppName.exe" -File | Select-Object -First 1
if (-not $Exe) { throw "The probe build produced no $AppName.exe under $BuildDir" }
$Carried = Get-ChildItem -Path $Exe.DirectoryName -Recurse -Filter "$ModuleName*.pyd" -File | Select-Object -First 1
if (-not $Carried) { throw "The frozen probe build does not carry $ModuleName.pyd" }
Write-Host "[NATIVE-PROBE] Carried: $($Carried.FullName)"

& $Exe.FullName --out $ReportPath
$ProbeExit = $LASTEXITCODE
if (-not (Test-Path -LiteralPath $ReportPath -PathType Leaf)) { throw "The frozen probe wrote no report ($ProbeExit)" }
$Result = Get-Content -LiteralPath $ReportPath -Raw | ConvertFrom-Json
if ($ProbeExit -ne 0 -or $Result.ok -ne $true -or $Result.frozen -ne $true) {
    throw "The frozen probe failed (exit $ProbeExit): $($Result.checks | ConvertTo-Json -Compress)"
}
Write-Host "[NATIVE-PROBE] The frozen build loaded the native core: $ReportPath"
Remove-Item -LiteralPath $BuildDir -Recurse -Force -ErrorAction SilentlyContinue
