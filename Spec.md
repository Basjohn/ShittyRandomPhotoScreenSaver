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

## Transitions
- GL and CPU variants for Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip; GL-only variant for Blinds (`GLBlindsTransition`) when hardware acceleration is enabled. In addition, compositor-backed controllers (`GLCompositorCrossfadeTransition`, `GLCompositorSlideTransition`, `GLCompositorWipeTransition`, `GLCompositorBlockFlipTransition`) delegate rendering to a single `GLCompositorWidget` per display.
- DisplayWidget injects the shared ResourceManager into every transition; overlays are created through `overlay_manager.get_or_create_overlay` so lifecycle is centralized.
- GL overlays remain persistent and pre-warmed via `overlay_manager.prepare_gl_overlay` / `DisplayWidget._prewarm_gl_contexts` to avoid first-use flicker on legacy GL paths, while compositor-backed transitions render through `GLCompositorWidget` instead of per-transition QOpenGLWidget overlays.
- Diffuse supports multiple shapes (`Rectangle`, `Circle`, `Diamond`, `Plus`, `Triangle`) with a validated block-size range (min 4px) shared between CPU and GL paths and enforced by the Transitions tab UI.
- Non-repeating random selection:
  - Engine sets `transitions.random_choice` per rotation.
  - Slide: cardinal-only directions; stored as `transitions.slide.direction` and last as `transitions.slide.last_direction` (legacy fallback maintained).
  - Wipe: includes diagonals; stored as `transitions.wipe.direction` and last as `transitions.wipe.last_direction` (legacy fallback maintained).
  - UI 'Random direction' respected when `random_always` is false.
  - Manual selection or hotkey cycling must clear `transitions.random_choice` cache immediately so the chosen type instantiates next rotation.
  - Random selection disabled when `transitions.random_always=False`; engine respects explicit `transitions.type` from settings/GUI.

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
- `input.hard_exit`: bool (when true, mouse movement/clicks do not exit; only ESC/Q and hotkeys remain active). Additionally, while the Ctrl key is held, `DisplayWidget` temporarily suppresses mouse-move and left-click exit even when `input.hard_exit` is false, allowing interaction with widgets without persisting a hard-exit setting change.
- `transitions.type`: Crossfade|Slide|Wipe|Diffuse|Block Puzzle Flip|Blinds
- `transitions.random_always`: bool
- `transitions.random_choice`: str
- `transitions.slide.direction`, `transitions.slide.last_direction` (legacy flat keys maintained)
- `transitions.wipe.direction`, `transitions.wipe.last_direction` (legacy flat keys maintained)
- `transitions.diffuse.block_size` (int, clamped to a 4–256px range) and `transitions.diffuse.shape` (`Rectangle`|`Circle`|`Diamond`|`Plus`|`Triangle`).
- `timing.interval`: int seconds
- `display.same_image_all_monitors`: bool
- Cache:
  - `cache.prefetch_ahead` (default 5)
  - `cache.max_items` (default 24)
  - `cache.max_memory_mb` (default 1024)
  - `cache.max_concurrent` (default 2)
- Widgets:
  - `widgets.clock.*` (Clock 1): monitor ('ALL'|1|2|3), position, font, colour, timezone, background options.
  - `widgets.clock2.*`, `widgets.clock3.*` (Clock 2/3): same schema as Clock 1 with independent per-monitor/timezone configuration.
  - `widgets.weather.*`: monitor ('ALL'|1|2|3), position, font, colour, optional iconography.
  - `widgets.media.*`: Spotify media widget configuration (enabled flag, target monitor, corner position, font family/size, margin, optional background frame and border, artwork size, controls/header style flags) as documented in `Docs/Spec.md`.
  - `widgets.shadows.*`: global drop-shadow configuration shared by all overlay widgets (enabled flag, colour, offset, blur radius, text/frame opacity multipliers).

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
- Additional **GL-only, compositor-backed transitions** (Peel, Rain Drops, Warp Dissolve, 3D Block Spins, Claw Marks) implemented as new transition types under the existing compositor architecture. These effects are only exposed when `display.hw_accel=True` and must either be hidden or mapped to a safe CPU fallback (e.g. Crossfade) when hardware acceleration is disabled. Detailed design and feasibility notes live in `Docs/GL_Transitions_Proposal.md`.

**Version**: 1.0  
**Last Updated**: Nov 21, 2025 00:30 - Canonical settings, GL compositor path, Spotify widget baseline
