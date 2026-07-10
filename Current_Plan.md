# Current Plan

Last updated: 2026-07-10

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, `Docs/Historical_Bugs.md`, and `Docs/Harness_Index.md`.
- Prune validated work aggressively. This is not a changelog.
- Prefer automation bars over repeated runtime-verification asks.
- Fallbacks must stay loud and routed through the relevant CLI family; a fallback is evidence, not success.
- UI pressure is barred as a perf fix. Do not add repaint/update requeue loops, rescue timers, or broad UI refreshes to chase FPS.
- Fullscreen / one-pixel shrink / startup-flash behavior is frozen at last committed behavior unless explicitly greenlit through a document-first audit.
- Before touching shared visualizer/audio/activation/render/transition seams, run the focused visualizer reactivity lock from `Docs/Harness_Index.md`.

## Active Tasks

### Blob Normal / Shaped Architecture Split, Dev-Gated

- [ ] Establish one explicit, preset-owned Blob type contract (`normal` / `shaped`) with forward migration from the legacy shaper toggle and clean replace semantics across defaults, model, snapshot normalization, curated/custom presets, import/export, startup, and hot preset switching.
- [ ] Split Blob settings construction and binding into shared appearance/layout controls plus dedicated Normal Blob and Shaped Blob custom builders; expose the Blob type as the high-level choice and show only the selected type's controls.
- [ ] Split Blob runtime ownership into dedicated Normal and Shaped render paths and shaders while keeping shared audio, activation, overlay cadence, and healthy visualizer modes neutral and unchanged.
- [ ] Rebuild Normal Blob around the older organic contract: constant living wobble plus music-reactive wobble/tendril extension, bounded inward motion that never reveals a raw circle or deep pinch, smooth release, and visibly reactive inner paint.
- [ ] Rebuild Shaped Blob around authored-contour fidelity plus bounded music-reactive wobble, local deviations, and moderate mutations that return cleanly to the goal shape.
- [ ] Reset subtype-owned solver/profile/ghost state at activation and Blob-type boundaries so startup, settings refresh, curated preset apply, custom preset apply, and runtime cycling cannot inherit the other Blob type's state.
- [ ] Add preset/model/UI/runtime/shader regressions and authored synthetic-audio oracles for both Blob types; run the pre/post current-good visualizer lock, focused Blob suite, preset audit, defaults parity, and documentation drift pass.

### Steam Achievement Pulse Promotion; Prototype Cards Dev-Gated

- [ ] In a fresh compiled run without `--devsteam`, verify saved identity/API-key status stays green on every Steam Settings reopen and cached Achievement Pulse content appears before the coordinated fade without a connect-required flash.
- [ ] Validate wide artwork plus the 140px-default/190px-maximum header-aligned square cover-filled portrait artwork with Unlocked centered below it, artwork-off mode, font-family changes, one-to-five unprefixed latest unlocks, cached bracketed names beside recent-game choices without selection-signal churn, Previous-field toggling, colon-free compact capsules, centred measured double-capsule headings (`PREVIOUSLY` for Previous), alpha-capable capsule fill/border swatches, and bottom-anchored whole-rail fields at authored size plus narrow/tall multi-monitor `Custom` geometry.
- [ ] Validate the 5-minute minimum/10-minute default freshness window against a real Steam account, `--noupdates`, transitions, manual refresh, and an unauthorized/stale-cache branch without exposing credentials in logs; confirm a multi-display `--steam` startup emits one provider batch per profile/cache namespace/selection rather than one batch per overlay.
- [ ] In a separate `--devsteam` run, confirm only Steam Journey, Friend Pulse, and Abandonment Issues become visible and remain disabled/provider-inert by default.

## Watchlist

