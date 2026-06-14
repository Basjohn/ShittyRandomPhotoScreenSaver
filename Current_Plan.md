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

- [ ] Close the remaining visualizer CUSTOM startup/runtime shape family.
  - Chosen path:
    - keep authored visualizer width/height preset-owned outside `Custom`
    - do not introduce free user-authored visualizer width/height as part of this bug closure
    - solve the real problem as authority drift:
      - committed CUSTOM rect must be iron-clad
      - startup/runtime must not strand the widget in a fallback rect
      - any rescue path must only bring the widget back onto a sane visible-display rect after the root-cause bars and writer audit are strong
  - Why this path:
    - adding free authored width/height now would add another geometry authority before the current startup/runtime lie is closed
    - the current evidence says saved CUSTOM geometry is usually right; the unresolved bug is that startup/live can still birth or retain the wrong shape before replay wins
    - fixing authority first keeps the long-term feature option open without using it as a workaround
- [ ] Refresh the visualizer geometry audit.
  - Keep the current execution audit in `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md`.
  - Keep it explicit about what is now closed:
    - creator-time committed CUSTOM rect priming
    - widget-local rejection of foreign outer-geometry writes while committed CUSTOM authority is active
  - Keep it explicit about what remains open:
    - display recreation / display swap first-visible truth
    - rescue policy only if the remaining bars still prove a real impossible-shape birth
- [ ] Build stricter visualizer geometry bars before the next runtime ask.
  - [x] Land first-wave bars for:
    - top-left startup-origin recovery
    - widget-vs-overlay parity under CUSTOM authority
    - repeated square-drift recovery with overlay parity
    - startup-finalize settle after forced square/startup pressure
    - live settings-refresh settle with stale overlay under active CUSTOM authority
    - creator-time CUSTOM startup guard that fails if the visualizer expands to authored preferred height before committed replay attaches the saved rect
    - creator-time CUSTOM committed-rect birth guard that fails if startup is born at a bogus default rect instead of the saved rect
    - creator-time CUSTOM startup-pressure guard that fails if post-create geometry pressure can still push the visualizer away from the committed rect
    - remote reconcile guard that fails if a remote CUSTOM visualizer accepts a square fallback rect once the committed rect is attached
  - [ ] Add a display-recreation bar that fails if a recreated display can still make the first visible visualizer instance appear in fallback geometry before the committed rect is visible again.
  - [ ] Add a display-swap / monitor-handoff bar that fails if the committed custom rect is correct but the runtime instance for the destination display still starts from a poisoned local rect.
  - [ ] Fail when `replay_final` is green but display recreation, display-swap, or rebuild still produces a live rect that disagrees with the committed custom rect.
  - [ ] Extend aspect-ratio / unauthorized-width-drift coverage beyond the current repeated-drift lane so broader rebuild/display-swap drift cannot hide behind replay logs.
  - [ ] Add a “recovery is not prevention” assertion:
    - if the widget becomes visible in an obscene fallback rect and only later heals, the bar still fails
    - do not allow late correction alone to count as success
- [ ] Remove non-authoritative post-replay geometry writers from the visualizer chain.
  - [x] Inventory direct visualizer geometry writers and rule out the generic transition-overlay helper path as the first culprit.
  - [x] Block authored preferred-height / authored positioning fallback while the visualizer is routed through `Custom` but the committed rect is still pending.
  - [x] Block the duplicate create-time canonical refresh pass while the visualizer is routed through `Custom` and waiting for committed replay.
  - [x] Attach the real `WidgetManager` before `startup_create` so visualizer CUSTOM-route detection is truthful during initial mode/card-height work.
  - [x] Re-audit startup create, settings refresh, secondary-stage activation, preferred-height application, widget positioning, and GL overlay sync from the current tree.
  - [ ] Document the last-authority chain for each risky flow:
    - display recreation
    - display swap
    - rebuild after destination-display handoff
  - [x] Prove where the startup widget rect authority now comes from:
    - creator-time committed rect priming when a saved CUSTOM rect already exists
    - widget-local CUSTOM rect guard for later outer-geometry writes
  - [ ] Prove where the first visible overlay rect comes from for the remaining risky flows:
    - display recreation
    - display swap
    - any prewarm rect tied to those flows
  - [x] Keep committed CUSTOM width/height authoritative once a visualizer rect is saved.
  - [ ] Ensure “CUSTOM chosen but rect not yet attached” is treated as a protected pending-authority state everywhere that can still write geometry.
- [ ] Collapse visualizer CUSTOM geometry onto one committed source while keeping authored follow-media intact outside `Custom`.
  - [x] Make the committed custom rect the sole authoritative shape source for widget outer rect while CUSTOM is active.
  - [x] Keep GL overlay target resolution reading the committed custom rect / runtime custom rect path first.
  - [ ] Prove that display recreation and display swap cannot strand overlay startup on a stale rect once the widget authority is correct.
  - [ ] Keep authored media-follow / preset-owned card sizing available only outside `Custom`.
  - [x] Do not let preset-owned preferred height re-enter as a second shape authority once a committed custom rect exists.
  - [ ] Keep the fix visualizer-local and CUSTOM-local; do not broaden it into generic overlay code unless the bars prove the generic seam guilty.
- [ ] Design the lightest acceptable recovery path after the root cause is narrowed.
  - [ ] Detect impossible/obscene live shapes relative to the committed custom rect.
  - [ ] Limit rescue to:
    - one-shot visible-display plausibility check
    - one repair/rebuild/correction-save path at most
  - [ ] Rescue should only run when the widget is clearly birthed into an impossible shape; it must not be a steady-state correction loop.
  - [ ] Rescue must prefer “bring back onto the visible display with sane committed proportions” rather than inventing a new authored size.
  - [ ] Do not introduce steady-state frame churn, startup poison, or continuous geometry fighting.

## Watchlist

- Spectrum solid-bar visual smoothness is no longer active work, but future tuning must stay visual-only and must not reopen audio/reactivity regressions.
- Bubble work is closed for now; future changes should preserve mode isolation rather than reopening shared-floor contracts casually.
- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.

## Deferred / Not Active

- Reddit fetch, cooldown, identity, and API work stays deferred until the ban/API situation changes.
- Dynamic Volume Floor follow-up is deferred until the visualizer geometry family is genuinely closed again.
- Startup update-policy observability and image-cache/prescale perf follow after the active geometry blocker.
- Secure-desktop long-runtime exit reliability stays deferred until the current interactive blockers stop dominating validation time.

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
