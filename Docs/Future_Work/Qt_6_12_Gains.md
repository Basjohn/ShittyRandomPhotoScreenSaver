# Qt 6.12 / PySide6 6.12: what it gives SRPSS (research, 12 Nov 2026)

Documents-only research from primary sources (doc.qt.io, code.qt.io, qt.io). No project detail was sent anywhere.
Statements are "confirmed" when read on the cited page, "unconfirmed" otherwise. A class page that carries no
version note proves nothing about 6.12; "no 6.12 tag" below means exactly that.

Sources:
- S1 What's New in Qt 6.12: https://doc.qt.io/qt-6/whatsnew612.html
- S2 PySide6 6.12.0 changelog: https://code.qt.io/cgit/pyside/pyside-setup.git/plain/doc/changelogs/changes-6.12.0
- S3 QRhi: https://doc.qt.io/qt-6/qrhi.html
- S4 QRhiCommandBuffer: https://doc.qt.io/qt-6/qrhicommandbuffer.html
- S5 QRhiSwapChain: https://doc.qt.io/qt-6/qrhiswapchain.html
- S6 QSGRenderNode: https://doc.qt.io/qt-6/qsgrendernode.html
- S7 QQuickWindow: https://doc.qt.io/qt-6/qquickwindow.html
- S8 QQuickGraphicsConfiguration: https://doc.qt.io/qt-6/qquickgraphicsconfiguration.html
- S9 QAudioSink: https://doc.qt.io/qt-6/qaudiosink.html
- S10 Release post: https://qt.io/blog/qt-6.12-released

## Box 1: inventory

### QRhi (touches: Current_Plan item 8b native QRhi core, Vulkan front face, Neon Lake / Extruded Bubble / Spectrum draw paths)
| Item | What it is | Source | Touches |
|---|---|---|---|
| Indirect rendering | `QRhiCommandBuffer::drawIndirect(QRhiBuffer *indirectBuffer, quint32 indirectBufferOffset, quint32 drawCount, quint32 stride = sizeof(QRhiIndirectDrawCommand))` and `drawIndexedIndirect(..., stride = sizeof(QRhiIndexedIndirectDrawCommand))`, both "since 6.12", inside a render pass only. Command structs `QRhiIndirectDrawCommand`, `QRhiIndexedIndirectDrawCommand`. Stride must be a multiple of 4 and at least the struct size. A new buffer kind `IndirectDrawBuffer` is named in S1 (not found in the S3 text read; unconfirmed where the usage flag lives, check `QRhiBuffer::UsageFlag`). | S1, S4 | GPU-driven draw counts (instanced bubbles, ribbons, particles) without CPU readback |
| `QRhi::DrawIndirect` (51) | Enables the two calls. Expected everywhere except OpenGL ES below 3.1. | S3 | Gate: check before use; GL fallback path on this project is desktop GL so expected true |
| `QRhi::DrawIndirectMulti` (52) | `drawCount > 1` native with default stride; otherwise Qt emits CPU-side separate draws (no speed benefit). Expected on Vulkan 1.1+, GL 4.3+, D3D12. | S3, S4 | Multi-draw only pays off on Vulkan/GL/D3D12; D3D11 gets emulation |
| `QRhi::ShaderDrawParameters` (53) | `gl_BaseInstance`, `gl_BaseVertex`, `gl_DrawID` available in shaders. Expected Vulkan 1.1+, GL 4.6 / `GL_ARB_shader_draw_parameters`. | S1, S3 | Per-draw data lookup in a multi-draw batch |
| Vulkan `VK_EXT_device_fault` | Vulkan backend reports more detail on device loss. | S1 | Vulkan front face: crash/TDR diagnostics; only useful on drivers exposing the extension (unconfirmed which) |
| Already in 6.11 (not new) | `QRhi::DepthClamp` (50), `QRhi::InstanceIndexIncludesBaseInstance` (49). | S3 | Note only |
| Already earlier | `Timestamps` feature + `QRhi::EnableTimestamps` flag (opt-in) and `QQuickGraphicsConfiguration::setTimestamps` (6.6); `setShadingRate`/`supportedShadingRates`/`newShadingRateMap` (6.9, variable rate shading); `QRhi::enumerateAdapters()` (6.10); `setQueueSubmitParams` (6.9); `QRhiSwapChain` HDR `Format`s `HDRExtendedSrgbLinear`, `HDR10`, `HDRExtendedDisplayP3Linear`, and flags `SurfaceHasPreMulAlpha`/`SurfaceHasNonPreMulAlpha`, `UsedAsTransferSource`, `NoVSync`, `MinimalBufferCount`; stereo `StereoTargetBuffer`. | S3, S5 | Nothing new in 6.12 on swapchain HDR/alpha, formats, compute, readback, multiview: no 6.12 tag found on any of them. Confirmed that S5 says HDR needs the OS HDR switch on and depends on the screen the window is on, and on Windows scRGB linear is the compositor's native space. |
| DirectComposition / D3D12 alpha | Not mentioned on the swapchain, QRhi or What's New pages. Unconfirmed: nothing found. | S1, S5 | Translucent desktop window for SMP: no Qt-side change in 6.12 |

