# Current Plan

Last updated: 2026-06-01

This file tracks active work only. Ongoing architecture truth belongs in the relevant reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. Once a milestone is materially landed and no longer driving active decisions, collapse it instead of letting this plan become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

- [ ] Re-audit general compositor transition performance after the warmup/desync rescue.
  - [ ] Keep all multi-display-specific checks explicitly open even while single-display testing is the only runtime available; one 1440p display cannot validate the real stagger/desync contract or clear same-instant sibling-display pressure.
  - [ ] Use the current single-display evidence as the live starting point: the old fake catastrophic timer-gap story is gone, but real drift still remains (`RainDrops` about `+374ms`, `Warp` about `+357ms`, `BlockSpin` about `+368ms`) and smaller real visualizer `Tick dt spike` warnings around `42-49ms` still show up both during and outside transitions.
  - [ ] Keep the timing-base audit explicit: remove cadence drift caused by compositor timer scheduling/loop overhead before blaming transition-local math, while preserving current visualizer audio freshness and first-frame guardrails.
  - [ ] Trace the real shared cadence fault instead of transition-local symptoms: focus on the recurring `SpotifyVisualizerWidget._on_tick` spikes, transition-active drift, and any UI-thread or overlay `show()` / `set_state` work clustered in the same windows.
  - [ ] Confirm the global display-level image handoff stagger plus the broadened compositor-side desync are both active for the transition families that matter in real use, not just crossfade.
  - [ ] Verify the broadened desync remains imperceptible to users while reducing same-instant multi-display start overhead once multi-display runtime is available again.
  - [ ] Keep all work on shared compositor/image/cache seams first; do not degrade fidelity or remove transition features to fake a perf win.

- [ ] Restore image-cache / prescale performance to a healthy runtime contract.
  - [ ] Treat the current single-display 1440p limitation as a validation boundary, not a closure signal: this setup can validate single-display cache authority, cold-start fallthrough, and transition-complete resume logging, but it cannot clear multi-display stagger/desync/bunching risk.
  - [ ] Validate the newly landed prefetch authority contract in runtime: mixed-source lookahead now mirrors `ImageQueue.next()` via preview state, so confirm the upcoming images being warmed are the images that actually appear under local/RSS ratio, history, and domain-diversity rules.
  - [ ] Focus the next single-display investigations on what this setup can still expose well: cold-start scaled misses, early manual-next worker fallthrough, scaled-hit growth during steady state, and whether cache-side work correlates with the shared cadence stalls still seen in `--perf`.
  - [ ] Validate the serialized/staggered scaled warmup path under aggressive multi-display use: confirm low-priority scaled warmup no longer bunches work across displays or noticeably drags UI-thread responsiveness, visualizer cadence, cursor halo smoothness, or input responsiveness.
  - [ ] Re-run clean `--perf --cache` validation after the contract fix and confirm shutdown summaries show real scaled/raw reuse while `ImageWorker prescale` spikes materially drop during cold startup and forced early next-image churn, not just later steady-state rotations.
  - [ ] If startup ordering must be touched again for cache reasons, treat it as explicit shared startup work with separate validation rather than as an incidental cache side effect.
  - [ ] Keep fixes on shared cache/prefetch/image-pipeline seams first, but allow adjacent shared startup sequencing work only when the evidence shows the cache contract and first-frame contract are interacting in the same path.
  - [ ] Treat any renewed startup flicker, black widget backgrounds, wrong shadow/backing behavior, or first-frame mismatch as an automatic rollback condition for cache work.

