<#
Compatibility entry point; the canonical 3.14 x64/GIL Nuitka compile path is
scripts/venv/build_nuitka.ps1. Do not reintroduce global Python builds.
#>
[CmdletBinding()]
param(
    [string]$EntryPoint = 'main.py',
    [string]$AppName = 'SRPSS',
    [switch]$Console,
    [switch]$KeepExe
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$worker = Join-Path $PSScriptRoot 'venv\build_nuitka.ps1'
& $worker -EntryPoint $EntryPoint -AppName $AppName -Console:$Console -KeepExe:$KeepExe -BuildWorkspace normal
if (-not $?) { throw 'Canonical SRPSS Nuitka build worker failed.' }
