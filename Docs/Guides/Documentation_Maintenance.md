# Documentation Maintenance

SRPSS documentation is organized by **current role**, not by the phase/checkpoint that created it. The repository should help a fresh agent find the present owner quickly; source control and Historical Bugs preserve archaeology.

## Roles

| Location | Role |
| --- | --- |
| `Current_Plan.md` | active work, current blocker, next acceptance debt |
| `Spec.md` | durable product/architecture contract |
| `Docs/Architecture/` | durable subsystem architecture/ownership |
| `Docs/Guardrails/` | binding invariants and preflight contracts |
| `Docs/Guides/` | maintained how-to/change procedures |
| `Docs/Reference/` | current lookup/reference/harness material |
| `Docs/Future_Work/` | genuinely pending or operator-activated work only; completed product contracts belong in `Docs/Reference/` or `Spec.md` |
| `Docs/Historical_Bugs/` | permanent regression, root-cause and failed-method evidence |
| `Docs/TestSuite.md` | live test inventory/status authority |
| `Docs/Architecture/Persisted_Input_Compatibility.md` | persisted-input compatibility-bridge guard (user-data protection, horizon-gated — not a backlog) |
| `Future_Work.md` / `FWPlan.md` | broad deferred ideas and dormant ordering |

Keep only the small routing authorities at `Docs/` root plus generated evidence with a stable path contract.

## Historical-document policy

`Docs/Historical_Bugs/` is the repository's intentional historical documentation home. It has repeatedly prevented regressions because it records mechanisms, falsifiers and forbidden repairs. Preserve it.

Do **not** maintain parallel `Fossils`, `audits`, retired decompositions, dated handoffs or closed investigation reports as another history system. When such a document closes:

1. move any durable current invariant into the relevant Spec/Architecture/Guardrail/Guide/Reference document;
2. move any important failed-method/root-cause lesson into an existing/new Historical Bug record;
3. delete the superseded plan/report from the live documentation tree;
4. rely on source control for the full chronological body.

A closed implementation decomposition must not remain under `Docs/Future_Work/` merely because moving/deleting it is inconvenient. `Future_Work` means future work.

## These are not changelogs

Current authority documents describe **what is true now or structurally required**. Do not append checkpoint diaries, commit-by-commit narratives or long closure histories to living contracts.

When a slice closes:

- keep only current status/next debt in `Current_Plan.md`;
- keep the durable rule at its current owner;
- preserve a useful regression/failed-method mechanism in Historical Bugs;
- delete redundant historical prose.

Exact commit hashes belong primarily in `Current_Plan.md`, `.godzip` handoff metadata and historical evidence where the exact tree matters. Broad living guides should avoid hashes that will turn into stale authority.

## Contract/source disagreement

Do not make documentation “consistent” by deleting an intended product requirement merely because current source fails it. Determine authority first:

- explicit current product intent -> keep the contract and promote the source gap into `Current_Plan.md`;
- genuinely superseded design -> rewrite the current contract cleanly;
- uncertain historical wording -> inspect source/evidence/operator intent before changing either.

## Current owner-change sweep

For a meaningful ownership change, inspect at least:

- `Current_Plan.md`;
- `Spec.md`;
- `Index.md`;
- `Docs/Contracts.md`;
- the relevant Architecture/Guardrail/Guide/Reference document;
- `Docs/Architecture/Persisted_Input_Compatibility.md` if old ownership, compatibility input or persisted schema is being retired;
- `Docs/TestSuite.md` if test inventory/authority changes;
- the relevant Historical Bug when the repair creates a durable negative control.

For Settings theme/backdrop ownership changes also inspect `Docs/Architecture/Settings_Theme_Architecture.md`, Theme Foundry and the owning theme/native-backdrop source together.

## Test documentation

`Docs/TestSuite.md` is inventory/status authority, not sequence authority. Keep row-level ownership truthful and avoid hand-maintained aggregate counts unless generated from the exact current tree for a durable reason.

When caller-dead implementation is retired, delete implementation-only tombstone tests with it unless a real surviving behavior needs rehomed coverage. Never resurrect museum architecture because an old test imports it.

For Qt/QQuick-heavy profiles, subprocess isolation is a valid test-harness boundary when one target can poison later targets through queued callbacks/scenegraph teardown. Isolation must expose the owning failure, not hide it.

## Import dormancy wording

Capability dormancy includes import boundaries. Current docs must not teach common registries/packages to eagerly import inactive provider/runtime/backend trees. Cheap catalog/static metadata is fine; meaningful owned work/resources resolve at activation/caller boundaries.

## Source-of-truth sweep boundaries

A documentation/tool-only pass may read production source and existing evidence to verify contracts, but must not silently modify product runtime, settings, tests or frozen historical records. Route unresolved implementation/acceptance gaps to the appropriate active work owner; do not manufacture source truth or convert an unverified source inspection into operator acceptance. A sweep does not grant permission to overwrite a newer local Foundry with an older checkpoint copy. Prefer a narrow manifest ZIP of the changed docs/tools over replaying the entire source tree.

## Closure check

Before calling a documentation tranche coherent:

- `Current_Plan.md` contains active work rather than completed diaries;
- `Index.md` routes only to paths that exist;
- no current-authority doc teaches a retired owner as destination;
- no completed decomposition remains disguised as Future Work;
- durable product requirements were not erased while deleting history;
- Historical Bugs preserve the important negative controls;
- test and cleanup/schema-migration ledgers remain truthful;
- cross-references to deleted/moved files are reconciled.
