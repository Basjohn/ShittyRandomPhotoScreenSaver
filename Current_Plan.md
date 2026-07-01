# Current Plan

Last updated: 2026-06-30

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, `Docs/Historical_Bugs.md`, and `Docs/Harness_Index.md`.
- Prune validated work aggressively. This is not a changelog.
- Prefer automation bars over repeated runtime-verification asks.
- Fallbacks must stay loud and routed through the relevant CLI family; a fallback is evidence, not success.
- UI pressure is barred as a perf fix. Do not add repaint/update requeue loops, rescue timers, or broad UI refreshes to chase FPS.
- Before touching shared visualizer/audio/activation/render/transition seams, run the focused visualizer reactivity lock from `Docs/Harness_Index.md`. `Spectrum`, `Sine Waves`, `Bubble`, `Dev Curve`, and `Oscilloscope` currently have accepted runtime behavior and must not be retuned from stale broad-suite failures.

## Active Tasks

### 1. Settings Qt Lifetime Cleanup

- [x] Preserve the latest evidence bundle at `.tmp/perf_settings_evidence_20260630_020535`.
- [x] Root-cause the current settings error shape: `NoWheelSlider` kept a Python weakref to a wrapper whose C++ object could already be deleted, then called `setProperty` / `style()` on it.
- [x] Add a regression bar proving stale `NoWheelSlider` wrappers are not touched and cannot remain the highlighted slider.
- [x] Fix the `NoWheelSlider` last-moved tracker to validate Qt object liveness before touching or storing wrappers.
- [ ] Runtime-check the next `--set` / main log for no `Internal C++ object (NoWheelSlider) already deleted` during settings open/close and slider movement.
- [ ] If another deleted-wrapper family appears, root-cause the owner/lifetime seam instead of catching broad `RuntimeError`.

### 2. Paint-Delivery Performance Recovery

- [x] Preserve latest honest-paint evidence at `.tmp/perf_settings_evidence_20260630_020535`.
- [x] Keep PERF HUD / parser paint-authoritative: `GL PAINT` is the visible cadence signal; `GL RENDER` and `GL ANIM` are supporting diagnostics.
- [x] Classify current evidence without over-closing it: latest logs show healthy `GL RENDER` near target while `GL PAINT` under-delivers, with Display 0 Raindrops visible paint around `82-89fps` against a `165Hz` target and no high-refresh near-60 collapse in this run.
- [ ] Keep rare `60/40` collapse deferred/watchlist until more post-compositor-rewrite evidence accumulates; do not close it, but treat the current run as paint-starvation evidence rather than the exact old collapse signature.
- [ ] Strengthen the perf parser only where it can prove a wrong behavior: healthy render timer plus poor paint delivery, stable-divisor paint cadence, settings/edit/display lifecycle correlation, and fallback reliance.
- [x] Promote settings UI stalls above 1s to first-class parser anomalies so `--perf` captures settings/build cost instead of burying it in timeline output.
- [ ] Investigate paint-delivery under-target from root seams only: `QOpenGLWidget.update()` consumption, pending-flag lifecycle, compositor/display rebuild boundaries, texture/cache upload timing, settings UI event-loop stalls, and visualizer tick payload.
- [ ] Do not alter visual fidelity, transition identity, first-frame/last-frame behavior, or visualizer reactivity to gain FPS.
- [ ] Run the focused visualizer lock before and after any shared render/tick/transition change.

### 3. Settings UI Cost And Churn

- [ ] Correlate settings open/close with frame-budget spikes, `AnimationManager` windows, visualizer tick spikes, display clear/recreate, and paint under-delivery using `--set`, `--life`, and `--perf`.
- [x] Add settings-hydration cancellation bars so delayed hidden-tab builds cannot run after settings close and bleed UI work into runtime restart.
- [x] Stop building the dev-gated Blob visualizer settings UI when Blob is not available in the mode registry.
- [x] Add granular `--set` / perf timing for Visualizers section build/load steps so future logs identify the expensive mode panel instead of only reporting `lazy_build_subtab_3`.
- [x] Rename WidgetsTab lazy-build perf labels to include the descriptor section id, e.g. `lazy_build_subtab_3:visualizers`.
- [x] Align WidgetsTab tests with current descriptor ownership: visualizer save/load routes through `visualizers`, while dev-gated Blob UI tests opt into the Blob gate deliberately.
- [ ] Audit any settings-time event storms or long-running dialog work that can continue into runtime; fixes must preserve persistence, buckets, scroll position, and lazy-build contracts.
- [ ] Keep WidgetsTab builders/loaders cheap and UI-focused. Backend/cache/auth probes must stay deferred or explicit.
- [ ] If fresh `--set` evidence still shows Visualizers section stalls, use the new per-mode timing to decide whether mode-panel lazy construction is worth the complexity; current logs still show explicit Visualizers builds at about `1.1-1.38s`, while later settings opens not visiting Visualizers are much cheaper at about `325-334ms`.
- [ ] Add or extend a harness only when it can fail on measurable churn, stale background hydration, or deleted-wrapper callbacks.

### 4. Reddit Candidate Cache And Refresh Cadence

