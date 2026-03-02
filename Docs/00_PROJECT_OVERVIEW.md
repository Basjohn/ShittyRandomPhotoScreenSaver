# Project Overview — ShittyRandomPhotoScreenSaver (SRPSS)

This document introduces the SRPSS codebase. Treat it as the top-level landing page before diving into `Spec.md`, `Index.md`, or any of the focused guides under `Docs/`.

## 1. Mission Statement

Deliver a modern Windows screensaver and media controller that blends curated imagery, GPU transitions, and rich overlay widgets while honoring strict thread/resource policies. Every subsystem (sources, rendering, widgets, visualizers) routes through centralized managers so behavior stays deterministic and debuggable.

## 2. Core Pillars

| Pillar | Summary | References |
|--------|---------|------------|
| Deterministic threading | All async work is scheduled through `ThreadManager`. No raw `threading.Thread`, no stray `QThread`. UI updates return to the Qt thread via `invoke_in_ui_thread()`. | `Spec.md` → “Thread Safety”, `Docs/QTIMER_POLICY.md` |
| Centralized lifecycle | ResourceManager tracks every Qt object, GL overlay, and animation. Settings changes replay through `SettingsManager` with JSON snapshots + SST import/export. | `Index.md`, `Docs/Defaults_Guide.md`, `core/settings/sst_io.py` |
| GPU-first rendering | Each display owns a single `GLCompositorWidget` that runs all shader-backed transitions, Spotify visualizer modes, and diagnostics. CPU/QPainter fallbacks remain for older hardware. | `Spec.md` → “Transitions”, `Docs/Visualizer_Debug.md` |
| Widget parity | Overlay widgets (clock/weather/media/Reddit/Spotify visualizer) follow `Docs/10_WIDGET_GUIDELINES.md` (ShadowFadeProfile, fade synchronization, interaction gating). | Widget guidelines doc |
| Preset hygiene | Global widget presets plus per-visualizer curated presets derive from canonical defaults and filtered snapshots; rebuild tooling prevents eco-mode or malformed JSON regressions. | `tools/rebuild_visualizer_presets.py`, `Docs/Visualizer_Presets_Plan.md`, new tests in `tests/test_visualizer_presets.py` |

## 3. Feature Overview

### 3.1 Image Sources

1. **Local folders** — recursive scan with extension filtering, per-path enablement, DPR-aware caching.
2. **RSS / JSON feeds** — `sources/rss/` stack handles Bing, NASA, Unsplash, Reddit JSON. Every download is vetted via `QImageReader`; assets below 1920×1080 never hit cache/queue. Background refresh maintains `MIN_WALLPAPER_REFRESH_TARGET` (11 images) by topping up from trusted feeds. Optional disk mirroring + health tracker keep feeds stable.
3. **Source ratio control** — probabilistic sampler enforces `sources.local_ratio` (default 60/40). Fallback logic automatically draws from the other pool if the chosen pool is empty so rotations never stall.

### 3.2 Rendering & Transitions

- Display modes: Fill (primary), Fit, Shrink. DPR-aware scaling plus optional Lanczos + sharpen toggles.
- `GLCompositorWidget` pre-warms shaders/programs per transition, caches the detected refresh rate (falls back to 240 Hz if Qt fails). All GL-only transitions (Peel, Ripple, Block Spins, Crumble, Particle, Burn) demote to QPainter/CPU groups when hardware acceleration is off or shader init fails mid-session.
- Transition catalog (March 2026): Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip, Blinds, Peel, 3D Block Spins, Ripple (Rain Drops), Warp Dissolve, Crumble, Particle, Burn. Each entry has a GL implementation with automatic CPU fallback where feasible.

### 3.3 Spotify Visualizer

Modes: Spectrum, Oscilloscope, Blob, Helix, Starfield (dev gated), Sine Wave, Bubble. Shared state lives in `SpotifyVisualizerWidget`, GPU uploads in `SpotifyBarsGLOverlay`, and GLSL shaders under `widgets/spotify_visualizer/shaders/`.

Key capabilities:

- **Advanced toggle hygiene**: Normal vs Advanced buckets share a session-cached collapse state per mode. Hidden sliders keep their values (Always-Apply rule).
- **Bubble controls**: Specular and gradient directions are fully decoupled (`bubble_specular_direction`, `bubble_gradient_direction`). Defaults, UI, config applier, overlay uniforms, and preset rebuild all ship both keys so curated presets + SST snapshots remain authoritative.
- **Preset integrity**: Curated JSON files are rebuilt from canonical defaults, filtered by mode, and covered by tests checking duplicate keys, mode enforcement, and SST round-trips (`tests/test_visualizer_presets.py`).
- **Diagnostics**: `Docs/Visualizer_Debug.md` + `Visualizer_Reset_Matrix.md` document cold-start expectations, shared beat engine resets, and per-mode shader uniform maps.

### 3.4 Widgets & Overlays

- **Clock (1–3 instances)**: Digital/analog, per-monitor placement, cached pixmaps, pixel-shift aware.
- **Weather**: Open-Meteo provider, 30 min refresh, monochrome option, detail rows.
- **Media**: GSMTC polling with idle/backoff, optional Spotify volume/mute controls, per-card color bindings.
- **Reddit**: Up to two widgets, rate-limited via `RedditRateLimiter`, staggered refresh, card growth (4→10→20 posts) without extra API calls.
- **Spotify Visualizer overlay**: GL widget with cold-start blanking, fade coordination, pixel-shift integration.

