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
- ResourceManager tracks Qt objects for deterministic cleanup.
- SettingsManager provides dot-notation access, persisted across runs.

## Runtime Variants
- Normal screensaver build:
  - Entry: `main.py`, deployed as `SRPSS.scr` / `SRPSS.exe`.
  - Uses QSettings organization `ShittyRandomPhotoScreenSaver` and application `Screensaver`.
- Manual Controller (MC) build:
  - Entry: `main_mc.py`, deployed as `SRPSS_MC.exe` (Nuitka) / `SRPSS MC.exe` (PyInstaller).
  - Uses the same organization but a separate QSettings application name `Screensaver_MC` so MC configuration is isolated from the normal screensaver profile.
  - At startup, forces `input.hard_exit=True` in the MC profile so mouse movement/clicks do not exit unless the user explicitly relaxes this in MC settings.
  - While Windows is configured to use SRPSS.scr as the active screensaver, calls `SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)` for the lifetime of the MC session so the system screensaver and display sleep are suppressed only while MC is running.
  - The fullscreen DisplayWidget window is also given the Qt.Tool flag in MC builds, keeping it out of the taskbar and the standard Alt+Tab list while remaining top-most fullscreen on all configured displays.

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

## Caching and Prefetch
- `ImageCache`: LRU with RLock, stores `QImage` or `QPixmap`, memory-bound by `max_memory_mb` and `max_items`.
- `ImagePrefetcher`: uses ThreadManager IO pool to decode file paths into `QImage`, tracks inflight under lock, and populates cache.
- Look-ahead: `ImageQueue.peek_many(n)` used to determine upcoming assets.
- Skip policy: when a transition is active, prefetch defers to avoid thrash; skipped requests are logged for pacing diagnostics.

## Image Sources

- Folder sources:
  - `FolderSource` scans configured `sources.folders` paths recursively (extensions filtered by `FolderSource.get_supported_extensions()`).
  - Behaviour is unchanged by RSS work; caps/TTL never apply to folder images.
- RSS / JSON sources:
  - `RSSSource` consumes `sources.rss_feeds` URLs and produces `ImageMetadata` with `source_type=ImageSourceType.RSS`.
  - Supports standard RSS/Atom feeds (via feedparser) and Reddit JSON listings with a light high‑resolution filter (prefers posts with preview width ≥ 2560px when available).
  - Uses an on-disk cache under the temp directory and optional save‑to‑disk mirroring when `sources.rss_save_to_disk` and `sources.rss_save_directory` are configured.
  - Startup: the engine assigns a global cap of 8 RSS images across all feeds (divided per‑feed) to avoid long startup stalls.
  - Background: the engine enforces a global RSS background cap (`sources.rss_background_cap`, default 30) and a time‑to‑live (`sources.rss_stale_minutes`, default 30 minutes) so older, unseen RSS images are gradually replaced when new ones arrive, but only when a background refresh successfully adds replacements.

## Transitions
- GL and CPU variants for Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip; GL-only variant for Blinds (`GLBlindsTransition`) when hardware acceleration is enabled.
- Compositor-backed controllers (`GLCompositorCrossfadeTransition`, `GLCompositorSlideTransition`, `GLCompositorWipeTransition`, `GLCompositorBlockFlipTransition`, `GLCompositorBlindsTransition`, `GLCompositorDiffuseTransition`) delegate rendering to a single `GLCompositorWidget` per display instead of per-transition `QOpenGLWidget` overlays.
-- Additional **GL-only, compositor-backed transitions** are implemented as first-class types:
  - **Peel** (`GLCompositorPeelTransition`) – strip-based peel of the old image in a cardinal direction over the new image.
  - **3D Block Spins** (`GLCompositorBlockSpinTransition`) – GL-only single-slab 3D spin rendered by the compositor: a single thin depth-tested box mesh fills the viewport and flips from the old image (front face) to the new image (back face) with neutral glass edges and specular highlights. Spin axis is controlled by direction (LEFT/RIGHT spin around the Y axis, UP/DOWN spin around the X axis) via a shared card-flip shader (`u_axisMode`, `u_angle`, `u_specDir`); legacy Block Puzzle grid settings are no longer used.
  - **Ripple** (`GLCompositorRainDropsTransition`) – radial ripple effect rendered entirely in GLSL, with a diffuse-region fallback path.
  - **Warp Dissolve** (`WarpState` + `GLCompositorWarpTransition`) – banded horizontal warp of the old image over a stable new image, fading out over time.
  - **Claw Marks** (`GLCompositorClawMarksTransition`) – a small set of diagonal scratch bands that grow to reveal the new image using the diffuse region API.
  - **Shuffle** (`GLCompositorShuffleTransition`) – block-based reveal where blocks of the new image slide in from a chosen/random edge; implemented as a moving diffuse region.
