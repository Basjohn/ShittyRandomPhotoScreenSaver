# P1 toolchain spike: native QRhi rendering in the SRPSS PySide6 process

Throwaway spike for the Graphics Backend Decision's piece B (P1, go/no-go). Findings and the verdict are in
`Docs/Future_Work/Native_Core_P1_Spike.md`. Nothing here is product code.

## What it builds

`_srpss_native_spike.pyd`: a plain CPython extension module (stable ABI, abi3, Python >= 3.10) compiled with
MSVC against the Qt 6.11.2 SDK, which is the exact Qt that PySide6 6.11.2 ships. It loads into our PySide6 process and
binds to PySide6's own `Qt6Core.dll`/`Qt6Gui.dll` (and `Qt6Qml.dll`/`Qt6Quick.dll` for part B). It refuses to import
under any other Qt version. Shaders (GLSL 440 compiled by PySide6's `qsb.exe` to SPIR-V, HLSL 5.0 and GLSL) are
embedded in the module, so a frozen build needs no data files.

| Part | Host | Needs |
| --- | --- | --- |
| A, `rhi` / `gil` | a standalone `QRhi` on a native `QThread`, offscreen, every backend | qtbase SDK |
| hybrid | Qt Quick (`QQuickRenderControl`, never shown) hosts a PySide6 `QSGRenderNode` whose `prepare()`/`render()` call the module, which records into Quick's own `QRhi` command buffer | qtbase SDK |
| B, `quick` | a C++ `QQuickItem` + C++ `QSGRenderNode` (`import SrpssNativeSpike 1.0; QuadField {}`), registered by the module at import, rendered by `QQuickRenderControl` on a separate render thread | qtbase + qtdeclarative SDK |

All parts draw the same 4096 instanced, animated dots (`src/quadfield.*`) and read the last frame back to a PNG.

## Building it: on GitHub only

Since 12 Nov 2026 the module is compiled only by `.github/workflows/native-module.yml` on GitHub's Windows runner
(operator: builds happen only through GitHub workflows, never on this machine). The lead runs
`tools/build_runner.py --mode github --run --select native_module`; the validated module lands in
`release\native_module\` of the checkout the tool runs from. The SDK fetch below is now
`tools/native_sdk_fetch.py` (the pins, sha256-checked before extraction), and `build.cmd` is the workflow's one CMake
invocation. Everything (the lead's command, what the runner checks, how a C++ slice iterates) is in
`Docs/Guides/GitHub_Remote_Build.md`, section "The native module". The sections below record the P1 spike's local
toolchain and commands as they were run on 7 Nov 2026.

## Toolchain on the reference machine (7 Nov 2026)

- PySide6 / shiboken6 6.11.2, Qt 6.11.2 (`MSVC 2022`, built with cl 19.44.35227), CPython 3.14.8 x64.
- Visual Studio Build Tools 2026 (18.9), MSVC 14.51.36231, Windows SDK 10.0.26100.0, CMake 4.1.2.
- No Vulkan SDK (not needed): Vulkan loader 1.4.341 from the NVIDIA driver; Vulkan-Headers v1.4.341 for `vulkan.h`.
- Ninja 1.13.2 and py7zr 1.1.4 in a tool venv `D:\Temp\Scratch\SRPSS\native_spike\venv` (never the repo `.venv`).
  aqtinstall 3.3.0 cannot read the Qt 6.11.2 repository layout (`Updates.xml` moved under
  `qt6_6112/qt6_6112_msvc2022_64/`), so the archives are fetched directly and checked against Qt's `.sha256`.

## SDK layout (D:\Temp\Scratch: downloads and SDKs never go on X: or F:)

```
D:\Temp\Scratch\SRPSS\native_spike\
  venv\                     tool venv: ninja, py7zr
  qt\                       Qt 6.11.2 msvc2022_64 prefix (qtbase; qtdeclarative extracts into the same prefix)
  vulkan_headers\Vulkan-Headers-1.4.341\include
  build\                    CMake/Ninja build tree; _srpss_native_spike.pyd
```

Fetch (PowerShell; `$B` is the Qt repository folder for the package):

```powershell
$B = "https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_6112/qt6_6112_msvc2022_64/qt.qt6.6112.win64_msvc2022_64"
$stamp = "6.11.2-0-202608131017"
$tail = "-Windows-Windows_11_24H2-MSVC2022-Windows-Windows_11_24H2-X86_64.7z"
# qtbase: 39,618,573 bytes, sha256 fd984b7264361b4dd3fd2a417702ca1258e4086268f2ee6a69b9a393d9c3f6bb
# qtdeclarative: 172,484,222 bytes (part B only; needs the operator's approval)
foreach ($m in "qtbase", "qtdeclarative") {
  curl.exe -L -o "D:\Temp\Scratch\SRPSS\native_spike\downloads\$m.7z" "$B/$stamp$m$tail"
  curl.exe -L -o "D:\Temp\Scratch\SRPSS\native_spike\downloads\$m.7z.sha256" "$B/$stamp$m$tail.sha256"
  (Get-FileHash "D:\Temp\Scratch\SRPSS\native_spike\downloads\$m.7z" -Algorithm SHA256).Hash   # compare with the .sha256
  D:\Temp\Scratch\SRPSS\native_spike\venv\Scripts\python.exe -I -c "import py7zr,sys; py7zr.SevenZipFile(sys.argv[1]).extractall(sys.argv[2])" "D:\Temp\Scratch\SRPSS\native_spike\downloads\$m.7z" D:\Temp\Scratch\SRPSS\native_spike\qt
}
# Vulkan-Headers v1.4.341 (3,092,442 bytes zip, sha256 c3b074a30b5bce4cf32a41d234fa559ff458513b7314d69cd0b336a01b53bb78)
curl.exe -L -o D:\Temp\Scratch\SRPSS\native_spike\downloads\vkh.zip https://codeload.github.com/KhronosGroup/Vulkan-Headers/zip/refs/tags/v1.4.341
D:\Temp\Scratch\SRPSS\native_spike\venv\Scripts\python.exe -I -c "import zipfile,sys; z=zipfile.ZipFile(sys.argv[1]); z.extractall(sys.argv[2], [n for n in z.namelist() if '/include/' in n])" D:\Temp\Scratch\SRPSS\native_spike\downloads\vkh.zip D:\Temp\Scratch\SRPSS\native_spike\vulkan_headers
# the downloads\ folder can be deleted after extraction
```

## Build

```bat
:: part A + hybrid only (qtbase SDK)
native\spike_p1\build.cmd D:\Temp\Scratch\SRPSS\native_spike\build OFF F:\Programming\Apps\ShittyRandomPhotoScreenSaver\.venv
:: everything, once qtdeclarative is in the prefix
native\spike_p1\build.cmd D:\Temp\Scratch\SRPSS\native_spike\build ON F:\Programming\Apps\ShittyRandomPhotoScreenSaver\.venv
```

`build.cmd` finds the newest Visual Studio with the x64 C++ tools with `vswhere`, calls its `vcvars64.bat`, then CMake
(Ninja, Release) with `CMAKE_PREFIX_PATH` = the Qt prefix,
`Python_EXECUTABLE` = the repo venv, `SPIKE_QSB` = PySide6's `qsb.exe` and `SPIKE_VULKAN_INCLUDE`. CMake stops if the
SDK's Qt version differs from 6.11.2. The `GuiPrivate` warning is expected: QRhi is semi-public API.

## Run (offscreen, repository venv)

```bat
.venv\Scripts\python.exe native\spike_p1\python\run_spike.py --module-dir D:\Temp\Scratch\SRPSS\native_spike\build --part all --label p1
:: the module built on GitHub
.venv\Scripts\python.exe native\spike_p1\python\run_spike.py --module-dir release\native_module --part all --label p1
```

`python/import_check.py` is the GPU-free part the runner runs after compiling (import, `runtime_info()`, the Qt DLLs
loaded from PySide6's folder); every part of `run_spike.py` needs a GPU device.

The backend is chosen inside each process (`QQuickWindow.setGraphicsApi` before `QGuiApplication`; Qt Quick parts run
one child process per backend). Evidence (PNGs + `summary.json`) goes to
`.artifacts/evidence/architecture/native_core_p1/<date>_<label>/` through `tools/artifact_paths.py`.

## Nuitka probe (operator only; agents never build frozen)

Stage the module next to the two scripts and compile a standalone probe on the scratch drive:

```bat
set STAGE=D:\Temp\Scratch\SRPSS\native_spike\frozen_stage
mkdir %STAGE%
copy native\spike_p1\python\frozen_probe.py %STAGE%\
copy native\spike_p1\python\run_spike.py %STAGE%\
copy D:\Temp\Scratch\SRPSS\native_spike\build\_srpss_native_spike.pyd %STAGE%\
cd /d %STAGE%
F:\Programming\Apps\ShittyRandomPhotoScreenSaver\.venv\Scripts\python.exe -m nuitka --standalone --msvc=latest ^
  --enable-plugin=pyside6 --include-qt-plugins=qml --include-module=PySide6.QtQuick --include-module=PySide6.QtQml ^
  --include-module=_srpss_native_spike --output-dir=D:\Temp\Scratch\SRPSS\native_spike\frozen_out frozen_probe.py
D:\Temp\Scratch\SRPSS\native_spike\frozen_out\frozen_probe.dist\frozen_probe.exe --out <evidence dir> --part hybrid --backend vulkan
D:\Temp\Scratch\SRPSS\native_spike\frozen_out\frozen_probe.dist\frozen_probe.exe --out <evidence dir> --part rhi
```

Pass: the JSON reports `"frozen": true`, `ok` on each backend, and `loaded_modules` shows `Qt6Gui.dll` from the
`.dist` folder (one copy), with PNGs matching the unfrozen ones.