- [ ] Performance cadence: preserve fresh evidence if Display 0 falls into a suspicious near-60 visible cadence, Display 1 into near-40 under-delivery, or the parser reports paint starvation, overlay under-delivery, swap-interval warnings, shader/cache fallbacks, or repeated app-shared `AnimationManager` under-target windows with actionable `active_labels`.
- [ ] Visualizer timing: if `--viz` logs show slow `_on_tick` phase breakdowns, fix the named owner directly; if only tick gaps appear, treat it as event-loop/timer delivery pressure rather than visualizer work.
- [ ] Reddit cadence: in the next long compiled run, confirm both widgets fire near due cadence, sparse HTML does not become the repeated primary source after partial rescue, and failed/empty chains do not freshen cache timestamps.
- [ ] Visualizer CUSTOM geometry route repair: reopen only if fresh logs show repeated bucket repair, duplicate-owner fallback, requested-monitor fallback, replay-green/runtime-wrong geometry, or settings-return suppression/stranding.
- [ ] Display wake / monitor recreate: keep the latest behavior accepted unless black-background recovery, missing compositor surfaces, duplicate displays, or placeholder truth returns.
- [ ] Settings runtime restart: reopen only if deleted Qt wrapper errors, stale background hydration, or settings-exit runtime bleed returns in `--set` / main logs.
- [ ] Sources / RSS reset: validate that "Just Make It Work" preserves existing RSS cache, emits one deferred source-change during settings, and settings exit performs only one clean source/RSS initialization without stranding media or visualizer.
- [ ] Non-`Custom` authored stacking: default-on for new users; re-audit with `--geo` only if authored-layout collision behavior reopens.
- [ ] Oscilloscope, Spectrum, Sine Waves, Bubble, and Dev Curve: accepted current behavior. Reopen mode-owned work only with fresh `--viz` evidence.
- [ ] Media metadata preservation during live visualizer preset churn: if it reopens, first suspect partial same-track playback snapshots during visualizer-only settings writes.
- [ ] Steam Journey, Friend Pulse, and Abandonment Issues remain production-hidden until each is explicitly promoted beyond `--devsteam`.

## Deferred / Not Active

- [ ] Feeds widget family architecture track:
  - [ ] Keep Reddit as its own branded widget and shared runtime owner; do not replace it with Feeds.
  - [ ] Extract reusable list-feed seams from Reddit without changing Reddit UX first.
  - [ ] Design Feeds as an additional widget family with isolated per-spawn source/cache/settings contracts.
  - [ ] Prefer official/feed-native sources and avoid HTML scraping/session automation by default; Reddit HTML is the explicit paced exception because Reddit's structured public endpoints are fragile.
- Dynamic Volume Floor follow-up stays deferred.
- Startup update-policy observability stays deferred behind current runtime-health priorities.
- Secure-desktop long-runtime exit reliability stays deferred.

## Documentation Rule

- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
- Runtime health audit: `audits/ArchitectureAudit/Project_Health_Audit.md`
- Historical geometry audit: `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md` when geometry/runtime replay issues reopen
- Bubble preset/runtime audit: `audits/BubbleAudit/Bubble_Preset_Runtime_Audit.md` as historical authored-setting reference
- Bubble historical audit reference: `audits/BubbleAudit/Bubble_End_To_End_Audit.md`
- Oscilloscope visual/reactivity audit: `audits/OscilloscopeAudit/Oscilloscope_End_To_End_Audit.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
1. Rename Defaults Widget Tab section in settings to "General", be careful not to catch the word default/defaults from the rest of the project accidentally while doing this, it is a very common word, which is why we are changing it.
1.1 In the new general add a Clear Caches button or Checkbox selection with button confirmation. The user would be able to specifically choose which caches to clear.
1.2 Assess feasability of adding "Shadow Direction" with a arrow like grid GUI (much like photoshops resize arrows in canvas resize look) where users can click one of 8 cardinal directions and change the general shadow direction of all our widgets/their backdrops to face a certain direction. The button would be inset to show which direction is chosen. Default is how we are now with bottom right aimed shadows. All other directions would use current settings adjusted for that direction relatively.
1.3. Bucket the General section as you go to avoid messes.
2. Measure logs drift idle vs drift soft-passages vs drift loud-passages to make sure there is an actual noticible increase in drift with loudest passages and minimal during idle. Use any logs and collect evidence about this.
----
######
