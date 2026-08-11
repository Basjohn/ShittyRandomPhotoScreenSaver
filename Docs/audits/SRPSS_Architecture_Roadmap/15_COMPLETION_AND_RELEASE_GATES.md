# 15 — Completion and Release Gates

Last reconciled: 2026-08-11

A release candidate fails when a critical gate fails even if one average metric improves.

## Architecture Gate

- [ ] Current plan/spec/guardrails/roadmap/code agree.
- [ ] One explicit owner per mutable concern/deletion identity.
- [ ] Full fail-closed lifecycle remains correct; solved Settings/Edit ownership does not regress.
- [ ] Visualizer producers never wait for paint and presentation is not a logical clock.
- [ ] No persistent/dedicated Bubble lane, paint-local Spectrum state or hidden fallback runtime.
- [ ] Temporary compatibility façades promoted for cleanup are gone or justified by a real current contract.
- [ ] Checkpoint/rollback history is clean enough to revert risky slices independently.

## Visualizer Gate

- [ ] `ff934616` behaviour remains approved until explicitly superseded.
- [ ] Strong source→state→publication→paint temporal package passes.
- [ ] Known-bad `666624d4`, terminal batching and `ebfec397` controls fail.
- [ ] Presentation opportunity changes do not alter logical state/events/dt.
- [ ] User installed review passes for affected modes.

## UI / Workload Gate

- [ ] Retained-current texture becomes next-old cache hit; steady transition uploads only new.
- [ ] Routine logging file/rotation work is off caller/UI threads with bounded queue/writer ownership.
- [x] Settings persistence is ordered/background with explicit flush semantics and no stale write winning.
- [ ] Proven Reddit/Weather/Gmail cache/data preparation is outside GUI/paint hot paths.
- [ ] p95/p99/max request-age/tick tails improve or remaining owners are named.
- [ ] No catch-all background thread or new unbounded queue.

## GPU Gate

- [ ] Representative transition families produce truthful paint + non-blocking GPU timer samples with support/sample counts.
- [ ] No routine `glFinish()` profiler synchronization.
- [ ] Process GPU busy is separated among texture upload, transition, visualizer/presentation and other measured owners sufficiently to guide action.
- [ ] Overlay state/update/paint rate is compared against display refresh without reducing logical visualizer cadence.
- [ ] Phase 8 is not started unless Phase 7 plus GPU/context evidence justifies it.

## Memory / Resource Gate

- [ ] No post-warmup monotonic equivalent-state growth.
- [ ] Preferred whole-app warm RSS under ~600 MiB or approved explanation; >900 MiB unresolved blocks release.
- [ ] Preferred dedicated VRAM under ~300 MiB or approved explanation; >500 MiB unresolved blocks release.
- [ ] No unexplained multi-GiB private commit.
- [ ] Strict retired-generation application GL ownership reaches zero.
- [ ] No fidelity/cadence/quality reduction used to hit resource targets.

## Logging / Evidence Gate

- [ ] Main log is readable high-level narrative plus every WARNING/ERROR/CRITICAL.
- [ ] Routine enabled-family INFO/DEBUG is routed to sidecar without systematic duplication.
- [ ] Structured family routing prevents token accidents like `[GL CACHE]` versus `[CACHE]`.
- [ ] Logging queue depth/writer lag/drop/flush telemetry is bounded and visible.
- [ ] Raw logs/failed runs/manifests/parser commands are preserved.

## Product Gate

- [ ] Correct multi-display routing/geometry/overlays.
- [ ] Cursor/interaction overlays remain smooth.
- [ ] Image/transition quality unchanged unless explicitly approved.
- [ ] All supported visualizer modes retain current behaviour.
- [ ] Background-load behaviour is equal or better than the approved runtime.
- [ ] Resource/GPU usage is appropriate for a screensaver, not merely technically bounded.

## Final Comparison

Compare ordinary work against the exact previous/current approved commit. Use historical
commits only for a named forensic/negative-control question. State remaining weaknesses
and uncertainty; a single favorable metric is never release readiness.
