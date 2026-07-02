# Current Plan

Last updated: 2026-07-02

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, `Docs/Historical_Bugs.md`, and `Docs/Harness_Index.md`.
- Prune validated work aggressively. This is not a changelog.
- Prefer automation bars over repeated runtime-verification asks.
- Fallbacks must stay loud and routed through the relevant CLI family; a fallback is evidence, not success.
- UI pressure is barred as a perf fix. Do not add repaint/update requeue loops, rescue timers, or broad UI refreshes to chase FPS.
- Fullscreen / one-pixel shrink / startup-flash behavior is frozen at last committed behavior unless explicitly greenlit through a document-first audit. Perf work must not touch fullscreen sizing, taskbar coverage, compositor prewarm visibility, first-frame readiness, or startup presentation ordering opportunistically.
- Before touching shared visualizer/audio/activation/render/transition seams, run the focused visualizer reactivity lock from `Docs/Harness_Index.md`. `Spectrum`, `Sine Waves`, `Bubble`, `Dev Curve`, and `Oscilloscope` currently have accepted runtime behavior and must not be retuned from stale broad-suite failures.

## Active Tasks

### 1. Paint-Delivery Performance Recovery

- [x] Keep PERF HUD / parser paint-authoritative: `GL PAINT` is the visible cadence signal; `GL RENDER`, `GL ANIM`, and `pending_skips` are supporting diagnostics.
- [x] Preserve representative evidence for the old collapse family and current under-delivery family under `.tmp/`; do not keep every repeated runtime log.
- [x] Latest parse (`2026-07-02 13:26-13:30`) shows no near-60 high-refresh collapse, no stable-divisor windows, no swap-interval warnings, no shader/cache fallbacks, no slow texture uploads, and no pending-paint requeues.
- [x] Latest remaining evidence is shared paint delivery pressure: five healthy-render / weak-paint windows on Display 0, 20 render pending-skip metric windows, 26 Spotify visualizer tick warnings, and two settings hydration stalls.
- [x] Reduce paint-path UI pressure without changing fidelity: transition paint dispatch resolves the active transition only, diagnostic section timing is sampled, and PERF HUD image caching now avoids repeated payload/profiler scans inside the refresh window.
- [ ] Root-cause the visualizer-existence / owner-display performance effect. Latest short log (`2026-07-02 14:41-14:42`) starts with Bubble visualizer on Display 0 and stays good (`GL PAINT` screen 0 `148.8fps` on 165Hz, no paint-starvation window), matching the prior post-move `147-151fps` band; this points away from CUSTOM transfer and toward the child `SpotifyBarsGLOverlay` / same-window GL paint topology.
- [ ] Isolate whether Display 0 improves because the visualizer child GL overlay is present in the Display 0 top-level, because Display 1 no longer owns that self-driving overlay, or because compositor update delivery is accidentally helped by same-window child GL activity.
- [ ] Inspect visualizer tick payload / overlay handoff (`push_spotify_visualizer_frame`, `SpotifyBarsGLOverlay.set_state`, `SpotifyBarsGLOverlay.paintGL`) for unnecessary per-tick copies, geometry churn, or continuous repaint ownership that can be reduced without changing mode behavior, reactivity, first-frame safety, or adding UI pressure.
- [ ] Improve perf attribution for accepted-update-to-paint delivery latency only if it separates compositor timer delivery from visualizer child-GL delivery; keep it metrics-only and avoid retry/repaint loops.
- [ ] Investigate recurring collateral pressure clues if they persist: Spotify visualizer tick spikes during transitions and isolated MediaWidget timer gaps.
- [ ] Use the next broad multi-transition runtime log to compare transition families, but keep the primary hypothesis display/visualizer-topology-wide. Do not blame any single transition from a run that only exercised that transition.
- [ ] If ThreadManager callback errors recur, use the new traceback/context fields to fix the source callback directly rather than adding defensive broad retries.
- [ ] Continue raw `QTimer.singleShot` removal only where it is adjacent to compositor/display/widget startup, settings restart, visualizer reveal, or first-frame readiness. Cosmetic/UI-local one-shots belong in `Future_Cleanup.md` unless fresh logs promote them.
- [ ] Keep the legacy [rendering/render_strategy.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/rendering/render_strategy.py) busy-wait timer classified as cleanup/dead-code risk unless a live import/caller appears.
- [ ] Do not alter visual fidelity, transition identity, first-frame/last-frame behavior, or visualizer reactivity to gain FPS.
- [ ] Add or improve a perf parser/bar only if it directly separates visualizer-present-on-screen-0, visualizer-present-on-screen-1, and no-visualizer cases without requiring new runtime UI pressure or new runtime controls.
- [x] Run the focused visualizer lock for the adaptive-timer cadence split; keep this as a recurring guardrail for the next shared render/tick/transition change.

### 2. Display Wake / Monitor Recreate First-Frame Resilience

