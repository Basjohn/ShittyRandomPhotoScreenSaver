# SRPSS Border Studio: repository-tool edition

Place these `tools/` and `tests/` folders **over the same folders in your SRPSS repository root**. This is a source-only overlay: it neither changes nor replaces any existing SRPSS files unless you already have identically named files. The integration does not alter `requirements.txt`, the build runner, installed application, settings or presets.

## Requirements: already present in SRPSS

The repository's canonical pinned `requirements.txt` (checked 8 Nov 2026) already lists:

- `PySide6==6.11.2`
- `Pillow==12.0.0`
- `pytest==8.4.1` (tests only)

**No second `.venv`, no `pip install`, and no new dependency requirements.** The launcher uses the repository-root `.venv\Scripts\python.exe` and checks that Pillow and PySide6 import successfully before launching. If your local venv is incomplete, fix it using your existing SRPSS dependency workflow, rather than allowing this tool to mutate it.

## Launch

Double-click `tools\run_srpss_border_studio.bat`, or run this **single-line PowerShell command from the SRPSS repository root**:

```powershell
.\.venv\Scripts\python.exe tools\srpss_border_studio.py
```

To preload a file, append its quoted path. Drag/drop also works inside the GUI.

## Tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_srpss_border_core.py -q
```

The GUI and processor are separately implemented: `tools/srpss_border_studio.py` is the PySide6 interface and `tools/srpss_border_core.py` performs image processing and validation. The tool does not import the screensaver's rendering engine or launch SRPSS itself.

## Preset and preservation

Standard treatment: resize source content first, then draw 2 px transparent outside margin, 2 px black border and 3 px outer radius. Animated WebP timing is read from the ANMF chunk fields, never guessed from an fps. It checks output frame count, per-frame durations, loop count, transparent perimeter, output file-size cap and ZIP integrity, rejecting invalid results rather than reporting false success. Source files are never overwritten. Preserve quality by shrinking dimensions before dropping below your configured quality floor.

**Scope:** This is a repackaging of the earlier Border Studio v1.0 implementation, not a new full architecture audit. The processor's tests can run here, but the PySide6 GUI still needs a first live run on Windows. The launcher does not install, update or pin packages.
