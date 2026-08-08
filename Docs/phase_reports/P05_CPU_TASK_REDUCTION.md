# Phase 5 — CPU and Task Reduction

Date: 2026-08-01
Branch: `main`
Foundation: closed Phase 4 (`Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md`)

## Outcome

Phase 5 reduces measured CPU, task, publication, and diagnostic work without changing authored visualizer feel, coupling simulation to paint, or enlarging the 256 MiB CPU-cache budget. It is **in progress**. The implemented slices below are not runtime closure.

Phase 4 is closed by `logs/evidence_chest/07_30_dc8d1741_00_26/`, including startup artwork and media-next during transitions. Older captures that reported a whole-process slope or media/startup collision remain useful historical failed-run evidence, but are superseded as Phase 4 gate evidence. Their CPU/frame-delivery and accounting questions transfer here.

## Current implementation state

The current unvalidated resource candidate adds six narrow reversible production
slices after the 2026-08-08 regression capture:

- ThreadManager task accounting no longer queues mutation records and periodic
  statistics publication through the GUI thread. Admission and terminal ownership
  counters remain exact and atomic; the ordinary COMPUTE executor and authored
  visualizer cadence are unchanged.
- Raw image prefetch is omitted when no planned scaled consumer needs it, and
  display prescale now uses the ImageWorker before exact parent raw-decode fallback.
- Terminal compositors retain only the authoritative current image texture and
  release idle upload PBO storage in the owning GL context.
- New PBOs no longer allocate full storage once at construction and immediately
  orphan/reallocate the same storage on their first upload.
- Usage evidence now separates whole/main/child private commit and USS in addition
  to RSS. Collection remains a low-rate background `--usage` task.

The latest resource detail gives these changes material targets: approximately
235.7 MiB of historical transition textures, approximately 45.7 MiB of retained
upload PBOs, and approximately 117.6 MiB of raw image forms alongside display-ready
derivatives. These are expected reductions, not installed results. Phase 5 remains
open until the same authored workload proves lower whole-app CPU/RSS/commit/VRAM.

The perf-only frame-owner snapshot was retained deliberately. Its exact headless
path measured approximately 6.5 microseconds per call, or about 0.15% of one core at
the dual-display 225 Hz presentation ceiling. It provides useful owner correlation
and is not a plausible explanation for the observed regression. Diagnostic evidence
may not be deleted merely to improve a perf run; diagnostic delivery may likewise
not create GUI scheduling work.

- Latency authority/lifecycle resets and WARNING rate limiting removed the impossible uptime-linear ERROR flood. The newest generation-matched 83.6–125.8 ms WARNING samples track real delivery tails rather than stale uptime.
- The attempted 60 submissions/s Bubble gate with maximum-two batching failed installed visual review and has been removed. The restored one-step lane-free path reached 50,106/50,106 offered/submitted work and is operator-validated for reaction and elasticity; Spectrum retains its existing shared newest-only path for now.
- Ordinary unchanged media polling is a no-op, but one redundant unchanged publication remains after startup/rebuild.
- Frame-gap ownership now points at transition-time Qt/event-loop delivery: 286/286 sampled gaps occurred with transition work active while paint and compute remained cheap.
- Recreated runtimes now wait on a non-reentrant old-generation QObject/resource/task/subscription destruction barrier before replacement construction. Settings has installed evidence. The first installed CUSTOM/Edit admission attempt exposed 64-bit manager identity truncation through Qt `int`; pointer-width signal transport is repaired mechanically, but installed dual-display proof remains open. Private commit, handles, and the five-cycle plateau gate remain open.
- R-56's deleted Settings wrapper retouch and R-57's scaled-prefetch positional removal defect are solved by mechanical tests plus the newest installed run.
- High-volume image-cache entry detail is routed to the cache sidecar; lifecycle resource ownership detail is routed to the lifecycle sidecar. Warnings and errors remain in the main log.
- Cache representation churn remains intentionally downstream of the recreation-ownership proof.

Across all 61 low-rate usage samples in the run, application CPU averaged about 59% with p95 about 95.3% and a transition/recreation maximum of 208.3%. Because the workload includes dialogs, rebuilds, transitions, Bubble, Spectrum, and image work, this is not a controlled before/after CPU win. Restoring Bubble correctness also restores its intentionally high task cadence, so P5.0 still needs a different design rather than claiming a CPU reduction from this run.

The mutable 2026-08-08 15:51–15:55 run is a delivery regression against the preserved 08_02 comparator, but not a controlled code-only comparison. Median application CPU rose from 79.3% to 103.2%; median paint-window FPS fell from 96.0 to 72.5; paint interval p99 rose from 32.9 to 41.0 ms; request-age p99 rose from 20.3 to 30.3 ms; event-loop lateness p99 rose from 38.9 to 57.6 ms; and the worst owner-labelled gap rose from 127.7 to 186.2 ms. The newest final runtime spent about 70% of its sampled life rendering transitions versus about 35% in the comparator, and machine-wide CPU was commonly about 35–39% versus about 14–18%.

