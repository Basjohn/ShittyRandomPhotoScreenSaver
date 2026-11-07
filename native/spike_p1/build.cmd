@echo off
rem SRPSS P1 spike build (MSVC x64 + Ninja). All arguments are optional:
rem   build.cmd [build dir] [SPIKE_WITH_QUICK ON|OFF] [repo .venv dir] [spike scratch root]
rem The scratch root holds the Qt SDK prefix (qt\), Vulkan-Headers and the tool venv (see README.md).
setlocal
set "SRC=%~dp0"
set "BUILD=%~1"
if "%BUILD%"=="" set "BUILD=X:\Scratch\SRPSS\native_spike\build"
set "QUICK=%~2"
if "%QUICK%"=="" set "QUICK=ON"
set "VENV=%~3"
if "%VENV%"=="" set "VENV=%~dp0..\..\.venv"
set "SPIKE=%~4"
if "%SPIKE%"=="" set "SPIKE=X:\Scratch\SRPSS\native_spike"

call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
cmake -S "%SRC%." -B "%BUILD%" -G Ninja ^
  -DCMAKE_MAKE_PROGRAM="%SPIKE%\venv\Scripts\ninja.exe" ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_PREFIX_PATH="%SPIKE%\qt" ^
  -DPython_EXECUTABLE="%VENV%\Scripts\python.exe" ^
  -DSPIKE_QSB="%VENV%\Lib\site-packages\PySide6\qsb.exe" ^
  -DSPIKE_VULKAN_INCLUDE="%SPIKE%\vulkan_headers\Vulkan-Headers-1.4.341\include" ^
  -DSPIKE_WITH_QUICK=%QUICK% || exit /b 1
cmake --build "%BUILD%" || exit /b 1
