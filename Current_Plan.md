# Current Plan

Last updated: 2026-06-15

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

- [ ] High priority: recover multi-display transition/compositor performance.
  - Keep the investigation scoped to measured throughput loss, not generic widget paint suspicion.
  - Maintain automation bars for:
    - adaptive/compositor timer dispatch must not flood the UI queue with duplicate pending updates
    - compositor warm helpers must not touch the live visible surface when hidden shared warmup is unavailable
    - transition perf fixes must preserve cadence responsiveness rather than solving stalls by becoming stale
    - PERF HUD / diagnostics work must not rebuild expensive overlay assets every compositor shader frame when the displayed content has not changed
    - overlay timer gap diagnostics must name likely starvation cause rather than implying a cheap widget callback is the hot path
    - adaptive timer manager logs must distinguish real pause/resume transitions from no-op state reports
    - scaled prefetch planning must follow likely runtime consumption order rather than path-by-display cross-product fan-out
    - scaled prefetch throughput must stay bounded and useful: immediate display-pair requests may use small controlled parallelism, but warmup must not reopen churn
  - Trace and validate the remaining hot-path seams in this order:
    - compositor render pacing during active transitions now that PERF HUD rebuild churn is reduced
    - image prescale / scaled-cache reuse after the new ordered/bounded scaled warmup pass
    - remaining per-image GL texture upload churn after live-surface warm deferral
    - any residual noisy timer-gap diagnostics versus real stalls
  - Immediate next runtime/log questions:
    - after paint-consumption coalescing plus resumed-metric resets, do compositor render-timer metrics now read per-transition truth instead of smearing paused/idle gaps into fake 10s stalls
    - after the CustomAnimator hot-path direct-callback pass, do compositor transition `GL ANIM` averages materially improve without reopening completion or listener compatibility regressions
    - after the frame-budget warning burst throttle, do `--perf` runs stay loud enough for diagnosis without the warning stream itself becoming measurable churn
    - after those passes together, do transition paint `avg_fps` / `dt_max` improve materially without reopening first-frame, last-frame, or stale-pending regressions
    - does fresh multi-display startup still crater before the first few transitions have warmed naturally
    - did warning-level `Hidden shared warmup context unavailable; deferring ... to first-use warmup` fire, and if so how often
    - after the PERF HUD cache pass plus the ordered/bounded scaled warmup pass, do `scaled_prefetch_completed`, `scaled_hits`, and `worker_fallbacks` materially improve
    - after those cache-side improvements, are the worst remaining spikes dominated by `ImageWorker prescale`, `GL TEXTURE Slow upload`, or compositor paint cadence
  - Use `--perf` evidence to separate:
    - true paint/upload cost
    - UI-queue backpressure
    - cache miss / redundant prescale work
  - Do not “fix” this by softening FPS targets, adding stale visual holds, or broad fallback behavior.

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
- Bubble work is closed for now; future changes should preserve mode isolation rather than reopening shared-floor contracts casually.
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

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
No unintegrated user tasks currently remain in this box.
----
######
