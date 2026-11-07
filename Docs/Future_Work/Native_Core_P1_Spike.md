# Native render core, P1 toolchain spike (7 Nov 2026)

Answers P1 of the [Graphics Backend Decision](Graphics_Backend_Decision_2026-11-05.md) addendum: can a compiled
render path draw through Qt Quick's QRhi inside our PySide6 process, on Vulkan and D3D, and ship in the Nuitka
build? Spike sources and exact commands: `native/spike_p1/` (README). Evidence:
`.artifacts/evidence/architecture/native_core_p1/20261107_p1/` (8 PNGs + `summary.json`).

## Verdict: GO, with conditions

The toolchain works on this machine with what is installed plus one small SDK download (qtbase, 39.6 MB, on X:).
A native module built against Qt 6.11.2 loads into the PySide6 process, binds to PySide6's own Qt DLLs, and draws
through QRhi on D3D11, D3D12, Vulkan and OpenGL, both standalone and inside Qt Quick's own frame. A native render
thread is unaffected by a Python thread that holds the GIL throughout.

Conditions, before P3 starts:
1. The operator approves the Qt Quick/Qml SDK download (qtdeclarative, 172.5 MB, below) so part B (C++
   `QSGRenderNode` + QML registration, sources written) can be compiled and run. This is the one unbuilt piece.
2. The operator runs the Nuitka probe (`native/spike_p1/README.md`, "Nuitka probe"). Agents do not build frozen.
3. The production core keeps a build guard on the MSVC runtime (below).

## Verified on this machine

| Check | Result |
| --- | --- |
| Versions | PySide6/shiboken6 6.11.2; Qt 6.11.2 (cl 19.44.35227, MSVC 2022); CPython 3.14.8; VS Build Tools 2026 18.9, MSVC 14.51.36231; Windows SDK 10.0.26100.0; CMake 4.1.2; Nuitka 4.2 (repo venv); Vulkan loader 1.4.341 (driver); no Vulkan SDK; GPU RTX 4090, driver 617.42 |
| Qt headers/libs | None in PySide6 (it ships only PySide wrapper headers). qtbase 6.11.2 msvc2022_64 from the Qt repository, sha256-verified, gives QtCore/QtGui headers incl. `rhi/qrhi.h`, import libs, moc and the CMake package |
| Exports | PySide6's `Qt6Quick.dll` exports everything part B uses (`QSGRenderNode::commandBuffer/renderTarget/projectionMatrix`, `QQuickWindow::rhi`, `QQuickRenderControl::prepareThread/rhi`, `QQuickRenderTarget::fromRhiRenderTarget`); `Qt6Qml.dll` exports `QQmlPrivate::qmlregister` |
| Build | CMake + Ninja + MSVC 14.51, `/W4` clean; `.pyd` 71 KB; imports only `python3.dll`, `Qt6Core.dll`, `Qt6Gui.dll`, `vcruntime140(_1).dll`, UCRT; **no `msvcp140.dll`** |
| ABI | In process, `Qt6Core/Gui.dll` resolve to PySide6's copies (one each); compile-time and runtime Qt both 6.11.2; the module refuses to import under another Qt |
| Shaders | PySide6's own `qsb.exe` compiles GLSL 440 to SPIR-V + HLSL 5.0 + GLSL; the `.qsb` bytes are embedded in the module |
| Part A, standalone QRhi | 4096 instanced dots, 960x540, read back to PNG on **D3D11, D3D12, Vulkan, OpenGL**; cross-backend max pixel difference 0-2/255 |
| Hybrid, inside Qt Quick | `QQuickRenderControl` (never shown) hosts a PySide6 `QSGRenderNode` whose prepare/render pass Quick's own `QRhi`, command buffer and render target to the module, which records the draw: correct PNGs on **D3D11, D3D12, Vulkan, OpenGL**, cross-backend max difference 0-3/255, clean process exit |
| GIL | Native render thread, 240 frames: median 0.025 ms with Python idle, 0.018 ms while a pure-Python loop held the GIL (2.5 M iterations meanwhile); the thread never had a Python thread state. Negative control, the same thread taking the GIL once per frame (what a Python `render()` does): 0.023 ms idle, **5.06 ms** median (p90 5.55) with Python busy, i.e. one 5 ms switch interval per frame. Timings are CPU-side times of a tiny offscreen frame, a functional contrast only, not a GPU measurement |
| Backend selection today | `rendering/quick/bootstrap.py` `configure_quick_graphics()`: `QQuickWindow.setGraphicsApi(OpenGL)`, `QSG_RENDER_LOOP=threaded` set in-process, `AA_UseDesktopOpenGL`, GL 4.6 core surface format; `rendering/quick/render/native_texture_bridge.py` rejects non-GL APIs |

