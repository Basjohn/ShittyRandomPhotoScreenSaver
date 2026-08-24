# Documentation Maintenance

Last updated: 2026-08-24

Rules for keeping SRPSS documentation useful to coding agents.

## Roles

| Document | Role |
| --- | --- |
| `Current_Plan.md` | current checkpoint, active work, next/future sequence, current acceptance debt |
| `Spec.md` | durable product/architecture |
| focused docs/guardrails | durable subsystem contracts |
| `Index.md` / `Docs/Contracts.md` | routing/current owner map |
| `Docs/TestSuite.md` | live test inventory/status ledger |
| `Future_Cleanup.md` | deferred deletion/debt |
| `Future_Work.md` | deferred features/experiments |
| historical plans/reports/bugs/evidence | history only |

## Current Plan must stay lean

Do **not** retain completed phase implementation narratives in `Current_Plan.md`.

When a phase closes:

1. preserve only the durable invariant in a focused current contract if it still matters;
2. move useful closure rationale/checkpoints to `Docs/Historical_Plans/` or an existing phase/evidence
   report;
3. remove completed task lists from Current Plan;
4. spend Current Plan length on current/next/future work.

A coding agent should not parse Phase E implementation history while working in Phase F.

## Focused docs after a phase closes

A technical decomposition may remain current if it is still the best subsystem authoring contract.

Reframe it:

```text
old: "implement/add/prove this Phase-C item"
new: "landed invariant/current authoring rule"
```

Remove stale phase-status/task instructions that can be mistaken for active work.

## Migration epoch / legacy wording

Current docs must distinguish:

```text
destination authority
temporary current implementation
temporary reference evidence
historical evidence
```

Do not use a single blanket “H/I” retirement label.

Current retirement policy:

- ordinary family pixels -> after family GREEN in F;
- old transition/visualizer pixel-only owners -> caller-proof early when possible;
- old CUSTOM pixels -> after G;
- physical presenter/backend -> H;
- residue -> I.

## Family-authored means independently authored

When old shared tuning is removed, do not relabel its numbers as family-authored.

A value/relationship is family-authored only if the family itself owned it independently of the retired
shared authority.

Clock analogue geometry qualifies.
`shadowtuning.json` card/text/icon/control/volume profiles do not.

## Large old implementation plans

If a large pre-migration plan contains useful product/data/security/visual history but obsolete
presentation architecture:

- replace the live file with a concise current-epoch wrapper/reference index;
- point to current source/current contracts;
- record the Git commit containing the full historical plan for targeted lookup;
- do not force every coding agent to ingest the obsolete plan.

This policy applies to the Steam family plan.

## Major owner-change sweep

When owner/deletion policy changes, inspect at least:

- `Current_Plan.md`;
- `Spec.md`;
- `Index.md`;
- `Docs/Contracts.md`;
- `Future_Cleanup.md`;
- relevant focused QtQuick docs;
- feature plans that name concrete pixel owners;
- `Docs/TestSuite.md` status/retirement wording where materially affected.

Historical bodies need not be rewritten merely to modernize names if clearly evidence-scoped.

## Test docs

`Docs/TestSuite.md` is inventory/status authority, not work-sequence authority.

Update it in the same checkpoint when:

- adding/deleting/renaming a test module;
- changing the owner asserted by a test;
- changing migration retirement classification;
- discovering stale/vacuous tests.

Do not churn the entire inventory just to refresh a phase label when no test ownership changed; sequence
still comes from `Current_Plan.md`.

## Closure check

Before docs are considered reconciled:

- current routing identifies current work unambiguously;
- no live current-authority doc teaches a retired owner as destination;
- no completed phase narrative bloats Current Plan;
- old plans are clearly fenced as historical/reference where presentation ownership changed;
- deletion timing matches the current owner-based retirement policy;
- test inventory remains truthful;
- historical evidence remains available without becoming execution authority.