- [x] Treat black-background-on-wake as a display lifecycle ownership problem, not a repaint/retry-loop problem.
- [x] Fix monitor hotplug ownership so `DisplayManager` only detects/emits `monitors_changed`; `ScreensaverEngine` owns cleanup, rebuild, and current-image redisplay.
- [x] Detach the old display manager from `screenAdded` / `screenRemoved` before replacing it during a monitor-change rebuild.
- [x] Add bars proving screen add/remove cannot both emit engine rebuild and mutate display widgets locally, and that engine monitor-change rebuild detaches/cleans/reinitializes/redisplays in order.
- [x] Replace count-only hotplug gates with coalesced screen-signature reconciliation so same-count display wake/topology swaps still rebuild after the Qt/Windows event burst settles.
- [x] Add a disconnected-manager guard so pending monitor reconciles from replaced display managers cannot emit zombie rebuilds.
- [x] Wire `monitors_changed` in the `DisplayManager` creation/rebuild lifecycle so replacement managers still notify `ScreensaverEngine`; keep `_subscribe_to_events()` from adding duplicate monitor rebuild subscriptions.
- [x] Remove `QTimer.singleShot` fallback paths from display lifecycle code; monitor reconcile and related foreground nudges now use `ThreadManager.single_shot` or fail loudly.
- [x] Fence creator-time visualizer CUSTOM route recovery during reduced live topology so an explicit monitor route is not rewritten to the sole temporary display.
- [x] Add a generation-scoped display startup readiness barrier: current-image replay after monitor rebuild waits until every current-generation display has completed show/setup, and stale delayed shows cannot satisfy a newer generation.
- [x] Replace first-frame readiness `QTimer.singleShot(0)` plus forced `repaint()` with a ThreadManager-owned handoff; keep normal paint scheduling only.
- [x] Add bars for staggered display readiness, stale monitor rebuild replay ordering, and no display startup `QTimer.singleShot` / forced repaint paths.
- [x] Runtime-check display off/on recovery: latest logs show recovery is acceptable and no duplicate/orphan display widgets or long-lived placeholder truth persisted.
- [ ] Leave the fullscreen/one-pixel/startup-flicker seam at the last committed behavior. If Display 1 startup flash or taskbar coverage reopens, make a fresh document-first audit and get explicit greenlight before touching fullscreen geometry, visible compositor prewarm, or readiness ordering again.

### 3. Settings UI Cost And Churn

- [x] Fix the `NoWheelSlider` deleted-wrapper family and add a stale-wrapper regression bar.
- [x] Add settings-hydration cancellation bars so delayed hidden-tab builds cannot run after settings close and bleed UI work into runtime restart.
- [x] Add granular `--set` / perf timing for Visualizers section build/load steps and descriptor section ids.
- [x] Route settings background hydration delays through the ThreadManager seam; remaining `QTimer.singleShot` settings sites are UI-local cleanup unless logs prove runtime impact.
- [ ] Runtime-check the next `--set` / main log for no `Internal C++ object (NoWheelSlider) already deleted` during settings open/close and slider movement.
- [ ] Correlate any remaining settings open/close stalls with frame-budget spikes, `AnimationManager` windows, visualizer tick spikes, display clear/recreate, and paint under-delivery using `--set`, `--life`, and `--perf`.
- [ ] Keep WidgetsTab builders/loaders cheap and UI-focused. Backend/cache/auth probes must stay deferred or explicit; if restored Widgets->Visualizers remains a measured 1s+ stall, optimize the Visualizers section internals rather than breaking restored-subtab hydration/persistence.
- [ ] Add or extend a harness only when it can fail on measurable churn, stale background hydration, or deleted-wrapper callbacks.

### 4. Reddit Candidate Cache And Refresh Cadence

- [x] Retire timed cache-growth reveal and keep the fixed `25`-post candidate window.
- [x] Consolidate automatic/manual startup cadence around terminal refresh chains: due horizons move only after success through a source or after all sources fail.
- [x] Keep both widgets eligible when stale: `reddit` may fire immediately, `reddit2` uses a `30s` stagger, and settings/edit rebuilds preserve per-cache-key due state.
- [x] Use bounded source chains: session/configured source first, then `old.reddit.com/r/<subreddit>/`, then `www.reddit.com/r/<subreddit>/`.
- [x] Prevent false freshness: failed/empty chains do not rewrite content timestamps.
- [x] Preserve provider metadata through transition-deferred refresh application so sparse HTML remains classified as sparse after the transition clears.
- [x] Harden sparse HTML merge against persisted-cache loss: `html_old` / `html_www` partial windows merge newer dated rows into the richer runtime or persisted candidate window instead of replacing it.
- [x] Add bars for persisted-cache sparse merge and transition-deferred sparse metadata preservation.
- [x] Prevent invalid Reddit timestamps from rendering as epoch-age labels such as `56Y AGO`; invalid/zero `created_utc` now displays no age instead of a fake ancient age.
- [ ] Runtime-watch one long compiled run for both widgets firing near due cadence, no repeated sparse-HTML primary preference after a partial rescue, and no failed/empty chain freshening the content timestamp.
- [ ] Treat any future `403`/`429` after the bounded source chain as a pacing/provider failure to investigate; the cooldown gate is a loud safety net, not a success state.

### 5. Runtime Health Audit Follow-Through

- [ ] Continue executing `audits/ArchitectureAudit/Project_Health_Audit.md`, but keep this plan limited to active next steps.
- [ ] Keep compositor/transition fallbacks clean: success must name the real shader/deferred path; failure must be loud, not a silent substitute.
- [ ] Keep cache/prescale fallback pressure loud through `--cache`; prefer worker/cache ownership fixes over UI-thread decode, scaling, or synchronous retry paths.
- [ ] Runtime-check the next `--cache` run for no startup/early zero-producer scaled fallback before reopening cache promotion, cancellation, or wakeup ownership.
- [ ] Continue authoritative delayed-work migration only where it removes real lifecycle/rebuild risk and has cancellation/coalescing bars; leave UI-local cosmetic one-shots alone.
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