- [x] Preserve the latest Reddit/visualizer/perf evidence at `.tmp/reddit_visualizer_route_perf_evidence_20260630_120708`.
- [x] Retire the old timed cache-growth reveal: Reddit now fetches/caches the fixed `25`-post candidate window and immediately displays the configured visible count from that candidate pool.
- [x] Consolidate automatic/manual startup cadence around terminal refresh chains: due horizons move only after success through a source or after all sources fail, not when a timer merely fires or a fetch is only attempted.
- [x] Keep both widgets eligible when stale: `reddit` may fire immediately, `reddit2` uses a small `30s` stagger, and settings/edit rebuilds reattach to existing per-cache-key due state instead of restarting it.
- [x] Make manual refresh useful without hammering: the spiral uses a `3min` manual gate, can bypass the longer blocked gate after that window, and does not push the automatic `15min` due unless the chain reaches a terminal outcome.
- [x] Rebuild provider fallback as a bounded source chain: session/configured source first, then `old.reddit.com/r/<subreddit>/`, then `www.reddit.com/r/<subreddit>/`; successful `old`/`www` sources become the per-widget session primary.
- [x] Prevent false freshness: empty listings, filtered-empty rows, provider failures, blocked responses, and visible fallback display never rewrite the Reddit JSON cache or content timestamp.
- [x] Add/refresh Reddit bars for retired growth, candidate-window fetch/display split, preserved per-cache-key due, 30s paired startup stagger, terminal-only due advancement, `3min` manual retry windows, old-before-www fallback, session source promotion, bounded provider chains, empty-result cache mtime truth, and padded hour/day age labels.
- [ ] Runtime-watch the next long `--cache` run: stale `reddit` and `reddit2` should each log a source chain with started/succeeded/failed/terminal outcome, `old`/`www` success should promote for the session, and no failed/empty chain should freshen the content cache timestamp.
- [ ] Treat any future `403`/`429` after the bounded source chain as a pacing/provider failure to investigate; the cooldown gate is a loud safety net, not a success state.

### 5. Visualizer CUSTOM Route Authority

- [x] Root-cause the latest wrong-display/top-left family as stale scalar route authority racing committed CUSTOM rect authority during settings/runtime recreate.
- [x] Recover a missing/stale CUSTOM visualizer monitor from a sole live saved visualizer rect before owner selection, rather than moving that rect to the stale requested monitor.
- [x] Refuse startup bucket repair when the sole saved visualizer rect belongs to another active display; allow only stale inactive signature repair for same-monitor display-signature drift.
- [x] Add route/rect bars for live-foreign refusal, stale-signature repair, and Custom+ALL route recovery from exact saved layout evidence.
- [ ] Runtime-watch next `--geo` / `--life`: no settings-exit visualizer destruction, no wrong-display recreate, and no bucket repair moving a rect away from an active display.
- [ ] If recovery still fires, treat the loud fallback as evidence of an upstream route/save owner bug and root-cause why scalar route and committed rect diverged.

### 6. Runtime Health Audit Follow-Through

- [ ] Continue executing the project-wide runtime health audit in `audits/ArchitectureAudit/Project_Health_Audit.md`, but keep `Current_Plan.md` limited to active next steps.
- [ ] Keep compositor/transition fallbacks clean: success must name the real shader/deferred path; failure must be loud, not a silent substitute.
- [ ] Keep cache/prescale fallback pressure loud through `--cache`; prefer worker/cache ownership fixes over UI-thread decode, scaling, or synchronous retry paths.
- [ ] Keep context-menu visualizer mode switching watchlisted until one sole-global CUSTOM visualizer case from the other display is runtime-checked.

## Watchlist

- Rare post-settings/edit performance collapse remains open but deferred: preserve future evidence where Display 0 falls into a suspicious near-60 visible cadence or Display 1 into near-40 under-delivery after settings/edit activity.
- Visualizer CUSTOM geometry route repair is watchlist unless fresh logs show repeated bucket repair, duplicate-owner fallback, requested-monitor fallback, replay-green/runtime-wrong geometry, or settings-return suppression/stranding.
- Non-`Custom` authored stacking is default-on for new users and should be re-audited with `--geo` if authored-layout collision behavior reopens.
- Oscilloscope visual/reactivity is watchlist only; reopen with fresh `--viz` evidence and keep fixes mode-owned unless a shared seam is proven.
- Media metadata preservation during live visualizer preset churn is watchlist; if it reopens, first suspect partial same-track playback snapshots during visualizer-only settings writes.

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
- Historical geometry audit: `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md` when geometry/runtime replay issues reopen
- Runtime health audit: `audits/ArchitectureAudit/Project_Health_Audit.md`
- Bubble preset/runtime audit: `audits/BubbleAudit/Bubble_Preset_Runtime_Audit.md` as historical authored-setting reference
- Bubble historical audit reference: `audits/BubbleAudit/Bubble_End_To_End_Audit.md`
- Oscilloscope visual/reactivity audit: `audits/OscilloscopeAudit/Oscilloscope_End_To_End_Audit.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
No unintegrated user tasks.
----
######