## Analysed, not verified

- **Part B** (`src/quick_item.*`, `src/quick_offscreen.*`): a C++ `QQuickItem` + `QSGRenderNode` (`NoExternalRendering`,
  QRhi only) registered at import as `SrpssNativeSpike 1.0 / QuadField`, rendered by `QQuickRenderControl` with
  sync/render on a separate render `QThread` while the GUI thread blocks during sync, plus the same GIL contention
  check. Written, not compiled: needs the qtdeclarative SDK.
- **Qt's real threaded render loop** with an exposed window: by design it calls `prepare()`/`render()` on its render
  thread; an on-screen run is the operator's (agents never show windows).
- **Nuitka standalone** (Nuitka 4.2 source read): the module is followed as an ordinary extension import. Nuitka's DLL
  scanner looks in the binary's own folder, the package folder, the Python folder, the MSVC redist and PATH, so the
  module's `Qt6*.dll` imports are not found from `rendering/...` and are skipped silently. That is harmless because
  PySide6's `.pyd` files pull the same `Qt6*.dll` into the dist root (destination = basename), the app directory is
  first in the loader's search order, and a DLL already loaded by name is reused. Requirements: import
  `PySide6.QtQuick` before the module; keep `--include-module=PySide6.QtQuick/QtQml` and `--include-qt-plugins=qml`
  (already in `scripts/venv/build_nuitka.ps1`); never put another Qt `bin` on PATH during the build (two copies of
  one DLL name). `python3.dll` is already shipped for PySide6 (also abi3). No data files: shaders are embedded and the
  QML type is registered from C++ (no `qmldir`, no QML plugin). `vulkan-1.dll` and `d3d*.dll` come from the system.
- **Mixed migration window:** a QRhi-native node and today's Python raw-GL nodes in one OpenGL window (Qt wraps
  non-`NoExternalRendering` nodes in `beginExternal`/`endExternal`). Exercised for real by the first P3 port.

## Binding approach: plain CPython extension module (abi3), no shiboken binding

- The module only needs Python for setup (register the QML type, attach a `QVulkanInstance`, hand over shared-memory
  names in P2). Per-frame work never crosses into Python, so there is no C++ API to wrap.
- PySide6 objects reach C++ as raw pointers from `shiboken6.getCppPointer()`, and back via `shiboken6.wrapInstance()`.
  Verified with `QQuickRenderControl`, `QQuickWindow`, `QRhi`, `QRhiCommandBuffer` and `QRhiTextureRenderTarget`.
- **Rejected, shiboken6-generated binding:** needs `shiboken6_generator` plus libclang (not on PyPI, large), ties the
  module to the exact shiboken ABI, and buys nothing here.
- **Rejected for now, `QQmlEngineExtensionPlugin` from a QML import path:** works in principle, but Nuitka does not
  follow it (the DLL and `qmldir` must be hand-added as data), and a Python-side module is still needed for setup.
- **Ownership caveat:** PySide6 6.11 exposes neither `QVulkanInstance` nor `QQuickWindow.setVulkanInstance`; the module
  attaches the instance (`vulkan_attach`). PySide temporaries can dangle (`rhi.driverInfo().deviceName` raised
  "already deleted" until the value was kept alive): RHI introspection belongs in C++.

## Installs needed (operator approval)

| Item | Version | Source | Size | Location |
| --- | --- | --- | --- | --- |
| **Qt Quick/Qml SDK (qtdeclarative, MSVC 2022 x64)** | 6.11.2 (`6.11.2-0-202608131017`) | `https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_6112/qt6_6112_msvc2022_64/qt.qt6.6112.win64_msvc2022_64/6.11.2-0-202608131017qtdeclarative-Windows-Windows_11_24H2-MSVC2022-Windows-Windows_11_24H2-X86_64.7z` (+ `.sha256`) | 172.5 MB download | extracted into `X:\Scratch\SRPSS\native_spike\qt` (no system install) |
| Optional: MSVC v143 14.44 toolset (VS Build Tools component) | 14.44 | Visual Studio Installer | about 1-2 GB | system-wide; only if the core must use STL DLL features (see runtime guard) |

