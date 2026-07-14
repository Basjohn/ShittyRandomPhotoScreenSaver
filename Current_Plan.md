# Current Plan

Last updated: 2026-07-14

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

### Steam And Visual Timing Runtime Bar

- [ ] In a fresh normal and MC compiled run, validate Achievement Pulse's default `140 x 196` Portrait art at `540 x 334`: header/right rails stay aligned, `Unlocked` remains six authored pixels below art and renders complete high counts without ellipsis in Portrait/Wide/Square/art-off, the first capsule rail retains its measured gap, and 140/190 width changes, high DPR, large capsule font, settings rebuild, and Custom scaling do not clip or rearrange content. With two recent games whose play order and latest-unlock order disagree, require Most Recent, Previous, and Settings labels to follow the newest positive unlock timestamp while missing timestamp evidence falls back stably.
- [ ] Run solid-bar Spectrum with `--viz --perf` through quiet/dropout material and at least one image transition: the 2026-07-14-style coherent input collapse must decay/recover without a brief zero flash or delayed-frame snap, while ordinary smoothing remains visually unchanged and logs show no new timer/repaint/audio-floor pressure.
- [ ] Run the analogue clock with seconds visible for several minutes in normal and MC builds: require discrete six-degree second ticks with matching one-second minute/hour progression, no semi-smooth pause/jump interpolation, and unchanged shared clock-ticker/paint cadence.

### Steam Abandonment Issues Production Runtime Bar

- [ ] In a fresh compiled run without `--devsteam`, enable Abandonment Issues and verify cached content appears before the first coordinated fade, Smart/Pinned/unknown-history states remain honest, cached library names populate without provider work, and explicit Refresh Steam Library gives gentle success/failure feedback.
- [ ] Run multi-display and long-idle passes with `--steam --perf --cache --set --geo --life`: set the shared Steam refresh interval to 5 minutes and confirm `ABANDONMENT_CADENCE` reports shared/rotation `5`, the recurring timer is 300,000 ms, automatic game changes follow that cadence without a competing 15/30-minute value, owned-library requests still respect their 24-hour source window, and recent games follow shared freshness. Widget/settings/display rebuilds or interval changes must preserve only the true remaining due interval; explicit widget refresh must force a visibly different non-repeating draw when alternatives exist; several due intervals must log preference-biased non-sequential `ARCHIVE` ranks without immediate repeats, and `ARCHIVE N/M` remains rank rather than cursor. A selected public-art cache miss may hydrate only on the existing IO job before the atomic fade commit; a requested-shape 404 may log one `fallback_hydrated` alternate, transient failures must not fan out, and `--noupdates` must remain cache-only. Require no provider/achievement request from rotation, no blank committed art when an allowlisted variant succeeds, no repaint burst/UI-thread stall/DT spike, and one deferred retry rather than a lost interval on parent-transition collision. Keep 15-minute session-floor/2-hour/2-unlock/26-week ranking changes honest.
- [ ] Validate portrait/wide/art-off, minimum/default/maximum portrait size, Guilt off/on/max, RGBA accent, rediscovery message off/on plus a longest alternate staying fitted and stable across displays/rebuilds, and every optional ledger-field combination. Specifically prove default `PLAYED` / `ACHIEVEMENTS` / `LAST UNLOCK` / exact `LAST PLAYED` date / `ARCHIVE CLASS` shelves remain truthful, unknown evidence removes only its shelf, all eight enabled shelves grow complete rows, and large fonts, high DPR, and narrow/tall multi-monitor `Custom` geometry do not overlap, reflow, clip, shrink the authored hierarchy, or mutate the committed rect.
- [ ] Exercise `--noupdates`, offline, unauthorized-with-valid-cache, disconnect, settings restart, frozen build, and non-repository cwd; cache must remain authoritative, `--noupdates` must log `cache_miss_network_disabled` rather than fetching public art automatically, failed sources must not freshen it, teardown must leave no Steam timer/task/resource warnings, and credentials/account data must remain absent from logs/exports/repo artifacts.

### Visualizer Regression-Bar Reconciliation

