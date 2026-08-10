# SRPSS Architecture Roadmap

Last reconciled: 2026-08-10

## Purpose

This package is the maintained architecture and validation roadmap for SRPSS. It is
written for **current `main`**. Historical baseline/candidate commits are retained only
as negative controls, provenance, and forensic evidence when they answer a specific
question; they are not implementation sources or an extraction seam that current work must follow.

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
| Documentation checkpoint | `5da02b050ecce84384f51431ee3b4282d6f5c5de` |
| Approved Bubble/Spectrum behaviour | `ff93461685476bd0657aa88312fc2e35e9037880` |
| Rejected persistent-lane negative control | `666624d421b08f978c5f610571a078570150a1e7` |
| Rejected paint-local Spectrum negative control | `ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9` |
| Historical candidate/reference | `7376bb9bb380253f3bd14079e65d7bdbca062fad` |
| Current mixed-load evidence | `logs/evidence_chest/08_09_ca830d7_14_59/` |

Settings/Edit/Diagnostic ownership and clock-shadow incidents are solved. Their rules
remain architecture contracts; their investigation is not active work.

## Current Architecture Reality

- GUI availability is the dominant observed delivery problem: request age is much larger than paint cost in the current mixed-load evidence.
- The image setter has a proven steady texture identity/reuse failure: retained current is not found as the next old texture, causing avoidable two-texture warm/upload work.
- Routine logging and some settings/service/cache work still execute avoidable I/O/data preparation on the GUI owner.
- Active-display process GPU busy is material (median `10.8%`, p95 `27.8%`, max `32.9%` in the current evidence) and needs owner-level attribution.
- The visualizer display is 60 Hz while captured overlay windows can approach ~100 state/update/paint operations per second. This is a presentation-rate investigation, not permission to lower visualizer logical cadence.
- Bubble/Spectrum timing is protected. Phase 5 first removes external starvation and cadence-neutral overhead; Phase 7 owns the state/presentation boundary.
- Temporary compatibility/fallback architecture is now an explicit simplification target when it has no current external/persistence contract.

## Operating Principle

**Prepare → Commit → Persist**

- Prepare thread-safe I/O, parsing, serialization and finite compute away from GUI.
- Commit only Qt/QPixmap/GL-affine state on the GUI/context owner.
- Persist durable state through ordered/background owners with explicit flush semantics.
- Paint prepared state; do not discover disk/JSON/heavy static construction inside paint.

## Checkpoint Principle

A clean commit after a risky slice is a rollback point, not a mandatory human stop.
Focused tests/evidence pass → continue. Stop on failure, contradictory evidence, or a
change whose visual result genuinely needs operator judgement.

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
GPU/CPU/memory costs have named owners; lifecycle remains deterministically fail-closed;
no hidden compatibility/fallback authority remains without a current contract; and
canonical `main.py` passes hostile/soak validation with a resource footprint appropriate
for a screensaver.
