# R-22 — 2026-05-07 — Spotify Visualizer State Bleed: Runtime Bar Arrays Not Cleared During Mode Transitions (Resolved)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Observed runtime symptom:** Spotify visualizer mode switches (e.g., DevCurve → Spectrum) caused visual state bleed where the new mode would start with stale bar array values from the previous mode. Spectrum would start roof-pinned or move as a uniform ceiling line; DevCurve would start dead/barely reactive.
- **Actual root cause:** Runtime bar/display state arrays (`_display_bars`, `_target_bars`, `_visual_bars`, `_per_bar_energy`) were not being cleared during mode transitions. The `reset_mode_owned_runtime_state()` function cleared these arrays, but the clearing occurred in the wrong order relative to engine reset, and there was no source tracking to prevent stale compute/frame commits from old activations.
- **What finally worked:** Three coordinated fixes:
  1. **Bar clearing order:** Moved `_clear_runtime_bar_state()` call earlier in `on_mode_fade_out_complete()` so bars are cleared before `prepare_engine_for_mode_reset()`. Also moved the RENDER_STATE logging for `after_full_runtime_fade_out_complete` to occur AFTER the reset to capture the cleared state.
  2. **Direct bar clearing in reset:** Strengthened `reset_mode_owned_runtime_state()` to directly clear all four runtime bar arrays to zero, rather than relying on a separate helper call.
  3. **Source tracking:** Added source generation/activation tracking fields (`_display_bars_source_generation`, `_display_bars_source_activation`, etc.) to the widget. These fields are cleared to `-1` during reset and set from the current engine generation/activation when bars are written from engine frames. This allows detection of stale compute/frame commits in logs.
- **Why the final solution worked:**
  - Bar arrays are now guaranteed to be zero at all reset checkpoints (`after_full_runtime_fade_out_complete`, `after_full_runtime_prepare_reset`, `after_technical_config_prepare_reset`)
  - Source tracking allows RENDER_STATE logs to prove that first non-zero bars after reset come from the current activation, not a stale one
  - The ordering fix ensures bars are cleared before any engine reset logic that might re-introduce state
- **Regression guards added:**
  - `test_on_mode_fade_out_complete_clears_bar_arrays_before_prepare_engine_reset`: Proves old-mode display bars cannot survive into `prepare_engine_for_mode_reset()`
  - `test_reset_mode_owned_runtime_state_clears_runtime_bar_arrays`: Verifies the reset function clears all bar arrays and source tracking fields
  - `test_prepare_engine_for_mode_reset_does_not_call_replay_engine_config`: Ensures no replay regression
  - `test_stale_activation_frame_cannot_commit_display_bars_after_mode_reset`: Verifies source tracking fields are cleared after reset
- **Validation evidence:** Runtime logs from Spectrum → DevCurve switch show:
  - All reset checkpoints have `display_max=0.000`
  - First non-zero display bars have `display_source_generation` and `display_source_activation` matching current `engine_generation` and `engine_activation`
  - Overlay generation/activation match engine generation/activation
  - No stale activation detected
- **2026-07-11 Bubble/Spectrum settings-roundtrip sanity recheck:**
  - Bubble loaded identical `Preset 1 (Deep Sea)` technical values before entering Settings and after the settings rebuild, received fresh generation/activation ownership, created a new simulation, and returned to comparable visible drift/reactivity. The one weak post-settings sample followed an explicit paused interval and the normal roughly 1.5-second playback-resume ramp; it was not poisoned state.
  - Spectrum hot activation and post-settings recreation both cleared runtime bars before accepting fresh frames. Their first visible measurements were close (`0.823/0.648` versus `0.808/0.620`), and floor/AGC settling was likewise equivalent (`0.430/0.040 -> 0.536/0.999` versus `0.430/0.036 -> 0.534/1.000`).
  - No `FIRST_FRAME_GUARD`, `PARITY`, technical replay miss, shader fallback, stale-frame warning, or asymmetric cadence collapse appeared in these passes.
  - Cached `[PERF][SPOTIFY_VIS][BUBBLE]` summary lines can continue after switching to Spectrum or Blob because the diagnostics dictionary is not immediately cleared/gated. In the audited logs no Bubble simulation, drift, or dispatch continued; these lines are stale telemetry only and must not be classified as cross-mode runtime poison without corresponding Bubble execution evidence.
  - `[FIRST_FRAME_PRIMER]` with stale overlay generation/activation is the guard doing its job before the first authoritative push. Treat it as poison only if current generation/activation authority fails to replace the stale payload, or if it is accompanied by a guard/parity/stale-commit failure.
