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


function Assert-SRPSSDefaultsAuthority {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$PythonExe
    )

    $auditTool = Join-Path $RepoRoot 'tools\check_defaults_authority.py'
    if (-not (Test-Path -LiteralPath $auditTool -PathType Leaf)) {
        throw "Defaults authority audit tool is missing: $auditTool"
    }

    Push-Location $RepoRoot
    try {
        & $PythonExe $auditTool
        if ($LASTEXITCODE -ne 0) {
            throw "Defaults authority audit failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
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

function Get-SRPSSVisualizerShaderNames {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $shaderSource = Join-Path $RepoRoot 'widgets\spotify_visualizer\shaders'
    if (-not (Test-Path -LiteralPath $shaderSource -PathType Container)) {
        throw "Visualizer shader source directory does not exist: $shaderSource"
    }

    $shaderNames = @(
        Get-ChildItem -LiteralPath $shaderSource -Filter '*.frag' -File |
            Sort-Object Name |
            Select-Object -ExpandProperty Name
    )
    if ($shaderNames.Count -eq 0) {
        throw "Visualizer shader source directory contains no .frag files: $shaderSource"
    }
    return $shaderNames
}

function Assert-SRPSSOnefileVisualizerShaderContract {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][object[]]$NuitkaArguments
    )

    $includeArgument = '--include-data-dir=widgets/spotify_visualizer/shaders=widgets/spotify_visualizer/shaders'
    if ($NuitkaArguments -notcontains $includeArgument) {
        throw "Onefile build does not declare the visualizer shader data directory."
    }

    return @(Get-SRPSSVisualizerShaderNames -RepoRoot $RepoRoot)
}

function Assert-SRPSSOnedirVisualizerShaders {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$DistributionRoot
    )

    $shaderNames = @(Get-SRPSSVisualizerShaderNames -RepoRoot $RepoRoot)
    $shaderDestination = Join-Path $DistributionRoot 'widgets\spotify_visualizer\shaders'
    $missingShaders = @(
        $shaderNames | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $shaderDestination $_) -PathType Leaf)
        }
    )
    if ($missingShaders.Count -gt 0) {
        throw "Onedir payload is missing visualizer shaders: $($missingShaders -join ', ')"
    }

    return $shaderNames
}

function Get-SRPSSQuickPayloadRelativePaths {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $qmlSource = Join-Path $RepoRoot 'rendering\quick\qml'
    if (-not (Test-Path -LiteralPath $qmlSource -PathType Container)) {
        throw "Qt Quick QML source directory does not exist: $qmlSource"
    }

    $requiredRelativePaths = @(
        'DisplayScene.qml',
        'VisualizerPresentation.qml',
        'WidgetInteractionGlow.qml',
        'shaders\widget_glow.frag.qsb'
    )
    foreach ($relativePath in $requiredRelativePaths) {
        if (-not (Test-Path -LiteralPath (Join-Path $qmlSource $relativePath) -PathType Leaf)) {
            throw "Qt Quick QML payload is missing required file: $relativePath"
        }
    }

    return @(
        Get-ChildItem -LiteralPath $qmlSource -Recurse -File |
            ForEach-Object {
                $_.FullName.Substring($qmlSource.Length + 1)
            } |
            Sort-Object
    )
}

function Assert-SRPSSSourceProductAssets {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $requiredFiles = @(
        'SRPSS.ico',
        'images\LogoBMP.bmp',
        'resources\tutuogg.ogg',
        'resources\jedimodeyall.mp3',
        'rendering\quick\qml\DisplayScene.qml',
        'rendering\quick\qml\FriendPulsePresentation.qml',
        'rendering\quick\qml\SystemStatsPresentation.qml',
        'rendering\quick\qml\VisualizerPresentation.qml',
        'rendering\quick\qml\WidgetInteractionGlow.qml',
        'rendering\quick\qml\shaders\widget_glow.frag.qsb',
        'images\system_stats_tools.svg'
    )
    foreach ($relativePath in $requiredFiles) {
        $candidate = Join-Path $RepoRoot $relativePath
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            throw "Required product asset is missing: $candidate"
        }
    }

    $requiredDirectories = @(
        'presets\visualizer_modes',
        'themes',
        'themes\widgets',
        'widgets\spotify_visualizer\shaders'
    )
    foreach ($relativePath in $requiredDirectories) {
        $candidate = Join-Path $RepoRoot $relativePath
        if (-not (Test-Path -LiteralPath $candidate -PathType Container)) {
            throw "Required product asset directory is missing: $candidate"
        }
    }

    $settingsThemes = @(
        Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'themes') -Filter '*.srtheme' -File -ErrorAction SilentlyContinue
    )
    $widgetThemes = @(
        Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'themes\widgets') -Filter '*.srwtheme' -File -ErrorAction SilentlyContinue
    )
    $visualizerPresets = @(
        Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'presets\visualizer_modes') -Filter '*.json' -File -Recurse -ErrorAction SilentlyContinue
    )
    if ($settingsThemes.Count -eq 0) {
        throw 'No shipped Settings .srtheme files were found under themes.'
    }
    if ($widgetThemes.Count -eq 0) {
        throw 'No shipped Widget .srwtheme files were found under themes\widgets.'
    }
    if ($visualizerPresets.Count -eq 0) {
        throw 'No shipped visualizer preset JSON files were found.'
    }

    return [pscustomobject]@{
        SettingsThemes = $settingsThemes.Count
        WidgetThemes = $widgetThemes.Count
        VisualizerPresets = $visualizerPresets.Count
        QuickPayloadFiles = @(Get-SRPSSQuickPayloadRelativePaths -RepoRoot $RepoRoot).Count
    }
}

