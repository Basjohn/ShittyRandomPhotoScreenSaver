# Current Plan

Last updated: 2026-05-25

This file tracks active work only. Ongoing architecture truth belongs in the relevant reference docs, while dated severe/complex bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails
- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. Once a milestone is materially landed and no longer driving active decisions, collapse it instead of letting this plan become a changelog.
- Keep harnesses/probes intact unless explicitly asked to retire them.
- Treat `presets/visualizer_modes/` as authored content. Tests may validate schema/index/repair behavior, but must not force exact preset names, slots, or creative numeric values.
- Do not close visual/runtime bugs from tests alone when symptoms are user-visible.
- Avoid broad focus, window-flag, compositor, widget-shadow, visualizer, or Qt effect rewrites unless the current task directly requires them.

## Active Tasks

- [ ] Validate hidden/quiescent deferred transition warmup against fresh runtime startup/transition logs.
  - [ ] Confirm the startup black flicker no longer appears around the deferred warmup window.
  - [ ] Confirm hidden deferred warmup is covering both remaining transition-program compile and representative transition-resource/state prep strongly enough that first-use transitions do not fall back to expensive visible-surface warmup work in normal startup runs.
  - [ ] Confirm first-use non-crossfade transitions still compile/bind and run correctly even if deferred startup warmup is skipped or incomplete on a given compositor.
  - [ ] Confirm transition start does not pay redundant compositor `makeCurrent()` / ensure-bind work once deferred warmup has already populated the pipeline attrs for that transition.
  - [ ] Confirm the async image path is now consuming prefetched `|scaled:WxH` cache variants instead of unnecessarily round-tripping through `ImageWorker` prescale on every image change.
  - [ ] Validate the broadened shared compositor-side desync across non-crossfade transition families and confirm the delay remains imperceptible while reducing same-instant multi-display start overhead.
  - [ ] Verify whether the documented `ImagePrefetcher` post-transition delay contract is actually exercised in runtime; if it is still inert, fix that at the shared prefetch/display seam instead of layering transition-specific throttles.
  - [ ] Keep this on the shared GL lifecycle seam only; do not reintroduce live-surface startup warmup or transition-specific ad hoc compile hacks.
  - [ ] Re-check Block Puzzle Flip after the CPU-side region simulation retirement; if it is still disproportionately expensive, treat that as a transition-specific redesign/perf follow-up rather than reintroducing dead controller bookkeeping.

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
- Visualizer first-frame / first-bar authority remains a cold watch item, not active implementation work, unless one of the audits above exposes a concrete regression path touching it.

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
