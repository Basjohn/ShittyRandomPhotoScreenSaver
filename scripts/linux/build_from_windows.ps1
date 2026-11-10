<#
.SYNOPSIS
    Build the SRPSS Linux product from Windows without WSL, Hyper-V or Docker.

.DESCRIPTION
    The build runs on a GitHub-hosted Ubuntu runner (.github/workflows/linux-build.yml);
    this script triggers it for a pushed branch, follows it, and downloads the
    resulting profile-specific tarball into -OutDir. -Profile mc builds main_mc.py; the
    default -Profile screensaver remains unchanged.

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
.EXAMPLE
    .\scripts\linux\build_from_windows.ps1 -Profile mc
#>
[CmdletBinding()]
param(
    [string]$Branch = '',
    [ValidateSet('Auto', 'Dispatch', 'Tag')][string]$Mode = 'Auto',
    [string]$OutDir = '',
    [string]$Commit = '',
    [ValidateSet('screensaver', 'mc')][string]$Profile = 'screensaver'
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
    $localSha = (Invoke-Checked git @('rev-parse', 'HEAD')).Trim()
    $currentBranch = (Invoke-Checked git @('rev-parse', '--abbrev-ref', 'HEAD')).Trim()
    if ($Commit) {
        # GitHub Remote already pinned and checked the pushed SHA. Avoid concurrent git fetch ref locks when
        # the user selects both Linux profiles; the two workers share this same checkout.
        if ($Commit -notmatch '^[0-9a-f]{40}$') { throw "-Commit must be a full 40-character SHA: $Commit" }
        & git cat-file -e "$Commit^{commit}" 2>$null
        if ($LASTEXITCODE -ne 0) { throw "Commit $Commit is not present locally" }
        $head = @(Invoke-Checked git @('ls-remote', '--heads', 'origin', $Branch))
        if (-not $head) { throw "origin/$Branch does not exist (push the branch first)" }
        $remoteSha = $Commit
        Write-Host "[LINUX-BUILD] Building the requested commit $Commit ($Profile)"
    } else {
        Invoke-Checked git @('fetch', 'origin', $Branch) | Out-Null
        $remoteSha = (Invoke-Checked git @('rev-parse', "origin/$Branch")).Trim()
    }
    if (-not $Commit -and $currentBranch -eq $Branch -and $localSha -ne $remoteSha) {
        Write-Warning "Local $Branch ($localSha) differs from origin/$Branch ($remoteSha); GitHub builds the pushed commit."
    }

    # GitHub Actions builds the pushed commit, not the locally edited files driving this launcher.
    # In particular an MC-tag against an old Linux workflow silently builds the screensaver,
    # succeeds, and uploads only srpss-linux. Check both remote-commit owners *before* any push/dispatch.
    if ($Profile -eq 'mc') {
        $sourceWorkflow = (& git show "$($remoteSha):.github/workflows/linux-build.yml" 2>$null | Out-String)
        $workflowReadExit = $LASTEXITCODE
        $sourceBuilder = (& git show "$($remoteSha):tools/linux_build.py" 2>$null | Out-String)
        $builderReadExit = $LASTEXITCODE
        $hasMcWorkflow = ($workflowReadExit -eq 0 -and
            $sourceWorkflow.Contains('refs/tags/linux-build/mc-') -and
            $sourceWorkflow.Contains('--profile "$BUILD_PROFILE"') -and
            $sourceWorkflow.Contains('srpss-linux-mc'))
        $hasMcBuilder = ($builderReadExit -eq 0 -and
            $sourceBuilder.Contains('main_mc.py') -and
            $sourceBuilder.Contains('--profile') -and
            $sourceBuilder.Contains('PROFILES'))
        if (-not $hasMcWorkflow -or -not $hasMcBuilder) {
            throw "[LINUX-BUILD] MC unavailable at pushed commit $remoteSha (branch $Branch): the GitHub workflow or Linux Nuitka builder there lacks MC support. Commit and push the Linux MC implementation, then rerun GitHub Remote against the NEW pushed SHA. A temporary tag cannot turn the old screensaver workflow into an MC build. No workflow was started."
        }
        Write-Host "[LINUX-BUILD] Pinned GitHub commit has the MC-capable workflow and builder: $remoteSha"
    }

    if ($Mode -eq 'Auto') {
        & gh workflow view $Workflow *> $null
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "[LINUX-BUILD] $Workflow is not registered on the default branch yet; using a temporary linux-build/* tag."
            $Mode = 'Tag'
        } elseif ($Profile -eq 'mc') {
            # GitHub's workflow_dispatch input contract is versioned by the workflow already on the default branch.
            # Until MC's input is merged, tag the pinned SHA so the branch's workflow can build MC on its own.
            $defaultWorkflow = (& git show 'origin/main:.github/workflows/linux-build.yml' 2>$null | Out-String)
            if ($LASTEXITCODE -ne 0 -or $defaultWorkflow -notmatch '(?m)^\s+profile:\s*$') {
                Write-Host '[LINUX-BUILD] Default workflow has no MC input yet; using the profile-specific tag route.'
                $Mode = 'Tag'
            } else {
                $Mode = 'Dispatch'
            }
        } else {
            $Mode = 'Dispatch'
        }
    }

    $started = (Get-Date).ToUniversalTime().AddSeconds(-5)
    $tag = $null
    $token = $null
    if ($Mode -eq 'Dispatch') {
        $dispatchArgs = @('workflow', 'run', $Workflow, '--ref', $Branch)
        if ($Commit) {
            # Pinned, uniquely identified dispatch: no ambiguity when Standard and MC build concurrently.
            $token = 'srpss-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + $Profile
            $dispatchArgs += @('-f', "commit=$remoteSha", '-f', "token=$token")
        }
        if ($Profile -eq 'mc') { $dispatchArgs += @('-f', 'profile=mc') }
        if ($token) {
            Write-Host "[LINUX-BUILD] Dispatching $Workflow on $Branch at $remoteSha (run token $token)"
        } else {
            Write-Host "[LINUX-BUILD] Dispatching $Workflow on $Branch at $remoteSha ($Profile)"
        }
        Invoke-Checked gh $dispatchArgs | Out-Null
        $runEvent = 'workflow_dispatch'
    } else {
        # Existing linux-build/* trigger also accepts mc- prefixed tag names, including before workflow merge.
        $stamp = (Get-Date -Format 'yyyyMMdd-HHmmss-fff') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 6)
        $tag = 'linux-build/' + $(if ($Profile -eq 'mc') { 'mc-' } else { '' }) + $stamp
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
        } elseif ($tag) {
            $runs = Invoke-Checked gh @('run', 'list', '--workflow', $Workflow, '--event', 'push',
                '--limit', '30', '--json', 'databaseId,headBranch') | ConvertFrom-Json
            $runId = ($runs | Where-Object { $_.headBranch -eq $tag } | Select-Object -First 1).databaseId
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
    $artifact = if ($Profile -eq 'mc') { 'srpss-linux-mc' } else { 'srpss-linux' }
    $pattern = if ($Profile -eq 'mc') { 'SRPSS-*-linux-mc-x86_64.tar.gz' } else { 'SRPSS-*-linux-x86_64.tar.gz' }
    $staging = Join-Path $OutDir ('.linux-download-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $staging | Out-Null
    try {
        Invoke-Checked gh @('run', 'download', $runId, '--name', $artifact, '--dir', $staging) | Out-Null
        $files = @(Get-ChildItem -LiteralPath $staging -Filter $pattern -File)
        if ($files.Count -ne 1 -or $files[0].Length -le 0) {
            throw "Expected one nonempty $pattern from GitHub artifact $artifact, found $($files.Count)"
        }
        $destination = Join-Path $OutDir $files[0].Name
        Move-Item -LiteralPath $files[0].FullName -Destination $destination -Force
        Write-Host "[LINUX-BUILD] $destination"
    } finally {
        Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host '[LINUX-BUILD] On Linux: tar xzf <archive> && ./SRPSS-*/install.sh'
} finally {
    if ($tag) {
        & git push origin ":refs/tags/$tag" 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Warning "Could not delete temporary tag $tag; remove it with: git push origin :refs/tags/$tag" }
    }
    Pop-Location
}
