# Regression Notes

Last updated: 2026-05-13

Smaller resolved regressions and follow-up hardening notes that are worth keeping visible,
but do not belong in `Docs/Historical_Bugs.md`.

## 2026-05-13

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
