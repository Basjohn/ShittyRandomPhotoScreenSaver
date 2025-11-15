# Direct3D11 Migration Plan

## Summary
- **Primary backend target:** Native Direct3D 11 renderer integrated with Qt Widgets via HWND embedding and DXGI flip-model swap chains.
- **Fallback path:** Maintain OpenGL hardware renderer as the only automatic fallback (emits red debug overlay on activation) and keep a software renderer available as a deliberate troubleshooting mode.
- **Key objectives:** Eliminate GL-driven flicker/downgrades, gain deterministic swap control, enable richer GPU transitions while maintaining widget overlays, and offer three explicit rendering modes (Direct3D 11 hardware premium path, OpenGL hardware legacy path, Software CPU path).

> **Decision rationale:** Qt’s RHI Direct3D path would require porting the UI to Qt Quick/SceneGraph, limiting low-level control over swap intervals and shader pipelines. A native D3D11 renderer gives full swapchain control, better tooling (PIX), and direct mapping for our GLSL transition shaders to HLSL with minimal runtime abstraction.

## Goals
- Stable, flicker-free rendering at configured refresh rates with verified triple buffering/vsync control.
- Backend-agnostic transition infrastructure supporting both D3D11 and legacy OpenGL until deprecation.
- Straightforward pathway to advanced transitions (compute, geometry shader effects).
- Explicit diagnostics and fallback handling for unsupported hardware or initialization failures.
- Reinforce centralized architecture: renderer/transition modules plug into existing ThreadManager, ResourceManager, and EventSystem without introducing ad-hoc timers or locks.

## Assumptions & Dependencies
- Target platform: Windows 10+ (DXGI 1.3+, Direct3D 11.1 availability assumed).
- Python packaging updated to ship HLSL shaders (compiled to bytecode via `fxc`/`dxc`).
- Ability to host a native child window per display for the D3D swap chain inside the existing Qt window hierarchy.
- ThreadManager can schedule render loop callbacks without conflicting with D3D present intervals (use SPSC queues/atomics; avoid new locks or unmanaged timers).
- Settings manager and GUI can expose backend toggles and diagnostic overrides without breaking existing configuration exports.

## Workstreams

### 1. Renderer Abstraction Layer
- Define backend-agnostic interfaces (`RendererBackend`, `RenderTarget`, `GpuTexture`, `TransitionPipeline`).
- Refactor `DisplayWidget` to depend on the abstraction rather than `QOpenGLWidget` subclasses.
- Implement backend selection logic via settings (default D3D11, fallback OpenGL) with runtime detection/logging; only one backend (D3D11 HW, OpenGL HW, or Software) can be active at a time.
- Ensure resource managers and transition builders query the active backend for texture creation, shader loading, framebuffer operations.
- Route all render loop scheduling through `core.threading.manager.ThreadManager` (no raw `QTimer` usage); leverage existing SPSC queues/atomics for frame tasks.

### 2. Direct3D11 Rendering Core
- Build initialization module: device, immediate context, DXGI factory, swap chain (flip discard, double/triple buffering as required).
- Implement render target creation (RTV, DSV) matching monitor dimensions/DPI; support resizing.
- Establish frame loop: BeginFrame → Execute active transition pipeline → Composite overlays → Present with chosen sync interval.
- Manage synchronization: GPU fences if multi-threaded command recording introduced.
- Port image upload path: convert Qt `QImage`/`QPixmap` to staging textures, update GPU resources (mip generation if desired).
- Device manager blueprint:
  - COM bootstrapping layer leveraging `ctypes` (prefer `comtypes` if available) to create `IDXGIFactory2`, enumerating adapters to prefer high-performance GPU.
  - `D3D11CreateDevice` invocation requesting feature levels 11.1 → 11.0 → 10.x fallback, capturing debug layer availability in debug builds.
  - Swap-chain creation via `IDXGIFactory2.CreateSwapChainForHwnd` configured for flip-discard, buffer count selectable (2 vs 3) based on settings; Direct3D path must fail fast rather than downgrading silently.
  - RTV/DSV cache management with resize helper that rebinds render targets after `ResizeBuffers`.
  - ThreadManager integration hook to ensure Present is scheduled via UI-thread safe callback.

### 3. Transition Pipeline Porting
- Inventory existing GL transitions (Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip, Blinds).
- Translate GLSL shaders to HLSL; decide shared constant buffer layout.
- Implement pipeline states: input assembler (fullscreen quad), vertex shader, pixel shader; optionally compute shaders for complex effects.
- Support per-transition uniforms (timing, easing, direction) via constant buffers updated each frame.
- Validate multi-monitor: unique swap chain per display, transitions execute with isolated context.