### Qt Quick and scene graph (touches: product QML host, Studio/Settings windows, protected QSG/clip commits)
| Item | What it is | Source | Touches |
|---|---|---|---|
| QSGRenderNode | No 6.12-tagged change. Doc still says: assume no active GL state in `render()`; only `ViewportState` and `ScissorState` matter; `NoExternalRendering` flag means QRhi-only; `commandBuffer()`/`renderTarget()` since 6.6; with Vulkan/Metal record copies in `prepare()`/`beforeRendering`. The page says nothing about VAO / `GL_ARRAY_BUFFER` restoration. | S6 | Matches the observed 6.12 array-buffer-binding change: the documented contract never promised it, so the inherited-state restore commit ccc19ef0 is the correct stance (the contract is "assume nothing"). Why the binding changed in 6.12: unconfirmed, no changelog entry found. |
| QQuickWindow / QQuickGraphicsConfiguration / QQuickGraphicsDevice | No 6.12 additions on either page. Newest tags: `QQuickWindow::devicePixelRatio` (+ `devicePixelRatioChanged`) is tagged "since 6.11"; configuration members max at 6.6 (`setTimestamps`, `timestampsEnabled`). | S7, S8 | Window DPR property is 6.11, usable now for mixed-DPR code instead of screen lookups |
| Text | `Text` renders `QTextCharFormat::UnderlineStyle` variants (dash, wave, spell-check) instead of always solid. | S1 | Only if the UI ever sets underline styles; low |
| Shapes | `ShapePath.strokeGradient` (new). | S1 | Studio/Settings vector decoration; possible alternative to hand-painted gradient borders (project rule: paint one continuous path, check seams) |
| Rectangle / AnimatedImage / VectorImage | `Rectangle.color = undefined` resets default; `AnimatedImage.loops`, `finishBehavior`, `finished`; `VectorImage.asynchronous`, `status`, `retainWhileLoading`, `generatedItem`; new `Color` singleton. | S1 | Minor UI conveniences |
| Canvas | Qt Canvas Painter module fully supported (QRhi, shader-based); `QtCanvas2D` QML element and `QCanvasCustomBrush` are Technology Preview. | S1, S10 | Not a render-node replacement; no plan item. Preview: do not adopt |
| Hot reload / Layouts / Controls | Built-in QML hot reload (`qmlpreview`), FlexBox layout, new Controls (Safe Area, Context Menu, Search Field, Double Spin Box), `QtQuick.Controls.Native` style, StyleKit (Qt Labs, `qtlabsstylekit`). | S10 | Dev iteration on Studio QML (hot reload); StyleKit is Labs, i.e. unstable |
| Threaded render loop, layers, ShaderEffect, QQuickRenderControl | No 6.12 entries found on What's New or the pages read. Not confirmed absent (the full qtdeclarative changelog `dist/changes-6.12.0` returned 404 on code.qt.io, so I could not read it). | S1 | Unconfirmed |
| Behaviour | A component with missing required properties now reports an error instead of silently building an incomplete object. | S1 | Watch (QML required properties in Studio/Settings) |

### Windowing on Windows (touches: translucent Settings/Studio, SMP desktop-through-material window)
| Item | What it is | Source | Touches |
|---|---|---|---|
| Screen colour space | Windows screen colour space is now derived from the display's ICC profile (`ColorProfileGetDisplayDefault`) instead of always sRGB. Only HDR-adjacent item. | S1 | `QScreen`/colour-managed image paths; Watch for colour shifts on wide-gamut monitors |
| DirectWrite | Reads the GASP table to pick antialiasing per font and size. | S1 | Text rendering sharpness on Windows; Watch (visual diff of UI text) |
| Shader disk cache | Re-enabled for current Intel drivers (driver version check). | S1 | Quick 3D perf on Intel; marginal |
| Manifest | `qt_add_executable()` generates a Windows 10/11 compat, long-path, UAC manifest (`QT_WINDOWS_APP_PROJECT_IDENTIFIER`, `QT_WINDOWS_APP_PROJECT_EXECUTION_LEVEL`). `windeployqt --appx`, `QOperatingSystemVersion::Windows11_25H2`. | S1 | C++ native core build only |
| DWM backdrop / Mica / Acrylic | Qt has no documented public API for system backdrops in 6.12; nothing in What's New or class pages. Practitioners call `DwmSetWindowAttribute` (`DWMWA_SYSTEMBACKDROP_TYPE`, Windows 11 22H2, build 22621+) on the HWND from `QWindow::winId()`, or use a wrapper such as QWindowKit. A Qt Centre thread reports a "phantom white box" with Mica and QML ApplicationWindow on Qt 6.10 (resolution not seen). | S1; Microsoft Learn https://learn.microsoft.com/windows/apps/windows-app-sdk/system-backdrop-controller ; https://qtcentre.org/threads/72280-Phantom-white-box-whilst-using-Application-Window-and-Windows-11-Mica-background-on ; https://github.com/stdware/qwindowkit/wiki | SMP desktop window: stays a project-owned Win32 call; no Qt help in 6.12 |
| Per-monitor DPR, frameless, high refresh | No 6.12 entries. (Qt 6.9 changelog items about a vblank-watcher thread for update requests on D3D11/12 are secondary-source only; unconfirmed.) | S1 | Nothing new |
| `QScreen::grabWindow()` | macOS-only behaviour change. | S1 | Not applicable |

