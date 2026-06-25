# Current Plan

Last updated: 2026-06-22

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
    - [ ] Use the next `--perf`/main log to classify RainDrops/Diffuse shader fallback as capability, texture-prep, or exception before changing render behavior
  - [ ] Reduce image-cache/prescale fallback pressure without moving work onto the UI thread
    - [x] Explain repeated `[CACHE] [FALLBACK] Worker fallback reason=scaled_miss raw_state=raw_missing` during real transition runs
      - Fresh `--cache` evidence showed the old idle-pending bug was gone, but preview warmup still prepared 5 images while only the first 2 raw producers were scheduled; later preview paths were skipped and then fell back during fast transitions.
    - [x] Investigate the newest `--cache` evidence where fallback logs show `raw_inflight:0`, `scaled_inflight:0`, and a growing `scaled_pending` queue; this pointed at scaled warmup registration during post-transition raw-prefetch cool-down
    - [x] Add a cache/pipeline bar so transition cool-down cannot leave scaled warmup pending while no raw/scaled worker is active
    - [x] Add a cache/pipeline bar so scaled warmup registration cannot orphan pending entries for raw paths that were never scheduled or cached
    - [x] Include prefetcher queue/inflight state in loud `--cache` fallback diagnostics so the next run distinguishes worker starvation from missing scheduling
    - [x] Add a bounded raw-prefetch backlog so the full preview window has raw producers without exceeding active IO concurrency
    - [x] Add a cache bar so preview windows larger than `max_concurrent` retain queued raw producers and scaled warmups instead of silently accepting only the first active paths
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
  - [ ] Keep fallback/recovery layers temporary and loud; do not add another self-heal layer before the owner map is narrower
  - [ ] Strengthen the bars so `replay_final` green but runtime-wrong still fails decisively

## Watchlist

- Non-`Custom` authored stacking is currently default-on for new users, but still needs future `--geo` re-audit against real authored layouts so the planner does not quietly regress while enabled.

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
