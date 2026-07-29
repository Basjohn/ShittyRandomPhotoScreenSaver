# Current Plan

Last updated: 2026-07-29

Active work only.

Stable architecture belongs in `Spec.md`. Durable safety rules belong in `Docs/Guardrails.md`. Detailed compositor design belongs in `Docs/Compositor_Architecture.md`. Dated failures belong in `Docs/Historical_Bugs.md`.

## Recovery Boundary

```text
main (based on baseline 00edb57a3076b845cb8ee4b6cb7f36ea83411f0c)
donor/reference only: 7376bb9bb380253f3bd14079e65d7bdbca062fad
```

The donor is read-only reference material, never a merge target. New evidence uses disposable plain subfolders under `logs/evidence_chest/`; legacy ZIPs are historical inputs only.
## Non-Negotiable Gates

- Visualizer feel is protected before infrastructure changes.
- Average FPS cannot hide poor p99/max frame delivery.
- Settings/Edit must not introduce GL affinity failure.
- RAM and VRAM must plateau.
- CPU/task reduction cannot lower quality or reactivity.
- Producers never wait for paint.
- Donor branch is not merged wholesale.
- Existing files and documents are not renamed or moved.

## Status Legend

- `[ ]` not started
- `[-]` active
- `[x]` complete with evidence
- `[!]` blocked/failed
- `[~]` explicitly deferred

A phase is complete only with tests, runtime evidence, visualizer result, and rollback point.

## Completed Checkpoints

- [x] **Phase 0 / Gate 0:** freeze, evidence, and ownership inventory are complete; the Phase 1 checkpoint supplies the clean committed recovery point. See `Docs/phase_reports/P00_FREEZE_INVENTORY_AND_EVIDENCE.md`, `Docs/phase_reports/P00_SOURCE_OWNERSHIP_INVENTORY.md`, and `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.
- [x] **Phase 1 / Gate 1:** bounded passive frame, event-loop, task, CPU-image, GL-resource, and lifecycle-snapshot measurement validated without behavioural change. See `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.
- [x] **Phase 2 / Gate 2:** deterministic all-mode visualizer replay, protected baseline goldens, cadence-separation tests, quantitative metrics, and Spectrum/Bubble logical review artifacts are complete. See `Docs/phase_reports/P02_VISUALIZER_FIDELITY_LOCK.md`.
- [x] **Phase 3 / Gate 3:** full stop/destroy/recreate lifecycle, generation-and-manager stale-work rejection, and strict owner-context GL deletion are complete. The post-checkpoint dual-display program-ownership defect, competing generic-registry deletion fallback, and missing two-compositor test shape were corrected and recorded in the Phase 3 report. See `Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md`.

## Phase 5 — CPU and Task Reduction

- [ ] Categorize recurring tasks.
- [ ] Remove tiny high-frequency pool jobs.
- [ ] Stop hidden/static work.
- [ ] Coalesce duplicate publications.
- [ ] Batch/vectorize measured hotspots.
- [ ] Eliminate logging/control overhead.
- [ ] Preserve visualizer fidelity and frame tails.

**Gate:** materially lower CPU and task rate.

## Phase 6 — Explicit GPU Resource Store

- [ ] Small metadata-first store.
- [ ] Exact byte accounting.
- [ ] Context/share generation.
- [ ] Explicit leases/references.
- [ ] No GL calls under registry locks.
- [ ] Deterministic owner-thread deletion.
- [ ] Byte caps and eviction for unleased resources.
- [ ] Context recreation invalidation tests.

**Gate:** bounded reuse without stale handles.

## Phase 7 — Visualizer/Presentation Decoupling

- [ ] Narrow immutable visualizer render state.
- [ ] Simulation cadence independent of paint.
- [ ] No producer paint waits.
- [ ] Latest render-state coalescing.
- [ ] Preserve input processing and mode feel.
- [ ] Test injected GUI stalls.

**Gate:** visualizer remains correct under presentation pressure.

## Phase 8 — Narrow Single-Surface Compositor

- [ ] One surface per display.
- [ ] Immutable scene snapshot.
- [ ] Explicit draw order.
- [ ] No simulation or lifecycle ownership.
- [ ] GUI-local update coalescing only.
- [ ] Replace the two adaptive presentation workers with one GUI-thread, active-animation-only update mechanism per display; preserve no worker waits or paint acknowledgement.
- [ ] No compatibility mega-layer.
- [ ] Correct multi-display overlay behaviour.
- [ ] Cursor halo and visualizer remain smooth.

**Gate:** ownership improves without coupling clocks.

## Phase 9 — Local Transition Completion

- [ ] Source/destination/start/duration/easing only.
- [ ] Finalize locally after completed paint.
- [ ] Release source/temporary resources.
- [ ] No terminal transaction or pipeline acknowledgement.
- [ ] Test interruption, resize, Settings, Edit, topology.

