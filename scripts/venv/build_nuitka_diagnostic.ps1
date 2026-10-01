<#
Dedicated repo-venv build worker for the published SRPSS diagnostic runtime.

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

# Diagnostic is deliberately always console-enabled. If the frozen runtime
# fails before ordinary logging/crash capture comes up, the console is the last
# available human-visible failure surface. The optional -Console switch remains
# accepted for backwards-compatible invocations but no longer controls this.
& $Worker `
    -EntryPoint 'main_diagnostic.py' `
    -AppName 'SRPSS_Diagnostic' `
    -Console `
    -ReinstallVenvDeps:$ReinstallVenvDeps `
    -BuildTarget 'diagnostic' `
    -DistributionName 'diagnostic' `
    -LogStem 'build_nuitka_diagnostic' `
    -OnefileCacheName 'diagnostic-onefile' `
    -ProductNameOverride 'SRPSS Diagnostic' `
    -DescriptionOverride 'SRPSS Diagnostic Runtime'

exit $LASTEXITCODE
