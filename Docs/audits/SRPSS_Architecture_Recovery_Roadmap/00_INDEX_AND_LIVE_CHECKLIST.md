# 00 — Index and Live Checklist

This file is the project control surface. Codex must keep it current.

## Status legend

- `[ ]` Not started
- `[-]` In progress
- `[x]` Complete and evidence-backed
- `[!]` Blocked or failed
- `[~]` Deferred by an explicit decision record

A phase may be marked `[x]` only after:

1. code is committed on `main` or an explicitly scoped child feature branch;
2. tests pass;
3. the required runtime scenario has been run;
4. the phase report records before/after evidence;
5. rollback instructions are known;
6. visualizer fidelity has not regressed.

## Authoritative document order

1. [Executive audit and decisions](01_EXECUTIVE_AUDIT_AND_DECISIONS.md)
2. [Codex operating contract](02_CODEX_OPERATING_CONTRACT.md)
3. [Work order and phase gates](03_WORK_ORDER_AND_PHASE_GATES.md)
4. [Target architecture and ownership](04_TARGET_ARCHITECTURE_AND_OWNERSHIP.md)
5. [Visualizer fidelity contract](05_VISUALIZER_FIDELITY_CONTRACT.md)
6. [Presentation and compositor design](06_PRESENTATION_AND_COMPOSITOR_DESIGN.md)
7. [GL lifecycle and reconfiguration](07_GL_LIFECYCLE_AND_RECONFIGURATION.md)
8. [CPU, threading, and workload plan](08_CPU_THREADING_AND_WORKLOAD_PLAN.md)
9. [RAM, VRAM, cache, and texture plan](09_MEMORY_GPU_RESOURCE_AND_CACHE_PLAN.md)
10. [Donor extraction matrix](10_DONOR_EXTRACTION_MATRIX.md)
11. [Guardrails and prohibited patterns](11_GUARDRAILS_AND_PROHIBITED_PATTERNS.md)
12. [Test and benchmark protocol](12_TEST_AND_BENCHMARK_PROTOCOL.md)
13. [Evidence chest guide](13_EVIDENCE_CHEST_AND_LOG_GUIDE.md)
14. [Failure triage map](14_FAILURE_TRIAGE_MAP.md)
15. [Completion and release gates](15_COMPLETION_AND_RELEASE_GATES.md)

Templates:

- [Phase report](templates/PHASE_REPORT_TEMPLATE.md)
- [Decision record](templates/DECISION_RECORD_TEMPLATE.md)
- [Benchmark report](templates/BENCHMARK_REPORT_TEMPLATE.md)
- [Visualizer change declaration](templates/VISUALIZER_CHANGE_DECLARATION.md)

---

# Live recovery checklist

## Phase 0 — Freeze, inventory, and evidence preservation

- [x] Freeze baseline evidence, archive hashes, environment limits, and source ownership inventory.
- [x] Establish the clean committed checkpoint on `main`, based on baseline `00edb57a3076b845cb8ee4b6cb7f36ea83411f0c`.

**Gate 0:** complete. Evidence and ownership inventory: `Docs/phase_reports/P00_FREEZE_INVENTORY_AND_EVIDENCE.md` and `Docs/phase_reports/P00_SOURCE_OWNERSHIP_INVENTORY.md`; clean checkpoint closure: `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.

## Phase 1 — Measurement foundation without behavioural change

- [x] Add bounded compositor frame-delivery metrics for render request, paint start/end, scene generation, and p50/p90/p95/p99/max tails.
- [x] Add the single app-owned, opt-in, bounded 20 Hz event-loop lateness sampler.
- [x] Add passive bounded task-category accounting.
- [x] Add exact logical CPU-image and known GL resource-byte accounting with resource metadata and lifecycle snapshots.
- [x] Preserve sampled, non-control diagnostics and no per-frame INFO output.
- [x] Validate overhead, real-GL enabled/disabled comparison, runtime-shaped visualizer coverage, parser outputs, and compilation.
- [x] Produce `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.

**Gate 1:** complete. Measurement is trustworthy, bounded in overhead, and does not change feel; validated results are recorded in `Docs/phase_reports/P01_MEASUREMENT_FOUNDATION.md`.
## Phase 2 — Visualizer fidelity lock before infrastructure changes

- [x] Build deterministic audio-input replay.
- [x] Capture representative input clips for silence, beats, sustained tones, transients, noisy music, and volume changes.
- [x] Capture baseline output series for Spectrum, Bubble, and every supported visualizer mode.
- [x] Record response latency, peak amplitude, decay curve, overshoot, elasticity, settling time, and low-energy behaviour.
- [x] Record baseline frame-state sequence independently of actual paint cadence.
- [x] Add perceptual review artifacts or replay videos for manual comparison.
- [x] Define pass tolerances per mode.
- [x] Prevent infrastructure tests from rewriting baseline golden data.
- [x] Require a visualizer change declaration for any intentional algorithm change.
- [x] Produce Phase 2 report.

