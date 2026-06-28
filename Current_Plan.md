# Current Plan

Last updated: 2026-06-28

This file tracks active work only. Long-lived architecture truth belongs in `Spec.md`; dated bug narratives belong in `Docs/Historical_Bugs.md`.

## Guardrails

- Keep this aligned with `Spec.md`, `Index.md`, `Docs/Guardrails.md`, and `Docs/Historical_Bugs.md`.
- Prune validated work aggressively. This is not a changelog.
- Prefer automation bars over repeated runtime-verification asks.
- Do not close visual/runtime bugs from polite unit doubles alone.
- Before touching shared visualizer/audio/activation/render/transition seams, protect the current-good modes with the visualizer reactivity lock in `Docs/Harness_Index.md`: `Spectrum`, `Sine Waves`, `Bubble`, and `Dev Curve` must match their current accepted bars or the change stops. `Oscilloscope` remains a watchlist mode, not a priority target.
- For visualizer geometry, treat these as separate seams until proven otherwise:
  - saved/custom rect authority
  - live widget rect authority
  - GL overlay rect authority
  - startup / prewarm / first-frame authority
  - mode-reset or preferred-height side effects
- A green `replay_final` log is necessary but not sufficient for visualizer geometry closure.
- Recovery paths are allowed only after the root-cause map and the stronger bars exist.

## Active Tasks

- [ ] Execute the project-wide runtime health audit in [audits/ArchitectureAudit/Project_Health_Audit.md](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/audits/ArchitectureAudit/Project_Health_Audit.md)
  - [ ] Establish the visualizer reactivity lock before any shared visualizer/perf/lifecycle work
    - [ ] Keep `Spectrum`, `Sine Waves`, `Bubble`, and `Dev Curve` green against the focused lock commands in [Docs/Harness_Index.md](F:/Programming/Apps/ShittyRandomPhotoScreenSaver/Docs/Harness_Index.md)
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
    - [x] Runtime-check the adaptive-timer GIL-spin fix against commit `40562fe`: latest `--perf` runs stay in the improved range with no pending-paint requeues, no shader fallbacks, no cache worker fallbacks, and no high-refresh near-60 paint windows
    - [x] Separate the latest collapse into two log-backed seams: early `GL RENDER` healthy / `GL PAINT` starved windows, and later `GL ANIM` control-callback cadence near `60fps` while paint-time interpolation still delivers higher visual paint cadence
    - [x] Remove the adaptive render timer's Python busy-spin deadline tail so high-refresh timing no longer monopolizes the GIL while Qt paint/event-loop delivery is trying to consume queued updates
    - [x] Fix the exit-stall/orphan-timer seam where a late compositor lazy animation callback or delayed/desynced transition starter could start an adaptive timer after `stop_rendering()` / display teardown had already invalidated that transition
    - [x] Runtime-check the next `--life` / `--perf` run for no `ThreadManager shutdown timed out` adaptive-timer tasks, no late `Internal C++ object (GLCompositorWidget) already deleted` transition-complete callbacks, and no post-stop adaptive frame signalling
    - [ ] Correlate any remaining paired starvation windows with settings open/close, edit-mode save, display clear/recreate, frame-budget spikes, and visualizer tick spikes using the parser timeline
    - [ ] Continue the remaining collapse investigation from the latest sharper evidence: Display 0 render cadence remains healthy at `~165Hz` while paint can drift into `~85-118fps`; Display 1 render cadence remains `~60Hz` while `GL ANIM` can fall into a suspicious `~40fps` cadence under some transitions
    - [ ] Root-cause any remaining Qt/GL paint delivery under-delivery while render timers remain at target; inspect update consumption, pending-flag lifecycle, compositor/widget lifecycle churn, display-specific refresh target state, and event-loop stalls
    - [ ] Root-cause settings UI stalls around widget tab hydration (`~2.3s` class stalls in latest logs) without breaking settings persistence, buckets, or scroll persistence
    - [ ] Correlate slow GL texture uploads with image-cache warmup and display rebuild boundaries; prefer cache/prewarm ownership fixes over UI-thread upload retries
    - [ ] Inspect visualizer tick-listener cadence separately from Bubble worker cost; Bubble compute is low in the latest collapse logs and must not be retuned for this perf task
    - [ ] Search for duplicate hidden visualizer owners, duplicate beat engines, extra worker loops, stale overlays, or uncollected visualizer resources before optimizing render paths
    - [ ] Treat current-good visualizer modes as locked: `Spectrum`, `Sine Waves`, `Bubble`, and `Dev Curve` must keep accepted behavior before and after any shared render/tick changes
    - [ ] Keep FPS work off the UI thread; root-cause cache/worker/timer ownership instead of adding synchronous decode, scaling, render retries, repaint loops, or update rescue timers
  - [ ] Reduce image-cache/prescale fallback pressure without moving work onto the UI thread
    - [x] Runtime-validate the bounded raw-prefetch backlog: latest `--cache` logs show full preview coverage (`active=2 pending=3`, scaled `request_count=5 prepared=5`) instead of the old first-two-only skip.
    - [x] Add a parser/bar that fails the still-active fallback path where transition images miss the preview window entirely (`raw_inflight:0,raw_pending:0,scaled_inflight:0,scaled_pending:0`)
    - [x] Keep the delayed post-transition prefetch resume armed while another display still reports transition work pending, instead of consuming the resume and leaving no producers registered
    - [x] Preserve raw/scaled prefetch registration intent through post-transition cooldown without dispatching new work during the cooldown window
    - [x] Rearm transition-complete prefetch resume until the prefetcher cooldown has actually expired, avoiding the just-before-expiry lost-wakeup shape
    - [x] Runtime-check the latest `--cache` run: zero-producer fallback count is now `0`, with preview producer registration and scaled coverage present after transition-complete resumes
    - [ ] Keep cache promotion, cancellation, and worker wakeup ownership on watch only if future `--cache` logs reintroduce zero-producer fallbacks or slow-upload clusters near collapse windows
    - [ ] Keep fallback logs loud through `--cache`; do not hide fallback usage by downgrading or moving warnings out of operator-visible logs
    - [ ] Prefer worker/cache ownership fixes over UI-thread decode, scaling, or synchronous retry paths
  - [ ] Split the visualizer suite into trustworthy gates before using it as a project health bar
    - [ ] Re-baseline Bubble oracle values against current accepted runtime feel only; do not touch Bubble reactivity or visuals for this task
    - [x] Fix non-Bubble/test-fixture drift separately from Bubble, including Oscilloscope runtime push and tick-pipeline unit doubles
    - [x] Keep mode-switch overlay reuse contract covered: preserved overlay must be reset/hidden/blanked and target-mode reset before fresh-frame reveal
    - [ ] Re-run and classify the remaining full visualizer suite failures so stale Bubble expectations do not mask real non-Bubble regressions

