# 15 — Completion and Release Gates

Last reconciled: 2026-08-02

A release candidate is rejected when a critical gate fails, even when average FPS, task count, or one resource number improves.

# Architecture gate

- [ ] One explicit owner exists for every mutable concern and deletion identity.
- [ ] `Current_Plan.md`, `Spec.md`, guardrails, roadmap, and code agree.
- [ ] Full Settings and committed Edit reinitialization remains authoritative.
- [ ] Teardown is admitted only by the process/runtime coordinator, never from a retiring owner frame.
- [ ] Graph-based CUSTOM placement and replay remain correct.
- [ ] Compositor does not own visualizer simulation/cadence, worker scheduling, image selection, or Settings lifecycle.
- [ ] Visualizer producers never wait for paint.
- [ ] One authoritative visualizer presentation cadence exists.
- [ ] Transition completion is local and exactly once.
- [ ] No adaptive/persistent visualizer lane, paint acknowledgement, or second presentation scheduler remains.
- [ ] No compatibility mega-layer or silent fallback runtime remains.
- [ ] Generations are minimal and represent real lifetime boundaries.
- [ ] Any future one-surface-per-display architecture preserves the ownership rules above.

# Visualizer gate

- [ ] Exact current approved commit/environment manifest exists.
- [ ] Deterministic logical replay passes all supported modes.
- [ ] Production general-executor temporal capture passes.
- [ ] Source-to-first-visible response is within approved bounds.
- [ ] Known-bad `666624d`, terminal batching, and `ebfec397` controls fail.
- [ ] Spectrum retains approved response, shape, attack/decay, and smoothness.
- [ ] Bubble retains approved elasticity, rebound, impulses, and responsiveness.
- [ ] Sine Waves, Oscilloscope, and Dev Curve retain approved current behaviour.
- [ ] Irregular paint cadence does not alter logical state.
- [ ] Background load does not materially change feel.
- [ ] Settings/Edit/mode switches do not reveal stale/poisoned state.
- [ ] User installed review passes separately for every affected mode.
- [ ] No mode-specific degradation was used to meet CPU/memory goals.

# Lifecycle gate

## Focused current blockers

- [ ] R-56 closes: dialog graph observed while valid; no call on deleted wrapper; one replacement.
- [ ] R-53 closes: temporary Edit session retires and owner frames return before queued engine admission.
- [ ] Both retired `CustomLayoutManager` wrappers and all shells die without `gc.collect()`.
- [ ] R-57 closes: scaled-prefetch selection/removal and accounting remain correct.

## Installed/release lifecycle

- [ ] Focused one-cycle Settings and dual-display Edit installed runs pass.
- [ ] Current Phase 5 alternating lifecycle matrix passes.
- [ ] Release-scale 50 Settings, 50 Edit, and 50 mixed cycles—or an explicitly approved equivalent hostile matrix—passes.
- [ ] No invalid Qt-wrapper or cross-thread/context error.
- [ ] No stale callback/publication/admission applies.
- [ ] No old-generation QObject, Python root, task, timer, animation, subscription, resource, visualizer owner, pixmap, texture, PBO, or GL byte survives.
- [ ] Exactly one replacement runtime is constructed per accepted request.
- [ ] Replacement reveal uses current authoritative state only.
- [ ] Timers/workers/handles/threads return to expected plateau.

# Performance and workload gate

- [ ] Every optimization names a measured owner and removed work.
- [ ] CPU is materially lower in comparable current scenarios.
- [ ] No normal one-core saturation remains without an approved explanation.
- [ ] Task/category/callback/queue work is bounded and justified.
- [ ] No task per paint/bar/bubble/group.
- [ ] No persistent/dedicated visualizer lane.
- [ ] No per-frame INFO logging or diagnostic control flow.
- [ ] p50/p90/p95/p99/max and first-visible response meet targets.
- [ ] No repeated unexplained idle 100+ ms gaps.
- [ ] Average FPS is reported only as context.
- [ ] Lower task count did not alter logical events/cadence/feel.
- [ ] Normal and Media Center results pass.

# RAM, commit, VRAM, and resource gate

## Containment

- [ ] Post-warmup RSS/private commit/VRAM and tracked resources do not grow monotonically across image, transition, and lifecycle cycles.
- [ ] Every retired generation returns application ownership to zero.
- [ ] CPU caches/prefetch queues/future bytes are bounded and internally consistent.
- [ ] GL resource owners/stores are byte-bounded and deterministic.
- [ ] Old image/transition/display/visualizer resources release exactly once.

## Absolute efficiency

For the current dual-1440p target environment:

- [ ] preferred whole-app warm RSS is under 600 MiB, or an explicit approved decision explains a higher value;
- [ ] values above 750 MiB have owner-level investigation;
- [ ] unresolved values above 900 MiB block release;
- [ ] preferred dedicated VRAM is under 300 MiB, or explicitly explained;
- [ ] values above 400 MiB have owner-level investigation;
- [ ] unresolved values above 500 MiB block release;
- [ ] no unexplained multi-GiB private commit remains;
- [ ] main/child resident, private, commit, VMS/mapped, stacks, Qt/native, shared-memory, cache, and driver categories are separated where measurable;
- [ ] tracked/untracked gaps are documented honestly.

## Quality boundary

- [ ] No working-set trimming, allocator trimming, production GC, process recycling, ignored owner, or hidden page-out is used as the fix.
- [ ] No visualizer cadence/source, image/texture resolution, precision, transition, artwork, shadow, widget-content, animation, or first-frame quality reduction is used.

# Product gate

- [ ] Overlays/widgets appear on correct displays and routes.
- [ ] Cursor halo and interaction overlays remain smooth.
- [ ] Image quality/crop/scaling is unchanged unless explicitly approved.
- [ ] Transition behaviour and interruption remain correct.
- [ ] No supported mode/widget is silently disabled.
- [ ] Settings/Edit preserve user settings and graph placement.
- [ ] Background-load behaviour is equal or better than the approved runtime.
- [ ] Resource usage is appropriate for a screensaver, not merely bounded.

# Evidence gate

- [ ] Exact commit/scenario/environment manifests stored.
- [ ] Raw logs and failed runs preserved.
- [ ] Parser/version/commands/source hashes recorded.
- [ ] Sample ages and comparison limitations stated.
- [ ] Phase and benchmark reports complete.
- [ ] Decision records complete for deviations/target changes.
- [ ] Historical bug records updated and active narratives removed from `Current_Plan.md` when closed.
- [ ] User visual approvals/rejections recorded accurately.
- [ ] Rejected experiments retained or summarized with exact revert.
- [ ] Rollback commit identified.
- [ ] No credentials, sensitive titles/URLs, or copyrighted audio retained.

# Critical gates

Critical failure areas:

- visualizer fidelity and one-cadence authority;
- Qt/GL/lifecycle ownership;
- first-frame/reveal correctness;
- p99/max delivery;
- memory containment and absolute footprint;
- correct multi-display/graph behaviour;
- honest evidence.

# Final comparison statement

The release report must compare the candidate against:

- the exact prior/current approved commit for ordinary behaviour;
- `ff934616` for current Bubble/Spectrum feel until superseded by explicit approval;
- `00edb57` and `7376bb9` only where historical context remains relevant;
- known-bad commits/fixtures as negative controls.

It must state remaining weaknesses and uncertainty. A single favorable metric cannot establish release readiness.