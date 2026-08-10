# 10 — Historical Candidate Lessons and Negative Controls

Last reconciled: 2026-08-10

## Role

This document is historical. It is **not an extraction matrix** and does not create a
historical-candidate seam for current architecture. Current `main` is the implementation authority.
Older commits are opened only to answer a specific forensic question, preserve a
negative control, or understand why a rejected architecture failed.

## Historical References

### `00edb57` — early behavioural baseline

Useful history: smoother perceived visualizer behaviour and simpler topology in some
scenarios. Weaknesses included high task/CPU work, memory/VRAM growth and weak resource
accounting. It is no longer current authority.

### `7376bb9` — historical architecture candidate

Useful principles: explicit resource identity/bytes, generation checks, immutable
handoff, affinity assertions and ownership tests.

Rejected shapes: producer-to-paint acknowledgement, adaptive/persistent visualizer
scheduling, partial lifecycle reconstruction, terminal-frame transactions, distributed
fallback/retry state, broad compatibility forwarding and ambiguous GL ownership.

### `666624d` — rejected persistent visualizer lane

Mandatory negative control. It changed scheduling/temporal behaviour and visibly
reduced approved response despite plausible throughput goals.

### `ebfec397` — rejected paint-local Spectrum state

Mandatory negative control. Paint became a second cadence/state authority; more paints
did not produce better perceived smoothness.

### R-53 / R-56 / R-59

Historical lifecycle lessons: teardown admission must not begin from a retiring owner
frame; Python wrapper identity is not QObject liveness; PySide/Nuitka compiled
bound-method callbacks can retain plain-Python owners after Qt teardown unless lifetime
ownership is explicit.

### R-57

Historical queue lesson: priority selection order is not safe positional deletion order.
Use stable identity/partitioning or descending unique numeric indices.

## Current Use Rule

When an old commit is consulted:

1. name the current-main question first;
2. inspect current code/evidence first;
3. open only the narrow historical component needed to answer that question;
4. import no hidden scheduler/fallback/lifecycle dependencies;
5. adapt any useful principle to current ownership rather than copying an implementation shape;
6. keep the old failure as a negative control when it can catch recurrence.

## What Not To Do

- no wholesale cherry-pick/merge;
- no compatibility bridge merely to preserve an old architecture;
- no “the historical candidate did it” as implementation rationale;
- no active roadmap item whose only justification is unfinished historical extraction;
- no historical branch name as a current execution instruction.

The historical value is the lesson and falsifier, not the code ancestry.
