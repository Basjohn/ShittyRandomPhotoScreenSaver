# 11 — Guardrails and Prohibited Patterns

Last reconciled: 2026-08-02

## Purpose

These are roadmap-level architectural guardrails. Compact always-loaded rules belong in `Docs/Guardrails.md` and focused guardrails; detailed incident evidence belongs in `Docs/Historical_Bugs/`.

The rules below incorporate lessons from the donor failure, persistent visualizer lanes, rejected Spectrum smoothing, current lifecycle evidence, and prefetch failure.

# Hard architectural guardrails

## G-1 — One owner per mutable concern

Do not share lifecycle admission, deletion responsibility, logical cadence, transition completion, cache eviction, or presentation authority across multiple objects.

A coordinator may invoke narrow owners but may not absorb their internal state or make generic managers responsible for unrelated domains.

## G-2 — No producer-to-paint wait

Normal producers never wait on:

- `paintGL()`;
- Qt `update()` completion;
- presentation generations;
- compositor acknowledgement;
- terminal-frame acknowledgement.

## G-3 — One visualizer presentation cadence

No:

- self-requested visualizer repaint loop;
- overlay-local animation timer for authoritative visualizer state;
- paint-derived clock;
- `paintGL()` smoothing/state mutation;
- paint count used as producer control.

R-55/`ebfec397` remains the historical negative control.

## G-4 — Preserve approved visualizer execution

The ordinary general COMPUTE executor restored at `4bde89e` is the approved production model.

Do not restore persistent analysis/Bubble lanes, dedicated long-lived visualizer loops, cadence caps, source decimation, or terminal batching.

## G-5 — Protect all modes; Bubble is not the default target

Aggregate load is presumed shared/runtime-owned until direct evidence proves mode ownership.

Do not alter Bubble-specific scheduling, physics, publication, buffers, resolution, or precision to solve general CPU/memory/task concerns without explicit user authorization.

## G-6 — No perceivable-fidelity trade for resource targets

Do not lower:

- visualizer cadence/source sampling;
- target texture/display resolution;
- buffer precision;
- transition quality;
- image scaling/crop quality;
- artwork/shadows/widget content;
- animation smoothness;
- first-frame responsiveness.

Resource optimization removes waste; it does not silently downgrade the product.

## G-7 — Full reinit remains mandatory

Settings and committed CUSTOM Edit perform full stop–destroy–recreate.

No partial reinit or retired-tree reuse without a separately approved architecture proposal after release-quality stability.

## G-8 — Teardown admission cannot come from a retiring owner frame

A retiring manager/session/widget must not synchronously initiate destruction of the runtime that owns its current call stack.

Persist and explicitly retire temporary session state, return from owner/action/key-filter frames, then queue engine-owned immutable admission on a later GUI turn.

R-53 is the negative control.

## G-9 — A Python wrapper is not Qt-object liveness

Whenever a QObject can be destroyed by modal close, `WA_DeleteOnClose`, `deleteLater()`, or queued deletion:

- register observation before the deletion boundary;
- validate the underlying C++ object before later touches;
- never use `isinstance(..., QObject)` as a liveness check;
- never double-close/delete an invalid wrapper.

R-56 is the negative control.

## G-10 — No GL outside the sole owner thread/context

No retries, warnings-only mode, or handle clearing after failed deletion.

Share-group accessibility does not create shared deletion ownership. One numeric GL handle has one deletion owner.

## G-11 — Every cache/queue is bounded and internally consistent

Every queue/cache has:

- count and/or byte cap appropriate to its retained cost;
- explicit owner;
- stable identity;
- generation/reset policy;
- drop/eviction policy;
- exact bookkeeping tests.

When removing multiple positions, use stable identity/partitioning or explicitly descending unique numeric indices. Priority order is not deletion order. R-57 is the negative control.

## G-12 — Plateau and absolute usage are separate requirements

RAM/private commit/VRAM must:

- stop growing in equivalent scenarios;
- reach an evidence-backed reasonable steady state;
- be reconciled against tracked ownership.

Flat usage near one GiB RSS, multi-GiB private commit, or more than 500 MiB dedicated VRAM is not automatically acceptable.

## G-13 — No fake memory fixes

Do not use:

- working-set/allocator trimming;
- production `gc.collect()`;
- process/worker recycling;
- cache inflation or blind cache reduction;
- ignored owners/counters;
- forced page-out;
- reduced quality;

