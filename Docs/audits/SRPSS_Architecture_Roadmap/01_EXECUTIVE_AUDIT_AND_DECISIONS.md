# 01 — Executive Architecture Audit and Decisions

Last reconciled: 2026-08-10

## Scope

This document states architecture decisions for current `main`. Older commits are
historical evidence and negative controls only. The project is no longer framed as a
reconstruction from one historical baseline or extraction from a historical candidate.

## Current Root Findings

1. **GUI availability dominates current frame-delivery tails.** In the current mixed-load capture request age tracks frame gaps while paint itself is usually cheap.
2. **A concrete GL reuse defect exists.** The terminal current texture is not found as the next transition's old texture, producing avoidable paired warm/upload work.
3. **Threading is already partly good but ownership is inconsistent.** Network/decode/some simulation work is off GUI; logging, persistence and service/cache preparation still contain avoidable synchronous GUI work.
4. **GPU work is material and under-attributed.** Active-display GPU busy reaches 32.9% in current evidence, while transition GPU telemetry is incomplete across families.
5. **Visualizer timing must be protected from infrastructure tuning.** Bubble workers remain small while UI tick/source-age spikes track broader GUI pressure.
6. **Presentation and logical cadence are different authorities.** A 60 Hz display can currently receive ~90–100 visualizer overlay state/update/paint operations per second. Phase 7 may reduce redundant presentation only after logical integration; it may not reduce authored/source cadence.
7. **Compatibility/fallback code is architecture debt when it no longer preserves a real current contract.** A temporary Bubble “lane” façade currently wraps the approved ordinary executor and should be removed as a behaviour-neutral simplification.
8. **Settings/Edit/Diagnostic ownership and clock shadows are solved.** Their rules remain regression constraints, not active work.

## Decision Set

### ADR-A — Current `main` is implementation authority

Historical baseline/candidate commits are read only when they answer a precise question or serve as a negative control. No active work is justified merely because a historical candidate contained a feature.

### ADR-B — Visual behaviour authority

`ff93461685476bd0657aa88312fc2e35e9037880` remains the current Bubble/Spectrum visual reference until superseded by explicit installed approval. Green tests do not automatically replace visual authority.

### ADR-C — One owner per mutable concern

Runtime admission, persistence ordering, logging output, logical visualizer state, presentation, GL deletion, transition completion and cache eviction each require one explicit authority.

### ADR-D — Prepare → Commit → Persist

Thread-safe I/O/parse/serialization/finite compute prepares immutable results away from GUI. GUI/context owners perform only required Qt/QPixmap/GL commits. Durable writes occur on ordered/background owners with explicit flush semantics.

### ADR-E — No catch-all background thread

Logging, persistence, independent I/O and finite compute are different workload classes. Separate them by blocking/ordering/lifetime needs rather than serializing unrelated work through one new choke point.

### ADR-F — Visualizer logical cadence is protected

Bubble/Spectrum source/event integration, authored step/dt semantics and publication ordering are not reduced to match display refresh or to hide GUI pressure. Scheduler changes are behavioural changes.

### ADR-G — Presentation is a consumer

After logical integration, presentation may consume only the latest valid immutable render state and may coalesce stale render snapshots. Paint/update opportunity cannot become a producer acknowledgement or simulation clock.

### ADR-H — GPU profiling must be truthful and non-blocking

Transition GPU timing must be wired at a shared compositor seam behind the explicit heavyweight `--gpu-timing` profile, with bounded non-blocking sampling and delayed result collection where supported. Ordinary `--perf` performs no query-driver calls; `glFinish()` is prohibited.

### ADR-I — Logging has two phases of work

Phase 5 moves routine logging file/rotation work off caller/UI threads and fixes obvious family-routing defects. Late Phase 7 normalizes family taxonomy/routing so main log is narrative + all WARNING+ while routine INFO/DEBUG belongs in sidecars.

### ADR-J — Compatibility/fallback debt requires a current contract

A compatibility surface remains only when it preserves a real persisted-data, external, frozen/runtime or migration contract. A temporary façade around a rejected scheduler shape is removed after dynamic/frozen-use proof and exact-behaviour tests.

### ADR-K — Checkpoints are rollback anchors

An independently risky slice receives a clean reversible commit and focused gate. A passing checkpoint does not require a pause; work continues. Failed evidence, conflicting repository state or actual visual judgement are stop conditions.

### ADR-L — Lifecycle remains full and fail-closed

Settings and committed Edit retain full teardown/recreation, later-turn admission and explicit owner release. Solved lifecycle incidents are not reopened as a performance shortcut.

### ADR-M — Resource containment and absolute efficiency are separate

Flat ownership is necessary but a screensaver may still be too heavy. RSS, private commit, VRAM and GPU busy must be both bounded and reasonable/attributed without quality reductions.

## Current Success Conditions

- request-age/p99 tails improve through named owner removal rather than cadence tricks;
- retained current texture reliably becomes next old texture under unchanged identity;
- normal callers no longer synchronously write logs/settings/cache data on the GUI path where unnecessary;
- GPU busy is attributable by transition/upload/visualizer/presentation owner;
- Bubble/Spectrum temporal behaviour is unchanged unless explicitly approved;
- dead alternate/compatibility authorities are removed rather than preserved “just in case”;
- memory/commit/VRAM are appropriate for a screensaver;
- lifecycle/GL ownership remains deterministic and fail-closed;
- canonical `main.py` evidence and user visual review agree.