- [ ] Validate hidden/quiescent deferred transition warmup against fresh runtime startup/transition logs.
  - [ ] Investigate the current startup flicker separately from cache work and keep ownership clear if it predates or outlives cache changes.
  - [ ] Keep the startup-order audit split by what is actually known now: current single-display logs support the coordinated overlay reveal gate on screen 0, but they do not clear the earlier display-1/multi-display report that media could surface too early in real runtime.
  - [ ] Compare Codex-terminal launches versus ordinary terminal launches as a timing-sensitive startup variant, since the embedded terminal appears to amplify the race even though SRPSS does not branch on any `CODEX_*` env vars.
  - [ ] Confirm hidden deferred warmup is covering both remaining transition-program compile and representative transition-resource/state prep strongly enough that first-use transitions do not fall back to expensive visible-surface warmup work in normal startup runs.
  - [ ] Confirm first-use non-crossfade transitions still compile/bind and run correctly even if deferred startup warmup is skipped or incomplete on a given compositor.
  - [ ] Confirm transition start does not pay redundant compositor `makeCurrent()` / ensure-bind work once deferred warmup has already populated the pipeline attrs for that transition.
  - [ ] Validate the broadened shared compositor-side desync across non-crossfade transition families and confirm the delay remains imperceptible while reducing same-instant multi-display start overhead.
  - [ ] Keep this on the shared GL lifecycle seam only; do not reintroduce live-surface startup warmup or transition-specific ad hoc compile hacks.
  - [ ] Keep first-use transition correctness and transition performance as separate acceptance criteria; startup must stay visually clean and policy-correct while deferred warmup also stops contributing to the remaining startup/first-use perf stalls.
  - [ ] Use the current single-display evidence as a partial positive check only: reveal diagnostics support the contract on screen 0, but the earlier cross-display startup artifact remains open until multi-display runtime reproduces cleanly.

- [ ] Audit long-runtime secure-desktop exit reliability with display wake/edit-mode/visualizer activity in mind.
  - [ ] Keep this fully open despite the current single-display focus; the real risk case is specifically long-runtime + wake + runtime activity under the real screensaver environment, and that cannot be waved away by cleaner ordinary exits in current local runs.
  - [ ] Trace the stop/quiesce/cleanup path used by real screensaver runtime after long display-off periods and confirm it still closes cleanly when displays are woken shortly before exit.
  - [ ] Examine whether `WM_DISPLAYCHANGE` / wake handling, display recreation, or wake-triggered visualizer/media refresh can leave late runtime work alive past the quiesce boundary and interfere with secure-desktop teardown.
  - [ ] Examine whether brief CUSTOM edit-mode entry/exit or visualizer-mode changes after a long runtime can leave any top-level overlays, timers, worker tasks, or focus/activation state behind that would block or delay clean exit from `winlogon`.
  - [ ] Add targeted lifecycle diagnostics only if needed, through the existing CLI-first logging families, so a future hard-to-reproduce winlogon hang can be correlated without making general logs noisy.

- [ ] Investigate high-resolution interaction smoothness for the cursor halo in general plus CUSTOM edit-mode widget movement.
  - [ ] Treat the current halo feel improvement as a partial runtime win, not closure: preserve it while continuing to trace why 4k interaction still diverges from 1440p.
  - [ ] Compare the live cursor halo path and edit-shell drag/update cadence between the 1440p-good and 4k-choppy displays to identify where higher refresh, DPR, larger repaint regions, or top-level move churn are causing stagger.
  - [ ] Trace whether the bottleneck is input event frequency, halo animation/repaint cost, halo window move churn, edit-shell restack/reclamp work, or a broader per-frame UI-thread choke shared by high-resolution interaction tasks.
  - [ ] Propose improvements that preserve the current 1440p feel and do not trade away lower-resolution smoothness, edit precision, or visual fidelity just to mask 4k choppiness.

- [ ] Audit and, if justified, modernize Blinds on the same clean compositor contract.
  - [ ] Confirm whether Blinds is still carrying dead CPU-side slat/`QRegion` work while the compositor shader is authoritative.
  - [ ] If so, migrate Blinds toward the `Diffuse`/clean Blockflip pattern: controller supplies only grid/direction/feather hints while the shader owns the reveal path.
  - [ ] Preserve the current visual fidelity; do not flatten or cheapen the look just to make the controller simpler.

