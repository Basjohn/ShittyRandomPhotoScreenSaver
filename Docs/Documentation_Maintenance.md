# Documentation Maintenance

Last updated: 2026-08-26

## Roles

| Document | Role |
| --- | --- |
| `Current_Plan.md` | current checkpoint, active work, next/future sequence, current acceptance debt |
| `Spec.md` | durable product/architecture |
| focused docs/guardrails | durable subsystem contracts |
| `Index.md` / `Docs/Contracts.md` | routing/current owner map |
| `Docs/audits/` | independent audit findings and closure evidence |
| `Docs/TestSuite.md` | live test inventory/status ledger |
| `Future_Cleanup.md` | deferred deletion/debt |
| `Future_Work.md` | deferred features/experiments |
| historical plans/reports/bugs/evidence | history only |

## Current Plan stays lean

Do not retain completed phase implementation narratives in `Current_Plan.md`.

When a slice/family closes:

1. keep only durable invariant in appropriate current contract;
2. put useful independent review/closure detail in `Docs/audits/` or historical evidence;
3. remove completed task lists from Current Plan;
4. spend Current Plan length on current/next/future work and live debt.

A coding agent working F6 should not parse F2 implementation history to discover today's task.

## Focused docs after closure

A technical decomposition may remain current if it is still the best subsystem authoring contract. Reframe
future-tense task language into landed invariant/current authoring rule.

```text
old: implement/add/prove this Phase-X item
new: current owner/contract; change only if evidence requires it
```

## Migration-epoch wording

Distinguish destination authority, temporary current-legacy implementation, temporary visual/behavior
reference, and historical evidence.

Current retirement policy:

- ordinary family pixels -> family GREEN under current audit policy + caller proof in F;
- transition/visualizer old pixel-only owners -> caller-proof early when possible;
- old CUSTOM pixels -> after G;
- physical presenter/backend -> H;
- residue -> I.

Do not use blanket H/I retirement labels.

## Source reality / phase labels

A closed phase must not remain described as `ACTIVE`, `candidate`, `awaiting audit` or `will be removed` in
a live authority document.

A partial checkpoint must be called **partial** and name what is still unproven. Do not promote model-only
or QML-only work into caller-proof/closure language.

## Family-authored

A value/relationship is family-authored only when independently owned by family. Clock analogue qualifies;
retired `shadowtuning.json` card/text/icon/control/volume profiles do not.

## Import dormancy wording

Capability dormancy includes import boundaries. Current docs must not teach common registries/packages to
eagerly import inactive family provider/runtime/backend implementation trees. Cheap catalog/static
presentation metadata is allowed; heavy family implementation resolves at real activation/caller boundary.

## Major owner-change sweep

Inspect at least `Current_Plan.md`, `Spec.md`, `Index.md`, `Docs/Contracts.md`, `Future_Cleanup.md`, relevant
focused QtQuick docs, `Docs/10_WIDGET_GUIDELINES.md` when ordinary-family patterns changed, feature plans
naming concrete owners, and `Docs/TestSuite.md` when test ownership/inventory materially changed.

Historical bodies need not be modernized if clearly evidence-scoped.

## Test docs

`Docs/TestSuite.md` is inventory/status authority, not sequence authority. Update it when adding/deleting/
renaming a test module, changing asserted owner/retirement classification, or discovering stale/vacuous tests.
Do not churn whole inventory just to refresh a phase label when ownership did not change.

## Closure check

Before docs are reconciled:

- current routing identifies current work unambiguously;
- no current-authority doc teaches a retired owner as destination;
- no closed phase is described as future work;
- Current Plan is not bloated with completed implementation narrative;
- audit evidence is available without becoming sequence authority;
- deletion timing matches current owner policy;
- test inventory remains truthful;
- historical evidence is available but fenced from execution authority.
