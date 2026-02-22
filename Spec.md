# Spec

Single source of truth for architecture and key decisions.

## Goals
- Smooth, flicker-free image transitions on multi-monitor setups.
- Centralized managers for threads, resources, settings, animations.
- Predictable performance with memory-aware caching and prefetching.

## Architecture Overview
- Engine orchestrates sources → queue → display → transitions.
- DisplayWidget is the fullscreen presenter; transitions are created per-settings.
- ThreadManager provides IO and compute pools; all business threading goes through it.
- ResourceManager tracks Qt objects for deterministic cleanup; includes QPixmap/QImage pooling to reduce GC pressure.
- SettingsManager provides dot-notation access, persisted to a JSON snapshot under
  `%APPDATA%/SRPSS/settings_v2.json` (or `%APPDATA%/SRPSS_MC/` for MC). Legacy
  QSettings profiles are migrated once at startup and future writes stay in
  the JSON store so backups and profile copies are simple file operations. The
  backing store (`core/settings/json_store.py`) performs atomic load/save with
  metadata (`version`, `profile`, `migrated_from`, timestamps) and treats
  structured roots (`widgets`, `transitions`, `custom_preset_backup`) as nested
  documents while exposing the dotted-key API expected by the rest of the app.
  Each profile owns:
  - `settings_v2.json` – canonical snapshot `{version, profile, metadata, snapshot}`
  - `backups/qsettings_snapshot_YYYYMMDD_HHMMSS.json` – raw registry export per migration
  - `custom_preset_backup.json` – most recent Custom preset capture (same schema as `snapshot`)
  These sibling files live under `%APPDATA%/SRPSS/` for the main build and `%APPDATA%/SRPSS_MC/` for MC.
- WidgetManager (extracted from DisplayWidget) handles overlay widget lifecycle, Z-order, rate-limited raises, and QGraphicsEffect invalidation.
- WidgetFactoryRegistry (`rendering/widget_factories.py`) provides centralized widget creation via factory pattern (ClockWidgetFactory, WeatherWidgetFactory, MediaWidgetFactory, RedditWidgetFactory, SpotifyVisualizerFactory, SpotifyVolumeFactory).
- InputHandler (extracted from DisplayWidget) handles all user input including mouse/keyboard events, context menu triggers, exit gestures, **global media key passthrough**, and **double-click next image navigation** (which respects interaction gating). The MC build keeps its fullscreen window out of the taskbar/Alt+Tab list by default but still relies on the central `MultiMonitorCoordinator` to decide who owns keyboard focus. As of Feb 2026 all global WM_ACTIVATE focus re-claim hacks were removed (they broke the Winlogon settings dialog); keyboard focus is now managed strictly through the coordinator and per-widget Qt focus events.
- Reddit Helper Bridge (`core/windows/reddit_helper_bridge.py`) provides a ProgramData-backed queue that both screensaver runtimes can write to from the Winlogon desktop. It now supports generic entries (open_url, open_settings) plus completion-token signaling and schtasks/token-based helper wake-up via the installer.
- Reddit Helper Worker (`helpers/reddit_helper_worker.py`) runs inside the interactive user session, drains those queue entries, opens URLs, and can launch the settings dialog on the user desktop while writing completion sentinels back into ProgramData. This pathway replaces any attempts to launch settings from Winlogon directly and gives us a low-AV-footprint way to surface UI while the saver stays paused.
- TransitionController (extracted from DisplayWidget) manages transition lifecycle including watchdog timeout handling. Transition factory guarantees that `transitions.type="Random"` is never passed downstream: the engine pre-resolves `transitions.random_choice` per rotation and the factory double-checks the selection (falling back to its own pool pick when necessary) so `_create_by_type` always receives a concrete type and never logs "Unknown transition type: Random".
- ImagePresenter (extracted from DisplayWidget) manages pixmap lifecycle.
- MultiMonitorCoordinator (singleton) coordinates cross-display state for multi-monitor setups.
- Settings Persistence: `SettingsDialog` saves and restores window geometry, automatically detecting the correct screen and clamping to available screen area to support multi-monitor and display changes.
- GLProgramCache (singleton) centralizes lazy-loading of shader programs and validates cached program IDs per-context (recompiling when IDs are stale).
- GLGeometryManager (per-compositor instance) handles VAO/VBO management. Changed from singleton because OpenGL VAOs are context-specific.
- GLTextureManager (per-compositor instance) handles texture upload, caching (LRU), and PBO pooling. Changed from singleton because OpenGL textures are context-specific.
- GLTransitionRenderer (extracted from GLCompositor) centralizes shader and QPainter transition rendering.
- GLErrorHandler (singleton) implements session-level fallback policy (Group A→B→C) with software GL detection.
- GLStateManager (`rendering/gl_state_manager.py`) provides centralized GL context state management with validated state transitions (UNINITIALIZED→INITIALIZING→READY/ERROR→DESTROYING→DESTROYED), thread-safe access, callbacks, and recovery tracking. Integrated into GLCompositorWidget and SpotifyBarsGLOverlay.
- TransitionStateManager (extracted from GLCompositor) manages per-transition state with change notifications.
- BeatEngine (extracted from SpotifyVisualizerWidget) handles FFT processing and bar smoothing on COMPUTE pool. `_compute_gate_token` invalidates stale FFT callbacks whenever a teardown occurs, and each smoothing reset bumps a monotonic `generation_id`. Widgets can query `get_latest_generation_with_frame()` to detect when fresh post-reset data has landed before resuming UI work.
- **Multi-Visualizer Architecture**: SpotifyBarsGLOverlay compiles all 7 GLSL shader programs (spectrum, oscilloscope, sine_wave, starfield, blob, helix, bubble) at `initializeGL()` and switches between them in `paintGL()` based on `_vis_mode`. Shaders are loaded from external `.frag` files via `widgets/spotify_visualizer/shaders/__init__.py`. Each mode has its own uniform set dispatched in `_render_with_shader()`, and as of Feb 2026 every per-mode uniform write (e.g. `u_sine_line{1,2,3}_shift`) is scoped inside its mode branch so stale values cannot leak when the compositor paints another shader. **Blob is now the default mode** (`core/settings/defaults.py`), matching the current user profile. Spectrum uses dynamic segment count based on card height (`_dynamic_bar_segments()`: ~4px/seg + 1px gap, 8–64 range). Blob features separated constant wobble (time-driven, zero when cw=0) and reactive wobble (energy-driven, zero when silent), vocal wobble, quadratic reactive deformation (range 0–3.0), and subtle dip contraction with CPU-smoothed energy. Sine Wave is a dedicated mode extracted from Oscilloscope with its own independent `_sine_*` attributes in the widget — the `_on_tick` method is mode-aware and sends sine-specific values for glow, color, speed, sensitivity, line count, line offset bias, wave effect (positional undulation), micro wobble (smooth snake-like bass-driven sinusoids at 2–10 spatial cycles, bass×0.60+mid×0.30+high×0.10 drive, ~0.18 amplitude factor; **fixed Feb 2026**: displacement now divided by amplitude so it is in normalised-Y space rather than amplitude-space, energy gate lowered to 0.001), heartbeat (CPU transient detection: bass vs rolling average, triggers asymmetric triangular bumps along the line on transients, decays at 4.0/s; **fixed Feb 2026**: uses dedicated `_heartbeat_last_ts` for dt so the bump timing is accurate regardless of Spotify state-poll cadence), rainbow hue cycling (shared with oscilloscope), vertical shift (slider) and width reaction (beat-synced horizontal scaling). Sine Wave no longer fights the oscilloscope sliders because every slider has its own storage and serializer slot. `_reset_visualizer_state()` replays the cached config when requested so the widget never resumes with stale rainbow/taste-the-rainbow overrides. Mode cycling now goes through a dedicated teardown → reset → re-entry pipeline:
  1. ShadowFadeProfile-driven fade-out kicks off as soon as the user double-clicks; timers keep ticking but `_mode_teardown_block_until_ready` suppresses heavy work.
  2. Once the fade completes, the widget pauses bubble/compute dispatch, cancels in-flight FFT jobs via `_compute_gate_token`, calls `reset_smoothing_state()` and `reset_floor_state()`, reapplies config, and restarts the shared engine.
  3. The widget records the target engine `generation_id` and blocks `_on_tick` output until `get_latest_generation_with_frame()` reports the same generation (fresh bars). A 750 ms timeout ensures we never deadlock if audio is quiet.
  4. After fresh data lands, `_mode_transition_ready` flips true, `_mode_transition_phase` advances, and the widget begins the fade-in. Card height changes are deferred until this point so the widget never resizes while still visible, keeping fade-out visuals stable. GPU fade factors combine ShadowFadeProfile progress with the mode crossfade to keep the GL overlay and QWidget card perfectly synchronized.

## Phase E Status: Context Menu / Effect Cache Corruption 
- Symptom: overlay shadow/opacity corruption artifacts triggered by Reddit link clicks and context menus.
- Root cause: `SetForegroundWindow()` in `_try_bring_reddit_window_to_front()` steals focus, triggering Windows activation messages that corrupt Qt's `QGraphicsEffect` cache.
- Solution: Smart Reddit link handling (A/B/C logic) exits screensaver immediately when primary display is covered, so corruption never manifests visually.
  - Case A: Primary covered + hard_exit → Exit immediately
  - Case B: Primary covered + Ctrl held → Exit immediately
  - Case C: MC mode (primary NOT covered) → Stay open, bring browser to foreground
- System-agnostic: Uses `QGuiApplication.primaryScreen()` for detection, not screen index assumptions.
- Dedicated investigation doc: `audits/PHASE_E_ROOT_CAUSE_ANALYSIS.md`.

