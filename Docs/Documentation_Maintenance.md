# Documentation Maintenance

Last updated: 2026-08-29

## Roles

| Document | Role |
| --- | --- |
| `Current_Plan.md` | current checkpoint, active blocker/work, next sequence, live acceptance debt |
| `Spec.md` | durable product/architecture |
| focused docs/guardrails | durable subsystem contracts |
| `Docs/Settings_Theme_Architecture.md` | permanent Settings theme / Acrylic / Glass / Foundry contract |
| `Index.md` / `Docs/Contracts.md` | routing/current owner map |
| `Docs/audits/` | independent audit findings and closure evidence |
| `Docs/TestSuite.md` | live test inventory/status ledger |
| `Future_Cleanup.md` | deferred deletion/debt |
| `Future_Work.md` | genuinely deferred features/experiments |
| historical plans/reports/bugs/evidence | history only |

Temporary working/theme-plan files may help an active migration but are not durable architecture. When a focused current
contract exists, route permanent invariants there and retire the temporary plan rather than making other docs depend on
it.

Reorientation/handoff summaries are operator/conversation aids by default, not repository architecture. Keep them outside
`Docs/` unless the operator explicitly asks for a repository handoff artifact. The repository should route through
`Current_Plan.md` + focused contracts rather than a dated reorientation file.

## These are not changelogs

Only `Current_Plan.md` should routinely carry volatile phase progress, exact active checkpoint and next-slice wording.
Routing indexes, subsystem contracts, guardrails and reusable decompositions should prefer durable owner/invariant language
and point back to `Current_Plan.md` for live status. Do not make every index or focused contract require editing after each
GREEN implementation checkpoint.

Current authority documents describe **what is true or structurally required**. Do not append chronological implementation
diaries, commit-by-commit narratives or “then we did X” history to living contracts.

When a slice closes:

1. keep the durable invariant in the relevant current contract;
2. keep only the current checkpoint/next blocker in `Current_Plan.md`;
3. put useful closure narrative/evidence under `Docs/audits/` or historical evidence;
4. remove superseded future-tense assumptions from living docs.

A new agent should not need to mentally subtract old phases from a current document.

## Contract/source disagreement

Do not make documentation “consistent” by deleting an intended product requirement merely because current source failed
to implement it. Determine which side is authoritative:

- explicit current product/destination intent -> keep the contract and promote the source gap into `Current_Plan.md`;
- genuinely superseded design -> rewrite the contract cleanly to the new destination;
- uncertain historical wording -> inspect source/evidence/operator intent before changing either.

The visualizer viewport work is the canonical example: the destination contract required edge viewport reflow for all five
modes, so the earlier missing Bubble/source affordance was implementation debt rather than prose to erase. Once that core
path landed, current docs then had to stop claiming Bubble was still capability-gated and name only the bounded
post-checkpoint ownership/spatial omissions that genuinely remained.

## Focused docs after closure

A technical decomposition may remain current if it is still the best subsystem authoring contract. Reframe task language
into present-tense owner/invariant language.

```text
old: implement/add/prove this Phase-X item
new: current owner/contract; named open debt only where it actually remains
```

## Migration-epoch wording

Distinguish destination authority, temporary source scaffolding, temporary visual/behavior reference and historical
evidence.

Current retirement policy:

- ordinary family pixels -> already retired during F after destination proof/caller proof;
- transition/visualizer old pixel-only owners -> caller-proof as soon as dead;
- old CUSTOM/auxiliary pixels -> caller-proof during G;
- remaining physical presenter/backend -> H;
- residue -> I.

Do not preserve old presentation to maintain temporary product continuity. Do not use blanket H/I retirement labels for
caller-dead components that can already leave.

## Source reality / phase labels

A closed phase must not remain described as `ACTIVE`, `candidate`, `awaiting audit` or future work in a live authority
document. A partial checkpoint must name exactly what remains unproven.


## Checkpoint/hash wording

Exact commit hashes are useful in `Current_Plan.md`, audits and checkpoint-scoped evidence. Avoid copying them into broad
living guides/indexes/decompositions unless that exact tree is intrinsic to the document. A stale hash in a live routing doc
creates false authority. Prefer `inspect exact current source; later source outranks owner-name details` for executable
decompositions that are meant to survive several bounded commits.

## Import dormancy wording

Capability dormancy includes import boundaries. Current docs must not teach common registries/packages to eagerly import
inactive family provider/runtime/backend implementation trees. Cheap catalog/static presentation metadata is allowed;
heavy family implementation resolves at real activation/caller boundary.

## Major owner-change sweep

Inspect at least `Current_Plan.md`, `Spec.md`, `Index.md`, `Docs/Contracts.md`, `Future_Cleanup.md`, relevant focused
QtQuick docs, `Docs/10_WIDGET_GUIDELINES.md` when ordinary-family patterns changed, feature plans naming concrete owners,
and `Docs/TestSuite.md` when test ownership/inventory materially changed.

For Settings theme/backdrop ownership changes, also inspect `Docs/Settings_Theme_Architecture.md`, Theme Foundry,
`ui/settings_theme_spec.py`, `ui/settings_theme.py`, `ui/settings_dialog.py` and `core/windows/dwm_blur.py` together.

Historical bodies need not be modernized if clearly evidence-scoped.

## Test docs

`Docs/TestSuite.md` is inventory/status authority, not sequence authority. Keep current gates and test-file ownership
truthful; do not turn its introduction into a phase diary.

Do not hard-code aggregate test/module/status counts into the live prose unless they are generated from the same current
tree in that checkpoint and have a durable reason to exist. Row-level ownership is the useful authority; hand-maintained
counts become contradictory almost immediately during an active migration.

When a caller-dead feature island is intentionally retired, remove its implementation and implementation-only tombstone
tests together rather than preserving zero-value modules merely because an old inventory row still exists. Preserve a
separate neutral module only when a real surviving caller/contract still owns it.

## Closure check

Before docs are reconciled:

- `Current_Plan.md` identifies current work unambiguously; routing/index docs do not duplicate volatile phase status;
- no current-authority doc teaches a retired owner as destination;
- no closed phase is described as future work;
- no intended requirement has been erased merely because source missed it;
- Current Plan is not bloated with completed implementation narrative;
- deletion timing matches current owner policy;
- test inventory remains truthful;
- historical evidence remains available but fenced from execution authority.
