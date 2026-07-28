# Current Plan

Last updated: 2026-07-28

Active work only.

Stable architecture belongs in `Spec.md`. Durable safety rules belong in `Docs/Guardrails.md`. Detailed compositor design belongs in `Docs/Compositor_Architecture.md`. Dated failures belong in `Docs/Historical_Bugs.md`.

## Recovery Boundary

```text
main (based on baseline 00edb57a3076b845cb8ee4b6cb7f36ea83411f0c)
donor/reference only: 7376bb9bb380253f3bd14079e65d7bdbca062fad
```

The donor is read-only reference material, never a merge target. Evidence archives remain under `logs/evidence_chest/`.
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


## Phase 3 — Lifecycle Safety

- [ ] Restore full stop/destroy/recreate semantics.
- [ ] Stop producers before GL teardown.
- [ ] Reject stale worker results.
- [ ] Delete GL resources on owner context/thread.
- [ ] Run repeated Settings cycles.
- [ ] Run repeated Edit cycles.
- [ ] Run mixed lifecycle cycles.
- [ ] Confirm zero context-affinity errors and zero resource accumulation.

**Gate:** lifecycle is repeatable and boring.

## Phase 4 — Baseline Memory/VRAM Containment

- [ ] Map all image representations and owners.
- [ ] Introduce byte-bounded CPU caches.
- [ ] Release obsolete transition resources.
- [ ] Release replaced/resized GL resources.
- [ ] Remove duplicate display copies where safely shareable.
- [ ] Prove stable RAM/VRAM plateau.

**Gate:** bounded explainable memory without changing presentation topology.

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
- [ ] Prove no silent fallback.
- [ ] Keep one understandable runtime path.

**Gate:** code matches target architecture.

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
Phase: 3 — Lifecycle Safety
Branch: main
Last evidence: Docs/phase_reports/P02_VISUALIZER_FIDELITY_LOCK.md
```

- [-] Inventory the real Settings, Edit, stop, display-destroy, and recreate call order and identify the single generation boundary.
- [ ] Advance the runtime generation at full reconfiguration admission so stale worker and deferred GUI callbacks cannot mutate the replacement display.
- [ ] Stop producers and disconnect/cancel callbacks before display-local GL teardown.
- [ ] Destroy visualizer and display GL resources synchronously on the owning GUI thread with the owning context current; fail loudly if context acquisition fails.
- [ ] Guard deferred warmup and image-result callbacks with both runtime generation and owning display identity.
- [ ] Add hostile in-flight callback, transition, Spectrum, and Bubble lifecycle cases.
- [ ] Run 50 Settings cycles, 50 Edit cycles, and 50 mixed cycles with zero context-affinity errors, dead-generation callbacks, or live-resource growth.
- [ ] Record lifecycle ordering, focused automation, runtime results, and rollback in `Docs/phase_reports/P03_*.md`.
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
!IMPORTANT! Reddit helper log doesn't cleanly keep size down and rotate, once it gets to 27mb the helper fails to launch and gives an error about the log. The expired files .bridge_ready may all contribute. To get Reddit links working in Screensaver mode again I had to: 1. Completely delete the logs. 2. Delete everything in url_queue and 3. Take ownership of ProgramData despite being an administrator. 

Unsure if 3 was required. 1 allowed the helper to start again but it did not save/launch urls. 2 and 3 were done together and fully resolved issues.
#######