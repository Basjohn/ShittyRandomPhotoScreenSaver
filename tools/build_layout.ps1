<#
Shared publication helpers for SRPSS build workers.

Compilers write only to their product-specific scratch directory. A completed
payload is copied into a temporary sibling under release, checked for its
required artifact, and then moved into the canonical product directory.
#>

Set-StrictMode -Version Latest

function Resolve-SRPSSChildPath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ParentPath
    )

    $parentFull = [System.IO.Path]::GetFullPath($ParentPath).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $pathFull = [System.IO.Path]::GetFullPath($Path).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $prefix = $parentFull + [System.IO.Path]::DirectorySeparatorChar

    if (-not $pathFull.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing build publication path outside '$parentFull': $pathFull"
    }

    return $pathFull
}

function Reset-SRPSSBuildDirectory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$BuildRoot
    )

    $safePath = Resolve-SRPSSChildPath -Path $Path -ParentPath $BuildRoot
    if (Test-Path -LiteralPath $safePath) {
        Remove-Item -LiteralPath $safePath -Recurse -Force
    }
    New-Item -ItemType Directory -Path $safePath -Force | Out-Null
    return $safePath
}

function Remove-SRPSSBuildDirectory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$BuildRoot
    )

    $buildRootFull = [System.IO.Path]::GetFullPath($BuildRoot).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $safePath = Resolve-SRPSSChildPath -Path $Path -ParentPath $buildRootFull
    if (Test-Path -LiteralPath $safePath) {
        Remove-Item -LiteralPath $safePath -Recurse -Force
    }

    $parentPath = Split-Path -Parent $safePath
    while (
        $parentPath.StartsWith(
            $buildRootFull + [System.IO.Path]::DirectorySeparatorChar,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    ) {
        if (
            @(Get-ChildItem -LiteralPath $parentPath -Force -ErrorAction SilentlyContinue).Count -gt 0
        ) {
            break
        }
        Remove-Item -LiteralPath $parentPath -Force
        $parentPath = Split-Path -Parent $parentPath
    }

    if (
        (Test-Path -LiteralPath $buildRootFull -PathType Container) -and
        (@(Get-ChildItem -LiteralPath $buildRootFull -Force).Count -eq 0)
    ) {
        Remove-Item -LiteralPath $buildRootFull -Force
    }
}

function Publish-SRPSSDirectory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$TargetPath,
        [Parameter(Mandatory = $true)][string]$ReleaseRoot,
        [Parameter(Mandatory = $true)][string[]]$RequiredRelativePaths
    )

    if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
        throw "Build payload directory does not exist: $SourcePath"
    }

    $sourceFull = (Resolve-Path -LiteralPath $SourcePath).Path
    $releaseFull = [System.IO.Path]::GetFullPath($ReleaseRoot)
    $targetFull = Resolve-SRPSSChildPath -Path $TargetPath -ParentPath $releaseFull
    $targetName = Split-Path -Leaf $targetFull
    $publishPath = Resolve-SRPSSChildPath `
        -Path (Join-Path $releaseFull ".$targetName.publish.$PID") `
        -ParentPath $releaseFull

    New-Item -ItemType Directory -Force -Path $releaseFull | Out-Null
    if (Test-Path -LiteralPath $publishPath) {
        Remove-Item -LiteralPath $publishPath -Recurse -Force
    }

    New-Item -ItemType Directory -Path $publishPath | Out-Null
    try {
        $sourceItems = @(Get-ChildItem -LiteralPath $sourceFull -Force)
        if ($sourceItems.Count -eq 0) {
            throw "Build payload directory is empty: $sourceFull"
        }

        foreach ($item in $sourceItems) {
            Copy-Item `
                -LiteralPath $item.FullName `
                -Destination $publishPath `
                -Recurse `
                -Force
        }

        foreach ($relativePath in $RequiredRelativePaths) {
            $requiredPath = Join-Path $publishPath $relativePath
            if (-not (Test-Path -LiteralPath $requiredPath)) {
                throw "Published payload is missing required artifact: $relativePath"
            }
        }

        if (Test-Path -LiteralPath $targetFull) {
            Remove-Item -LiteralPath $targetFull -Recurse -Force
        }

        Move-Item -LiteralPath $publishPath -Destination $targetFull
    } catch {
        if (Test-Path -LiteralPath $publishPath) {
            Remove-Item -LiteralPath $publishPath -Recurse -Force -ErrorAction SilentlyContinue
        }
        throw
    }

    return $targetFull
}

function Remove-SRPSSLegacyReleasePath {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ReleaseRoot
    )

    $safePath = Resolve-SRPSSChildPath -Path $Path -ParentPath $ReleaseRoot
    if (Test-Path -LiteralPath $safePath) {
        Remove-Item -LiteralPath $safePath -Recurse -Force
        Write-Host "[BUILD] Retired legacy release path: $safePath"
    }
}
