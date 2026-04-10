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

- **Date:** `2026-04-11`
- **Status:** Reddit Helper scheduled-task authority remains runtime-proven, Spectrum vocal-lane and Energy Arrow work are user-validated, the shared preset/repair flow is now on the modern lane-map contract, Blob concurrent pockets are landed and behaving well in runtime, the settings shell now uses an accepted forged-corner outer-border compromise that is visually almost bleed-free without disturbing acrylic or the custom title bar, and the early-cycle visualizer preset-switch hitch now uses a single startup/runtime-parity beat-engine rebuild path instead of hidden warmed engine variants. Spectrum consolidation remains open for deeper control-pruning decisions, the visualizer isolation/bleed audit is now down to final runtime confirmation items, and Bubble/Blob now have log-shaped regression coverage for the hot-hold/hot-baseline trap rather than only clean synthetic phrases.
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

### H9. Visualizer Runtime Preset-Switch Hitch / Shared Beat-Engine Rebuild
The once-per-cycle slow preset/mode-switch hitch no longer uses hidden bar-count-specific warmed engine variants. The shared beat engine now rebuilds bar-count-dependent state through one canonical startup/runtime-parity reconfigure path, preserving the bleed guardrails while removing the “slow once, fine later” warm-pool architecture.

### H10. Blob Concurrent Deformation Pockets
Non-shaped Blob now uses concurrent local deformation pockets with transient-aware spawning and short-lived attack accents so rapid phrases can stack organically instead of fighting one shared decay bucket. Shaped Blob remains fenced off from that runtime-only pocket state.

---

## Active Tasks

### 1. Spectrum Consolidation Pass (was §3.3)

**Status:** `[~]` Partially landed / deeper cleanup still open
**Priority:** Medium

- [x] Clarify the highest-confusion Spectrum overlaps without changing the runtime math contract
- [x] Separate authored `Reactivity` / `Shape Floor` copy from Technical sensitivity/noise-floor copy
- [x] Replace misleading `Adaptive Sensitivity` wording with an explicit recommended fixed-sensitivity path
- [x] Add mode-aware audio block size guidance with lower/higher tradeoffs and a Spectrum recommendation
- [x] Add a centralized per-mode recommendation marker to the shared `AGC Strength` slider so guidance is visible without creating a second control surface
- [ ] Decide whether `AGC Strength` can be reduced further in scope or presentation without removing genuinely useful expert tuning
- [ ] Decide whether Spectrum should keep the recommended/manual sensitivity toggle at all or collapse fully to a single manual slider path
- [ ] Keep shimmer-at-mid-height as a defined tuning target rather than a vibe-based cleanup
- [ ] Defer shimmer assessment/fix until the rest of this plan has landed cleanly, but do not defer ordinary consolidation work that can proceed safely now
- [ ] When shimmer/flicker work starts, add a behavior-level reactivity regression test in the same spirit as the Blob stage-seeding test so the failure is reproducible without relying only on manual runs

What landed in this pass:
- Spectrum authored Audio copy now explicitly separates creative motion controls from Technical signal tuning
- `Profile Floor` is now presented as `Shape Floor` so it stops reading like the same thing as Technical noise floor
- Shared Technical UI now calls the checkbox `Use Recommended Sensitivity` because the underlying worker path is a fixed tuned multiplier, not live adaptive analysis
- Shared Technical audio-block tooltip now explains lower-vs-higher tradeoffs and shows a per-mode recommendation (`128` for Spectrum/Oscilloscope/Sine Wave, `256` for Blob/Bubble)
- Shared Technical AGC guidance now explains the shared normalization behavior in mode-specific language with recommendation ranges instead of one generic tooltip
- Shared Technical `AGC Strength` keeps a single slider but now paints a subtle per-mode recommended groove marker through the centralized slider styling layer
- Sine Wave renderer-side `Sensitivity` now reads as `Line Response`, and Oscilloscope `Line Amplitude` now explicitly explains that it is renderer-side waveform height rather than a duplicate of Technical sensitivity
- Bubble keeps its broad control surface, but Swirl now hides the ordinary stream/drift direction rows while active so the motion branch reads more honestly

