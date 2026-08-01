# Current Plan

Last updated: 2026-08-01

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
- [x] **Phase 4 / Gate 4:** byte-bounded CPU/GL/image-worker ownership, whole-application plateau evidence, and transition-time startup-artwork/media-next presentation are closed. The older failed platform and collision captures remain in `Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md` as superseded evidence; unresolved CPU/frame-delivery/accounting diagnosis is Phase 5 work.

## Phase 5 — CPU and Task Reduction

Active checklist and evidence contract: `Docs/phase_reports/P05_CPU_TASK_REDUCTION.md`.

- [-] **P5.0 visualizer cadence:** compare Bubble and Spectrum task cadence, input-to-visible latency, loud-passage response, smoothing, and first-frame/mode-switch behaviour under 60 Hz, 165 Hz, irregular paint, transition, and GUI-stall scenarios.
  - [x] Validate the restored Bubble lane-free path: the latest installed run reached 50,106 offered / 50,106 submitted steps, no artificial cadence deferrals, cheap workers, and operator-confirmed restored reaction/elasticity.
  - [ ] Reduce Bubble task volume only through a design that preserves each discrete scheduler edge and the visible attack of every integrated logical step. The rejected 60 Hz/max-two attempt is recorded in the Phase 5 report and Historical Bugs.
  - [ ] Add a runtime-shaped source/discrete-edge-to-first-visible temporal oracle; final-state, ordering, task-cap, average-FPS, and worker-duration checks may not authorize reactive cadence work.
- [-] **P5.1 delivery tails:** investigate transition-time Qt/event-loop update delivery and request coalescing. The latest run recorded 286 owner-labelled gaps, all during transitions; 105 exceeded 50 ms, p95 was 84.43 ms, max was 109.4 ms, while paint and compute execution remained cheap.
- [-] **P5.2 latency truthfulness:** the impossible uptime-linear ERROR flood is eliminated; verify the remaining bounded, generation-matched 81–100 ms WARNING samples distinguish logical frame age from Qt delivery delay.
- [-] **P5.3 unchanged media:** prove unchanged polls perform no metadata publication, layout mutation, artwork work, or repaint while preserving changed-track and transition-time media feedback.
  - [ ] Remove the remaining one-shot post-start/rebuild unchanged publication (`metadata_changed=False`, `presentation_changed=False`, `layout_mutations=2`, `update_requested=True`) without disturbing first-track artwork/layout.
- [-] **P5.4 recreation ownership:** validate the non-reentrant destruction barrier and generation-owned ResourceManager, ThreadManager, timer, animation, subscription, dialog/Edit, widget, compositor, context, and surface cleanup through at least five alternating Settings/Edit rebuild cycles.
  - [x] Validate that closing Settings crosses its dialog destruction barrier and returns to a fresh application runtime. Two installed Settings cycles returned correctly and the operator confirmed ingress/exit behaviour.
  - [ ] Require every retiring generation to reach zero runtime roots, resources, timers, animations, subscriptions, queued/delayed callbacks, and tasks before replacement construction.
  - [ ] Eliminate or precisely release the `diagnostic_python_owners_remaining` set seen after the latest barriers (`WidgetManager`, `CustomLayoutManager`, and `FadeCoordinator`). QObject/resource zero is encouraging but does not satisfy the required retired-Python-root zero.
  - [ ] Require strict owner-context GL/display accounting to reach zero during teardown; do not weaken full stop/destroy/recreate or use event pumping, repeated GC, trimming, recycling, worker restart, cache growth, or warm-standby reuse.
  - [ ] Correlate equivalent settled states for main/worker/total RSS, private commit, dedicated VRAM, handles, threads, tracked bytes, first-frame readiness, and FadeCoordinator reveal; prove the per-cycle staircase is gone or identify the remaining live owner.
  - [ ] Preserve the undeniable latest improvement—generation 1/2/3 main RSS about 900.9/901.2/895.2 MiB, dedicated VRAM about 539.2/554.9/540.0 MiB, and ResourceManager total/unknown 58/47, 58/47, 56/45—while tracing the remaining private-commit and handle rise.
  - [ ] Give the one-shot compositor-ready signal explicit connection ownership so cleanup does not repeat an already-completed disconnect and emit PySide `RuntimeWarning`; preserve its first-frame readiness semantics.
  - [ ] Re-run first-frame and mode-switch poison checks around Bubble → Spectrum → Bubble, active transition, media polling/artwork, and pending image work. Destruction and authoritative-first-frame barriers must both pass before the existing FadeCoordinator reveal.
- [ ] **P5.5 cache representations:** only after P5.4 ownership is proven, audit raw/scaled/display co-retention, exact-transform duplication, unused prefetch results, and eviction churn without raising the 256 MiB limit.
- [-] **P5.6 logging hygiene:** verify cache entry detail stays in `screensaver_cache.log`, lifecycle ownership detail stays in `screensaver_lifecycle.log`, bounded summaries remain correlatable, and all warnings/errors remain in `screensaver.log`.
- [ ] Close the Phase 5 runtime gate with before/after evidence; implemented slices and deterministic automation alone are not closure.

**Gate:** materially lower CPU/task cost with equal-or-better p99/max frame delivery, preserved Spectrum/Bubble behaviour, bounded accounting, and no diagnostic-induced work.

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
Priority: Phase 5 — CPU and Task Reduction (in progress)
Branch: main
Temporary Phase 4 comparator: logs/evidence_chest/07_30_dc8d1741_00_26/ (mutable operator evidence)
Owning report: Docs/phase_reports/P05_CPU_TASK_REDUCTION.md
```

Phase 4's startup-artwork and media-next transition scenarios are closed by the current evidence capture. The Phase 5 report owns the remaining CPU/task, frame-delivery, cache-representation, and accounting uncertainty; it is deliberately not a runtime-closure claim.

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
