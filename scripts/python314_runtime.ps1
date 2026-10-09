# Canonical SRPSS Windows base-interpreter discovery (not a global PATH contract).
# Python Install Manager places standard per-user CPython at
# %LOCALAPPDATA%\Python\pythoncore-3.14-64\python.exe.
# Build workers and the destructive cutover share this single owner.
function Resolve-BasePython {
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\python.exe'))
    }
    # The legacy all-users installer remains supported, but isn't required.
    $candidates.Add('C:\Python314\python.exe')
    foreach ($launcherName in @('pymanager', 'py')) {
        if (-not (Get-Command $launcherName -ErrorAction SilentlyContinue)) { continue }
        try {
            $versionArg = if ($launcherName -eq 'pymanager') { '-V:3.14' } else { '-3.14' }
            $discovered = & $launcherName $versionArg -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0 -and $discovered) {
                $candidates.Add(([string]($discovered | Select-Object -Last 1)).Trim())
            }
        } catch { }
    }
    foreach ($exe in $candidates | Select-Object -Unique) {
        if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) { continue }
        try {
            $ok = & $exe -c "import sys, struct; print(int(sys.version_info[:2] == (3, 14) and struct.calcsize('P') == 8 and sys._is_gil_enabled()))" 2>$null
            if ($LASTEXITCODE -eq 0 -and ([string]$ok).Trim() -eq '1') {
                Write-Host "[PY314] Canonical base interpreter: $exe"
                return $exe
            }
        } catch { }
    }
    throw 'GIL-enabled CPython 3.14 x64 not found. Install Python 3.14 through Python Install Manager (pymanager install 3.14), then retry.'
}
