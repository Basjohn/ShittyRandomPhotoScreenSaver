# 11 — Guardrails and Prohibited Patterns

Last reconciled: 2026-08-10

## Hard Architecture Guardrails

1. **One owner per mutable concern.** Lifecycle admission, persistence order, logging output, logical cadence, presentation, transition completion, cache eviction and GL deletion cannot have competing authorities.
2. **Producers never wait for paint.** No `paintGL()`/`update()` acknowledgement, requested/acknowledged frame protocol or terminal-frame handshake.
3. **One authoritative logical visualizer clock.** Presentation may coalesce immutable snapshots only after logical integration; it may not become a second state clock.
4. **Bubble/Spectrum timing is protected.** No persistent Bubble lane, terminal batching, source decimation, display-refresh cap or paint-local Spectrum state.
5. **No fidelity trade for resource targets.** Preserve source sampling, resolution/precision, image quality, transitions, artwork/shadows and first-visible response.
6. **Full fail-closed lifecycle remains authoritative.** Solved Settings/Edit ownership is not weakened for performance.
7. **GL stays on sole GUI/context owner.** One deletion owner per handle; failed deletion retains ownership; no worker GL/QPixmap mutation.
8. **Every queue/cache is bounded and internally consistent.** Stable identity, generation, drop/eviction policy and byte/count accounting.
9. **Plateau and absolute footprint are separate.** Flat but excessive RSS/commit/VRAM still fails without an approved explanation.
10. **No fake memory fix.** No working-set trimming, production GC, process recycling, hidden page-out or ignored ownership.
11. **No hidden fallback runtime.** A fallback must be explicit, observable, bounded and temporary.
12. **Compatibility requires a current contract.** Runtime façades/shims kept only for a real external/persisted/frozen/migration requirement and must have a removal criterion.
13. **No state-machine expansion without deletion.** A new timer/queue/retry/generation/flag must name the old complexity it replaces.
14. **Diagnostics remain evidence.** They do not request paints, control cadence or become hot-path work.
15. **Logging routing is semantic, not textual accident.** Main log keeps all WARNING+ and high-level narrative; routine enabled-family INFO/DEBUG belongs in sidecars. Prefer explicit family metadata over parsing message strings.
16. **GPU profiling must not synchronize the workload.** No routine `glFinish()` to obtain timings.
17. **Checkpoint does not mean stop.** Passing risky-slice checkpoint → continue; stop on failed gate/model conflict/real visual approval need.

## Performance Guardrails

- p95/p99/max, request/source age and first-visible response outrank average FPS;
- remove work before moving it;
- no task per paint/bar/bubble/group;
- no catch-all background thread;
- measure queueing/serialization/commit cost when moving work to a worker;
- no optimization that merely shifts cost to another thread/process/memory pool;
- physical presentation work above display demand is investigated only after logical cadence is frozen/protected.

## Compatibility/Debris Review Questions

Before retaining a shim ask:

- Which current external/persisted/runtime contract requires it?
- Is production actually calling it, or only tests/docs?
- Does it preserve an alternate scheduler/state machine/fallback path?
- Does frozen/dynamic import require it?
- What exact test proves deletion is safe?
- What is its removal criterion?

A “temporary” adapter with no current consumer is not a safety feature.

## Review Questions

Every architecture review answers:

1. Who owns mutable state/deletion?
2. Which thread/context mutates it?
3. What generation/lifetime can outlive it?
4. Which work can prepare off GUI?
5. Does it alter logical visualizer cadence or source age?
6. What happens when paint is late?
7. What bytes/GPU work does it retain or execute?
8. What happens while static/hidden/unchanged?
9. Does it add a queue/timer/lane/retry/fallback/compatibility authority?
10. Which negative control catches failure?
11. What focused test/evidence makes the checkpoint safe to keep and continue?
