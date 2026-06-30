# Current Plan

Last updated: 2026-06-29

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. This is not a changelog.
- Prefer automation bars over repeated runtime-verification asks.
- Do not close visual/runtime bugs from polite unit doubles alone.
- Before touching shared visualizer/audio/activation/render/transition seams, protect the current-good modes with the visualizer reactivity lock in `Docs/Harness_Index.md`: `Spectrum`, `Sine Waves`, `Bubble`, `Dev Curve`, and the now-accepted `Oscilloscope` path must match their current accepted bars or the change stops.
- For visualizer geometry, treat these as separate seams until proven otherwise:
  - saved/custom rect authority
  - live widget rect authority
  - GL overlay rect authority
  - startup / prewarm / first-frame authority
  - mode-reset or preferred-height side effects
- A green `replay_final` log is necessary but not sufficient for visualizer geometry closure.
- Recovery paths are allowed only after the root-cause map and the stronger bars exist.

## Active Tasks

- [x] Refresh canonical project docs after the late-June runtime-health, geometry, visualizer, and widget-settings work
  - [x] Preserve the immediate perf/debug direction before the broader doc sweep: next runtime evidence should classify Display 0 paint under-delivery and Display 1 `GL ANIM` cadence with `owner=`, `listeners=`, `max_active=`, and `max_listeners=` instead of guessing from FPS alone
  - [x] Refresh `Index.md` as the live module map for current owners: display startup/rebuild, `AnimationManager` diagnostics, transition perf parser, visualizer audits/watchlists, widget guidelines, and Contracts routing
  - [x] Refresh `Spec.md` for current architecture truth: CLI-first diagnostics, loud fallbacks, no UI-pressure cadence fixes, display startup stagger via owned scheduling, current visualizer mode isolation, CUSTOM geometry authority, Reddit/Gmail capacity policy, and cache/prefetch ownership
  - [x] Refresh `Docs/Contracts.md` as the short routing layer for current seams: perf parser/evidence, display lifecycle, transition `FrameState`, visualizer activation/settings, CUSTOM layout, cache/prescale, Reddit provider/cadence, and widget settings descriptors
  - [x] Refresh `Docs/Guardrails.md` only where policy has materially changed or sharpened; do not turn it into a changelog
  - [x] Cross-check doc claims against current code/tests before finalizing, especially defaults/provider claims, visualizer mode/preset contracts, transition ownership, and settings/widget descriptor ownership