Parser 1.5 repaired a derived-evidence defect: nested `tm_categories` JSON had been discarded whenever the newer `tm_delivery` object followed it on the same line. Recovered owner rates show comparable high-rate intervals in both runs at roughly 69–70 audio-analysis tasks/sec plus 92–93 Bubble-simulation tasks/sec. Submission frequency therefore did not newly increase, and these logs do not authorize a visualizer cadence change. The remaining regression needs a controlled workload and stronger per-owner execution/delivery attribution.

## P5.0 — Visualizer authored cadence

- [!] The 60 submissions/s maximum-two batching attempt failed the 2026-08-01 installed run. Of 2,566 offered steps, only 1,723 tasks were submitted: 842 were artificial cadence deferrals versus one worker-busy deferral. Only the terminal snapshot of each batch was published, so an impulse could be integrated and already decaying before its first visible result; the older packet could also consume a live scheduler edge intended for the newer packet.
- [x] Validate the restored lane-free path: the latest installed run reached 50,106 offered and 50,106 submitted lane-free steps (ratio 1.000) with no artificial cadence deferrals and roughly 1–2 ms worker execution. Later intervals stayed near 89 FPS with only isolated genuine worker/result ownership deferrals. The operator confirmed restored immediate Bubble reaction and elasticity.
- [x] Add a runtime-shaped source/discrete-edge-to-first-visible temporal oracle. The 100 Hz recurring-tick test authors a discrete kick at the exact phase deferred by the rejected 60 Hz token gate and requires that edge to appear in the first lane-free visible state. It fails terminal-only edge-plus-quiet batching while preserving the current one-step authored path.
- [ ] Compare input-to-visible latency, p99/max delivery, and CPU/task cost before/after any new design. Do not reintroduce a second cadence authority, terminal-only multi-step batching, or live scheduler capture merely to improve the counter.
- [ ] Exercise Spectrum on its unchanged shared newest-only path and Bubble → Spectrum → Bubble; do not retune Spectrum smoothing or Bubble authored behaviour without mode-owned failure evidence.
- [ ] Reject any optimization that turns paint delivery, feedback animation, or a retry timer into the visualizer clock.

## P5.1 — Frame-delivery owner telemetry

- [-] Add/passively consume owner-labelled render, submission, GUI callback, update-request, and paint timestamps without creating UI work or a new timer/queue.
- [-] The newest run supplied 222 owner-labelled frame gaps: 136 exceeded 33 ms, 86 exceeded 50 ms, and the maximum was 186.2 ms. Last-callback labels were overwhelmingly cheap mutation-drain, single-shot scheduling, and cursor-halo callbacks; they correlate with the delayed delivery but do not account for the missing tens of milliseconds. Prioritize controlled event-loop/update-delivery attribution rather than shader or Bubble-worker retuning.
- [x] Resolve the known transition-label hole: owner telemetry now accepts the compositor display-transition `name`, which was present on the 62 active records but previously ignored.
- [ ] Correlate the now-labelled transition owner with logical scene age, event-loop lateness, queue/callback tails, and per-display request-to-paint delay in the next installed capture.
- [ ] Attribute delayed delivery to its actual owner before changing cadence mechanics; a healthy render clock with delayed paint is event-loop delivery starvation, not permission to add repaint retries.

## P5.2 — False visualizer-latency diagnostics

- [x] The latest run has no impossible uptime-linear latency values and no false visualizer ERROR flood. Nine bounded WARNING samples remained at roughly 81–100 ms with matching engine/frame generations and activation identities.
- [x] Separate passive Bubble source age, logical simulation-step age, render-state application age, and existing request-to-paint age in frame-gap owner diagnostics. These timestamps are observation-only and create no timer, queue, repaint, or scheduling dependency.
- [ ] Validate the separated ages in an installed transition capture and classify the remaining 81–100 ms warnings against request-to-paint delivery.
- [ ] Prove diagnostic warnings neither claim a mode regression from presentation delay nor hide a real first-frame, mode-switch, or audio-input failure.

## P5.3 — Unchanged media repaint churn

