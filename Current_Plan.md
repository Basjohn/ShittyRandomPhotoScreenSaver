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
  - [ ] Treat `Preset 13 (Deep Sea Hero Lift)` as the current golden debug preset for loud-path Bubble runtime/bar work until the loud-collapse family is truly closed.
  - [ ] Lock the next Bubble runtime-shaped bars to the current `Preset 13` authored truth on the difficult song family and fail if:
    - hot sustained sections still look less broadly alive than softer sections
    - small-lane participation collapses while hero/big bubbles stay comparatively healthy
    - louder windows only gain spike/speed character without materially gaining visible body openness
  - [ ] Treat Bubble-authored AGC / input / transient balance as the next first-class suspect before any more shared-floor or broad simulation rewrites:
    - `bubble_agc_strength`
    - `bubble_input_gain`
    - `bubble_transient_pulse_gain`
    - `bubble_transient_mix_bass`
    - `bubble_transient_mix_vocal`
    - `bubble_transient_clamp`
    - `bubble_sensitivity`
  - [ ] Use `audits/BubbleAudit/Bubble_Preset_Runtime_Audit.md` as historical authored context only; do not reopen the older preset experiment loop blindly now that the user-tuned `Preset 13` has become the real runtime oracle.
  - [ ] Reopen Bubble runtime code only if the stricter `Preset 13`-anchored bars still fail after the authored control balance is understood well enough to prove a code-owned seam remains.

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

- Reddit fetch, cooldown, identity, and API work stays deferred until the ban/API situation changes.
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
