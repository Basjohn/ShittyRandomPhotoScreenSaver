# Current Plan

Last updated: 2026-06-18

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. This is not a changelog.
- Prefer automation bars over repeated runtime-verification asks.
- Do not close visual/runtime bugs from polite unit doubles alone.
- For visualizer geometry, treat these as separate seams until proven otherwise:
  - saved/custom rect authority
  - live widget rect authority
  - GL overlay rect authority
  - startup / prewarm / first-frame authority
  - mode-reset or preferred-height side effects
- A green `replay_final` log is necessary but not sufficient for visualizer geometry closure.
- Recovery paths are allowed only after the root-cause map and the stronger bars exist.
- Gmail/Reddit may adjust height for visible count/cache/dead-space QoL, but no widget gets width authority from that path.

## Active Tasks

- [ ] High priority: execute the Bubble end-to-end audit from `audits/BubbleAudit/Bubble_End_To_End_Audit.md`.
  - Bubble remains the dominant current perf drag, and small-bubble loud participation is still not honest enough in some hot passages.
  - Start with oracle tightening, not tuning.
  - Keep Bubble mode-isolated unless evidence proves a shared seam is truly culpable.
  - Treat Bubble's current good soft/hot feel as locked until stricter bars say otherwise.
  - Immediate checklist:
    - [x] Add the newest late-hot replay lane from the 2026-06-15 live run so the current loud small-lane complaint fails before more Bubble tuning.
    - [x] Extend the Bubble feel-locks with the newest latest-live manual-floor replay signature so current good behavior is harder to erode.
    - [x] Keep a dispatch guard that proves repeated ticks cannot queue duplicate in-flight Bubble compute work.
    - [x] Keep all existing Bubble feel-locks and loud-path lanes green with no softened thresholds.
    - [x] Add Bubble renderer payload-equivalence coverage before changing transport behavior.
    - [x] Surface Bubble-owned worker/sim perf diagnostics into the existing visualizer perf log before deeper hot-path refactors.
    - [x] Remove Bubble trail snapshot payload when no visible trail exists anywhere in the frame, with direct bars proving trail-enabled output still keeps full layout.
    - [x] Stop recomputing effective collision radii for every pair inside the Bubble collision loop.
    - [x] Stop growing Bubble snapshot payload lists bubble by bubble; keep exact-size frame buffers while the feel-locks stay green.
    - [ ] Add the Bubble transition-time perf oracle before deeper simulation/snapshot work.
    - [ ] Audit Bubble hot-path cost in this order:
      - collision path in `widgets/spotify_visualizer/bubble_simulation.py`
      - snapshot/trail list churn in `widgets/spotify_visualizer/bubble_simulation.py`
      - render transport / uniform upload churn in `widgets/spotify_visualizer/renderers/bubble.py`
      - only then bubble cadence / pending-result delivery truth if still needed
    - [ ] Keep every Bubble-touching task entering and exiting through improved Bubble bar evidence.

- [ ] High priority: audit Weather cache blanking / premature expiry.
  - Confirm why Weather is going blank too often even though the cache should behave as replace-only, not expire-to-empty.
  - Trace `widgets/weather_widget.py` cache-read, startup-use, refresh, and replacement paths.
  - Add bars for:
    - stale cache remains visible until replacement data arrives
    - fetch/error/empty responses do not blank a previously valid card
    - cache timestamps do not force unnecessary blank states during ordinary startup/runtime refresh
  - Record whether the bug is:
    - cache timestamp policy
    - startup visibility policy
    - result-authority bug
    - provider payload/replace bug

## Watchlist

- Visualizer requested-display participation/fallback warnings still need a later re-audit if they keep firing while the requested display is clearly live; keep that separate from the current perf pass unless logs prove it is causing rebuild churn.
- Spectrum solid-bar visual smoothness is no longer active work, but future tuning must stay visual-only and must not reopen audio/reactivity regressions.
- Bubble behavior is locked during the current audit pass. Future work should stay mode-isolated and oracle-first rather than reopening shared-floor or casual cross-mode retuning.
- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.
- Visualizer CUSTOM/runtime geometry is intentionally out of the active queue for now. The current long-term state, landed protections, and low/deferred follow-up work live in `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md`.

## Deferred / Not Active

- Reddit fetch, cooldown, identity, and API work stays deferred until the ban/API situation changes.
- Dynamic Volume Floor follow-up is deferred until the visualizer geometry family is genuinely closed again.
- Startup update-policy observability and image-cache/prescale perf stay deferred behind the current active widget/runtime priorities.
- Secure-desktop long-runtime exit reliability stays deferred until the current interactive blockers stop dominating validation time.
- Any further visualizer geometry action should be treated as low/deferred unless new runtime evidence appears. Prefer the audit over reactivating broad mitigation work in the main plan.

## Documentation Rule

- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
- Active geometry audit: `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md`
- Active Bubble audit: `audits/BubbleAudit/Bubble_End_To_End_Audit.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
1.   Over zealous display participation for visualizer recovery that was previous causing duplicate visualizers is still firing when it shouldn't according to logs.
1.2  The same recovery contract/seam is likely responsible for duplicate visualizer instances spawning if the screensaver is active, user turns off their displays and turns them on again. The spawn is identical to the one that previously happened from 1 during normal multi-display runtime.
1.3  My suggestion is to rework that contract entirely, find out why it is firing when it shouldn't, why it is duplicating and rework it with failures in mind. Also consider, what would this contract/seam do it the media/visualizer was set to ALL displays before going into custom? Would it make 3 visualizers? Would it make an even worse break?
----
######