## Developer Feature Gate (SRPSS_ENABLE_DEV)

**Purpose**: Hide experimental, broken, or API-dependent features from end users while keeping code intact for future restoration or development.

**Environment Variable**: `SRPSS_ENABLE_DEV`
- **Default**: `false` (features disabled)
- **Enable**: Set to `true` to activate gated features
- **Usage**: `$env:SRPSS_ENABLE_DEV='true'; python main.py`

**Currently Gated Features**:
1. **Imgur Widget** (`widgets/imgur/`)
   - **Reason**: Imgur's modern website is JavaScript-rendered; BeautifulSoup scraping cannot extract proper gallery URLs with title slugs (e.g., `https://imgur.com/gallery/watching-8ayb0WE`). Only ID-only URLs can be extracted (e.g., `https://imgur.com/gallery/8ayb0WE`), which result in 404 errors or incorrect redirects.
   - **Gate Location**: `rendering/widget_manager.py` line ~1783
   - **Future**: May be restored if Imgur reopens their API or if Selenium/Playwright implementation is added for JS rendering.
   - **Alternative**: Consider Unsplash, Pexels, or Flickr as replacement image sources (all have free APIs or scrapable HTML).
2. **Starfield Visualizer** (`widgets/spotify_visualizer/shaders/starfield.frag`)
   - **Reason**: Experimental shader mode, not yet production-ready. Visual quality and performance still being tuned.
   - **Gate Location**: `ui/tabs/widgets_tab_media.py` — visualizer type combo only shows "Starfield" when dev flag is set.
   - **Future**: Ungated once visual quality and performance are validated.

**Implementation Pattern**:
```python
import os
dev_features_enabled = os.getenv('SRPSS_ENABLE_DEV', 'false').lower() == 'true'

if dev_features_enabled:
    # Create experimental widget
    widget = ExperimentalWidgetFactory.create(...)
```

**Guidelines for Adding Gated Features**:
- Use `SRPSS_ENABLE_DEV` for features that are broken, experimental, or require external APIs that may be unavailable
- Document the reason for gating in this spec
- Keep code intact rather than removing it (allows future restoration)
- Do NOT expose gated features in settings UI or documentation unless dev mode is enabled
- Test that features are properly hidden when gate is disabled

## Deployment
- **SRPSS.scr** / **SRPSS.exe**: Main screensaver build
- **SRPSS_MC.exe**: Manual Controller variant
- **Inno Setup installer**: `scripts/SRPSS_Installer.iss`
- **Build scripts**: PyInstaller and Nuitka options
- **Defender heuristic mitigation**: Windows Defender may flag the SCR as `Trojan:Win32/Wacatac.B!m` without proper PE version metadata. `scripts/build_nuitka.ps1` forwards `APP_VERSION`, `APP_COMPANY`, `APP_DESCRIPTION`, and `APP_NAME` into Nuitka's `--product-version`, `--file-version`, `--company-name`, `--file-description`, and `--product-name` flags. If heuristics flare up, first confirm those fields are emitted before changing binaries. `-KeepExe` / `-SkipScrRename` exist for experiments only.

## Runtime Variants
- Normal screensaver build:
  - Entry: `main.py`, deployed as `SRPSS.scr` / `SRPSS.exe`.
  - Uses the `ShittyRandomPhotoScreenSaver/Screensaver` profile name for legacy migration only; the canonical runtime store is `%APPDATA%/SRPSS/settings_v2.json`.
- Manual Controller (MC) build:
  - Entry: `main_mc.py`, deployed as `SRPSS_Media_Center.exe` (Nuitka onedir) or legacy `SRPSS MC.exe` (PyInstaller onefile).
  - Uses the same organization but stores settings in `%APPDATA%/SRPSS_MC/settings_v2.json`, keeping MC configuration isolated from the normal screensaver profile. Detection now includes the renamed executable stems (`srpss_media_center.exe`) so MC settings stay isolated regardless of the build artifact name and JSON directory.
  - At startup, forces `input.hard_exit=True` in the MC profile so mouse movement/clicks do not exit unless the user explicitly relaxes this in MC settings.
  - `SetThreadExecutionState()` call removed to reduce Defender heuristics; MC runs like any other fullscreen app and relies on Windows power management.
  - MC builds keep their fullscreen DisplayWidget windows out of the taskbar/Alt+Tab list by applying `Qt.Tool` (mirroring the historical behaviour) while a guarded toggle (`rendering.display_widget.MC_USE_SPLASH_FLAGS`) allows splash-style flags when we need to experiment. A dedicated regression test (`tests/test_mc_window_flags.py`) pins this behaviour so any deviation (e.g., accidental SplashScreen flip) is caught immediately.
  - MC packaging defaults to a Nuitka onedir bundle so Defender sees a single EXE plus DLL folder; PyInstaller script (`scripts/build_mc.ps1`) remains as fallback. Nuitka bundle is the primary path referenced by `scripts/SRPSS_MediaCenter_Installer.iss`.

## Image Pipeline
1) Queue selects next `ImageMetadata`.
2) Prefetcher decodes next N images to `QImage` on IO threads and stores in `ImageCache`.
3) On image change, engine loads via cache:
   - If cached `QPixmap` exists: use directly.
   - If cached `QImage`: convert to `QPixmap` on UI thread.
   - Else: fall back to direct `QPixmap(path)` load.
4) DisplayWidget processes to screen size (DPR-aware) via `ImageProcessor`.
5) Transition (GL or CPU) presents old→new.
6) After display, schedule next prefetch.

Optional UI warmup: after a prefetch batch, convert the first cached `QImage` to `QPixmap` on the UI thread to reduce later conversion spikes.

Optional compute pre-scale: after prefetch, a compute-pool task may scale the first cached `QImage` to the primary display size and store it under a `"path|scaled:WxH"` cache key. This is a safe, removable optimization to reduce per-frame scaling cost without visual changes.

## RSS Image Source Architecture

The RSS system is split into focused modules under `sources/rss/`:

- **constants.py**: Feed URLs, priorities, rate limits, cache settings (single source of truth).
- **cache.py** (`RSSCache`): Disk cache with ResourceManager integration, startup loading, LRU eviction, image header validation.
- **parser.py** (`RSSParser`): Stateless feed parsing — detects RSS/Atom vs Flickr JSON vs Reddit JSON, extracts image URLs and metadata into `ParsedEntry` objects. No network I/O.
- **downloader.py** (`RSSDownloader`): All network I/O — RSS fetch (feedparser), JSON fetch (requests), image download with atomic write (temp→rename). Domain-based rate limiting, Reddit rate limiter coordination, shutdown-aware with interruptible waits. **As of v2.75, every downloaded asset is probed with `QImageReader` and rejected if either dimension < 1920×1080, preventing low-res Flickr items from ever hitting cache/prefetch.**
- **health.py** (`FeedHealthTracker`): Persistent feed health tracking with exponential backoff, auto-reset after 24h.
- **coordinator.py** (`RSSCoordinator`): State machine (IDLE→LOADING→LOADED→ERROR), dynamic download budget (target 50 total images), orchestrates cache+parser+downloader+health. Provides `load_async()` (ThreadManager IO pool) and `load_sync()` APIs.

**Key design decisions:**
- No `time.sleep()` in coordinator or parser — interruptible waits live only in downloader.
- Dynamic budget: `new_needed = max(0, TARGET_TOTAL_IMAGES - cached_count)`, distributed across feeds with per-feed cap of 3. **If total usable wallpapers after the main loop < `MIN_WALLPAPER_REFRESH_TARGET` (11), the coordinator immediately tops up using trusted high-res feeds (Bing/NASA) with an elevated `FALLBACK_MAX_PER_FEED_DOWNLOAD` budget, guaranteeing a minimum viable pool without issuing extra feed scans.**
- Sequential single-threaded feed processing — no locks needed for rate limiting state.
- `sources/rss_source.py` retained as thin facade re-exporting constants and wrapping `RSSCoordinator` for backward compatibility.

## Caching and Prefetch
- `ImageCache`: LRU with RLock, stores `QImage` or `QPixmap`, memory-bound by `max_memory_mb` and `max_items`.
- `ImagePrefetcher`: uses ThreadManager IO pool to decode file paths into `QImage`, tracks inflight under lock, and populates cache.
- Look-ahead: `ImageQueue.peek_many(n)` used to determine upcoming assets.
- Skip policy: when a transition is active, prefetch defers to avoid thrash; skipped requests are logged for pacing diagnostics.

## Media (Windows GSMTC)

- Windows media polling uses `core/media/media_controller.py`.
- GSMTC/WinRT calls are treated as potentially blocking IO and are executed via `ThreadManager` with a hard timeout so they cannot stall the UI thread or test runner.
- Inflight check prevents query pileup (only one query at a time).
- Coroutine factory pattern: `_run_coroutine()` accepts a callable that returns a fresh coroutine to avoid "cannot reuse already awaited coroutine" errors.
- Timeouts return `None` but do not disable future queries - widget handles `None` gracefully.


## Image Sources

- Folder sources:
  - `FolderSource` scans configured `sources.folders` paths recursively (extensions filtered by `FolderSource.get_supported_extensions()`).
  - Behaviour is unchanged by RSS work; caps/TTL never apply to folder images.