### Multimedia / audio (touches: SMP docs `Docs/Future_Work/ShittyMusicPlayer/`)
| Item | What it is | Source | Touches |
|---|---|---|---|
| Native period size | `QAudioSink`/`QAudioSource` `qsizetype nativePeriodFrameCount() const` (-1 = unset) and `void setNativePeriodFrameCount(qsizetype)`. Values: powers of two 32..4096. Default platform-chosen, typically 1024 frames. Only while stopped. Maps to `IAudioClient::bufferDuration` on Windows. Suggested 64-256 low latency, 2048-4096 robust. Separate from `setBufferSize()`/`setBufferFrameCount()` ring buffer. Unconfirmed: whether it applies in both pull and push modes. | S1, S9 | SMP output latency / underrun trade; visualizer PCM sync (`03_PCM_Source_and_Native_Core_Seams`) |
| Capture | `QScreenCapture`/`QWindowCapture` `maximumFrameRate`. `QMediaCaptureSession::setNativeVideoSource()`. | S1 | Not relevant to SMP |
| Deprecation | `QMediaMetaData::ThumbnailImage` deprecated, use `CoverArtImage`. | S1 | SMP cover art reading: use `CoverArtImage` |
| Behaviour | `QSoundEffect` always emits `sourceChanged` after `setSource()`. | S1 | Only if used |
| Device selection / formats | No 6.12 entries. | S1 | Nothing new |

### Qt Quick 3D (project uses framed 3D; only listed because they exist)
`SkyMaterial`, `QuadTextureProvider` (QtQuick3D.Helpers, custom fragment shader quad), `Model.instancingLodFactor`, `ExtendedSceneEnvironment.ssrThickness`/`ssrMaxSteps`, `RuntimeLoader.query()/queryAll()`, physics joints, XR mono view. Source S1. Directly relevant: none found (project renders its own scene, not Quick 3D). `Model.instancingLodFactor` only if a Quick 3D path exists (unconfirmed).

### PySide6 6.12 (S2)
- No entry mentions `@Slot(result=...)`, QML signals to slots, or startup time. The recorded native crash (QML signal connected to a `@Slot(..., result=...)`, see `Docs/Reference/Visualizer_Studio.md` line 29 and the TestSuite note) has NO fix or mention in the 6.12.0 changelog: treat it as still live. Re-verify on 6.12 only with the existing negative-control test, not by assumption.
- New: `QtQmlFeatures` module (reactive properties `@auto_properties`, `@watch`, `@effect`, `@computed`, PYSIDE-3302): possible tidy alternative to hand-written property bridges; new and unproven.
- `QMetaObject::className()` returns dot-separated names for nested classes (PYSIDE-3294): Watch (code that matches class names).
- New warning for unknown signal parameters (PYSIDE-3364): Watch (log noise or a real typo).
- Bug fixes: private-method connections from derived classes (PYSIDE-3376), `QAbstractItemModel.data()` crash (PYSIDE-3423), `QStandardItemModel.clear()` leak (PYSIDE-3365), `QLayoutItem` stale pointer (PYSIDE-3409).
- Shiboken: free-threaded GIL type-system attribute (PYSIDE-2221); blocking functions such as `QEventLoop.exec()` markable (PYSIDE-3356); recursive `shibokenmodule.dump()` parent/child view (PYSIDE-3469, a debug aid for the detached-QML-item ownership work).
- Python: initial 3.15 support (PYSIDE-3221); 3.14 appears only as an Android host bound. 3.14 support itself is not stated in this changelog: unconfirmed (it was added in an earlier release, not verified).
- Deploy: `pyside6-deploy` defaults to standalone, `--onefile` restores old default (PYSIDE-3459), `[tool.pyside6.deploy]` in `pyproject.toml` (PYSIDE-1612); security fixes in deploy and `pyside6-qml` import warning (PYSIDE-3319). Relevant only if the project's packaging uses these tools (unconfirmed).

