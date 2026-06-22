# Current Plan

Last updated: 2026-06-20

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

## Active Tasks

- [ ] Close the reopened visualizer false `Custom+ALL` route-recovery seam before more CUSTOM geometry work
  - [ ] Prove the creator is reading a transient routing lie rather than bad saved geometry; keep `--geo` / `--viz` evidence attached to the `17:27:06` family where `replay_final` stays correct but the creator still logs `Restored invalid Custom+ALL...`
  - [ ] Keep custom visualizer route validation authoritative to committed custom-layout evidence first:
    - recover a missing/`ALL` visualizer monitor only from a matching saved visualizer screen bucket
    - do not let a broad authored-restore helper mutate valid CUSTOM state during recreate
  - [ ] Refuse to claim a route was restored unless the visualizer actually exits `Custom` and lands on a non-`ALL` authored route
  - [ ] Strengthen the visualizer plumbing bars so this branch fails if it:
    - "restores" authored routing while `custom_routing` is still true
    - clears the saved visualizer rect when only the monitor field was transiently wrong
    - suppresses creation without a genuinely invalid route

## Watchlist

- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.

## Deferred / Not Active

- [ ] Feeds widget family (deferred architecture track)
  - [ ] Keep Reddit as its own branded widget and shared runtime owner; do not replace it with Feeds or duplicate its paint/cache/refresh/click machinery.
  - [ ] Extract reusable list-feed seams from Reddit without changing Reddit UX first: feed item model, shared service-backed refresh/cooldown/startup-skip/cache-authority policy, progressive visible-count growth, manual refresh, and URL-open routing.
  - [ ] Keep provider/network semantics widget-owned and explicit so Reddit and Feeds can diverge cleanly without a second opaque backend framework.
  - [ ] Design `Feeds` as an additional widget family with `1..5` user-configured spawns, per-spawn source URL, quick validation/test affordance, isolated cache key/storage, and shared `--noupdates` / cooldown behavior.
  - [ ] Make official/feed-native sources the first-class Feeds contract: custom RSS/Atom, explicit JSON feeds, and source-specific adapters only when the site already offers a stable public feed contract.
  - [ ] Keep likely friendly Feeds source candidates narrow and explicit: official publisher RSS/Atom feeds, project/blog feeds, public NASA/APOD-style feeds, Bing-style image/news feeds, Flickr public feeds, and other feed-native sources that do not require HTML scraping or session automation.
  - [ ] Add settings/runtime bars before activating Feeds work: feed-url validation stays off the UI thread, empty/error replacements do not blank valid cached content, per-spawn caches stay isolated, and manual refresh/cooldown/startup-skip behavior matches the intended user contract.
- Dynamic Volume Floor follow-up stays deferred.
- Startup update-policy observability and image-cache/prescale perf stay deferred behind the current widget/runtime priorities.
- Secure-desktop long-runtime exit reliability stays deferred.

## Documentation Rule

- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
- Active geometry audit: `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md` when geometry/runtime replay issues reopen
- Bubble preset/runtime audit: `audits/BubbleAudit/Bubble_Preset_Runtime_Audit.md` as historical authored-setting reference
- Bubble historical audit reference: `audits/BubbleAudit/Bubble_End_To_End_Audit.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
No unintegrated user tasks.
----
######
