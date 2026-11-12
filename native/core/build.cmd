@echo off
rem SRPSS native core build (MSVC x64 + Ninja): the one CMake invocation, run by .github/workflows/native-module.yml on
rem GitHub's Windows runner (builds happen only through GitHub workflows, operator 12 Nov 2026). The arguments are the
rem workflow's one call for every native source (native/spike_p1/build.cmd takes the same four):
rem   build.cmd <build dir> <Qt Quick part: ON> <repo .venv dir> <SDK root>
rem The core always has its Qt Quick part (the host adapter), so the second argument must be ON. The SDK root holds the
rem Qt SDK prefix (qt\), Vulkan-Headers and the tool venv (venv\ with ninja), the layout tools/native_sdk_fetch.py
rem creates.
setlocal
set "SRC=%~dp0"
set "BUILD=%~1"
set "QUICK=%~2"
set "VENV=%~3"
set "SDK=%~4"
if "%BUILD%"=="" (
  echo usage: build.cmd ^<build dir^> ON ^<repo .venv dir^> ^<SDK root^>
  exit /b 2
)
if /i not "%QUICK%"=="ON" (
  echo The native core always builds its Qt Quick part: the second argument must be ON, not "%QUICK%"
  exit /b 2
)
if "%VENV%"=="" (
  echo usage: build.cmd ^<build dir^> ON ^<repo .venv dir^> ^<SDK root^>
  exit /b 2
)
if "%SDK%"=="" (
  echo usage: build.cmd ^<build dir^> ON ^<repo .venv dir^> ^<SDK root^>
  exit /b 2
)

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
  -DCMAKE_MAKE_PROGRAM="%SDK%\venv\Scripts\ninja.exe" ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_PREFIX_PATH="%SDK%\qt" ^
  -DPython_EXECUTABLE="%VENV%\Scripts\python.exe" ^
  -DCORE_QSB="%VENV%\Lib\site-packages\PySide6\qsb.exe" ^
  -DCORE_VULKAN_INCLUDE="%SDK%\vulkan_headers\include" || exit /b 1
cmake --build "%BUILD%" || exit /b 1