function Assert-SRPSSOnefileQuickPayloadContract {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][object[]]$NuitkaArguments
    )

    $requiredArguments = @(
        '--include-data-dir=rendering/quick/qml=rendering/quick/qml',
        '--include-data-dir=images=images',
        '--include-data-files=resources/tutuogg.ogg=resources/tutuogg.ogg',
        '--include-data-files=resources/jedimodeyall.mp3=resources/jedimodeyall.mp3',
        '--include-package=rendering.quick',
        '--include-package=widgets.spotify_visualizer',
        '--include-package=rendering.gl_programs',
        '--include-package=OpenGL',
        '--include-package=pyaudiowpatch',
        '--include-package=sounddevice',
        '--include-qt-plugins=qml',
        '--include-qt-plugins=multimedia',
        '--include-module=PySide6.QtQuick',
        '--include-module=PySide6.QtQml',
        '--include-module=PySide6.QtMultimedia'
    )
    foreach ($argument in $requiredArguments) {
        if ($NuitkaArguments -notcontains $argument) {
            throw "Onefile build is missing required Qt Quick/runtime declaration: $argument"
        }
    }

    return @(Get-SRPSSQuickPayloadRelativePaths -RepoRoot $RepoRoot)
}

function Assert-SRPSSOnedirQuickPayload {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$DistributionRoot
    )

    $relativePaths = @(Get-SRPSSQuickPayloadRelativePaths -RepoRoot $RepoRoot)
    $qmlDestination = Join-Path $DistributionRoot 'rendering\quick\qml'
    $missing = @(
        $relativePaths | Where-Object {
            -not (Test-Path -LiteralPath (Join-Path $qmlDestination $_) -PathType Leaf)
        }
    )
    if ($missing.Count -gt 0) {
        throw "Onedir payload is missing Qt Quick/QML data: $($missing -join ', ')"
    }

    $requiredProductFiles = @(
        'resources\tutuogg.ogg',
        'resources\jedimodeyall.mp3'
    )
    foreach ($relativePath in $requiredProductFiles) {
        if (-not (Test-Path -LiteralPath (Join-Path $DistributionRoot $relativePath) -PathType Leaf)) {
            throw "Onedir payload is missing required product file: $relativePath"
        }
    }
    $requiredProductDirectories = @(
        'themes',
        'themes\widgets',
        'presets\visualizer_modes',
        'widgets\spotify_visualizer\shaders'
    )
    foreach ($relativePath in $requiredProductDirectories) {
        if (-not (Test-Path -LiteralPath (Join-Path $DistributionRoot $relativePath) -PathType Container)) {
            throw "Onedir payload is missing required product directory: $relativePath"
        }
    }

    return $relativePaths
}

function Assert-SRPSSPythonRuntimeDependencies {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe
    )

    # Keep this aligned with requirements.txt and the dynamic/lazy runtime
    # surfaces that Nuitka cannot safely infer from one top-level import graph.
    $probe = @'
import importlib
modules = (
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtMultimedia",
    "shiboken6",
    "OpenGL",
    "numpy",
    "PIL",
    "winrt.windows.media.control",
    "winrt.windows.storage.streams",
    "pyaudiowpatch",
    "sounddevice",
    "pycaw",
    "comtypes",
    "psutil",
)
for name in modules:
    importlib.import_module(name)
print("SRPSS_RUNTIME_DEPENDENCIES_OK")
'@

    & $PythonExe -c $probe 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Python runtime dependency probe failed for: $PythonExe"
    }
}
