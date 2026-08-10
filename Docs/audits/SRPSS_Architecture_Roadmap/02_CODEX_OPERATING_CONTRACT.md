# 02 — Codex Operating Contract

Last reconciled: 2026-08-10

This contract defines how architecture work is executed. `Current_Plan.md` owns task
order; this document owns execution discipline.

## 1. Work directly on `main`

Do not create a branch, fork or pull request unless explicitly requested. Keep changes
narrow, reversible and mechanically verifiable.

## 2. Read current authority first

Before implementation:

1. read the relevant `Current_Plan.md` section;
2. read the focused guardrail/historical record;
3. read the phase-specific roadmap file;
4. inspect current `main` code/tests;
5. inspect current evidence named by the plan;
6. inspect historical commits only for a specific negative-control/forensic question;
7. state uncertainty when the causal claim is below 90%.

Do not begin from a historical branch/candidate, old completion claim or stale local patch.

## 3. Do not rebuild Diagnostic by default

Settings/Edit/Diagnostic ownership is solved. `main.py` is the performance and ordinary
runtime authority. Build/run Diagnostic only when a new frozen-only/native-boundary
hypothesis specifically requires it. Do not spend a 10–20 minute build to prove work
that current source/evidence already closes.

## 4. One dominant concern per risky change

Do not mix independent lifecycle, logging, persistence, compositor, visualizer,
resource, provider and compatibility deletions. Each concern gets a clear hypothesis,
focused test/evidence gate and exact rollback.

## 5. Checkpoint and continue

After an independently risky slice:

1. produce a clean commit;
2. run the focused owning tests/evidence;
3. if it passes, keep the commit and **continue immediately** to the next planned slice;
4. stop only for failed evidence, a contradicted model, unexpected repository state, or an affected visual result that requires operator judgement.

A checkpoint is not a user-approval ceremony. Git is used to make rollback cheap.

## 6. The user remains the visual authority

Current approved Bubble/Spectrum behaviour is `ff93461685476bd0657aa88312fc2e35e9037880`. Infrastructure work may
not silently change cadence, source sampling, attack/decay, physics, amplitudes,
precision, transition timing, image quality, artwork/shadows or first-frame response.

## 7. Protect logical cadence separately from presentation

Do not equate display refresh with visualizer simulation/source cadence. Bubble/Spectrum
logical integration remains authoritative. A later presentation consumer may skip stale
immutable render snapshots only after all logical events/steps are integrated.

No paint acknowledgement, paint-derived clock, source decimation, terminal batching,
or display-refresh cadence cap.

## 8. Use workload-class ownership, not “more threads”

- GUI/context: QWidget/QObject/QPixmap/GL and final commits.
- IO: independent blocking network/file/cache work.
- ordered persistence: revision-ordered settings durability.
- logging writer: ordinary formatting/rotation/file writes.
- general COMPUTE: finite worker-safe native/CPU work and the approved Bubble task path.

Normal GIL-governed Python threads do not make pure Python loops truly parallel by
magic. Measure native GIL release and queueing before adding worker width.

## 9. No hidden fallback or compatibility architecture

A runtime fallback or façade must state the current contract it preserves, its owner,
activation rule, telemetry and removal criterion. A compatibility wrapper that only
preserves an obsolete/rejected architecture shape is debt, not safety.

Persisted-data/external migration compatibility may be legitimate; do not delete it
merely because it is old.

## 10. GL rules are absolute

No worker GL/QPixmap mutation; one deletion owner per numeric handle; retain ownership
on failed deletion; no handle reuse across context generation; no `glFinish()` in
ordinary profiler code; no GL under registry locks.

## 11. Logging must not become workload

Routine logging callers should enqueue a structured record cheaply. One process-owned
writer owns normal formatting, family routing, rotation and file I/O. Fatal/native
breadcrumbs remain direct and independent.

Main log retains every WARNING/ERROR/CRITICAL. Enabled-family INFO/DEBUG should route
to sidecars without routine duplication. Prefer structured `family` metadata over
parsing human message text.

## 12. Lifecycle correctness remains non-negotiable

Solved Settings/Edit ownership remains full stop–destroy–recreate, fail-closed barriers,
primitive later-turn admission, exact generation/manager identity and authoritative
first-frame reveal. Performance work is not permission to weaken it.

## 13. Tests reproduce production ownership

Fakes may not invent lifecycle methods absent from production. Scheduler tests must
use production-shaped timing/ownership where the bug depends on it. Known-bad
negative controls must remain failing.

## 14. Evidence discipline

Performance claims include exact commit/scenario, warm/cache state, display identity,
p50/p95/p99/max, request/source age, CPU, GPU busy, RSS/commit/VRAM, task/queue data and
visual result where relevant. Averages alone are insufficient.

## 15. Stop conditions

Stop/revert when:

- user-observed feel worsens;
- a known-bad control passes;
- source-to-first-visible or p99/max materially regresses;
- a stale/retired owner or GL/context violation appears;
- memory/resource growth becomes unexplained;
- queue/backlog becomes unbounded;
- the “fix” needs another scheduler, cadence, retry, hidden fallback or compatibility layer to conceal unclear ownership.