Already fetched without approval (under the 50 MB limit, scratch drive only): qtbase 6.11.2 (39.6 MB, sha256
`fd984b72...c3f6bb`), Vulkan-Headers v1.4.341 (3.1 MB). Not needed: the Vulkan SDK, a new CMake, aqtinstall (3.3.0
cannot read the 6.11.2 repository layout; archives are fetched directly).

## Risks for P2 and P3

1. **The GIL leaves the render thread only when no Python runs there at all.** Today Python runs on the render thread
   in `updatePaintNode` (visualizer item, background item, surface backdrop, Studio viewport, all during sync), in the
   Python `QSGRenderNode` subclasses, in the visualizer retirement `beforeRendering` one-shot, and in the frame-trace
   `DirectConnection` hooks (diagnostics only). PySide wrapper classes also take the GIL on the first virtual call per
   method. P3 must make every item in the window native (or GIL-free) before the full gain shows; the spike's thread
   probe (calls with a Python thread state) is the check.
2. **QRhi 6.11 has no indirect draws.** `rendering/quick/scene3d/population.py` uses `glDrawArraysIndirect` for
   GPU-driven counts. Options: draw the maximum count and cull in the vertex shader, read counts back with a frame of
   latency, or a per-backend native command through the RHI native handles (breaks single-core neutrality). Decide at
   the Extruded Bubble port. Persistent mapping maps to QRhi dynamic buffers; image load/store and compute exist;
   geometry shaders (`scene3d/probe.py` prefilter) are a per-backend QRhi feature: check D3D support there.
3. **QRhi has limited compatibility guarantees.** The core is rebuilt for every PySide6/Qt release in lockstep (CMake
   and import-time checks enforce the exact version). The SDK fetch must be scripted per version.
4. **MSVC runtime in process:** the compiler is 14.51, but the `msvcp140.dll` loaded is shiboken6's 14.44 copy
   (`vcruntime140` is Python's 14.51). Code built with a newer toolset than the loaded `msvcp140` is unsupported. The
   spike imports nothing from `msvcp140`; the core needs a build guard (fail if the module imports an `msvcp140`
   symbol the bundled copy lacks) or the v143 14.44 toolset.
5. **Clip and the protected QSG/clip optimisations:** a native node must honour Quick's scissor/stencil clip
   (`RenderState`, pipeline `UsesScissor`/`UsesStencilRef`); the spike ignores clip. Parity with the clip/render-node
   oracles is part of each port, never a reason to retune the protected optimisations.
6. **Shader start-up:** `.qsb` holds HLSL source, so D3D compiles at first use (the slowest frame of each run, the
   one creating the pipeline, took 4-26 ms here, against well under 1 ms for the others). Precompile DXBC/DXIL (`qsb -c` with the Windows SDK's fxc/dxc) and use the QRhi pipeline
   cache; warm up per the gradual warm-up rules. PySide6's `qsb.exe` already satisfies port-readiness rule 5 (a
   SPIR-V compile test), with no extra SDK.
7. **P2 packet layout:** the native core will read the worker's shared-memory packets directly, so the layout must be
   C-compatible and versioned (fixed-width fields, explicit alignment, sequence/generation counters readable without
   Python). Settings snapshots stay versioned; one Visualizer at a time.
8. **The Vulkan flip:** an on-screen Vulkan window needs a `QVulkanInstance` that PySide6 cannot create; the native
   module provides it. Verify on the real window at the flip; GL stays the fallback setting until acceptance.

## Proposed text for `Current_Plan.md` §1 item 8b (for the lead to apply)

> - P1: GO with conditions (7 Nov, `Docs/Future_Work/Native_Core_P1_Spike.md`): a native abi3 module built against
>   Qt 6.11.2 draws through QRhi on D3D11/D3D12/Vulkan/OpenGL standalone and inside Qt Quick's frame, bound to
>   PySide6's Qt DLLs; a native render thread is unaffected by a GIL-holding Python thread. Open: operator approval of
>   the qtdeclarative 6.11.2 SDK (172.5 MB, X:) to build part B (C++ `QSGRenderNode` + QML type), and the operator's
>   Nuitka probe run.
