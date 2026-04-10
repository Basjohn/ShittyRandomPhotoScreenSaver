# Current Plan

Update this after every significant change.

## Guardrails (always active)

- Keep this aligned with [Index.md](Index.md), [Spec.md](Spec.md), [Docs/Defaults_Guide.md](Docs/Defaults_Guide.md), and [Docs/Visualizer_Debug.md](Docs/Visualizer_Debug.md).
- Do not mark runtime or visual-feel issues as fixed without user confirmation.
- Treat `presets/visualizer_modes` as the only authored visualizer preset source tree.
- Treat `release/main_mc.dist/presets/visualizer_modes*` as generated artifacts only.
- Do not introduce Curve again (for Spectrum).
- Do not change render methods or move Spectrum to a non-GL path.
- Do not treat passing tests as visual sign-off.
- Do not make global/shared math changes unless explicitly requested.
- Do not reduce FPS caps below current configured values.
- Whenever dead/dirty/messy/violating/architecturally poor code is discovered during unrelated work, note it here for later cleanup.
- Keep checkboxes honest:
  - `[x]` landed and validated
  - `[~]` partially proven / still needs runtime eyes
  - `[ ]` not done

---

## Snapshot

- **Date:** `2026-04-09`
- **Status:** Reddit Helper scheduled-task authority remains runtime-proven, Spectrum vocal-lane and Energy Arrow work are user-validated, the shared preset/repair flow is now on the modern lane-map contract, runtime preset cycling now honors the same Custom-slot snapshot/restore contract as the settings UI, and the settings shell now uses an accepted forged-corner outer-border compromise that is visually almost bleed-free without disturbing acrylic or the custom title bar. Spectrum consolidation remains partially open for deeper control-pruning decisions, and a broader visualizer isolation/bleed audit is now active so mode-specific tuning does not quietly degrade adjacent modes.
- **Preset pipeline:** Source tree -> repair tool -> shipped regeneration -> all green.

---

## Completed Work (Historical Summaries)

### H1. Baseline Stabilization (§0)
Preset source tree recovered after revert damage. `core/settings/defaults.py` now returns a normalized visualizer section; `SettingsManager._ensure_widgets_defaults()` canonicalizes fresh insertion. Fresh startup is repair-free. `--fresh` switch clears logs before `setup_logging()`. Commits: baseline recovery + `--fresh` switch.

### H2. Preset / Schema Guardrails (§1)
Documented hard-won lessons: authored source tree vs generated artifacts, AppData drift, baseline commit checklist. `tools/visualizer_preset_repair.py` stays flexible. Curated preset names not hardcoded in tests. Runtime cache is generated state.

### H3. Spectrum Width Reclaim (§2.1)
Reclaimed wasted horizontal side space for BARS and SEGMENTS without overshooting into borders. Regression coverage in `tests/test_spectrum_shaping.py`.

### H4. Replace Single Piece Mode (§2.2)
Removed `Single Piece Mode`, replaced with explicit `SEGMENTS` / `BAR` toggle buttons. `spectrum_render_mode` is canonical key. Runtime bridge translates to older widget boolean. `spectrum_unique_colors` remains the canonical unique-colour key.

### H5. Spectrum Buckets (§2.3)
Replaced loose section headings with real collapsible buckets. Normal: `Appearance`, `Shape`. Advanced: `Render`, `Audio`, `Ghost`. Commit: `ad63b29`.

### H6. Border Colour Participation (§3.1)
Audited why borders were excluded from rainbow. Added `spectrum_rainbow_border` (bool, default `False`) with UI checkbox `Rainbow Borders` in Render bucket. Wired through all 8 layers + shader uniform `u_rainbow_border` in both SINGLE PIECE and SEGMENTED paths. Tests: 92 passed in plumbing suite.