- [ ] Root-cause the deterministic Oscilloscope failure in `test_paused_reactive_modes_keep_waiting_for_fresh_engine_frame`: a paused Oscilloscope currently clears `_waiting_for_fresh_engine_frame` while the Spectrum branch preserves it. Reconcile the intended fresh-generation contract against `Docs/Historical_Bugs.md` and the current tick pipeline before changing either the test or runtime; do not disturb the accepted Spectrum zero-frame/catch-up behavior.
- [ ] Reconcile the 15 deterministic Bubble/Deep Sea failures in `tests/test_spotify_visualizer_widget.py` as likely stale-oracle debt against the currently accepted live Bubble behavior. Freeze Bubble runtime/preset behavior unless fresh runtime-shaped evidence proves a user-visible regression; use the existing fixture/log-replay harnesses to identify obsolete numeric signatures, update/remove only disproven expectations, and do not retune Bubble or add UI-thread/timer/paint pressure merely to make the suite green.
- [ ] Require the complete `tests/test_spotify_visualizer_widget.py` file to pass (environment skips excepted), then run the focused visualizer reactivity lock from `Docs/Harness_Index.md` before pruning this task.

### Deprecated Blob End-To-End Removal

- [ ] Inventory every Blob-owned dev gate, default/descriptor, settings field/control, preset, runtime builder/binding, shader/asset, package rule, log route, test, and documentation reference. Treat the current 267 collected tests and 115-file / 5,955-match footprint as deletion scope, not a repair queue; shared visualizer/audio/animation/compositor behavior is frozen unless removal proves a direct dependency.
- [ ] Add the migration seam first: a saved Blob mode must resolve once to the registry-owned supported default, obsolete Blob keys must be stripped without being re-emitted, and normal/MC imported settings plus generated defaults must remain valid. Preserve only absence/migration tests that protect supported modes.
- [ ] Remove Blob implementation and its dedicated test corpus end to end, then remove the temporary default pytest skip and `--run-deprecated-blob-tests` escape hatch. A repository-wide search may retain only explicit historical migration notes; startup, settings, presets, packaging, synthetic audio, and the focused supported-visualizer reactivity lock must pass without Blob fixtures or branches.

### Canonical SST Reproducibility And Parity

- [ ] Make the generated normal and MC `.sst` artifacts derive from one profile-aware canonical defaults source. Remove accidental snapshot-only keys such as empty Weather latitude/longitude unless they become descriptor-owned defaults, and explicitly classify the small intended normal/MC delta rather than maintaining two independent settings bodies.
- [ ] Replace run-time-dependent `migrated_at` / `last_migration_completed` output with deterministic generated metadata or exclude operational migration state from distributable defaults. Two clean regenerations from identical source must be byte-identical.
- [ ] Extend regeneration tests to compare every generated snapshot against canonical defaults for its profile, reject secrets/private runtime state, and prove the Defaults Foundry does not invalidate existing installation JSON. Regenerate both tracked artifacts, run Foundry/import/default-parity suites, and document the single authoritative edit/regenerate path before pruning this task.

### Gmail OAuth Thread Ownership

- [ ] Replace the raw `threading.Thread` used for `HTTPServer.serve_forever` in `core/gmail/gmail_oauth.py` with a bounded `ThreadManager`-owned task using the manager already supplied to the OAuth flow. Define one owner for completion, cancellation, timeout, server shutdown, and task cleanup.
- [ ] Add success, user-cancel, callback-timeout, settings-close, and application-teardown tests that prove the local server/port and task are released exactly once. Keep browser handoff and DPAPI-backed credential behavior unchanged, and do not add UI polling, repaint loops, or rescue timers.
- [ ] Require the thread-policy suite and focused Gmail OAuth tests to pass in source and frozen-build-shaped paths, with no orphan-thread, late-callback, or UI-thread pressure warnings.

### Canonical Audit Document Classification