- DisplayWidget injects the shared ResourceManager into every transition. Legacy GL overlays are created through `overlay_manager.get_or_create_overlay` so lifecycle is centralized, while compositor-backed transitions render exclusively through `GLCompositorWidget`.
- GL overlays remain persistent and pre-warmed via `overlay_manager.prepare_gl_overlay` / `DisplayWidget._prewarm_gl_contexts` to avoid first-use flicker on legacy GL paths; compositor-backed transitions reuse the same per-display compositor widget and never create additional GL surfaces.
- Diffuse supports multiple shapes (`Rectangle`, `Circle`, `Diamond`, `Plus`, `Triangle`) with a validated block-size range (min 4px) shared between CPU and GL paths and enforced by the Transitions tab UI. Shuffle reuses the diffuse block-size setting to size its grid cells.
- Durations: a global `transitions.duration_ms` provides the baseline duration for all transition types, while `transitions.durations["<Type>"]` (e.g. `"Slide"`, `"Wipe"`, `"Diffuse"`, `"Block Puzzle Flip"`, `"Blinds"`, `"Peel"`, `"3D Block Spins"`, `"Rain Drops"`, `"Warp Dissolve"`, `"Claw Marks"`, `"Shuffle"`) stores optional per-type overrides. The Transitions tab slider is bound to the active type and persists its value into `durations` while keeping `duration_ms` up to date for legacy consumers.
- Per-transition pool membership:
  - `transitions.pool` is a map of transition type name → bool.
  - Random rotation and C-key cycling only consider types whose pool flag is true.
  - Pool membership never affects explicit selection via the settings UI.
- GL-only gating:
  - GL-only types (Blinds, Peel, 3D Block Spins, Rain Drops, Warp Dissolve, Claw Marks, Shuffle) are only instantiated on the compositor/GL paths when `display.hw_accel=True` and the compositor is available.
  - When hardware acceleration is disabled, the Transitions tab disables these types and the engine maps any request for them to a safe CPU fallback (currently Crossfade).
  - Shader-backed variants (Group A, e.g. GLSL Block Spins and future Rain Drops / Warp / Claws ports) run on top of the compositor and, on any shader failure, degrade to the existing QPainter compositor transitions (Group B); only when the compositor or GL backend is unavailable does the engine fall back to pure software transitions (Group C).
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
- Profiling keys:
  - `GL_SLIDE_PREPAINT`
  - `GL_WIPE_PREPAINT`
  - `GL_WIPE_REPAINT_FRAME`
  - `[PERF] [GL COMPOSITOR] Slide metrics` (per-transition summary: duration, frame count, avg_fps, dt_min/dt_max, compositor size) emitted by `GLCompositorWidget` for compositor-driven Slide to validate timing on mixed-refresh setups.
- If spikes persist, consider compute-pool pre-scale-to-screen ahead of time as a future enhancement.

