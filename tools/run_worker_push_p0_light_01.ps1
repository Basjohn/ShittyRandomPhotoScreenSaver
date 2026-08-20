$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$presentMonPath = "C:\Tools\PresentMon\PresentMon.exe"
$pythonPath = "C:\Python311\python.exe"
$jsonPath = Join-Path $repoRoot "Docs\Performance_Evidence\WorkerPush-P0-Light-01.json"
$csvPath = Join-Path $repoRoot "Docs\Performance_Evidence\WorkerPush-P0-Light-01-PresentMon.csv"

if ((Test-Path -LiteralPath $jsonPath) -or (Test-Path -LiteralPath $csvPath)) {
    throw "Run 01 evidence already exists; refusing to overwrite it."
}

$presentMonArguments = @(
    "--process_name"
    "python.exe"
    "--output_file"
    ('"{0}"' -f $csvPath)
    "--date_time"
    "--v2_metrics"
    "--no_console_stats"
    "--timed"
    "45"
    "--terminate_on_proc_exit"
    "--terminate_after_timed"
)

Push-Location -LiteralPath $repoRoot
try {
    $capture = Start-Process -FilePath $presentMonPath -ArgumentList $presentMonArguments -PassThru -NoNewWindow
    Start-Sleep -Seconds 1

    if ($capture.HasExited) {
        throw "PresentMon exited before the benchmark started (exit code $($capture.ExitCode))."
    }

    & $pythonPath -m tools.worker_push_presentation_benchmark --population P0 --target-hz "165,60" --load-label light --run-id worker-p0-light-01 --output $jsonPath
    $benchmarkExitCode = $LASTEXITCODE

    if (-not $capture.HasExited) {
        Wait-Process -Id $capture.Id
    }

    if (($benchmarkExitCode -ne 0) -or ($capture.ExitCode -ne 0)) {
        Remove-Item -LiteralPath $jsonPath, $csvPath -Force -ErrorAction SilentlyContinue
        throw "Capture failed (benchmark=$benchmarkExitCode, PresentMon=$($capture.ExitCode))."
    }
} finally {
    Pop-Location
}

Get-Item -LiteralPath $jsonPath, $csvPath