- [-] Preserve the unchanged-media poll no-op through idle, transition, startup, and media-next scenarios.
- [ ] Measure media-card paint/update requests and layout mutations for unchanged key/metadata; require no recurring repaint, Qt structural mutation, artwork decode, or pixmap replacement.
- [ ] Remove the one unchanged post-start/rebuild publication still observed after each replacement (`metadata_changed=False`, `presentation_changed=False`, `layout_mutations=2`, `update_requested=True`); preserve the preceding first-track and layout-refresh contract.
- [ ] Keep changed artwork/title and transition-time feedback contracts from Phase 4 intact; validate current-key updates remain responsive without reviving the historical 30–38-paint burst.

## P5.4 — Memory/driver accounting and repeated edit/rebuild cycles

The preserved `07_30_ce1ba31c_5_34` operator capture exposed a distinct session-lifetime staircase during equivalent-state recreation. Main RSS advanced from about 832.5 MiB initially to 911.5 MiB after one Edit reload, 1,000.6 MiB after a second Edit reload, and 1,146.8 MiB after a Settings restart. Dedicated VRAM advanced from about 554.8 to 600.8, 722.9, and 806.7 MiB, while tracked known bytes stayed near 456.9, 455.9, 471.7, and 489.1 MB. Teardown itself still returned tracked GL, texture, PBO, and display-pixmap bytes to zero and substantially reduced driver VRAM, so strict GL cleanup remains authoritative. ResourceManager unknown registrations nevertheless rose from 35 to 52 to 74, including GUI components and timers. This is Phase 5 ownership work and does not reopen Phase 4.

The latest 17:23–17:38 installed run is an undeniable improvement but still not the required five-cycle plateau proof. It completed Settings → generation 1, CUSTOM → generation 2, and Settings → generation 3 recreation. Equivalent settled main RSS was about 900.9, 901.2, and 895.2 MiB; dedicated VRAM about 539.2, 554.9, and 540.0 MiB; and ResourceManager total/unknown counts 58/47, 58/47, and 56/45. The former approximately 80–90 MiB main-RSS, large VRAM, and 35 → 52 → 74 unknown-registration step per recreation did not recur. Both Settings exits crossed their dialog barriers, constructed fresh runtimes, and were operator-validated.

The residual accounting prevents closure. Equivalent total private commit rose about 2,911.4 → 2,944.7 → 3,000.2 MiB and total handles rose 2,130 → 2,146 → 2,189; direct main-process lifecycle samples similarly rose from about 1,792 to 1,810, 1,831, and 1,863 handles. Worker RSS stayed about 96.4–98.3 MiB, all 34 shared-memory segments were consumed, live shared-memory bytes remained zero, and unlink failures remained zero. Threads returned broadly to 90–94. The first reconstruction also carried a one-time roughly 60 MiB main-RSS rise versus the cold state; only additional equivalent cycles after every retired owner is absent can classify that as a plateau/high-water effect.

The same barriers still logged diagnostic-only surviving Python wrappers: two `WidgetManager` plus two `FadeCoordinator` instances after Settings, and those plus two `CustomLayoutManager` instances after CUSTOM. They had no retiring-generation ResourceManager/task/subscription ownership at barrier completion, but the acceptance contract still requires retired Python roots to reach zero. Their explicit release or bounded post-continuation proof remains open; they may not be dismissed as harmless allocator state.

The newest two-Settings run no longer supports a plateau claim. Equivalent Bubble replacement snapshots were:

```text
state                    main RSS   main private   handles   threads   tracked known   RM total/unknown
cold generation 0         786.6       1994.7        1782       61        338.6 MiB         60 / 49
Settings generation 1     917.6       2103.7        1862       68        403.1 MiB         55 / 45
Settings generation 2     977.2       2177.8        1841       64        416.7 MiB         55 / 44
```

Generation 1 to 2 therefore added about 59.6 MiB main RSS and 74.0 MiB main private bytes while tracked known bytes added only about 13.6 MiB. ResourceManager totals/unknowns did not climb, handles and threads fell, retired ownership cleared, tracked GL/display bytes reached zero during teardown, the image worker stayed bounded, and shared-memory live bytes/unlink failures remained zero. Two cycles do not prove a linear leak, but whole-process containment remains unproven and active.

