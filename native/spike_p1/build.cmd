@echo off
rem SRPSS P1 spike build (MSVC x64 + Ninja): the one CMake invocation, run by .github/workflows/native-module.yml on
rem GitHub's Windows runner (builds happen only through GitHub workflows, operator 12 Nov 2026). All arguments are
rem optional:
rem   build.cmd [build dir] [SPIKE_WITH_QUICK ON|OFF] [repo .venv dir] [SDK root]
rem The SDK root holds the Qt SDK prefix (qt\), Vulkan-Headers and the tool venv (venv\ with ninja), the layout
rem tools/native_sdk_fetch.py creates (see README.md).
setlocal
set "SRC=%~dp0"
set "BUILD=%~1"
if "%BUILD%"=="" set "BUILD=D:\Temp\Scratch\SRPSS\native_spike\build"
set "QUICK=%~2"
if "%QUICK%"=="" set "QUICK=ON"
set "VENV=%~3"
if "%VENV%"=="" set "VENV=%~dp0..\..\.venv"
set "SPIKE=%~4"
if "%SPIKE%"=="" set "SPIKE=D:\Temp\Scratch\SRPSS\native_spike"

rem The newest Visual Studio (or Build Tools) with the x64 C++ tools, found with vswhere (never a fixed path).
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "%VSWHERE%" (
  echo vswhere.exe not found: install Visual Studio or its Build Tools with the C++ workload
  exit /b 1
)
set "VSROOT="
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSROOT=%%i"
if not defined VSROOT (
  echo No Visual Studio installation with the x64 C++ tools was found
  exit /b 1
)
call "%VSROOT%\VC\Auxiliary\Build\vcvars64.bat" >nul || exit /b 1
echo MSVC toolset %VCToolsVersion% from %VSROOT%

cmake -S "%SRC%." -B "%BUILD%" -G Ninja ^
  -DCMAKE_MAKE_PROGRAM="%SPIKE%\venv\Scripts\ninja.exe" ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_PREFIX_PATH="%SPIKE%\qt" ^
  -DPython_EXECUTABLE="%VENV%\Scripts\python.exe" ^
  -DSPIKE_QSB="%VENV%\Lib\site-packages\PySide6\qsb.exe" ^
  -DSPIKE_VULKAN_INCLUDE="%SPIKE%\vulkan_headers\Vulkan-Headers-1.4.341\include" ^
  -DSPIKE_WITH_QUICK=%QUICK% || exit /b 1
cmake --build "%BUILD%" || exit /b 1
