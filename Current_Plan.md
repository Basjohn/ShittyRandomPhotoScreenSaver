# Current Plan

Last updated: 2026-06-19

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

- [ ] Visualizer CUSTOM settings-close geometry audit
  - [ ] Keep `U-09` open until a real settings-close rebuild no longer produces:
    - top-left visualizer placement
    - impossible narrow/square visualizer live shapes
    - replay-green/runtime-wrong visualizer ownership
  - [ ] Prove the startup/settings rebuild seam uses one cautious delayed verify/confirm contract before any last-resort visualizer custom-rect reapply.
  - [ ] Add or keep regression bars for:
    - startup square-pressure recovery without blind next-turn reapply churn
    - persistent post-startup visualizer custom-rect mismatch self-healing after delayed confirmation
    - no duplicate-owner regression from the separate sleep/wake fallback path
  - [ ] Recheck the newest settings-close/runtime logs after the next live validation and prune this task immediately if the visualizer stays on its committed rect.

- [ ] Bubble preset/runtime pass
  - [ ] Treat `Preset 9 (Deep Sea Hero Lift)` as the current golden debug preset/oracle for loud-path Bubble work until the loud-collapse family is truly closed.
  - [ ] Keep the `Preset 9` bars as the active minimum so Bubble tuning stays anchored to runtime-visible truth instead of drifting back into proxy math:
    - broad hot windows must stay more alive than the soft opener
    - loud fixture windows must gain visible hero openness, not just speed
    - manual-floor loud holds must stay alive without clamp-faked single-shape pinning
  - [ ] Re-run the difficult-song runtime with the current `Preset 9` authored envelope:
    - `bubble_big_size_max=0.038`
    - `bubble_big_size_clamp=4.0`
    - `bubble_big_bass_pulse=0.85`
    - `bubble_input_gain=0.75`
    - `bubble_agc_strength=0.18`
  - [ ] Keep the current logic order explicit:
    - authored AGC/input/transient balance remains the first suspect because it already helped somewhat without reopening shared-floor churn
    - Bubble-owned code changes should stay narrow and only serve seams the `Preset 9` bars still prove wrong
  - [ ] If runtime still shows loud small-bubble under-participation, capture the exact `--viz` window and compare it against the corrected `Preset 9` replay/fixture bars before any more Bubble tuning.

- [ ] Weather cache blanking audit
  - [ ] Confirm why Weather can still go blank even though cache should remain visible until replacement data arrives.
  - [ ] Keep/add cache-authority bars proving:
    - stale cache stays visible through refresh
    - empty/error replacements do not blank a valid card
    - cache timestamps do not force an avoidable empty startup

## Watchlist

- Spectrum solid-bar smoothness is no longer active work; keep future changes visual-only.
- Bubble end-to-end audit notes are historical reference now; use the new preset/runtime audit before more Bubble code tuning.
- Non-`Custom` authored stacking stays default-off until a future re-audit proves it against real authored layouts plus `--geo`.

## Deferred / Not Active

- [ ] Feeds widget family (deferred architecture track)
  - [ ] Keep Reddit as its own branded widget and shared runtime owner; do not replace it with Feeds or duplicate its paint/cache/refresh/click machinery.
  - [ ] Extract the reusable list-feed seams from Reddit into shared code without changing Reddit UX first:
    - feed-item model (`title`, `url`, `created_utc`, optional score/source label)
    - shared service-backed refresh/cooldown/startup-skip/cache-authority policy
    - shared progressive visible-count growth and cache replay
    - shared manual refresh / `--noupdates` behavior
    - shared URL-open routing and secure-desktop handoff
  - [ ] Keep provider/network semantics widget-owned and explicit:
    - Reddit provider behavior stays local to Reddit
    - Feeds provider behavior stays local to Feeds
    - shared helpers must not become a second opaque backend framework
  - [ ] Design `Feeds` as an additional widget family that reuses the shared Reddit-derived architecture but has its own identity and settings:
    - allow user-configured feed widget spawns (`1..5`)
    - per-spawn source URL with quick validation/test affordance
    - per-spawn cache key/storage and visible-count settings
    - shared cooldown / startup-skip policy aligned with current Reddit expectations, including `--noupdates`
  - [ ] Add settings/runtime bars before activating Feeds work:
    - feed-url validation does not block settings entry
    - empty/error replacements do not blank valid cached content
    - per-spawn caches stay isolated
    - manual refresh and cooldown behavior match the intended user contract
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
- Active geometry audit: `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md`
- Bubble preset/runtime audit: `audits/BubbleAudit/Bubble_Preset_Runtime_Audit.md`
- Bubble historical audit reference: `audits/BubbleAudit/Bubble_End_To_End_Audit.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
No unintegrated user tasks.
----
######
