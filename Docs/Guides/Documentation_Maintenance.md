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
| `Docs/Historical_Bugs/` | permanent regression, root-cause and failed-method evidence |
| `Docs/TestSuite.md` | live test inventory/status authority |
| `Docs/Guides/Test_Durability.md` | test-authoring authority for mutable versus intentionally exact expectations |
| `Docs/Architecture/Persisted_Input_Compatibility.md` | persisted-input compatibility-bridge guard (user-data protection, horizon-gated — not a backlog) |
| `Future_Work.md` | deferred ideas, their admission rules and dormant ordering (the single future-work router) |

Keep only the small routing authorities at `Docs/` root plus generated evidence with a stable path contract.

## Historical-document policy

`Docs/Historical_Bugs/` is the repository's intentional historical documentation home. It has repeatedly prevented regressions because it records mechanisms, falsifiers and forbidden repairs. Preserve it.

Do **not** create or route new live authority through parallel `Fossils`, `audits`, retired decompositions, dated handoffs or closed investigation reports. The legacy `Docs/Fossils/` folder described outdated architecture and is retired; source control keeps it. When such a document closes:

1. move any durable current invariant into the relevant Spec/Architecture/Guardrail/Guide/Reference document;
2. move any important failed-method/root-cause lesson into an existing/new Historical Bug record;
3. delete the superseded plan/report from the live documentation tree;
4. rely on source control for the full chronological body.

A promoted implementation program belongs in `Current_Plan.md`; dormant ideas belong in the single root `Future_Work.md`. Do not keep a second live decomposition merely because it once carried more detail. If a maintained Guide/Reference already contains the durable contract, delete any byte-identical or superseded planning copy rather than keeping two authorities.

## Extensible catalogs are count-neutral

Live docs must not encode the current cardinality of an extensible registry as a product invariant. Visualizer modes,
transitions, providers and similar catalogs grow over time. Write contracts against the owning registry/descriptor/capability:

- **good:** "every registered Visualizer mode declares a presentation policy";
- **good:** "enumerate the canonical transition registry at capture/test time";
- **bad:** "all six modes" / "the 23 transitions" when the number is merely today's membership count.

A numeric count is appropriate only when the number itself is product behavior, a fixed protocol/resource bound, or explicitly
historical evidence. Current catalog membership belongs to source registries and registry-derived tests/tools. Reference docs may
describe mode/effect-specific exceptions without pretending their prose list is a second membership authority.

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

## Build and test execution ownership

An archive/documentation agent may run read-only audits and bounded relevant focused tests. **Never invoke frozen product compilation, Build Runner, Nuitka, installer packaging or trial builds:** the operator runs those costly gates and supplies reports/logs. Do not automatically request another four-chunk suite; provide only affected focused tests unless the operator chooses the expensive full gate. Instructions copied into Godzip Foundry RUN SCRIPT must be one line and semicolon-separated.

## Test documentation

`Docs/TestSuite.md` is inventory/status authority, not sequence authority. Keep row-level ownership truthful and avoid hand-maintained aggregate counts unless generated from the exact current tree for a durable reason.

When caller-dead implementation is retired, delete implementation-only tombstone tests with it unless a real surviving behavior needs rehomed coverage. Never resurrect museum architecture because an old test imports it.

For Qt/QQuick-heavy profiles, subprocess isolation is a valid test-harness boundary when one target can poison later targets through queued callbacks/scenegraph teardown. Isolation must expose the owning failure, not hide it.

## Test authority hygiene

Test expectations follow the same source-of-truth rule as documentation. Mutable defaults, extensible registry/catalog membership and authored preset/theme payloads must not be copied into unrelated tests as a second authority. Authored Markdown prose is explanatory authority, not a substitute behavioral oracle: tests prove the runtime/source contract itself unless a generated document is explicitly the product artifact under test. Use `Docs/Guides/Test_Durability.md` and the blocking `tools/test_durability_audit.py` bar. Exact regression pins remain desirable when the value itself is the contract.

## Import dormancy wording

Capability dormancy includes import boundaries. Current docs must not teach common registries/packages to eagerly import inactive provider/runtime/backend trees. Cheap catalog/static metadata is fine; meaningful owned work/resources resolve at activation/caller boundaries.

## Source-of-truth sweep boundaries

A documentation/tool-only pass may read production source and existing evidence to verify contracts, but must not silently modify product runtime, settings, tests or frozen historical records. Route unresolved implementation/acceptance gaps to the appropriate active work owner; do not manufacture source truth or convert an unverified source inspection into operator acceptance. The supplied/latest GODZIP is the working-tree authority for handoff work. Significant slices ship as **full superseding GODZIPs** carrying the complete current replacement set; do not reconstruct the tree from GitHub and do not substitute a narrow patch/diff/manifest-only handoff.

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