- [ ] Review all nine ignored/untracked Markdown documents under `audits/` for unique evidence, stale conclusions, credentials, identifiers, screenshots, absolute machine paths, and generated debris. Do not unignore or upload the directory wholesale.
- [ ] For each document, either sanitize and deliberately track it as durable source, migrate still-valid guidance into `Spec.md` / `Docs/Historical_Bugs.md` / `Docs/Harness_Index.md` and retire the local copy, or leave it explicitly local and noncanonical with no navigation dependency.
- [ ] Add a bounded documentation-link check proving every canonical file reference in `Index.md` and this plan exists in tracked source. Restore specific audit links only for documents that pass classification, then prune this task.

## Watchlist

- [ ] Performance cadence: preserve fresh evidence if Display 0 falls into a suspicious near-60 visible cadence, Display 1 into near-40 under-delivery, or the parser reports paint starvation, overlay under-delivery, swap-interval warnings, shader/cache fallbacks, or repeated app-shared `AnimationManager` under-target windows with actionable `active_labels`.
- [ ] Visualizer timing: if `--viz` logs show slow `_on_tick` phase breakdowns, fix the named owner directly; if only tick gaps appear, treat it as event-loop/timer delivery pressure rather than visualizer work.
- [ ] Reddit cadence: in the next long compiled run, confirm both widgets fire near due cadence, sparse HTML does not become the repeated primary source after partial rescue, and failed/empty chains do not freshen cache timestamps.
- [ ] Visualizer CUSTOM geometry route repair: reopen only if fresh logs show repeated bucket repair, duplicate-owner fallback, requested-monitor fallback, replay-green/runtime-wrong geometry, or settings-return suppression/stranding.
- [ ] Display wake / monitor recreate: keep the latest behavior accepted unless black-background recovery, missing compositor surfaces, duplicate displays, placeholder truth, or an exhausted per-display image-replacement warning returns. A worker-rejected first candidate should now recover that display within the same compute pass.
- [ ] Settings runtime restart: expected lazy-section omission must stay free of `blocked_save_from_unhydrated_section`; reopen only if that warning reflects a real direct unhydrated save, deleted Qt wrapper errors, stale background hydration, or settings-exit runtime bleed in `--set` / main logs.
- [ ] Sources / RSS reset: validate that "Just Make It Work" preserves existing RSS cache, emits one deferred source-change during settings, and settings exit performs only one clean source/RSS initialization without stranding media or visualizer.
- [ ] Non-`Custom` authored stacking: default-on for new users; re-audit with `--geo` only if authored-layout collision behavior reopens.
- [ ] Oscilloscope, Sine Waves, Bubble, and Dev Curve: accepted current behavior. Reopen mode-owned work only with fresh `--viz` evidence. Spectrum is temporarily covered by the active rare-dropout runtime bar above.
- [ ] Media metadata preservation during live visualizer preset churn: if it reopens, first suspect partial same-track playback snapshots during visualizer-only settings writes.
- [ ] Steam Journey and Friend Pulse remain production-hidden until each is explicitly promoted beyond `--devsteam`; Journey's next gate is editorial classification/noise/request-budget evidence, not transport discovery.

## Deferred / Not Active

- [ ] Feeds widget family architecture track:
  - [ ] Keep Reddit as its own branded widget and shared runtime owner; do not replace it with Feeds.
  - [ ] Extract reusable list-feed seams from Reddit without changing Reddit UX first.
  - [ ] Design Feeds as an additional widget family with isolated per-spawn source/cache/settings contracts.
  - [ ] Prefer official/feed-native sources and avoid HTML scraping/session automation by default; Reddit HTML is the explicit paced exception because Reddit's structured public endpoints are fragile.
- Startup update-policy observability stays deferred behind current runtime-health priorities.
- Secure-desktop long-runtime exit reliability stays deferred.

## Documentation Rule

- Architecture: `Spec.md`
- Module map: `Index.md`
- Policy: `Docs/Guardrails.md`
- Dated regressions: `Docs/Historical_Bugs.md`
- Drift-check routine: `Docs/Documentation_Maintenance.md`
- Harness reference: `Docs/Harness_Index.md`
- Local ignored `audits/` notebooks are noncanonical until the active classification task either tracks a sanitized document or migrates its valid guidance into the sources above.

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