**Gate:** transition completion is local and leak-free.

## Phase 10 — Remove Temporary/Legacy Scaffolding

- [ ] Remove dynamic forwarding.
- [ ] Remove duplicate runtime paths.
- [ ] Remove dead retry/backoff state.
- [ ] Remove obsolete metrics.
- [ ] Remove or migrate inert `workers.fft` settings/default leaves after a compatibility audit; do not restore a separate FFT process without contrary latency and reliability evidence.
- [ ] Prove no silent fallback.
- [ ] Keep one understandable runtime path.

**Gate:** code matches target architecture and no removed compatibility path remains silently active.

## Phase 11 — Full Validation

- [ ] Normal 30-minute run.
- [ ] Two-hour soak.
- [ ] Spectrum and Bubble fidelity review.
- [ ] CPU background load.
- [ ] Disk/decode background load.
- [ ] GPU background load.
- [ ] Mixed hostile load.
- [ ] Settings/Edit during animation.
- [ ] Multi-display/topology scenarios.
- [ ] RAM/VRAM plateau.
- [ ] p99/max frame gates.

**Gate:** candidate is better than both evidence versions.

## Phase 12 — Release Preparation

- [ ] Update canonical docs to match code.
- [ ] Archive benchmark evidence.
- [ ] Record budgets and known limitations.
- [ ] Identify rollback commit.
- [ ] Tag release candidate.
- [ ] Preserve donor history and evidence.

## Current Phase

```text
Priority: P0 — Phase 4 ImageWorker Shared-Memory Containment
Queued recovery phase: 5 — CPU and Task Reduction
Branch: main
Last evidence: Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md
```

### P0 — Phase 4 ImageWorker Shared-Memory Containment

Phase 4 is reopened. The deterministic cache/display/texture/PBO owner gate remains valid, but `phase4plus_a2f7bd89` exposed a separate child-process staircase: the sole ImageWorker grew from about 92 MiB to 770 MiB while the main process stayed broadly bounded. The approximately 31–32 MiB steps match one `3840×2158` RGBA frame. Phase 4 remains blocked until a real run proves worker, total RSS/private commit, tracked GL bytes, and driver VRAM plateau together.

- [x] Replace process-lifetime `_shared_memories` retention with one bounded transfer handoff; on Windows, keep only the published mapping open until the parent has attached, then close the worker handle immediately.
- [x] Consume the mapped RGBA view directly into a temporary `QImage`, perform exactly one `QImage.copy()` into Qt-owned memory, then release the source QImage/view and close/unlink in `finally`.
- [x] Tombstone timed-out and cancelled correlations and reclaim shared-memory payloads on late response, stale runtime generation, invalid payload, buffer overflow, supervisor shutdown, queue drain, and worker cleanup.
- [x] Replace blind buffered-response clears with payload-aware disposal and drain in-flight responses while stopping a worker.
- [x] Emit separate ImageWorker PID/RSS/VMS and shared-memory counters: `segments_created`, `segments_live`, `live_bytes`, `segments_consumed`, `segments_reclaimed_late`, and `unlink_failures`.
- [x] Add focused ownership regressions plus a real spawned-worker harness for normal consumption, timeout/late response, cancellation, runtime-generation rejection, buffered shutdown, publish failure, worker cleanup, queue drain, and orphan-name probing.
- [x] Pass 50 sequential `3840×2160` transfers: 50 consumed plus one forced shutdown-transfer reclaim, zero live bytes, zero unlink failures/orphans, worker RSS 89.2–90.1 MiB, and effectively zero post-warmup slope (-0.00009 MiB/cycle). Evidence: `logs/evidence_chest/phase4_shm_50x4k_codex/`.
- [x] Rerun the protected visualizer boundary after the transport and media/startup changes: 66 replay goldens verified; the current first-frame/mode-switch poison selection passed 21.
- [ ] Rerun the full Phase4plus scenario against `phase4plus_a2f7bd89` and require no approximately 31.6 MiB-per-image child slope, a labelled ImageWorker RSS plateau, total RSS/private commit plateau, bounded tracked GL bytes and driver VRAM, and unchanged visualizer/transition presentation.
- [ ] During that real run, manually review Spectrum transitions and Bubble loud-passage expansion; do not retune either mode unless mode-owned evidence fails rather than shared scheduling/presentation.
- [ ] Force Spotify artwork changes during 60 Hz and 165 Hz image transitions and verify `[PERF][MEDIA_ARTWORK]` shows one worker decode per local unique key, no UI pixmap/fade until every display is idle, newest-only coalescing, 60 Hz p95 at or below 25 ms with no repeated frames above 50 ms, and 165 Hz p95 at or below 16 ms with no sustained frames above 33 ms.
- [ ] On a cold startup, verify `[STARTUP_SEQUENCE]` orders first-frame readiness, terminal critical GL preparation, primary fade start/completion, then deferred shader/resource slices; require no deferred warmup record between `fade_started` and `fade_completed` and no multi-second event-loop stall.
- [ ] Confirm teardown leaves `segments_live=0`, `live_bytes=0`, `unlink_failures=0`, and no captured `srpss_img_*` name attachable after the worker stops.
- [ ] Only after the shared-memory real-run gate passes, reassess the 256 MiB CPU cache for raw/scaled co-retention, raw survival after a display-ready derivative exists, duplicate exact transforms, unconsumed prefetch outputs, and explicit current/next display-ready pinning.
- [ ] Amend the Phase 4 report with the new Phase4plus measurements and close Gate 4 only after the platform comparator passes.

