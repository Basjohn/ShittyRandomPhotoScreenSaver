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

function Remove-SRPSSPathWithRetry {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$AttemptCount = 4,
        [int]$DelayMilliseconds = 200
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $attempts = [Math]::Max(1, $AttemptCount)
    for ($attempt = 1; $attempt -le $attempts; $attempt += 1) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            return
        } catch {
            if ($attempt -ge $attempts) {
                throw (
                    "Could not remove '$Path' after $attempts bounded attempts. " +
                    "A running/previewed artifact or another process may still hold the path: " +
                    $_.Exception.Message
                )
            }
            Start-Sleep -Milliseconds ([Math]::Max(0, $DelayMilliseconds))
        }
    }
}

function Clear-SRPSSPublishedProductDirectory {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$ReleaseRoot
    )

    $releaseFull = [System.IO.Path]::GetFullPath($ReleaseRoot)
    $safePath = Resolve-SRPSSChildPath -Path $Path -ParentPath $releaseFull
    if (Test-Path -LiteralPath $safePath) {
        Remove-SRPSSPathWithRetry -Path $safePath
    }
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

function Assert-SRPSSQmlSourceContract {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$PythonExe
    )

    $auditTool = Join-Path $RepoRoot 'tools\check_qml_source_contract.py'
    if (-not (Test-Path -LiteralPath $auditTool -PathType Leaf)) {
        throw "QML source contract audit tool is missing: $auditTool"
    }

    Push-Location $RepoRoot
    try {
        & $PythonExe $auditTool
        if ($LASTEXITCODE -ne 0) {
            throw "QML source contract audit failed with exit code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
}


function Assert-SRPSSQmlExternalImportContract {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    $qmlRoot = Join-Path $RepoRoot 'rendering\quick\qml'
    if (-not (Test-Path -LiteralPath $qmlRoot -PathType Container)) {
        throw "Qt Quick QML source directory does not exist: $qmlRoot"
    }

    # The frozen QML dependency surface is intentionally tiny. Expanding it
    # must be an explicit packaging decision rather than silently re-growing
    # the PySide6 QML tree in every product.
    $allowedImports = @(
        'QtQuick',
        'QtQuick.Effects'
    )
    $seenImports = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $unexpected = [System.Collections.Generic.List[string]]::new()

    foreach ($qmlFile in @(Get-ChildItem -LiteralPath $qmlRoot -Filter '*.qml' -File -Recurse)) {
        $lineNumber = 0
        foreach ($line in [System.IO.File]::ReadLines($qmlFile.FullName)) {
            $lineNumber += 1
            $match = [regex]::Match($line, '^\s*import\s+([A-Za-z0-9_.]+)(?:\s|$)')
            if (-not $match.Success) {
                continue
            }

            $namespace = $match.Groups[1].Value
            if (-not $namespace.StartsWith('Qt', [System.StringComparison]::Ordinal)) {
                continue
            }

            [void]$seenImports.Add($namespace)
            if ($allowedImports -notcontains $namespace) {
                $relativePath = [System.IO.Path]::GetRelativePath($RepoRoot, $qmlFile.FullName)
                $unexpected.Add(("{0}:{1}: {2}" -f $relativePath, $lineNumber, $namespace))
            }
        }
    }

    if ($unexpected.Count -gt 0) {
        throw (
            "Qt QML import contract expanded beyond the frozen packaging allowlist. " +
            "Review the new runtime dependency before changing the prune contract: " +
            ($unexpected -join '; ')
        )
    }

    foreach ($requiredNamespace in $allowedImports) {
        if (-not $seenImports.Contains($requiredNamespace)) {
            throw "Expected Qt QML namespace is no longer used: $requiredNamespace"
        }
    }

    return @($seenImports | Sort-Object)
}

function Get-SRPSSNuitkaQmlPruneArguments {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot
    )

    # Validate live source before applying the denylist. QtQuick,
    # QtQuick.Effects, and the core QtQuick/QtQml substrate are intentionally
    # retained; the families below are not imported by any SRPSS QML file.
    [void](Assert-SRPSSQmlExternalImportContract -RepoRoot $RepoRoot)

    $unusedQmlFamilies = @(
        'Qt/labs',
        'Qt3D',
        'Qt5Compat',
        'QtCharts',
        'QtDataVisualization',
        'QtGraphs',
        'QtLocation',
        'QtMultimedia',
        'QtNetwork',
        'QtPositioning',
        'QtQml/StateMachine',
        'QtQml/XmlListModel',
        'QtQuick3D',
        'QtQuick/Controls',
        'QtQuick/Dialogs',
        'QtQuick/Layouts',
        'QtQuick/LocalStorage',
        'QtQuick/NativeStyle',
        'QtQuick/Particles',
        'QtQuick/Pdf',
        'QtQuick/Shapes',
        'QtQuick/Templates',
        'QtQuick/Timeline',
        'QtQuick/VectorImage',
        'QtQuick/VirtualKeyboard',
        'QtRemoteObjects',
        'QtScxml',
        'QtSensors',
        'QtTest',
        'QtTextToSpeech',
        'QtWebChannel',
        'QtWebEngine',
        'QtWebSockets',
        'QtWebView'
    )

    $arguments = [System.Collections.Generic.List[string]]::new()
    foreach ($family in $unusedQmlFamilies) {
        # Nuitka's PySide6 plugin turns QtQuick/QtQml usage into one monolithic
        # QML-directory scan.  A one-level wildcard is not sufficient for nested
        # QML families and, more importantly, excluding only the QML plugin DLL
        # does not stop Nuitka's dependency scanner from retaining its linked
        # Qt framework DLLs.  Exclude the family tree recursively here; the
        # top-level framework denylist below closes the dependency side too.
        $arguments.Add("--noinclude-data-files=PySide6/qml/$family/**")
        $arguments.Add("--noinclude-dlls=PySide6/qml/$family/**")
    }

    # These Qt framework families have no authored Python/QML import in SRPSS.
    # QML plugin scanning can nevertheless discover their plugin binaries and
    # then pull the linked framework DLLs into standalone/onefile products.
    # Match by DLL basename so transitive copies cannot survive merely because
    # they were discovered from another path.  Keep core QtQuick/Qml/Gui/Core,
    # Widgets, Svg, Multimedia, OpenGL and ShaderTools out of this denylist.
    foreach ($dllPattern in @(
        '*Qt6WebEngine*.dll',
        '*Qt6Pdf*.dll',
        '*Qt6VirtualKeyboard*.dll',
        '*Qt6Quick3D*.dll',
        '*Qt63D*.dll',
        '*Qt6Charts*.dll',
        '*Qt6Graphs*.dll',
        '*Qt6DataVisualization*.dll',
        '*Qt6Location*.dll',
        '*Qt6Positioning*.dll',
        '*Qt6RemoteObjects*.dll',
        '*Qt6Scxml*.dll',
        '*Qt6Sensors*.dll',
        '*Qt6TextToSpeech*.dll',
        '*Qt6WebView*.dll',
        '*Qt6QuickControls2*.dll',
        '*Qt6QuickTemplates2*.dll',
        # QML scan dependency fossils whose source namespaces are explicitly
        # outside the authored QtQuick + QtQuick.Effects contract.
        '*Qt6Labs*.dll',
        '*Qt6Concurrent.dll',
        '*Qt6MultimediaQuick.dll',
        '*Qt6OpenGLWidgets.dll',
        '*Qt6QmlLocalStorage.dll',
        '*Qt6QmlNetwork.dll',
        '*Qt6QmlXmlListModel.dll',
        '*Qt6QuickDialogs2*.dll',
        '*Qt6QuickLayouts.dll',
        '*Qt6QuickParticles.dll',
        '*Qt6QuickTest.dll',
        '*Qt6QuickTimeline*.dll',
        '*Qt6QuickVectorImage*.dll',
        '*Qt6SpatialAudio.dll',
        '*Qt6Sql.dll',
        '*Qt6StateMachine*.dll',
        '*Qt6Test.dll',
        '*Qt6WebChannel*.dll',
        '*Qt6WebSockets.dll'
    )) {
        $arguments.Add("--noinclude-dlls=$dllPattern")
    }

    # qpdf.dll is an image-format plugin, not the QtQuick.Pdf QML plugin.
    # SRPSS has no PDF source contract; keeping it pulls Qt6Pdf into every
    # frozen product solely for an unused decoder.
    $arguments.Add('--noinclude-dlls=*qpdf.dll')

    # PySide6.QtQuick has a binding-level dependency on PySide6.QtOpenGL even
    # though SRPSS does not import that binding directly. Do not prune it merely
    # because application source references QOpenGLContext through QtGui. A
    # frozen build can otherwise compile successfully and then die before Python
    # logging starts when QtQuick initialises. Qt6OpenGLWidgets remains separate
    # and unused; the QtOpenGL binding/native Qt6OpenGL substrate is retained.

    # Named timezone conversion is owned by QtCore.QTimeZone.  Do not let a
    # stale global/.venv pytz install wander back into a frozen product merely
    # because it still happens to exist in the build interpreter.
    $arguments.Add('--nofollow-import-to=pytz')
    $arguments.Add('--nofollow-import-to=tzdata')
    $arguments.Add('--noinclude-data-files=pytz/**')
    $arguments.Add('--noinclude-data-files=tzdata/**')

    return @($arguments)
}

