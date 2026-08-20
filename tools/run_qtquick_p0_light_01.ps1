$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = "C:\Python311\python.exe"
$presentMon = "C:\Tools\PresentMon\PresentMon.exe"
$json = Join-Path $repoRoot "Docs\Performance_Evidence\QtQuick-P0-Light-01.json"
$csv = Join-Path $repoRoot "Docs\Performance_Evidence\QtQuick-P0-Light-01-PresentMon.csv"

if ((Test-Path -LiteralPath $json) -or (Test-Path -LiteralPath $csv)) {
    throw "Quick P0 light run 01 already exists; refusing to overwrite it."
}

Push-Location -LiteralPath $repoRoot
try {
    $benchmark = Start-Process -FilePath $python -PassThru -NoNewWindow -ArgumentList @(
        "-m", "tools.qtquick_p0_presentation_benchmark",
        "--population", "P0",
        "--target-hz", "165,60",
        "--load-label", "light",
        "--run-id", "qtquick-p0-light-01",
        "--output", $json
    )

    $capture = Start-Process -FilePath $presentMon -PassThru -NoNewWindow -ArgumentList @(
        "--process_id", $benchmark.Id,
        "--output_file", $csv,
        "--date_time",
        "--v2_metrics",
        "--no_console_stats",
        "--timed", "25",
        "--terminate_after_timed"
    )

    $benchmark.WaitForExit()
    $capture.WaitForExit()
    if (($benchmark.ExitCode -ne 0) -or ($capture.ExitCode -ne 0)) {
        throw "Capture failed (benchmark=$($benchmark.ExitCode), PresentMon=$($capture.ExitCode))."
    }
} finally {
    Pop-Location
}

Get-Item -LiteralPath $json, $csv