Why the task stays open:
- Spectrum still has a real expert-layer overlap question around `Output Lift`, `AGC Strength`, and `Input Gain`
- The shimmer work is still intentionally deferred and should not get bundled into these copy/ownership cleanups by accident

Captured tuning notes:
- Mid-height shimmer is not the same problem as quiet-floor jitter
- The target is steadier mid-height motion at 60 fps without flattening large high/low movements
- Compare behavior on `<=60 Hz` displays versus `165 Hz` displays and decide whether the eventual fix should improve one, both, or both differently
- `drop_speed` alone is too blunt; Spectrum needs room for large rises and large falls
- Guardrail: `Input Gain` is non-negotiable and must stay available during any consolidation/reduction pass
- Recurring Bubble/Blob warning: do not accept a "fix" that only swaps shared smoothed/post-AGC deadness for pre-AGC/raw blowout. The root issue is a signal-contract mismatch: a hotter signal family being fed into support/overdrive math tuned for a colder one.
- Recurring Bubble/Blob warning: stale scheduler events can create the same fake-hot behavior even after the continuous signal path is improved. Treat repeated `peek_latest()` reuse on mode event lanes as the same bug family, not as a separate tuning issue.

Runtime watch note:
- [x] Runtime preset cycling now shares the Custom-slot snapshot/restore contract with the settings UI
- [x] Runtime preset cycling no longer blocks the hot path on an immediate settings JSON flush
- [x] Runtime preset cycling no longer spins up hidden bar-count-specific beat-engine/worker variants

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
- Blob and Bubble continuous-energy routing no longer depend on the retired `_use_raw_energy` seam; both modes now explicitly consume mode-owned pre-AGC energy bands through the shared signal handoff without persisting a sidecar toggle or reviving old preset keys
- Preset/save/repair/regeneration ownership already agrees with the isolation contract: mode filtering stays prefix-driven in `visualizer_presets`, repair sanitization uses the same filtered/defaulted mode contract, and the shipped regeneration path remains a downstream mirror rather than a competing schema authority
- [~] Bubble flattening after `Move To Custom` / re-entry appears to have been a real shared-signal routing problem rather than a dead preset. The log-backed fix is landed; next runtime eyes should confirm Bubble no longer enters a visually "dead" hold state under hot floor pressure.
- [~] Bubble/Blob root-cause trap is now explicit: repeated regressions have shown that changing only the source signal path is not enough. Any future work here must solve the signal-contract mismatch itself rather than just tuning whichever symptom appears next (Bubble dead hold, Bubble ceiling pinning, Blob blowout, Blob judder).

### 6. Blob / Bubble Energy Contract Follow-up

**Status:** `[~]` Reopened from latest long-run evidence
**Priority:** High

The latest long validation run showed the shared signal-contract family was not fully solved yet. That led to new log-shaped regression tests that now reproduce the real failure shape instead of only idealized alternation. Bubble overdrive gating and Blob hot-state unwind have since been tightened in code and are now green in the targeted suites, but the issue should stay open until fresh runtime validation confirms the live feel matches the synthetic win.