function Assert-SRPSSForbiddenFrozenPayloadAbsent {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$DistributionRoot
    )

    if (-not (Test-Path -LiteralPath $DistributionRoot -PathType Container)) {
        throw "Frozen payload validation root does not exist: $DistributionRoot"
    }

    # This is intentionally a product assertion, not merely a size heuristic.
    # These tokens name frozen families with no SRPSS runtime contract. If
    # Nuitka/plugin behavior changes and one comes back, the MC build must fail
    # rather than silently publishing dead payload.
    $forbiddenTokens = @(
        'webengine',
        'qpdf',
        'qt6pdf',
        'virtualkeyboard',
        'quick3d',
        'qt3d',
        'qt6charts',
        'qt6graphs',
        'datavisualization',
        'qt6location',
        'qt6positioning',
        'qt6remoteobjects',
        'qt6scxml',
        'qt6sensors',
        'qt6texttospeech',
        'qt6webview',
        'qt6quickcontrols2',
        'qt6quicktemplates2',
        'qt6labs',
        'qt6concurrent',
        'qt6multimediaquick',
        'qt6openglwidgets',
        'qt6qmllocalstorage',
        'qt6qmlnetwork',
        'qt6qmlxmllistmodel',
        'qt6quickdialogs2',
        'qt6quicklayouts',
        'qt6quickparticles',
        'qt6quicktest',
        'qt6quicktimeline',
        'qt6quickvectorimage',
        'qt6spatialaudio',
        'qt6sql',
        'qt6statemachine',
        'qt6test',
        'qt6webchannel',
        'qt6websockets',
        'pytz',
        'tzdata'
    )

    $hits = [System.Collections.Generic.List[string]]::new()
    $rootFull = [System.IO.Path]::GetFullPath($DistributionRoot)
    foreach ($file in @(Get-ChildItem -LiteralPath $rootFull -Recurse -File -ErrorAction Stop)) {
        $relative = [System.IO.Path]::GetRelativePath($rootFull, $file.FullName).Replace('\', '/').ToLowerInvariant()
        foreach ($token in $forbiddenTokens) {
            if ($relative.Contains($token)) {
                $hits.Add($relative)
                break
            }
        }
    }

    if ($hits.Count -gt 0) {
        $preview = @($hits | Sort-Object -Unique | Select-Object -First 24) -join '; '
        throw "Unused frozen payload survived packaging: $preview"
    }

    return $true
}