- **Keep-closed checks:**
  - Targeted tests:
    - `tests/test_spotify_visualizer_widget.py -k "first_frame_guard or before_first_overlay_push_logs_once_per_source_signature or runtime_switch_paths_reset_all_bleed_state_for_all_modes or mode_switch_synthetic_audio_matches_fresh_worker_after_reset or widget_manager_preset_cycle_discards_real_engine_bleed_state or mode_switch_discards_stale_audio_buffer_before_next_frame"`
    - `tests/test_spotify_visualizer_mode_transition.py`
    - `tests/test_ghost_isolation.py -k "TestOverlayModeResetIsolation"`
  - Log markers to grep during runtime validation:
    - `FIRST_FRAME_GUARD`
    - `before_first_overlay_push`
    - `after_first_overlay_push`
    - `MODE_RESET_ASSERT`
    - `No technical config available`
  - Healthy sign pattern:
    - no `FIRST_FRAME_GUARD`
    - balanced `before_first_overlay_push` / `after_first_overlay_push`
    - no replay-miss line such as `No technical config available for mode=...`
    - no reset checkpoints showing non-zero stale display bars before fresh-frame acceptance
- **Later closure hardening (2026-06-01):**
  - The first-visible path now explicitly permits a hidden primer frame when the overlay still belongs to the previous activation, instead of allowing that stale handoff to count as the authoritative first visible push.
  - Fresh reactive-mode activation coverage was widened beyond raw bar-array clearing:
    - hot mode switch and preset cycle now have synthetic-audio oracle tests that compare the first authoritative visible frame against a fresh activation oracle under the same preset-owned technical values
    - runtime settings cleanup now strips retired global visualizer technical keys from current-schema settings instead of letting `validate_and_repair()` keep re-honoring legacy dirt on every load
  - Healthy June 2026 runtime logs show the expected shared pattern across startup, settings recreate, and hot mode switch:
    - `before_first_overlay_push`
    - optional `[SPOTIFY_VIS][FIRST_FRAME_PRIMER]` when overlay state is stale
    - `after_first_overlay_push` with current activation/generation
    - no `[SPOTIFY_VIS][PARITY]` warnings and no `FIRST_FRAME_GUARD` warnings
- **Blob subtype hardening (2026-07-11):** the stable `blob` mode now contains explicit `mighty` / `shaped` renderer subtypes, which exposed a reset seam that ordinary mode-change detection cannot see. `blob_type` is now canonical, legacy aliases/`blob_shaper_enabled` migrate forward without re-emission, preset/custom payloads strip the inactive subtype's creative fields, and a type change clears both contour-solver families plus ghost/peak/pocket state before the new frame is accepted.
- **Takeaways:**
  - Runtime state that can cause visual bleed must be cleared explicitly during mode transitions
  - Source tracking is valuable for diagnosing state bleed issues in logs
  - RENDER_STATE logging must be placed after state changes to capture the correct state
  - Do not rely on implicit clearing or ordering assumptions for critical visual state
  - First-visible activation parity needs a stronger bar than “no obvious reset leak”: hot activation, preset cycle, clean startup, and settings recreate should all converge on the same authoritative first-visible contract
  - A stable visualizer mode may still contain renderer subtypes. If subtype identity changes without the mode id changing, treat it as an explicit reset boundary rather than assuming mode-reset hooks will fire.

## Record Provenance

This standalone file preserves the complete former inline `R-22` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
