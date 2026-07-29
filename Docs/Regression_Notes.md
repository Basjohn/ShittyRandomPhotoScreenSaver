# Regression Notes

Last updated: 2026-07-29

Resolved regression notes that should remain easy to find but do not need the full dated narrative treatment in `Docs/Historical_Bugs.md`.

## Scope
- Use this for small resolved regressions, narrow hardening notes, and validation reminders.
- Use `Docs/Historical_Bugs.md` for larger bug families, failed fix paths, or lessons that should shape future architecture decisions.
- Do not use this as a changelog. Ordinary completed feature work should disappear from `Current_Plan.md` after validation.

## Current Notes

### Media Artwork Waits For Its Card Reveal
- **Area:** media startup artwork presentation
- **Files:** `widgets/media_widget.py`, `tests/test_media_transition_deferral.py`
- **Issue:** cold-start generation 1 could decode and queue artwork during transition work, then be discarded by transition idle after a same-key generation 2 query began. Generation 2 correctly skipped duplicate decode but consequently had no image from which to create a pixmap. The earlier reveal-only diagnosis was incomplete.
- **Fix:** idle flush retains the sole decoded pending image while the current query is in flight. Its result then authoritatively promotes that image for the same key or replaces it for a changed key. A resulting startup pixmap remains at zero opacity until card fade completion; overlapping display transition work hands the same pending fade to the existing all-displays-idle callback.
- **Coverage:** the runtime-shaped startup test reproduces first-track publication, transition queueing, the in-flight generation race, same-key promotion, pixmap creation, and card-before-artwork fade ordering; reveal-completion-during-transition remains separate.

### SettingsManager Bulk-Mutation Cache Purge
- **Area:** settings cache invalidation after maintenance/destructive paths
- **Files:** `core/settings/settings_manager.py`, `tests/test_settings_manager.py`
- **Issue:** direct JSON-store mutations in clear/cleanup/repair paths could leave stale in-memory dotted-key cache values.
- **Fix:** shared cache purge is used by bulk mutation paths.
- **Coverage:** `test_clear_purges_cached_values`, obsolete-key cleanup, and legacy-preset cleanup tests.

### SST Replace-Import Must Actually Replace
- **Area:** settings snapshot transport
- **Files:** `core/settings/sst_io.py`, `tests/test_settings_manager.py`
- **Issue:** `import_from_sst(..., merge=False)` claimed replacement semantics while stale values could survive.
- **Fix:** replace mode clears the store before applying the normalized snapshot and clears the settings cache.
- **Coverage:** replace import and preview tests.

### Live Audio Block-Size Rebind On Mode Switch
- **Area:** Spotify visualizer audio capture
- **Files:** `widgets/spotify_visualizer/audio_worker.py`, `tests/test_spotify_visualizer_widget.py`
- **Issue:** mode-owned technical config could change `audio_block_size` without restarting active capture.
- **Fix:** changing the preferred block size is a live capture rebind boundary.
- **Coverage:** block-size restart/no-op tests.

### Lifecycle-Aware Visualizer Latency Diagnostics
- **Area:** Spotify visualizer diagnostics
- **Files:** `widgets/spotify_visualizer/tick_pipeline.py`, `widgets/spotify_visualizer/startup_staging.py`, `widgets/spotify_visualizer_widget.py`
- **Issue:** settings teardown gaps could be logged as live runtime latency stalls.
- **Fix:** latency probes clear on stop/deactivate and refuse to log when the widget is not live.
- **Coverage:** disabled-widget and stop-state latency tests.

### Visualizer Overlay State And Stencil Extraction
- **Area:** Spotify visualizer GL overlay hardening
- **Files:** `widgets/spotify_visualizer/overlay_state.py`, `overlay_mask.py`, `widgets/spotify_bars_gl_overlay.py`
- **Issue:** high-risk GL overlay state, reset, and stencil math were concentrated in one large path.
- **Fix:** state handoff and stencil math were extracted while preserving first-frame authority and mask alignment.
- **Coverage:** ghost isolation, mode transition, stencil mask, overlay kwargs, and synthetic bleed subsets.

### Mute Button Secondary-Stage Late-Anchor Recovery
- **Area:** Spotify dependent-widget startup
- **Files:** `widgets/mute_button_widget.py`, `tests/test_mute_button_widget.py`
- **Issue:** the mute button could remain hidden if its secondary-stage starter fired before the media anchor appeared.
- **Fix:** later anchor visibility can release secondary-stage reveal once the shared deadline is satisfied.
- **Coverage:** secondary-stage and anchor-visibility tests.

### Transition Random Pool Parity
- **Area:** random transition selection
- **Files:** `engine/screensaver_engine.py`, `tests/test_transition_distribution.py`
- **Issue:** `Burn` existed in defaults/factory/UI expectations but was missing from engine random selection.
- **Fix:** engine random selection now matches the enabled transition pool.
- **Coverage:** random pool eligibility and approximate distribution tests.