- [ ] Audit Rain Drops with special attention to shader-path truth and fallback removal.
  - [ ] Confirm in real runtime/log evidence whether Rain Drops is ever falling back from its shader path to the diffuse-region path.
  - [ ] If fallback is still being exercised under ordinary supported runtime conditions, treat that as a bug, not an acceptable steady-state contract.
  - [ ] Remove or retire fallback usage where safe so Rain Drops stays on one authoritative shader path under normal supported operation; broad steady-state fallback behavior is explicitly unwanted here.
  - [ ] Keep this aligned with the project guardrail that broad/steady-state fallbacks are harmful when they silently preserve poorer behavior.

- [ ] Re-audit opt-in non-`Custom` authored stacking against live `--geo` traces before trusting it beyond experimental use.
  - [ ] Keep the feature default-off until the left-column `weather` / `reddit` / `gmail` case stops preserving dead air and stops pushing `gmail` below the display despite a fit being possible.
  - [ ] Verify the planner is using canonical authored anchor baselines plus real visible-footprint heights, not stale post-stack live `y` drift or shadow-inflated collision envelopes.
  - [ ] Keep `spotify_visualizer` and other companion/media-relative widgets out of authored stacking.
  - [ ] Keep known follow-media companion occupancy, especially the media+visualizer block, as a fixed obstacle in the shared lane planner so fade-in does not create a new overlap after authored widgets already stacked and the planner does not shove media off-screen trying to make room.
  - [ ] Make `--geo` logs show the final runtime lane plan clearly enough to compare authored anchors, measured heights, and resolved offsets without needing screenshots alone.
  - [ ] Do not disturb `Custom`; all rescue work stays on the authored non-`Custom` seam only.

- [ ] Preserve the future Reddit/Gmail edge-resize contract before implementation so later work does not drift.
  - [ ] Keep overall font/element size as the primary size authority.
  - [ ] Keep wheel resize uniform-only.
  - [ ] Keep corner resize uniform-only.
  - [ ] Treat future top/bottom edge resize as a separate vertical-capacity gesture only; it may add/remove rows/posts/content but must not replace the overall size contract.
  - [ ] Treat future left/right edge resize as a separate horizontal content-budget gesture only; it may widen/narrow text budgets/padding but must not replace the overall size contract.
  - [ ] When that work starts, extend the canonical CUSTOM resize seam instead of adding widget-local alternate resize paths.

## Watchlist
- Non-`Custom` authored stacking is now explicit opt-in and must stay default-off until a future re-audit proves the planner respects real authored screenshots plus `--geo` traces.
  - Latest bad evidence showed left-column layouts preserving dead air while still pushing `gmail` too low, and right-column layouts pulling `media` far upward from authored bottom-right, which in turn dragged the media-relative visualizer with it.
  - If stacking is reopened later, reassess authored intent vs runtime movement before tuning the planner again; do not silently re-enable it as a global default.
- If `--perf` is enabled and a transition watchdog or compositor-complete failure reappears, check `rendering/gl_profiler.py` / `rendering/gl_compositor.py` before treating it as a transition-runtime regression.
- Keep visualizer preset/settings drift in view during later audits:
  - preserve CLEAR-then-APPLY semantics,
  - do not reintroduce a second post-overlay merge phase,
  - do not reintroduce entry-point-specific fallback behavior for visualizer settings.

## Deferred / Not Active
- Parallelism policy stays profiling-driven if performance work is reopened:
  - profile first and identify a real hotspot before changing thread/process counts,
  - prefer isolated pure-compute kernels or process-safe workloads, not Qt/UI/OpenGL ownership paths,
  - treat visualizer mode work as eligible for more off-thread compute only when it can be expressed as snapshot-in / result-out without thread-affinity side effects,
  - treat another process as more likely than another generic Python thread if a future hotspot is both heavy and sufficiently isolated.
- Imgur raise-path cleanup/testing is not active work while Imgur remains inactive. Revisit only if the widget is reactivated or if a shared overlay-system change would otherwise leave the dormant path stale.



## Documentation Rule
- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
----
######
