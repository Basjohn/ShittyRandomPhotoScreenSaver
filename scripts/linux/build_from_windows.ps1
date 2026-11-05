<#
.SYNOPSIS
    Build the SRPSS Linux product from Windows without WSL, Hyper-V or Docker.

.DESCRIPTION
    The build runs on a GitHub-hosted Ubuntu runner (.github/workflows/linux-build.yml);
    this script triggers it for a pushed branch, follows it, and downloads the
    resulting SRPSS-<version>-linux-x86_64.tar.gz into -OutDir.

    Requirements: the GitHub CLI (`winget install GitHub.cli`, then `gh auth login`)
    and the branch pushed to GitHub. Nothing is built or virtualised locally.

    Trigger modes:
      Dispatch (default) - `gh workflow run`; GitHub allows this only once the
                           workflow file is on the default branch.
      Tag                - pushes a temporary tag linux-build/<timestamp> at the
                           branch's pushed commit (works before the workflow is
                           merged) and deletes it after the run.

.EXAMPLE
    .\scripts\linux\build_from_windows.ps1
.EXAMPLE
    .\scripts\linux\build_from_windows.ps1 -Branch claude/eager-carson-5da6ge -Mode Tag
#>
[CmdletBinding()]
param(
    [string]$Branch = '',
    [ValidateSet('Dispatch', 'Tag')][string]$Mode = 'Dispatch',
    [string]$OutDir = ''
)

$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
if (-not $OutDir) { $OutDir = Join-Path $Root 'release\linux' }
$Workflow = 'linux-build.yml'

function Invoke-Checked {
    param([string]$Exe, [string[]]$Arguments)
    $output = & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Exe $($Arguments -join ' ') failed with exit code $LASTEXITCODE" }
    return $output
}

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'GitHub CLI (gh) not found. Install it with: winget install GitHub.cli ; then run: gh auth login'
}
Invoke-Checked gh @('auth', 'status') | Out-Null

Push-Location $Root
try {
    if (-not $Branch) { $Branch = (Invoke-Checked git @('rev-parse', '--abbrev-ref', 'HEAD')).Trim() }
    Invoke-Checked git @('fetch', 'origin', $Branch) | Out-Null
    $remoteSha = (Invoke-Checked git @('rev-parse', "origin/$Branch")).Trim()
    $localSha = (Invoke-Checked git @('rev-parse', 'HEAD')).Trim()
    $currentBranch = (Invoke-Checked git @('rev-parse', '--abbrev-ref', 'HEAD')).Trim()
    if ($currentBranch -eq $Branch -and $localSha -ne $remoteSha) {
        Write-Warning "Local $Branch ($localSha) differs from origin/$Branch ($remoteSha); GitHub builds the pushed commit."
    }

    $started = (Get-Date).ToUniversalTime().AddSeconds(-5)
    $tag = $null
    if ($Mode -eq 'Dispatch') {
        Write-Host "[LINUX-BUILD] Dispatching $Workflow on $Branch"
        Invoke-Checked gh @('workflow', 'run', $Workflow, '--ref', $Branch) | Out-Null
        $runEvent = 'workflow_dispatch'
    } else {
        $tag = 'linux-build/' + (Get-Date -Format 'yyyyMMdd-HHmmss')
        Write-Host "[LINUX-BUILD] Pushing temporary tag $tag at origin/$Branch ($remoteSha)"
        Invoke-Checked git @('push', 'origin', "$($remoteSha):refs/tags/$tag") | Out-Null
        $runEvent = 'push'
    }

    Write-Host '[LINUX-BUILD] Waiting for the run to appear...'
    $runId = $null
    for ($attempt = 0; $attempt -lt 30 -and -not $runId; $attempt++) {
        Start-Sleep -Seconds 4
        $runs = Invoke-Checked gh @('run', 'list', '--workflow', $Workflow, '--commit', $remoteSha, '--event', $runEvent,
            '--limit', '5', '--json', 'databaseId,createdAt') | ConvertFrom-Json
        $runId = ($runs | Where-Object { [datetime]$_.createdAt -ge $started } | Select-Object -First 1).databaseId
    }
    if (-not $runId) { throw 'The workflow run did not appear. Check the Actions tab on GitHub.' }

    Write-Host "[LINUX-BUILD] Following run $runId (typically 30-60 minutes; Ctrl+C leaves it running on GitHub)"
    & gh run watch $runId --exit-status
    if ($LASTEXITCODE -ne 0) { throw "Linux build run $runId failed: gh run view $runId --log-failed" }

    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    Invoke-Checked gh @('run', 'download', $runId, '--name', 'srpss-linux', '--dir', $OutDir) | Out-Null
    Get-ChildItem -LiteralPath $OutDir -Filter '*.tar.gz' | ForEach-Object { Write-Host "[LINUX-BUILD] $($_.FullName)" }
    Write-Host '[LINUX-BUILD] On Linux: tar xzf <archive> && ./SRPSS-*/install.sh'
} finally {
    if ($tag) {
        & git push origin ":refs/tags/$tag" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning "Could not delete temporary tag $tag; remove it with: git push origin :refs/tags/$tag" }
    }
    Pop-Location
}
