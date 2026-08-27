# Regression Notes

Last updated: 2026-08-28

Resolved regression notes that should remain easy to find but do not need the full dated narrative
treatment in `Docs/Historical_Bugs.md`.

## Scope

- Use this for small resolved regressions, narrow hardening notes and validation reminders.
- Use `Docs/Historical_Bugs.md` for larger bug families, failed-fix paths, or lessons that should shape
  future architecture decisions.
- Do not use this as a changelog.
- `Current_Plan.md` owns only current blockers/sequence and compact durable invariants; completed implementation
  narrative belongs in current contracts or historical/audit evidence, not as a running changelog.

## Architecture-epoch rule

The notes below record the implementation owner that existed when the regression was fixed. Some old
QWidget/overlay/compositor file references are therefore historical/current-legacy implementation
coordinates, not destination authority.

When a named historical owner is gone or caller-dead:

- preserve the behavioral/lifecycle lesson;
- keep surviving regression coverage on the destination owner;
- do not keep or reconstruct a dead presenter/widget class merely because this note names it.

## Current Notes

### Media Artwork Waits For Its Card Reveal
- **Area:** media startup artwork presentation
- **Files at fix:** `widgets/media_widget.py`, `tests/test_media_transition_deferral.py`
- **Issue:** cold-start generation 1 could decode and queue artwork during transition work, then be
  discarded by transition idle after a same-key generation 2 query began. Generation 2 correctly
  skipped duplicate decode but consequently had no image from which to create a pixmap. The earlier
  reveal-only diagnosis was incomplete.
- **Fix:** idle flush retains the sole decoded pending image while the current query is in flight. Its
  result then authoritatively promotes that image for the same key or replaces it for a changed key. A
  resulting startup pixmap remains at zero opacity until card fade completion; overlapping display
  transition work hands the same pending fade to the existing all-displays-idle callback.
- **Current architecture note:** the QWidget/pixmap presentation coordinates are historical; the
  generation/artwork-before-reveal ordering contract survives on the retained destination.
- **Coverage:** runtime-shaped startup ordering/reveal coverage must survive the owner migration.

### SettingsManager Bulk-Mutation Cache Purge
- **Area:** settings cache invalidation after maintenance/destructive paths
- **Files:** `core/settings/settings_manager.py`, `tests/test_settings_manager.py`
- **Issue:** direct JSON-store mutations in clear/cleanup/repair paths could leave stale in-memory
  dotted-key cache values.
- **Fix:** shared cache purge is used by bulk mutation paths.
- **Coverage:** `test_clear_purges_cached_values`, obsolete-key cleanup and legacy-preset cleanup tests.

### SST Replace-Import Must Actually Replace
- **Area:** settings snapshot transport
- **Files:** `core/settings/sst_io.py`, `tests/test_settings_manager.py`
- **Issue:** `import_from_sst(..., merge=False)` claimed replacement semantics while stale values could
  survive.
- **Fix:** replace mode clears the store before applying the normalized snapshot and clears the
  settings cache.
- **Coverage:** replace import and preview tests.

### Live Audio Block-Size Rebind On Mode Switch
- **Area:** Spotify visualizer audio capture
- **Files at fix:** `widgets/spotify_visualizer/audio_worker.py`, `tests/test_spotify_visualizer_widget.py`
- **Issue:** mode-owned technical config could change `audio_block_size` without restarting active
  capture.
- **Fix:** changing the preferred block size is a live capture rebind boundary.
- **Migration note:** preserve the source/capture contract even if old widget presentation ownership is
  deleted.
- **Coverage:** block-size restart/no-op tests or their destination equivalent.

### Lifecycle-Aware Visualizer Latency Diagnostics
- **Area:** Spotify visualizer diagnostics
- **Files at fix:** `widgets/spotify_visualizer/tick_pipeline.py`,
  `widgets/spotify_visualizer/startup_staging.py`, `widgets/spotify_visualizer_widget.py`
- **Issue:** settings teardown gaps could be logged as live runtime latency stalls.
- **Fix:** latency probes clear on stop/deactivate and refuse to log when the visualizer is not live.
- **Migration note:** old widget/presenter coordinates may become obsolete; lifecycle-aware diagnostics
  remain a durable requirement.
- **Coverage:** disabled/stop-state latency tests or their rehomed equivalent.

### Visualizer Overlay State And Stencil Extraction
- **Area:** historical Spotify visualizer GL overlay hardening
- **Files at fix:** `widgets/spotify_visualizer/overlay_state.py`, `overlay_mask.py`,
  `widgets/spotify_bars_gl_overlay.py`
- **Issue:** high-risk GL overlay state, reset and stencil math were concentrated in one large path.
- **Fix:** state handoff and stencil math were extracted while preserving first-frame authority and mask
  alignment.
- **Migration note:** old `SpotifyBarsGLOverlay` presentation/resource-host ownership is
  historical/remaining-host coordinates. Preserve relevant GL-state/clip/first-frame contracts in
  the Quick render-node tests rather than preserving the overlay.

### Mute Button Secondary-Stage Late-Anchor Recovery
- **Area:** media dependent-widget startup
- **Files at fix:** `widgets/mute_button_widget.py`, `tests/test_mute_button_widget.py`
- **Issue:** the mute button could remain hidden if its secondary-stage starter fired before the media
  anchor appeared.
- **Fix:** later anchor visibility can release secondary-stage reveal once the shared deadline is
  satisfied.
- **Current architecture note:** QWidget pixel ownership is not destination authority; anchor/reveal ordering survives.
- **Coverage:** secondary-stage and anchor-visibility behavior.

### Transition Random Pool Parity
- **Area:** transition selection
- **Files at fix:** `engine/screensaver_engine.py`, `tests/test_transition_distribution.py`
- **Issue:** `Burn` existed in defaults/factory/UI expectations but was missing from the then-current
  engine Random selection.
- **Fix:** selection inventory was brought back into parity.
- **Current terminology:** application activation, saved Random-pool membership and manual selection are
  now separate authorities. Current effective Random candidates are governed by the landed
  activation/pool/hardware contract in `Docs/Transition_Change_Checklist.md`.
- **Coverage:** registry/pool/admission parity remains permanent; do not restore an old “enabled pool” as
  a competing authority.
