# Regression Notes

Last updated: 2026-05-13

Smaller resolved regressions and follow-up hardening notes that are worth keeping visible,
but do not belong in `Docs/Historical_Bugs.md`.

## 2026-05-13

### Live Audio Block-Size Rebind on Mode Switch
- **Area:** Spotify visualizer live runtime config / capture restart
- **Files:** `widgets/spotify_visualizer/audio_worker.py`, `tests/test_spotify_visualizer_widget.py`
- **Issue:** mode-owned technical config changes could push a new `audio_block_size` into the live visualizer worker without restarting the already-running capture stream. In practice this left runs like `devcurve -> spectrum` on the stale negotiated block size until a full settings-dialog restart rebuilt audio capture, which matched the "hot/pinned until settings open/close" failure shape in logs.
- **Fix:** `SpotifyVisualizerAudioWorker.set_audio_block_size()` now treats a real preferred-block change as a live capture rebind boundary: it updates the backend config, restarts capture when already running, and logs the restart clearly so future log review can see whether the live switch really took effect.
- **Regression coverage:**
  - `test_audio_worker_block_size_change_restarts_running_capture`
  - `test_audio_worker_block_size_noop_does_not_restart_capture`
- **Log note:** future log review should specifically check that a live mode switch negotiates the requested block size immediately, instead of only after a settings-dialog restart.

### Spotify GL Overlay State-Handoff Extraction
- **Area:** Spotify visualizer GL overlay state/reset hardening
- **Files:** `widgets/spotify_visualizer/overlay_state.py`, `widgets/spotify_bars_gl_overlay.py`, `tests/test_ghost_isolation.py`, `tests/test_spotify_visualizer_mode_transition.py`
- **Issue:** `SpotifyBarsGLOverlay.set_state()` still mixed visibility early-return, activation/generation capture, mode-reset bookkeeping, border-width storage, and the large per-mode payload application in one monolithic entrypoint. That made the highest-risk visualizer file harder to audit without touching the first-frame / bleed-sensitive render path.
- **Fix:** extracted the non-shader state side into `overlay_state.py` so manual reset scheduling, cold-reset bookkeeping, activation/generation/frame metadata capture, floor snapshot handoff, invisible-frame early return, and border-width storage are centralized behind thin overlay wrappers. `paintGL()` stencil math and first-frame authority were intentionally left untouched.
- **Regression coverage:**
  - `tests/test_ghost_isolation.py`
  - `tests/test_spotify_visualizer_mode_transition.py`
  - `tests/test_stencil_mask_alignment.py`
  - synthetic bleed-family subset from `tests/test_spotify_visualizer_widget.py`
- **Log note:** post-change review of `logs/screensaver_spotify_vis.log` stayed free of first-bar / bleed / first-frame / error markers; only a latency warning remained visible from the user's multi-swap runs.

### Spotify GL Overlay Stencil-Path Extraction
- **Area:** Spotify visualizer GL overlay render-side hardening
- **Files:** `widgets/spotify_visualizer/overlay_mask.py`, `widgets/spotify_bars_gl_overlay.py`, `tests/test_stencil_mask_alignment.py`
- **Issue:** the painted-card stencil clip path was still fully inlined in `paintGL()`, mixing GL state transitions, mask uniform math, and shader draw setup inside the main render method. That made the most fragile card-boundary path harder to audit without risking accidental math drift.
- **Fix:** extracted the rounded-rect mask uniform math into `overlay_mask.py` and split `paintGL()` into explicit begin/draw/end stencil helpers while preserving the exact inset, border-width, and radius contract.
- **Regression coverage:**
  - `tests/test_stencil_mask_alignment.py`
  - `tests/test_visualizer_overlay_kwargs.py`
  - `tests/test_ghost_isolation.py`
  - `tests/test_spotify_visualizer_mode_transition.py`
  - synthetic bleed-family subset from `tests/test_spotify_visualizer_widget.py`
- **Risk note:** this still does not alter first-frame authority or shader content behavior; it only makes the stencil path explicit so future risky work has a narrower seam.