- RSS / JSON sources:
  - `RSSSource` consumes `sources.rss_feeds` URLs and produces `ImageMetadata` with `source_type=ImageSourceType.RSS`.
  - Supports standard RSS/Atom feeds (via feedparser) and Reddit JSON listings with a light high‑resolution filter (prefers posts with preview width ≥ 2560px when available).
  - Uses an on-disk cache under the temp directory and optional save‑to‑disk mirroring when `sources.rss_save_to_disk` and `sources.rss_save_directory` are configured.
  - **Rotating cache**: Cache cleanup always retains at least 20 images (`min_keep=20`) regardless of size limits, ensuring faster startup for RSS users. Disk cache is also limited by file count (max 2x min_keep or 30, whichever is larger) to prevent unbounded growth.
  - **Runtime caps**: Initial load limits cached images to `sources.rss_rotating_cache_size` (default 20). Async and background refresh enforce `sources.rss_background_cap` (default 30) as the maximum RSS images in queue at any time.
  - **Async loading**: `_load_rss_images_async()` processes sources in priority order (Bing=95, Unsplash=90, Wikimedia=85, NASA=75, Reddit=10) with 8 images per source per cycle to prevent any single source from blocking.
  - **State Management**: Engine uses `EngineState` enum instead of boolean flags for lifecycle management:
    - States: UNINITIALIZED → INITIALIZING → STOPPED → STARTING → RUNNING → STOPPING/SHUTTING_DOWN
    - REINITIALIZING state used during settings changes (not STOPPING)
    - `_shutting_down` property returns False for REINITIALIZING, True for STOPPING/SHUTTING_DOWN
    - This fixes the RSS reload bug where async loading would abort after settings changes.
  - **Shutdown callback**: Each RSSSource receives a `set_shutdown_check(callback)` so downloads abort mid-stream when the engine shuts down.
  - **Cache pre-loading**: Cached RSS images are added to the queue before async download starts, providing immediate variety.
  - Background: the engine enforces a global RSS background cap (`sources.rss_background_cap`, default 30) and a time‑to‑live (`sources.rss_stale_minutes`, default 30 minutes) so older, unseen RSS images are gradually replaced when new ones arrive, but only when a background refresh successfully adds replacements.
  - **Reddit Rate Limiting (Centralized)**: All Reddit API calls are coordinated through `RedditRateLimiter` (`core/reddit_rate_limiter.py`) to stay under Reddit's 10 req/min unauthenticated limit:
    - **Safety target**: 8 req/min max (`MAX_REQUESTS_PER_MINUTE = 8`) with safety threshold at 6 requests (`SAFETY_THRESHOLD = 6`).
    - **Minimum interval**: 8 seconds between consecutive requests (`MIN_REQUEST_INTERVAL = 8.0`).
    - **RSS limits**: Maximum 2 Reddit feeds processed at startup (`MAX_REDDIT_FEEDS_GLOBAL = 2`), 1 per background refresh cycle (`MAX_REDDIT_BG_REFRESH = 1`). 8-second delays enforced between RSS fetches.
    - **Widget refresh**: 5-minute interval (`_refresh_interval = timedelta(minutes=5)`), staggered by 2.5 minutes between widgets (reddit at 0/5/10min, reddit2 at 2.5/7.5/12.5min) with ±2s random jitter.
    - **Widget growth**: Progressive reveal from cached data—4 posts immediately, 10 posts at +2min, 20 posts at +4min—requires zero additional API calls.
    - **Quota coordination**: Widgets use HIGH priority (`RateLimitPriority.HIGH`, 5s min interval) and `reserve_quota()`/`record_request()` to prevent RSS from consuming widget quota. RSS uses NORMAL priority (8s min interval) and `should_skip_for_quota()` checks.
    - **RSSWorker**: Records requests via `record_request(namespace="rss_worker")` for cross-process coordination; checks `should_skip_for_quota()` before Reddit fetches.
    - **Theoretical max**: ~0.6 req/min with all safeguards active, leaving ~7.4 req/min headroom.
  - `ImageQueue` maintains separate pools for local (folder) and RSS images.
  - `sources.local_ratio` (default 60) controls the percentage of images drawn from local sources; the remainder comes from RSS.
  - Ratio-based selection uses probabilistic sampling: each `next()` call randomly decides which pool to draw from based on the configured ratio.
  - **Fallback**: If the selected pool is empty, the queue automatically falls back to the other pool, ensuring continuous image availability.
  - The ratio control is only active when **both** local folders and RSS feeds are configured; otherwise, images come exclusively from the available source type.
  - **Legacy single-source semantics**: when only one source type exists, `ImageQueue.next()` consumes from the combined queue to preserve deterministic `peek()/size()/wraparound` behavior.
  - UI: The Sources tab displays a slider and spinboxes ("X% Local / Y% RSS") between the folder and RSS groups. The control is grayed out when only one source type is configured.

## Transitions
- GL and CPU variants for Crossfade, Slide, Wipe, Block Puzzle Flip; GL-only variant for Blinds (`GLBlindsTransition`) when hardware acceleration is enabled. Diffuse retains a CPU-based effect (`DiffuseTransition`) as the authoritative fallback, while a compositor-backed GLSL Diffuse shader now exists for the `Rectangle`, `Membrane`, `Lines`, `Diamonds`, and `Amorph` shapes when routed via `GLCompositorDiffuseTransition`.
- Compositor-backed controllers (`GLCompositorCrossfadeTransition`, `GLCompositorSlideTransition`, `GLCompositorWipeTransition`, `GLCompositorBlockFlipTransition`, `GLCompositorBlindsTransition`, `GLCompositorDiffuseTransition`) delegate rendering to a single `GLCompositorWidget` per display instead of per-transition `QOpenGLWidget` overlays.
- Additional **GL-only, compositor-backed transitions** are implemented as first-class types:
  - **Peel** (`GLCompositorPeelTransition`) – strip-based peel of the old image in a cardinal direction over the new image.
  - **3D Block Spins** (`GLCompositorBlockSpinTransition`) – GL-only single-slab 3D spin rendered by the compositor: a single thin depth-tested box mesh fills the viewport and flips from the old image (front face) to the new image (back face) with neutral glass edges and specular highlights. Spin axis is controlled by direction (LEFT/RIGHT spin around the Y axis, UP/DOWN spin around the X axis) via a shared card-flip shader (`u_axisMode`, `u_angle`, `u_specDir`); legacy Block Puzzle grid settings are no longer used.
  - **Ripple** (`GLCompositorRainDropsTransition`) – radial ripple effect rendered entirely in GLSL, with a diffuse-region fallback path.
  - **Warp Dissolve** (`WarpState` + `GLCompositorWarpTransition`) – shared vortex-style dissolve where the old and new images participate in a single whirlpool that intensifies mid-transition and then unwhirls back to the final frame.
  - **Claw Marks / Shooting Stars** – a GLSL Shooting Stars variant for Claw Marks was implemented and evaluated and has now been removed from the active transition pool. Its claws shader path is hard-disabled in the compositor so it cannot be used even if compiled; any legacy requests for this effect are mapped to a safe Crossfade-style fallback instead of a dedicated Claw transition.
- DisplayWidget injects the shared ResourceManager into every transition. Legacy GL overlays are created through `overlay_manager.get_or_create_overlay` so lifecycle is centralized, while compositor-backed transitions render exclusively through `GLCompositorWidget`.
- GL overlays remain persistent and pre-warmed via `overlay_manager.prepare_gl_overlay` / `DisplayWidget._prewarm_gl_contexts` to avoid first-use flicker on legacy GL paths; compositor-backed transitions reuse the same per-display compositor widget and never create additional GL surfaces.
- Compositor pre-upload helpers (`GLCompositorWidget._prepare_*_textures`) now include wipe transitions, matching the shader_dispatch contract so `start_wipe` no longer raises `AttributeError` when `_pre_upload_textures()` is invoked.
- DisplayWidget now runs a per-transition warmup pass before the first animation of each GL compositor transition. This pass calls `GLCompositorWidget.warm_transition_resources(...)`, which ensures the GLSL pipeline is initialized, shader programs are compiled via `GLProgramCache`, and both the generic pixmaps **and** transition-specific state/texture preparations (BlockFlip grids, BlockSpin slab textures, Particle buffers, etc.) are uploaded through `GLTextureManager`. Warmed transition types are tracked per DisplayWidget instance so subsequent runs skip the expensive preflight.
- Diffuse shapes: `Rectangle`, `Membrane`, `Lines`, `Diamonds`, `Amorph`. Block size is clamped (min 4px) and shared between CPU and GL paths and enforced by the Transitions tab UI. The CPU fallback always performs a block-based dissolve; non-Rectangle shapes are implemented only in the GLSL compositor path.
- Durations: a global `transitions.duration_ms` provides the baseline duration for all transition types, while `transitions.durations["<Type>"]` (e.g. `"Slide"`, `"Wipe"`, `"Diffuse"`, `"Block Puzzle Flip"`, `"Blinds"`, `"Peel"`, `"3D Block Spins"`, `"Rain Drops"`, `"Warp Dissolve"`) stores optional per-type overrides. The Transitions tab slider is bound to the active type and persists its value into `durations` while keeping `duration_ms` up to date for legacy consumers. Legacy settings for "Shuffle" are mapped to Crossfade for back-compat.

### Transition implementation matrix (v1.2 status)

The table below clarifies which transitions currently have CPU, compositor (QPainter/geometry on the GLCompositor) and GLSL shader implementations. All shader-backed paths retain CPU/compositor fallbacks.

