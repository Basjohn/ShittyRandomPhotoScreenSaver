@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo SRPSS repository .venv not found.
    echo Expected: .venv\Scripts\python.exe in the repository root.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "import PIL; import PySide6; from PySide6 import QtCore, QtGui, QtWidgets; print('Border Studio dependencies OK: Pillow', PIL.__version__, 'PySide6', PySide6.__version__)"
if errorlevel 1 (
    echo Missing or broken dependencies in existing SRPSS .venv.
    echo Use your normal repository dependency setup. This tool never installs packages.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" "tools\srpss_border_studio.py" %*
if errorlevel 1 (
    echo Border Studio exited with an error.
    pause
    exit /b 1
)
endlocal
