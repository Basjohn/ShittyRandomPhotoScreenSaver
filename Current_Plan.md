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
  - Bubble perf is materially better, so keep this narrow: only chase the hot spots the 2026-06-18 05:58-05:59 run still exposes and do not reopen broad shared-seam suspicion without fresh evidence.
  - Keep Bubble mode-isolated unless evidence proves a shared seam is truly culpable.
  - Treat Bubble's current soft feel and the newly recovered perf floor as locked until stricter bars say otherwise.
  - Latest evidence from `logs/screensaver_spotify_vis.log`:
    - Bubble sim now sits around `worker_ms=1.25..1.49`, `tick_ms=0.95..1.18`.
    - The biggest remaining Bubble-owned cost is still collision work: `collision_ms=0.57..0.74`.
    - Snapshot/transport remains second: `snapshot_ms=0.27..0.36`.
    - The new broad-phase guard already cut the isolated Bubble oracle down from near-full quadratic scans to a still-meaningful but much smaller collision field, so the next perf seam is trail/upload churn rather than another blind pair-loop rewrite.
    - Trail transport is still always live in this run: `trail_payload=True`, `trail_floats=495..594`.
  - Immediate checklist:
    - [x] Add the newest late-hot replay lane from the 2026-06-15 live run so the current loud small-lane complaint fails before more Bubble tuning.
    - [x] Add the newest 2026-06-18 mixed-hot replay lane so thinner-but-still-hot manual-floor windows cannot drift back toward soft-passage behavior unnoticed.
    - [x] Extend the Bubble feel-locks with the newest latest-live manual-floor replay signature so current good behavior is harder to erode.
    - [x] Keep a dispatch guard that proves repeated ticks cannot queue duplicate in-flight Bubble compute work.
    - [x] Keep all existing Bubble feel-locks and loud-path lanes green with no softened thresholds.
    - [x] Add Bubble renderer payload-equivalence coverage before changing transport behavior.
    - [x] Surface Bubble-owned worker/sim perf diagnostics into the existing visualizer perf log before deeper hot-path refactors.
    - [x] Remove Bubble trail snapshot payload when no visible trail exists anywhere in the frame, with direct bars proving trail-enabled output still keeps full layout.
    - [x] Stop recomputing effective collision radii for every pair inside the Bubble collision loop.
    - [x] Stop growing Bubble snapshot payload lists bubble by bubble; keep exact-size frame buffers while the feel-locks stay green.
    - [x] Trim Bubble pair-loop policy arithmetic and per-bubble no-op trail writes while keeping the current replay and feel-lock bars green.
    - [x] Add the Bubble transition-time perf oracle before deeper simulation/snapshot work.
    - [x] Avoid needless `sqrt` work for non-overlapping Bubble pairs by comparing squared distances before normalization, while the replay/perf bars stay green.
    - [x] Tighten the Bubble perf oracle to treat the current recovered floor as the minimum acceptable band for `worker_ms`, `collision_ms`, and `snapshot_ms`.
    - [x] Add a safe Bubble-only broad-phase pair-pruning pass so the collision loop no longer behaves like a near-full quadratic scan under the isolated oracle.
    - [x] Stop clearing Bubble uniform transport buffers more broadly than the active payload requires, while keeping the payload-equivalence tests green.
    - [ ] Audit only these safe Bubble perf seams next:
      - trail snapshot / upload churn in `widgets/spotify_visualizer/bubble_simulation.py` and `widgets/spotify_visualizer/renderers/bubble.py` without removing visible trail fidelity
      - leave cadence / delivery / shared-floor suspicion alone unless the strengthened bars or fresh logs reopen them
    - [ ] Keep every Bubble-touching perf task entering and exiting through improved Bubble bar evidence.

- [ ] High priority: close the remaining Bubble loud mixed-hot inconsistency without sacrificing the current soft-path or recovered hot-path feel.
  - Do not special-case vocals, dynamic floor, or shared seams from this run alone; the latest log stayed in `mode=manual gate=0.200 manual=0.200 support=0.000`, so the remaining issue is still a Bubble-owned consistency problem until evidence says otherwise.
  - Latest useful contrast from `logs/screensaver_spotify_vis.log`:
    - stronger hot windows:
      - `05:58:19` `raw_bass=1.572`
      - `05:58:39` `raw_bass=1.257`
      - `05:58:54` `raw_bass=1.503`
      - `05:59:14` `raw_bass=1.271`
    - weaker-than-expected mixed-hot windows:
      - `05:58:29` `raw_bass=1.118` but visible bar envelope stays close to a modest band
      - `05:58:59` `raw_bass=0.945` and still reads restrained
      - `05:59:19` `raw_bass=1.107` but lands well below the friendlier hot windows from the same run
    - newest long-run tail family still worth preserving:
      - `13:40:10` `raw_bass=1.627` with a clearly open, healthy hot shape
      - `13:41:11` `raw_bass=1.377` while the visible shape compresses more than that still-hot section should
      - `13:41:26` `raw_bass=0.476` but the later recovery looks friendlier again, so the remaining issue is inconsistency rather than universal loud failure
  - Immediate checklist:
    - [x] Strengthen the mixed-hot Bubble oracle so hot sparse/thin windows from this run must stay clearly above ordinary mid-level behavior and cannot hide behind “soft is still good” bars.
    - [x] Compare the weak-hot windows against the stronger hot windows from the same run, not only against soft passages, so inconsistency becomes decisively red before more tuning lands.
    - [x] Add the newest late-tail hot replay lane so materially hot tail windows cannot quietly fall below later lower-feed recovery windows without the suite noticing.
    - [x] Keep the first code pass Bubble-only and feed-first; do not reopen shared Dynamic Volume Floor work unless new evidence proves the Bubble seam is already healthy.
    - [x] Land a narrow tiny-bubble sustained-loud support pass that stays simulation-owned, keeps the current hero-lane/soft-path feel locks green, and does not turn into a shared-floor retune.
    - [ ] Preserve the current soft-path feel and the recovered stronger hot windows as locked behavior while fixing the weaker mixed-hot windows.

## Watchlist

- Spectrum solid-bar visual smoothness is no longer active work, but future tuning must stay visual-only and must not reopen audio/reactivity regressions.
- Bubble behavior is locked during the current audit pass. Future work should stay mode-isolated and oracle-first rather than reopening shared-floor or casual cross-mode retuning.
- Visualizer display-participation fallback / duplicate-owner work moved to `Docs/Historical_Bugs.md` entry `R-26`. Reopen it only if fresh runtime logs show fallbacks or duplicate owners after the startup-registration fix plus the cautious sleep/wake recheck contract.
- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.
- Visualizer CUSTOM/runtime geometry is intentionally out of the active queue for now. The current long-term state, landed protections, and low/deferred follow-up work live in `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md`.

## Deferred / Not Active

- Weather cache blanking / premature expiry stays queued but is no longer ahead of the current Bubble perf/loud pass.
  - When it returns to active work, confirm why Weather goes blank even though cache should remain visible until replacement data arrives.
  - Re-audit `widgets/weather_widget.py` cache-read, startup-use, refresh, and replacement authority.
  - Required bars when reactivated:
    - stale cache remains visible until replacement data arrives
    - fetch/error/empty responses do not blank a previously valid card
    - cache timestamps do not force unnecessary blank states during ordinary startup/runtime refresh
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
No unintegrated user tasks.
----
######
