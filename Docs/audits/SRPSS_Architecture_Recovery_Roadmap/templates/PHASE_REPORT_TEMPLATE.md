# Phase Report — PXX: <Name>

## Metadata

- Working branch: `main`
- Commit before:
- Commit after:
- Approved behavioural comparison commit:
- Date/time/timezone:
- Environment manifest:
- Evidence folder/archive:
- Related current-plan section:
- Related decisions/incidents:

## Phase objective

## Hypothesis and confidence

- Directly proven facts:
- Inferences:
- Cause confidence:
- Important details below 90% confidence:

## Invariants protected

- User-observed visualizer behaviour:
- One visualizer cadence/approved executor:
- Lifecycle and full reinit:
- Graph placement/replay:
- First-frame/reveal authority:
- GL/resource deletion ownership:
- Frame pacing/first-visible response:
- RAM/private commit/VRAM:
- Image/widget/transition quality:

## Code and documents inspected

### Current `main`

### Historical baseline/donor, only where relevant

### Guardrails/historical incidents

## Changes made

## Changes explicitly not made

Include any mode-specific, cadence, quality, partial-reinit, cache-budget, trimming, or fallback changes that were forbidden.

## Tests added/changed

- Deterministic logic:
- Production-shaped temporal/relay:
- Weakref/lifecycle:
- Known-bad negative controls:
- Regression tests that fail on the prior implementation:

## Runtime scenarios executed

- Exact authored actions/input:
- Normal/Media Center:
- Displays/route:
- Warmup/cache state:
- Visualizer mode/source/preset:
- Transition/image/widget activity:

## Before/after results

### Delivery and workload

| Metric | Before | After | Result |
|---|---:|---:|---|
| CPU | | | |
| Task/callback rate by owner | | | |
| Frame interval p95 | | | |
| Frame interval p99 | | | |
| Maximum interval | | | |
| Source-to-first-visible | | | |
| Event-loop lateness p99/max | | | |

### System memory

| Metric | Before | After | Result |
|---|---:|---:|---|
| Whole-app RSS | | | |
| Main/child RSS | | | |
| Private working set, if available | | | |
| Whole-app/main/child private commit | | | |
| VMS/reserved/mapped, if available | | | |
| Handles/threads | | | |

Do not add RSS and private commit.

### Application/GPU resources

| Metric | Before | After | Result |
|---|---:|---:|---|
| CPU cache/image/display bytes | | | |
| Pending future/mapping bytes | | | |
| Tracked GL bytes | | | |
| Dedicated VRAM | | | |
| Shared GPU memory | | | |
| Tracked/untracked gap | | | |

## Visualizer fidelity result

- Modes/shared paths affected:
- Logical replay:
- Production-executor temporal result:
- Known-bad negative controls:
- Generation/activation/first-frame:
- User manual review separately by mode:
- Exact approval/rejection statement:

## Lifecycle result

- Admission owner and GUI-turn boundary:
- Barrier checkpoints:
- QObject/Python/task/resource survivors:
- Invalid-wrapper/context evidence:
- Replacement count:
- Graph replay and reveal:

## Memory/resource interpretation

- Containment result:
- Absolute-footprint result:
- Main/child/native/Qt/driver attribution:
- Remaining uncertainty/confidence:

## Unexpected findings

## Failures and rejected approaches

## Rollback instructions

- Exact revert/rollback:
- Accepted behaviour revalidation:

## Gate decision

- [ ] Pass
- [ ] Fail
- [ ] Inconclusive
- [ ] Pass with explicit deferred issue approved in `Current_Plan.md`

## Repository artifact updates

- [ ] `Current_Plan.md`
- [ ] live roadmap checklist
- [ ] phase/benchmark report
- [ ] historical bug record
- [ ] decision record
- [ ] focused guardrail only if a compact durable rule changed
