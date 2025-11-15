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
- GL and CPU variants for Crossfade, Slide, Wipe, Diffuse, Block Puzzle Flip.
- DisplayWidget injects the shared ResourceManager into every transition; overlays are created through `overlay_manager.get_or_create_overlay` so lifecycle is centralized.
- GL overlays persistent and pre-warmed via `overlay_manager.prepare_gl_overlay` to avoid first-use flicker.
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
- If spikes persist, consider compute-pool pre-scale-to-screen ahead of time as a future enhancement.

## Settings
- `display.refresh_sync`: bool
- `display.hw_accel`: bool
- `display.mode`: fill|fit|shrink
- `transitions.type`: Crossfade|Slide|Wipe|Diffuse|Block Puzzle Flip
- `transitions.random_always`: bool
- `transitions.random_choice`: str
- `transitions.slide.direction`, `transitions.slide.last_direction` (legacy flat keys maintained)
- `transitions.wipe.direction`, `transitions.wipe.last_direction` (legacy flat keys maintained)
- `timing.interval`: int seconds
- `display.same_image_all_monitors`: bool
- Cache:
  - `cache.prefetch_ahead` (default 5)
  - `cache.max_items` (default 24)
  - `cache.max_memory_mb` (default 1024)
  - Widgets:
    - `widgets.clock.monitor`: 'ALL'|1|2|3
    - `widgets.weather.monitor`: 'ALL'|1|2|3
  - `cache.max_concurrent` (default 2)

## Thread Safety & Centralization
- All business logic threading via `ThreadManager`.
- UI updates only on main thread (`run_on_ui_thread`).
- Simple locks (Lock/RLock) guard mutable state; no raw QThread.
- Qt objects registered with `ResourceManager` where appropriate.

## OpenGL Overlay Lifecycle
- Persistent overlays per transition type; reuse prevents reallocation churn.
- Warmup path (`DisplayWidget._prewarm_gl_contexts`) initializes five core overlays per monitor and records per-stage telemetry.
- Triple-buffer requests may downgrade to double-buffer when driver rejects configuration; log and surface downgrade reason through diagnostics overlay.
- Watchdog timers accompany each GL transition; timeout cancellation required once `transition_finish` fires to avoid thread leaks.
- Overlay Z-order is revalidated after each transition to ensure widgets (clock/weather) remain visible across monitors.

## Banding & Pixmap Seeding
- `DisplayWidget` seeds `current_pixmap` as soon as an image loads, before transition warmup, to prevent black/banding frames.
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