**Gate 2:** complete. Visualizer feel is protected by deterministic all-mode replay, immutable baseline goldens, cadence-separation tests, quantitative metrics, and manually reviewed Spectrum/Bubble logical artifacts; see `Docs/phase_reports/P02_VISUALIZER_FIDELITY_LOCK.md`.

## Phase 3 — Restore and formalize lifecycle safety

- [x] Inventory Settings and Edit entry/exit order.
- [x] Restore full stop–destroy–recreate lifecycle semantics.
- [x] Stop producers before deleting render resources.
- [x] Disconnect callbacks before destruction.
- [x] Cancel or reject worker tasks without unbounded waits.
- [x] Destroy all GL resources on the owning GUI thread with the correct context current.
- [x] Destroy compositor surfaces only after child resources are gone.
- [x] Apply settings only after the old runtime is fully quiescent.
- [x] Recreate resources under a new runtime/context generation boundary.
- [x] Reject stale worker publications from prior generations and manager identities.
- [x] Run at least 50 Settings cycles.
- [x] Run at least 50 Edit cycles.
- [x] Run mixed Settings/Edit cycles.
- [x] Confirm zero `QOpenGLContext` cross-thread errors.
- [x] Confirm zero stopped-resource growth per cycle.

**Gate 3:** complete. Lifecycle is full-stop, repeatable, and fail-loud; 150 hostile Settings/Edit/mixed cycles completed with zero stale publications, context-affinity errors, or stopped-resource growth. See `Docs/phase_reports/P03_GL_LIFECYCLE_AND_RECONFIGURATION.md`.

## Phase 4 — Remove baseline resource leaks and establish budgets

- [x] Produce a resource-lifetime map for each displayed image.
- [x] Identify encoded, decoded, scaled, pixmap, upload-buffer, texture, FBO, and transition copies.
- [x] Define one owner for each representation.
- [x] Add byte-budgeted CPU caches.
- [x] Add byte-budgeted GPU resource storage.
- [x] Remove unbounded or count-only caches.
- [x] Release transition source resources after terminal presentation.
- [x] Release resized/replaced FBOs immediately on the GL thread.
- [x] Eliminate duplicate per-display copies where dimensions and transforms match.
- [x] Ensure ten minutes of cycling reaches a stable plateau.
- [x] Ensure Settings/Edit returns to the expected post-rebuild plateau.
- [x] Produce Phase 4 memory report.

**Gate 4:** complete. Exact application-owned CPU image/display and per-compositor texture/PBO bytes are bounded and explainable; the 45-cycle pressure run is non-monotonic and returns full owners to zero. Driver-reported VRAM remains the explicit Phase 11 platform gate. See `Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md`.

## Phase 5 — Reduce task rate and main-thread pressure

- [ ] Categorize all thread-pool tasks.
- [ ] Remove tiny recurring jobs whose queueing overhead exceeds their useful work.
- [ ] Batch visualizer numeric work where safe.
- [ ] Replace high-frequency Python loops with vectorized/native operations where measured.
- [ ] Coalesce duplicate state publications.
- [ ] Ensure only the latest non-critical visual state is retained.
- [ ] Stop scheduling work when state is static or hidden.
- [ ] Keep GUI and GL mutation on the GUI thread.
- [ ] Do not “solve” the GIL by adding more Python threads.
- [ ] Run idle, visualizer, transition, and background-load scenarios.
- [ ] Produce Phase 5 CPU report.

**Gate 5:** CPU and task rate fall without visualizer or pacing regression.

## Phase 6 — Introduce explicit GPU resource store

- [ ] Implement a small, metadata-first texture/FBO registry.
- [ ] Keep GL calls outside registry locks.
- [ ] Use explicit leases or references.
- [ ] Track share group/context generation.
- [ ] Implement deterministic deletion on the owning context.
- [ ] Add LRU eviction only for unleased resources.
- [ ] Add hard byte caps and diagnostic dumps.
- [ ] Prove shared reuse does not retain stale resources.
- [ ] Prove context recreation invalidates old entries.
- [ ] Compare against baseline and donor memory behaviour.
- [ ] Produce Phase 6 report.

**Gate 6:** Resource reuse is bounded and cannot outlive its GL generation.

## Phase 7 — Decouple visualizer simulation from presentation