### 4. Overlay & UI Integration
- Choose composition strategy:
  - Option A: Render overlays (clock, weather) onto intermediate textures via Qt → shared handle and composite in D3D pixel shader.
  - Option B: Use DirectComposition layers for overlays, keeping Qt widgets but ensuring z-order and transparency.
- Ensure mouse/keyboard events still originate from Qt window while render child handles GPU output.
- Update overlay manager to raise overlays appropriately depending on backend.
- Validate overlays continue to use centralized managers (ThreadManager, ResourceManager) and emit events via EventSystem when lifecycle changes.

### 5. Diagnostics & Fallback Handling
- Add startup checks: log D3D feature level, swap chain details, vsync/triple buffer status.
- Direct3D 11 backend must surface fatal errors (EventSystem + dialog/overlay guidance) and require user action; no automatic downgrade.
- OpenGL backend may automatically fall back to Software renderer on failure, logging `[CRITICAL] Falling back to Software renderer` and rendering red debug overlay text explaining the downgrade.
- Introduce settings flag to force fallback for troubleshooting.
- Ensure fallback notifications propagate through EventSystem for telemetry/log consumers.

### 6. Testing & QA
- Unit/integration tests for backend selection, renderer initialization, transition output validation (image diff where possible).
- Performance profiling: measure frame times with PIX; confirm absence of flicker across monitors and refresh rates.
- Regression tests ensuring OpenGL fallback still functional until decommissioned.

### 7. Documentation & Tooling
- Update `Docs/05_DISPLAY_AND_RENDERING.md`, `Docs/06_TRANSITIONS.md`, `Docs/FlashFlickerDiagnostic.md` with D3D info. *(2025-11-14: Documented backend diagnostics/UI progress)*
- Create developer setup guide for shader compilation tools (fxc/dxc) and PIX usage.
- Adjust packaging scripts to ship D3D shader binaries and optional `d3dcompiler_47.dll` if required.
- Document centralized architecture expectations (ThreadManager, ResourceManager, EventSystem usage) for new backend contributors.

### 8. Settings & Configuration Integration
- Extend `core.settings.settings_manager` schema to include backend selection, vsync/triple buffering overrides, and diagnostic toggles.
- Update settings serialization/deserialization to persist backend choice; ensure defaults drive D3D11 while keeping OpenGL available as fallback.
- Modify `ui.settings_dialog` / `ui.tabs.transitions_tab` (or new rendering tab) to expose backend toggle, explaining fallback semantics and debug behavior. *(2025-11-14: Display tab now surfaces preferred backend dropdown + "force legacy" switch tied to SettingsManager.)*
- Wire settings change events through EventSystem so renderer backend can hot-switch safely (or request restart).
- Audit spec docs to reflect new configuration options and fallback messaging.
- New controls:
  - `display.render_backend` defaulting to `d3d11` (already implemented in core + UI wiring 2025-11-14).
  - `display.force_legacy_backend` boolean override to pin legacy OpenGL (default False, UI toggle added 2025-11-14).

## Live Checklist

### Backend Abstraction
- [x] Draft renderer interface definitions (`RendererBackend`, `RenderSurface`, `TransitionPipeline`).
- [ ] Refactor `DisplayWidget` to request backend-specific render views instead of `QOpenGLWidget`.
- [x] Update settings manager & UI to expose backend toggle (default D3D11, fallback OpenGL) and centralize reads via SettingsManager.
- [x] Implement backend factory + detection with structured logging.
- [ ] Ensure render loop scheduling uses ThreadManager single-shot / recurring tasks instead of raw timers.

### Direct3D11 Core
- [x] Create `rendering/d3d11/device_manager.py` (device + swap chain init) with flip-model configuration.
- [x] Establish ctypes-based device initialization (D3D11CreateDevice + IDXGIFactory2) with diagnostics logging (2025-11-14).
- [ ] Implement render loop (`begin_frame`, `draw_transition`, `composite_overlays`, `present`).
- [ ] Add texture upload pipeline (Qt image → staging resource → shader resource view).
- [ ] Handle resize/fullscreen changes and DPI scaling.