to make a graph look better.

## G-14 — No silent fallback architecture

Fallback activation is explicit, bounded, observable, and temporary. It cannot silently switch to a second complete runtime path.

## G-15 — No dynamic compatibility façade

No broad `__getattr__`/`__setattr__`, giant forwarding lists, widget/controller impersonation, or whole-owner free-function seams.

## G-16 — No state-machine expansion without deletion

A new state, generation, retry, flag, queue, timer, or callback authority must identify what old complexity it replaces and why plain ownership cannot express the requirement.

Adding a compensating state without deleting another requires architecture review.

## G-17 — No optimization without an equivalent baseline

Every optimization records exact scenario, environment, cache/warmup state, before/after metrics, fidelity result, lifecycle result, resource result, and rollback.

# Performance guardrails

- user-observed feel and first-visible response outrank average FPS/task count;
- p99/max and event-loop lateness are mandatory;
- task rate is categorized, not blindly minimized;
- instrumentation overhead is measured;
- unchanged/static work should stop where genuinely unnecessary;
- no recurring full-buffer hash/copy without evidence;
- no task per paint or per bar/bubble/group;
- no performance result that merely shifts work or memory elsewhere.

# Visualizer guardrails

- approved fixtures/goldens are immutable during infrastructure work;
- strengthened temporal suite includes production executor and known-bad controls;
- logical input/events are integrated before render-state coalescing;
- activation/generation/first-frame identity is explicit;
- manual installed review is required for shared source/scheduling/presentation changes;
- user rejection triggers rollback, not parameter compensation.

# Lifecycle guardrails

- stop producers before deleting display/GL ownership;
- reject late results by generation and exact manager/owner identity;
- destroy GL with owner context current;
- retain ownership on failed deletion;
- destroy surfaces last;
- barrier reaches zero before replacement construction;
- reveal uses fresh authoritative state only;
- no nested event pumping, retry sleeps, timeout extension, forced GC, or ignored owners.

# Resource guardrails

- exact logical bytes and stable identity;
- deterministic release reason;
- context/runtime/source generation;
- no Python-GC-owned GL lifetime;
- no registry GL calls under locks;
- no per-display duplicate unless transform/DPR/output genuinely differ;
- no retained previous/fallback frame without a bounded product reason;
- tracked counters are reconciled with main/child RSS, private commit, mapped regions, and driver memory.

# Prohibited anti-patterns

## “Fix the symptom with another flag”

Examples:

- `paint_pending_but_not_really`;
- `visualizer_retry_after_pause`;
- `ignore_generation_once`;
- `force_reinit_on_next_gap`;
- `terminal_ack_deferred`.

Repeated compensating flags indicate an ownership error.

## “Thread pool or lane as animation loop”

A persistent or per-frame worker loop can alter timing even when equations are identical.

## “More paints means smoother”

Extra repaint requests can create a competing cadence, higher paint pressure, and worse visual continuity.

## “More averaging to hide jitter”

Smoothing or damping to conceal scheduling gaps changes feel.

## “Keep all representations for speed”

Retaining raw, scaled, pixmap, upload, texture, previous, and fallback copies without measured benefit is not optimization.

## “Fast Settings/Edit by retaining unknown state”

A quick partial restart is not a win if ownership cannot be proven.

## “Tests passed, therefore feel/lifecycle passed”

Counter stubs, logical-only replay, and offscreen cleanup cannot replace the real relay shape, temporal negative controls, installed weakref/barrier evidence, and user review.

## “Tracked bytes are flat, therefore memory is solved”

Whole-process physical/commit/driver memory can remain excessive despite correct logical counters.

# Review questions

Every review answers:

1. Who owns each mutable state and deletion responsibility?
2. Which thread/context mutates it?
3. Can it outlive runtime/context/source/activation identity?
4. Does it alter approved cadence or first-visible response?
5. What happens when paint is late?
6. What happens when Settings closes the modal dialog?
7. What happens when Edit Save-and-Continue fires from a key/action frame?
8. What bytes/commit/mappings does it retain in main and children?
9. What happens while hidden/static/unchanged?
10. Does it add a timer/lane/queue/retry/generation/flag?
11. Which known-bad negative control would catch failure?
12. What exact installed evidence and rollback prove the result?

If those answers require several overlapping owners or hidden control paths, the design has regressed.