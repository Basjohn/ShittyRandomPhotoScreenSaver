# Index

A living map of modules, purposes, and key classes. Keep this up to date.

## Core Managers
- core/threading/manager.py
  - ThreadManager, ThreadPoolType, TaskPriority
  - UI dispatch helpers: run_on_ui_thread, single_shot
  - IO/Compute pools, lock-free stats and mutation queues
- core/resources/manager.py
  - ResourceManager for Qt object lifecycle tracking (register_qt, cleanup_all)
- core/events/event_system.py
  - EventSystem pub/sub (thread-safe)
- core/settings/settings_manager.py
  - SettingsManager (get/set, dot-notation)
- core/animation/animator.py
  - AnimationManager and easing types

## Engine
- engine/screensaver_engine.py
  - Orchestrator: sources → ImageQueue → display → transitions
  - Caching/prefetch integration via ImageCache + ImagePrefetcher
  - Random transition/type selection with non-repeating logic (persisted)
- engine/display_manager.py
  - Multi-monitor DisplayWidget management, sync scaffolding
- engine/image_queue.py
  - ImageQueue with RLock, shuffle/history, wraparound
  - peek() and peek_many(n) for prefetch look-ahead

## Rendering
- rendering/display_widget.py
  - Borderless fullscreen (frameless, always-on-top per monitor) image presentation, DPR-aware scaling
  - Creates transitions based on settings (GL and CPU variants, including GL-only Blinds when HW accel is enabled)
  - Injects shared ResourceManager into transitions; seeds base pixmap pre/post transition and on startup to avoid black frames (wallpaper snapshot seeding + previous-pixmap fallback)
  - Uses lazy GL overlay initialization via `overlay_manager.prepare_gl_overlay` instead of a global startup prewarm; manages widgets Z-order, logs per-stage telemetry, handles transition watchdog timers
- rendering/image_processor.py
  - Scaling/cropping for FILL/FIT/SHRINK, optional Lanczos via PIL
- rendering/pan_and_scan.py
  - Pan & scan utility for post-transition motion
- rendering/display_modes.py
  - DisplayMode enum and helpers

## Transitions
- transitions/base_transition.py
  - BaseTransition with centralized animation
- transitions/overlay_manager.py
  - Persistent overlay helpers (`get_or_create_overlay`, `prepare_gl_overlay`, diagnostics/raise helpers) registering with shared ResourceManager; logs swap downgrades and readiness telemetry
- transitions/crossfade_transition.py, transitions/gl_crossfade_transition.py
- transitions/slide_transition.py, transitions/gl_slide_transition.py
- transitions/wipe_transition.py, transitions/gl_wipe_transition.py
  - Slide/Wipe directions stored independently in settings; Slide is cardinals only, Wipe includes diagonals
  - Wipe random direction honored; non-repeating when Random is selected in UI
- transitions/diffuse_transition.py, transitions/gl_diffuse_transition.py
  - Diffuse shapes: Rectangle, Circle, Diamond, Plus, Triangle; block size clamped (min 4px) and shared between CPU/GL
- transitions/block_puzzle_flip_transition.py, transitions/gl_block_puzzle_flip_transition.py
- transitions/gl_blinds.py
  - GL-only Blinds transition using a persistent overlay; participates in GL prewarm and requires hardware acceleration

## Sources
- sources/base_provider.py
  - ImageMetadata
- sources/folder_source.py
- sources/rss_source.py

## Widgets
- widgets/clock_widget.py
  - Digital clock widget supporting three instances (Clock 1/2/3) with per-monitor selection, independent timezones, optional seconds and timezone labels
- widgets/weather_widget.py
  - Weather widget with per-monitor selection via settings (ALL or 1/2/3); planned QPainter-based iconography
- widgets/media_widget.py
  - Spotify/media overlay widget driven by `core/media/media_controller.py`; per-monitor selection via `widgets.media`, corner positioning, background frame, and monochrome transport controls (Prev/Play/Pause/Next) over track metadata
 - widgets/reddit_widget.py
   - Reddit overlay widget showing top posts from a configured subreddit with 4- and 10-item layouts, per-monitor selection via `widgets.reddit`, shared overlay fade-in coordination, and click-through to the system browser.
 - widgets/overlay_timers.py
   - Centralised overlay timer helper providing `create_overlay_timer()` and `OverlayTimerHandle` for recurring UI-thread timers (clock/weather/media/Reddit). Prefers `ThreadManager.schedule_recurring` with ResourceManager tracking and falls back to a widget-local `QTimer` when no ThreadManager is available.

## Utilities
- utils/image_cache.py
  - Thread-safe LRU (QImage/QPixmap), memory-bound, eviction
- utils/image_prefetcher.py
  - IO-thread decode to QImage; prefetch N ahead; inflight tracking
- utils/profiler.py
- utils/lockfree/spsc_queue.py
- utils/monitors.py

## Docs
- Docs/TestSuite.md – canonical tests
- Docs/AUDIT_*.md – technical audits
- Docs/Route3_OpenGL_Roadmap.md – live checklist for stability work, must update each step
- Docs/FlashFlickerDiagnostic.md – flicker/banding symptom tracker and mitigation history
 - Docs/10_WIDGET_GUIDELINES.md – canonical overlay widget design (card styling, fade/shadow via ShadowFadeProfile, Z-order/integration with DisplayWidget and overlay_manager, interaction gating)
 - audits/*.md – repository-level Cleaning/Architecture/Optimization audit documents with live checklists

## Settings (selected)
- display.refresh_sync: bool
- display.hw_accel: bool
- display.mode: fill|fit|shrink
- transitions.type
- transitions.random_always: bool
- transitions.random_choice: str
- transitions.duration_ms: int (global default duration in milliseconds for transitions)
- transitions.durations: map of transition type name → duration_ms used for per-transition duration independence (e.g. Crossfade/Slide/Wipe/Diffuse/Block Puzzle Flip/Blinds)
- transitions.slide.direction, transitions.slide.last_direction (legacy flat keys maintained for back-compat; nested `transitions['slide']['direction']` is the canonical form)
- transitions.wipe.direction, transitions.wipe.last_direction (legacy flat keys maintained for back-compat; nested `transitions['wipe']['direction']` is the canonical form)
- timing.interval: int seconds
- display.same_image_all_monitors: bool
- cache.prefetch_ahead: int (default 5)
- cache.max_items: int (default 24)
- cache.max_memory_mb: int (default 1024)
- cache.max_concurrent: int (default 2)
- widgets.clock.monitor: 'ALL'|1|2|3
- widgets.weather.monitor: 'ALL'|1|2|3
 - widgets.media.monitor: 'ALL'|1|2|3
 - widgets.reddit.monitor: 'ALL'|1|2|3
 - widgets.shadows.*: global widget shadow configuration shared by all overlay widgets

## Notes
- DPR-aware scaling in DisplayWidget → ImageProcessor to reduce GL upload cost
- GL overlays are persistent and initialized lazily on first use via `prepare_gl_overlay`; NoPartialUpdate enabled
- Prefetch pipeline: ImageQueue.peek_many → IO decode (QImage) → optional UI warmup (QPixmap) → optional compute pre-scale-to-screen (QImage) → transition