### H7. Reddit Helper Scheduled-Task Authority
Reddit handoff is now working in real runtime through a durable interactive scheduled task plus session-lived helper model. Final shape: saver queues URL and exits normally; helper launch authority comes from a reusable Task Scheduler task; helper waits for shell readiness, opens the URL, and self-exits. The winning registration path uses native Task Scheduler COM XML with `InteractiveToken`, with the XML owning the principal and the COM registration call passing empty user/password variants. Repo harness coverage now exists for register/query/run/delete of that authority layer.

### H8. Spectrum Energy Arrows / Lane Contract Cleanup
Spectrum now uses lane-native vertical energy arrows in the shaper as the real authored lane-power surface. The old scalar lane controls are retired from live settings/presets/runtime, the shaper persists label-driven mirrored/non-mirrored lane-strength maps, curated Spectrum presets were rewritten onto that contract, and the repair tool now does one-time scalar-to-lane promotion only when cleaning genuinely old authored payloads. User runtime validation confirmed the arrows are working better than expected.

---

## Active Tasks

### 1. Spectrum Consolidation Pass (was §3.3)

**Status:** `[~]` Partially landed / deeper cleanup still open
**Priority:** Medium

- [x] Clarify the highest-confusion Spectrum overlaps without changing the runtime math contract
- [x] Separate authored `Reactivity` / `Shape Floor` copy from Technical sensitivity/noise-floor copy
- [x] Replace misleading `Adaptive Sensitivity` wording with an explicit recommended fixed-sensitivity path
- [x] Add mode-aware audio block size guidance with lower/higher tradeoffs and a Spectrum recommendation
- [ ] Decide whether `Output Lift`, `AGC Strength`, and `Input Gain` can be reduced further without removing genuinely useful expert tuning
- [ ] Decide whether Spectrum should keep the recommended/manual sensitivity toggle at all or collapse fully to a single manual slider path
- [ ] Keep shimmer-at-mid-height as a defined tuning target rather than a vibe-based cleanup
- [ ] Defer shimmer assessment/fix until the rest of this plan has landed cleanly, but do not defer ordinary consolidation work that can proceed safely now
- [ ] When shimmer/flicker work starts, add a behavior-level reactivity regression test in the same spirit as the Blob stage-seeding test so the failure is reproducible without relying only on manual runs

What landed in this pass:
- Spectrum authored Audio copy now explicitly separates creative motion controls from Technical signal tuning
- `Profile Floor` is now presented as `Shape Floor` so it stops reading like the same thing as Technical noise floor
- Shared Technical UI now calls the checkbox `Use Recommended Sensitivity` because the underlying worker path is a fixed tuned multiplier, not live adaptive analysis
- Shared Technical audio-block tooltip now explains lower-vs-higher tradeoffs and shows a per-mode recommendation (`128` for Spectrum/Oscilloscope/Sine Wave, `256` for Blob/Bubble)

Why the task stays open:
- Spectrum still has a real expert-layer overlap question around `Output Lift`, `AGC Strength`, and `Input Gain`
- The shimmer work is still intentionally deferred and should not get bundled into these copy/ownership cleanups by accident

Captured tuning notes:
- Mid-height shimmer is not the same problem as quiet-floor jitter
- The target is steadier mid-height motion at 60 fps without flattening large high/low movements
- Compare behavior on `<=60 Hz` displays versus `165 Hz` displays and decide whether the eventual fix should improve one, both, or both differently
- `drop_speed` alone is too blunt; Spectrum needs room for large rises and large falls
- Guardrail: `Input Gain` is non-negotiable and must stay available during any consolidation/reduction pass

Runtime watch note:
- [~] Runtime preset cycling now shares the Custom-slot snapshot/restore contract with the settings UI. Keep watching for intermittent reports where cycling `Custom -> curated -> ... -> Custom` appears to inherit the previously viewed curated slot, especially in Spectrum and especially during live runtime rather than in the settings dialog.
- [~] Runtime preset cycling no longer blocks the hot path on an immediate settings JSON flush; keep watching for reports where specific preset edges still feel much slower than a full reset, especially if the hitch only appears once per cycle and then clears after a full pass.
- [~] Runtime preset cycling no longer spins up hidden bar-count-specific beat-engine/worker variants. The shared beat engine now rebuilds bar-count state through one startup/runtime-parity path instead of farming warmed alternate engines, but this still needs live validation against the once-per-cycle slow-switch symptom.