# Compatibility alias for older build-worker references. New workers use the
# broader frozen-payload assertion above.
function Assert-SRPSSForbiddenQtPayloadAbsent {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$DistributionRoot
    )
    return Assert-SRPSSForbiddenFrozenPayloadAbsent -DistributionRoot $DistributionRoot
}

function Invoke-SRPSSQrcRegeneration {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$PythonExe
    )

    $qrcTool = Join-Path $RepoRoot 'tools\regen_qrc.py'
    if (-not (Test-Path -LiteralPath $qrcTool -PathType Leaf)) {
        throw "QRC regeneration tool is missing: $qrcTool"
    }
    $pythonCommand = Get-Command -Name $PythonExe -CommandType Application -ErrorAction SilentlyContinue
    if ($null -eq $pythonCommand) {
        throw "Selected Python toolchain is missing: $PythonExe"
    }
    $pythonPath = $pythonCommand.Source

    Push-Location $RepoRoot
    try {
        & $pythonPath $qrcTool --python $pythonPath
        if ($LASTEXITCODE -ne 0) {
            throw "Selected PySide6 QRC generation failed with exit code $LASTEXITCODE"
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
            Remove-SRPSSPathWithRetry -Path $targetFull
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

function Get-SRPSSDirectoryFootprint {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [int]$LargestFileCount = 40
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        throw "Build footprint root does not exist: $Path"
    }

    $rootFull = (Resolve-Path -LiteralPath $Path).Path.TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $files = @(Get-ChildItem -LiteralPath $rootFull -File -Recurse -Force -ErrorAction Stop)
    [long]$totalBytes = 0
    $bucketTable = @{}

    foreach ($file in $files) {
        [long]$bytes = $file.Length
        $totalBytes += $bytes
        $relative = [System.IO.Path]::GetRelativePath($rootFull, $file.FullName)
        $parts = $relative -split '[\\/]'
        $bucket = if ($parts.Count -gt 1) { $parts[0] } else { '(root)' }
        if (-not $bucketTable.ContainsKey($bucket)) {
            $bucketTable[$bucket] = [ordered]@{ file_count = 0; bytes = [long]0 }
        }
        $bucketTable[$bucket].file_count = [int]$bucketTable[$bucket].file_count + 1
        $bucketTable[$bucket].bytes = [long]$bucketTable[$bucket].bytes + $bytes
    }

    $topLevel = @(
        foreach ($bucket in $bucketTable.Keys) {
            [pscustomobject]@{
                name = [string]$bucket
                file_count = [int]$bucketTable[$bucket].file_count
                bytes = [long]$bucketTable[$bucket].bytes
            }
        }
    ) | Sort-Object -Property bytes -Descending

    $largestFiles = @(
        $files |
            Sort-Object -Property Length -Descending |
            Select-Object -First ([Math]::Max(0, $LargestFileCount)) |
            ForEach-Object {
                [pscustomobject]@{
                    path = [System.IO.Path]::GetRelativePath($rootFull, $_.FullName)
                    bytes = [long]$_.Length
                }
            }
    )

    return [pscustomobject]@{
        file_count = $files.Count
        bytes = $totalBytes
        top_level = $topLevel
        largest_files = $largestFiles
    }
}

function Get-SRPSSQrcSourceMetrics {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$QrcRelativePath,
        [Parameter(Mandatory = $true)][string]$GeneratedPackRelativePath
    )

    $qrcPath = Join-Path $RepoRoot $QrcRelativePath
    $generatedPath = Join-Path $RepoRoot $GeneratedPackRelativePath
    if (-not (Test-Path -LiteralPath $qrcPath -PathType Leaf)) {
        throw "QRC manifest does not exist: $qrcPath"
    }
    if (-not (Test-Path -LiteralPath $generatedPath -PathType Leaf)) {
        throw "Generated binary QRC pack does not exist: $generatedPath"
    }

    [xml]$qrc = Get-Content -LiteralPath $qrcPath -Raw
    $qrcDirectory = Split-Path -Parent $qrcPath
    $sourceFiles = @()
    [long]$sourceBytes = 0
    foreach ($node in @($qrc.SelectNodes('//file'))) {
        $relativeSource = [string]$node.InnerText
        if ([string]::IsNullOrWhiteSpace($relativeSource)) { continue }
        $sourcePath = [System.IO.Path]::GetFullPath((Join-Path $qrcDirectory $relativeSource.Trim()))
        if (-not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
            throw "QRC source file is missing: $sourcePath"
        }
        $source = Get-Item -LiteralPath $sourcePath
        $sourceFiles += $source
        $sourceBytes += [long]$source.Length
    }

    $qrcFile = Get-Item -LiteralPath $qrcPath
    $generatedFile = Get-Item -LiteralPath $generatedPath
    $ratio = if ($sourceBytes -gt 0) { [double]$generatedFile.Length / [double]$sourceBytes } else { 0.0 }
    return [pscustomobject]@{
        qrc = $QrcRelativePath
        qrc_manifest_bytes = [long]$qrcFile.Length
        source_file_count = $sourceFiles.Count
        source_bytes = $sourceBytes
        generated_pack = $GeneratedPackRelativePath
        generated_pack_bytes = [long]$generatedFile.Length
        generated_to_source_ratio = [Math]::Round($ratio, 4)
        representation_note = 'Binary .rcc is the deployed Qt resource representation registered through QResource; generated Python resource modules are not packaged.'
    }
}