## Settings
- `display.refresh_sync`: bool
- `display.hw_accel`: bool
- `display.mode`: fill|fit|shrink
- `input.hard_exit`: bool (when true, mouse movement/clicks do not exit; only ESC/Q and hotkeys remain active). Additionally, while the Ctrl key is held, `DisplayWidget` temporarily suppresses mouse-move and left-click exit even when `input.hard_exit` is false, allowing interaction with widgets without persisting a hard-exit setting change. MC builds default this setting to true at startup in their own QSettings profile, while the normal screensaver build respects the saved value.
- `transitions.type`: Crossfade|Slide|Wipe|Diffuse|Block Puzzle Flip|Blinds|Peel|"3D Block Spins"|"Ripple"|"Warp Dissolve"|"Claw Marks"|Shuffle
- `transitions.random_always`: bool
- `transitions.random_choice`: str (current random pick for this rotation; cleared on manual type changes)
- `transitions.slide.direction`, `transitions.slide.last_direction` (legacy flat keys maintained).
- `transitions.wipe.direction`, `transitions.wipe.last_direction` (legacy flat keys maintained).
- `transitions.duration_ms`: int global default transition duration in milliseconds.
- `transitions.durations`: mapping of transition type name → per-type duration in milliseconds (e.g. `{"Crossfade": 1300, "Slide": 2000, ...}`) used by the Transitions tab and `DisplayWidget` to make durations independent per transition.
- `transitions.diffuse.block_size` (int, clamped to a 4–256px range) and `transitions.diffuse.shape` (`Rectangle`|`Circle`|`Diamond`|`Plus`|`Triangle`). The same block-size is reused by Shuffle to size its GL grid.
- `transitions.pool`: mapping of transition type name → bool controlling whether a type participates in engine random rotation and C-key cycling (explicit selection is always allowed regardless of this flag).
- `timing.interval`: int seconds
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
  - `sources.rss_background_cap` (int, default 30): global cap on queued RSS/JSON images during background refresh; 0 disables the cap.
  - `sources.rss_refresh_minutes` (int, default 10): background RSS refresh interval in minutes, clamped to at least 1 minute.
  - `sources.rss_stale_minutes` (int, default 30): TTL for RSS images; stale entries are only removed when a refresh successfully adds replacements.
 - Widgets:
  - `widgets.clock.*` (Clock 1): monitor ('ALL'|1|2|3), position, font, colour, timezone, background options.
  - `widgets.clock2.*`, `widgets.clock3.*` (Clock 2/3): same schema as Clock 1 with independent per-monitor/timezone configuration.
  - `widgets.weather.*`: monitor ('ALL'|1|2|3), position, font, colour, optional iconography. **FR-5.2**: Weather widget - temperature, condition, location ✅ IMPLEMENTED (Days 14-16)
    - Open-Meteo provider integration (no API key required), with back-compat parsing for legacy OpenWeather-style JSON in tests/mocks
    - Background fetching with QThread
    - 30-minute caching
    - 4 position options
  - `widgets.media.*`: Spotify/media widget configuration (enabled flag, per-monitor selection via `monitor` ('ALL'|1|2|3), corner position, font family/size, margin, text colour, optional background frame and border with independent opacity, background opacity, artwork size, controls/header style flags). Media participates in the shared overlay fade-in coordination and uses the global widget shadow configuration once its own opacity fade completes. Artwork uses a square frame for album covers and adapts to non-square thumbnails (e.g. Spotify video stills) by adjusting the card frame towards the source aspect ratio while preserving cover-style scaling (no letterboxing/pillarboxing).
  - `widgets.spotify_visualizer.*`: Spotify Beat Visualizer configuration (enabled flag, per-monitor selection via `monitor` ('ALL'|1|2|3) but positioned automatically just above the Spotify/media card, bar_count, bar_fill_color, bar_border_color, bar_border_opacity). The visualizer inherits its card background/border styling from the Spotify/media widget at runtime, participates in the shared overlay fade-in coordination via `DisplayWidget.request_overlay_fade_sync("spotify_visualizer", ...)`, attaches its drop shadow via the global widget shadow configuration, and only animates while the centralized media controller reports Spotify as actively playing.
  - `widgets.reddit.*`: Reddit overlay widget configuration (enabled flag, per-monitor selection via `monitor` ('ALL'|1|2|3), corner position, subreddit slug, item limit (4- or 10-item layouts), font family/size, margin, text colour, optional background frame and border with opacity, background opacity). The widget fetches Reddit's unauthenticated JSON listing endpoints with a fixed candidate pool (up to 25 posts), then sorts all valid entries by `created_utc` so the newest posts appear at the top; 4- and 10-item modes draw from the same sorted list and only differ by how many rows are rendered. The widget hides itself on fetch/parse failure and only responds to clicks in Ctrl-held / hard-exit interaction modes. Initial visibility is coordinated through the shared overlay fade-in system so Reddit, Weather and Media fade together per display.
  - `widgets.shadows.*`: global drop-shadow configuration shared by all overlay widgets (enabled flag, colour, offset, blur radius, text/frame opacity multipliers). Individual widgets perform a two-stage startup animation: first a coordinated card opacity fade-in (driven by the overlay fade synchronizer), then a shadow fade where the drop shadow grows smoothly from transparent to its configured opacity using the same global duration/easing. Shadows are slightly enlarged/softened via a shared blur-radius multiplier so all widgets share a consistent halo.