| Transition         | CPU fallback | Compositor (QPainter) | GLSL shader path            | Notes |
|--------------------|-------------|------------------------|-----------------------------|-------|
| Crossfade          | Yes         | Yes                    | Yes (fullscreen quad)       | Port complete; perf tuning tracked via `[PERF] [GL COMPOSITOR] Crossfade` metrics. |
| Slide              | Yes         | Yes                    | Yes (fullscreen quad)       | Port complete; per-transition perf tuning (dt_max spikes on some sizes) still open. |
| Wipe               | Yes         | Yes                    | Yes (mask shader)           | GLSL Wipe path implemented; remaining work is primarily perf/QA and parity checks. |
| Diffuse            | Yes         | Yes                    | Yes (5 shapes)              | GLSL Diffuse with Rectangle/Membrane/Lines/Diamonds/Amorph shapes; CPU Diffuse remains the authoritative fallback. |
| Block Puzzle Flip  | Yes         | Yes                    | Yes (blockflip shader)      | GLSL BlockFlip shader implemented on GLCompositorWidget with a directional, centre-biased block wave that mirrors the CPU Block Puzzle Flip timing; the existing QPainter/compositor path is retained as the authoritative fallback and for non-GL sessions. |
| Blinds             | No CPU-only | Yes (`GLBlindsTransition`) | Yes (blinds shader)        | GL-only compositor path with a shader-backed renderer; requires hardware acceleration. |
| Peel               | No CPU-only | Yes (`GLCompositorPeelTransition`) | Yes (peel shader)         | Strip-based compositor effect where thin bands of the old image peel away over a static new base using per-strip timing offsets and individual strip fading; the existing QPainter implementation remains the authoritative fallback when shaders are unavailable. |
| 3D Block Spins     | N/A         | Yes                    | Yes (card-flip shader)      | Implemented via shared card-flip shader with 6 directions (L/R/U/D + diagonal TL-BR/TR-BL via Rodrigues rotation); legacy grid Block Puzzle settings removed. |
| Ripple (legacy: Rain Drops) | Yes  | Yes (fallback path)    | Yes (ripple shader)         | Primary path is GLSL ripple with configurable ripple count (1-8, default 3); multiple concentric ripples from staggered random centres. |
| Warp Dissolve      | Yes         | Yes (fallback path)    | Yes (vortex shader)         | Shader path tuned; further adjustments are perf/visual polish only. |
| Crumble            | No          | No                     | Yes (voronoi shader)        | GL-only Voronoi crack pattern with physics-based piece falling. Configurable piece count (4-64), crack complexity, and mosaic mode. |
| Particle           | No          | No                     | Yes (particle shader)       | GL-only particle transition with Directional (8 dirs + random), Swirl (3 build orders), and Converge modes. Features 3D ball shading, motion trails, texture mapping, wobble, and configurable gloss/light direction. |
| Burn               | No          | No                     | Yes (burn shader)           | GL-only fire/burn transition with 4 directions (L→R, R→L, T→B, B→T; center-out removed — direction clamped 0–3). Thin bright receding line (~4–8px glow at 1080p), noise only recedes front (never advances), tail_fade smoothstep guarantees clean end at progress=1.0. Configurable jaggedness, glow intensity/colour, char width, smoke/ash toggles and densities. UI in `transitions_tab.py`. Default duration 8000ms. |
| Shuffle            | Yes         | Retired                | Retired                     | Legacy Shuffle is fully removed from random/switch pools; any future Shuffle would be a new GLSL design. |

- Per-transition pool membership:
  - `transitions.pool` is a map of transition type name → bool controlling whether a type participates in engine random rotation and C-key cycling (explicit selection is always allowed regardless of this flag).
- GL-only gating:
  - GL-only types (Blinds, Peel, 3D Block Spins, Ripple, Warp Dissolve, Crumble, Particle, Burn) are only instantiated on the compositor/GL paths when `display.hw_accel=True` and the compositor is available.
  - When hardware acceleration is disabled, the Transitions tab disables these types and the engine maps any request for them to a safe CPU fallback (currently Crossfade).
  - Shader-backed variants (Group A) run on top of the compositor. On any shader initialisation or runtime failure, the engine disables shader usage for the remainder of the session and demotes all subsequent shader-backed requests to the existing QPainter compositor transitions (Group B). Only when the compositor or GL backend is unavailable for the session does the engine fall back to pure software transitions (Group C). Per-transition "try GLSL and silently fall back" paths are avoided; group demotion is explicit and session-scoped.
- Non-repeating random selection:
  - Engine sets `transitions.random_choice` per rotation, filtered through `transitions.pool` and GL-only gating.
  - Slide: cardinal-only directions; stored as `transitions.slide.direction` and last as `transitions.slide.last_direction` (legacy fallback maintained).
  - Wipe: includes diagonals; stored as `transitions.wipe.direction` and last as `transitions.wipe.last_direction` (legacy fallback maintained).
  - UI 'Random direction' respected when `random_always` is false.
  - Manual selection or hotkey cycling must clear `transitions.random_choice` cache immediately so the chosen type instantiates next rotation.
  - Random selection is disabled when `transitions.random_always=False`; engine then respects explicit `transitions.type` from settings/GUI.

## Performance Notes
- All decoding happens off UI thread.
- DPR-aware pre-scaling reduces GL upload pressure.
- Image prefetch + prescale pipeline:
  - `ImagePrefetcher` decodes upcoming images into `QImage` on IO threads and stores them in `ImageCache`.
  - A COMPUTE-pool prescale step uses `ThreadManager.submit_compute_task` to scale the first upcoming image to distinct display sizes and caches them under `"path|scaled:WxH"` keys as `QImage`.
  - When displaying, `ScreensaverEngine._load_image_task` prefers these prescaled entries and promotes them to `QPixmap` on the UI thread, writing the pixmaps back into `ImageCache` so subsequent loads avoid repeated conversions.
