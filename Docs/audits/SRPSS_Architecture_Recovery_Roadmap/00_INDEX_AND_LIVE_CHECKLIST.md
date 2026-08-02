# 00 — Index and Live Checklist

Last reconciled: 2026-08-02

This file is the compact status ledger for the architecture roadmap. Detailed active tasks belong in `Current_Plan.md`; completed evidence belongs in phase reports and historical bug records.

## Status legend

- `[ ]` not started
- `[-]` active
- `[x]` complete with accepted evidence
- `[!]` reopened, failed, or blocked
- `[~]` explicitly deferred

A roadmap phase can have implemented architecture while still being reopened by later installed evidence. Do not treat an old `[x]` or phase report as permission to ignore a newer failure.

## Authority and references

```text
working branch:                 main
original recovery baseline:     00edb57a3076b845cb8ee4b6cb7f36ea83411f0c
approved visual behaviour:      ff93461685476bd0657aa88312fc2e35e9037880
restored executor behaviour:    4bde89e8e39177dc4dd7b5e64b9ac99256ab9486
rejected persistent lane:       666624d421b08f978c5f610571a078570150a1e7
rejected Spectrum smoothing:    ebfec397fb2ae0bbc1f3e95c5298c0e7d6ff1db9
donor/reference only:           7376bb9bb380253f3bd14079e65d7bdbca062fad
active task owner:              Current_Plan.md
latest installed evidence:      logs/evidence_chest/08_02_3877b2c7_20_27/
```

## Document order

1. [Executive audit and current decisions](01_EXECUTIVE_AUDIT_AND_DECISIONS.md)
2. [Operating contract](02_CODEX_OPERATING_CONTRACT.md)
3. [Work order and phase gates](03_WORK_ORDER_AND_PHASE_GATES.md)
4. [Target architecture and ownership](04_TARGET_ARCHITECTURE_AND_OWNERSHIP.md)
5. [Visualizer fidelity contract](05_VISUALIZER_FIDELITY_CONTRACT.md)
6. [Presentation and compositor design](06_PRESENTATION_AND_COMPOSITOR_DESIGN.md)
7. [GL lifecycle and reconfiguration](07_GL_LIFECYCLE_AND_RECONFIGURATION.md)
8. [CPU, threading, and workload plan](08_CPU_THREADING_AND_WORKLOAD_PLAN.md)
9. [RAM, VRAM, resource, and cache plan](09_MEMORY_GPU_RESOURCE_AND_CACHE_PLAN.md)
10. [Donor extraction matrix](10_DONOR_EXTRACTION_MATRIX.md)
11. [Guardrails and prohibited patterns](11_GUARDRAILS_AND_PROHIBITED_PATTERNS.md)
12. [Test and benchmark protocol](12_TEST_AND_BENCHMARK_PROTOCOL.md)
13. [Evidence chest and log guide](13_EVIDENCE_CHEST_AND_LOG_GUIDE.md)
14. [Failure triage map](14_FAILURE_TRIAGE_MAP.md)
15. [Completion and release gates](15_COMPLETION_AND_RELEASE_GATES.md)

Templates are under `templates/`.

# Roadmap status

## Phase 0 — Freeze, inventory, and evidence preservation

- [x] Original baseline/donor evidence, hashes, ownership inventory, and recovery checkpoint were recorded.
- [x] Historical phase reports remain valid as the starting forensic record.

**Current interpretation:** complete historical foundation. It does not define the working branch or active behavioural baseline today.

## Phase 1 — Measurement foundation

- [x] Bounded frame, event-loop, task, CPU-image, GL-resource, lifecycle, and usage instrumentation exists.
- [x] Diagnostics are intended to remain sampled and non-controlling.
- [!] Whole-process attribution remains incomplete: current RSS/private-commit/VRAM substantially exceed tracked application-owned bytes.

**Current interpretation:** measurement plumbing exists; absolute-memory attribution is active work.

## Phase 2 — Visualizer fidelity lock

- [x] Deterministic logical replay and versioned baseline artifacts were created.
- [x] Infrastructure changes are not allowed to rewrite visualizer behaviour silently.
- [!] The original logical package did not prevent rejected scheduler/cadence regressions.
- [!] A stronger production-executor temporal package, first-visible response checks, known-bad negative controls, and exact installed approval manifest remain required under P5.0.
- [x] `ff934616` is the current user-approved Bubble/Spectrum behavioural authority.

**Current interpretation:** logical protection exists; temporal and operator-approval protection is reopened.

## Phase 3 — Full lifecycle and GL ownership