What is still landed and worth keeping:
- Non-shaped Blob idle wobble/deformation was reduced so low-energy passages stop looking busier than loud ones
- Non-shaped reactive/vocal motion and stage-driving support were increased, then increased again from real Blob runtime logs/preset data so subtle rapid drums and higher stage tiers have a better chance to register
- Non-shaped Blob fast-hit attack/release shaping was tightened again so rapid kick/snare phrases reach the body/stage path faster without turning hitch frames into one-frame event snaps
- Non-shaped Blob concurrent pockets now trigger from fresher raw/transient hit strength with shorter family cooldowns so alternating rapid drum phrases are less likely to land in a pocket dead-zone between spawns
- Non-shaped Blob pocket rendering now adds a short-lived local attack accent on spawn so a fresh hit reads as a distinct pulse instead of disappearing into an already-elevated local plateau
- Blob stage math now explicitly seeds stage `1` from transient-rich snare phrases without letting vocal/snare-heavy material climb the upper rungs too aggressively
- Non-shaped Blob defaults no longer start with inward stretch pressure by accident: shared widget/overlay/renderer defaults now keep inner stretch at `0.0` and outward stretch at the modern `0.35` baseline until authored settings say otherwise
- Shaped Blob now owns its own contour residual motion via `blob_shaper_idle_motion` and `blob_shaper_audio_motion` instead of reusing the generic unshaped wobble knobs
- Shaper mode now hides the generic unshaped `Idle Edge Motion`, `Audio Edge Motion`, `Stretch`, and `Shape Reactivity` rows so authored-shape controls stop pretending to share ownership with the freeform Blob path
- Blob shaper arrow tips now read more like actual arrows, and runtime still interprets drag direction as a real authored input rather than a decorative handle
- Focused regression fences now cover both the shaped/unshaped motion split and the shaper-mode UI gating so future tuning work cannot silently reintroduce cross-over
- Dedicated mode-isolation fences now also cover the per-mode renderer/math modules so foreign runtime tokens cannot quietly creep back in there
- Stale scheduler event reuse is now fenced at the right seams: Blob mode handoff consumes event edges once, and Bubble no longer re-authorizes burst/overdrive by repeatedly polling the same scheduler event
- New log-shaped regression coverage now reproduces the real failure family instead of only the earlier clean synthetic phrases:
  - Bubble medium-vocal runs now fail if overdrive latches for too much of the phrase
  - Blob hot-seed calm windows now fail if live/support/stage pressure stays too hot after the phrase has already cooled
- Targeted tuning is now landed against those tests:
  - Bubble overdrive authorization is stricter and its hold timer is shorter so medium vocal material can breathe instead of parking in hold
  - Blob calm-only hot-state unwind is faster across live body support, glow support, and stage release when the incoming frame has genuinely cooled
- Latest code-side state is better than the older long run: the regression family is now behavior-tested and no longer invisible to the suite, but live runtime still has to confirm that Bubble ceiling/specular feel and Blob hot-body feel are genuinely corrected
- Treat the current state as rescue/tuning follow-up again, not as final polish

- [x] Audit the current non-shaped `Body Response` balance for constant, reactive, and vocal energy
- [x] Confirm the shaped Blob path is isolated before making non-shaped tuning changes
- [x] Land a first tuning pass on the non-shaped path that reduces idle/no-energy deformation and increases real reactive/vocal ownership
- [x] Validate that the new balance is directionally right in live runtime rather than assuming the latest pass is final
- [x] Audit why subtle rapid drum phrases still under-drive non-shaped Blob in live runtime even when authored settings are reasonable
- [x] Audit why stage `2/3` still spend too much time asleep in non-shaped Blob and make the main core size feel parked
- [x] Re-audit the continuous support / glow / stage handoff using the latest long-run logs rather than the earlier shorter healthy-seeming runs
- [x] Add stronger behavior tests that fail for the current reality:
  - Bubble now fails if medium-vocal / conservative runs can sit in overdrive hold for extended windows
  - Blob now fails if a log-shaped hot seed cannot unwind quickly enough during a calm window
- [ ] Decide whether curated Blob presets need a source-tree retune after the runtime contract is corrected
- [ ] Re-audit Bubble big-bubble ceiling and specular-size coupling once the overdrive contract is calmer
- [ ] Review the `Glow Drive` selection list for useful additions such as `Transient`
- [ ] Confirm Blob identity still feels like Blob and has not drifted toward another visualizer mode
- [ ] Final shaped runtime spot-check: confirm shaped Blob still feels correct and unaffected after the non-shaped pocket/stage work
- [x] Keep shaped and non-shaped behavior isolated so no cross-over tuning is introduced
- [ ] Once runtime is behaving again, create dedicated Blob and Bubble sentinel presets with sane no-blowout settings so future manual runs can use them as quick antagonists instead of re-litigating whether authored settings were the problem

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
- [~] Bubble/Blob signal-path watch: if Bubble sticks at max size / jerky hold or non-shaped Blob becomes a constant hot judder after a "raw energy" rescue, treat that as the same recurring signal-contract bug family rather than as isolated mode-local fallout.

---

## Idea Box

> Raw ideas that have not yet been shaped into active tasks. Promote them once they have a concrete goal, scope, and guardrails.

1. Expansion: Raise the supported authored line-count ceiling for Sine and Oscilloscope Modes from `3` to `6` without reviving the old hidden Sine/Osc shared-setting problem.