- Settings dialog:
  - Palette: app-owned dark theme without Windows accent bleed.
  - Geometry: 60%-of-screen, clamped geometry for the configuration window.

## Thread Safety & Centralization
- All business logic threading via `ThreadManager`.
- UI updates only on main thread (`run_on_ui_thread`).
- Simple locks (Lock/RLock) guard mutable state; no raw QThread.
- Qt objects registered with `ResourceManager` where appropriate.

## OpenGL Overlay Lifecycle
- Persistent overlays per transition type for legacy GL paths (including Blinds and Diffuse), plus a single per-display `GLCompositorWidget` that renders the base image and compositor-backed transitions (Crossfade, Slide, Wipe, Block Puzzle Flip). Reuse prevents reallocation churn across both overlays and compositor surfaces.
- Warmup path (`DisplayWidget._prewarm_gl_contexts`) initializes core GL surfaces per monitor (per-transition overlays and/or compositor) and records per-stage telemetry.
- Warmup uses a dummy pixmap derived from the currently seeded frame (wallpaper snapshot or last image) so any first GL frames match existing content rather than a solid black buffer.
- Triple-buffer requests may downgrade to double-buffer when driver rejects configuration; log and surface downgrade reason through diagnostics overlay.
- Watchdog timers accompany each GL transition; timeout cancellation required once `transition_finish` fires to avoid thread leaks.
- Overlay Z-order is revalidated after each transition to ensure widgets (clock/weather/multi-clocks) remain visible across monitors.

### Widget Overlay Behaviour (canonical reference)

- Overlay widgets (clock/weather/media/Spotify visualizer/Reddit and future
  cards) follow the patterns defined in `Docs/10_WIDGET_GUIDELINES.md` for:
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

## Banding & Pixmap Seeding
- `DisplayWidget.show_on_screen` grabs a per-monitor wallpaper snapshot via `screen.grabWindow(0)` and seeds `current_pixmap`, `_seed_pixmap`, and `previous_pixmap` before GL prewarm runs. This prevents a wallpaper→black flash during startup even while overlays are initializing.
- `DisplayWidget` seeds `current_pixmap` again as soon as a real image loads, before transition warmup, to keep the base widget drawing a valid frame while overlays warm and transitions start.
- `paintEvent` prefers `current_pixmap`, then `_seed_pixmap`, and finally `previous_pixmap` (when no error is set), only falling back to a pure black fill when no pixmap is available. This keeps startup and fallback paths visually continuous.
- After closing the settings dialog, force reseed and unblock updates before transitions resume (multi-monitor specific).
- `_has_rendered_first_frame` gates transitions only for the initial frame; settings reopen must reset this guard.

## Diagnostics & Telemetry
- Structured logging captures overlay readiness stages, swap behavior, and watchdog activity.
- `Docs/Route3_OpenGL_Roadmap.md` acts as live checklist; every change must update both roadmap and `audits/AUDIT_OpenGL_Stability.md`.
- `Docs/FlashFlickerDiagnostic.md` tracks symptoms, triggers, and mitigation experiments; roadmap items link back for traceability.
- High-verbosity debug sessions require log rotation (size/time bound) to avoid disk pressure.
- Telemetry counters record transition type requested vs. instantiated, cache hits/misses, and transition skips while in progress.

## Future Enhancements
- Compute-pool pre-scale-to-screen (per-display DPR) ahead of time for the next image.
- Transition sync improvements across displays using lock-free SPSC queues.
- Additional tuning of the **GL-only, compositor-backed transitions** (Peel, Rain Drops, Warp Dissolve, 3D Block Spins, Claw Marks, Shuffle) based on visual QA and user feedback (e.g. strip counts, band amplitudes, droplet density, scratch thickness, shuffle block size/density). Detailed design notes remain in `Docs/GL_Transitions_Proposal.md` and are kept consistent with this Spec.

**Version**: 1.2  
**Last Updated**: Nov 30, 2025 00:47 - 3D Block Spins migrated to a single-slab axis-based GL compositor design (LEFT/RIGHT = Y-axis, UP/DOWN = X-axis) with corrected DOWN orientation; Spec/Index and v1.2 roadmap documentation updated accordingly.