- [ ] Execute the project-wide runtime health audit in [audits/ArchitectureAudit/Project_Health_Audit.md](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/audits/ArchitectureAudit/Project_Health_Audit.md)
  - [x] Establish the visualizer reactivity lock before any shared visualizer/perf/lifecycle work
    - [x] Keep `Spectrum`, `Sine Waves`, `Bubble`, `Dev Curve`, and `Oscilloscope` green against the focused lock commands in [Docs/Harness_Index.md](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/Docs/Harness_Index.md)
    - [ ] Treat stale Bubble oracle failures as oracle re-baseline work only; do not touch Bubble feel/reactivity unless fresh runtime evidence contradicts the accepted current behavior
    - [ ] Re-run the same lock after any change touching visualizer audio feeds, activation reset, overlay payloads, transition handoff, or shared tick/render plumbing
  - [ ] Audit widget lifecycle ownership and add parity bars before any broad activation-path migration
  - [x] Inventory and classify production raw `QTimer.singleShot(...)` callsites as authoritative delayed work vs UI-local one-shots
  - [ ] Migrate only the risky runtime-reconcile/stabilize shots after each target has token/cancellation ownership and a regression bar
    - [x] Move CUSTOM edit-shell global restack scheduling to `ThreadManager.single_shot(...)` with coalesce/menu-deferral bars
    - [x] Move `BaseOverlayWidget` CUSTOM geometry reapply scheduling to `ThreadManager.single_shot(...)` and guard against self-triggered reapply churn during authoritative correction
    - [x] Move `SpotifyVolumeWidget` CUSTOM geometry reapply scheduling to `ThreadManager.single_shot(...)` with coalescing so dependent-volume rect correction does not queue duplicate corrections
    - [x] Move `WidgetManager` deferred Spotify visibility sync to `ThreadManager.single_shot(...)` with a coalescing bar
    - [ ] Audit remaining visualizer/volume reveal-stage retry shots only with owner-thread and no-first-frame-poisoning bars
  - [ ] Audit bounded compositor / GL churn-reduction opportunities before any broad FBO/render-target experiment:
    - reduce expensive framebuffer-grab prewarm fallbacks where safe
    - verify first-frame and transition warmup parity with stronger bars
    - document or retire viewport/DPR hacks only with proof
    - [x] Make active shader-path fallback logs loud, bounded, and reason-bearing instead of repeating blind per-frame errors
    - [x] Refuse Rain Drops cleanly when its shader/compositor path cannot start; do not report a legacy diffuse substitute as a successful transition
    - [x] Fix the deferred/desynced transition-start contract so a delayed compositor start returns a deferred token instead of `None`, preventing real delayed Rain Drops starts from being misreported as refused failures
    - [x] Replace the stale handwritten compositor-prewarm widget raise list with the owner-based runtime-widget raise helper
    - [x] Runtime-check the next `--perf` / transition log for Rain Drops/Diffuse failures: latest logs show named shader starts and no silent substitute/refusal path
    - [ ] Keep Rain Drops/Diffuse failure semantics clean if this path reopens: success must name the real shader path or deferred start, and failure must be loud rather than silently substituting another transition
  - [ ] Root-cause transition paint-delivery collapse without degrading visual fidelity, first-frame correctness, or visualizer feel
    - [x] Lock in the failed pending-paint requeue lesson: parser stays red for requeue rescues, production must not queue extra UI work to force cadence
    - [x] Strengthen [tools/transition_perf_health_parser.py](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/tools/transition_perf_health_parser.py) to flag paired starvation where `GL RENDER` is healthy but same-screen/same-target `GL PAINT` under-delivers
    - [x] Add parser timeline markers for settings stalls, edit saves, display lifecycle churn, frame-budget spikes, visualizer tick spikes, slow texture uploads, cache fallbacks, shader fallbacks, and pending-paint rescues
    - [x] Add passive adaptive-timer observability for stale pending paint updates with `no_requeue=True`; do not add any repaint/update retry path
    - [x] Split paint-time transition progress sync into its own `GL PAINT` section metric so future logs can prove whether interpolation sync is a real hot-path cost
    - [x] Runtime-check the adaptive-timer GIL-spin fix against commit `40562fe`: post-fix logs recovered the broad regression and removed pending-paint requeues/shader fallbacks, but newer preserved evidence still shows rarer high-refresh near-60 / divisor-like collapse that remains active below
    - [x] Separate the latest collapse into two log-backed seams: early `GL RENDER` healthy / `GL PAINT` starved windows, and later `GL ANIM` control-callback cadence near `60fps` while paint-time interpolation still delivers higher visual paint cadence
    - [x] Remove the adaptive render timer's Python busy-spin deadline tail so high-refresh timing no longer monopolizes the GIL while Qt paint/event-loop delivery is trying to consume queued updates
    - [x] Fix the exit-stall/orphan-timer seam where a late compositor lazy animation callback or delayed/desynced transition starter could start an adaptive timer after `stop_rendering()` / display teardown had already invalidated that transition
    - [x] Runtime-check the next `--life` / `--perf` run for no `ThreadManager shutdown timed out` adaptive-timer tasks, no late `Internal C++ object (GLCompositorWidget) already deleted` transition-complete callbacks, and no post-stop adaptive frame signalling
    - [x] Preserve the latest post-`FrameState` collapse evidence under `.tmp/perf_collapse_evidence_20260628_164113/20260629_154319_post_framestate_collapse`
    - [x] Classify the newest evidence without over-reading it: no pending-paint requeues, shader fallbacks, cache fallbacks, CUSTOM suppression, or slow GL uploads appear; Display 0 still shows render-healthy/paint-under-delivered windows, while Display 1's suspicious `~40fps` signature is `GL ANIM` / control-callback cadence rather than visible `GL PAINT` in this run
    - [x] Remove settings/edit display-rebuild `processEvents()` pumps from the active seams while preserving display startup stagger through owned `ThreadManager.single_shot(...)` scheduling and stale-generation suppression
    - [x] Tag app-shared, settings-dialog, config-dialog, and display-local `AnimationManager` owners so the next `--perf` run can distinguish real display managers from shared/settings cadence sources
    - [x] Extend `AnimationManager` perf metrics and parser bars with peak active/listener counts so completed transitions are not misread as idle timer churn, and true no-work timer churn can fail loudly
    - [x] Correlate the newest paired starvation windows with settings open/close, display clear/recreate, frame-budget spikes, visualizer tick spikes, slow texture uploads, and AnimationManager owner/listener cadence using the parser timeline
    - [x] Preserve the newest collapse evidence under `.tmp/perf_collapse_evidence_20260628_164113/20260629_211259_user_extensive_60_40_collapse`
    - [x] Classify the newest collapse without over-reading literal FPS labels: Display 0 `GL RENDER` stays near `165Hz`, `GL PAINT` under-delivers around `80-96fps`, and later Display 0 `GL ANIM` / compositor-control cadence falls near `63fps`; Display 1 `GL PAINT` can remain near `60Hz` while `GL ANIM` and its display-local `AnimationManager` fall into a stable `~40fps` lane with `max_listeners=1`
    - [x] Remove the transition-start dependency on the first `AnimationManager` callback: compositor paint metrics, animation metrics, and render strategy now start at transition start so `FrameState` paint authority is not gated by a sick callback cadence
    - [x] Decouple Spotify visualizer ticks from transition `AnimationManager` listeners: visualizer work stays on its owned tick source during transitions and can no longer run full `_on_tick()` inside the transition progress manager
    - [ ] Runtime-check the next `--perf --life --set --viz` run for no Display 1 transition `AnimationManager` windows with `max_listeners=1`, no stable `~40fps` display-local `GL ANIM` lane, and whether Display 0 paint under-delivery remains after render wake-up no longer waits for first animation callback
    - [ ] Root-cause any remaining Qt/GL paint delivery under-delivery while render timers remain at target; inspect update consumption, pending-flag lifecycle, compositor/widget lifecycle churn, display-specific refresh target state, and event-loop stalls
    - [x] Classify `GL ANIM` cadence separately from visible paint cadence before changing timers: latest evidence shows the exact `60/40` signature is primarily control-callback cadence, while visible `GL PAINT` under-delivery is a separate remaining seam
    - [x] Add a display-local AnimationManager bar proving mixed-refresh transition widgets do not retarget each other's transition managers
    - [x] Strengthen the perf parser so long completed `AnimationManager` under-target runs stay red even when `active_count=0`; short idle post-completion samples remain allowed
    - [x] Add passive `AnimationManager` listener-count logging so the next `--perf` run can prove whether visualizer tick listeners are attached during suspicious `GL ANIM` cadence collapse
    - [x] Fix the settings-dialog local animation/timer ownership leak: dialog-owned `AnimationManager` is cleaned before runtime restart, and delayed background tab hydration cancels at close instead of waking during runtime
    - [x] Fix the display-local transition `AnimationManager` ownership break: image handoff no longer nulls the manager before `TransitionController.stop_current()` can cancel it, display shutdown explicitly releases the manager, and `--perf` summaries now include manager id/owner for future leakage vs delivery-starvation classification
    - [x] Add bars proving image handoff preserves manager ownership through controller stop and mixed-refresh transition managers remain display-local
    - [x] Root-cause the visible-progress coupling: `FrameState` paint interpolation was still sample-stream-tethered, so a low-cadence `AnimationManager` callback stream could cap shader-visible progress even when the render timer was healthy
    - [x] Move `FrameState` paint reads to an elapsed-time/easing timeline while leaving `AnimationManager` as the completion/callback owner; this avoids repaint retries and keeps first-frame/delay behavior explicit
    - [x] Add a `FrameState` bar proving paint-time progress outruns stale samples without advancing before an authored delay
    - [x] Preserve the newest settings-return collapse evidence under `.tmp/perf_collapse_evidence_20260628_164113/20260629_214034_settings_return_60_40_collapse`
    - [x] Classify the newest evidence without forcing one story onto all symptoms: deleted-C++ errors were not present in the saved sidecars, Display 0 still shows healthy `GL RENDER` with under-delivered `GL PAINT`, Display 1's suspicious `~40fps` lane is display-local transition/control cadence, and the old visualizer-listener seam is not present in this run (`max_listeners=0`)
    - [x] Remove compositor transition progress/completion from per-frame UI `AnimationManager` callbacks: transition progress is now paint-time `FrameState` authoritative, render wake starts at transition start, and completion is a single generation-guarded scheduled handoff
    - [x] Add lifecycle bars proving scheduled timeline completion is invalidated by `stop_rendering()` and does not call into deleted/stale compositors
    - [x] Harden delayed/desynced transition starts against deleted compositor wrappers: deferred starts now validate the target before touching it and stay covered by stop/deleted-object suppression bars
    - [x] Rework the frame-timing workload harness so it uses a production-shaped compositor parent with `_thread_manager`; keep steady-state cadence strict while recording cold first-run transition gaps as a separate signal
    - [ ] Runtime-check the next `--perf --life --set` run for no `GL ANIM` transition-progress windows on compositor shader transitions, no stable Display 1 `~40fps` transition-control lane, no late `GLCompositorWidget already deleted` completion callbacks, and whether Display 0 paint under-delivery remains when progress is no longer UI-timer driven
    - [ ] If fresh logs still show a visible `60/40` collapse after compositor transition timeline scheduling, classify each remaining bad window as `GL PAINT`, `GL RENDER`, visualizer tick, app-shared animation, settings-dialog work, texture upload, or display lifecycle churn before changing cadence code
    - [ ] Root-cause settings UI stalls around widget tab hydration (`~2.3s` class stalls in latest logs) without breaking settings persistence, buckets, or scroll persistence
    - [ ] Correlate slow GL texture uploads with image-cache warmup and display rebuild boundaries; prefer cache/prewarm ownership fixes over UI-thread upload retries
    - [ ] Root-cause the cold first-use transition-start gap exposed by `tests/test_frame_timing_workload.py`: resource warmup alone does not remove the first measured slide hole, so inspect adaptive timer thread start, first paint upload, and context warmup ownership without adding repaint/update rescues
    - [ ] Inspect visualizer tick-listener cadence separately from Bubble worker cost; Bubble compute is low in the latest collapse logs and must not be retuned for this perf task
    - [ ] Search for duplicate hidden visualizer owners, duplicate beat engines, extra worker loops, stale overlays, or uncollected visualizer resources before optimizing render paths
    - [ ] Treat current-good visualizer modes as locked: `Spectrum`, `Sine Waves`, `Bubble`, `Dev Curve`, and `Oscilloscope` must keep accepted behavior before and after any shared render/tick changes
    - [ ] Keep FPS work off the UI thread; root-cause cache/worker/timer ownership instead of adding synchronous decode, scaling, render retries, repaint loops, or update rescue timers
  - [ ] Close the reopened settings-return visualizer CUSTOM suppression seam
    - [x] Preserve the fresh evidence under `.tmp/perf_collapse_evidence_20260628_164113/20260629_0417_settings_return_collapse`
    - [x] Preserve the latest collapse/return evidence under `.tmp/perf_collapse_evidence_20260628_164113/20260629_143536_root_cause_latest`
    - [x] Classify the failure: settings return suppressed CUSTOM visualizer creation because the route pointed at monitor `2` but the only saved visualizer rect lived under a stale/foreign display bucket
    - [x] Add a narrow startup repair for exactly one stale visualizer rect when the requested concrete monitor is active and matches the current display
    - [x] Keep absent/ambiguous/wrong-monitor foreign rects rejected so duplicate-owner and wrong-display geometry bugs cannot return
    - [x] Add parser timeline markers for CUSTOM visualizer creation suppression and single-foreign-bucket repair
    - [x] Fix the root staged-startup registration split: visualizer self-registration now goes through the manager-owned secondary-stage wrapper, and runtime-pause/fade-reset invalidates stale registered generations so old starters cannot strand or hot-start the visualizer
    - [x] Add bars proving stale secondary-stage starters do not hot-start after runtime pause and stale visualizer registration re-registers with the live manager generation
    - [ ] Runtime-check next `--geo --perf --set --life` run: no normal settings return should suppress or strand the visualizer; at most one loud bucket repair may appear, and after it saves the exact bucket the warning should not repeat
  - [ ] Reduce image-cache/prescale fallback pressure without moving work onto the UI thread
    - [x] Runtime-validate the bounded raw-prefetch backlog: latest `--cache` logs show full preview coverage (`active=2 pending=3`, scaled `request_count=5 prepared=5`) instead of the old first-two-only skip.
    - [x] Add a parser/bar that fails the still-active fallback path where transition images miss the preview window entirely (`raw_inflight:0,raw_pending:0,scaled_inflight:0,scaled_pending:0`)
    - [x] Keep the delayed post-transition prefetch resume armed while another display still reports transition work pending, instead of consuming the resume and leaving no producers registered
    - [x] Preserve raw/scaled prefetch registration intent through post-transition cooldown without dispatching new work during the cooldown window
    - [x] Rearm transition-complete prefetch resume until the prefetcher cooldown has actually expired, avoiding the just-before-expiry lost-wakeup shape
    - [x] Root-cause the latest zero-producer fallback family to first scaled prefetch scheduling before display target sizes exist; first prefetch scheduling now runs after display creation, not during cache-prefetcher construction
    - [x] Add a lifecycle bar proving engine initialization orders cache construction, display creation, then first prefetch scheduling
    - [ ] Runtime-check the next `--cache` run for no startup/early `scaled_miss raw_missing` fallback with all producer counts at zero
    - [ ] If fresh logs still show zero-producer fallbacks after startup ordering, inspect cache promotion, cancellation, and worker wakeup ownership before closing the cache fallback track
    - [ ] Keep fallback logs loud through `--cache`; do not hide fallback usage by downgrading or moving warnings out of operator-visible logs
    - [ ] Prefer worker/cache ownership fixes over UI-thread decode, scaling, or synchronous retry paths
  - [ ] Split the visualizer suite into trustworthy gates before using it as a project health bar
    - [ ] Re-baseline Bubble oracle values against current accepted runtime feel only; do not touch Bubble reactivity or visuals for this task
    - [x] Run the focused current-good visualizer lock and keep it green before shared perf/cache/lifecycle edits
    - [x] Classify the broad visualizer suite separately: current-good lock is trusted, while stale Bubble expectations, old Sine UI doubles, exact-bucket settings tests, and obsolete doc-reference tests are re-baseline/test-debt work
    - [x] Fix the real broad-suite hard exception where `BubbleSimulation.tick(None, ...)` left pulse variables uninitialized
    - [x] Repair stale visualizer doc-reference bars so retired visualizer docs are not required as current truth
    - [x] Fix non-Bubble/test-fixture drift separately from Bubble, including Oscilloscope runtime push and tick-pipeline unit doubles
    - [x] Keep mode-switch overlay reuse contract covered: preserved overlay must be reset/hidden/blanked and target-mode reset before fresh-frame reveal
    - [x] Close Oscilloscope-specific bars for waveform response, ghost stability, idle/live boundaries, transient-width strobe, and media metadata preservation
    - [ ] Continue classifying remaining broad visualizer failures as stale tests vs real production bugs; do not change current-good runtime behavior from broad-suite proxy failures alone