function Write-SRPSSBuildFootprintReport {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string]$ProductName,
        [Parameter(Mandatory = $true)][string]$PublishedRoot,
        [Parameter(Mandatory = $true)][string]$PrimaryArtifact,
        [Parameter(Mandatory = $true)][string]$NuitkaReportPath,
        [Parameter(Mandatory = $true)][string]$OutputPath
    )

    if (-not (Test-Path -LiteralPath $PrimaryArtifact -PathType Leaf)) {
        throw "Build footprint primary artifact is missing: $PrimaryArtifact"
    }
    if (-not (Test-Path -LiteralPath $NuitkaReportPath -PathType Leaf)) {
        throw "Nuitka compilation report is missing: $NuitkaReportPath"
    }

    $published = Get-SRPSSDirectoryFootprint -Path $PublishedRoot
    $artifact = Get-Item -LiteralPath $PrimaryArtifact
    $nuitkaReport = Get-Item -LiteralPath $NuitkaReportPath
    $resources = @(
        Get-SRPSSQrcSourceMetrics `
            -RepoRoot $RepoRoot `
            -QrcRelativePath 'ui\resources\assets.qrc' `
            -GeneratedPackRelativePath 'ui\resources\assets.rcc'
        Get-SRPSSQrcSourceMetrics `
            -RepoRoot $RepoRoot `
            -QrcRelativePath 'ui\resources\onboarding_assets.qrc' `
            -GeneratedPackRelativePath 'ui\resources\onboarding_assets.rcc'
    )

    $payload = [ordered]@{
        schema_version = 2
        generated_at_utc = [DateTime]::UtcNow.ToString('o')
        product = $ProductName
        primary_artifact = [ordered]@{
            path = [System.IO.Path]::GetRelativePath($RepoRoot, $artifact.FullName)
            bytes = [long]$artifact.Length
        }
        published_payload = $published
        nuitka_compilation_report = [ordered]@{
            path = [System.IO.Path]::GetRelativePath($RepoRoot, $nuitkaReport.FullName)
            bytes = [long]$nuitkaReport.Length
        }
        qrc_source_reference = $resources
        notes = @(
            'This report describes the current build and current package contents only.',
            'Binary .rcc packs are the installed/frozen Qt resource representation; generated Python resource modules are excluded.',
            'Use the Nuitka XML plus published payload buckets/largest files to identify real dependency/package bloat before adding exclusions.'
        )
    }

    $outputDirectory = Split-Path -Parent $OutputPath
    if ($outputDirectory) {
        New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
    }
    $payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding utf8

    $payloadMiB = [Math]::Round(([double]$published.bytes / 1MB), 2)
    $artifactMiB = [Math]::Round(([double]$artifact.Length / 1MB), 2)
    Write-Host "[BUILD] Footprint: artifact=$artifactMiB MiB, published payload=$payloadMiB MiB, files=$($published.file_count)"
    foreach ($resource in $resources) {
        $sourceMiB = [Math]::Round(([double]$resource.source_bytes / 1MB), 2)
        $generatedMiB = [Math]::Round(([double]$resource.generated_pack_bytes / 1MB), 2)
        Write-Host "[BUILD] QRC source reference $($resource.qrc): source=$sourceMiB MiB -> binary RCC=$generatedMiB MiB"
    }
    Write-Host "[BUILD] Nuitka compilation report: $NuitkaReportPath"
    Write-Host "[BUILD] Footprint report: $OutputPath"

    return $payload
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
        'ui\resources\assets.qrc',
        'ui\resources\assets.rcc',
        'ui\resources\onboarding_assets.qrc',
        'ui\resources\onboarding_assets.rcc',
        'resources\tutuogg.ogg',
        'resources\jedimodeyall.mp3',
        'rendering\quick\qml\DisplayScene.qml',
        'rendering\quick\qml\FriendPulsePresentation.qml',
        'rendering\quick\qml\SystemStatsPresentation.qml',
        'rendering\quick\qml\VisualizerPresentation.qml',
        'rendering\quick\qml\WidgetInteractionGlow.qml',
        'rendering\quick\qml\shaders\widget_glow.frag.qsb'
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
        '--include-module=PySide6.QtMultimedia',
        '--include-data-files=ui/resources/assets.rcc=ui/resources/assets.rcc',
        '--include-data-files=ui/resources/onboarding_assets.rcc=ui/resources/onboarding_assets.rcc'
    )
    foreach ($argument in $requiredArguments) {
        if ($NuitkaArguments -notcontains $argument) {
            throw "Onefile build is missing required Qt Quick/runtime declaration: $argument"
        }
    }

    foreach ($pruneArgument in @(Get-SRPSSNuitkaQmlPruneArguments -RepoRoot $RepoRoot)) {
        if ($NuitkaArguments -notcontains $pruneArgument) {
            throw "Onefile build is missing required Qt QML bloat exclusion: $pruneArgument"
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
        'resources\jedimodeyall.mp3',
        'ui\resources\assets.rcc',
        'ui\resources\onboarding_assets.rcc'
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
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [string]$RequirementsPath = (Join-Path (Split-Path -Parent $PSScriptRoot) 'requirements.txt')
    )

    if (-not (Test-Path -LiteralPath $RequirementsPath -PathType Leaf)) {
        throw "Canonical runtime requirements file not found: $RequirementsPath"
    }

    # Keep this aligned with requirements.txt and the dynamic/lazy runtime
    # surfaces that Nuitka cannot safely infer from one top-level import graph.
    $probe = @'
import importlib
from importlib import metadata as importlib_metadata
from pathlib import Path
import re
import sys


requirements_path = Path(sys.argv[1]).resolve()
qt_distributions = (
    "PySide6",
    "PySide6_Addons",
    "PySide6_Essentials",
    "shiboken6",
)


def canonical_distribution(name):
    return re.sub(r"[-_.]+", "-", name).casefold()


expected_qt_pins = {}
for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
    line = raw_line.split("#", 1)[0].strip()
    if not line:
        continue
    match = re.fullmatch(r"([^=<>!~\[\s]+)==([^\s;]+)", line)
    if match is None:
        continue
    name, version = match.groups()
    canonical_name = canonical_distribution(name)
    if canonical_name in {
        canonical_distribution(distribution) for distribution in qt_distributions
    }:
        expected_qt_pins[canonical_name] = version

missing_pins = [
    distribution
    for distribution in qt_distributions
    if canonical_distribution(distribution) not in expected_qt_pins
]
if missing_pins:
    raise RuntimeError(
        "requirements must pin exact versions for: " + ", ".join(missing_pins)
    )

metadata_mismatches = []
for distribution in qt_distributions:
    expected = expected_qt_pins[canonical_distribution(distribution)]
    installed = importlib_metadata.version(distribution)
    if installed != expected:
        metadata_mismatches.append(
            f"{distribution}: installed {installed}, required {expected}"
        )
if metadata_mismatches:
    raise RuntimeError("Qt distribution version mismatch: " + "; ".join(metadata_mismatches))

import PySide6
from PySide6 import QtCore
import shiboken6

loaded_versions = {
    "PySide6": PySide6.__version__,
    "Qt runtime": QtCore.qVersion(),
    "shiboken6": shiboken6.__version__,
}
loaded_expectations = {
    "PySide6": expected_qt_pins[canonical_distribution("PySide6")],
    "Qt runtime": expected_qt_pins[canonical_distribution("PySide6_Essentials")],
    "shiboken6": expected_qt_pins[canonical_distribution("shiboken6")],
}
loaded_mismatches = [
    f"{name}: loaded {loaded_versions[name]}, required {expected}"
    for name, expected in loaded_expectations.items()
    if loaded_versions[name] != expected
]
if loaded_mismatches:
    raise RuntimeError("Loaded Qt/Shiboken version mismatch: " + "; ".join(loaded_mismatches))

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

    & $PythonExe -c $probe $RequirementsPath 2>&1 | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Python runtime dependency/version probe failed for: $PythonExe"
    }
}