User guidance to preserve:
- Research whether optional interpolation, motion blur, or related display-side presentation techniques are standard for reducing shimmer on lower-refresh displays
- The problem is most noticeable on Spectrum because it is visually rigid, but some shimmer is still visible even at `165 Hz`
- A promising direction is per-lane hysteresis once a lane reaches a materially stable height, requiring more visual movement before it visibly shifts again
- Important guardrail: do not further smooth the underlying music/math signal; only improve the visual motion presented to the user
- Drops should be encouraged through a less flickery presentation method than simply increasing `drop_speed`
- Higher internal resolution appears to reduce shimmer but increases latency and does not eliminate the issue

### 1A. Visualizer Mode Isolation / Bleed Audit

**Status:** `[~]` In progress
**Priority:** High

Each time one visualizer mode is improved, a different mode seems to pick up collateral damage. This pass exists to make mode ownership explicit all the way from UI/settings through dedicated renderers/math.

- [x] Audit dedicated Blob/Bubble/Spectrum/Oscilloscope/Sine renderer ownership for foreign mode-setting bleed
- [x] Audit dedicated visualizer math/helpers (`blob_math`, `blob_shaper_solver`, `bubble_simulation`, `bar_computation`, `transient_bus`) for foreign mode-setting bleed
- [x] Add a static isolation fence for dedicated mode-owned modules
- [x] Create a stable visualizer setting-change checklist so future setting additions/removals touch all required seams
- [~] Audit the intentionally shared seams (`config_applier`, `spotify_visualizer_widget`, `spotify_bars_gl_overlay`) and document which cross-mode behavior is deliberate versus accidental and how to remove or minimize potential bleed.
- [x] Confirm preset/save/repair/regeneration paths still agree with current mode ownership after the audit findings
- [ ] Finish a live runtime spot-check across the shaper-capable modes after the current Blob tuning pass

Current findings:
- Dedicated renderers/math now look substantially cleaner; the remaining high-risk areas are the shared runtime bridges, not the per-mode solver files
- Sine/Oscilloscope now rely on an intentional neutral line-mode transport rather than hidden ownership through fake `_osc_*` setting flow
- Blob shaped and unshaped motion ownership is intentionally split and now guarded by focused tests, but live Blob feel still needs more runtime validation
- Any future mode-setting change should now route through `Docs/Visualizer_Change_Checklist.md` before being considered complete
- Shared technical-cache replay no longer falls back to "whatever mode happened to be cached first"; missing mode entries now no-op instead of silently applying foreign technical state
- `SpotifyBarsGLOverlay` now treats Spectrum bar-peak memory as Spectrum-owned runtime state: non-Spectrum modes no longer mutate `_peaks`, and switching back into Spectrum resets that ghost history instead of reviving foreign-mode bar memory
- Line-mode overlay resets now explicitly clear waveform count/ring buffers plus transient event envelopes on mode change so Oscilloscope/Sine re-entry starts from its own live signal state instead of carrying stale signal pressure
- Focused behavior coverage now exists for shared technical replay itself, not just for static foreign-token scans in dedicated renderer/math files
- `build_gpu_push_extra_kwargs(...)` now emits mode-local live extras only; line-mode payloads no longer carry Blob extras, Blob no longer carries line-mode extras, and Bubble no longer inherits unrelated line/blob payload clutter just because the overlay can accept those kwargs
- Shared beat-engine bar-count changes now use one canonical reconfigure path instead of keeping a hidden bar-count engine pool; this is meant to remove the early-cycle “slow once, fine later” warm-up hitch without creating runtime-only behavior that diverges from cold startup
- Preset/save/repair/regeneration ownership already agrees with the isolation contract: mode filtering stays prefix-driven in `visualizer_presets`, repair sanitization uses the same filtered/defaulted mode contract, and the shipped regeneration path remains a downstream mirror rather than a competing schema authority

