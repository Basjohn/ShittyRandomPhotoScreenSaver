# Documentation Maintenance

Last updated: 2026-08-20

Rules for keeping SRPSS documentation useful to coding agents during and after architecture changes.

## 1. Canonical roles

| Document | Role |
|---|---|
| `Current_Plan.md` | active unfinished execution |
| `Spec.md` | durable product/architecture contracts |
| `Docs/Compositor_Architecture.md` | accepted runtime presentation design |
| `Docs/Guardrails.md` + focused guardrails | durable stop rules |
| `Index.md`, `Docs/Contracts.md` | routing/owner map |
| current evidence reports | measurements |
| phase reports/Historical_Bugs | historical evidence |
| `Future_Cleanup.md` | deferred debt |

## 2. Migration-epoch truth

During an architecture migration, docs must distinguish:

```text
current implementation
from
accepted destination
```

Exact source answers what runs today.

Canonical architecture docs answer what new work must converge toward.

`Current_Plan.md` controls which migration step is currently allowed.

Do not let temporary old implementation names silently redefine the destination.

## 3. Major owner migration sweep

When a major presenter/owner changes, reconcile together:

- `Current_Plan.md`;
- `Spec.md`;
- `Index.md`;
- `Docs/Contracts.md`;
- `Docs/Guardrails.md`;
- relevant focused guardrails;
- `Docs/Compositor_Architecture.md`;
- visualizer/reference/checklists where affected;
- `Docs/TestSuite.md`;
- `Docs/Harness_Index.md`;
- `Future_Cleanup.md`.

Do not leave a future/spike document competing with a closed decision.

## 4. Evidence

Do not delete evidence reports merely because their architecture is old.

Evidence may preserve old class names and mechanisms.

Current owner questions route to current canonical docs and source.

## 5. Architecture fossils

After presentation changes search current-authority docs for:

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
```

Interpret matches by document role.

Historical evidence may legitimately match.

Current authority may mention old mechanisms only as explicit migration/reference/history.

## 6. Deleting completed planning docs

When a research/spike/planning document's decision has been absorbed into canonical architecture,
delete it rather than maintain a competing task list.

Do not delete the evidence that supported the decision.

## 7. Closure

Before calling a migration epoch complete:

- current core docs agree on the landed owner/type;
- no current doc calls landed architecture "future";
- no route points agents to retired owners as current;
- active plan contains unfinished work only;
- Future_Cleanup contains deferred cleanup only;
- evidence remains evidence-scoped.