- [ ] Make context-menu visualizer mode switching display-aware but globally helpful
  - [x] Prefer the visualizer owned by the display where the context menu was invoked
  - [x] If the invoking display owns none and exactly one visualizer exists globally, route the mode switch to that sole instance
  - [x] Refuse to guess when multiple visualizers exist, so the fix cannot reopen duplicate-owner drift
  - [ ] Runtime-check one sole-global CUSTOM visualizer case from the other display's context menu

- [ ] Restore Reddit's automatic periodic refresh cadence and observability
  - [x] Verify current code/logs: startup cache loads are visible, but periodic timer arm/fire evidence was too quiet to prove long-run updates
  - [x] Use a shared `15min` automatic cadence with a `reddit2` initial phase stagger instead of lengthening `reddit2`'s repeat interval forever
  - [x] Keep startup refresh gating independent from periodic/manual refresh; a skipped startup fetch must still arm the recurring timer
  - [x] Log periodic timer arm/start/fire through `[CACHE][REDDIT]` so future `--cache` runs prove cadence without manual inference
  - [ ] Await compiled-build validation instead of blocking on a long Codex log parse: in a normal long run, expect `[CACHE][REDDIT] Periodic refresh fired` for `reddit` around `15min` and `reddit2` around `22.5min` after startup, subject to jitter/cooldown/transition deferral

