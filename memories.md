# Project Memories

Curated internal policies and recurring context for ShittyRandomPhotoScreenSaver (SRPSS).

## 1. Logging & Performance Instrumentation
- **Perf gating:** All performance/profiling output must be behind `SRPSS_PERF_METRICS=1` using `core.logging.logger.is_perf_metrics_enabled()`. Never emit PERF logs (including widget timing, transition guards, worker FFT/image traces) without the gate.
- **Log routing:** Use the centralized handlers in `core/logging/logger.py`:
  - `screensaver.log` (INFO+, main app)
  - `screensaver_verbose.log` (DEBUG/INFO trace, referenced when console suppresses output)
  - `screensaver_perf.log` (records `[PERF]` metrics only)
  - `screensaver_spotify_vis.log` / `screensaver_spotify_vol.log` for Spotify visualizer & volume modules
  - All use `DeduplicatingRotatingFileHandler` (1 MB files, duplicate suppression, thread-safe).
- **Perf tags:** Follow existing tags (`[PERF_WIDGET]`, `[PERF][MEDIA_FEEDBACK]`, `[SPOTIFY_VIS]`, `[SPOTIFY_VOL]`). Route new widget telemetry through existing tags instead of inventing new ones.
- **Worker diagnostics:** Image worker / FFT logs and similar heavy traces are disallowed unless the PERF gate is enabled.
- **Performance baselines:** Keep `Docs/PERFORMANCE_BASELINE.md` current with dt/fps targets, env vars, and regression steps before landing perf-related changes.
- **Iterative perf runs:** When investigating performance, run the saver for ~15 s, capture logs, kill the process, inspect *all* logs, fix issues, and repeat until satisfied.

## 2. Threading, Resources, and Settings
- **Central managers only:** Use `core/threading/manager.ThreadManager` for *all* business threading (IO/compute pools, UI callbacks), `core/resources/manager.ResourceManager` for Qt lifecycle, `core/settings/settings_manager.SettingsManager` plus its shared `EventSystem`, and `core/animation/animator.AnimationManager` for animations. Never spin raw `threading.Thread`, `ThreadPoolExecutor`, or unmanaged `QTimer`/`QPropertyAnimation` instances.
- **Thread safety checklist:**
  - Protect shared flags with simple `threading.Lock`/`RLock` only when needed.
  - All Qt/UI mutations must go through `ThreadManager.invoke_in_ui_thread()`.
  - Keep business logic off the UI thread; even 100 ms sync work causes visible dt spikes.
- **Resource tracking:** Register widgets/effects/timers with ResourceManager; avoid `obj.deleteLater(); obj = None` patterns that leak.
- **SettingsManager integration:** Widgets requiring settings should fetch the shared `EventSystem` via `SettingsManager.get_event_system()` to remain in sync with `ScreensaverEngine`.
- **No raw QTimers:** Use the centralized thread/timer abstractions (e.g., shared clock tick driver) rather than standalone QTimer instances.

## 3. Widget, Overlay, and Theming Policies
- **Widget guidelines:** `Docs/10_WIDGET_GUIDELINES.md` is the canonical reference for overlay styling, layout, Z-order, fade/shadow profiles, DisplayWidget integration, and overlay manager interactions. All new/updated widgets must follow it.
- **Raise order:** Widgets must call `raise_()` synchronously right after `transition.start()` completes—never via deferred `QTimer.singleShot(0, ...)` calls that let the compositor paint first.
- **Overlay attributes:** Every overlay widget should call `configure_overlay_widget_attributes()` to ensure `WA_StyledBackground=True` and consistent shadow/fade behavior.
- **Fade/show discipline:** GL overlays delay `show()` until fade > 0, set `_gl_initialized=True` at the end of `initializeGL()`, and skip `paintGL()` until initialized.
- **Halo/fade sync:** Follow the Halo/Fade audit guidance so control halos appear only when overlays are above the compositor and compositor-ready signals precede widget visibility.
- **Spotify visualizer:** Never lower existing FPS caps. Performance work may raise caps if justified, but reducing them is prohibited due to prior regressions.
- **Theming:** Prefer theming through the centralized QSS/CSS system; keep styles segmented per widget element. Programmatic styling is acceptable only when it simplifies logic or is the sole option.

## 4. Transition & Rendering Rules
- **Transition final frame:** All transitions (CPU, compositor, GLSL) must finish on a frame visually indistinguishable from the fully-rendered new image. No residual blending or old-image remnants at progress 1.0.
- **Transition cleanup:** `rendering/gl_compositor` transitions must call `cancel_current_transition(snap_to_new=True)` during cleanup/stop so the compositor never flashes the old frame.
- **Desync & scheduling:** Widget timers and GPU/CPU work should respect the desync-safe scheduling guidance (Docs/10_WIDGET_GUIDELINES.md §11) so heavy work does not align exactly with transition start.
- **GL overlay startup:** Adhere to the GL initialization guard pattern (`_gl_initialized` flag, deferred paint until ready) to prevent flashes.
- **Reddit URL handling in Winlogon saver mode:** Use `core/windows/url_launcher.py` helper processes for Reddit links when running as a native screensaver so URLs open on the interactive desktop without breaking the saver.

## 5. Testing, Tooling, and Docs Hygiene
- **Test registry:** `Docs/TestSuite.md` is the canonical list of tests. Consult it before/after adding or modifying tests and update it for any changes.
- **Pytest wrapper:** When running tests, prefer `tests/pytest.py` so runs are logged under `logs/`. If this script is missing functionality, extend it instead of bypassing it.
- **RSS/Hybrid tests:** Skip the long-running RSS/Hybrid tests unless directly modifying RSS support; they have 2-minute timeouts.
- **Logging discipline in tests:** Capture pytest output via the logging wrapper and inspect rotating logs if console output is truncated or missing.
- **Documentation maintenance:** Keep `Spec.md`, `Index.md`, and `Docs/TRANSITION_POLICY.md` aligned with implementation changes (architecture decisions, module maps, transition policies). Update these docs before/after major feature work.
- **Audits & backups:** Significant changes should be reflected in `/audits/` (live checklists) and essential `.py` files backed up under `/bak` with minimal rotation.

## 6. Build & Runtime Notes
- **Interpreter:** CLI commands/tests assume Python 3.11 located at `C:\Python311`.
- **Env controls:** Use `SRPSS_PERF_METRICS` for perf logging, `SRPSS_DISABLE_LOGGING` to silence logs when needed, and respect existing env-based switches before introducing new flags.
- **Process supervisor & worker logs:** Keep ProcessSupervisor integrations and worker factories aligned with the centralized architecture (Image, RSS, FFT, Transition workers). Any new worker diagnostics must still honor the PERF gate.

These memories should be treated as living policy—keep this file updated whenever new canonical behaviors are established or existing ones change.
