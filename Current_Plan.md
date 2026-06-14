# Current Plan

Last updated: 2026-06-14

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
