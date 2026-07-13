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

- [ ] Run a fresh `-devblob --viz --perf` pass through temporary presets 5-8 and Custom: Mighty must show one-to-three broad lifecycle limbs that visibly grow, hold, retract to zero, and reappear at new hidden-retargeted sites without a fixed splat, orbit, flicker, circular fallback, or sharp groove; vocal contour motion must remain independently visible.
- [ ] In the same pass, verify Shaped Filled retains its authored goal inside the filled-only soft bounds while still mutating, and Shaped Ring keeps the wider negative-space warps, light migrating tendrils, and vocal/transient contour wobble that made Ring the stronger live reference.
- [ ] Confirm fresh `[BLOB_PROFILE]` transport telemetry stays near the bounded 30 Hz contour cadence while tendril display transport follows every coherent handoff, target/display lane counts remain sparse, per-step reach/angle deltas stay bounded, and Blob-active paint/tick cadence remains comparable to healthy modes on all displays.
- [ ] Exercise startup, settings close, subtype switches, preset cycling, and reset: require current-generation authority after any expected primer, no Mighty/Shaped geometry inheritance, no fallback/first-frame poison, and unchanged Bubble/Spectrum/shared-audio behavior.
- [ ] After the live visual gate passes, rerun the Blob architecture/UI/preset locks plus the current-good visualizer lock, then prune this task instead of retaining implementation history here.

### Steam Abandonment Issues Production Runtime Bar

- [ ] In a fresh compiled run without `--devsteam`, enable Abandonment Issues and verify cached content appears before the first coordinated fade, Smart/Pinned/unknown-history states remain honest, cached library names populate without provider work, and explicit Refresh Steam Library gives gentle success/failure feedback.
- [ ] Run multi-display and long-idle passes with `--steam --perf --cache --set --geo --life`: confirm one shared owned-library request per 24-hour source window, recent games follow the shared freshness window, 30-minute rotation is cache-only/profile-synchronized, 15-minute/2-hour/2-unlock/26-week ranking changes rotate through several cached games without completion claims, and game/title/art changes use the sparse fade without a repaint burst, UI-thread stall, or DT spike.
- [ ] Validate portrait/wide/art-off, minimum/default/maximum portrait size, Guilt off/on/max, RGBA accent, rediscovery message off/on plus a longest alternate staying fitted and stable across displays/rebuilds, every optional ledger-field combination, large fonts, high DPR, and narrow/tall multi-monitor `Custom` geometry without overlap, reflow, clipping, or committed-rect mutation.
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
