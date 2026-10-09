<#
Compatibility entry point; single authoritative 3.14/GIL MSVC worker performs
full QML/asset validation and forbidden frozen-payload verification.
#>
[CmdletBinding()]
param(
    [string]$EntryPoint = 'main_mc.py',
    [string]$AppName = 'SRPSS_Media_Center',
    [switch]$Console
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$worker = Join-Path $PSScriptRoot 'venv\build_nuitka_mc_onedir.ps1'
& $worker -EntryPoint $EntryPoint -AppName $AppName -Console:$Console -BuildWorkspace normal
if (-not $?) { throw 'Canonical SRPSS Media Center worker failed.' }