## Watchlist

- Non-`Custom` authored stacking is currently default-on for new users, but still needs future `--geo` re-audit against real authored layouts so the planner does not quietly regress while enabled.
- Visualizer CUSTOM geometry route repair is watchlist except for the active settings-return stale-bucket seam above. Ordinary edit/save/replay geometry remains healthy unless fresh logs show `[CUSTOM_LAYOUT][FALLBACK] Repaired spotify_visualizer CUSTOM save route...`, duplicate-owner fallback, requested-monitor fallback, replay-green/runtime-wrong geometry, or repeated bucket repair after the first save.
- Oscilloscope visual/reactivity is closed to watchlist after the 2026-06-29 runtime pass: idle starts, pause no longer needs to "break free", playback reads as waveform deformation rather than brightness strobe, and visualizer preset cycling no longer wipes media metadata. Reopen only with fresh `--viz` / runtime evidence and keep fixes mode-owned unless a shared seam is proven.
- Media metadata preservation during live visualizer preset churn is closed to watchlist; if it reopens, the first suspect is partial same-track playback snapshots during visualizer-only settings writes, not a broad media refresh fallback.

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
- Startup update-policy observability stays deferred behind the current widget/runtime priorities.
- Secure-desktop long-runtime exit reliability stays deferred.

## Documentation Rule

- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
- Historical geometry audit: `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md` when geometry/runtime replay issues reopen
- Bubble preset/runtime audit: `audits/BubbleAudit/Bubble_Preset_Runtime_Audit.md` as historical authored-setting reference
- Bubble historical audit reference: `audits/BubbleAudit/Bubble_End_To_End_Audit.md`
- Oscilloscope visual/reactivity audit: `audits/OscilloscopeAudit/Oscilloscope_End_To_End_Audit.md`

#######
### User Task Box: NEVER remove this box/section, only integrate its tasks into the active plan and then remove the text BELOW prompting the tasks.
----
No unintegrated user tasks.
----
######
