# SRPSS Architecture Roadmap

Last reconciled: 2026-08-15

## Purpose

This package is the maintained architecture and validation roadmap for SRPSS. It is
written for **current `main`**.

Historical baseline/candidate commits are retained only as negative controls,
provenance, and forensic evidence when they answer a specific question. They are not
implementation sources.

## Authority Order

1. `Current_Plan.md` — unfinished work and immediate execution order.
2. `Spec.md` — stable product/architecture contracts.
3. `Docs/Guardrails.md` and focused guardrails — durable prohibitions.
4. this roadmap — ownership model, phase dependencies, measurements and release gates.
5. `Docs/Historical_Bugs/` — solved failure evidence and anti-regression lessons.
6. `Docs/audits/OLD/` — historical audits only.

## Current References

| Role | Reference |
|---|---|
| Working branch | `main` |
| Approved Bubble/Spectrum behaviour | `ff93461685476bd0657aa88312fc2e35e9037880` |
| Rejected persistent-lane negative control | `666624d421b08f978c5f610571a078570150a1e7` |
| Rejected paint-local Spectrum negative control | `ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9` |
| Historical candidate/reference | `7376bb9bb380253f3bd14079e65d7bdbca062fad` |
| Active evidence pointer | `Current_Plan.md` |
| Historical mixed-load causal checkpoint | `logs/evidence_chest/08_09_ca830d7_14_59/` |

Do not duplicate a rapidly changing "current evidence" path here. `Current_Plan.md` owns
the exact active run and next gate.

Settings/Edit/Diagnostic ownership and clock-shadow incidents are solved. Their rules
remain architecture contracts; their investigations are not active Phase 5 work.

## Current Architecture Reality

- GUI/request delivery remains the dominant unresolved frame-tail problem: repeated stalls show request age much larger than paint duration.
- Retained-current → next-old texture identity is repaired and validated; it is no longer an active root-cause hypothesis.
- The previous steady full-surface QPainter base draw is replaced by exact retained-texture presentation where capability/cache identity allows it.
- Redundant ordinary upload conversion/source-buffer copies are removed; direct native RGB32/ARGB32 read-only upload is validated and steady pair warm is substantially cheaper.
- Routine logging and ordered settings durability are process-owned background writers; Reddit/Weather/Gmail preparation and shared static overlay-cache preparation have moved off avoidable GUI work where proven.
- Heavy owner-context GL timer queries are isolated behind explicit sampled `--gpu-timing`; ordinary `--perf` performs no GL query-driver calls.
- The ordinary-PERF control did not recover the remaining delivery regression. Profiling overhead is no longer the active suspect.
- The next delivery gate is stage attribution: adaptive-render wakeup lateness versus queued GUI dispatch waiting versus already-dispatched paint waiting.
- Bubble/Spectrum worker/paint/GPU costs remain too small to explain the largest delivery stalls. Their authored logical timing stays protected.
- Absolute process RSS/private commit/driver VRAM still exceeds tracked application ownership enough to justify continued owner-level attribution.
- Temporary compatibility/fallback architecture remains a cleanup target only after call-graph and runtime proof.

## Operating Principle

**Prepare → Commit → Persist**

- Prepare thread-safe I/O, parsing, serialization and finite compute away from GUI.
- Commit only Qt/QPixmap/GL-affine state on the GUI/context owner.
- Persist durable state through ordered/background owners with explicit flush semantics.
- Paint prepared state; do not discover disk/JSON/heavy static construction inside paint.

## Checkpoint Principle

A clean commit after a risky slice is a rollback point, not a mandatory human stop.

Focused tests/evidence pass → continue. Stop on failure, contradictory evidence, dirty or
conflicted repository state, or a visual change that genuinely requires operator
judgement.

## Roadmap Documents

- `00_INDEX_AND_LIVE_CHECKLIST.md` — compact status ledger.
- `01_EXECUTIVE_AUDIT_AND_DECISIONS.md` — current architecture decisions.
- `02_CODEX_OPERATING_CONTRACT.md` — execution discipline.
- `03_WORK_ORDER_AND_PHASE_GATES.md` — dependency order.
- `04_TARGET_ARCHITECTURE_AND_OWNERSHIP.md` — target owner map.
- `05_VISUALIZER_FIDELITY_CONTRACT.md` — protected visual behaviour/timing.
- `06_PRESENTATION_AND_COMPOSITOR_DESIGN.md` — presentation boundary and future surface design.
- `07_GL_LIFECYCLE_AND_RECONFIGURATION.md` — durable GL/lifecycle ownership.
- `08_CPU_THREADING_AND_WORKLOAD_PLAN.md` — threading/UI workload architecture.
- `09_MEMORY_GPU_RESOURCE_AND_CACHE_PLAN.md` — memory/VRAM/GPU/cache work.
- `10_HISTORICAL_CANDIDATE_LESSONS.md` — historical candidate lessons/negative controls.
- `11_GUARDRAILS_AND_PROHIBITED_PATTERNS.md` — roadmap-level prohibitions.
- `12_TEST_AND_BENCHMARK_PROTOCOL.md` — evidence method.
- `13_EVIDENCE_CHEST_AND_LOG_GUIDE.md` — evidence/log routing.
- `14_FAILURE_TRIAGE_MAP.md` — owner-oriented triage.
- `15_COMPLETION_AND_RELEASE_GATES.md` — release acceptance.

## Definition Of Success

The architecture succeeds when current approved visual behaviour survives stronger
temporal and installed validation; GUI work is limited to real affinity requirements;
delivery stalls have named stage/owners rather than cadence workarounds; GPU/CPU/memory
costs have named owners; lifecycle remains deterministically fail-closed; logging remains
useful without becoming the measured workload; no hidden compatibility/fallback authority
remains without a current contract; and canonical `main.py` passes hostile/soak validation
with a resource footprint appropriate for a screensaver.