**Non-goals:** do not change the multi-display compositor topology; attach shared-memory lifetime to compositor teardown; restart/recycle workers for reclamation; add repeated `gc.collect()`, process trimming, or memory-cache enlargement; or pull Phase 5 CPU/task-rate work into this fix.

**P0 gate:** the platform Phase4plus comparator shows worker and total memory plateau with zero live shared-memory bytes and unchanged Spectrum, Bubble, and transition presentation.

### Queued Phase 5 continuation

- [ ] Inventory every recurring operation and record trigger, frequency, thread, typical/p95 duration, allocations, queue delay, coalescing eligibility, hidden/static behavior, and cross-display duplication.
- [ ] Use `phase4plus_a2f7bd89` as the current pre-Phase-5 owner baseline after separating the shared-memory defect: median compute submission rate 163.8/s (56.6–175.1/s across sampled mode/transition intervals). Keep the earlier 101.2/s capture as historical comparison only; reduce measured owners without reducing visualizer fidelity.
- [ ] Preserve the 2026-07-28 visualizer diagnostic boundary: Bubble soft/medium/loud drift remained monotonic and all 66 replay goldens plus 17 first-frame/mode-switch poison oracles passed, while Spectrum's visible-smoothing concern correlated with 44–88 ms tick/latency gaps at image-transition boundaries. Remove the shared scheduling gaps in Phase 5 without retuning Spectrum smoothing or Bubble elasticity unless new mode-owned evidence appears.
- [ ] Establish idle, visualizer, transition, image-decode, and controlled background-load baselines for process CPU, GUI event-loop delay, task submissions, queue depth, callback tails, and duplicate/stale publication.
- [ ] Reconcile tracked CPU/GL bytes against RSS, private commit, and driver VRAM; specifically explain sustained RSS above roughly 900 MiB, multi-GiB private commit, driver VRAM above roughly 500 MiB, and ResourceManager unknown-byte entries without raising budgets.
- [ ] Remove tiny recurring pool jobs whose queue/callback overhead exceeds useful work; keep Qt/GL mutation on the GUI/context owner and coarse I/O/decode/measured computation on workers.
- [ ] Measure and attribute the two per-display adaptive presentation workers without optimizing or entrenching them; Phase 8 owns their removal in favor of GUI-local active-animation scheduling.
- [ ] Coalesce duplicate scene invalidations, visual render-state publication, geometry updates, stale image results, metadata refresh, and deletion requests without dropping audio impulses, stop/release, topology, or settings events.
- [ ] Stop recurring work when its owner is hidden or static, and require near-zero idle general-pool submissions outside justified monitoring.
- [ ] Batch/vectorize only measured Python-heavy hotspots; do not add Python threads or multiprocessing without latency, memory, and GIL evidence.
- [ ] Rerun the protected visualizer replay/runtime lock and Phase 4 resource gate after each optimization slice; require lower task/CPU cost with equivalent or better p99 frame delivery and no new synchronization.
- [ ] Record the task inventory, before/after evidence, unsupported platform measurements, and direct rollback in `Docs/phase_reports/P05_CPU_TASK_REDUCTION.md`.

## Deferred Until Recovery Passes

- new production widget families;
- partial GL reinitialization;
- speculative quality scaling;
- architectural cleanup unrelated to measured recovery;
- donor feature promotion without isolated evidence.

## Plan Hygiene

- Remove completed detail after evidence is archived.
- Do not keep benchmark narratives here.
- Do not copy stable contracts from `Spec.md`.
- Do not add provider-specific feature backlogs.
- Do not rename this file.

USER TASK BOX. ADD ITEMS BELOW INTO PLANNED STEPS AND EMPTY BOX. NEVER EVER DELETE THIS BOX AS A WHOLE OR THESE INSTRUCTIONS, ONLY PROPERLY ADOPTED IDEAS, YA GOBLIN ASS BITCH.
#######
#######
