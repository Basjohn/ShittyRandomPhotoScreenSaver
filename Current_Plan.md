# Current Plan

Last updated: 2026-07-12

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

### Blob Dynamic Morphology And Active-Mode Performance, Dev-Gated

- [ ] Use the 2026-07-12 live Blob/profile/performance logs to quantify the repeated-silhouette failure, vocal/tendril response, active-mode render cost, and any first-frame/type bleed without changing shared audio or another visualizer mode.
- [ ] Replace Mighty’s fixed recognizable basis with rounded Blob-owned mutations whose lobe count, width, reach, and local anchor family alter over time and musical events; keep vocal outline wobble independently visible, make tendrils grow/retract instead of orbit, and never reveal a circular support body or sharp radial cut.
- [ ] Give Shaped equivalent dynamic life beyond its authored goal through topology-preserving warps, local mutations, light tendrils, and vocal/transient contour wobble that return cleanly without merely scaling the same silhouette.
- [ ] Remove or cache redundant per-paint Blob contour work so Blob-active cadence and application responsiveness remain comparable to healthy visualizer modes, including multi-display/runtime refresh paths.
- [ ] Add final-profile sequence oracles that reject repeated silhouettes and size-only motion, measure vocal/event correlation plus morphology change at fixed angles, and pair them with Blob-focused perf bars, startup/settings/type-boundary checks, curated/Custom smoke coverage, and the unchanged current-good visualizer lock.

### Steam Abandonment Issues Production Runtime Bar

- [ ] In a fresh compiled run without `--devsteam`, enable Abandonment Issues and verify cached content appears before the first coordinated fade, Smart/Pinned/unknown-history states remain honest, cached library names populate without provider work, and explicit Refresh Steam Library gives gentle success/failure feedback.
- [ ] Run multi-display and long-idle passes with `--steam --perf --cache --set --geo --life`: confirm one shared owned-library request per 24-hour source window, recent games follow the shared freshness window, 30-minute rotation is cache-only/profile-synchronized, 15-minute/2-hour/2-unlock/26-week ranking changes rotate through several cached games without completion claims, and game/title/art changes use the sparse fade without a repaint burst, UI-thread stall, or DT spike.
- [ ] Validate portrait/wide/art-off, minimum/default/maximum portrait size, Guilt off/on/max, RGBA accent, every optional ledger-field combination, large fonts, high DPR, and narrow/tall multi-monitor `Custom` geometry without overlap, reflow, clipping, or committed-rect mutation.
- [ ] Exercise `--noupdates`, offline, unauthorized-with-valid-cache, disconnect, settings restart, frozen build, and non-repository cwd; cache must remain authoritative, failed sources must not freshen it, teardown must leave no Steam timer/task/resource warnings, and credentials/account data must remain absent from logs/exports/repo artifacts.

## Watchlist

- [ ] Performance cadence: preserve fresh evidence if Display 0 falls into a suspicious near-60 visible cadence, Display 1 into near-40 under-delivery, or the parser reports paint starvation, overlay under-delivery, swap-interval warnings, shader/cache fallbacks, or repeated app-shared `AnimationManager` under-target windows with actionable `active_labels`.
- [ ] Visualizer timing: if `--viz` logs show slow `_on_tick` phase breakdowns, fix the named owner directly; if only tick gaps appear, treat it as event-loop/timer delivery pressure rather than visualizer work.
- [ ] Reddit cadence: in the next long compiled run, confirm both widgets fire near due cadence, sparse HTML does not become the repeated primary source after partial rescue, and failed/empty chains do not freshen cache timestamps.
- [ ] Visualizer CUSTOM geometry route repair: reopen only if fresh logs show repeated bucket repair, duplicate-owner fallback, requested-monitor fallback, replay-green/runtime-wrong geometry, or settings-return suppression/stranding.
- [ ] Display wake / monitor recreate: keep the latest behavior accepted unless black-background recovery, missing compositor surfaces, duplicate displays, placeholder truth, or an exhausted per-display image-replacement warning returns. A worker-rejected first candidate should now recover that display within the same compute pass.
- [ ] Settings runtime restart: expected lazy-section omission must stay free of `blocked_save_from_unhydrated_section`; reopen only if that warning reflects a real direct unhydrated save, deleted Qt wrapper errors, stale background hydration, or settings-exit runtime bleed in `--set` / main logs.
- [ ] Sources / RSS reset: validate that "Just Make It Work" preserves existing RSS cache, emits one deferred source-change during settings, and settings exit performs only one clean source/RSS initialization without stranding media or visualizer.
- [ ] Non-`Custom` authored stacking: default-on for new users; re-audit with `--geo` only if authored-layout collision behavior reopens.
- [ ] Oscilloscope, Spectrum, Sine Waves, Bubble, and Dev Curve: accepted current behavior. Reopen mode-owned work only with fresh `--viz` evidence.
- [ ] Media metadata preservation during live visualizer preset churn: if it reopens, first suspect partial same-track playback snapshots during visualizer-only settings writes.
- [ ] Steam Journey and Friend Pulse remain production-hidden until each is explicitly promoted beyond `--devsteam`; Journey's next gate is editorial classification/noise/request-budget evidence, not transport discovery.

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
