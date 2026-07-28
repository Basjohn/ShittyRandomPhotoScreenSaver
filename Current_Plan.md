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
- [x] **Phase 3 / Gate 3:** full stop/destroy/recreate lifecycle, generation-and-manager stale-work rejection, strict owner-context GL deletion, and 50 Settings + 50 Edit + 50 mixed hostile cycles are complete without fallback, affinity errors, stale publication, or stopped-resource growth. See `Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md`.


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
- [ ] Remove or migrate inert `workers.fft` settings/default leaves after a compatibility audit; do not restore a separate FFT process without contrary latency and reliability evidence.
- [ ] Bound and rotate the Reddit helper log before oversized-log startup failure.
- [ ] Expire/reconcile `.bridge_ready` and URL queue state so stale files cannot block helper recovery.
- [ ] Verify and correct the ProgramData ACL/ownership creation path so administrator takeover is not required.
- [ ] Add automated helper recovery coverage for an oversized log, stale bridge signal, queued URLs, and restricted ProgramData ownership.
- [ ] Prove no silent fallback.
- [ ] Keep one understandable runtime path.

**Gate:** code matches target architecture and adopted helper recovery failures are reproducibly closed.

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
Phase: 4 — Baseline Memory/VRAM Containment
Branch: main
Last evidence: Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md
```

- [-] Trace the baseline image path and record every encoded, decoded, oriented, scaled, `QImage`, `QPixmap`, upload-buffer, texture, FBO, PBO, transition, preview, and fallback representation with its owning object and release event.
- [ ] Reconcile Phase 1 logical byte metrics with the real cache, transition, compositor, and visualizer owners; identify unexplained or count-only retention before changing budgets.
- [ ] Add deterministic alternating large/small image churn with aspect-ratio, transition, resize, and Settings/Edit cases, recording RAM plus exact application-owned CPU/GL bytes.
- [ ] Replace unbounded or count-only CPU image caches with immutable byte-accounted entries and conservative eviction without moving GUI-only objects onto workers.
- [ ] Release obsolete transition sources, upload staging, replaced textures, and resized FBOs immediately at their current ownership seams.
- [ ] Remove duplicate per-display CPU copies only where source identity, transform, dimensions, and quality are exactly equal; preserve the baseline presentation topology.
- [ ] Run plateau and pressure evidence, require no monotonic RAM/VRAM growth, rerun the Phase 2 visualizer lock, and record rollback in `Docs/phase_reports/P04_*.md`.
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