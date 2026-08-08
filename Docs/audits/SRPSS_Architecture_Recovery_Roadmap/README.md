# SRPSS Architecture Recovery Roadmap

Last reconciled: 2026-08-08

## Purpose

This package records the architecture-recovery rationale, phase model, target ownership, validation rules, and release gates for **Shitty Random Photo Screen Saver (SRPSS)**.

It began as a comparison between behavioural baseline `00edb57` and donor/reference `7376bb9`. The project has since advanced well beyond that starting comparison. These documents must therefore be read as a maintained roadmap, not as instructions to return to an old branch or blindly complete an untouched original plan.

## Authority order

When documents disagree, use this order:

1. `Current_Plan.md` — active unfinished work, current evidence, and immediate implementation order.
2. `Spec.md` — stable product and architecture contracts.
3. `Docs/Guardrails.md` and focused guardrails — durable prohibitions and stop conditions.
4. this roadmap — architecture rationale, phase boundaries, target design, and validation gates.
5. `Docs/Historical_Bugs/` — dated failure evidence and anti-regression history.
6. `Docs/audits/OLD/` — historical audits only; never current authority.

The live checklist in `00_INDEX_AND_LIVE_CHECKLIST.md` is a compact roadmap status ledger. It must not duplicate the detailed active plan.

## Current Git and behavioural references

| Role | Reference |
|---|---|
| Working branch | `main` |
| Original recovery baseline | `00edb57a3076b845cb8ee4b6cb7f36ea83411f0c` |
| Pre-persistent-lane behaviour reference | `6f188adadabb77b1a9d47a0fe1685c86ad39fb77` |
| Rejected persistent-lane checkpoint | `666624d421b08f978c5f610571a078570150a1e7` |
| Restored executor behaviour | `4bde89e8e39177dc4dd7b5e64b9ac99256ab9486` |
| Current user-approved visual behaviour | `ff93461685476bd0657aa88312fc2e35e9037880` |
| Donor/reference only | `7376bb9bb380253f3bd14079e65d7bdbca062fad` |

`ff934616` is code-equivalent to `4bde89e` for Bubble/Spectrum behaviour and remains the visual approval authority until the user explicitly approves another exact commit.

Work is performed directly on `main`. Do not create recovery branches, forks, or pull requests unless the user explicitly changes that instruction.

## Current recovery reality

The original roadmap produced useful measurement, lifecycle, and resource-accounting work, but later installed evidence reopened important completion claims:

- shared audio analysis and Bubble were restored from rejected persistent lanes to the ordinary general COMPUTE executor;
- Bubble and Spectrum are currently user-approved and must not be retuned by infrastructure or memory work;
- Settings full teardown/recreation succeeds, and R-56 invalid-wrapper handling is mechanically repaired; installed Settings confirmation remains open;
- CUSTOM/Edit R-53 now retires the temporary session and queues immutable engine-owned admission on a later GUI turn; installed dual-display confirmation remains open;
- R-57 scaled-prefetch selection/removal ordering is mechanically repaired with the decisive preferred-index fixture; installed image/transition confirmation remains open;
- tracked resources may plateau while the absolute active footprint remains excessive: roughly 847–1074 MiB whole-app resident RAM, 2.86–3.17 GiB private commit, and 554–777 MiB dedicated VRAM in the latest evidence;
- stronger production-executor temporal visualizer goldens are still required despite the earlier logical replay package.

Therefore Phase 3 and Phase 4 retain valuable implemented architecture, but their installed closure is reopened under the current Phase 5 plan.

## Non-negotiable product priorities

Priority order:

1. visualizer fidelity and reactivity;
2. lifecycle safety;
3. frame pacing and perceived smoothness;
4. lower and bounded RAM/VRAM/commit;
5. CPU and task efficiency;
6. average FPS;
7. code elegance.

All supported visualizer modes are protected as a family. Aggregate load is presumed to come from shared/runtime ownership unless direct evidence proves a mode-specific owner. Bubble is not a default optimization target.

No resource target may be met by lowering perceivable fidelity, cadence, source sampling, resolution, buffer precision, transition quality, artwork/shadow quality, widget content, or first-frame responsiveness.

## How to use this package

For active work:

1. read `Current_Plan.md`;
2. read `00_INDEX_AND_LIVE_CHECKLIST.md`;
3. read the phase-specific roadmap document;
4. read the relevant focused guardrail and historical bug record;
5. inspect current `main`, not only baseline/donor code;
6. gather deterministic and installed evidence before claiming completion.

For architectural history, consult `01_EXECUTIVE_AUDIT_AND_DECISIONS.md` and `10_DONOR_EXTRACTION_MATRIX.md`.

For any visualizer-adjacent change, read `05_VISUALIZER_FIDELITY_CONTRACT.md` and `Docs/Guardrails/Visualizer_Presentation.md`.

For memory work, read `09_MEMORY_GPU_RESOURCE_AND_CACHE_PLAN.md`; plateau and absolute footprint are separate gates.

## Definition of success

Recovery succeeds only when:

- current approved visualizer behaviour survives deterministic temporal tests and installed user review;
- no producer waits for paint and no second presentation cadence exists;
- Settings and Edit repeatedly complete full stop–destroy–recreate with zero retired owners;
- Qt/PySide wrapper lifetime is handled explicitly;
- graph-based CUSTOM placement and replay remain intact;
- RAM, private commit, and VRAM both plateau and fall to evidence-backed reasonable levels;
- CPU/task work falls without mode-specific fidelity cuts;
- all GL creation and destruction occurs on the owner GUI/context thread;
- resource and whole-process usage gaps are explainable;
- canonical `main.py` passes hostile and long-duration validation, while shared package routes receive bounded no-capture smoke coverage;
- failed experiments and remaining weaknesses are recorded honestly.

Start with the live checklist, but treat `Current_Plan.md` as the active execution authority.