### Behaviour changes and deprecations summary (all from S1 unless noted)
Missing required QML properties now error; `QSoundEffect.sourceChanged` always emitted; `QMediaMetaData::ThumbnailImage` deprecated; Windows screen colour space from ICC; DirectWrite GASP; `qt_add_shaders()` messages moved to DEBUG; rcc content de-duplication (S10). OpenGL in Qt Quick: S1 has no OpenGL-specific entry.

## Box 2: recommendation

### Worth using (ranked)
1. Indirect draws: `QRhiCommandBuffer::drawIndirect`/`drawIndexedIndirect` gated by `QRhi::DrawIndirect`, multi-draw gated by `DrawIndirectMulti`, `gl_DrawID` via `ShaderDrawParameters`. Plan item: 8b N-steps (native QRhi core, Vulkan front face). Design the draw-submission layer with a CPU-emulated fallback, because D3D11 and old GL report no native multi-draw. Sources S3, S4.
2. `QAudioSink::setNativePeriodFrameCount()` for SMP output latency control (Windows maps to `IAudioClient::bufferDuration`). Plan item: SMP `02_ShittyMusicPlayer_Implementation_Plan.md` and `03_PCM_Source_and_Native_Core_Seams_2026-11-09.md` (visualizer PCM alignment). Source S9. Measure before choosing a value.
3. `VK_EXT_device_fault` reporting on the Vulkan backend: wire the device-lost log into the native core's diagnostics (opt-in only, no per-frame cost). Plan item: 8b Vulkan steps. Source S1.
4. `QQuickWindow::devicePixelRatio` (6.11) / `devicePixelRatioChanged` for mixed-DPR logic; and `QQuickGraphicsConfiguration::setTimestamps` + `QRhi::EnableTimestamps` for the benchmark tooling (older, but confirmed available). Plan items: 1B/1C perf harnesses. Sources S7, S8.
5. `QMediaMetaData::CoverArtImage` in SMP library code (avoid the deprecated `ThumbnailImage`). SMP plan. Source S1.
6. `ShapePath.strokeGradient` as an optional Studio/Settings border technique (must still pass the project's seam/zoom check). Source S1. Low priority.
7. QML hot reload for Studio QML iteration (developer tooling only). Source S10. Low.

### Watch
- QSGRenderNode GL state: the 6.12 scene graph sync changes `GL_ARRAY_BUFFER` binding (observed locally); S6 documents "assume no state" and has no 6.12 note, so keep restoring/measuring inherited state (as commit ccc19ef0 does). Cause unconfirmed.
- `@Slot(result=...)` from QML signals: no PySide 6.12 fix mentioned; the crash rule stays in force.
- Windows screen colour space from ICC profile: wide-gamut monitors may render image colours differently (screenshot/pixel oracles).
- DirectWrite GASP antialiasing: text pixels in Settings/Studio and pixel-compared captures may shift.
- Required-property errors in QML (previously silent).
- PySide6 `QMetaObject::className()` format change for nested classes; new unknown-signal-parameter warning.
- `QRhi::DrawIndirect` is "expected" everywhere but OpenGL ES < 3.1: still query the flag at runtime on every backend.
- Backdrop/Mica: no Qt API; any SMP desktop-through-material window is a project-owned `DwmSetWindowAttribute` plus window-attribute combination, with a known "phantom white box" class of problems in Qt Quick (see the Qt Centre thread). Prototype early.

### Could not confirm
- Full `dist/changes-6.12.0` files for qtbase and qtdeclarative (code.qt.io returned 404 for both tried URLs): so threaded render loop, layers, ShaderEffect, QQuickRenderControl, D3D12, Windows platform-plugin, DPI and DWM changelog items are unread. Only What's New, class pages, the PySide changelog and the release post were read.
- Why the GL array-buffer binding changed in 6.12.
- The `IndirectDrawBuffer` enum/usage flag exact location and `QRhiIndirectDrawCommand` field layout (S3/S4 link but did not show them).
- Python 3.14 status for PySide6 6.12, startup-time changes, and per-backend `DrawIndirectMulti` actual support on this hardware.
- Any 6.12 change to HDR swapchains, translucent/alpha swapchains, DirectComposition, mipmap/readback, compute, formats or multiview (none tagged 6.12 on the pages read).
- The Phoronix beta article (403) and Qt 6.9 vblank-thread note (secondary source only).