### Visualizer Settings/Activation/Runtime Residue Reduction
- **Area:** Spotify visualizer structural hardening
- **Files:** `core/settings/models/_spotify_visualizer.py`, `widgets/spotify_visualizer/technical_config.py`, `widgets/spotify_visualizer/activation_runtime.py`, `widgets/spotify_visualizer/runtime_config.py`, `widgets/spotify_visualizer_widget.py`
- **Issue:** large settings/activation/technical-config blocks were still concentrated in monolithic seams, making future visualizer work riskier and harder to audit. That kind of coordinator bloat raises the chance of accidentally reopening the historical bleed / fresh-frame / startup regressions.
- **Fix:** extracted dedicated helper ownership for:
  - visualizer settings ingestion/serialization groupings in `_spotify_visualizer.py`,
  - per-mode technical cache/override/engine-application logic in `technical_config.py`,
  - settings-model apply and canonical activation-payload replay in `activation_runtime.py`,
  - shared beat-engine/thread/process/audio-block/runtime-bar-state coordination in `runtime_config.py`.
- **Regression coverage:**
  - `tests/test_visualizer_settings_plumbing.py`
  - `tests/test_spotify_visualizer_widget.py`
  - synthetic-audio / bleed-focused checks:
    - `test_runtime_switch_paths_reset_all_bleed_state_for_all_modes`
    - `test_mode_switch_synthetic_audio_matches_fresh_worker_after_reset`
    - `test_widget_manager_preset_cycle_discards_real_engine_bleed_state`
    - `test_mode_switch_discards_stale_audio_buffer_before_next_frame`
- **Risk note:** these extractions intentionally avoided `widgets/spotify_bars_gl_overlay.py` and did not alter first-frame authority gates. If a future runtime issue appears, compare against this split before assuming the GL layer regressed.

### Mute Button Secondary-Stage Late-Anchor Recovery
- **Area:** Spotify secondary-stage startup / mute button reveal
- **Files:** `widgets/mute_button_widget.py`, `tests/test_mute_button_widget.py`
- **Issue:** if the mute button's secondary-stage starter fired while the media anchor was still hidden, the button could remain stranded and never begin its fade once the anchor appeared later.
- **Fix:** allow later anchor-visibility sync to release `begin_spotify_secondary_stage()` once the centralized parent secondary-stage deadline is satisfied.
- **Regression coverage:**
  - `test_mute_button_waits_for_secondary_stage_before_reveal`
  - `test_mute_button_anchor_visibility_can_release_secondary_stage`
  - `test_mute_button_anchor_sync_respects_parent_secondary_stage_deadline`
- **Runtime note:** still worth visually confirming in a real startup path because the symptom is timing-sensitive.

### SettingsManager Bulk-Mutation Cache Purge
- **Area:** settings cache invalidation after maintenance/destructive paths
- **Files:** `core/settings/settings_manager.py`, `tests/test_settings_manager.py`
- **Issue:** some bulk store mutations (`clear()`, obsolete-key cleanup, legacy preset cleanup, validation/repair) updated the JSON store without purging the in-memory settings cache, allowing stale reads to survive behind direct store writes.
- **Fix:** added a shared bulk cache-clear helper and used it in those maintenance paths.
- **Regression coverage:**
  - `test_clear_purges_cached_values`
  - `test_cleanup_obsolete_settings_clears_cached_retired_widget_shadow_keys`
  - `test_cleanup_legacy_global_preset_state_clears_cached_legacy_keys`

### SST Replace-Import Must Actually Replace
- **Area:** SST import destructive-flow semantics
- **Files:** `core/settings/sst_io.py`, `tests/test_settings_manager.py`
- **Issue:** `import_from_sst(..., merge=False)` claimed to replace instead of merge, but did not clear the existing store first, so stale settings could survive a supposed replace import.
- **Fix:** clear the store before applying the imported snapshot when `merge=False`, and clear the in-memory cache through the shared helper.
- **Regression coverage:**
  - `test_import_from_sst_replace_mode_clears_stale_settings`
  - `test_preview_import_from_sst_replace_mode_reports_removed_sections`

### Transition Random Pool Parity and Uniformity
- **Area:** engine-driven random transition selection
- **Files:** `engine/screensaver_engine.py`, `tests/test_transition_distribution.py`
- **Issue:** the engine's real random-transition chooser had drifted from the broader transition contract: `Burn` existed in defaults/factory/UI expectations but was omitted from the engine's actual random pool, making it effectively dead in normal random mode. There was also no automated guard proving long-run transition choice stayed approximately uniform across the enabled pool.
- **Fix:** restore `Burn` to the engine random pool and add a deterministic statistical regression test over many draws.
- **Regression coverage:**
  - `test_random_transition_pool_can_select_burn_when_hw_accel_enabled`
  - `test_random_transition_distribution_is_approximately_uniform_for_enabled_pool`
