<# Compatibility entry point. The repo-root Python 3.14 .venv owns the helper. #>
[CmdletBinding()]
param(
    [string]$EntryPoint = 'helpers/reddit_helper_worker.py',
    [string]$AppName = 'SRPSS_RedditHelper',
    [switch]$Console,
    [switch]$ReinstallVenvDeps
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$worker = Join-Path $PSScriptRoot 'venv\build_reddit_helper.ps1'
& $worker -EntryPoint $EntryPoint -AppName $AppName -Console:$Console -ReinstallVenvDeps:$ReinstallVenvDeps -BuildWorkspace normal
if (-not $?) { throw 'Canonical SRPSS Reddit helper worker failed.' }