### 6. Blob Energy Balance / Glow Drive Follow-up

**Status:** `[~]` Runtime/log behavior is healthy; only final focused sign-off items remain
**Priority:** Low

Blob `Constant Energy` reportedly overpowers reactive/vocal energy in the non-shaped Blob path and likely needs retuning there only. There is also a product question around Glow Drive inputs.

Landed in code:
- Non-shaped Blob idle wobble/deformation was reduced so low-energy passages stop looking busier than loud ones
- Non-shaped reactive/vocal motion and stage-driving support were increased, then increased again from real Blob runtime logs/preset data so subtle rapid drums and higher stage tiers have a better chance to register
- Non-shaped Blob fast-hit attack/release shaping was tightened again so rapid kick/snare phrases reach the body/stage path faster without turning hitch frames into one-frame event snaps
- Non-shaped Blob concurrent pockets now trigger from fresher raw/transient hit strength with shorter family cooldowns so alternating rapid drum phrases are less likely to land in a pocket dead-zone between spawns
- Non-shaped Blob pocket rendering now adds a short-lived local attack accent on spawn so a fresh hit reads as a distinct pulse instead of disappearing into an already-elevated local plateau
- Blob stage math now explicitly seeds stage `1` from transient-rich snare phrases without letting vocal/snare-heavy material climb the upper rungs too aggressively
- Shaped Blob now owns its own contour residual motion via `blob_shaper_idle_motion` and `blob_shaper_audio_motion` instead of reusing the generic unshaped wobble knobs
- Shaper mode now hides the generic unshaped `Idle Edge Motion`, `Audio Edge Motion`, `Stretch`, and `Shape Reactivity` rows so authored-shape controls stop pretending to share ownership with the freeform Blob path
- Blob shaper arrow tips now read more like actual arrows, and runtime still interprets drag direction as a real authored input rather than a decorative handle
- Focused regression fences now cover both the shaped/unshaped motion split and the shaper-mode UI gating so future tuning work cannot silently reintroduce cross-over
- Dedicated mode-isolation fences now also cover the per-mode renderer/math modules so foreign runtime tokens cannot quietly creep back in there
- Latest live-log read looks healthy overall: no shader fallback, no obvious mode bleed, and strong transient phrases now visibly promote stage `2/3`
- Latest live run impression: Blob now looks significantly nicer, more adaptive, and more organic while keeping the intended feel; remaining work is sign-off and polish, not rescue engineering

- [x] Audit the current non-shaped `Body Response` balance for constant, reactive, and vocal energy
- [x] Confirm the shaped Blob path is isolated before making non-shaped tuning changes
- [x] Land a first tuning pass on the non-shaped path that reduces idle/no-energy deformation and increases real reactive/vocal ownership
- [x] Validate that the new balance is directionally right in live runtime rather than assuming the latest pass is final
- [x] Audit why subtle rapid drum phrases still under-drive non-shaped Blob in live runtime even when authored settings are reasonable
- [x] Audit why stage `2/3` still spend too much time asleep in non-shaped Blob and make the main core size feel parked
- [ ] Review the `Glow Drive` selection list for useful additions such as `Transient`
- [ ] Confirm Blob identity still feels like Blob and has not drifted toward another visualizer mode
- [ ] Final shaped runtime spot-check: confirm shaped Blob still feels correct and unaffected after the non-shaped pocket/stage work
- [x] Keep shaped and non-shaped behavior isolated so no cross-over tuning is introduced

### 6A. Blob Concurrent Deformation Pockets (non-shaped path)

**Status:** `[x]` Landed
**Priority:** N/A

The concurrent non-shaped pocket model is now part of the shipped runtime contract.

