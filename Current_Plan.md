# Current Plan

Last updated: 2026-07-30

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

- [-] Execute P5.0–P5.6 in order, preserving authored visualizer feel and measured frame delivery.
- [ ] Close the Phase 5 runtime gate with before/after evidence; implemented slices alone are not closure.

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
Phase 4 closure evidence: logs/evidence_chest/07_30_dc8d1741_00_26/
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
