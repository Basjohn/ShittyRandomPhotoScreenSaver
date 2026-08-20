<#
Build and optionally run the bounded Phase A Qt Quick render-node smoke.

This does not publish or install a product artifact. Output stays under the
repository's ignored build/a4_qtquick_smoke directory.
#>

[CmdletBinding()]
param(
    [switch]$Run,
    [ValidateRange(1, 2)]
    [int]$Windows = 1,
    [ValidateRange(100, 5000)]
    [int]$PhaseDelayMs = 400
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$EntryPath = Join-Path $Root 'tools\qtquick_render_node_smoke.py'
$QmlSource = Join-Path $Root 'rendering\quick\qml'
$BuildOutputDir = Join-Path $Root 'build\a4_qtquick_smoke'

if (-not (Test-Path -LiteralPath $EntryPath -PathType Leaf)) {
    throw "Qt Quick smoke entry point not found: $EntryPath"
}
if (-not (Test-Path -LiteralPath $QmlSource -PathType Container)) {
    throw "Qt Quick QML source root not found: $QmlSource"
}

$NuitkaArgs = @(
    '-m', 'nuitka',
    '--mingw64',
    '--jobs=2',
    '--standalone',
    '--remove-output',
    '--assume-yes-for-downloads',
    '--windows-console-mode=force',
    "--output-dir=$BuildOutputDir",
    '--output-filename=SRPSS_Quick_Smoke.exe',
    '--enable-plugin=pyside6',
    '--include-qt-plugins=qml',
    '--include-data-dir=rendering/quick/qml=rendering/quick/qml',
    '--include-package=rendering.quick',
    '--include-package=OpenGL',
    '--include-module=PySide6.QtQuick',
    '--include-module=PySide6.QtQml',
    '--noinclude-default-mode=error',
    $EntryPath
)

Push-Location $Root
try {
    Write-Host '[QUICK-A4] Compiling bounded Qt Quick smoke...'
    & python @NuitkaArgs
    $BuildExit = $LASTEXITCODE
    if ($BuildExit -ne 0) {
        throw "Qt Quick smoke compilation failed with exit code $BuildExit"
    }
}
finally {
    Pop-Location
}

$DistDir = Get-ChildItem -LiteralPath $BuildOutputDir -Directory -Filter '*.dist' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($null -eq $DistDir) {
    throw "Qt Quick smoke distribution directory missing under $BuildOutputDir"
}
$Executable = Join-Path $DistDir.FullName 'SRPSS_Quick_Smoke.exe'
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
    throw "Qt Quick smoke executable missing: $Executable"
}

Write-Host "[QUICK-A4] Built $Executable"
if ($Run) {
    Write-Host "[QUICK-A4] Running compiled smoke on $Windows window(s)..."
    & $Executable `
        '--windows' $Windows `
        '--size' '320x180' `
        '--phase-delay-ms' $PhaseDelayMs
    $SmokeExit = $LASTEXITCODE
    if ($SmokeExit -ne 0) {
        throw "Compiled Qt Quick smoke failed with exit code $SmokeExit"
    }
}

exit 0