- [x] Full stop–destroy–recreate, owner-context GL deletion, generation rejection, and destruction barriers were implemented.
- [x] Settings now completes full teardown/recreation in current installed evidence.
- [!] R-56: the Settings close path retouches an already-deleted `SettingsDialog` wrapper.
- [!] R-53: CUSTOM/Edit begins full teardown synchronously from inside the retiring manager save graph and fails closed on two surviving `CustomLayoutManager` wrappers.
- [ ] Repair Edit admission by persisting/retiring the temporary edit session, returning from its frames, then queueing one engine-owned immutable reload intent.
- [ ] Preserve full reinit, graph-based placement/replay, generation barriers, and authoritative-first-frame reveal.

**Current interpretation:** architecture retained; installed lifecycle closure reopened.

## Phase 4 — Resource containment

- [x] CPU image caches, textures, PBOs, and shared-memory transfer ownership gained explicit accounting and bounded policies.
- [x] Known historical monotonic image/worker/GL leaks were corrected and recorded.
- [x] Full display teardown can reduce tracked GL bytes to zero and dedicated VRAM to near idle-driver levels.
- [!] Active steady-state usage remains excessive: roughly 847–1074 MiB whole-app RSS, 2.86–3.17 GiB private commit, and 554–777 MiB dedicated VRAM in latest evidence.
- [!] Plateau is not sufficient; absolute physical RAM, commitment, and VRAM must fall without visible quality loss.
- [ ] Attribute the gap between tracked resources and whole-process usage before changing budgets or introducing trimming/recycling.

**Current interpretation:** tracked containment implemented; whole-process efficiency and explainability reopened.

## Phase 5 — CPU, task, delivery, recreation, and resource recovery

- [-] Active phase. `Current_Plan.md` is the detailed owner.
- [x] Rejected persistent audio/Bubble lanes were removed from production.
- [x] Ordinary general COMPUTE executor behaviour was restored and visually approved.
- [x] Rejected paint-local Spectrum smoothing was reverted and documented.
- [ ] Create the stronger temporal visualizer approval package.
- [ ] Repair R-57 scaled-prefetch selection/removal ordering.
- [ ] Repair R-56 Settings wrapper lifetime.
- [ ] Repair R-53 CUSTOM/Edit admission and deterministic shell callback retirement.
- [ ] Establish clean alternating lifecycle cycles before drawing final leak conclusions.
- [ ] Attribute and lower absolute RAM/private-commit/VRAM while preserving perceivable fidelity.
- [ ] Reduce only measured duplicate, idle, unchanged, allocation, callback, logging, and representation work.
- [ ] Validate all supported visualizer modes against the shared restored source.

**Gate 5:** user-approved visual behaviour preserved; lifecycle complete; task/CPU work reduced; memory both plateaus and reaches an evidence-backed reasonable level; normal and Media Center installed evidence passes.

## Phase 6 — Explicit GPU resource store

- [~] Future architecture work.
- [ ] Reassess necessity against the current per-compositor ownership and measured active-VRAM gap before implementation.
- [ ] Any store must remain metadata-first, byte-bounded, lease-based, context-generation aware, and incapable of GL calls under registry locks.

## Phase 7 — Visualizer/presentation decoupling

- [~] Future architecture work after stronger goldens.
- [ ] Preserve the accepted ordinary executor and logical integration semantics.
- [ ] No second cadence, paint acknowledgement, paint-local authoritative mutation, or compositor-owned visualizer scheduler.

## Phase 8 — Narrow one-surface compositor

- [~] Future architecture work.
- [ ] One surface per display remains a product/architecture target only if it can be implemented without importing donor orchestration or harming visual fidelity.

## Phase 9 — Local transition completion

- [~] Future architecture work.
- [ ] Completion stays local, deterministic, and resource-releasing; no producer/pipeline terminal acknowledgement.

## Phase 10 — Temporary and legacy scaffolding removal

- [~] Future cleanup after current recovery gates.
- [ ] Remove only after production-use, dynamic-import, frozen-build, fallback, and rollback audits.

## Phase 11 — Hostile and long-duration validation

- [ ] Normal and Media Center variants.
- [ ] Idle, visualizer, transitions, combined work, CPU/disk/GPU/mixed load, Settings/Edit during activity, display topology, and long soak.
- [ ] Exact environment and source/cache state recorded.

## Phase 12 — Release and documentation

- [ ] Canonical docs match code and current evidence.
- [ ] Remaining weaknesses and provisional budgets stated honestly.
- [ ] Rollback point and release candidate identified.

# Immediate blockers summary

| ID | State | Required result |
|---|---|---|
| P5.0 | Open | Strong temporal visualizer goldens and installed approval manifest |
| R-53 | Blocking | Edit full reinit admitted after temporary session retirement; zero manager survivors |
| R-56 | Open | No post-modal calls on invalid `SettingsDialog` wrapper |
| R-57 | Open | Stable scaled-prefetch selection/removal with exact regression fixture |
| Memory | Open | Explain and reduce whole-app RSS/commit/VRAM without fidelity cuts |

Do not add new active detail here when it belongs in `Current_Plan.md`.