- **Display FPS detection & fallback:** Each `GLCompositorWidget` now caches the first successful refresh-rate detection per display and reuses it after settings dialog hops or restarts. When Qt/GPU fails to report a Hz value, the compositor, display setup helpers, `DisplayWidget`, and adaptive timer all fall back to an uncapped 240 Hz target instead of 60 Hz so high-refresh panels never get stuck at 60 fps.
- Image processing pipeline (v1.2 and beyond):  
  - Fully wire prefetch + prescale so large 4K–8K images are decoded on IO threads and pre-scaled for distinct display sizes using COMPUTE threads, caching under "path|scaled:WxH" keys in `ImageCache` while keeping QPixmap creation on the UI thread.  
  - Design an optional further-async `ImageProcessor` path that can move safe crop/composite steps to COMPUTE threads while preserving current quality and semantics.  
    - Operate on `QImage` frames sourced from `ImageCache` (including prescaled `"path|scaled:WxH"` entries) on the COMPUTE pool; avoid `QPixmap` work off the GUI thread.
    - Promote the final cropped/composited `QImage` to `QPixmap` (or GL textures) **once per image per display** on the UI thread only, then reuse that pixmap/texture across transitions.
    - Add tests that compare this async QImage-based crop/composite output against `ImageProcessor.process_image(...)` pixel-for-pixel for representative modes (FILL/FIT/SHRINK) and resolutions (1080p/4K) to lock in visual equivalence.
  - Keep DPR-aware sizing and pixmap seeding in [DisplayWidget](cci:2://file:///f:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/display_widget.py:100:0-4382:16) so base frames are always ready before transitions start.
-- Profiling keys:
  - `GL_SLIDE_PREPAINT`
  - `GL_WIPE_PREPAINT`
  - `GL_WIPE_REPAINT_FRAME`
  - `[PERF] [GL COMPOSITOR] <Name> metrics` summary lines for **all** compositor-driven transitions (Slide, Wipe, Block Puzzle Flip, Ripple/Raindrops, Warp Dissolve, Block Spins, legacy GLSL Claws when enabled). Each line reports `duration`, `frames`, `avg_fps`, `dt_min`, `dt_max`, and compositor `size` and is emitted once per transition completion by `GLCompositorWidget` when PERF metrics are enabled.
 - Telemetry counters record transition type requested vs. instantiated, cache hits/misses, and transition skips while in progress.
 - Animation timing for **all** transitions (CPU and GL/compositor) is centralised through per-display `AnimationManager` instances driven by a `PreciseTimer`-backed loop; transitions use `[PERF] [ANIM]` metrics (duration, frames, avg_fps, dt_min/max, fps_target) as the canonical timing signal rather than ad-hoc timers.
- Spotify visualizer tick instrumentation logs dt spikes with the currently-running transition name, elapsed time, and idle age, allowing correlation between transition warmup gaps and audio/UI timer starvation. `_reset_visualizer_state()` is now the single reset surface for cold starts, settings applies, and double-click mode switches; it replays the last applied settings model, clears GPU/cache state, and restarts fade detection so all modes start identical to a cold launch. `logs/screensaver_perf.log` remains the canonical perf source; set `SRPSS_PERF_METRICS=1` to enable the aggregated summary emitted on exit.
- Frame timing workload regression tests rely on the `FrameTimingHarness` (see `tests/test_frame_timing_workload.py`). The harness provisions a fresh `GLCompositorWidget` and `AnimationManager`, wraps `compositor.update` to sample dt, temporarily silences noisy GL loggers, and performs deterministic teardown. Because the harness is sensitive to GL state, the entire module is marked `@pytest.mark.frame_timing_isolated` and run via `python pytest.py tests/test_frame_timing_workload.py -vv` after the primary suite so dt_max telemetry stays meaningful without affecting faster CI groups.
 - Background work (IO/COMPUTE) is routed through the central `ThreadManager` pools wherever possible; any remaining direct `QThread`/`QTimer` usages outside `core.threading.manager` are explicitly logged fallbacks (e.g. widget-level weather fetch when ThreadManager is unavailable) rather than parallel primary paths.
 - Console debug output uses a suppressing stream handler that groups consecutive INFO/DEBUG lines from the same logger into `[N Suppressed: CHECK LOG...]` summaries while leaving file logs untouched. The high-visibility `Initializing Screensaver Engine 🚦🚦🚦🚦🚦` banner is exempt from grouping so it always appears once per run, and when multiple `[PERF]` lines with `avg_fps=...` are collapsed, the summary includes the trailing `avg_fps` token to keep grouped telemetry readable in the console.
 - A central PERF switch is configured in `core.logging.logger`: `PERF_METRICS_ENABLED` defaults to false and can be overridden by the `SRPSS_PERF_METRICS` environment variable (`0/false/off/no` vs `1/true/on/yes`). In frozen builds, it is finalised at startup by a small `<exe-stem>.perf.cfg` file written next to the executable by the build scripts (`scripts/build_nuitka*.ps1`).
 - Optional CPU profiling for both RUN and CONFIG modes is gated by the `SRPSS_PROFILE_CPU` environment variable. When enabled, `main.py` wraps the selected entrypoint (`run_screensaver` or `run_config`) in a `cProfile.Profile` run and writes `.pstats` snapshots into the active log directory returned by `core.logging.logger.get_log_dir()`, so developers can inspect hotspots and feed them back into the roadmap.
 - When PERF metrics are enabled, `GLCompositorWidget` can optionally draw a small on-screen FPS/debug overlay on top of compositor frames (e.g. Slide/Wipe) to visualise real frame pacing during development. This overlay is disabled implicitly when PERF metrics are turned off so retail builds incur no additional HUD cost.
 - On `initializeGL`, `GLCompositorWidget` logs the OpenGL adapter vendor/renderer/version and disables the shader pipeline for the session when a clearly software GL implementation is detected (for example, GDI Generic, Microsoft Basic Render Driver, llvmpipe). In this case, compositor QPainter-based transitions and CPU fallbacks remain active, but shader-backed paths are not used on that stack.
 - If spikes persist, further expand compute-pool pre-scale-to-screen (including DPR-specific variants) as a future enhancement.

## Settings
- Timer-only rendering: DisplayWidget initialises `_target_fps = 0` (sentinel); `configure_refresh_rate_sync` detects the panel Hz and writes the resolved value. If the compositor reads 0 it forces late re-detection from the screen object. GL surfaces request `swapInterval=0`. No adaptive ladders, no vsync, no user-facing refresh-sync toggle.
- `display.hw_accel`: bool
- `display.mode`: fill|fit|shrink
- `display.use_lanczos`: bool - Use Lanczos resampling for image scaling (higher quality, slightly more CPU intensive)
- `display.sharpen_downscale`: bool - Apply sharpening when downscaling images
- `input.hard_exit`: bool (when true, mouse movement/clicks do not exit; only ESC/Q and hotkeys remain active). Additionally, while the Ctrl key is held, `DisplayWidget` temporarily suppresses mouse-move and left-click exit even when `input.hard_exit` is false, allowing interaction with widgets without persisting a hard-exit setting change. MC builds default this setting to true at startup in their own QSettings profile, while the normal screensaver build respects the saved value.
- `transitions.type`: Crossfade|Slide|Wipe|Diffuse|Block Puzzle Flip|Blinds|Peel|"3D Block Spins"|"Ripple"|"Warp Dissolve"|Crumble|Particle|Burn (legacy `Shuffle` values are mapped to `Crossfade` for back-compat and are no longer exposed in the UI)
- `transitions.random_always`: bool
- `transitions.random_choice`: str (current random pick for this rotation; cleared on manual type changes)
- `transitions.slide.direction`, `transitions.slide.last_direction` (legacy flat keys maintained).
- `transitions.wipe.direction`, `transitions.wipe.last_direction` (legacy flat keys maintained).
- `transitions.duration_ms`: int global default transition duration in milliseconds.
- `transitions.durations`: mapping of transition type name → per-type duration in milliseconds (e.g. `{"Crossfade": 1300, "Slide": 2000, "Ripple": 7000, ...}`) used by the Transitions tab and `DisplayWidget` to make durations independent per transition. Legacy settings keys using the label `"Rain Drops"` are migrated to `"Ripple"` at load time.
- `transitions.diffuse.block_size` (int, clamped to a 4–256px range) and `transitions.diffuse.shape` (`Rectangle`|`Membrane`). The same block-size was historically reused by Shuffle to size its GL grid; Shuffle is now retired but the configuration key is kept for back-compat.
- `transitions.burn.direction` (`Left to Right`|`Right to Left`|`Top to Bottom`|`Bottom to Top`|`Random`; **Center Out removed**), `transitions.burn.jaggedness` (float 0–1), `transitions.burn.glow_intensity` (float 0–1), `transitions.burn.char_width` (float 0–1), `transitions.burn.smoke_enabled` (bool), `transitions.burn.smoke_density` (float 0–1), `transitions.burn.ash_enabled` (bool), `transitions.burn.ash_density` (float 0–1).
- `transitions.pool`: mapping of transition type name → bool controlling whether a type participates in engine random rotation and C-key cycling (explicit selection is always allowed regardless of this flag).
- `timing.interval`: int seconds (default 45). The Display tab now always loads this canonical 45 s value when the key is missing so UI defaults match `SettingsManager`. Regression test `tests/test_display_tab.py::TestDisplayTab::test_display_tab_default_values` guards this.
- `display.same_image_all_monitors`: bool
- Cache:
  - `cache.prefetch_ahead` (default 5)
  - `cache.max_items` (default 24)
  - `cache.max_memory_mb` (default 1024)
  - `cache.max_concurrent` (default 2)
 - Sources:
  - `sources.folders` (list[str]): image folder paths, surfaced in the Sources tab.
  - `sources.rss_feeds` (list[str]): RSS/JSON feed URLs; only feeds explicitly configured here are used by `RSSSource`.
  - `sources.rss_save_to_disk` (bool): when true, new RSS images are mirrored into `sources.rss_save_directory` in addition to the temp cache.
  - `sources.rss_save_directory` (str): absolute path for permanent RSS copies.
  - `sources.rss_rotating_cache_size` (int, default 20): max RSS images to keep between sessions; controls initial load cap.
  - `sources.rss_background_cap` (int, default 35): global cap on queued RSS/JSON images at runtime; enforced on initial load, async load, and background refresh. Increased from 30 to 35 (Feb 2026).
- `sources.spotify_visualizer.spectrum_single_piece`: bool (default **True** as of v2.75) — drives Spectrum “Single Piece Mode”, producing pillar-style bars by default to match the preferred UI look. Existing UI + widget wiring already honours the flag; only the default changed.
  - `sources.rss_refresh_minutes` (int, default 10): background RSS refresh interval in minutes, clamped to at least 1 minute.
  - `sources.rss_stale_minutes` (int, default 30): TTL for RSS images; dynamically adjusted based on transition interval (5-15 min). Stale entries are only removed when a refresh successfully adds replacements.
  - **RSS Rate Limiting** (Feb 2026): `RSSSource` implements domain-based rate limiting (15 requests/minute per domain) to prevent overwhelming any single source. Feed health is persisted to `%TEMP%/srpss_feed_health.json` across restarts, maintaining exponential backoff for failed feeds. Default feeds now include Flickr (7 feeds), Wikimedia (2 feeds), Bing, and NASA. **Reddit feeds removed from defaults** due to cross-process rate limit coordination issues (MC build + screensaver = separate `RedditRateLimiter` instances = unsafe). Users can manually add Reddit feeds; rate limiter remains active for user-added feeds.
 - Widgets:
  - `widgets.clock.*` (Clock 1): monitor ('ALL'|1|2|3), position, font, colour, timezone, background options, analogue-only controls (`show_numerals`, `analog_face_shadow`, and the new `analog_shadow_intense` toggle that doubles drop-shadow opacity/size for dramatic analogue lighting on large displays). **Visual Offset Alignment**: Analogue clocks without backgrounds use `_compute_analog_visual_offset()` to calculate precise offset from widget bounds to visual content (XII numeral or clock face edge), ensuring correct margin alignment with other widgets across all scenarios (with/without background, numerals, timezone).
  - `widgets.clock2.*`, `widgets.clock3.*` (Clock 2/3): same schema as Clock 1 with independent per-monitor/timezone configuration.
  - `widgets.weather.*`: monitor ('ALL'|1|2|3), position, font, colour, margin, optional iconography. **FR-5.2**: Weather widget - temperature, condition, location 
    - Open-Meteo provider integration (no API key required, free tier: 10k calls/day, 5k/hour, 600/min), with back-compat parsing for legacy OpenWeather-style JSON in tests/mocks
    - Background fetching and refresh timers run exclusively through ThreadManager-driven overlay timers (no raw QThread usage); failures fall back to cached data with retry timers also registered via the overlay timer helper.
    - 30-minute refresh interval with early 30-second refresh after startup to ensure fresh data
    - Dual cache: provider cache (`%TEMP%/screensaver_weather_cache.json`) + widget cache (`~/.srpss_last_weather.json`), both with 30-minute TTL
    - Day/night icon variants: auto-selected based on `is_day` field from Open-Meteo API
    - Monochrome icon mode: optional grayscale conversion on icon load (cached, zero paint overhead)
    - Font size hierarchy: location 100% (base), condition 80%, detail/forecast 50% of user setting
    - Detail metrics row: rain chance (from hourly[0]), humidity (from current or hourly[0]), wind speed

- **Atomic JSON snapshot** – The canonical store lives at `%APPDATA%/SRPSS/settings_v2.json` (or `%APPDATA%/SRPSS_MC/settings_v2.json`). `core/settings/json_store.py` maintains a flat in-memory map for all dotted keys, persists `{version, profile, metadata, snapshot}` documents atomically via `*.tmp` swap, and treats `widgets`, `transitions`, and `custom_preset_backup` as structured roots so large maps stay nested on disk.
- **Structured key helpers** – `SettingsManager` exposes transparent dotted access for structured roots. Calls like `get("widgets.clock.enabled")`, `set("transitions.Ripple.enabled", False)`, `contains(...)`, and `get_all_keys()` all operate on the nested JSON without flattening hacks, keeping presets/SST/import/export logic identical to the legacy QSettings APIs.
- **One-shot migration** – On first run without `settings_v2.json`, SettingsManager reads the legacy QSettings profile, normalizes via `_to_plain_value`, populates the JSON store, stamps metadata (`migrated_from`, `legacy_profile`, `migrated_at`), and writes a human-readable backup under `%APPDATA%/SRPSS/backups/qsettings_snapshot_YYYYMMDD_HHMMSS.json`. Subsequent runs skip QSettings entirely; deleting the JSON file forces a re-migration or a defaults reset when no registry data exists.
- **Preset backup parity** – `_save_custom_backup()` now captures nested sections (widgets, transitions, display, accessibility, sources) into a JSON-friendly payload kept under `custom_preset_backup`. `_restore_custom_backup()` replays that snapshot via dotted setters so Custom behaves identically between legacy and JSON stores, and MC adjustments operate directly on the nested `widgets` map.
- **Legacy display toggles ignored** – Import paths (SST, preset application, custom restore) drop `display.refresh_sync`, `display.refresh_adaptive`, `display.render_backend_mode`, and `display.hw_accel` keys so historical bundles cannot resurrect driver-vsync or software-backend toggles. Timer-only rendering remains authoritative regardless of imported payloads.
- **SST compatibility** – `export_to_sst()` mirrors the JSON snapshot (including structured sections) and tags the payload with `settings_version`. `import_from_sst()` and `preview_import_from_sst()` coerce values through `_coerce_import_value`, merge structured sections when requested, and remain tolerant of older `.sst` files by flattening their legacy layout into the new schema before writing.
  - `widgets.reddit.*`: Reddit overlay widget configuration (enabled flag, per-monitor selection via `monitor` ('ALL'|1|2|3), 9 position options (Top/Middle/Bottom × Left/Center/Right), subreddit slug, item limit (4-, 10-, or 20-item layouts for ultra-wide/large displays), font family/size, margin, text colour, optional background frame and border with opacity, background opacity). The widget fetches Reddit's unauthenticated JSON listing endpoints with a fixed candidate pool (up to 25 posts), then sorts all valid entries by `created_utc` so the newest posts appear at the top; each layout simply changes how many rows are rendered from that sorted list. The widget hides itself on fetch/parse failure and only responds to clicks in Ctrl-held / hard-exit interaction modes. Initial visibility is coordinated through the shared overlay fade-in system so Reddit, Weather and Media fade together per display.
  - `widgets.reddit2.*`: Second Reddit widget configuration (enabled flag, per-monitor selection via `monitor`, 9 position options, subreddit slug, item limit). Inherits all styling (font, colors, background, border, opacity) from `widgets.reddit.*` to allow showing two different subreddits simultaneously.
  - `widgets.imgur.*`: Imgur image gallery widget (enabled flag, per-monitor selection via `monitor`, 9 position options, tag selection from presets or custom, grid dimensions via `grid_rows`/`grid_columns` for NxM layout, layout mode (vertical/square/hybrid with dynamic aspect ratio), update interval, header visibility with optional border, image border settings). Uses web scraping with BeautifulSoup since Imgur API is closed to new registrations. Implements LRU disk cache (100MB max) with GIF-to-first-frame conversion, conservative rate limiting (24 req/10min with rolling window tracking), exponential backoff, 429 handling, concurrent downloads (4 at a time via ThreadManager IO pool), circular buffer image rotation (max 100 images), smooth fade transitions (300ms), high-DPI pixmap support, async cache loading to prevent UI blocking, cell pixmap caching to avoid re-scaling, click-to-open-in-browser functionality, and Shiboken validity guards on all UI-thread callbacks from background tasks. Paint-cached grid rendering follows minimal painting policy with widget-level and cell-level caching. Fade coordination via FadeCoordinator for synchronized startup with other widgets.
 - `widgets.shadows.*`: global drop-shadow configuration shared by all overlay widgets (enabled flag, colour, offset, blur radius, text/frame opacity multipliers). Individual widgets perform a two-stage startup animation: first a coordinated card opacity fade-in (driven by the overlay fade synchronizer), then a shadow fade where the drop shadow grows smoothly from transparent to its configured opacity using the same global duration/easing. Shadows are slightly enlarged/softened via a shared blur-radius multiplier so all widgets share a consistent halo.
 - Accessibility:
  - `accessibility.dimming.enabled` (bool, default false): enables compositor-based dimming via `GLCompositorWidget.set_dimming()`, rendered after the base image/transition but before overlay widgets.
  - `accessibility.dimming.opacity` (int, 10-90, default 30): opacity percentage (mapped to 0.0–1.0) for compositor dimming. `widgets/dimming_overlay.py` remains as a legacy/test/fallback widget.
  - `accessibility.pixel_shift.enabled` (bool, default false): enables periodic 1px shifts of all overlay widgets to prevent burn-in on older LCD displays.
  - `accessibility.pixel_shift.rate` (int, 1-5, default 1): number of shifts per minute. Widgets drift up to 4px in any direction then drift back. Shifting is deferred during transitions.
- Settings dialog:
  - Palette: app-owned dark theme without Windows accent bleed.
  - Geometry: 60%-of-screen, clamped geometry for the configuration window.

### Settings snapshots (SST) and About-tab import/export

- SettingsManager continues to use QSettings as the canonical runtime store for each profile (normal `Screensaver` build vs `Screensaver_MC` for the Manual Controller); no runtime behaviour is gated directly on external files.
- The About tab exposes "Export Settings…" and "Import Settings…" actions that read/write a JSON-formatted Single Source of Truth (SST) snapshot of the *current* QSettings profile. Screenshots and tests should treat these as human‑edited backups/restores, not as a second live config store.
- SST files contain a top-level object with `settings_version` (int), `application` (str, currently informational) and `snapshot` (mapping). The `snapshot` map mirrors the nested schema above: top-level `widgets` and `transitions` sections plus nested `display`, `timing`, `input`, `sources`, and any future sections represented by dotted keys.
- Import is merge‑by‑default: values from the snapshot overwrite the current profile where they overlap, but keys that do not exist in the snapshot are preserved. A full restore is therefore "Reset To Defaults" followed by "Import Settings…".

## Settings Type Safety
- Type-safe settings dataclass models in `core/settings/models.py` provide IDE autocompletion and runtime validation.
- Enums: `DisplayMode` (fill/fit/shrink), `TransitionType` (all transition types), `WidgetPosition` (9 positions).
- Core models: `DisplaySettings`, `TransitionSettings`, `InputSettings`, `CacheSettings`, `SourceSettings`.
- Widget models: `ShadowSettings`, `ClockWidgetSettings`, `WeatherWidgetSettings`, `MediaWidgetSettings`, `RedditWidgetSettings`.
- Container: `AppSettings` aggregates all settings sections with `from_settings(SettingsManager)` factory method.
- Each model has `to_dict()` for serialization back to flat keys.
- **22 unit tests** in `tests/test_settings_models.py`.

## Intense Shadows
- Optional "Intense Shadows" styling for all overlay widgets with dramatic visual effect.
- Multipliers in `widgets/shadow_utils.py`: blur 2.0x, opacity 1.8x, offset 1.5x.
- `BaseOverlayWidget.set_intense_shadow(bool)` method for all widgets.
- Clock widget has separate `analog_shadow_intense` and `digital_shadow_intense` options.
- Settings: `widgets.clock.digital_shadow_intense`, `widgets.weather.intense_shadow`, `widgets.media.intense_shadow`, `widgets.reddit.intense_shadow`.
- Applied via `WidgetManager` during widget creation.

## Thread Safety & Centralization
- All business logic threading goes via `ThreadManager` where available.
- Overlay widgets and engine-level timers (image rotation + background RSS refresh) must obtain timers via `ThreadManager.schedule_recurring`; the legacy raw `QTimer` fallback has been removed and widgets now log/abort startup when no manager is injected.
- UI updates only on the main thread (`run_on_ui_thread`).
- Simple locks (Lock/RLock) guard mutable state; no raw QThread or `ThreadPoolExecutor` in production code.
- **Shiboken validity guards**: All widget callbacks dispatched from background threads via `run_on_ui_thread()` must check `Shiboken.isValid(self)` before touching Qt objects, preventing crashes when widgets are destroyed during shutdown while deferred callbacks are still queued. All overlay widgets audited and guarded (Feb 2026).
- Qt objects registered with `ResourceManager` where appropriate.

## Semantics Audit

- See `audits/SEMANTICS_AUDIT_2025_12_18.md` for the live checklist of semantics/naming changes and doc/comment updates required for long-term sanity.

## OpenGL Overlay Lifecycle
- Persistent overlays per transition type for legacy GL paths (including Blinds and Diffuse), plus a single per-display `GLCompositorWidget` that renders the base image and compositor-backed transitions (Crossfade, Slide, Wipe, Block Puzzle Flip). Reuse prevents reallocation churn across both overlays and compositor surfaces.
- Warmup path (`DisplayWidget._prewarm_gl_contexts`) initializes core GL surfaces per monitor (per-transition overlays and/or compositor) and records per-stage telemetry.
- Warmup uses a dummy pixmap derived from the currently seeded frame (wallpaper snapshot or last image) so any first GL frames match existing content rather than a solid black buffer.
- Triple-buffer requests may downgrade to double-buffer when driver rejects configuration; log and surface downgrade reason through diagnostics overlay.
- Watchdog timers accompany each GL transition; timeout cancellation required once `transition_finish` fires to avoid thread leaks.
- Overlay Z-order is revalidated after each transition to ensure widgets (clock/weather/multi-clocks) remain visible across monitors.

### Widget Overlay Behaviour (canonical reference)

- Overlay widgets (clock/weather/media/Reddit/Spotify) extend `BaseOverlayWidget` (`widgets/base_overlay_widget.py`) which provides:
  - Common font/color/background/shadow/position management
  - Pixel shift support via `_pixel_shift_offset` and `apply_pixel_shift()`
  - Thread manager integration via `set_thread_manager()`
  - Size calculation helpers for stacking/collision detection
  - Widget-specific position enums (ClockPosition, WeatherPosition, MediaPosition, RedditPosition) support 9 positions: Top Left/Center/Right, Middle Left/Center/Right, Bottom Left/Center/Right
  - Position enums are stored separately from the base class `OverlayPosition` for type safety
  - **Lifecycle State Machine**: `WidgetLifecycleState` enum (CREATED→INITIALIZED→ACTIVE⇄HIDDEN→DESTROYED) with validated transitions via `is_valid_lifecycle_transition()`. Public methods `initialize()`, `activate()`, `deactivate()`, `cleanup()` drive state changes and invoke subclass hooks (`_initialize_impl`, `_activate_impl`, `_deactivate_impl`, `_cleanup_impl`). Thread-safe state access via `_lifecycle_lock`. ResourceManager integration for automatic resource cleanup. All 6 overlay widgets (Clock, Weather, Media, Reddit, SpotifyVisualizer, SpotifyVolume) implement lifecycle hooks while preserving backward-compatible `start()`/`stop()` methods.
- Overlay widgets follow the patterns defined in `Docs/10_WIDGET_GUIDELINES.md` for:
  - Card styling and typography.
  - Coordinated fade/shadow application via `ShadowFadeProfile` and the
    global `widgets.shadows.*` config.
  - Integration with `DisplayWidget._setup_widgets`,
    `DisplayWidget.request_overlay_fade_sync`,
    `DisplayWidget._ensure_overlay_stack`, and
    `transitions.overlay_manager.raise_overlay` so widgets stay above both the
    base image and any GL compositor/legacy overlays for the full duration of
    transitions.
  - Recurring overlay timers (clock/weather/media/Reddit) are created via `widgets.overlay_timers.create_overlay_timer`, which prefers `ThreadManager.schedule_recurring` with ResourceManager tracking and falls back to widget-local `QTimer` instances when no ThreadManager is attached. This keeps timer lifecycle unified with the rest of the engine.

`Docs/10_WIDGET_GUIDELINES.md` is the **canonical source of truth** for overlay
widget behaviour; this Spec only summarises the high-level contract.

### Spotify Visualizer lifecycle & debugging checklist

When the Spotify Beat Visualizer misbehaves (no fade, flat bars, or popping),
debug in this order:

1. **Card creation & primary fade** – `DisplayWidget._setup_widgets` must:
   - Create `SpotifyVisualizerWidget` when both media and Spotify visualiser
     are enabled for the display.
   - Register `"spotify_visualizer"` in `_overlay_fade_expected` so the card
     participates in the primary overlay fade wave next to media/weather/Reddit.
   - Call `SpotifyVisualizerWidget.start()` once, which in turn registers a
     `request_overlay_fade_sync("spotify_visualizer", starter)` callback.
2. **ShadowFadeProfile progress** – the widget stores fade progress from
   `ShadowFadeProfile` (card + shadow) and exposes it to the GPU path via a
   private `_shadowfade_progress` field. If this value never advances from 0→1,
   the card will not fade and the GPU bars will remain fully gated.
3. **GPU fade factor & secondary wave** – `_get_gpu_fade_factor(now_ts)` on the
   widget derives a delayed cubic fade from `_shadowfade_progress`. Bars and the
   Spotify volume widget should:
   - Stay at 0.0 while the card fade is in its early stages.
   - Ramp smoothly from 0.0→1.0 after the card crosses the configured delay.
   If bars pop in instantly or never appear, inspect this helper first.
4. **Media state & playback gating** – `MediaWidget.media_updated` emits a
   payload with `state` mapped to `MediaPlaybackState` (`PLAYING`, `PAUSED`,
   `STOPPED`). `SpotifyVisualizerWidget.handle_media_update(payload)` sets a
   boolean `_spotify_playing` gate and clears `_target_bars` only when not
   playing so the idle floor shows while preventing motion.
5. **Beat engine & smoothing** – `_SpotifyBeatEngine` owns a single
   `SpotifyVisualizerAudioWorker` and per-process triple buffers for bar
   magnitudes. `SpotifyVisualizerWidget._on_tick()` pulls bars from the engine
   when `_spotify_playing` is true, applies time-based per-bar smoothing and the
   current GPU fade, then calls
   `DisplayWidget.push_spotify_visualizer_frame(...)` when values or fade
   change. Flat bars with a healthy fade usually point to either a muted/
   stalled beat engine or smoothing never updating `_display_bars`.
6. **GL overlay wiring** – `SpotifyBarsGLOverlay` must be created via
   `overlay_manager.prepare_gl_overlay` and raised after transitions; if the
   overlay is never visible, bars will not appear even with correct fade and
   bar values. PERF logs (`[PERF] [SPOTIFY_VIS] Tick/Paint metrics`) and
   `[PERF] [GL COMPOSITOR]` summaries are the canonical signals for confirming
   that frames are being produced and composited.

## Banding & Pixmap Seeding
- `DisplayWidget.show_on_screen` grabs a per-monitor wallpaper snapshot via `screen.grabWindow(0)` and seeds `current_pixmap`, `_seed_pixmap`, and `previous_pixmap` before GL prewarm runs. This prevents a wallpaper→black flash during startup even while overlays are initializing.
- `DisplayWidget` seeds `current_pixmap` again as soon as a real image loads, before transition warmup, to keep the base widget drawing a valid frame while overlays warm and transitions start.
- `paintEvent` prefers `current_pixmap`, then `_seed_pixmap`, and finally `previous_pixmap` (when no error is set), only falling back to a pure black fill when no pixmap is available. This keeps startup and fallback paths visually continuous.
- After closing the settings dialog, force reseed and unblock updates before transitions resume (multi-monitor specific).

## Diagnostics & Telemetry
- Structured logging captures overlay readiness stages, swap behavior, and watchdog activity.
- `audits/ARCHITECTURE_AND_MULTIPROCESSING_PLAN_2026.md` plus the Phase detailed planners are the live checklists for OpenGL stability, multiprocessing, widgets/settings, and documentation work; mirror any significant GL/compositor or telemetry changes there alongside this Spec.
- High-verbosity debug sessions require log rotation (size/time bound) to avoid disk pressure. A dedicated rotating `screensaver_perf.log` file, configured via a PERF-only logging filter in `core.logging.logger`, mirrors all `[PERF]` lines (including `[PERF] [SPOTIFY_VIS]`, `[PERF] [ANIM]`, and `[PERF] [GL COMPOSITOR]` summaries) so performance telemetry remains easy to inspect across rotated main logs.
 - Telemetry counters record transition type requested vs. instantiated, cache hits/misses, and transition skips while in progress.
 - Animation timing for **all** transitions (CPU and GL/compositor) is centralised through per-display `AnimationManager` instances driven by a `PreciseTimer`-backed loop; transitions use `[PERF] [ANIM]` metrics (duration, frames, avg_fps, dt_min/max, fps_target) as the canonical timing signal rather than ad-hoc timers.
 - Background work (IO/COMPUTE) is routed through the central `ThreadManager` pools wherever possible; any remaining direct `QThread`/`QTimer` usages outside `core.threading.manager` are explicitly logged fallbacks (e.g. widget-level weather fetch when ThreadManager is unavailable) rather than parallel primary paths.
 - Console debug output uses a suppressing stream handler that groups consecutive INFO/DEBUG lines from the same logger into `[N Suppressed: CHECK LOG...]` summaries while leaving file logs untouched. The high-visibility `Initializing Screensaver Engine 🚦🚦🚦🚦🚦` banner is exempt from grouping so it always appears once per run, and when multiple `[PERF]` lines with `avg_fps=...` are collapsed, the summary includes the trailing `avg_fps` token to keep grouped telemetry readable in the console.
 - A central PERF switch is configured in `core.logging.logger`: `PERF_METRICS_ENABLED` defaults to false and can be overridden by the `SRPSS_PERF_METRICS` environment variable (`0/false/off/no` vs `1/true/on/yes`). In frozen builds, it is finalised at startup by a small `<exe-stem>.perf.cfg` file written next to the executable by the build scripts (`scripts/build_nuitka*.ps1`). GUI/retail builds typically write `0` to disable PERF metrics, while console/debug builds write `1` to keep full telemetry enabled.
 - Optional CPU profiling for both RUN and CONFIG modes is gated by the `SRPSS_PROFILE_CPU` environment variable. When enabled, `main.py` wraps the selected entrypoint (`run_screensaver` or `run_config`) in a `cProfile.Profile` run and writes `.pstats` snapshots into the active log directory returned by `core.logging.logger.get_log_dir()`, so developers can inspect hotspots and feed them back into the roadmap.
 - When PERF metrics are enabled, `GLCompositorWidget` can optionally draw a small on-screen FPS/debug overlay on top of compositor frames (e.g. Slide/Wipe) to visualise real frame pacing during development. This overlay is disabled implicitly when PERF metrics are turned off so retail builds incur no additional HUD cost.
 - On `initializeGL`, `GLCompositorWidget` logs the OpenGL adapter vendor/renderer/version and disables the shader pipeline for the session when a clearly software GL implementation is detected (for example, GDI Generic, Microsoft Basic Render Driver, llvmpipe). In this case, compositor QPainter-based transitions and CPU fallbacks remain active, but shader-backed paths are not used on that stack.
 - If spikes persist, further expand compute-pool pre-scale-to-screen (including DPR-specific variants) as a future enhancement.

## Future Enhancements
 - Further expand compute-pool pre-scale-to-screen (per-display DPR) ahead of time for the next image and potentially cache DPR-specific scaled variants when memory allows.
 - Transition sync improvements across displays using lock-free SPSC queues.
 - Additional tuning of the **GL-only, compositor-backed transitions** (Peel, Ripple, Warp Dissolve, 3D Block Spins) based on visual QA and user feedback (e.g. strip counts, band amplitudes, droplet density). The legacy Shuffle transition has been fully retired for v1.2; any future Shuffle effect would be a fresh, tile-based GLSL design scheduled post-v1.2 rather than an evolution of the old compositor-based Shuffle.
- Optional Slide edge spark FX (GL/compositor-backed) where slide edges emit short-lived sparks with direction-aware angles and Auto/Blue/Orange colour modes; Auto samples a dominant edge colour and offsets it for visibility. This effect is strictly opt-in and must respect per-display clipping so it never bleeds across monitors.

## Spotify Volume Control

The volume slider widget (`widgets/spotify_volume_widget.py`) uses `core/media/spotify_volume.py` which controls the **Windows mixer session level** for Spotify via pycaw/Core Audio (`ISimpleAudioVolume`).

### Current Implementation (Windows Mixer)
- Controls the per-application volume in Windows Volume Mixer
- Works without authentication or Premium subscription
- **Limitation**: Does NOT sync with Spotify's internal volume slider - they are independent controls
- **Limitation**: Spotify audio sessions are only discoverable via Core Audio when actively playing; volume changes while paused will silently fail
- Volume fill colour alpha is user-configurable (default 140/255 ≈ 55%); border alpha is always forced to 255

### Alternative: Spotify Web API
Spotify's Web API provides `PUT /v1/me/player/volume` which controls the **internal Spotify volume** (the slider inside the app):
- **Pros**: Syncs with Spotify's UI, works across devices via Spotify Connect
- **Cons**: Requires OAuth authentication with `user-modify-playback-state` scope, requires Spotify Premium subscription
- **Implementation complexity**: Would need OAuth flow, token refresh, and API calls

### Recommendation
The current Windows mixer approach is simpler and works for all users. Implementing Spotify Web API volume control would require:
1. OAuth 2.0 PKCE flow for desktop apps
2. Secure token storage
3. Token refresh logic
4. Premium-only feature gating
5. Fallback to mixer control for non-Premium users

This is a **low-priority enhancement** that could be added post-v1.2 if users request Spotify-synced volume.

## Clean Exit Architecture

> **Status**: Clean exit implementation complete - no taskkill required

### Shutdown Pipeline

The application guarantees clean exit through a coordinated shutdown sequence:

1. **ScreensaverEngine.stop()** - Orchestrates shutdown
   - Transitions to SHUTTING_DOWN state (signals async tasks to abort)
   - Stops rotation and RSS refresh timers
   - Clears displays via DisplayManager
   - Shuts down ProcessSupervisor workers
   - Shuts down ThreadManager (wait=False for fast exit)

2. **DisplayManager.cleanup()** - Per-display cleanup
   - Calls `shutdown_render_pipeline("cleanup")` for each display
   - Logs display state via `describe_runtime_state()` before cleanup
   - Clears display widgets and deletes later
   - Flushes deferred Reddit URLs

3. **DisplayWidget.shutdown_render_pipeline()** - Render pipeline teardown
   - Stops transitions via TransitionController with reason logging
   - Stops GL compositor render strategy via `stop_rendering()`
   - Logs state via `describe_runtime_state()` for diagnostics

4. **TransitionController.stop_current()** - Transition cancellation
   - Cancels AnimationManager animations
   - Signals compositor to snap to new image
   - Calls transition.stop() and cleanup()
   - Perf-gated instrumentation for shutdown analysis

5. **Adaptive Timer Fast-Path** - Immediate timer halt
   - `exit_immediate` flag in `AdaptiveTimerConfig`
   - Skips thread wait when set (shutdown only)
   - No performance impact during normal operation

### Key Components

- **GLCompositorWidget.stop_rendering()**: Stops frame pacing and render strategy with perf logging
- **AdaptiveRenderStrategyManager.stop()**: Sets exit_immediate=True before timer stop
- **ThreadManager.shutdown()**: Cancels active tasks, shuts down executors with logging
- **ProcessSupervisor.shutdown()**: Graceful worker termination

### Instrumentation

All shutdown paths instrumented with perf-gated logging (`SRPSS_PERF_METRICS=1`):
- `[PERF][ENGINE]` - Display state aggregation pre-shutdown
- `[PERF][DISPLAY_MANAGER]` - Cleanup display state logging
- `[PERF][DISPLAY]` - Render pipeline shutdown with reason
- `[PERF][GL COMPOSITOR]` - Stop rendering with reason and state
- `[PERF][ADAPTIVE_TIMER]` - Timer stop/pause/resume with state
- `[PERF][TRANSITION]` - Transition cancellation with reason and anim info

### State Description Methods

Diagnostic state capture for shutdown debugging:
- `AdaptiveTimerStrategy.describe_state()` - Timer snapshot (task_id, state, events)
- `AdaptiveRenderStrategyManager.describe_state()` - Strategy config and timer state
- `FrameState.describe()` - Frame interpolation state (progress, samples)
- `TransitionController.describe_state()` - Transition status (running, transition name, elapsed)
- `GLCompositorWidget.describe_state()` - GL state (transition, frame_state, render_strategy)
- `DisplayWidget.describe_runtime_state()` - Aggregated display state

---

## v2.0 Architecture Updates

### Fade Coordination Architecture

- **FadeCoordinator** (`rendering/fade_coordinator.py`) provides centralized, lock-free fade synchronization:
  - Atomic state machine (IDLE → READY → STARTED) using simple attribute assignments (GIL-protected)
  - Lock-free SPSCQueue for cross-thread fade requests
  - Participant registration and compositor-ready signaling
  - Automatic batch fade start when all participants registered and compositor ready
  - No raw locks for business logic - uses atomic operations and queue-based threading
- **WidgetManager** delegates all fade coordination to FadeCoordinator:
  - `reset_fade_coordination()` → `FadeCoordinator.reset()`
  - `set_expected_overlays()` / `add_expected_overlay()` → `FadeCoordinator.register_participant()`
  - `request_overlay_fade_sync()` → `FadeCoordinator.request_fade()`
  - `_on_compositor_ready()` → `FadeCoordinator.signal_compositor_ready()`
- Legacy SPSCQueue/TripleBuffer fade coordination has been removed in favor of the centralized FadeCoordinator

### Media Key Updates
  - `play_pause()` bypasses diff gating for optimistic state updates
  - Uses `repaint()` (not `update()`) for immediate feedback
  - Performance-guarded: only repaints if `_show_controls` and `isVisible()`
  - Visualizer already updates instantly; now play/pause glyph matches
- **Media control bar visual improvements** (`widgets/media_widget.py`):
  - Shifted up 5px for better positioning within card
  - Outer border increased from 1px to 2px for better visibility
  - 3D lift/depth effect: filled slab 4px right/4px down
  - Slab uses same gradient as control bar but 15% darker
  - Slab outline: white 10% darker than control bar outline
  - Light shadow (alpha 40) behind slab for depth
  - **Slab Effect - Experimental** setting added to toggle the 3D effect

### GL State Management Refactoring
- **GLStateManager** (`rendering/gl_state_manager.py`) provides centralized GL context state management with validated state transitions.
- **ResourceManager GL Hooks** (`core/resources/manager.py`): Added `register_gl_handle()`, `register_gl_vao()`, `register_gl_vbo()`, `register_gl_program()`, `register_gl_texture()` for VRAM leak prevention.
- **TransitionController** (`rendering/transition_controller.py`): Added `snap_to_new` parameter to `stop_current()` for clean transition interruption.
- All GL handles in `spotify_bars_gl_overlay.py`, `geometry_manager.py`, and `texture_manager.py` are now tracked by ResourceManager.

### Settings Validation
- **validate_and_repair()** in SettingsManager auto-fixes corrupted settings values on startup.
- Sensitivity validation: Values below 0.5 are reset to default 1.0 to prevent visualizer regression.

### Test Coverage
- **1279 unit tests** across 30+ test files (62 skipped in headless) covering process isolation, GL state, widgets, MC features, settings, performance tuning, integration, threading policy compliance, and frame timing.
- Key test files: `test_display_integration.py` (57 tests), `test_weather_widget.py` (26 tests), `test_adaptive_timer.py` (27 tests), `test_integration_full_workflow.py` (19 tests), `test_spotify_visualizer_widget.py` (13 tests), `test_gl_texture_streaming.py` (18 tests), `test_policy_compliance.py` (threading/import policy enforcement).

**Version**: 2.0.0-dev
