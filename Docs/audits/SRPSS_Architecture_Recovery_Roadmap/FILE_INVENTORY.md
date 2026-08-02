# Roadmap Package Map

Last reconciled: 2026-08-02

The previous version stored SHA-256 and byte counts for every Markdown file. That inventory became false whenever any roadmap document was legitimately maintained and created unnecessary hash churn.

Git already provides exact content identity and history. This file now records purpose and authority instead.

## Core package

| File | Purpose |
|---|---|
| `README.md` | Package purpose, authority order, current references, and success definition |
| `00_INDEX_AND_LIVE_CHECKLIST.md` | Compact phase/status ledger; `Current_Plan.md` remains active task owner |
| `01_EXECUTIVE_AUDIT_AND_DECISIONS.md` | Historical baseline/donor audit plus current architecture decision amendments |
| `02_CODEX_OPERATING_CONTRACT.md` | Execution discipline for work on `main` |
| `03_WORK_ORDER_AND_PHASE_GATES.md` | Phase dependency model and reopened/current gates |
| `04_TARGET_ARCHITECTURE_AND_OWNERSHIP.md` | One-owner target model and current lifecycle/resource boundaries |
| `05_VISUALIZER_FIDELITY_CONTRACT.md` | Approved visual reference, all-mode protections, temporal goldens, and negative controls |
| `06_PRESENTATION_AND_COMPOSITOR_DESIGN.md` | One-cadence latest-state presentation and future compositor boundary |
| `07_GL_LIFECYCLE_AND_RECONFIGURATION.md` | Full teardown/recreate, R-53/R-56 corrections, barriers, and first-frame separation |
| `08_CPU_THREADING_AND_WORKLOAD_PLAN.md` | Evidence-led work reduction without persistent lanes or cadence/fidelity cuts |
| `09_MEMORY_GPU_RESOURCE_AND_CACHE_PLAN.md` | RAM/commit/VRAM definitions, current footprint, attribution, budgets, and quality boundary |
| `10_DONOR_EXTRACTION_MATRIX.md` | Reference-only donor lessons and current extraction policy |
| `11_GUARDRAILS_AND_PROHIBITED_PATTERNS.md` | Roadmap-level architecture rules and anti-patterns |
| `12_TEST_AND_BENCHMARK_PROTOCOL.md` | Equivalent scenarios, temporal/lifecycle/resource metrics, and pass gates |
| `13_EVIDENCE_CHEST_AND_LOG_GUIDE.md` | Original/current evidence identity, manifests, parser use, and epistemic rules |
| `14_FAILURE_TRIAGE_MAP.md` | Evidence-led routing from symptom to ownership seam |
| `15_COMPLETION_AND_RELEASE_GATES.md` | Final architecture, visualizer, lifecycle, performance, resource, product, and evidence gates |
| `ROADMAP_MANIFEST.json` | Machine-readable package references and authority metadata |

## Templates

| File | Purpose |
|---|---|
| `templates/BENCHMARK_REPORT_TEMPLATE.md` | Repeatable scenario/environment/timing/resource report |
| `templates/DECISION_RECORD_TEMPLATE.md` | Architecture decision, confidence, alternatives, consequences, validation, rollback |
| `templates/PHASE_REPORT_TEMPLATE.md` | Phase objective, invariants, changes, evidence, failures, and gate decision |
| `templates/VISUALIZER_CHANGE_DECLARATION.md` | Explicit user-authorized visual behaviour change record |

## External canonical dependencies

| Path | Role |
|---|---|
| `Current_Plan.md` | Active unfinished work and exact implementation order |
| `Spec.md` | Stable architecture/product contracts |
| `Docs/Guardrails.md` | Compact cross-cutting rules |
| `Docs/Guardrails/Visualizer_Presentation.md` | Focused visualizer cadence/presentation rules |
| `Docs/Historical_Bugs/` | Detailed dated incident evidence |
| `Docs/phase_reports/` | Completed phase evidence and implementation reports |
| `Docs/benchmark_reports/` | Benchmark summaries where present |
| `logs/evidence_chest/` | Raw/derived installed evidence |

## Historical audit boundary

`Docs/audits/OLD/` contains historical Architecture/Bubble/geometry/Oscilloscope audits. Those files may contain unique forensic value but are not current authority and are not part of the live roadmap maintenance surface.

## Integrity policy

- use Git commit/blob identity when exact content verification is needed;
- do not maintain hand-copied hashes for frequently edited documentation;
- canonical links must be repository-relative and use exact path capitalization;
- adding/removing a live roadmap file requires updating this map, `README.md`, and the live checklist/document order where applicable;
- do not add `/OLD` documents to active reading order unless a current task explicitly requires their historical evidence.