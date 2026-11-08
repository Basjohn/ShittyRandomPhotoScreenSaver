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
      Auto (default)     - Dispatch when GitHub already knows the workflow (its file is
                           on the default branch), otherwise Tag; the choice is printed.
      Dispatch           - `gh workflow run`; GitHub allows this only once the
                           workflow file is on the default branch. Inputs (commit,
                           token) are sent only with -Commit; without it the dispatch
                           carries none (a branch whose workflow predates them accepts
                           it) and the run is found by its commit and start time.
      Tag                - pushes a temporary tag linux-build/<timestamp> at the
                           branch's pushed commit (works before the workflow is
                           merged) and deletes it after the run.

.EXAMPLE
    .\scripts\linux\build_from_windows.ps1
    -Commit <sha> builds exactly that pushed commit (it must be on origin/<Branch>): Dispatch passes it to the
    workflow, which checks it out and verifies it; Tag tags it. Build Runner's GitHub Remote tab passes the commit
    its pre-flight fixed, so the Linux build is the same commit as the Windows builds.

.EXAMPLE
    .\scripts\linux\build_from_windows.ps1 -Branch claude/eager-carson-5da6ge -Mode Tag
.EXAMPLE
    .\scripts\linux\build_from_windows.ps1 -Branch main -Commit 0123456789abcdef0123456789abcdef01234567
#>
[CmdletBinding()]
param(
    [string]$Branch = '',
    [ValidateSet('Auto', 'Dispatch', 'Tag')][string]$Mode = 'Auto',
    [string]$OutDir = '',
    [string]$Commit = ''
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
    if ($Commit) {
        if ($Commit -notmatch '^[0-9a-f]{40}$') { throw "-Commit must be a full 40-character SHA: $Commit" }
        & git merge-base --is-ancestor $Commit "origin/$Branch" 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Commit $Commit is not on origin/$Branch (push it first)" }
        $remoteSha = $Commit
        Write-Host "[LINUX-BUILD] Building the requested commit $Commit"
    } elseif ($currentBranch -eq $Branch -and $localSha -ne $remoteSha) {
        Write-Warning "Local $Branch ($localSha) differs from origin/$Branch ($remoteSha); GitHub builds the pushed commit."
    }

    if ($Mode -eq 'Auto') {
        & gh workflow view $Workflow *> $null
        if ($LASTEXITCODE -eq 0) {
            $Mode = 'Dispatch'
        } else {
            Write-Warning "[LINUX-BUILD] $Workflow is not on the default branch yet; using a temporary linux-build/* tag instead of dispatch."
            $Mode = 'Tag'
        }
    }

    $started = (Get-Date).ToUniversalTime().AddSeconds(-5)
    $tag = $null
    $token = $null
    if ($Mode -eq 'Dispatch') {
        if ($Commit) {
            # The Remote tab's pinned commit: the workflow checks it out and verifies it, and the token names the
            # run (the workflow's run-name), so exactly this dispatch is followed. Only with -Commit: GitHub refuses
            # a dispatch whose inputs the ref's linux-build.yml does not declare (HTTP 422), so a branch cut before
            # the inputs existed keeps the plain dispatch below on the other tabs.
            $token = 'srpss-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff')
            Write-Host "[LINUX-BUILD] Dispatching $Workflow on $Branch at $remoteSha (run token $token)"
            Invoke-Checked gh @('workflow', 'run', $Workflow, '--ref', $Branch, '-f', "commit=$remoteSha",
                '-f', "token=$token") | Out-Null
        } else {
            Write-Host "[LINUX-BUILD] Dispatching $Workflow on $Branch at $remoteSha"
            Invoke-Checked gh @('workflow', 'run', $Workflow, '--ref', $Branch) | Out-Null
        }
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
        if ($token) {
            $runs = Invoke-Checked gh @('run', 'list', '--workflow', $Workflow, '--event', $runEvent,
                '--limit', '20', '--json', 'databaseId,displayTitle') | ConvertFrom-Json
            $runId = ($runs | Where-Object { $_.displayTitle -like "*$token*" } | Select-Object -First 1).databaseId
        } else {
            $runs = Invoke-Checked gh @('run', 'list', '--workflow', $Workflow, '--commit', $remoteSha, '--event', $runEvent,
                '--limit', '5', '--json', 'databaseId,createdAt') | ConvertFrom-Json
            $runId = ($runs | Where-Object { [datetime]$_.createdAt -ge $started } | Select-Object -First 1).databaseId
        }
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
