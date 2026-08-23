# Documentation Maintenance

Last updated: 2026-08-23

Rules for keeping SRPSS documentation useful to coding agents during and after architecture changes.

## 1. Canonical roles

| Document | Role |
|---|---|
| `Current_Plan.md` | current sequence/work admission + clearly marked migration phase closure/rationale |
| `Spec.md` | durable product/architecture contracts |
| `Docs/Compositor_Architecture.md` | accepted runtime presentation design |
| `Docs/Guardrails.md` + focused guardrails | durable stop rules |
| `Index.md`, `Docs/Contracts.md` | routing/current owner map |
| `Docs/TestSuite.md` | canonical live test inventory + migration retirement/status ledger + testing strategy |
| `Docs/Harness_Index.md` | recurring test/runtime harness routing; not the complete test inventory |
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


### 3.1 Forward-obsolescence labels

During an active migration, current docs should state explicitly when an owner is real today but
scheduled for removal. Use these meanings consistently:

```text
LANDED / PRESERVE
    current/destination contract; do not retire merely because its originating phase is old

CURRENT-LEGACY — WILL BE OBSOLETE: <phase>
    still has live callers today, but must not become destination authority; retire when the named
    caller/cutover gate is reached

OBSOLETE NOW
    no longer meaningful current authority; delete/retire rather than teaching it as a live option

HISTORICAL ONLY
    preserve evidence/chronology; status/owner wording inside it does not define current work
```

Do not label a live legacy owner `OBSOLETE NOW` if production still depends on it. Conversely, do not
leave a current-legacy owner unlabeled when a reader could reasonably mistake its temporary existence
for the migration destination.

This applies to docs as well as tests. During the current migration, QRhiWidget/GLCompositor/
`DisplayWidget` runtime presentation and QWidget runtime-pixel/shadow/effect owners are generally
**CURRENT-LEGACY — WILL BE OBSOLETE** at their caller-proven H/I/F cutover gates, while their
presentation-neutral provider/model/business contracts may survive.

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
- feature-specific implementation/design plans that name concrete runtime owners or presentation paths;
- `Docs/TestSuite.md`;
- `Docs/Harness_Index.md`;
- `Docs/Defaults_Guide.md` where persisted/default schema changed;
- `Future_Cleanup.md` where caller/deletion sequencing changed;
- `Docs/Historical_Bugs.md` + `Docs/Historical_Bugs/README.md` when incident status changes;
- evidence/archive **navigation READMEs** when they still call an old phase/owner current.

Do not rewrite historical evidence bodies merely to modernize names. Update their navigation/status
wrappers when those wrappers would otherwise route readers into an obsolete epoch.

Do not leave a future/spike document competing with a closed decision.

Feature-specific plans require the same epoch discipline. A plan may remain valuable for provider,
security, product, data or UX decisions while its old QWidget/painter/factory presentation map becomes
**CURRENT-LEGACY — WILL BE OBSOLETE / REHOMED**. Fence that explicitly in the plan itself when practical
or in `Index.md` plus the canonical focused owner doc if rewriting the historical body would destroy useful
chronology. The current Steam family plan is the concrete example: its source/privacy/product decisions
remain useful, but its `BaseOverlayWidget`/painter/runtime-pixel mapping cannot override the E1/F/I Quick
ownership contracts.

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
before E2 exits
E2 remains active work
disabled family
current P2 work
current Phase 5 work
QRhi/single-surface design
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

## 9. Test inventory maintenance

`Docs/TestSuite.md` is the canonical **live inventory and architectural status ledger for tests**.
`Docs/Harness_Index.md` may point to useful recurring commands, but it must not become a competing or
partial manifest treated as exhaustive.

Update `Docs/TestSuite.md` in the same checkpoint/documentation sweep whenever a change:

- adds a test module;
- deletes a test module;
- renames or rehomes a test module;
- changes which runtime/presenter/owner the test asserts;
- turns a current test into migration-only or destination coverage;
- makes a test obsolete;
- replaces an old-owner assertion with a destination-owner assertion;
- discovers that an existing test is stale, vacuous, permanently skipped, a zero-test tombstone or
  otherwise no longer meaningful authority.

The ledger status describes **test authority**, not whether that file happened to pass in the latest
run. Do not rewrite `KEEP` into “green” merely because one execution passed, and do not mark a useful
test obsolete merely because it is temporarily red.

Do not classify by filename age or phase prefix. A historical phase-named test may protect a permanent
contract; a newly named test may still encode an owner scheduled for deletion.

Before deleting a migration-sensitive test, establish one of:

1. its protected contract is intentionally retired; or
2. equivalent/current coverage has been rehomed to the destination owner.

Do not preserve deleted-test placeholders or empty tombstone modules merely to remember history. If the
history matters, capture it in the inventory/retirement note or historical evidence.

When the complete `tests/` inventory is deliberately re-audited, refresh the reviewed source basis and
module count recorded in `Docs/TestSuite.md`. Incremental test changes do not require pretending that
all unrelated tests were re-audited; update the affected ledger row(s) truthfully.

## 10. Deleting completed planning docs

When a research/spike/planning document's decision has been fully absorbed into canonical architecture
and the document no longer provides useful landed rationale, delete it rather than maintaining a
competing task list.

Do not delete the evidence supporting the decision.

A technical decomposition that remains the best focused authoring/integration reference may survive its
phase, but must be reclassified as landed/reference rather than active sequencing.

## 11. Closure

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
- `Docs/TestSuite.md` matches the current test inventory/status for affected migration areas;
- test/harness docs distinguish landed regression gates from unfinished work;
- current-legacy owners that are scheduled for removal are labelled **WILL BE OBSOLETE** rather than
  presented as durable alternatives;
- evidence/archive navigation wrappers do not advertise old P2/P5/QRhi status as current.