- [ ] Close the remaining visualizer CUSTOM geometry authority family without adding more mitigation churn
  - [ ] Keep `audits/GeoAudit/Visualizer_Runtime_Shape_Audit.md` as the root-cause map owner
  - [ ] Enumerate every post-replay writer that can still touch visualizer live rect or overlay rect after committed CUSTOM authority should have won
  - [x] Add a save-time bar for the poisoned route shape where `spotify_visualizer` is physically on one display but carries another display's monitor route
  - [x] Repair `spotify_visualizer` CUSTOM save ownership from the shell's actual global rect before persisting monitor/bucket authority, with a loud log when a poisoned route is corrected
  - [x] Add a recovery-button bar for the case where no exact current-screen visualizer bucket exists but one saved visualizer rect exists elsewhere
  - [x] Make explicit visualizer recovery create a centered, visualizer-aspect rescue shell instead of inheriting media-shaped or polluted active-shell geometry when exact saved data is unavailable
  - [x] Runtime-check the next `--geo` run for the clock-edit scenario: latest long run shows the visualizer surviving edit saves and replaying a valid corrected rect after save-route repair
  - [x] Runtime-check the media recovery button only as a rescue path: user run shows the recovery seam now creates a usable edit rect instead of removing the visualizer from all displays or exiting edit mode
  - [ ] Eliminate the upstream reason save-route repair still fires: latest logs still emit `[CUSTOM_LAYOUT][FALLBACK] Repaired spotify_visualizer CUSTOM save route...`, so recovery is validated but not a clean steady-state success
  - [ ] Keep fallback/recovery layers temporary and loud; do not add another self-heal layer before the owner map is narrower
  - [ ] Strengthen the bars so `replay_final` green but runtime-wrong still fails decisively

- [ ] Fix Digital Clock edge-case wobble without regressing analogue or CUSTOM mode swaps
  - [ ] Use `--geo` evidence to model the Display 0 digital-clock case where seconds changes still resize/shift the clock while Display 1 remains stable
  - [x] Add a bar that compares digital text/layout geometry across changing seconds (`08:08:08`, `11:11:11`, `18:49:11`, `23:59:59`) inside the Display-0-shaped CUSTOM rect
  - [x] Remove time-tick stylesheet rebuild churn so digital background/frame styling remains setting-driven instead of second-driven
  - [x] Ensure digital mode uses a stable measured template/container instead of live-text-dependent width/scale changes
  - [x] Remove stale timezone-label-height feedback from the digital font fit path so tight CUSTOM rects cannot oscillate between previous-label and next-font measurements
  - [ ] Runtime-check the next `--geo` run for Display 0 digital-clock stability; if wobble persists, inspect parent/custom replay writers rather than text measurement
  - [ ] Preserve the already-fixed contracts: no clipping, timezone balanced inside the frame, double-click swaps work in CUSTOM runtime, and mode swaps rebuild cleanly around the current rect

- [ ] Improve CUSTOM edit-mode guide lines as real snap/assist affordances
  - [ ] Add display-center horizontal and vertical guide assists for the adjusted widget's active display
  - [ ] Add peer-widget center horizontal and vertical guide assists without making hidden/shadow/debug bounds authoritative
  - [ ] Keep guide visibility tied to the existing touch/threshold behavior so the grid does not become permanent visual noise
  - [ ] Add bars around the snap/guide resolver so painted guide lines correspond to real candidate assists, not cosmetic-only lines

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
  - [ ] Runtime-check a `--cache` run past the first cadence window: expect `reddit` around `15min` and `reddit2` around `22.5min` after startup, subject to jitter/cooldown/transition deferral

## Watchlist

- Non-`Custom` authored stacking is currently default-on for new users, but still needs future `--geo` re-audit against real authored layouts so the planner does not quietly regress while enabled.
- Oscilloscope needs a later focused audit: current runtime appears to flicker/strobe in brightness and ghosting is not visually obvious even though `--viz` logs still report `ghost2=True ghost3=True`.

## Deferred / Not Active

- [ ] Oscilloscope visual audit (deferred until transition perf and clock wobble are stable)
  - [ ] Capture current Oscilloscope behavior under `--viz --perf` and confirm whether the brightness flicker is shader state, glow/reactivity, alpha/ghost layer, or activation reset churn
  - [ ] Add a visual/runtime-shaped oracle before changing Oscilloscope rendering so current-good modes stay isolated
  - [ ] Restore ghost visibility only through mode-owned rendering contracts; do not touch shared visualizer audio/floor/tick behavior for this audit
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
