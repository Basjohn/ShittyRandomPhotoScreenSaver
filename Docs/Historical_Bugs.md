# Historical Bugs

Last updated: 2026-05-08

Track significant bugs with clear dates, failed attempts, and final fixes.
This is the long-term anti-regression record for the project, not an active task list.

## Quick Navigation (Numbered IDs)

### Open Issues
1. [U-05 — 2026-04-08 — MC Keyboard Focus / Ctrl Halo Runtime Input Family Reopened (Unresolved)](#U-05)
2. [U-06 — 2026-04-30 — Multi-Monitor MC Shadow Cache Corruption On Focus Loss (Unresolved)](#U-06)

### Recent Resolutions
1. [R-22 — 2026-05-07 — Spotify Visualizer State Bleed: Runtime Bar Arrays Not Cleared During Mode Transitions (Resolved)](#R-22)
2. [R-21 — 2026-05-04 — Visualizer Painted-Card GL Content Escaping Card Boundary (Resolved)](#R-21)
3. [R-19 — 2026-04-25 — Bubble / Blob Signal-Contract Trap: Dead Smoothed Hold vs Raw-Energy Blowout (Resolved)](#U-02)
4. [R-20 — 2026-04-25 — Non-Mirrored Spectrum Vocal Lane Still Missing After Claimed Landing (Resolved)](#U-03)
5. [R-18 — 2026-04-23 — Settings Dialog Flicker / Taskbar Ghost (`Qt691QWindowIcon`) (Resolved)](#R-18)
6. [R-01 — 2026-04-09 — Settings Shell Outer Border Radius / Corner Bleed (Resolved With Caveats)](#R-01)
7. [R-02 — 2026-04-08 / 2026-04-09 — Reddit Helper Link Handoff Fails In Real Screensaver Runtime (Resolved)](#R-02)
8. [R-03 — 2026-04-18 — Sine Idle Motion Dead/Flat During Paused State (Resolved)](#R-03)
9. [R-04 — 2026-04-18 — Visualizer Curated Preset Selection Reused Custom Runtime Values (Resolved)](#R-04)
10. [R-05 — 2026-04-18 — Visualizer Preset Slot Label Mismatched Edit Target (Resolved)](#R-05)
11. [R-06 — 2026-04-11 — Visualizer Preset Override Bug (MERGE Semantics + Cross-Mode Pollution + Call-Site MERGE) (Resolved)](#R-06)

### Archived Context
1. [A-01 — MAJOR VISUAL BUG: Settings Dialog Flicker / Placeholder Regression — Historical Investigation Archived](#A-01)
2. [A-02 — 2026-02-24 — Spotify Visualizer "Crossover Persistence" (Blob muted after mode switch)](#A-02)
3. [A-03 — 2026-03-22 — Settings Dialog Flicker / Placeholder Regression (Resolved) - USER NOTE: UNRESOLVED BUT LOW PRIORITY NOW. SEE DUPLICATION OF THIS ISSUE IN THIS VERY DOCUMENT.](#A-03)
4. [A-04 — 2026-03-22 — MC Keyboard Focus / Ctrl Halo Interaction Regressions (Historical Partial Fixes Archived; superseded by U-05 current matrix)](#A-04)
5. [A-05 — 2026-03-22 — Blob Ghost/Pulse Investigation (Resolved Subsystems Archived)](#A-05)

### Older Resolved Archive
1. [R-07 — 2026-03-28 — Startup Fade / Visualizer Secondary-Stage Ownership Split (Resolved)](#R-07)
2. [R-08 — 2026-02-26 / 2026-03-05 — Pixel Shift Visualizer Bleed-Through (Resolved)](#R-08)
3. [R-09 — 2026-03-05 — Settings Spinbox/LineEdit Fill Regression (Resolved)](#R-09)
4. [R-10 — 2026-03-06 — Widget C++ Object Already Deleted on Provider Switch (Resolved)](#R-10)
5. [R-11 — 2026-03-14 — Visualizer Preset Tooling Regression (Resolved)](#R-11)
6. [R-12 — 2026-04-09 — Runtime Custom Slot Replaced While Cycling Presets (Resolved)](#R-12)
7. [R-13 — 2026-04-13 — Visualizer Sine/Oscilloscope Lines 4-6 Settings Never Persisted (Resolved)](#R-13)
8. [R-14 — 2026-04-17 — Blob Inward-Liquid Runtime Handoff Broke GL Overlay Push (Resolved In Code, Visual Validation Pending)](#R-14)
9. [R-15 — 2026-04-18 — Frozen Curated Presets Silently Fell Back to Onefile Tree (Resolved)](#R-15)
10. [R-16 — 2026-04-18 — One-Dir Runtime Misdetected As Script + Curated Slot Drift (Resolved)](#R-16)
11. [R-17 — 2026-04-18 — Goo No-Gap/Artifact Regression Family (Resolved In Dev-Gated Path)](#R-17)

## Recent Entries

<a id="R-18"></a>
### [R-18] 2026-04-23 — Settings Dialog Flicker / Taskbar Ghost (`Qt691QWindowIcon`) (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final state:** the transient taskbar/titlebar ghost during settings startup was removed without disabling startup switches or custom styling.
- **Root cause:** a redundant `setVisible(True)` call for the visualizer preset slider edit button in `ui/tabs/media/preset_slider.py` was triggering transient helper windows (`Qt691QWindowIcon`) during construction.
- **What proved it:** automated harness isolation (`tools/flicker_test.py`) plus external HWND observer traces (`tools/winprobe_observer.py`) reproduced and then eliminated the ghost across targeted and full-dialog variants.
- **Final fix:** remove the redundant explicit visibility call and keep the existing widget default visibility behavior.
- **Why it worked:** the fix removed the actual constructor-time native-window trigger instead of masking behavior (no startup-flag restrictions, no style rollback).
- **Harness note:** keep the flicker harness + observer pair; they are now part of the regression toolbelt for this bug family.


<a id="R-01"></a>
### [R-01] 2026-04-09 — Settings Shell Outer Border Radius / Corner Bleed (Resolved With Caveats)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** the settings shell now uses a forged rounded outer-border paint compromise rather than true window rounding. Live validation got the bleed down to a near-imperceptible level while preserving acrylic, the custom title bar, and the existing inner styling contract.
- **What finally worked:** a paint-only border treatment in `ui/settings_dialog.py`.
  - the real acrylic top-level window remains structurally unchanged
  - the white outer border is still custom-painted in `paintEvent`
  - a darker backing stroke and a forged corner-cover path are painted under that border
  - the accepted outer-corner radius ended up as a very conservative compromise (`6.5`) rather than a visually stronger curve
- **Why the final solution worked:** it solved the correct seam.
  - it did not ask Qt/Windows to genuinely round, clip, or mask the top-level acrylic HWND
  - it did not expose any acrylic margin outside the visible shell
  - it did not touch the custom title-bar composition again
  - it kept all risk localized to a small paint-only edge treatment
- **Important caveats:**
  - this is an accepted compromise, not a mathematically perfect true rounded window edge
  - a trace amount of corner fringe may still exist on some machines/themes/compositor paths
  - pushing the radius stronger than the accepted range quickly re-enters regression territory
  - the fix is intentionally conservative to stay mixed-machine friendly and avoid reopening the much worse failures below
- **Key failed methods worth preserving:**
  - true outer-window rounding: live runtime bled all four corners and broke the top/title-bar segment
  - inset inner-shell/card illusion: exposed a sharp black acrylic strip outside the border
  - hidden-render/offscreen validation as sign-off: produced false confidence and did not match live compositor behavior
  - mask/polygon clipping and dialog-shadow paths from the older styling history: incompatible with this acrylic/translucent frameless shell family
- **Validation rule to preserve:** for this bug family, hidden render is only a paint sanity check. Live runtime on the real Windows shell is the only valid sign-off path.
- **Takeaways:**
  - keep acrylic untouched unless a future rewrite explicitly budgets for it
  - prefer forged-corner paint over true outer-window rounding for this dialog family
  - treat “almost invisible bleed with no collateral regressions” as the practical success bar here, not a quest for perfect geometry at any cost


<a id="R-02"></a>
### [R-02] 2026-04-08 / 2026-04-09 — Reddit Helper Link Handoff Fails In Real Screensaver Runtime (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** real runtime success now holds with a durable reusable scheduled task named `SRPSS_RedditHelper`, interactive-only launch authority, normal saver exit, helper-side shell polling, and post-handoff self-exit. The queue/clipboard fallback behavior remains secondary.
- **What finally worked:** the winning launch-authority model is:
  - saver writes queue entries and exits normally
  - saver may refresh a benign ProgramData session ticket while active, but that ticket never gates saver shutdown
  - Windows Task Scheduler owns helper launch authority in the logged-in user desktop
  - the task definition is durable and reusable; only the helper process is ephemeral
  - helper waits for shell readiness independently, opens the URL, and exits itself
- **Actual final technical solution:** Task Scheduler registration uses native COM XML registration with `InteractiveToken`.
  - the XML owns the principal `UserId`
  - the COM registration call passes empty user/password variants
  - runtime starts the task with `schtasks /Run`
  - helper/browser launch remains shell-native (`os.startfile` first)
- **Why the final solution worked:** it cleanly separated responsibilities.
  - saver no longer tries to birth or manage the helper from the active saver desktop
  - helper no longer influences saver exit timing
  - Task Scheduler provides the user-desktop launch authority without a 24/7 resident process, token tricks, or repeated runtime prompts
- **Key failed methods worth preserving:**
  - persistent Windows-login helper: rejected because it kept the helper alive outside actual screensaver use
  - click-path helper bootstrap on the same Reddit exit click: regressed into a black/dark-grey cursor-only trap while helper waited for shell readiness
  - saver-desktop preload/spawn, even detached: still regressed into black-screen/dead-Winlogon behavior
  - `schtasks /Create` as the registration authority: kept pulling user-task registration back toward password-oriented semantics and failed for this product shape
  - COM XML registration with `encoding="UTF-8"` in the XML declaration: failed because the XML was being passed as a Unicode COM string
  - COM XML registration while also passing user/password args into `RegisterTask(..., TASK_LOGON_INTERACTIVE_TOKEN)`: failed with credential/logon errors because the XML already owned the principal
- **Useful supporting work that remained part of the fix:**
  - removed the app-driven shutdown race that could kill the session helper before deferred URLs became eligible
  - removed the legacy `HKCU\Run` startup helper path
  - kept MC direct-open behavior separate from real SCR helper authority
  - added ProgramData breadcrumb logging for packaged diagnosis
  - added a best-effort clipboard copy of clicked Reddit URLs as a non-blocking fallback only
  - shortened secure-desktop queue delay from `11.0s` to `3.0s`
  - shortened helper shell-settle wait from `1.0s` to `0.75s`
- **Repo-side proof/harness now available:** `python tools\reddit_helper_task_harness.py --action smoke-test --task-name SRPSS_TaskHarness_Test`
  - this locally proved register/query/run/delete of the same native task-authority layer used by the installer/runtime
- **Observed final validation evidence:**
  - installed task now queries successfully as `\SRPSS_RedditHelper`
  - task is `Interactive only`
  - real runtime success has been observed
- **Takeaways:**
  - do not let helper state leak back into saver teardown logic
  - do not trust preview/script success as proof of real SCR behavior
  - for this feature family, Windows launch authority matters more than queue semantics once queueing already works


<a id="R-03"></a>
### [R-03] 2026-04-18 — Sine Idle Motion Dead/Flat During Paused State (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** Sine idle now remains visibly alive while paused, preserves authored travel direction semantics, and avoids drift/snap artifacts when resuming from idle.
- **Observed failure pattern:**
  - paused Sine intermittently showed zero visible travel despite shader recompiles and passing tests
  - one attempted fallback produced a flat/near-flat visual line
  - later fallback restored motion but introduced out-of-sync lane drift, snap-back, and direction inversion vs authored travel
- **Failed approaches worth preserving:**
  - shader-only idle-phase tweaks without hard runtime payload checks
  - lane-1-only travel fallback (ineffective when visible emphasis came from other lanes)
  - absolute wall-clock shift magnitudes in fallback phase math (precision loss risk inside shader phase arithmetic)
  - per-line multiplier drift in paused fallback (visual de-sync then snap-back)
- **Why the final solution worked:**
  - moved idle fallback authority into renderer upload logic (active-lane aware), not just shader assumptions
  - used bounded incremental idle phase accumulation (wrapped), not absolute-time magnitude injection
  - corrected fallback direction semantics to match existing Sine travel contract (`1=left`, `2=right`)
  - enforced phase-coherent fallback across active lines to remove lane drift/snap artifacts
  - added paused diagnostics at overlay state + uniform upload boundaries so runtime payload mismatches can be seen directly in logs
- **Takeaways:**
  - for paused-idle visual bugs, tests must verify behavior contracts but runtime diagnostics must verify actual per-frame payload values
  - do not use unbounded time-based shift magnitudes in renderer fallback paths
  - preserve authored direction semantics across all fallback layers


<a id="R-04"></a>
### [R-04] 2026-04-18 — Visualizer Curated Preset Selection Reused Custom Runtime Values (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** selecting a curated visualizer preset now deterministically applies curated values, and selecting Custom applies custom values only.
- **Observed failure pattern:**
  - curated preset selection sometimes behaved like a hybrid of curated + prior custom/live runtime values
  - one problematic example was Bubble preset changes where `manual_floor`/`audio_block_size` continued reflecting stale custom values, degrading reactivity and making presets look "wrong"
- **Root cause:**
  - `SpotifyVisualizerSettings.from_mapping()` applied `apply_preset_to_config(...)` and then re-applied a broad runtime override set through `_restore_explicit_visualizer_runtime_overrides(...)`
  - this post-overlay restore step could stomp curated payload values with stale source mapping values
  - additionally, `apply_preset_to_config(...)` preserved mode technical keys not present in curated payloads, allowing more hidden carry-over
- **What finally worked:**
  - removed the post-overlay runtime override restore pass from model hydration
  - tightened curated apply semantics to clear all mode-specific keys not present in the curated payload before applying curated settings
  - kept Custom slot semantics unchanged (`Custom` remains pass-through for user-authored state)
- **Why the final solution worked:**
  - it enforces one authoritative source per selection path:
    - curated index -> curated payload
    - custom index -> custom payload
  - there is no longer a second merge phase that can re-introduce stale state after curated application
- **Regression guards added:**
  - curated apply clears mode keys absent from curated payload
  - curated `from_mapping` values win over saved custom/runtime values
  - custom `from_mapping` preserves custom values
- **Takeaways:**
  - do not add post-overlay re-merge phases in visualizer preset hydration
  - if curated presets are selected, partial technical carry-over from prior custom state is a correctness bug, not a convenience feature


<a id="R-05"></a>
### [R-05] 2026-04-18 — Visualizer Preset Slot Label Mismatched Edit Target (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Observed failure pattern:**
  - preset slider labels could disagree with `Edit Preset` target file
  - `Save Preset As…` default path could drift back toward onefile extraction-like roots in some one-dir runtime shapes
- **Root causes:**
  - onefile extraction path detection was too strict (`part == "onefile"`), so prefixed extraction folder names could bypass shared ProgramData root enforcement
  - curated parser trusted embedded payload `name` too much, allowing stale authored metadata to mislabel slots despite filename slot correctness
  - `get_preset_file_path()` used `first-match` filename lookup while curated slot loading used `last-wins` index overwrite behavior; duplicate-slot files could therefore produce label/file divergence
  - snapshot override payload names could rename curated slot labels, even when `Edit Preset` still points to curated files
- **What fixed it:**
  - broadened onefile extraction detection to any segment starting with `onefile`
  - curated parsing now prefers filename-derived names and slot indices
  - file-open path resolution now follows the same parser/precedence as curated slot loading
  - snapshot overrides now replace settings only for existing curated slots and preserve curated labels
- **Why the final solution worked:**
  - all user-facing slot surfaces (label, slot assignment, edit file path) now use one consistent slot-resolution contract
  - root resolution no longer relies on a brittle exact folder-name check
- **Guardrails/tests added:**
  - onefile-prefixed runtime path resolves to shared ProgramData
  - curated filename-name precedence test
  - duplicate-slot file path precedence parity test
  - snapshot override cannot rename curated slot labels




<a id="R-06"></a>
### [R-06] 2026-04-11 — Visualizer Preset Override Bug (MERGE Semantics + Cross-Mode Pollution + Call-Site MERGE) (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Final resolved state:** All three MERGE/pollution bugs in preset loading/saving were fixed. Preset application uses CLEAR-then-APPLY at every layer, and saving only collects current-mode settings.
- **What finally worked:** Three distinct fixes across two sessions:
  1. **Loading path fix (2026-04-11):** Changed `apply_preset_to_config()` in `core/settings/visualizer_presets.py` to use CLEAR-then-APPLY pattern. Clears all mode-specific keys not present in the preset before applying the preset's settings.
  2. **Saving path fix (2026-04-11):** Modified `save_media_settings()` in `ui/tabs/widgets_tab_media.py` to only collect settings for the current visualizer mode instead of collecting from all modes.
  3. **Call-site fix (2026-04-12):** Both callers of `apply_preset_to_config` (`_on_visualizer_preset_changed` in `widgets_tab.py` and `cycle_visualizer_preset` in `widget_manager.py`) used `.update()` to merge the clean result back into the live config dict. `.update()` only adds/overwrites — it never removes stale mode-specific keys that `apply_preset_to_config` had cleared. Replaced with `restore_visualizer_snapshot()` which does proper in-place CLEAR-then-APPLY.
- **Why the final solution worked:** It addressed all three root causes:
  1. MERGE semantic inside `apply_preset_to_config`: The old `merged.update(preset_settings)` only overwrote keys present in the preset.
  2. Cross-mode pollution in saving: The old save path collected settings from ALL modes.
  3. Call-site MERGE: Even after fix #1, the callers used `.update()` to merge the returned clean dict back into the live config, re-introducing the exact same stale-key problem at the call site.
- **Symptoms before fix:**
  - Custom settings (shaper, others) were overriding preset application
  - User got "stuck" on shaped blob even after explicitly choosing unshaped presets
  - Reset did not clear the stuck state
  - Selecting "The Mighty Blob" in settings showed selected but rendered Preset 3 behavior
  - Custom slot may not have been surviving hotswapping
  - When user saved a custom preset (e.g., Bubble Preset 4 → Custom → Save As Preset 9), the saved preset contained incorrect reactions and behavior due to pollution from other modes' default values
- **Root causes:**
  1. **BUG #1 - MERGE Semantic:** `apply_preset_to_config()` used `merged.update(preset_settings)` which only overwrote keys present in preset. Keys not in preset (e.g., `blob_shaper_enabled`) persisted from previous config.
  2. **BUG #2 - Cross-Mode Pollution:** `save_media_settings()` collected settings from ALL modes (`collect_spectrum_mode_settings()`, `collect_bubble_mode_settings()`, etc.). Inactive modes returned fallback defaults that polluted saved presets.
  3. **BUG #3 - Call-Site MERGE:** `_on_visualizer_preset_changed` and `cycle_visualizer_preset` used `vis_config.update(applied)` to merge the clean result of `apply_preset_to_config` back into the live dict. Since `.update()` only adds/overwrites, stale mode-specific keys (like `blob_shaper_enabled: true` from Custom) survived into curated presets that never declared them.
- **Affected modes:** ALL visualizer modes (Blob, Spectrum, Bubble, Sine Wave, Oscilloscope) were affected by the MERGE bugs. The pollution bug affected any user who saved custom presets.
- **Verification:** 11 cycling tests pass (including 2 new regression tests for Bug #3), 295 broader tests pass. Manual verification confirms no cross-mode pollution.
- **Defense in depth:** All three layers are now fixed:
  1. Loading: `apply_preset_to_config` clears mode-specific keys before applying presets
  2. Call sites: Use `restore_visualizer_snapshot()` instead of `.update()` for proper CLEAR-then-APPLY
  3. Saving: Only collects current mode settings (prevents cross-mode pollution)
  4. Export: `extract_visualizer_snapshot()` filters to only mode-specific keys
- **Takeaways:**
  - Preset application must use REPLACE semantics at EVERY layer, not just inside the config builder — callers that merge the result back must also purge stale keys
  - `.update()` is never safe for applying preset results because it only adds; it cannot remove
  - Preset saving should be mode-scoped, not mode-agnostic
  - The normalization layer is defense-in-depth but should not be relied on as the primary guard
  - Users who saved custom presets during the buggy period may need to re-save them to remove pollution
- **Documentation:** Full investigation retained in `Docs/Visualizer_Preset_Override_Bug_Investigation.md`



## Section 2 — Unresolved / Active Investigation (Includes Archived Open Threads)

<a id="R-22"></a>
### [R-22] 2026-05-07 — Spotify Visualizer State Bleed: Runtime Bar Arrays Not Cleared During Mode Transitions (Resolved)

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
- **Takeaways:**
  - Runtime state that can cause visual bleed must be cleared explicitly during mode transitions
  - Source tracking is valuable for diagnosing state bleed issues in logs
  - RENDER_STATE logging must be placed after state changes to capture the correct state
  - Do not rely on implicit clearing or ordering assumptions for critical visual state

<a id="U-06"></a>
### [U-06] 2026-04-30 — Multi-Monitor MC Shadow Cache Corruption On Focus Loss (Unresolved)

- [ ] COMPLETELY FUCKED
- [x] ACTIVE
- [ ] AWAITING VALIDATION
- [ ] SOLVED

- **Observed runtime symptom:** in MC mode, clicking into SRPSS on Display 1 and then clicking into anything on Display 0 frequently corrupts widget shadows/shadow caches until clicking back into SRPSS restores them through existing mitigations.
- **Current suspicion:** this is a visual Qt `QGraphicsEffect`/pixmap-cache corruption path triggered by multi-monitor focus/activation changes, not a property-level effect state change that Qt exposes cleanly. Normal logs cannot currently say "shadow corrupted" with certainty unless we add external visual or pixel-based observation.
- **Immediate correction made:** Gmail was missing from `rendering/widget_effects.py`'s peer-widget overlay-effect invalidation cadence. Add `gmail_widget` there so Gmail no longer sticks out when the existing mitigation fires.
- **Research/implementation guardrails:**
  - Do not regress the MC focus restore/key fix from U-05.
  - Do not apply broad focus-policy changes across widget trees; prior H1 work caused worse shadow corruption by destabilizing Qt focus routing.
  - Do not alter visual fidelity or global shadow styling as a first response.
  - Compare any proposed permanent fix against the Phase E effect-corruption history below and against R-18/flicker lessons before touching top-level window flags, focus routing, or graphics effects.
- **Next target:** inspect recent `/logs` around focus loss/cross-display click sequences and add low-noise diagnostics around effect invalidation reasons, screen index, focus owner, and widget effect participation. If the visual corruption remains non-detectable from Qt state, document that explicitly and prefer preventing the activation/cache trigger over pretending to detect it.

<a id="U-02"></a>
### [U-02] 2026-04-10 / 2026-04-25 — Bubble / Blob Signal-Contract Trap: Dead Smoothed Hold vs Raw-Energy Blowout (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- 04/15 Status: Bubble is fine, Blob issues appear to be different at the moment. Keep as partial until sign off that Blob is perfect.
- **Current symptom family:** Bubble and Blob have repeatedly fallen into two opposite but related failure states:
  - shared smoothed/post-AGC pressure makes them feel dead, flattened, and visually stuck in hold-like states
  - rescuing them with hotter pre-AGC/raw pressure through the old downstream math flips the failure mode into Bubble max-size pinning / jerky speed and non-shaped Blob blowout / judder
- **Newly confirmed sub-trap (2026-04-10):** even after separating continuous support from burst/stage math, stale scheduler events could still be replayed as if they were fresh accents every frame:
  - Bubble was polling `peek_latest("snare")` / `peek_latest("vocal_swell")` inside `BubbleSimulation`, which let one recent event keep re-authorizing burst / overdrive
  - Blob handoff was also using `peek_latest(...)` when building the live overlay payload, which let the same scheduled event keep heating stage/event lanes across multiple frames
  - this recreates the same “always hot” family under a different disguise, so it belongs to this same bug entry rather than to a separate tuning note
- **Why this matters:** this is now clearly a recurring architectural trap, not a sequence of unrelated mode-specific tuning mistakes.
- **Root cause to preserve:** the source signal family changed, but the downstream support/overdrive/stage math was still tuned for the old one. Changing only the source path is therefore not a real fix.
- **Expanded root cause:** the mode event handoff also matters. If one-shot scheduler accents are treated like reusable level signals instead of consume-once edges, they silently bypass whatever continuous-path protections were added and keep the mode parked in a fake hot state.
- **Anti-patterns to avoid:**
  - reviving `_use_raw_energy` or other persisted sidecar toggles
  - declaring victory because only one side of the trap disappeared
  - feeding pre-AGC/raw pressure into legacy support/overdrive math unchanged
  - falling back to shared smoothed/post-AGC pressure solely because the hotter path became too aggressive
- **Anti-patterns to avoid (event handoff):**
  - using `peek_latest(...)` per frame in places that actually need consume-once accent edges
  - accepting “better reactivity” that is really just one scheduler event being replayed for its full max-age window
  - fixing only Bubble or only Blob when the shared architectural smell is stale event reuse
- **Latest code-side correction:** Blob event strengths are now consumed once at the mode handoff boundary in `widgets/spotify_visualizer/config_applier.py`, and Bubble now consumes snare/vocal scheduler edges once inside `widgets/spotify_visualizer/bubble_simulation.py` instead of polling them with `peek_latest(...)`.
- **Regression coverage added:**
  - `tests/test_transient_per_mode_integration.py::TestBlobSchedulerEventWiring::test_build_kwargs_consumes_blob_events_once_per_mode_snapshot`
  - `tests/test_bubble_reactivity.py::TestBubblePlateauGuardrails::test_bubble_burst_path_consumes_scheduler_edges`
- **Latest code-side correction (2026-04-11):** the remaining continuous-path contract was tightened rather than replaced.
  - Bubble overdrive now uses a stricter burst/hold gate so medium vocal phrases can release instead of living in active hold.
  - Blob now performs a faster calm-only unwind when live/support/glow/stage pressure is still hot after the incoming phrase has already cooled.
- **Latest code-side correction (2026-04-11 later pass):** the current rescue work stayed narrow and tried to remove specific remaining live failure paths instead of rewriting the whole mode family again.
  - Bubble no longer uses the retired persisted raw-energy toggle path; the remaining Bubble work is on the live contract only.
  - Bubble overdrive was tightened further and the hold time shortened again because real logs still showed routine re-entry at gate values that were too low for an emergency lane.
  - Bubble big-bubble sustained support was cooled and its decay was strengthened so big bubbles can breathe instead of camping near the ceiling on ordinary hot passages.
  - Bubble refill now has post-startup spawn budgets so missing-count backlogs cannot all respawn in one frame.
  - Bubble spawn overlap spacing is now size-aware so big bubbles are not allowed to arrive nearly on top of each other.
  - Blob now applies a non-circular final-radius safety floor after wobble is added, specifically to stop deep inward pinches without flattening the silhouette into a safe boring circle.
- **Behavior-level regression coverage added (2026-04-11):**
  - `tests/test_bubble_reactivity.py::TestBubblePlateauGuardrails::test_medium_vocal_run_does_not_latch_overdrive_for_entire_phrase`
  - `tests/test_visualizer_reactivity_quality.py::test_non_shaped_blob_log_shaped_hot_seed_unwinds_quickly`
- **Additional regression coverage added (2026-04-11 later pass):**
  - `tests/test_bubble_reactivity.py::TestBubblePlateauGuardrails::test_post_initial_refill_does_not_spawn_a_backlog_wave_in_one_tick`
  - `tests/test_bubble_reactivity.py::TestBubblePlateauGuardrails::test_post_initial_refill_caps_big_bubble_backlog_too`
- **Newly confirmed continuation (2026-04-17):** bubble could still dead-start in chorus and flatten over long hot passages because the control path was effectively hard-ceilinged.
  - Transient log signatures showed repeated `bass=1.000 mid=1.000` with near-zero flux under loud sections.
  - Final mitigation path:
    - introduce a dedicated bubble/blob control-lane normalization (`_bubble_control_norm`, `_bubble_pre_agc_*`)
    - feed transient bus from control-normalized pre-AGC energy (not hard `min(1.0, ...)`)
    - make beat-engine pre-AGC accessor prefer the control-lane values for bubble/blob consumers
  - New regression tests:
    - `tests/test_bubble_reactivity.py::TestSustainedLoudSection::test_hot_start_chorus_still_reacts`
    - `tests/test_bubble_reactivity.py::TestSustainedLoudSection::test_hot_chorus_variation_not_flatlined`
- **Latest runtime evidence (2026-04-10 late run):**
  - Bubble is still spending long stretches inside `[SPOTIFY_VIS][BUBBLE][OVERDRIVE] hold` even on a conservative baseline similar to `preset_8_abyss`, with gate values repeatedly living around `0.36-0.87` instead of only flashing briefly on meaningful bursts.
  - Blob still shows a too-hot baseline in live diagnostics: many frames log filtered live/support values near or above `1.0` and stage-filtered values that stay elevated for long windows, which matches the user's report that even dramatically lowered custom settings still look blown out, twitchy, and max-glow-heavy.
  - This means the stale-event replay fix was real and necessary, but it did **not** finish the bug family. The remaining problem is no longer "fake hot because one event kept replaying"; it is now "continuous support / overdrive / glow contracts still run too hot for the current authored ranges."
- **Mode split to preserve:** Bubble and Blob are still part of the same signal-contract family, but the latest evidence suggests the remaining failure is not identical in both modes:
  - Bubble currently looks closer to an over-permissive overdrive / ceiling / specular contract problem, because conservative authored settings can still spend too much time in active hold.
  - Blob currently looks like both a preset-authoring problem and a runtime baseline/gain problem, because old curated presets are obviously too hot **and** even heavily reduced custom settings can still remain blown out.
- **Latest runtime/log evidence (2026-04-11):**
  - Bubble overdrive was still re-entering in real logs at gate values roughly `0.56` to `0.89`, which is too common for a true emergency lane and proved the earlier tightening was not sufficient on its own.
  - Bubble clustering reports became more specific: the visible problem was not only the explicit decorative `2-3` texture cluster. Runtime eyes described arrival piles that felt more like `~9` bubbles stacking together, especially including big bubbles, which strongly suggests refill-backlog cadence was part of the failure and not just the cosmetic cluster path.
  - Blob inward pinch remained visible even after stale-key cleanup, which pushed the root cause away from bad preset junk and toward the final geometry contract itself.
- **Latest runtime/log evidence (2026-04-11 newer run):**
  - Bubble is still a live failure in ordinary stream modes. The user explicitly reported that "nothing is solved" in practice for Bubble: it still sticks near max, overdrives constantly, produces weirdly sized elements, and forms huge groups of big bubbles.
  - Spiral/swirl variants behave noticeably better in both spawning and reactivity. That makes it much less likely that Bubble is failing for one totally global reason; the worse failure appears concentrated in the ordinary edge-spawn / stream-travel / refill family.
  - The worst recent preset examples called out by the user are `Preset 3 (Orange Soda)` and `Preset 6 (Lava Flow)`. These should be treated as active antagonists for future tracing rather than as random anecdotal bad cases.
  - Fresh log context also showed `Bubble worker: count=52` on one of the failing runs, which lines up exactly with authored target counts on the denser presets. That does not prove the preset is "wrong", but it does prove the full target density is being exposed immediately at runtime and must be considered part of the practical failure.
  - Blob is currently less catastrophic than Bubble, but still not convincingly reaching higher stages on musical changes. At the moment that looks more like baseline/preset tuning than a new clearly isolated architecture break.
- **Older-anchor comparison update (2026-04-11 later):**
  - Much older Bubble baselines are more useful here than the recent April commits:
    - `a87a46f` (`2026-03-05`, `Bubble And Burn, The Obvious Combination.`)
    - `5b82c63` (`2026-03-18`, `The Unfuckening Part 2wo`)
  - Comparing current Bubble to `a87a46f` showed two especially suspicious stream-mode inflation paths that were not part of the older healthier baseline:
    - the newer full-card initial fill path that scatters the entire authored target count across the card during startup/reset
    - the newer temporary small->big promotion path that lets ordinary small bubbles behave like extra bass-driven big bubbles during beat bursts
  - This matters because the user's current runtime failure is not just "there are many bubbles." It is "ordinary stream presets look wrongly big, overstuffed, and badly grouped." Those two newer paths are a much better match for that symptom family than the old decorative small-cluster branch by itself.
  - The same older comparison also reinforces that recent Bubble clutter is not coming from a wild authored preset change alone. `Orange Soda` still authors very dense counts, but older Bubble presented that density through entry/travel behavior rather than immediately exposing the whole population in-card.
- **Latest code-side correction (2026-04-11 newest pass):**
  - kept gradient/specular improvements intact; did **not** throw away modern Bubble styling just to chase old runtime feel
  - ordinary stream modes no longer use the same in-card initial-fill scatter path that was immediately exposing full authored dense counts on cold start and reset
  - swirl/center-origin families still keep intentional in-card cold start behavior because that belongs to their authored motion language
  - promotions were kept, but ordinary stream modes now treat them as a tiny short-lived hot-lane assist rather than a general-purpose second big-bubble population
  - promoted stream bubbles now require the real big-bubble lane to already be hot, only promote one bubble at a time, and use much weaker sustained support so they add fresh accent noise instead of inflating the whole card
- **Latest runtime evidence (2026-04-11 newest screenshot/report):**
  - the latest ordinary-stream change removed the old in-card clutter path, but it also exposed a new directional cold-start failure: startup now produces obvious entry-lane columns / stacked vertical bands across directional presets
  - the first attempted answer to that was a seeded travel-depth ramp, but runtime rejected it too: instead of one birth queue at the edge, it produced several visible birth columns before the stream normalized
  - that means the seeded-depth idea itself was the wrong fix shape for this product. For directional presets, startup should simply trickle from the real entry side with restrained early spawn budgets rather than trying to fake an already-filled stream
  - Bubble big bubbles are also still not breathing correctly in live use. They remain too maxed and do not contract deeply enough between hits, even though `bubble_big_contraction_bias` exists as a control
  - that makes the current Bubble state a split bug family:
    - directional stream startup/depth seeding is wrong
    - big-bubble pulse/contraction balance is still wrong
  - these need to stay split in future investigation so we do not keep "fixing" one by worsening the other
- **Regression coverage added for this narrower fix:**
  - `tests/test_bubble_reactivity.py::TestInitialFillContract::test_ordinary_stream_mode_does_not_spawn_full_density_in_card_on_cold_start`
  - `tests/test_bubble_reactivity.py::TestInitialFillContract::test_swirl_mode_may_still_use_in_card_initial_fill`
  - `tests/test_bubble_reactivity.py::TestSmallBubblePromotion::test_stream_mode_promotions_only_appear_when_big_lane_is_hot`
  - `tests/test_bubble_reactivity.py::TestSmallBubblePromotion::test_stream_mode_promotion_expires_quickly`
- **New gap exposed by runtime:** the current startup tests only prove that ordinary stream modes no longer dump the full authored density in-card on the first tick. They do **not** yet prove that the remaining edge-spawn depth distribution looks like a real flowing stream instead of a visible column. A dedicated startup-depth/entry-column test is needed.
- **Testing gap updated (2026-04-11):** this is no longer a pure reproduction gap.
  - current synthetic coverage now includes log-shaped failure tests for both sides of the remaining bug family, not just stale-event replay and clean alternating phrases
  - the remaining gap is live validation and feel-signoff, especially around Bubble ceiling/specular behavior and Blob authored-preset stability, not the absence of behavior-level reproduction in the suite
- **Latest runtime evidence (2026-04-11 later Bubble passes):**
  - Bubble reactivity is materially improved relative to the worst raw-energy/blowout state, but startup and grouping are still visibly regressed compared to older healthier Bubble behavior
  - directional presets still cold-start with obvious entry-side columns for several visible passes before the field settles into something more natural
  - current grouping/spacing reads too uniform and too overlap-friendly in motion, which makes the column issue more obvious rather than less
  - the user's product rule is now explicit and should be treated as authoritative:
    - small bubbles may cluster with each other and around big bubbles
    - big bubbles should avoid overlapping other big bubbles as much as possible
    - promoted small bubbles should be treated like big bubbles for spacing/overlap purposes
  - runtime screenshots now show the current regression family more clearly than logs do:
    - big bubbles still group with other big bubbles too readily
    - overlap is still too common, especially in the live flow after startup
    - startup still looks birthed in columns instead of naturally trickling in from the edge
- **Method/result update (2026-04-11):**
  - removing the old full-card cold fill was a real improvement, because it stopped immediately dumping the full authored density in-card
  - adding entry-side trickle logic was also directionally right, but current grouping and overlap still make the startup look columnar and too uniform
  - this means the remaining Bubble failure is no longer just “too many bubbles at once”; it is now specifically a bad ownership contract between startup cadence, grouping flavor, and overlap rules
- **Failed methods to keep visible so we stop looping:**
  - pushing hotter raw/pre-AGC pressure into legacy support/overdrive math unchanged
  - “fixing” deadness by reviving raw-energy style behavior without also renegotiating plateau/ceiling/refill contracts downstream
  - assuming Bubble spawn pile-ups were only the decorative cluster branch instead of checking refill cadence and backlog release
  - assuming that removing in-card initial fill automatically fixed directional stream startup; it can just trade "too much visible density" for "visible edge-column birth queue"
  - assuming Blob inward pinch was still just stale preset pollution once the stale-key path had already been fenced
  - treating green synthetic tests as equivalent to runtime sign-off for these modes
  - splitting Bubble startup handling by axis family; the user explicitly rejected “horizontal gets one boot rule, vertical gets another” as a product direction because both families exhibit the same startup defect
  - allowing big-bubble grouping logic to drift toward “everything can overlap a bit” uniformity. That erased an older healthy visual rule: big bubbles should largely avoid other big bubbles, while smalls are the permissive cluster/noise layer
- **Intended solution direction:** preserve the hit readability gained from pre-AGC routing, but solve the root signal-contract mismatch with bounded attack/release, plateau protection, ceiling control, and consume-once event ownership in the downstream math / handoff seam.
- **Validation needed:** Bubble should remain lively without living at max big-bubble size, giant specular sizing, overdrive hold for seconds at a time, or visible refill-wave pile-ups, and non-shaped Blob should stay reactive/organic without constant hot-state blowout, 24/7 max-glow behavior, or inward pinches severe enough to read as a geometric failure.
- **Loop-avoidance lessons to preserve:**
  - when Bubble or Blob regress, first identify whether the failure is continuous-path contract, stale event reuse, refill cadence, or geometry floor. Do not throw all four into one tuning bucket.
  - do not call the issue solved merely because one half of the opposite-failure pair disappeared.
  - if runtime says “worse in reality than in tests,” expand the synthetic toward the runtime evidence instead of assuming the user is seeing noise.
  - keep this entry and [Current_Plan.md](F:\Programming\Apps\ShittyRandomPhotoScreenSaver\current_plan.md) aligned so the current attempted fix and the retired bad ideas are both visible at the same time.
  - if spiral/swirl Bubble modes behave better than ordinary stream modes, do not keep applying Bubble-wide tuning blindly. Trace the edge-spawn + travel + refill path specifically.
  - dense Bubble presets should be treated as hostile-but-valid authored content. If runtime cannot present them cleanly anymore, first assume a runtime regression before assuming the preset suddenly became unreasonable.
  - when older commits were visibly healthier, compare against those much older baselines instead of only diffing the newest churn. Recent-vs-recent diffs can hide the actual regression family.
  - preserve Bubble's visual class distinction:
    - small bubbles are the permissive cluster/noise layer
    - big bubbles are the hero/readability layer and should avoid big-big overlap whenever possible
    - promoted small bubbles must obey the big-bubble overlap rules while promoted


<a id="U-03"></a>
### [U-03] 2026-04-08 / 2026-04-25 — Non-Mirrored Spectrum Vocal Lane Still Missing After Claimed Landing (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Resolution date:** 2026-04-25
- **Root cause:** the original migration only promoted one exact stock old linear layout. If a user's old `Bass / Low / Mid / Hi-Mid / Treble` family had been nudged even slightly, it bypassed migration and kept surfacing the stale labels. A stale runtime/widget default also still carried the old linear label family.
- **Fix applied:** migration now promotes legacy-shaped five-lane linear layouts lacking `Vocal` even when the user previously moved the boundaries, preserving those user positions while renaming the old `Low`/`Mid` family into `Low-Mid`/`Vocal`. Widget/model defaults were also updated so fresh/runtime paths stop reintroducing the stale labels.
- **Validation status:** user-confirmed resolved in editor UI and runtime.


<a id="U-04"></a>
### [U-04] 2026-04-21 — Settings Dialog Flicker / Taskbar Ghost (Investigation Archive; Superseded by [R-18](#R-18))

- [ ] COMPLETELY FUCKED
- [X] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Status note:** this investigation thread is kept for timeline context; the resolved outcome is tracked in **R-18 (2026-04-23)**.

- **Symptom:** When the settings dialog is summoned, the taskbar flickers and a small window with the SRPSS app icon briefly appears (typically centered on Display 0) before the dialog renders. This affects title bars / taskbar of OTHER applications (e.g. the IDE on Display 0) even though the dialog targets Display 1. Present in both engine mode (via `dialog.exec()`) and config mode (`--s`, via `dialog.show()` + `app.exec()`).
- **Earlier partial fixes (kept, each individually valid):**
  - **Fix A:** Removed premature `raise_()` / `activateWindow()` in `engine_handlers.py` — these were redundant with `exec()` internals and could produce ghost frames.
  - **Fix B:** Changed window flags from `Window | FramelessWindowHint | WindowSystemMenuHint` to `Dialog | FramelessWindowHint` — the `Window` type created an unnecessary independent taskbar entry during HWND allocation.
  - **Fix C:** Added `WA_ShowWithoutActivating` during construction, cleared in `showEvent` — prevents incidental Win32 activation during `__init__`.
  - These fixes eliminated a separate "tiny ghost window" artifact from the old window type. The primary flicker (taskbar + Display 0 title bars + small icon window) **persists** after all three.
- **Systematic isolation via `tools/flicker_test.py` (13 variants tested):**
  - Variants 1-7: Basic QDialogs with every combination of flags/attributes (`FramelessWindowHint`, `WA_TranslucentBackground`, `Dialog`, `Window`, `Tool`, stylesheets). **None flickered.**
  - Variant 8: Font registration via `QFontDatabase.addApplicationFont`. **No flicker.**
  - Variant 9: Font registration + `QGuiApplication.setFont()` global font change. **No flicker.**
  - Variant 10: Full flags + real `dark.qss` stylesheet (256ms show). **No flicker.**
  - Variant 11: Full flags + 200 child widgets (QGroupBox/QLabel/QPushButton/QCheckBox/QComboBox). **No flicker.**
  - Variant 12: All combined — font reg + global font + large QSS + 200 widgets (670ms construction). **No flicker.**
  - Variant 13: Actual `SettingsDialog` construction (2260ms). **FLICKERED — tiny central window with app icon in title bar.**
  - Variants 14-16: Same as 1/5/12 but with main.py startup steps applied first (DPI policy, `AA_UseDesktopOpenGL`, `AA_ShareOpenGLContexts`, `QSurfaceFormat.setDefaultFormat`, `app.setWindowIcon`). **None flickered.**
  - Variant 17: Actual `SettingsDialog` + main.py setup (1960ms). **FLICKERED — same tiny window.**
- **What this proves:**
  - The flicker is NOT caused by window flags, attributes, `WA_TranslucentBackground`, font loading, global font changes, large stylesheets, many child widgets, construction time, or main.py OpenGL/DPI/icon setup.
  - The flicker IS caused by something specific inside `SettingsDialog.__init__` that no mock variant reproduces — something about the specific widget tree, signal wiring, effect composition, or native API calls during its construction.
- **Failed approaches to stop repeating:**
  - Off-screen HWND creation (`self.move(-32000, -32000)` + snap in `showEvent`) — flicker still occurred.
  - Focus gap theory (reordering `engine.stop()` vs `dialog.show()`) — user confirmed "not focus related AT ALL."
  - Multi-monitor compositor / placeholder theory (Approaches A-E in the historical entry) — proven wrong; flicker occurs in standalone `--s` config mode with no engine, no compositor, no multi-monitor windowing.
  - Acrylic blur — user confirmed "added acrylic after this issue first appeared."
- **Current investigation direction:** Binary search within `SettingsDialog.__init__` to find the exact operation that triggers the tiny HWND with title bar. The tiny window has a standard title bar with the app icon, suggesting somewhere during construction a native HWND is created with `WS_CAPTION` style before frameless flags take effect, or a secondary HWND (tooltip, popup, or internal Qt helper) is briefly shown.
- **2026-04-23 follow-up isolation (new):**
  - Added auto-close harness behavior in `tools/flicker_test.py` (default `10s`) plus new targeted variants `34-36`.
  - `v34` (`force_widgets_initial_no_hydration`): **~2271ms construct**, **45** `QComboBoxPrivateContainer` helper frames already present **before** `show()`.
  - `v35` (`force_sources_initial_no_hydration`): **~519ms construct**, **0** helper frames before/after show.
  - `v36` (`force_sources_hydrate_without_widgets`): **~519ms construct**, then **15** helper frames after show (non-widgets tabs only).
  - Interpretation: the strongest construction-time pressure/flicker candidate is the **Widgets tab build path**, especially when it is initial-tab or hydrated immediately.
- **2026-04-23 automation upgrade (new):**
  - Added external observer `tools/winprobe_observer.py` and wired it into `tools/flicker_test.py` per variant run (`SRPSS_FLICKER_EXTERNAL_WINPROBE=1`).
  - This captures transient native HWNDs + foreground changes across the **entire** variant lifecycle (constructor + show), not just post-show.
  - In failing paths (`v13`, `v34`), observer repeatedly reports transient tiny caption windows:
    - class `Qt691QWindowIcon`
    - size ~`105x59`
    - title `python` (harness process title)
    - each appearance briefly steals foreground before focus returns to Codex window.
  - In control paths (`v35`, `v36`, `v18`), these transient `Qt691QWindowIcon` windows/foreground steals are absent when Widgets build pressure is removed.
- **Important correction (why earlier env A/B could still fail):**
  - `SRPSS_SETTINGS_FORCE_INITIAL_TAB_SOURCES=1` was being undermined by `_restore_last_tab_selection()`, which could switch back to saved Widgets tab after init.
  - Fixed: when force-initial-sources is enabled, last-tab restore is now skipped so the A/B toggle behavior is actually deterministic.
- **2026-04-23 root-cause breakthrough (new):**
  - Isolated to `ui/tabs/media/preset_slider.py` inside `VisualizerPresetSlider._build_ui()`.
  - The explicit `self._edit_btn.setVisible(True)` call (redundant, default is already visible) consistently triggered the transient `Qt691QWindowIcon` caption windows during startup construction.
  - Removing that single call eliminated the startup taskbar/titlebar ghost in automated repro paths:
    - `tools/flicker_test.py v54` (plain dialog + six `VisualizerPresetSlider` instances): tiny caption windows removed.
    - `v48` (SettingsDialog visualizers-only): tiny caption windows removed.
    - `v13` (full real SettingsDialog): tiny caption windows removed.
- **Immediate next step (actionable):**
  - Run live user validation in the actual startup path (normal settings open and `--s`) to confirm the ghost is gone outside harness.
  - If validated, flip this issue from `PARTIAL` to `SOLVED` and archive older hydration-deferral workaround options as no longer needed for this bug family.


<a id="U-05"></a>
### [U-05] 2026-04-08 — MC Keyboard Focus / Ctrl Halo Runtime Input Family Reopened (Unresolved)

- [x] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

- **Current symptom matrix (2026-04-23 user validation):**
  - **MC runtime (`main_mc.py`) after clicking into SRPSS window (any display/setup):**
    - Media keys fail while SRPSS remains focused.
    - Media keys begin working again when focus shifts to another application.
    - Normal control keys do not work in this state.
  - **Normal mode Windows preview runtime:** all keys work, including media keys.
  - **Normal mode Winlogon runtime:** all media keys fail; most other keys fail; `S` still works and opens Settings.
- **Why this is important:** this is no longer a "single MC key bug." It is a cross-runtime input ownership/routing split with different behavior by launch surface and focus state.
- **Active priority (2026-04-24):** make MC runtime key behavior perfect and reproducible before touching Winlogon. Winlogon may share a root cause, but it is a different runtime surface and should not steer the next fix.
- **Non-negotiable MC window contract:** fixes must preserve the MC surface as no normal taskbar entry, no Alt-Tab entry, and topmost/no-fall-behind. Normal-window comparisons are reference data only, not candidate fixes.
- **Critical clue:** `S` working in Winlogon while media keys fail suggests at least one keyboard path remains alive, but media-key capture/dispatch path diverges by runtime.
- **Constraint note:** do not casually tweak this family without heavy research; keep archived sub-fixes intact unless a replacement model is proven by runtime matrix + harness evidence.
- **Validation needed:** first isolate the exact MC breakpoint between focused MC failure and external-focus recovery. Preview and Winlogon remain reference points, not the next active target.
- **False suspects ruled out (2026-04-23 harness split runs):**
  - Generic app hotkey handling is not dead: focused MC harness captures `C key pressed - cycle transition requested`.
  - Synthetic media VK route is not dead: focused MC harness captures `InputHandler` media-key detection.
  - Injected native appcommand dispatch is not dead: focused MC harness captures `[WIN_APPCOMMAND]` in verbose logs.
  - Therefore, broad "all key plumbing is broken" is not an accurate root-cause model.
  - Important limit: these are synthetic/injected probe results. They do not reproduce the user's physical-key MC failure.
- **Live-profile parity update (2026-04-23):**
  - Harness now validates MC runtime contract before scoring probes (MC tool/splash window class, display creation, `show_on_screen`, GL compositor creation).
  - In elevated live-profile run, matrix initially showed:
    - `focused_idle`: Qt media pass, native appcommand pass, `C` pass
    - `focused_clicked`: Qt media fail, native appcommand pass, `C` fail
  - This narrows the active breakage to post-click focused input routing/state, while native appcommand ingress remains alive.
  - Native key-message probe extension (`WM_KEYDOWN/UP` for `C`) passes in `focused_clicked` while synthetic `SendInput` `C` fails, further ruling out downstream transition handler breakage.
  - Additional evidence review showed these failing `focused_clicked` cells were contaminated by focus theft in setup: click preparation could foreground external browser windows (Firefox) instead of keeping SRPSS focused.
  - Harness now marks such `focused_clicked` samples as invalid/blocked (`focused_clicked_unstable_focus_or_overlay_focus_steal`) rather than scoring them as real focused-MC failures.
  - Harness click-safety guard now disables Reddit interaction surfaces in mirrored/isolated harness profiles so focused-click automation cannot trigger outbound Reddit actions during investigation runs.
  - Mirrored-safe A/B run (`2026-04-23 22:31`) confirms both `focused_idle` and `focused_clicked` pass across strict + realistic policies when scenario validity is enforced.
  - After edge-first click targeting + invalid-row blocking landed, repeated live-profile runs produced valid focused SRPSS samples where both `focused_idle` and `focused_clicked` passed all probes (Qt media, native appcommand, native key-message `C`, transition `C`) across strict and realistic focus policies.
  - Result: previously observed `focused_clicked` failures are now treated as harness setup artifacts, not confirmed app-path regressions.
  - Result limit: the harness has not yet simulated the real-world failure. It has proved controlled synthetic/injected MC paths can work, which means the next harness target is physical/hardware ingress or an observer-backed workflow that captures the user's actual failing input.
- **What remains unresolved after ruling these out:**
  - Real hardware media-key ingress under user repro conditions still needs explicit automated/native proof (not only synthetic or injected messages).
  - Normal control-key failure in focused MC still needs the same physical/hardware-ingress treatment.
  - Newest user observation (2026-04-24): MC starts with physical keys working while unfocused; bringing MC into focus is the transition that makes keys fail.
  - Harness response: `tools/media_key_reality_harness.py --scenario focus_transition` now captures unfocused-working and focused-failing phases in one report.
  - Splash-window experiment is ruled out as a product fix: it shares the key/focus issue and becomes unstable after focus changes. Keep it only as a diagnostic comparison.
  - Native-style evidence from the current Tool baseline shows the intended guardrail shape (`WS_EX_TOOLWINDOW` + topmost), so the next investigation stays inside that contract rather than testing normal windows.
  - MC focused-click harness parity is stable only for controlled probes; remaining gap is proving/isolating divergence between synthetic/injected probes and physical hardware key ingress on user machines.
  - Winlogon asymmetry (`S` works while media keys fail) is deferred until MC is understood or the MC root cause clearly requires Winlogon comparison.
- **2026-04-25 Research + Code Analysis (new):**
  - **Hardware ingress validator confirms real-world repro**: manual click into SRPSS on Display 1 causes keys to be "eaten". Programmatic `SetForegroundWindow` and `SendInput` mouse clicks do NOT reproduce the bug.
  - **PowerToys remapping accounted for**: PgUp/PgDn remapped to Volume Up/Down appear as `injected=true` in `WH_KEYBOARD_LL`.
  - **Online research findings** (8 independent sources mapped in `Docs/MEDIAKEYDEBUG.md` Section 7.1):
    - `Qt::Tool` / `WS_EX_TOOLWINDOW` windows exhibit documented anomalous focus/keyboard behavior on Windows.
    - `activateWindow()` is unreliable when app is not already foreground (QTBUG-14062).
    - Key events are LOST during focus transitions between Qt widgets.
    - `WS_EX_TOOLWINDOW` + manual click produces "focus cursor present but no keyboard capture" — direct symptom match.
    - Tool windows can steal focus unexpectedly on `showNormal()` / activation.
    - AutoKey issue reveals distinction between **focused window** (keyboard target) vs **active window** (title bar highlight). Manual click may make SRPSS "active" but not "focused".
    - `Qt::WindowDoesNotAcceptFocus` is insufficient on Windows; native `WS_EX_NOACTIVATE` is required.
    - Embedded/native child HWNDs cause focus routing problems (Qt forum QTBUG-40320).
  - **Code analysis identified 8 compounding issues** (full detail in `Docs/MEDIAKEYDEBUG.md` Section 7.2):
    - **Issue 7 (Severity: HIGH)**: Overlay widgets may have default `StrongFocus`/`ClickFocus` policies. Manual click routes focus to a child widget that doesn't handle keys. Programmatic focus bypasses child routing. This is the **strongest candidate**.
    - **Issue 6 (Severity: MODERATE-HIGH)**: GL compositor (`QOpenGLWidget`) has its own native window. Click on compositor area may give focus to compositor widget instead of DisplayWidget.
    - **Issue 2 (Severity: MODERATE)**: `_restore_mc_input_focus()` uses `MouseFocusReason` which may route focus to child widgets.
    - **Issue 3 (Severity: LOW-MODERATE)**: `CursorHaloWidget` is a separate top-level `Qt.Tool` window that may interfere with focus ownership.
    - Other issues (focus policy toggling, coordinator stale state, Raw Input per-window registration, `perform_activation_refresh()` lack of focus restore) ruled out or low severity.
  - **Synthesized root-cause model** (speculative): Manual click triggers Qt focus routing to a child widget (overlay/GL compositor). Child widget doesn't handle keys → keys "eaten". Programmatic `SetForegroundWindow` sets focus on top-level DisplayWidget, bypassing child routing. `Qt.Tool` / `WS_EX_TOOLWINDOW` exposes this edge case; normal `Qt.SplashScreen` builds don't.
  - **Testable hypotheses documented** (7 hypotheses in `Docs/MEDIAKEYDEBUG.md` Section 7.4). Strongest test: set `NoFocus` on all child widgets (H1) or GL compositor alone (H2).
- **2026-04-25 H1 Test — FAILED and REVERTED**:
  - H1 (recursive `setFocusPolicy(Qt.NoFocus)` on all child widgets) did **NOT** fix media keys. Bug persists after manual click.
  - H1 introduced **frequent shadow corruption** on `MediaWidget` and `RedditWidget` (doubled drop shadows). Was occasional before H1.
  - **Shadow corruption mechanism**: H1 destabilized Qt's focus tree (~30+ widgets got NoFocus simultaneously). Each click caused Qt focus routing to bounce between widgets trying to find one that accepts focus. Each focus transition fired `focusInEvent`/`focusOutEvent`, which called `invalidate_overlay_effects("focus_in")`. Rapid `eff.setEnabled(False); eff.setEnabled(True)` cycles on `QGraphicsDropShadowEffect` corrupted Qt's internal `QPixmapCache`. Context menu clear-cache restored correct shadows.
  - **Prevention rule**: Never manipulate focus policies on large widget trees during runtime. Focus policy changes trigger `styleChange`/`updateGeometry` cascades that stress the shadow pixmap cache.
- **2026-04-25 Critical Discovery — `_restore_mc_input_focus` is DEAD CODE**:
  - Grepped entire codebase (excluding docs/tests): `_restore_mc_input_focus()` in `rendering/display_input.py` is **defined but NEVER CALLED**.
  - The function was added as part of a previous "final fix" commit but was never wired into `handle_mousePressEvent`.
  - **This is the root cause**: After ANY widget click in MC mode, focus is never restored to `DisplayWidget`. Media keys are delivered to the child widget that received the click, which does not handle them. `SetForegroundWindow` bypasses this by resetting top-level window focus.
  - Revised model: Not "child widget focus theft" (H1 was wrong), but "no focus restoration after click". The child widget legitimately receives focus on click; the bug is that `handle_mousePressEvent` never calls `_restore_mc_input_focus()` to return focus to `DisplayWidget`.
  - **Next step**: Wire `_restore_mc_input_focus()` into `handle_mousePressEvent` after widget click routing (MC mode, non-exit clicks).
- **2026-04-25 FIX APPLIED — `_restore_mc_input_focus` WIRED and HALO SIDE-EFFECT RESOLVED**:
  - `_restore_mc_input_focus()` wired into `handle_mousePressEvent` at 3 return points within `hard_exit`/`ctrl_mode` branches: after context menu click, after handled widget click, after unhandled interaction click.
  - **Result**: Media keys, hotkeys (`C`, `S`) now work after manual click into SRPSS MC on secondary display. MC bug is **resolved**.
  - **Side effect**: `widget.raise_()` in `_restore_mc_input_focus` pushed cursor halo behind `DisplayWidget`, making it invisible. Fixed by adding `hint.raise_()` at end of `_restore_mc_input_focus` to re-raise the halo after `DisplayWidget` activation. Halo is a `Qt.Tool` + `WindowDoesNotAcceptFocus` window, so `raise_()` only affects z-order, not keyboard focus.
  - **No taskbar/Alt-Tab behavior preserved**: `Qt.Tool` + `WS_EX_TOOLWINDOW` unchanged.
- Winlogon asymmetry (`S` works while media keys fail) is deferred until MC is understood or the MC root cause clearly requires Winlogon comparison.




## Section 3 — Archived / Legacy Investigation Context

<a id="A-01"></a>
### [A-01] MAJOR VISUAL BUG: Settings Dialog Flicker / Placeholder Regression — Historical Investigation Archived

- [ ] COMPLETELY FUCKED
- [X] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **User later confirmed this issue is resolved in live use (Mar 22 2026).**
- The investigation record is retained below because several failed approaches are still useful anti-patterns. The final working state is summarized in the resolved entry dated **2026-03-22**.

- **Problem statement:** On MC builds we only render the fullscreen DisplayWidget on Display 1 while Display 0 remains a normal Windows desktop (winlogon is *not* involved). When we summon Settings (which still launches on Display 0), `engine.stop(exit_app=False)` tears down the MC window on Display 1 *and* leaves Display 0 unprotected for ~3 s while the dialog constructs. Windows fills that gap with a security-style popup that shows a lock icon and rapidly flickers. This is **not** historical behavior; the regression appeared after the March 13 settings work. **Update:** running `main.py` in script mode (non-winlogon screensaver) exhibits the exact same flicker, proving the bug is tied solely to the settings dialog invocation/creation path and is independent of build flags or MC-only windowing.
- **MC-specific observations supplied by user:**
  - Flicker occurs on whichever display is about to host the settings dialog even if that display never had SRPSS content (e.g., MC pinned to Display 1, dialog on Display 0).
  - Switching MC window flags between `Qt.SplashScreen` and `Qt.Tool` does **not** change the outcome; the secure popup still flashes.
  - Adding the `SettingsShieldManager` overlay not only failed to help, it added a second flicker on top of the MC display, so shields are now fully disabled.
  - The issue never repros in screensaver mode (every monitor has a DisplayWidget) which re-confirms this is an MC-only regression tied to mixed content across monitors, not Winlogon.
- **Observed deltas vs ≤ March 12 builds:** identical teardown order except for shields, but settings used to appear almost instantly, suggesting presentation timing/foreground activation hid the blanking earlier. Currently: log timestamps show ~3 s between “Settings requested” and “Settings dialog created,” during which Windows repeatedly presents the placeholder on the target monitor. 
- User note: Settings always opened slowly and there was no shitty ass flickering when it did.
- **Investigation Hypothesis (user):** MC builds need either (a) the dialog to become visible <200 ms so Windows never paints the placeholder, or (b) a masking strategy that works on *non*-MC monitors without introducing new artifacts. Shields are ruled out; we must find a different architectural fix.

**Approach A – Delay display teardown until dialog is visible** — **FAILED**
- Rationale: Even if teardown is delayed, the dialog often opens on monitor 0 while the compositor/render stack sits on monitor 1 (especially in MC builds where only one display is covered). The moment we finally pause/destroy the compositor, the monitor hosting the dialog will flash Windows’ placeholder, so this approach cannot eliminate flicker without additional masking.

**Approach B – Keep DisplayWidgets composited with a static frame during pause** — **FAILED**
- Rationale: `engine.stop()` always clears and hides every `DisplayWidget` within ~60 ms of the hotkey. Even if we froze the compositor first, the mandatory teardown would still destroy the HWNDs and Windows would drop in its placeholder for the remaining ~3.2 s while `SettingsDialog` builds. Avoiding teardown entirely would violate engine lifecycle contracts (widgets expect cleanup/start) and reintroduce the multi-monitor focus issues that Approach A already failed to solve.

**Approach C – Replace OS placeholder with compositor-controlled blackout** — **FAILED**
- Rationale: Blackout overlays only exist on monitors that currently host DisplayWidgets. MC builds (and script-mode runs) routinely summon Settings on a monitor that **never** had our compositor window, so there is no HWND on that screen to paint the blackout. Windows still shows its placeholder the moment the dialog begins constructing, so this approach cannot solve the regression without an entirely different masking primitive.
- (Historical steps retained for reference)

**Approach D – Cut SettingsDialog construction time to <200 ms without hurting UX** — **FAILED**
- [x] **Target-tab-first creation (no ugly placeholders):**
  [x] **Per-tab styling/shadow application:**
  [x] **Cache heavy-but-static data with freshness checks:**
- **Summary:** Target-tab-first hydration, per-tab styling deferral, and caching are live, but dialog construction still takes ~3 s on MC builds (see latest `screensaver.log`). The flicker persists even when only one monitor hosts SRPSS content, so raw construction speed is insufficient to mask the OS placeholder. Fade-in fallback remains unimplemented and is no longer expected to solve the problem; Approach D is marked failed pending a new direction.

**Approach E – External research before redesign (NEW)**
- [ ] Research and corroborate ROOT CAUSES from **≥5 recent sources** (2024+) focused on Windows multi-monitor Qt apps that mix fullscreen + desktop content. Emphasize findings about secure-desktop placeholders, HWND teardown ordering, and alternative masking primitives. Summarize pros/cons and cite each source before proposing a new architecture.
Mitigation last resort, but unacceptable as early builds of this project did not have this bug.





<a id="A-02"></a>
### [A-02] 2026-02-24 — Spotify Visualizer "Crossover Persistence" (Blob muted after mode switch)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Starting the session in Blob mode behaved normally, but switching into Blob from any other mode (or re-applying Blob via Settings) left radius/glow muted for 5–8 s despite healthy energy readings (`stage_filtered ≈ (1.00,0.03–0.08,0.00)`, radius stuck ~0.27–0.32 while `overall` > 0.6).
- Cold starts (Settings exit) immediately restored reactivity, confirming stale state carried across crossovers rather than shader issues.

**Failed / insufficient attempts**
1. *Overlay-only reset (Jan 2026):* `SpotifyBarsGLOverlay` reset `_blob_stage_progress_*` when `_vis_mode` changed. Helped literal mode flips but not config replays, because the enum often stayed on `blob`.
2. *Widget-only zeroing (Feb 2026 rev 1):* `_reset_visualizer_state()` cleared `_display_bars/_target_bars` and bubble caches but never asked the overlay to reseed, so stale smoothing reappeared on the next GPU push.
3. *Blob smoothing reseed (Feb 2026 rev 2):* Added `_blob_seed_pending` + `_reset_mode_state('blob')` when `_vis_mode` flipped. Still failed whenever settings re-applied Blob without changing the enum.
4. *Overlay reset wiring (Feb 2026 rev 3):* Widget now called `overlay.request_mode_reset()` for `_reset_visualizer_state()` / `_clear_gl_overlay()`. Logs showed `[OVERLAY][RESET]`, yet stage2 remained pinned because the beat engine + widget bars immediately reintroduced stale smoothed data.

**Final fix**
- `_reset_engine_state()` now cancels pending compute tasks, calls `reset_smoothing_state()` / `reset_floor_state()`, replays smoothing config, seeds `_waiting_for_fresh_engine_frame`, and zeros widget bar/energy buffers.
- `_track_engine_generation()` records the post-reset generation so `_on_tick()` blocks GPU pushes (`_waiting_for_fresh_engine_frame`) until `engine.get_latest_generation_with_frame()` reaches the pending generation, guaranteeing Blob never reuses the old smoothing envelope.
- `SpotifyBarsGLOverlay` reseeds `smoothed_energy` on the first non-zero FFT, so stage2 can rise immediately once the engine publishes fresh data.

**Regression coverage & validation**
- Added `tests/test_spotify_visualizer_widget.py::test_blob_crossover_waits_for_fresh_engine_frame`, which stubs the beat engine + overlay bridge, forces a Spectrum→Blob crossover, and asserts GPU pushes remain blocked until the fake engine publishes a new generation with stage2 energy > 0.4.
- Manual log runs (Sine→Blob crossover and Blob cold start, Feb 24) show stage2 surpassing 0.4 within ~1 s after mode switch, with `[SPOTIFY_VIS] Engine delivered fresh frame` immediately clearing the wait gate.

**Takeaways**
- Always reset the shared beat engine, widget bar cache, and overlay state within the same tick when handling cross-mode transitions.
- Gate GPU pushes on fresh FFT generations whenever smoothing state is invalidated.
- Keep regression tests that cover the exact gating contract so future plumbing changes cannot reintroduce stale-state persistence.


<a id="A-03"></a>
### [A-03] 2026-03-22 — Settings Dialog Flicker / Placeholder Regression (Resolved) - USER NOTE: UNRESOLVED BUT LOW PRIORITY NOW. SEE DUPLICATION OF THIS ISSUE IN THIS VERY DOCUMENT.

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Opening Settings from the screensaver/MC flow could produce a bad Windows placeholder/flicker moment while the dialog came up.
- The regression was especially visible in mixed monitor setups and became tied to the settings invocation path rather than image rendering itself.

**Failed / insufficient attempts**
1. Shield overlays and masking experiments did not solve the root problem and could add their own flicker.
2. Pure teardown-order tweaks were not enough on their own because the settings path still had visible timing gaps.
3. Early placeholder-tab work and caching helped, but were not originally considered sufficient in isolation.

**Final working state**
- The screensaver/settings handoff now keeps the workflow on the safe path guarded by `tests/test_s_hotkey_workflow.py`: opening Settings hides display windows instead of leaving fullscreen content in a half-torn state over the dialog.
- `SettingsDialog` builds the initial tab immediately and hydrates remaining tabs asynchronously, reducing visible construction pressure during first paint.
- Flicker-regression coverage also lives in `tests/test_flicker_fix_integration.py`, including guards around immediate fullscreen presentation and avoiding `processEvents()`-style races in transition code.

**Validation / guardrail**
- User later confirmed the settings flicker is resolved in live use.
- Keep `tests/test_s_hotkey_workflow.py` and `tests/test_flicker_fix_integration.py` as the minimum regression bar before reworking settings launch flow again.

**Takeaways**
- Do not reintroduce shield-style masking as a first response.
- Keep the settings launch path explicit and test-guarded: hide displays cleanly, paint Settings quickly, and avoid event-loop race hacks.


<a id="A-04"></a>
### [A-04] 2026-03-22 — MC Keyboard Focus / Ctrl Halo Interaction Regressions (Historical Partial Fixes Archived; superseded by [U-05](#U-05))

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

**Archive scope note**
- This entry records March 2026 partial improvements only.
- Current runtime truth is tracked in [U-05](#U-05); do not treat this section alone as current behavior status.

**Symptoms**
- MC hotkeys and media keys could stop working after interaction clicks.
- Ctrl-held suppression could drift across local/global/handler state.
- Cursor Halo behavior regressed around compositor interaction: it could fail to return after slight coordinate drift, and hard-exit interaction clicks could make it vanish immediately.

**Failed / insufficient attempts**
1. Relying on only one Ctrl-held source was too fragile; focus/ownership drift could leave different subsystems disagreeing about whether interaction mode was active.
2. Halo behavior tied too closely to raw move events was vulnerable to compositor coordinate drift and click-driven focus churn.
3. A later "simplify it" experiment that made the top-level Halo window `WA_TransparentForMouseEvents` was a regression: clicks could escape the compositor/widget tree instead of being forwarded through the real display interaction path, which in turn worsened click swallowing and shadow-side fallout. Do not reintroduce that top-level transparent Halo path as a casual cleanup.

**Final fix**
- `display_input._ctrl_interaction_active()` now resolves Ctrl-held state across local widget state, coordinator state, deprecated global state, and handler state.
- `InputHandler.handle_ctrl_press()` explicitly marks handler-held state, so downstream guards agree even after interaction/focus churn.
- MC interaction clicks now perform a best-effort focus reclaim via `display_input._restore_mc_input_focus()`, which keeps keyboard/media support alive after clicking overlays.
- `display_input.show_ctrl_cursor_hint()` clamps small compositor drift back inside the display instead of treating it as a real out-of-bounds exit.
- `display_input.handle_mousePressEvent()` now refreshes halo visibility/activity after interactive clicks in hard-exit mode, so clicking compositor elements no longer makes the halo disappear immediately.
- `CursorHaloWidget._forward_mouse_event()` now routes button events back through the fullscreen display root so the existing interaction router, preset cycling, focus reclaim, and halo keepalive logic all run on forwarded clicks.
- Later Mar 22 follow-up: the blanket click-triggered halo keepalive / focus-reclaim calls in `display_input.handle_mousePressEvent()` were backed back out. They were well-intended, but in live use they worsened Halo visibility and click behavior instead of restoring last-commit behavior. The valuable retained parts are the multi-source Ctrl gate, display-root forwarding, and drift clamp.

**Regression coverage & validation**
- `tests/test_mc_keyboard_input.py` guards the focus reclaim path and hotkey behavior.
- `tests/test_dimming_and_interaction_fixes.py` now guards the multi-source Ctrl gate, halo drift clamp, removal of the bad generic click-keepalive path, and display-root halo forwarding contract.
- User confirmed that keys are now working again in script mode.
- Follow-up note (later Mar 22 user validation): keyboard/focus improvements held, but Cursor Halo click passthrough/hide behavior was still not fully correct. Keep treating Halo click behavior as an active issue even though the underlying keyboard-focus repair remains valuable and should not be reverted casually.

**Takeaways**
- Interaction reliability depends on focus reclaim and state agreement together; fixing only one side is not enough.
- Halo lifetime should be treated as its own interaction contract, not just a side effect of mouse-move traffic.
- Halo passthrough must preserve the real display interaction pipeline; bypassing the display root silently breaks preset cycling / keepalive behavior even when focus handling looks correct.
- Top-level transparent Halo windows are not equivalent to real compositor passthrough in this project; preserving forwarded ownership is safer than assuming Qt click-through will land on the right target.
- When a bug family only partly resolves, keep the resolved sub-contracts documented separately so later work does not accidentally unwind them while chasing the remaining visual issue.


<a id="A-05"></a>
### [A-05] 2026-03-22 — Blob Ghost/Pulse Investigation (Resolved Subsystems Archived)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Blob spent a long period oscillating between several failure classes:
  - ghost shape mismatch
  - ghost flicker
  - live core briefly hitting the "correct" shape and then snapping back
  - settings that appeared to do nothing, especially when trying to disable kick assist or cap reactive lift
- The user repeatedly reported that Blob could look musically expressive for a moment and then throw jarring oversized pulses unrelated to the actual track.

**Failed / retired approaches**
1. *Delayed-history / state-blend ghost replay:* created obvious "second blob" behavior and visible flicker.
2. *Ghost-only peak time / stage snapshotting:* preserved the wrong motion model and still produced wrong-shape behavior.
3. *Trying to solve the remaining pulse problem as ghost math:* misleading. Once parity returned, the real issue was in the live-core reaction path.

**Root causes that were actually fixed**
- **Divergent live vs ghost source paths:** Blob ghost memory and live uniforms were not always starting from the same processed support signal. That made the ghost look like a different interpretation of the audio.
- **Wrong event-energy ownership:** discrete kick/snare help could leak back into the same `bass/overall` channels driving whole-body scale, creating giant pulses instead of smooth staged growth.
- **Zero-valued controls silently ignored:** parts of Blob’s live-band path still used `... or default` reads, so valid `0` values for settings like `blob_kick_lane_gain`, `blob_pulse_cap`, and transient mixes were replaced by defaults. This made "off" or "minimum" settings feel fake.

**Final working state / guardrails**
- Ghost and live Blob now share the same processed live-band source before ghost hold/decay, restoring silhouette parity.
- Scheduler help is now intentionally asymmetric:
  - continuous `bass/overall` remain the main whole-body support
  - kick assist primarily feeds staged growth inputs
  - snare assist primarily feeds live `mid/high` wobble/stretch behavior
- `blob_pulse_cap` and `blob_pulse_release_ms` were added so reactive lift can be capped and released more gracefully without slowing attack.
- `blob_kick_lane_gain` now genuinely applies to Blob as a real user control; `0%` disables scheduler kick assist for Blob while leaving continuous support and snare-driven deformation available.
- Most importantly: Blob control reads in the live-band path must preserve valid zeroes. Do not reintroduce `... or default` when reading zero-allowed Blob controls.

**Regression coverage & validation**
- `tests/test_ghost_isolation.py` now guards Blob scheduler boost routing, kick-lane disable behavior, and the retired ghost-path contracts.
- `tests/test_visualizer_reactivity_quality.py` covers bounded Blob boost behavior on calm passages.
- User later confirmed that ghost/main-blob shape parity became correct again after this work, even though some preset/live-feel tuning remained an artistic validation task.

**Takeaways**
- Blob problems that "look like ghosting" may actually be live-core ownership bugs.
- Do not spend discrete scheduler events in the same channels that drive whole-body scalar pulse unless that is an intentional design choice.
- When a slider supports `0`, never read it through truthy fallback logic.
- Record retired experimental branches explicitly; otherwise Blob work tends to bounce back to the same two failed ideas.



## Section 4 — Resolved Archive (Historical)

<a id="R-07"></a>
### [R-07] 2026-03-28 — Startup Fade / Visualizer Secondary-Stage Ownership Split (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Primary overlays could sit behind a compositor-only dead gap and then appear too abruptly instead of following a coordinated fade wave.
- The Spotify visualizer could enter later than before but still in a bad state: jittery first frames, fallback-timer reveal, and occasional startup-side audio restart noise.
- Cold start, mode-cycle recovery, and settings-return recovery could behave differently, which pointed to orchestration drift rather than one isolated renderer bug.

**Root Cause**
- `WidgetManager` / `FadeCoordinator` were the real owners of primary fade state, but Spotify secondary-stage timing still depended on display-local fade/runtime fields.
- That split let coordinator logs look healthy while the live visualizer still followed a different runtime schedule.
- Shared fade behavior also had helper-level leaks: some widgets waited for the first animation tick to become visible, and several callers carried timing literals that were not actually authoritative.

**Fixes**
- Moved Spotify secondary-stage scheduling back under manager-owned control, with display-local fields treated as mirrored readable state rather than a second source of truth.
- Removed the old primary startup dead-gap and fixed the shared fade helper so widgets can become visible immediately at opacity `0.0`.
- Centralized startup contracts into:
  - `rendering/overlay_startup_policy.py` for display-side startup timing
  - `widgets/spotify_visualizer/startup_contract.py` for visualizer staged-startup state
- Delayed visualizer hot-start/reveal behind the centralized Spotify secondary stage, seeded from anchor/media state, and prewarmed shader/overlay work while hidden.
- Blocked the delayed-play startup branch from revealing via fallback before real playback becomes live.
- Restored proper duration-override forwarding so shared fade timing is real policy, not decorative literals.

**Validation**
- Latest user-validated runs covered all three comparison paths:
  - cold start with music already playing
  - full mode cycle back to Spectrum
  - settings open/close and return
- In those runs:
  - primary fade begins at compositor-ready
  - the visualizer reveals through `fresh_frame_ready_delay`, not `fallback_timer`
  - `Audio capture unhealthy, restarting...` no longer appears during startup
  - startup behavior now matches the healthier recovery paths closely enough to close the bug

**Takeaways**
- Keep shared fade ownership centralized. Do not reintroduce display-local scheduling logic that can diverge from manager/coordinator state.
- Prefer narrow mirrored runtime-readable state over duplicate decision-making state.
- If startup needs more polish later, tune it from the shared fade/startup contracts instead of adding visualizer-specific timing hacks.
- Occasional future fade-softness polish is a separate UX tuning topic, not a reason to reopen this resolved startup bug unless the old parity failure returns.



<a id="R-08"></a>
### [R-08] 2026-02-26 / 2026-03-05 — Pixel Shift Visualizer Bleed-Through (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Visualizer bar content briefly flashed inside the weather widget every pixel shift tick.
- Earlier investigation (Feb 26) found no code delta in the pixel shift subsystem itself; the bug was architectural.

**Failed / insufficient attempts**
1. *Feb 26 audit:* Diffed `base_overlay_widget.py`, `pixel_shift_manager.py`, `display_setup.py` — found no functional changes. Concluded issue was outside the subsystem.
2. *Mar 5 — skip `parent.update()` for small moves (≤3px):* Reduced generic overlay flicker during pixel shift, but did NOT fix the visualizer-specific bleed. The GL overlay content still appeared over the weather widget.

**Root Cause**
Double-shifting of `SpotifyVisualizerWidget` (card) and `SpotifyBarsGLOverlay` (GL surface).

Both were registered with `PixelShiftManager` (PSM), but they are **dependent widgets** that already inherit pixel shift through the media widget chain:
1. PSM shifts `MediaWidget` via `apply_pixel_shift()` → `_update_position()` → `media_layout` → `_position_spotify_visualizer()` → vis card repositioned relative to shifted media 
2. PSM **also** direct-moved the vis card by `offset` on top → **double-shift** 
3. Every tick, `set_state(rect=vis.geometry())` set the GL overlay to the card's double-shifted position
4. PSM **also** direct-moved the GL overlay → **triple offset** possible 
5. The GL overlay drifted past the card boundary and overlapped the weather widget

**Fix**
- `display_setup.py`: Removed `spotify_visualizer_widget` from the PSM registration loop. The card is positioned relative to the media widget (same pattern as the volume widget, which was already excluded).
- `display_image_ops.py`: Removed `pixel_shift_manager.register_widget(overlay)` for the GL overlay. The overlay tracks the card's geometry via `set_state(rect=vis.geometry())` every tick.
- `widget_manager.py`: Removed stale `update_original_position()` call for the vis widget.
- `base_overlay_widget.py`: Added secondary defence — skip `parent.update(old_geo.united(new_geo))` when move delta ≤3px per axis and no size change (reduces unnecessary repaints).

**Status**
- **Resolved** — User confirmed pixel shift no longer causes visualizer bleed into weather widget.

**Takeaways**
- Widgets positioned relative to a pixel-shifted parent must NOT be independently registered with PSM — they inherit the shift through the positioning chain.
- `QOpenGLWidget` overlays that track their source widget's geometry every tick are especially vulnerable to double-shift because the per-tick `setGeometry()` resets any PSM offset, creating visible jitter.
- The volume widget was already excluded from PSM for the same reason (comment in `display_setup.py`). The vis card and GL overlay should have followed the same pattern from the start.


<a id="R-09"></a>
### [R-09] 2026-03-05 — Settings Spinbox/LineEdit Fill Regression (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Every `QSpinBox` and `QLineEdit` inside the settings dialog rendered with the container gray instead of the intended `#282828` fill.
- `SPINBOX_STYLE` QSS was attached to `WidgetsTab`, yet the widgets never showed the correct background.

**Root Cause**
CSS specificity conflict. Every tab's `QScrollArea` had this inline rule (also centralized in `SCROLL_AREA_STYLE`):
```css
QScrollArea QWidget { background: transparent; }
```
This descendant selector has **specificity 002** (two type selectors), which beats the `SPINBOX_STYLE` rules like `QSpinBox { background-color: #282828; }` at **specificity 001**. Because `QSpinBox` IS-A `QWidget`, the transparent background was always winning. The same rule also existed in `dark.qss` line 380 for `#subsettingsDialog`.

**Failed attempts (all reverted)**
1. Global stylesheet append in `settings_theme.load_theme` — no effect (specificity still lost).
2. Palette forcing in `apply_shadows_to_inputs` — bypassed by QSS.
3. Stack stylesheet sync + STYLE_PROBE hooks — confirmed styles existed but didn't help.
4. Dialog-level palette override — palette changed but QSS still won.

**Fix**
- Removed `QScrollArea QWidget { background: transparent; }` from `SCROLL_AREA_STYLE` in `shared_styles.py`.
- Replaced all inline scroll area stylesheets in `widgets_tab.py`, `transitions_tab.py`, `sources_tab.py`, `display_tab.py` with centralized `SCROLL_AREA_STYLE` import.
- `accessibility_tab.py` already used the import — no change needed.
- Fixed `dark.qss` `#subsettingsDialog QScrollArea QWidget` → `#subsettingsDialog QScrollArea > QWidget > QWidget`.
- The remaining rules (`QScrollArea { ... }` and `QScrollArea > QWidget > QWidget { ... }`) use direct-child combinators, so they only target the viewport and content widget — not all descendants.

**Cleanup**
- Removed all STYLE_PROBE diagnostic code from `settings_dialog.py` (`_log_stylesheet`, `_install_stylesheet_hooks`, `_log_tab_styles`, `_sync_stack_stylesheet`, `_log_palette_snapshot`, `_style_probe_enabled`).
- Removed `_SpinboxProbeFilter`, `_style_probe_enabled()`, `_format_color_hex()`, `_log_input_styles()`, `_install_spinbox_probes()` from `widgets_tab.py`.
- Removed unused `os`, `QPalette` imports from `settings_dialog.py`.

**Status**
- ✅ **Resolved** — Visually confirmed `#282828` fill on all spinboxes, entry boxes, and line edits.


<a id="R-10"></a>
### [R-10] 2026-03-06 — Widget C++ Object Already Deleted on Provider Switch (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- `RuntimeError: Internal C++ object (SpotifyVisualizerWidget) already deleted` when switching Spotify provider in settings GUI and returning to the application.
- Same error for `MuteButtonWidget` and `SpotifyVolumeWidget`.
- Error occurred in `widget_manager.py` `_register_spotify_secondary_fade` closures fired by `QTimer.singleShot`.

**Root Cause**
When the user switches media providers in settings, the engine destroys the old Spotify widgets (visualizer, mute button, volume). However, `QTimer.singleShot` lambdas in `_register_spotify_secondary_fade` still held Python references to the destroyed widgets. When the timers fired, accessing any Qt method (`objectName()`, `isVisible()`, etc.) on the stale Python wrapper raised `RuntimeError` because the underlying C++ object was already deleted by Qt.

**Fix**
- Added a validity guard at the top of both `_starter()` and `_run_sync()` closures in `widget_manager.py`:
```python
try:
    widget.objectName()
except RuntimeError:
    return
```
- This pattern is consistent with existing exception handling in the file (no `shiboken6` import needed).

**Status**
- ✅ **Resolved** — No RuntimeError on provider switch in settings.

**Takeaways**
- Any `QTimer.singleShot` lambda that captures a widget reference must guard against the widget being destroyed before the timer fires.
- Use `try/except RuntimeError` around a lightweight Qt accessor (`objectName()`) as the validity check.
- This is distinct from the `Shiboken.isValid()` pattern used for background-thread callbacks — deferred main-thread timers need the same protection.


<a id="R-11"></a>
### [R-11] 2026-03-14 — Visualizer Preset Tooling Regression (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- Running `visualizer_preset_repair.py` on new Spectrum presets (e.g., `preset_2_cake.json`) shrank the JSON but silently reset `spectrum_shape_nodes` and all shaping sliders back to defaults. The GUI then loaded "Preset 2" with the default curve, ignoring the user-authored shape entirely.
- Switching from any curated preset back to Custom instantly overwrote the Custom slot (even without hitting Save). Toggling presets was enough to nuke hand-tuned slider values because the parser reapplied the curated dict into the Custom slot while the UI reloaded.

**Root Causes**
1. `_collect_visualizer_sections` appended `snapshot.custom_preset_backup` *after* the `snapshot.widgets.spotify_visualizer` block. Because the parser merges sections in order, the backup dict (which still held default values) overwrote the curated entries the moment the preset was reapplied.
2. The repair tool only inferred `preset_index`, leaving `name` blank whenever the snapshot lacked metadata. The UI therefore showed the placeholder "Preset 2" even for curated files like `preset_2_cake`. Combined with #1, it looked as if presets were not sticking.

**Fixes**
- Parser now feeds `custom_preset_backup` first and then the main `widgets.spotify_visualizer` block, so curated settings remain authoritative and the Custom slot stops being overwritten when presets reload. @core/settings/visualizer_presets.py#223-247
- `tools/visualizer_preset_repair.py` now derives friendly names from the filename when missing metadata (e.g., `preset_2_cake.json` → "Preset 2 (Cake)"). We also re-ran the tool to confirm Spectrum retains custom shape nodes and that backups are emitted (`.bak1`).

**Status**
- ✅ Resolved — Spectrum `preset_2_cake.json` retains custom shaping data and displays the friendly name. Switching between presets and Custom no longer wipes the Custom slot. Cross-mode audit pending to ensure every curated file behaves the same way.

**Takeaways**
- Always merge snapshot backup sections *before* the primary widget payload so curated presets remain authoritative.
- Repair-tool outputs must include human-friendly names; otherwise it’s impossible to tell curated presets apart in the UI.


<a id="R-12"></a>
### [R-12] 2026-04-09 — Runtime Custom Slot Replaced While Cycling Presets (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

**Symptoms**
- In live runtime, cycling away from `Custom` and eventually back to `Custom` could replace the user's hand-tuned settings with a different preset payload instead of restoring the real Custom state.
- In the reported Spectrum case, the replaced payload appeared to match the most recently viewed curated preset before returning to `Custom`.
- The overwrite did not require `Move To Custom`; simple runtime preset stepping was enough to corrupt what `Custom` represented for that mode.

**Root Cause**
1. The settings-dialog path already had a `leave Custom -> snapshot live payload -> return to Custom -> restore cached payload` rule.
2. The runtime path (`WidgetManager.cycle_visualizer_preset`) did not honor that same rule. It advanced preset indices and applied curated payloads, but it did not snapshot the outgoing `Custom` payload or restore the cached one on re-entry.
3. Because runtime cycling is settings-backed and non-UI, the active `spotify_visualizer` config could end up carrying the last curated payload when the preset index wrapped back to `Custom`.

**Fixes**
- Shared Custom snapshot helpers now live in `core/settings/visualizer_presets.py` so the contract is not duplicated differently in separate callers.
- `ui/tabs/widgets_tab.py` and `rendering/widget_manager.py` now both use that shared snapshot/restore path, which keeps the settings UI and runtime manager aligned.
- Runtime regression coverage was added in `tests/test_visualizer_preset_cycling_runtime.py` for the exact `Custom -> curated -> Custom` round-trip through `WidgetManager`.

**Status**
- Resolved in code and covered by focused runtime regression tests.
- Keep an eye on live reports across all modes, because the symptom had been remembered as intermittent and cross-mode rather than Spectrum-only.

**Takeaways**
- `Custom` is not just another preset index; it is a live user-owned snapshot that must be preserved consistently across UI and runtime code paths.
- If the same workflow exists in settings UI and runtime interaction, both paths need to share the same helper/contract instead of re-implementing it separately.


<a id="R-13"></a>
### [R-13] 2026-04-13 — Visualizer Sine/Oscilloscope Lines 4-6 Settings Never Persisted (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

Cross-mode settings loss had been ongoing since lines 4-6 were added. User-visible symptoms: editing Line 4 color/glow/shift → entering runtime → returning to settings → all Line 4-6 changes reverted to defaults. Affected both Sine and Oscilloscope modes identically.

**What finally worked:** Two layered bugs needed to be fixed together.

**BUG #6 — Cross-mode save wipe (fixed 2026-07-25):**
`_save_settings_now()` in `ui/tabs/widgets_tab.py` replaced the entire `widgets.spotify_visualizer` dict with freshly-collected data that only contained shared + active-mode keys. Every save wiped all inactive-mode settings. Fixed to read existing config first, merge fresh current-mode data via `.update()`, then normalize the merged result.
- **File:** `ui/tabs/widgets_tab.py`

**BUG #7 — Model serialization gap for lines 4-6 (fixed 2026-04-13, the true root cause):**
`SpotifyVisualizerSettings.from_mapping()`, `from_settings()`, and `to_dict()` in `core/settings/models.py` all read/wrote line 1-3 settings but completely omitted lines 4-6 for both Sine and Oscilloscope. The normalization pass (`normalize_visualizer_section_mapping`) round-trips through these methods, so it silently dropped all line 4-6 keys even when `collect_sine_wave_mode_settings()` correctly collected them from the UI.

Pipeline trace:
1. User edits Line 4 color → `collect_sine_wave_mode_settings()` reads it correctly ✓
2. `_save_settings_now()` merges it into existing config correctly ✓ (after BUG #6 fix)
3. `normalize_visualizer_section_mapping()` round-trips through model → line 4-6 keys silently dropped ✗
4. Normalized result written to JSON without line 4-6 → settings lost

**Secondary fix — Wiring alignment (2026-07-25):**
All 10 sine multi-line color button lambdas in `ui/tabs/media/sine_wave_builder.py` were converted from direct `color_changed.connect(lambda ...)` to `bind_color_button()` for consistency with line 1. This was not the root cause but is the canonical wiring pattern.

**Keys added to all three model methods:**
- Sine: `sine_line4/5/6_color`, `sine_line4/5/6_glow_color`, `sine_travel_line4/5/6`, `sine_line4/5/6_shift`, `sine_ghost_line4/5/6_enabled`
- Osc: `osc_line4/5/6_color`, `osc_line4/5/6_glow_color`, `osc_ghost_line4/5/6_enabled`

**Key failed methods (BUGs #1-#5 in Current_Plan.md Historical Reference):**
- BUG #1: `apply_preset_to_config()` merge overlay → correct partial fix but not root cause
- BUG #2: `save_media_settings()` collected all modes → correct fix but not root cause
- BUG #3: `.update()` left stale keys → correct fix but not root cause
- BUG #4: Technical keys lost when switching presets → correct fix but not root cause
- BUG #5: Technical keys from ALL modes leaked → correct fix but not root cause

**BUG #8 — Runtime config bridge missing lines 4-6 kwargs (fixed 2026-04-13):**
`apply_spotify_vis_model_config()` in `rendering/spotify_widget_creators.py` built the kwargs dict that feeds the runtime visualizer widget via `apply_vis_mode_config()`. It explicitly listed lines 2-3 but completely omitted lines 4-6 for both sine and osc (colors, glow colors, travel, shifts, ghost enabled). Also missing: `sine_smoothing`, `sine_glow_reactivity`, `osc_glow_reactivity`. The fallback path in `rendering/widget_manager.py` had the same gap.

This is why the GUI retained correct values (save path worked after BUGs #6+#7) but runtime showed defaults — the model→widget bridge simply never forwarded them.

**BUG #9 — Shift updaters wrote wrong attribute name + shift rows always visible (fixed 2026-04-13):**
Lines 4-6 shift `bind_setting_signal` updaters in `ui/tabs/media/sine_wave_builder.py` wrote to `_sine_lineN_horizontal_shift` instead of `_sine_lineN_shift`. Harmless for saving (collect reads slider `.value()` directly) but incorrect. All shift rows (lines 2-6) used `_aligned_row()` (untracked) instead of `_aligned_row_widget()`, so the visibility function couldn't hide them — they always displayed regardless of line count.

**BUG #10 — Overlay set_state silently dropped lines 4-6 shift and travel (fixed 2026-04-13):**
`SpotifyBarsGLOverlay.set_state()` accepted `sine_line4/5/6_shift` and `sine_travel_line4/5/6` as named parameters but the method body never assigned them to `self._sine_line4_shift` etc. The overlay attributes stayed at their `__init__` defaults (0.0 / 0) even when the entire upstream pipeline (model → widget → config_applier → tick_pipeline → extras → overlay) was passing correct values. The shader's `upload_uniforms` reads from `self._sine_line4_shift`, so lines 4-6 always rendered at shift=0 and travel=0.
- **File:** `widgets/spotify_bars_gl_overlay.py`

**Why prior fixes failed:** They addressed real secondary issues in the save/load pipeline, but none addressed the full 5-layer chain: (a) save path replacing instead of merging, (b) settings model discarding lines 4-6 during normalization, (c) the runtime config bridge never forwarding lines 4-6 to the widget, (d) the UI builder using wrong attribute names and untracked rows, and (e) the overlay `set_state` accepting parameters but never storing them.

**Takeaways:**
- When adding new per-line settings, all three serialization methods (`from_settings`, `from_mapping`, `to_dict`) must be updated in the same commit. The dataclass fields + `__post_init__` defaults are necessary but not sufficient.
- The runtime config bridge (`apply_spotify_vis_model_config`) must also be updated — it is a separate explicit kwargs list that does not auto-discover model fields.
- `SpotifyBarsGLOverlay.set_state()` accepts parameters explicitly and assigns them to `self` manually — adding a parameter to the signature does **not** mean it is stored. Every new parameter needs a corresponding `self._xxx = ...` line in the method body.
- Normalization passes that round-trip through a model will silently drop any field the model doesn't know how to serialize — this failure mode produces no errors or warnings.
- When debugging settings persistence, always test the normalization round-trip directly: feed test data into `normalize_visualizer_section_mapping` and verify the output contains all expected keys.
- UI row widgets that should conditionally hide must use `_aligned_row_widget()` (tracked) instead of `_aligned_row()` (fire-and-forget).

**Closure update (2026-04-16):**
- The issue was pruned from `current_plan.md` after user-reported runtime confirmation that the settings round-trip now appears solved in practice, not just in code/tests.
- Keep this entry because the bug was unusually sneaky: the user-facing symptom looked like one cross-mode persistence failure, but the real failure chain spanned save merge semantics, model normalization, runtime config bridging, UI builder wiring, and overlay state storage.
- Future regressions that look like "custom settings randomly reverted" should be checked against this entire chain before assuming a single save-path bug.


<a id="R-14"></a>
### [R-14] 2026-04-17 — Blob Inward-Liquid Runtime Handoff Broke GL Overlay Push (Resolved In Code, Visual Validation Pending)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

**Symptoms**
- Blob could appear to fall back or fail to react correctly right after the inward-liquid settings landed.
- Runtime logs showed repeated overlay push failures during normal visualizer updates instead of a clean Blob frame handoff.
- The noisy symptom was easy to misread as a mode/render fallback, but the logs pointed at a state-transport exception instead.

**What the logs actually showed**
- `SpotifyBarsGLOverlay.set_state()` raised:
  - `unexpected keyword argument 'blob_inward_liquid_color'`
  - then on the retry path `unexpected keyword argument 'blob_inward_liquid_enabled'`
- This happened inside the runtime overlay push path in `rendering/display_image_ops.py`, so the new Blob extras were reaching the handoff boundary but the overlay contract was out of sync.

**Root Cause**
1. The inward-liquid settings had already been added to settings/defaults/model/config/widget/GPU-extra plumbing.
2. `build_gpu_push_extra_kwargs()` correctly included the new `blob_inward_liquid_*` payload.
3. `SpotifyBarsGLOverlay.set_state()` had not been updated to accept/store those kwargs, so the overlay push failed at runtime.
4. The Blob shader already declared the inward-liquid uniforms, but the GL overlay uniform-location table and Blob uniform uploader also needed to be taught about the new fields to complete the handoff intentionally.

**Fixes**
- Updated `SpotifyBarsGLOverlay.set_state()` to accept and store:
  - `blob_inward_liquid_color`
  - `blob_inward_liquid_enabled`
  - `blob_inward_liquid_reactivity`
  - `blob_inward_liquid_max_size`
- Added the matching inward-liquid uniform names to the overlay GL lookup table in `widgets/spotify_bars_gl_overlay.py`.
- Added Blob renderer uniform upload support in `widgets/spotify_visualizer/renderers/blob.py` so the shader receives the new values deliberately rather than by accident or omission.
- Added a focused regression in `tests/test_visualizer_overlay_kwargs.py` so future Blob GPU extras and Blob uniform declarations stay aligned with the overlay/frame-push contract.
- While validating this, two stale tests were corrected to reflect the current Blob/Bubble guardrail: their continuous body signal intentionally stays on the cooler standard energy snapshot, not the hotter pre-AGC snapshot.

**Status**
- Fixed in code and covered by focused regressions.
- Live visual confirmation is still required because the issue was a runtime/visual handoff seam, not just a serialization seam.

**Takeaways**
- A new visualizer field is not "done" when it exists in settings and widget state; it must also survive the explicit overlay/frame-push boundary.
- `SpotifyBarsGLOverlay.set_state()` is a manual contract. New runtime kwargs must be added to both the signature and the body.
- Shader support alone is insufficient; the GL uniform lookup table and mode-specific uploader must also know about the new fields.
- When logs suggest a visualizer "fell back", verify whether the real failure is a shared transport exception before diagnosing the renderer itself.


<a id="R-15"></a>
### [R-15] 2026-04-18 — Frozen Curated Presets Silently Fell Back to Onefile Tree (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Symptoms**
- Normal/frozen runtime could load curated visualizer presets from onefile extraction paths under `%LOCALAPPDATA%` instead of shared curated content.
- MC path behavior could appear correct while SCR path drifted to older bundled payloads, causing cross-build preset mismatch on the same machine.

- **Root cause**
- `core/settings/visualizer_presets.py::_presets_root()` allowed frozen-mode fallback to `_bundled_presets_root()` when shared-root bootstrap failed.
- Bootstrap failures were debug-logged and then masked by that fallback, so runtime stayed functional but silently selected the wrong preset source.

- **Fix**
- Frozen-mode root resolution is now strict-canonical:
  - always resolve to `%ProgramData%\SRPSS\presets\visualizer_modes`
  - attempt bootstrap from bundled shipped tree only as a copy source
  - never return bundled/onefile paths as active curated root
- Added regression tests to lock this behavior, including bootstrap-failure and missing-bundled scenarios.

- **Why this worked**
- It removed ambiguous runtime source selection entirely: frozen curated reads now have one authoritative root regardless of bootstrap outcome.
- This aligns SCR and MC with the same machine-wide curated preset contract.


<a id="R-16"></a>
### [R-16] 2026-04-18 — One-Dir Runtime Misdetected As Script + Curated Slot Drift (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Symptoms**
- Frozen Main build sometimes resolved visualizer preset save/edit defaults into extracted onefile paths.
- Preset slider labels could drift from the file opened by "Edit Preset" when curated JSON payloads carried mismatched `preset_index` values.

- **Root cause**
- `core/settings/visualizer_presets.py::_is_frozen_build()` used a narrower detection contract than `main.py`, so some one-dir runtimes were treated as script mode.
- Curated preset parsing trusted embedded `preset_index` before filename slot inference, so malformed payload indices could remap in-memory preset slots even when filenames were correct.

- **Fix**
- Unified frozen detection behavior with `main.py` semantics, including executable-name detection (`SRPSS*` / `.scr`) for runtimes where `sys.frozen` is absent.
- Added one-dir extraction-path guard: when bundled roots include a `onefile` segment, preset roots are treated as frozen-style and pinned to shared ProgramData roots.
- Hardened curated parsing to prefer filename-derived slot (`preset_N_*.json`) over payload index, while snapshot override parsing keeps payload-index behavior.
- Added regression tests for both detection paths and filename-slot precedence.


<a id="R-17"></a>
### [R-17] 2026-04-18 — Goo No-Gap/Artifact Regression Family (Resolved In Dev-Gated Path)

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Symptoms**
- Goo rendered as disconnected edge blobs or rigid circles instead of coordinated center+border liquid.
- White highlight layer showed block/noise artifacts.
- Liquid could escape visual card limits or visually clip inconsistently.
- Center and inward border systems could visually merge, violating the explicit "never touch" rule.

- **Root cause**
- Single-field Goo architecture could not model border-vs-center pressure balancing or hard-gap behavior.
- Shader used hash/floor noise specular gating and lacked strict rounded-card clipping across all compositing passes.
- Runtime transport only carried one source field, so center/edge semantics were not representable.

- **Fix**
- Replaced single Goo field with a dual-field solver (`edge_liquid`, `core_liquid`) and per-tick gap invariant enforcement.
- Added pressure-coupled retreat/compression controls and mode-local settings (`goo_gap_min`, `goo_edge_pressure`, `goo_core_pressure`).
- Upgraded renderer/upload contract to dual vec4 arrays (`u_goo_edge_sources`, `u_goo_core_sources`) plus gap/boundary uniforms.
- Rewrote Goo shader compositing with strict rounded-card clipping, overlap barrier, vector contour stack, and smooth ribbon-style speculars (no block-noise path).
- Added regression coverage for solver invariants and Goo shader compile/contract checks.

- **Guardrail**
- Any future Goo change must preserve these invariants before runtime ask:
  - edge/core liquids never merge
  - no out-of-card pixels
  - no hash/floor specular artifact path

- **Follow-up regression noted 2026-04-18 (still open for visual sign-off)**
- **Observed pattern:** even after dual-field landing, runtime could still render disconnected "oval islands" and a hollow/weak center instead of pooled mock-like sheets.
- **Contributing causes:**
  - field influence had an effective hard radius cutoff, so neighboring sources did not fuse into fluid structures
  - center-void trim was too aggressive and suppressed core liquid visibility
  - evenly distributed core seeding reinforced ring/donut artifacts
- **Corrective direction now applied:**
  - switched Goo field influence to long-tail blending in shader so sources can merge naturally
  - reduced center-void trim to contour shaping (not center suppression)
  - randomized core angular homes and increased core depth/radius envelope to avoid stable ring lock
- **Loop-avoidance reminder:** if Goo resembles isolated circles, do not tune "hotness" first; inspect field kernel tail, threshold range, and center-void suppression as the first triage path.

<a id="R-21"></a>
### [R-21] 2026-05-04 — Visualizer Painted-Card GL Content Escaping Card Boundary (Resolved)

- [ ] COMPLETELY FUCKED
- [ ] ACTIVE
- [ ] AWAITING VALIDATION
- [x] SOLVED

- **Symptom:** When painted-card shadows are enabled, GL-rendered visualizer content (all real modes: Spectrum, DevCurve, Sine, Blob, Bubble, Oscilloscope) visibly escapes the painted card boundary at the right, bottom, and rounded-corner edges. The bleed was ~1px on sides/corners and ~1.5px on right/bottom, with the top-right corner being the worst.

- **Surface-level root cause (2026-05-03):** The `SpotifyBarsGLOverlay` receives the full `vis.geometry()` rect. The painted card is inset by `card_shrink_right/bottom` (11px each), but the GL overlay renders into the full widget rect, extending past the visible card edge.

- **True root cause (2026-05-04):** The initial stencil mask matched the card *fill* rect (inset by 1 logical px via `.adjusted(1.0, 1.0, -1.0, -1.0)`). However, the card border is drawn with a centred pen stroke (`border_width = 3px` from `BaseOverlayWidget.get_global_border_width()`). The mask was therefore bleeding over the inner ~1.5px of the border stroke. The apparent "all sides" bleed was the stencil mask being exactly flush with the card path instead of inside it.

- **Failed approaches (DO NOT REATTEMPT):**
  1. **Rect shrink in `display_image_ops.py`** (2026-05-03/04): Adjusted `geom` with `geom.adjusted(0, 0, -shrink_r, -shrink_b)` before passing to the GL overlay. **Why it failed:** This shrinks the visualizer *content* instead of *clipping* it. The content is rendered at a smaller size, which changes authored mode behavior (amplitude, curve scale, bar widths). It also only covered the prewarm path, not the per-tick `push_spotify_visualizer_frame` path. **Reverted 2026-05-04.**
  2. **QPainter clip path in `SpotifyVisualizerWidget.paintEvent`** (2026-05-03): Added a `QPainterPath` rounded-rect clip before CPU bar painting. **Why it failed:** Only affects `QPainter`-drawn content. GL overlay renders via `QOpenGLWidget.paintGL()` in a separate pipeline — the `QPainter` clip path has zero effect on GL output. The majority of real modes are GL-rendered. **Reverted 2026-05-04.**
  3. **QPainter in `resizeEvent`** (2026-05-03): Attempted to draw the shadow pixmap from `resizeEvent`. **Why it failed:** Painting outside `paintEvent` is invalid in Qt and produces `QPainter::paintEngine: Should no longer be called` errors. **Reverted 2026-05-03.**

- **Side effects of failed fixes:**
  - The combined shrink + clip changes caused the media control bar to shift lower when in bottom-right position. Traced to `MediaWidget._update_stylesheet()` not being painted-card-shadow-aware, causing double-painting of card background. This was a separate bug exposed during investigation but NOT caused by the shrink/clip code itself. Fixed separately.

- **Fix implemented (2026-05-04):**
  - Rounded-rect **stencil mask** in `SpotifyBarsGLOverlay.paintGL()` clips GL fragments to the visible card boundary (including rounded corners).
  - Two-pass approach per frame:
    1. Mask pass: color writes disabled, stencil writes 1 inside the card rounded rect via a dedicated SDF shader (`roundedRectSDF`).
    2. Visualizer pass: stencil test `GL_EQUAL 1` so only fragments inside the card shape are drawn.
  - Card bounds derived from `PAINTED_FRAME_SHADOW_TUNING` (`card_shrink_right`, `card_shrink_bottom`) plus corner radius `8 + radius_extra`.
  - **Critical correction:** The mask receives an additional inset of `border_width_px * 0.5 * dpr` so the visualizer stays inside the inner edge of the centred pen stroke, not flush with the card path. The radius uniform is reduced by the same amount.
  - `rendering/display_image_ops.py` now passes `border_width_px=vis._border_width` to `set_state` so the mask can compute the correct inset.
  - No content size, amplitude, curve scale, or authored mode behavior changes. Visualizer shaders untouched.
  - The QPainter fallback path (`_render_with_qpainter`) was removed as dead code.

- **Verification:**
  - `tests/test_stencil_mask_alignment.py` passes: zero bleed, correct corner rounding, zero-radius rectangle parity, and documented bleed when inset is omitted.
  - Runtime validation confirmed no visible bleed at card edges or corners across all modes.

- **Guardrails:**
  - Do not attempt rect-shrink or QPainter-clip approaches for this bug family again.
  - The mask inset must account for both the 1-px painted-frame shadow inset (`inset=1.0`) AND the centred card border width (`border_width/2`).

<a id="R-22"></a>
### [R-22] 2026-05-06 — Visualizer Runtime Mode/Preset Bleed Survived Audio Resets (Awaiting Validation)

- [ ] COMPLETELY FUCKED
- [x] ACTIVE
- [x] AWAITING VALIDATION
- [ ] SOLVED

- **Symptoms:** Runtime switches between visualizer modes or presets could leave the target mode visually corrupted even when the target settings were logged as applied. Two clear examples were Spline/DevCurve -> Spectrum becoming blown out and uniform, and Spectrum -> Spline/DevCurve becoming flat with weak reactivity. Opening settings and returning could make the same target mode look normal, which proved runtime hot activation was not equivalent to the settings refresh/restart path.

- **Failed narrow fixes:** Resetting the shared beat engine, audio worker AGC/floor state, audio buffers, waveform buffers, idle phase, and generation counters was necessary but not sufficient. Resetting/destroying the GL overlay and widget-owned accumulators was also necessary, but still not sufficient. Those fixes cleaned visible state containers, but they did not protect the mutable DSP state inside an already-running background FFT job.

- **Root causes found:** Runtime activation did not have a hard transaction boundary. A canceled compute callback was rejected after completion, but the background job itself still called bar computation on the live `SpotifyVisualizerAudioWorker`, mutating dynamic floor, AGC envelopes, transient bus/event state, bar history, and related DSP caches before the callback token check. That let previous-mode audio authority leak into the target mode even when the target settings had already been applied. A later log pass showed a second authority leak: during `DevCurve -> Spectrum`, `WidgetManager` logged target Spectrum config (`manual=0.140`) while the live floor logs still reported DevCurve config (`manual=0.610`, `expansion=5.989`). That proved reset/overlay cleanup and detached compute jobs were still insufficient unless the fade-complete and pre-reset paths force the target mode's full technical config onto the shared engine before fresh frames are accepted. The deeper settings-side contributor was ambiguous technical-key ownership: shared/global technical keys were still treated as live state in parts of save/load/logging while presets and runtime were already mode-owned. That made diagnostics misleading and allowed active-mode technical values to be rewritten back into shared keys instead of staying isolated to their mode/preset payload. Preset-varying runtime visuals turned out to have the same problem family: shared authored `bar_fill_color` / `bar_border_color` / `bar_border_opacity` keys survived inside curated payloads and could bleed one mode's render styling into another during hot switches. Another concrete settings-contract seam was gated-mode preset ownership: `blob` remained a stable runtime/settings mode id, but some normalization/model loops iterated only currently active descriptors, so `preset_blob` could be silently dropped when blob was dev-gated and the hot path fell back to curated preset 1 instead of the stored target preset/custom payload. A further concrete seam was the split runtime activation path itself: startup/create, refresh, and hot mode switches were not all consuming the same resolved mode/preset payload, and `sine_wave` technical sensitivity could be shadowed by the separate visual `sine_sensitivity` key when prefix resolution preferred loose aliases over the canonical `sine_wave_*` technical key.

- **Fix direction:** Treat runtime mode and preset activation as an atomic activation boundary without creating a new beat engine. Each activation increments an id, discards audio/result buffers, resets idle/waveform/smoothed/widget/overlay state, reapplies target technical config before and after the engine reset, and refuses reveal until the engine generation and activation id match. Background FFT jobs compute against a bounded detached audio-worker snapshot and commit floor/AGC/transient/bar state only after the callback verifies both the compute token and activation id. Stale audio frames tagged with an old activation id are dropped.

- **Guardrails:**
  - Runtime mode switch, context-menu switch, double-click cycle, and preset switch must be tested as activation paths, not only as settings-key updates.
  - Tests must poison and assert cleanup across audio worker DSP state, queued compute jobs, audio/result buffers, widget-owned visual accumulators, and GL overlay payload state.
  - Background FFT jobs must never mutate live DSP state unless their compute token and activation id are current at commit time.
  - Runtime transition tests must assert the live audio worker's target-mode technical values, not only widget-side logs or fake-engine reset counts.
  - Visualizer technical settings must remain canonicalized as per-mode keys. Shared/global technical keys are migration inputs only and should not survive normalized settings, custom snapshots, preset payloads, or runtime diagnostics.
  - Preset-varying runtime visuals must follow the same ownership rule. Shared/global authored bar colors, border opacity, or legacy ghost keys must be migrated once and removed from canonical preset/custom/live payloads.
  - Canonical per-mode technical keys must win over looser alias prefixes when a mode also has visual keys with overlapping names; `sine_wave_*` technical keys must not be shadowed by `sine_*` visual keys.
  - Settings/model normalization that preserves mode-owned preset data must iterate all stable mode ids, not only active descriptor gates. Dev-gated modes like `blob` still own persisted preset/custom state.
  - Do not solve this by creating per-mode beat engines. The shared engine identity must remain stable; only its state/config may be reset.
  - If settings round-trip fixes a visualizer state that runtime switching breaks, compare reconstruction-owned state first before tuning creative values.
