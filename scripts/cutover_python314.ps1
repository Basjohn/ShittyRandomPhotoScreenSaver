<#
SRPSS destructive CPython 3.14 x64 cutover. Uses the already-installed
Python Install Manager (or a compatible legacy 3.14 installation). Removes the old repository .venv (NO BACKUP),
installs pinned dependencies, validates native ABI and optionally uninstalls 3.11.
Run only after importing the latest superseding full Godzip.
#>
[CmdletBinding()]
param(
    [switch]$UninstallPython311
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
. (Join-Path $PSScriptRoot 'python314_runtime.ps1')
$PythonExe = Resolve-BasePython
$VenvPath = Join-Path $Root '.venv'
$VenvPython = Join-Path $VenvPath 'Scripts\python.exe'

function Assert-NativeExit($Label) {
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit code $LASTEXITCODE)." }
}
function Assert-Python314($Exe) {
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { throw "Python executable not found: $Exe" }
    & $Exe -c "import sys,struct; assert sys.version_info[:2]==(3,14),sys.version; assert struct.calcsize('P')==8; assert sys._is_gil_enabled(); print(sys.executable, sys.version.split()[0], 'x64, GIL=on')"
    Assert-NativeExit 'Python 3.14.8 x64 / GIL check'
}

Assert-Python314 $PythonExe
Set-Location $Root
if (Test-Path -LiteralPath $VenvPath) {
    Write-Host '[PY314] Deleting existing .venv (no backup).'
    Remove-Item -LiteralPath $VenvPath -Recurse -Force
}
& $PythonExe -m venv $VenvPath
Assert-NativeExit 'Fresh venv creation'
& $VenvPython -m pip install --upgrade pip
Assert-NativeExit 'pip upgrade'
& $VenvPython -m pip install -r (Join-Path $Root 'requirements.txt')
Assert-NativeExit 'Canonical dependencies'
& $VenvPython -m pip install -r (Join-Path $Root 'build_deps\requirements_helper.txt')
Assert-NativeExit 'Helper dependencies'
& $VenvPython -m pip check
Assert-NativeExit 'pip check'
& $VenvPython (Join-Path $Root 'tools\python314_probe.py')
Assert-NativeExit 'SRPSS 3.14 native runtime probe'

# Match the worker's requirements stamp so first real build need not reinstall all wheels.
$venvVer = (& $VenvPython -c 'import sys; print(sys.version.split()[0])').Trim()
$reqPath = Join-Path $Root 'requirements.txt'
$reqHash = (Get-FileHash -LiteralPath $reqPath -Algorithm SHA256).Hash
@("python=$venvVer", "requirements_sha256=$reqHash", "requirements_path=$reqPath") -join "`n" |
    Out-File -LiteralPath (Join-Path $VenvPath '.srpss_requirements_stamp.txt') -Encoding utf8 -Force

if ($UninstallPython311) {
    # Uninstall is idempotent; 3.11 may have been removed before this script.
    $uninstallRoots = @(
        'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $installed311 = @(Get-ItemProperty -Path $uninstallRoots -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -match '^Python 3\.11(?:\.|\s|$)' })
    if ($installed311.Count -eq 0) {
        Write-Host '[PY314] Python 3.11 is already absent from Windows uninstall registrations; no action required.'
    } else {
        Write-Host '[PY314] Attempting registered uninstall of Python 3.11 using winget.'
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if ($null -eq $winget) { throw 'winget is missing: uninstall Python 3.11 through Windows Installed Apps.' }
        & $winget.Source uninstall --id Python.Python.3.11 -e --silent --disable-interactivity
        Assert-NativeExit 'Python 3.11 registered uninstall'
    }
}
Write-Host '[PY314] Canonical 3.14 environment prepared. Windows Qt/full-suite/frozen product acceptance still required.'
