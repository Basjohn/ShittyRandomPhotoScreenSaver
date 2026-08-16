# SRPSS Architecture Roadmap

Last reconciled: 2026-08-16

## Purpose

This package is the maintained architecture, dependency and validation roadmap for
current `main`. It must not become a second active task list.

Historical commits remain negative controls, provenance and forensic references only.

## Authority Order

1. `Current_Plan.md` — unfinished work and immediate execution order.
2. `Spec.md` — stable product/architecture contracts.
3. `Docs/Guardrails.md` and focused guardrails — durable prohibitions.
4. `Docs/phase_reports/` — accepted detailed evidence for completed/active phase checkpoints.
5. this roadmap — owner model, dependencies, audit priorities and release gates.
6. `Future_Cleanup.md` — deferred cleanup, temporary-code removal and test debt.
7. `Docs/Historical_Bugs/` — solved incidents and anti-regression lessons.
8. `Docs/audits/OLD/` — historical audits only.

When documents appear to disagree, resolve them in that order. A phase report may contain
more detail than `Current_Plan.md`, but it does not own execution order.

## Current References

| Role | Reference |
|---|---|
| Working branch | `main` |
| Approved Bubble/Spectrum behaviour | `ff93461685476bd0657aa88312fc2e35e9037880` |
| Rejected persistent-lane negative control | `666624d421b08f978c5f610571a078570150a1e7` |
| Rejected paint-local Spectrum negative control | `ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9` |
| Active execution owner | `Current_Plan.md` |
| Current Phase 5 delivery evidence | `Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md` |
| Cleanup/test-debt owner | `Future_Cleanup.md` |

Do not freeze raw log/ZIP paths here. Durable interpretation belongs in the phase report;
`Current_Plan.md` points to the current accepted report.

## Current Architecture Reality

Phase 5 now has two explicitly separated delivery smells:

1. **publication-coupled visualizer presentation — proven material amplifier.**
   The same-process 2026-08-16 A/B/A run proves that suppressing only the auxiliary
   visualizer `QOpenGLWidget.update()` stream improves both the 165 Hz and 60 Hz
   compositors while logical visualizer state continues publishing.
2. **residual queued GUI dispatch without visualizers — proven existence, owner unknown.**
   A no-visualizer-from-start control improves further but still leaves the 165 Hz display
   below target with dispatch-pending skips dominating paint-pending skips.

Between them is one still-unassigned visualizer-family cost: the no-visualizer control is
better than a live-but-hidden visualizer, so logical-to-overlay preparation/commit must be
measured after the proven repaint-request owner is corrected.

Other current facts:

- adaptive-render wake opportunity is not the dominant current owner; downstream GUI/paint
  pending state rejects later deadlines;
- retained-current texture identity, retained-base presentation and redundant ordinary
  upload-copy work are closed;
- visualizer shader GPU time is far too small to explain the delivery loss;
- Settings/Edit/Diagnostic ownership and clock-shadow incidents remain solved regression contracts;
- absolute process RSS/private commit/driver VRAM still requires separate owner-level attribution;
- Phase 8 one-surface-per-display work is **not** justified by the A/B/C evidence.

## Audit Priority

The compact priority ledger is `00_INDEX_AND_LIVE_CHECKLIST.md`.

For Phase 5 delivery work, the dependency order is:

```text
P0 remove completed diagnostic scaffolding
    ↓
P1 lock fidelity/presentation tests
    ↓
P2 correct publication-coupled presentation requests
    ↓
P3 measure remaining visualizer handoff/preparation cost
    ↓
P4 name/fix residual non-visualizer queued GUI dispatch
    ↓
resume lower-leverage Phase 5 resource/debris work
```

Exact checkboxes live only in `Current_Plan.md`.

## Operating Principle

**Prepare → Commit → Persist → Present**

- Prepare thread-safe I/O, parsing, serialization and finite pure-data compute away from GUI.
- Commit only Qt/QPixmap/GL-affine state on the GUI/context owner.
- Persist durable state through ordered/background owners with explicit flush semantics.
- Present already-integrated state without turning paint/update into a simulation clock or producer acknowledgement.

## Roadmap Documents

- `00_INDEX_AND_LIVE_CHECKLIST.md` — compact status and audit priority ledger.
- `01_EXECUTIVE_AUDIT_AND_DECISIONS.md` — current root findings and architecture decisions.
- `02_CODEX_OPERATING_CONTRACT.md` — execution discipline.
- `03_WORK_ORDER_AND_PHASE_GATES.md` — dependency order.
- `04_TARGET_ARCHITECTURE_AND_OWNERSHIP.md` — target owner map.
- `05_VISUALIZER_FIDELITY_CONTRACT.md` — protected visual behaviour/timing.
- `06_PRESENTATION_AND_COMPOSITOR_DESIGN.md` — presentation boundary and current proven seam.
- `07_GL_LIFECYCLE_AND_RECONFIGURATION.md` — durable GL/lifecycle ownership.
- `08_CPU_THREADING_AND_WORKLOAD_PLAN.md` — threading/UI workload architecture.
- `09_MEMORY_GPU_RESOURCE_AND_CACHE_PLAN.md` — memory/VRAM/GPU/cache work.
- `10_HISTORICAL_CANDIDATE_LESSONS.md` — historical negative controls.
- `11_GUARDRAILS_AND_PROHIBITED_PATTERNS.md` — roadmap-level prohibitions.
- `12_TEST_AND_BENCHMARK_PROTOCOL.md` — evidence method and mixed-refresh gates.
- `13_EVIDENCE_CHEST_AND_LOG_GUIDE.md` — evidence/log routing.
- `14_FAILURE_TRIAGE_MAP.md` — owner-oriented triage.
- `15_COMPLETION_AND_RELEASE_GATES.md` — release acceptance.

## Definition Of Success

Current approved visual behaviour survives stronger temporal/installed validation; the
proven presentation-request amplifier is removed without cadence hacks; remaining
visualizer and non-visualizer GUI delivery owners are named; lifecycle remains
deterministic/fail-closed; GPU/CPU/memory have named owners; and canonical `main.py`
passes hostile/soak validation with an appropriate screensaver footprint.
