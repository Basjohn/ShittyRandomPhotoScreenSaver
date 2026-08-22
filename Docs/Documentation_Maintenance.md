# Documentation Maintenance

Last updated: 2026-08-22

Rules for keeping SRPSS documentation useful to coding agents during and after architecture changes.

## 1. Canonical roles

| Document | Role |
|---|---|
| `Current_Plan.md` | current sequence/work admission + clearly marked migration phase closure/rationale |
| `Spec.md` | durable product/architecture contracts |
| `Docs/Compositor_Architecture.md` | accepted runtime presentation design |
| `Docs/Guardrails.md` + focused guardrails | durable stop rules |
| `Index.md`, `Docs/Contracts.md` | routing/current owner map |
| current evidence reports | measurements/checkpoint evidence |
| phase reports/Historical_Bugs | historical evidence |
| `Future_Cleanup.md` | deferred debt/deletion ledger |
| `Future_Work.md` | explicitly deferred features/experiments |

## 2. `Current_Plan.md` role

`Current_Plan.md` owns **what work is admitted now**.

It may also retain clearly marked completed-phase closure/rationale when that history is useful for
migration continuity and prevents agents from reopening settled decisions.

Do **not** mechanically prune useful completed Phase A–D rationale merely to satisfy an obsolete
“unfinished work only” rule.

Instead require:

- a fast, explicit active execution/status section;
- completed sections visibly marked complete/landed;
- no completed subsection phrased so it can be mistaken for current work admission;
- current-next-work section matching exact source and phase state;
- volatile evidence kept out of durable contracts unless it affects a durable decision.

`Current_Plan.md` must not become an uncontrolled archive. Historical bug/evidence detail belongs in
its dedicated evidence documents; compact phase closure/rationale may remain when it materially helps
current execution.

## 3. Migration-epoch truth

During an architecture migration, docs distinguish:

```text
current implementation
from
accepted destination
from
currently admitted migration work
```

Exact source answers what runs today.

Canonical architecture docs answer what new work must converge toward.

`Current_Plan.md` controls which migration step is currently allowed.

A landed technical decomposition may remain current reference after its phase completes, but its header
and imperative wording must not falsely advertise that completed phase as active.

Do not let temporary old implementation names silently redefine the destination.

## 4. Major owner migration sweep

When a major presenter/owner changes, reconcile the relevant subset together:

- `Current_Plan.md`;
- `Spec.md`;
- `Index.md`;
- `Docs/Contracts.md`;
- `Docs/Guardrails.md`;
- focused guardrails;
- `Docs/Compositor_Architecture.md`;
- relevant QtQuick migration decomposition(s);
- visualizer/transition/widget reference/checklists where affected;
- `Docs/TestSuite.md`;
- `Docs/Harness_Index.md`;
- `Docs/Defaults_Guide.md` where persisted/default schema changed;
- `Future_Cleanup.md` where caller/deletion sequencing changed.

Do not leave a future/spike document competing with a closed decision.

## 5. Evidence

Do not delete evidence reports merely because their architecture is old.

Evidence may preserve old class names, measurements and mechanisms.

Current owner questions route to current canonical docs and exact source.

Do not rewrite old evidence so it looks as though Qt Quick existed when the evidence was collected.

## 6. Architecture/status fossils

After presentation/owner/phase changes, search current-authority docs for terms such as:

```text
QOpenGLWidget
QRhiWidget
GLCompositorWidget
QQuickWidget
QQuickWindow
GUI timer
present_tick
paint acknowledgement
pending until paint
separate visualizer surface
C++
native presenter
ACTIVE Phase-D
current normal implementation phase: Phase D
Phase D may proceed
after E2 lands
disabled family
QSGClipNode preferred
```

Interpret every match by document role.

Historical evidence may legitimately contain any old mechanism.

Current authority may mention old mechanisms only when they are clearly current implementation during
migration, rejected architecture, migration source/reference or historical evidence.

Phase-status phrases must match `Current_Plan.md` or be explicitly historical.

## 7. Terminology migrations are contracts

When a new concept exists because two old terms became ambiguous, reconcile terminology across current
authority rather than allowing both meanings to survive.

Current Phase-E example:

```text
activated / deactivated
    = application-level capability gate

enabled / disabled
    = ordinary feature/instance state
```

Do not use `disabled family` when the contract means `deactivated family`.

Likewise, visualizer clip docs must distinguish valid inherited framebuffer clip state from arbitrary
PySide `QSGClipNode` metadata; a shortened phrase must not silently broaden the proved contract.

## 8. Completed work in test/harness docs

A permanent regression requirement may remain detailed after the implementation work that created it
is complete.

Reframe:

```text
add/fix/build this test
```

into:

```text
this landed regression must remain enforced
```

once current source proves it landed.

Do not leave completed hardening worded as a TODO that a future agent may repeat or redesign.

Runnable commands may remain because they still have regression/acceptance value.

## 9. Deleting completed planning docs

When a research/spike/planning document's decision has been fully absorbed into canonical architecture
and the document no longer provides useful landed rationale, delete it rather than maintaining a
competing task list.

Do not delete the evidence supporting the decision.

A technical decomposition that remains the best focused authoring/integration reference may survive its
phase, but must be reclassified as landed/reference rather than active sequencing.

## 10. Closure

Before calling a migration epoch complete:

- current core docs agree on landed owner/type;
- no current doc calls landed architecture “future” where that would misdirect implementation;
- no current route points agents to retired owners as current;
- active/status sections identify current work unambiguously;
- completed phase rationale cannot be mistaken for work admission;
- `Future_Cleanup.md` contains deferred cleanup/deletion rather than current feature work;
- `Future_Work.md` remains explicitly non-active;
- evidence remains evidence-scoped;
- defaults/settings docs match canonical persisted schema;
- test/harness docs distinguish landed regression gates from unfinished work.