### 3.5 Configuration UX

- Tabs: Sources, Display, Transitions, Widgets, Accessibility, About.
- Instant apply: `WidgetsTab` rehydrates slider positions, preset indices, and advanced toggle states on every open.
- Settings snapshots: Export/import via SST (human-readable JSON). Merge-import respects structured roots (`widgets`, `transitions`, `custom_preset_backup`) and rejects legacy display keys automatically.

### 3.6 Deployment Modes

| Artifact | Purpose | Notes |
|----------|---------|-------|
| `SRPSS.scr` / `SRPSS.exe` | Primary screensaver build | Handles `/s`, `/c`, `/p` args. |
| `SRPSS_MC.exe` | Manual Controller | Forces `input.hard_exit=True`, stores settings under `%APPDATA%/SRPSS_MC`, primary build uses Nuitka onedir. |
| Installers | `scripts/SRPSS_Installer.iss`, `scripts/SRPSS_MediaCenter_Installer.iss` | PyInstaller path kept for experiments, Nuitka mainline. |

## 4. Technology Stack

- **Language / runtime**: Python 3.11, PySide6 6.9.1.
- **Rendering**: OpenGL 4.1 via PyOpenGL, GLSL fragment shaders per mode/transition.
- **Audio**: WASAPI loopback (pyaudiowpatch), shared beat engine with compute-pool smoothing.
- **Threading**: `ThreadManager` IO + compute pools, lock-free queues, zero ad-hoc threads.
- **Persistence**: JSON settings store (`core/settings/json_store.py`), SST snapshot import/export, curated presets under `presets/`.

## 5. Performance & QA Targets

| Target | Current Status | Notes |
|--------|----------------|-------|
| Steady 60 FPS on 1080p | ✅ | GL compositor warms programs per transition, fallback to 240 Hz default if refresh detection fails. |
| Dual 4K stability | ✅ | Image pipeline prefetch/prescale via compute threads; DisplayWidget avoids synchronous repaints. |
| Memory guard | ✅ | ImageCache bounded by item count + MB, GL overlays tear down cleanly, ResourceManager ensures deterministic cleanup. |
| Logging | ✅ | Five rotating logs (`screensaver*.log`, `screensaver_perf.log`, `screensaver_spotify_vis.log`, etc.) with suppression/deduplication. |
| Tests | ✅ | See `Docs/TestSuite.md` for suites. Visualizer preset audit tests added Mar 2026. |

## 6. Settings Snapshot Cheat Sheet

- **Defaults**: `core/settings/default_settings.py` (mirrored to `core/settings/defaults_snapshot.*`).
- **Models**: `core/settings/models.py` – Spotify visualizer dataclass includes both specular and gradient direction fields.
- **Preset rebuild**: `tools/rebuild_visualizer_presets.py` overlays canonical defaults + legacy JSON, filters allowed keys, writes compact payload.
- **SST export/import**: `core/settings/sst_io.py`. Export includes metadata + snapshot; import merge respects structured roots and skips deprecated display toggles automatically. Preview path computes diffs without mutating settings.

## 7. Documentation Map

| Doc | Purpose |
|-----|---------|
| `Spec.md` | Architecture, policies, settings schema, Spotify visualizer checklist |
| `Index.md` | Living module map with per-file summaries and responsibilities |
| `Docs/Defaults_Guide.md` | Canonical defaults, how to change them safely, per-mode tables |
| `Docs/10_WIDGET_GUIDELINES.md` | Overlay widget contract (ShadowFadeProfile, fade sync, DisplayWidget integration) |
| `Docs/Advanced_Migration.md` | Normal vs Advanced bucket playbook, Always-Apply rule, alignment helpers |
| `Docs/Visualizer_Debug.md` & `Docs/Visualizer_Reset_Matrix.md` | Visualizer architecture, reset expectations, diagnostics |
| `Docs/Visualizer_Presets_Plan.md` | End-to-end preset workflow (creation, filtering, rebuild tooling) |
| `Docs/TestSuite.md` | Test matrix, fixtures, execution order |
| `Docs/Historical_Bugs.md` | Postmortems and regression coverage |

## 8. Quick Start for Contributors

1. **Read** `Spec.md` → `Index.md` → relevant plan doc (e.g., `Bubble_Motion_Plan.md`).
2. **Follow** the centralized managers (ThreadManager, ResourceManager, SettingsManager). Never create ad-hoc threads or timers.
3. **Update** `Index.md`, `Spec.md`, and any relevant doc after feature work. Preset or defaults changes must pass through defaults → models → UI → docs/tests.
4. **Test** using `Docs/TestSuite.md` guidance (PySide Qt plugin issues are already handled). New features need regression tests plus SST/preset coverage when settings change.
5. **Log** using the dedicated loggers; performance metrics (`[PERF]`) gate to `screensaver_perf.log`.

For anything not covered here, locate the corresponding doc in `Docs/`, confirm it matches the latest code, and keep it updated going forward.
