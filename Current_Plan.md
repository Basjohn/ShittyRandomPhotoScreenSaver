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
Priority: P0 — Phase 4 whole-application plateau and transition-collision validation
Queued recovery phase: 5 — CPU and Task Reduction
Branch: main
Last evidence: logs/evidence_chest/fresh_20260729_2233/
Owning report: Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md
```

### P0 — Phase 4 whole-application plateau and transition-collision validation

The 52-minute `fresh_20260729_2140` run remains the whole-process memory baseline: ImageWorker/shared-memory, tracked GL bytes, and driver VRAM were bounded, but main-process RSS, total RSS, and private commit retained positive post-warmup slopes (about +2.42, +2.54, and +3.87 MiB/min respectively). The shorter forced-collision run `fresh_20260729_2233` validates all three transition-time artwork changes as worker decode → newest-only queue → all-displays-idle apply with `ui_pixmap_ms=0.00`, but exposes a separate media-control presentation collision. A media-key track change launched a 1.35-second 60 Hz feedback fade, producing 30–38 full media-card paints versus roughly 2–6 in comparable transition windows while actual GL paint remained cheap. External Windows/Qt media routes now converge through one process-wide claim; transition-time feedback is one immediate static acknowledgement plus one managed clear; painter metadata publishes through one coalesced update without redundant Qt geometry setters; and repeated header-logo smooth scaling is cached. Display-change/double-click refreshes no longer invalidate an already-decoded in-flight generation. The 23:40 installed startup disproved the first reveal-only correction: generation 1 decoded and queued the image, transition idle discarded it after generation 2 began, and generation 2 then applied the same key without an image or pixmap. A stale pending generation is now retained only while its current query is in flight, so that query can authoritatively promote the same decoded image or replace it with a different key. Once a pixmap exists, startup artwork remains hidden until the card reveal completes and resumes once transition-idle. These corrections still require an installed dual-display comparator.

- [ ] Rerun the full installed dual-display scenario against `fresh_20260729_2140`; require ImageWorker/shared-memory, tracked GL bytes, driver VRAM, main RSS, total application RSS, and private commit all to settle into bounded post-warmup plateaus.
- [ ] Attribute any remaining main-process slope with synchronized CPU-cache, display-backing, GL-owner, main/worker/total RSS, and private-commit snapshots; do not infer containment from a bounded child alone.
- [ ] Force Spotify artwork and title changes with media Next/Previous during active 60 Hz and 165 Hz transitions. Require one accepted `[PERF][MEDIA_FEEDBACK] phase=ingress` command and immediate-route duplicates marked `duplicate_suppressed=True`; `mode=static` with exactly two paint requests and no `start_feedback_animation` label; one `event=decoded` per locally owned changed key; bounded `queued`/`replaced`/`flushing`/`applied` lifecycle records; no stale idle-flush discard; and no QPixmap/art-dependent layout/fade publication until every display is idle. Immediate painter metadata remains intentional, but `[PERF][MEDIA_PRESENTATION]` must show one bounded publication with `layout_mutations=0` for an unchanged fixed-card footprint. Media-card paint calls must remain near the no-track-change transition comparator rather than returning to the observed 30–38-paint burst.
- [ ] Trigger manual Next and Previous immediately before the old timer deadline. Require `[ROTATION] Timer rebased` after an accepted submission, `expiry_coalesced` before queue/cache/worker/prescale acquisition if image-change work is active, and no rebase after a rejected submission.
- [ ] Reload image sources while raw and scaled prefetch work is in flight; require stale generations neither repopulate the cleared cache nor release a newer same-key owner.
- [ ] Exercise previous-image replay on equal-transform displays and on differing source/DPR displays; require exact matches to share one processed/GUI backing and non-matches to remain distinct.
- [ ] On a cold startup, verify `[STARTUP_SEQUENCE]` orders first-frame readiness, terminal critical GL preparation, primary fade start/completion, then deferred shader/resource slices; require no deferred warmup record during the coordinated fade and no multi-second event-loop stall.
- [ ] On cold media startup with available artwork, require one decode; no `stale_idle_flush_generation` discard while the current query is in flight; optional `event=retained reason=awaiting_current_generation`; one apply with `pixmap_ready=True`; card fade completion before `[PERF][MEDIA_ARTWORK] event=fade_started reason=widget_reveal_complete`; visible artwork fade-in; and no stranded zero-opacity art. If a display transition overlaps card completion, require the same fade once at `reason=all_displays_idle`.
- [ ] Deliberately run Bubble loud passages, Spectrum transition boundaries, and Bubble → Spectrum → Bubble. Require the protected first-frame/mode-switch behavior and unchanged visual response; do not retune either mode unless mode-owned evidence fails.
- [ ] After the whole-process comparator, measure raw/scaled co-retention and unconsumed prefetch residency before deciding whether raw derivatives need explicit leases/retirement. Current display ownership does not justify CPU-cache pins; add none without a concrete readiness failure.
- [ ] Amend the Phase 4 report with the post-fix comparator, explain the remaining main-process owner or correct it, and close Gate 4 only after the complete platform plateau and presentation gate passes.

**Non-goals:** do not change the multi-display compositor topology; attach shared-memory lifetime to compositor teardown; restart/recycle workers for reclamation; add repeated `gc.collect()`, process trimming, or memory-cache enlargement; or pull Phase 5 CPU/task-rate work into this fix.

**P0 gate:** the installed comparator shows worker, main, total RSS/private commit, tracked GL bytes, and driver VRAM plateau together; shared-memory counters terminate at zero; artwork/rotation/media-feedback collisions are absent; and Spectrum, Bubble, and transition presentation remain unchanged.

### Queued Phase 5 continuation

- [ ] Inventory every recurring operation and record trigger, frequency, thread, typical/p95 duration, allocations, queue delay, coalescing eligibility, hidden/static behavior, and cross-display duplication.
- [ ] Use `fresh_20260729_2140` as the current pre-Phase-5 owner baseline: median compute submission rate 166.2/s, GUI event-loop p99 38.28 ms, and a 46.6 FPS tail interval on screen 1 with p95 56.40 ms despite comparatively cheap paint work. Keep `phase4plus_a2f7bd89` and the earlier 101.2/s capture as historical comparators only.
- [ ] Preserve the current visualizer boundary: Bubble loud response remained healthy and cheap in the fresh run, while Spectrum and a runtime mode switch were not exercised. Remove measured shared scheduling/delivery gaps in Phase 5 without retuning Spectrum smoothing or Bubble elasticity unless deliberate mode-owned evidence fails.
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