### Transition Re-Implementation
- [ ] Translate GLSL shaders to HLSL for each transition (Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip, Blinds).
- [ ] Standardize constant buffer layouts and transition parameter structs.
- [ ] Build shader compilation scripts (fxc/dxc) integrated into build process.
- [ ] Validate each transition visually (compare against GL reference captures).

### Overlay & Composition
- [ ] Prototype DirectComposition or texture-based overlay compositing strategy.
- [ ] Ensure clock/weather render correctly over D3D output with correct z-order and raises when needed to match transition behaviour.
- [ ] Integrate overlay manager with backend abstraction for show/hide/resize.
- [ ] Verify overlays continue to register with ResourceManager/EventSystem; avoid ad-hoc timers.

### Diagnostics & Fallbacks
- [ ] Implement startup diagnostics logging feature level, swap interval status, VSYNC mode.
- [ ] Create red debug overlay text when falling back to OpenGL (only enabled in debug mode but present in release logs).
- [x] Add telemetry counters for backend selection & fallback occurrences (2025-11-13: exposed via `rendering.backends.get_backend_diagnostics`).
- [x] Emit EventSystem notifications when backend switches or falls back (2025-11-13: implemented via `rendering.backends.create_backend_from_settings`).
- [x] Display backend fallback overlay in DisplayWidget when OpenGL/software engages (2025-11-14: `transitions.overlay_manager.show_backend_fallback_overlay`).

### Testing & Tooling
- Establish automated smoke test launching D3D backend and validating first transition.
- Document PIX workflow for reproing flicker/perf issues.
- Update CI/build to bundle compiled HLSL shaders and validate their presence.
- Unit tests:
  - `tests/test_rendering_backends.py` covering backend registry fallback paths and force-legacy flag.
  - [x] `tests/test_d3d11_device_manager.py` ensuring device creation semantics using fake DLLs (2025-11-14).
  - [ ] Device manager initialization mock tests once COM layer added (use monkeypatch to simulate success/failure).
  - [ ] RenderSurface begin/end/present sequencing tests once frame loop stub is ready.

### Documentation
- [ ] Update `INDEX.md` with new D3D modules and architecture notes.
- [ ] Revise `FlashFlickerDiagnostic.md` to reflect D3D migration strategy and fallback messaging.
- [ ] Produce developer onboarding doc for D3D backend (toolchain setup, coding standards, centralization expectations).
- [ ] Update Spec.md/settings docs to cover backend toggle defaults and fallback behavior.

## Pitfalls & Mitigations
- **Qt + Native Window Embedding:** QWidget parenting quirks can cause focus/input issues. Mitigation: Use `QWindow.fromWinId` or `QWidget::createWindowContainer` carefully and test focus transitions.
- **Synchronization Bugs:** Present with improper sync interval can still tear; rely on DXGI frame statistics and PIX to validate vsync/triple buffering.
- **Shader Compilation:** Runtime compilation adds latency; precompile shaders and ship bytecode.
- **Resource Lifetime:** Ensure clean shutdown (release D3D resources before Qt destroys windows) to avoid device-removed errors.
- **Fallback Drift:** Keep OpenGL code path minimally maintained but instrumented; schedule periodic regression runs until officially deprecated.

## Next Steps
1. Review abstraction design with team; confirm module layout and coding standards.
2. Kick off backend abstraction refactor (parallelizable with shader porting).
3. Schedule D3D shader porting sprint; create visual test plan for each transition.
4. Plan milestone reviews: bring-up, transition parity, overlay integration, QA sign-off.

### Progress Log (2025-11-14)
- DisplayWidget first frame now bypasses GL transitions and seeds the base pixmap to eliminate startup black flicker.
- Backend fallback overlay added via `show_backend_fallback_overlay`, registering with ResourceManager and raising above transitions.
- GL surface format logging deduplicated (per reason) to avoid overlay spam.
- Settings dialog Display tab exposes backend choice + force legacy toggle, persisting to `SettingsManager`.
- D3D11 device manager now loads real system DLLs via ctypes, creates devices/factories, and tracks swap-chain descriptors with diagnostics and tests.

### Progress Log (2025-11-13)
- DisplayWidget now instantiates renderer backends via `create_backend_from_settings`, with automatic fallback to OpenGL if D3D11 init fails.
- Render surface lifecycle helpers added (`_ensure_render_surface`, `_destroy_render_surface`) with resize handling scaffolding, ready for swap-chain wiring once D3D device manager is implemented.
- Settings default now prefer D3D11 with force-legacy override; backend registry honors the override and is covered by new tests.
