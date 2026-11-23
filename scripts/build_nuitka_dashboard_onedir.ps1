<#
Compatibility entry point; single authoritative 3.14/GIL MSVC worker performs
full QML/asset validation and forbidden frozen-payload verification.
#>
[CmdletBinding()]
param(
    [string]$EntryPoint = 'main_dashboard.py',
    [string]$AppName = 'SRPSS_Dashboard',
    [switch]$Console
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$worker = Join-Path $PSScriptRoot 'venv\build_nuitka_dashboard_onedir.ps1'
& $worker -EntryPoint $EntryPoint -AppName $AppName -Console:$Console -BuildWorkspace normal
if (-not $?) { throw 'Canonical SRPSS Dashboard worker failed.' }
