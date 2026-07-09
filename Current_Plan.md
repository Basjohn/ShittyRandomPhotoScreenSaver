# Current Plan

Last updated: 2026-07-09

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

### Steam Widget Family, Dev-Gated Foundation

- [x] Foundation gates complete:
  - [x] `--devsteam` / `--steam` gate and sidecar routing are in place.
  - [x] Steam credentials use strict DPAPI-only storage with SST/settings secret stripping.
  - [x] Steam source feasibility is documented in `Docs/Steam_Data_Feasibility.md`.
  - [x] Phase 2 backend/cache scaffolding is fixture-safe, generation-aware, backoff-aware, and asset-cache guarded.
- [x] Phase 3 descriptor/default/settings skeleton:
  - [x] Four descriptor-owned factory/runtime/custom entries are hidden unless `--devsteam` is active.
  - [x] Canonical defaults exist for shared Steam preferences and all four disabled cards.
  - [x] The lazy Steam Settings shell builds bucketed Connection & Privacy plus four card buckets without credential/cache/provider work on general Settings open.
  - [x] Disabled mock cards create/reuse/remove through normal factory descriptors and `WidgetManager.setup_all_widgets`.
- [x] Phase 4 shared mock visual system:
  - [x] Shared Steam card painting/layout helpers are provider-, asset-, and timer-inert.
  - [x] Immutable mock card view models and fingerprints exist for all four cards.
  - [x] Deterministic render/layout bars cover normal, long-title, missing-artwork/placeholder, unavailable/private, tight `Custom`, and DPR cases.
  - [x] `Custom` rects uniformly scale authored card/elements and never decide visible-field count, rails, or content availability.
  - [x] Constructors, `paintEvent`, and Settings preview do no Steam provider/cache/asset/credential work.
- [x] Phase 5 Achievement Pulse cache/fixture slice:
  - [x] Resolve selected-app modes from fixture/cache records only: Most Recent, Recent #2-#5, and literal Custom app ID.
  - [x] Add selected-game achievement progress view-model mapping without provider calls from widget constructors or paint.
  - [x] Preserve unavailable/private/no-achievement states as literal card states, not substitute games.
  - [x] Keep shared Steam headers as bundled Steam logo + widget name, with widget styling still customizable through normal card settings.
  - [x] Add enabled-card connection states: no connection + no usable cache shows centered `Connect With Steam To Use` without mock-art/content placeholders; cache remains visible when the connection needs attention.
  - [x] Add optional default-on stale connection info icon, shown only for cached data at least 1 day stale and routed through the shared Settings request seam.
  - [x] Add cache-first fixture bars before any live Steam request path is connected.
- [ ] Steam family shell + user-facing connection prelude:
  - [ ] Add the outer bordered Steam family shell with the main `Enable Steam Widget` toggle so the section matches Gmail/Reddit bucket framing.
  - [ ] Keep the Connection & Privacy bucket as the first inner bucket and keep the account-connection affordance explicit before real-data Phase 6 work.
  - [ ] Keep the shell/configured flag separate from any future runtime master switch so card enablement remains the runtime authority.
- [ ] Steam OAuth/OpenID auth seam:
  - [ ] Decide whether the supported auth contract is OAuth, OpenID, or a narrower Steam identity/token seam.
  - [ ] Add the actual user-facing connection/disconnect flow and persisted credential/status contract.
  - [ ] Keep auth off constructors/paint and on the shared thread/service seams only.
- [ ] Steam Phase 6, Achievement Pulse real data hookup:
  - [ ] Connect the pure Achievement Pulse resolver to versioned Steam cache records without provider calls from constructors or paint.
  - [ ] Use shared service-widget/ThreadManager scheduling for any live refresh path; no private timers, raw `QTimer`, or UI-pressure retries.
  - [ ] Preserve cache-first fade behavior and stale-connection affordances during transition deferral/settings rebuilds.

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
- [ ] Steam widget family remains production-hidden until the user explicitly promotes it beyond `--devsteam`.

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
3. Long term deferred task. Split Blob within its own custom builder, wiring and shaders to have normal blob and shaped blob as high level options that change the entire blob worked with. It would need to be preset compatible. Normal blob would need to go back to similiar design of very old builds (~3.0) while maintaining improvements (like inner paint reactions - which is broken right now too). This would under no cirumstances effect the general audio/visualizer systems that are shared, completely isolated, adjusting the blobs to our architecture and not the other way around. Long term goal, extremely heavy planning and research required before considering or detailing further.
4. If not already present add support for .mp3 files in our email alert system (and general sound architecture) it is no longer as closed off as it used to be, turns out since 2017 we don't need lincences or ffmpeg for it in Python!
----
######