- [-] Validate generation-scoped ResourceManager registration metadata, weak passive cleanup observation, QObject-destroyed release, retained-bound-callback reporting, and process/runtime scope separation on the installed runtime.
- [-] Validate installed zero-owner release for `WidgetManager`, `CustomLayoutManager`, and `FadeCoordinator`. Production-shaped teardown tests now release two of each observed owner before continuation without `gc.collect()`, but installed CUSTOM evidence is still mandatory.
- [ ] Give `WidgetManager` explicit ownership state for its one-shot `image_displayed` connection. `_on_compositor_ready()` disconnects after first readiness and `cleanup()` currently repeats the disconnect; PySide emits `RuntimeWarning: Failed to disconnect` when no matching connection remains. This is redundant signal bookkeeping, not evidence of a retained connection, and the fix must preserve the authoritative first-frame gate.
- [-] Validate Settings, committed CUSTOM Edit, and monitor recreation as two-stage operations. CUSTOM now persists and retires its Edit session first, returns from manager-owned frames, then admits unchanged full teardown through an immutable engine-owned later-turn request; installed dual-display confirmation remains open.
- [-] Confirm terminal shutdown disarms replacement continuations and creates no QObject/timer work after Qt starts closing; timeout must fail closed rather than construct alongside a surviving retired graph.
- [-] Confirm SettingsDialog/Edit-owned callbacks, timers, animations, panels, handles, models, and global clock subscriptions are generation-owned and destroyed rather than hidden or cached.
- [-] Confirm closing Settings completes the dialog destruction barrier and then constructs/reveals the replacement runtime. RUN sessions disable Qt last-window auto-quit only after successful engine startup; explicit engine/tray/error routes remain terminal authorities.
- [-] Correlate synchronized lifecycle snapshots at stop, generation invalidation, producer stop, strict GL cleanup, queued destruction, confirmed root destruction, replacement construction, authoritative first frame, FadeCoordinator reveal, and settled replacement. Use the latest already-collected `--usage` sample for total RSS/private commit/VRAM; lifecycle logging must not issue a new driver query.
- [x] Deterministic five-cycle alternating Settings/Edit ownership regression requires the barrier to observe nonzero resource, delayed-callback, and global-subscription ownership, then proves zero retired-generation ownership and one continuation per generation.
- [ ] Run at least five installed alternating Settings/Edit cycles with Bubble, Spectrum, Bubble → Spectrum → Bubble, active transition near teardown, pending image work, media polling/artwork, and idle settle windows.
- [ ] Require every retired generation to reach zero QObject roots, timers, animations, subscriptions, ThreadManager work, and ResourceManager entries before replacement; require stable handles/threads and no approximately linear equivalent-state RSS/private-commit/VRAM increase.
- [ ] Preserve the separate authoritative-first-frame barrier and existing FadeCoordinator reveal. No retired frame, prior activation, zeroed Spectrum state, or previous-mode Bubble state may satisfy replacement readiness.
- [ ] Use one diagnostic-only `gc.collect()` only if needed to classify a proven residual Python cycle; it may not become production cleanup. Do not use process-event pumping, repeated GC, trimming, recycling, worker restart, cache growth, or runtime reuse.

## P5.5 — Cache representation churn

- [ ] Profile raw/scaled/GUI backing co-retention, prefetch future bytes, transformations, and cache hit usefulness under representative cycling.
- [ ] Remove only measured redundant representation/copy churn while retaining exact source/transform/size/mode/DPR identity and existing newest-only/stale-generation ownership.
- [ ] Keep the CPU image cache at its 256 MiB production ceiling; do not add pins, enlarge budgets, or use trimming/GC as a substitute for owner evidence.

## P5.6 — Logging hygiene

- [x] Recovery parser 1.5 decodes nested task-category counters independently of a trailing delivery JSON object and has a regression fixture for the production log shape.
- [-] Keep latency diagnostics and warnings bounded, sampled, passively collected, and rate-limited.
- [-] Verify `--perf`/`--viz` output has owner labels and correlation fields sufficient to diagnose delivery without per-frame INFO logs, whole-state dumps, or new diagnostic work queues.
- [-] Verify per-entry image-cache hit/miss/put/remove/eviction detail appears only in `screensaver_cache.log` when `--cache` is active; keep one bounded `[PERF] [CACHE]` lifecycle summary for correlation.
- [-] Verify bounded per-resource generation/owner/site detail appears in `screensaver_lifecycle.log` only when `--life` is active; ordinary aggregate resource counters remain in `screensaver_perf.log` without duplicating the resource list.
- [ ] Confirm warnings/errors remain visible in `screensaver.log`; rate limiting may coalesce repeats but must retain count/window/owner context and never change runtime control flow.

## Runtime gate

- [ ] Capture before/after evidence for idle, Bubble, Spectrum, mode switch, active transition, image decode, and at least five alternating Settings/Edit/CUSTOM rebuild cycles under controlled background load.
- [ ] Require materially lower task/CPU cost, equal-or-better p99/max frame delivery, preserved visualizer runtime review, bounded memory/driver accounting, and no new synchronization or UI-pressure workaround.
- [ ] Record environment, commit, parser version, excluded intervals, rollback, and unsupported platform measurements before marking Phase 5 complete.

## Non-goals

Do not remove the Phase 8 presentation-worker architecture here, add threads/processes without latency/GIL/memory evidence, change the compositor topology, turn diagnostics into control flow, or modify visualizer creative settings solely to improve a metric.
