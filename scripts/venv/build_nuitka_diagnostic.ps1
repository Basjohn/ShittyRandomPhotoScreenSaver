<#
Dedicated repo-venv build worker for the installable SRPSS diagnostic runtime.

The ordinary standard and Media Center workers remain diagnostics-free.  This
thin worker reuses the canonical onefile compiler pipeline with isolated build,
release, cache, log, product, and entry-point identities.
#>

[CmdletBinding()]
param(
    [switch]$Console,
    [switch]$ReinstallVenvDeps
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Worker = Join-Path $PSScriptRoot 'build_nuitka.ps1'
if (-not (Test-Path -LiteralPath $Worker -PathType Leaf)) {
    throw "Canonical venv onefile worker not found: $Worker"
}

& $Worker `
    -EntryPoint 'main_diagnostic.py' `
    -AppName 'SRPSS_Diagnostic' `
    -Console:$Console `
    -SkipScrRename `
    -ReinstallVenvDeps:$ReinstallVenvDeps `
    -BuildTarget 'diagnostic' `
    -DistributionName 'diagnostic' `
    -LogStem 'build_nuitka_diagnostic' `
    -OnefileCacheName 'diagnostic-onefile' `
    -ProductNameOverride 'SRPSS Diagnostic' `
    -DescriptionOverride 'SRPSS Diagnostic Runtime'

exit $LASTEXITCODE