- [ ] Define narrow immutable visualizer frame/state DTOs.
- [ ] Keep simulation cadence independent from image-transition cadence.
- [ ] Ensure visualizer producers never wait for paint acknowledgement.
- [ ] Coalesce publication to latest state.
- [ ] Preserve simulation timing during skipped paints.
- [ ] Preserve baseline response curves and elasticity.
- [ ] Remove any compositor-owned visualizer scheduler.
- [ ] Test under idle and artificial main-thread stalls.
- [ ] Produce Phase 7 fidelity and pacing report.

**Gate 7:** Visualizer feel survives presentation pressure.

## Phase 8 — Rebuild single-surface compositor narrowly

- [ ] Implement one compositor surface per display.
- [ ] Keep compositor free of simulation and application lifecycle logic.
- [ ] Feed it an immutable scene snapshot.
- [ ] Draw base image, optional transition, visualizer, and overlays in explicit order.
- [ ] Request continued frames only while something is animated.
- [ ] Use ordinary latest-state coalescing, not producer blocking.
- [ ] Remove compatibility attribute forwarding.
- [ ] Remove widget-shaped visualizer façade.
- [ ] Remove adaptive timer and paint-acknowledgement handshake.
- [ ] Confirm cursor halo and UI overlays remain smooth.
- [ ] Produce Phase 8 report.

**Gate 8:** Single-surface composition improves ownership without coupling clocks.

## Phase 9 — Simplify transition completion

- [ ] Replace distributed terminal transaction with local transition state.
- [ ] Define source, destination, start time, duration, easing, and active flag.
- [ ] Finalize destination on the first paint at or beyond completion.
- [ ] Release source/temporary resources immediately after finalization.
- [ ] Ensure no image pipeline, widget, worker, or scheduler acknowledgement is needed.
- [ ] Test interruption, replacement, resize, monitor change, Settings, and Edit.
- [ ] Produce Phase 9 report.

**Gate 9:** Transition completion is local, deterministic, and leak-free.

## Phase 10 — Remove obsolete compatibility and donor scaffolding

- [ ] Remove dynamic `__getattr__`/`__setattr__` forwarding.
- [ ] Remove `_LOCAL_ATTRS`-style compatibility state registries.
- [ ] Remove widget-instance free-function seams.
- [ ] Remove dead retry/backoff branches.
- [ ] Remove obsolete overlay/widget implementation only after parity proof.
- [ ] Remove stale diagnostics that measure deleted machinery.
- [ ] Confirm no hidden fallback silently activates old architecture.
- [ ] Produce Phase 10 report.

**Gate 10:** One understandable runtime path remains.

## Phase 11 — Full regression, soak, and hostile-load validation

- [ ] Run all deterministic visualizer replays.
- [ ] Run 30-minute normal screensaver scenario.
- [ ] Run 2-hour image-cycling soak.
- [ ] Run background CPU, disk, GPU, and mixed-load scenarios.
- [ ] Run repeated Settings/Edit cycles during active visualizer and transitions.
- [ ] Run monitor sleep/wake, resolution change, and display reconnect scenarios where supported.
- [ ] Verify no monotonically increasing RAM/VRAM.
- [ ] Verify p99 and maximum frame gaps meet gates.
- [ ] Verify visualizer manual review.
- [ ] Produce final benchmark report.

**Gate 11:** The recovery is demonstrably better than both evidence versions.

## Phase 12 — Release preparation

- [ ] Update architecture documentation to match actual code.
- [ ] Archive benchmark artifacts.
- [ ] Record final resource budgets.
- [ ] Record known limitations.
- [ ] Record rollback commit.
- [ ] Tag release candidate.
- [ ] Do not merge donor branch.
- [ ] Do not delete evidence or donor history.

**Gate 12:** Release candidate is reproducible and auditable.

---

# Current global blockers

- [x] Logged baseline and donor runtime timelines are documented; uncontrolled external load remains an evidence limitation.
- [ ] Deterministic visualizer input capture does not yet exist.
- [x] Phase 1 exact logical CPU-image and known application-owned GL byte accounting is available; broader plateau work remains Phase 4.
- [x] Baseline and donor GL lifecycle ownership maps are recorded in the Phase 0 ownership inventory.
- [x] Phase 1 task categories are recorded with a bounded `other` overflow bucket; reduction remains Phase 5.

# Decisions that require explicit approval before changing

- Visualizer equations, smoothing, decay, spring, elasticity, normalization, amplitude mapping, or mode-specific behaviour.
- User-visible transition timing or easing.
- Image quality, scaling, crop, color handling, or fidelity.
- Cache budgets that materially reduce image quality or cause repeated decode thrashing.
- Removal of a supported visualizer mode.
- Any plan to reintroduce partial GL reinitialization.
- Any producer-to-paint blocking handshake.