What landed:
- Rapid successive non-shaped hits now claim concurrent local deformation pockets instead of fighting one shared decay bucket
- Pocket spawning is driven from fresher transient/raw hit information with shorter family cooldowns
- Fresh pockets carry a short-lived attack accent so new hits read as distinct pulses instead of blending into an already-raised plateau
- The stage ladder now allows transient-rich snare phrases to wake stage `1` without letting vocal/snare-heavy material climb upper stages too aggressively
- The pocket layer remains runtime-only in this first cut; no persisted authored settings, preset schema, repair flow, or regeneration payload was added for it
- Regression fence note: `tests/test_visualizer_reactivity_quality.py::test_blob_transient_rich_snare_phrase_can_seed_stage_progress` exists specifically to catch the “visible drum hit, local deformation moves, but stage stays asleep” failure instead of only checking prettier motion


### 9. Shared Preset Install / Save Location Across SCR and MC

**Status:** `[~]` Landed in code / awaiting dual-install runtime validation
**Priority:** Medium

MC and SCR/NORMAL builds should use the same shipped/user preset location so dual-install users are not split across two preset worlds.

- [x] Audited where SCR/NORMAL currently installs shipped presets and where MC currently installs shipped presets
- [x] Moved frozen runtime loading onto the shared ProgramData curated tree instead of build-local frozen roots
- [x] Added one-time frozen bootstrap so a missing shared ProgramData tree is repopulated from bundled assets instead of silently falling back forever
- [x] Updated MC install flow to refresh the same ProgramData curated tree used by SCR/NORMAL while still keeping a packaged backup copy for `Replace Visualizers`
- [x] Updated `Replace Visualizers` source resolution to prefer packaged/bundled assets and keep the shared ProgramData tree as the active target
- [x] Removed the normal SCR uninstall cleanup that would have deleted the shared preset tree out from under a co-installed MC build
- [x] Added focused tests for frozen shared-root resolution and packaged-source replacement routing
- [ ] Validate install, upgrade, and coexistence behavior with both builds present on one machine

Design guardrails:
- Use one reliable preset location for authored/shipped/user preset state where possible
- Do not break existing user custom presets during migration
- Keep authored source tree vs generated release artefacts clearly separated in repo semantics even if installed locations converge

Implementation notes to preserve:
- Shared active curated root is now `ProgramData\SRPSS\presets\visualizer_modes` for frozen SCR and MC
- Script mode still uses the repo source tree directly
- Packaged/bundled preset trees are now replacement/bootstrap sources, not the active frozen runtime root
- `Replace Visualizers` must keep restoring from packaged assets, not from the already-active shared target
- We still do not have a separate on-disk custom visualizer preset library; the trailing `Custom` slot remains settings-backed rather than file-backed

## Runtime / Log Watchlist

**Status:** `[~]` Ongoing

Keep watching for:
- [ ] Roaming AppData visualizer normalization repair line repeating indefinitely
- [ ] Creator bridge drift between canonical settings model and widget kwargs
- [ ] Source curated tree vs generated shipped tree drift
- [ ] Stale defaults snapshot drift
- [ ] UI preview/live-config helper paths throwing misleading exceptions
- [ ] Reddit Helper queue/heartbeat/state drift that could mask the actual link-handoff failure mode
- [ ] Settings dialog shutdown logs that indicate shell/child teardown ordering regressions

Known items:
- [~] `%APPDATA%/SRPSS/settings_v2.json` may contain older visualizer-era state that `SettingsManager` heals on load. Confirm whether a user-side save permanently clears the repair path.
- [~] Spectrum lane-strength arrows are now the live contract; keep watching for any remaining legacy scalar-lane drift or preset remap edge cases that would make runtime behavior disagree with the editor

---

## Idea Box

> Raw ideas that have not yet been shaped into active tasks. Promote them once they have a concrete goal, scope, and guardrails.

1. Expansion: Raise the supported authored line-count ceiling for Sine and Oscilloscope Modes from `3` to `6` without reviving the old hidden Sine/Osc shared-setting problem.
