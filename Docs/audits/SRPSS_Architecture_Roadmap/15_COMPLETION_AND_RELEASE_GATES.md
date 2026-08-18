# 15 — Completion and Release Gates

Last reconciled: 2026-08-18

A release candidate fails when a critical gate fails even if one average metric improves.
`Current_Plan.md` owns current execution; these are product/architecture exit conditions.

---

## Architecture

- [ ] One accelerated OpenGL QRhi compositor surface per physical display.
- [ ] Visualizer is compositor-owned presentation, not a second surface.
- [ ] One owner per mutable concern/deletion identity.
- [ ] Visualizer logical/source cadence is independent from physical presentation.
- [ ] No paint acknowledgement, pending-until-paint, second visualizer clock or source decimation.
- [ ] Qt-owned QRhi/OpenGL context is borrowed correctly.
- [ ] No silent CPU/QPainter visualizer fallback.
- [ ] No rejected persistent Bubble scheduler/lane reactivated.
- [ ] Compatibility/diagnostic façades are gone or justified by a real current contract.

## Visualizer

- [ ] All five current modes preserve approved authored behaviour.
- [ ] Reaction latency remains low.
- [ ] Authored reactions are not routinely missed.
- [ ] Smoothing is visually continuous when enabled.
- [ ] No mode/preset/generation poisoning.
- [ ] Startup/mode fades have no flash/slam/dead scene.
- [ ] Mode change works from context menu and Settings/recreation.
- [ ] Ordinary pause/resume does not unnecessarily rebuild GL/runtime state.
- [ ] CUSTOM Cancel restores a live visualizer.
- [ ] CUSTOM Save/rebuild restores authoritative geometry.
- [ ] Intentional cross-display edit transfer works.
- [ ] Temporary monitor absence does not permanently migrate configured ownership.

## Presentation / Frame Pacing

- [ ] 60-Hz display is effectively refresh-limited under ordinary load.
- [ ] High-refresh delivery is stable rather than collapsing unpredictably between equivalent windows.
- [ ] Visualizer-only physical presentation does not repeatedly redraw unchanged immutable state.
- [ ] Transition-active presentation remains eligible every display deadline.
- [ ] Request/dispatch age tails do not dominate ordinary interaction.
- [ ] Logical visualizer cadence has no recurring visible 40–90 ms holes under ordinary load.
- [ ] No callback queue/backlog growth.
- [ ] Average FPS is never accepted as a substitute for p95/p99/max and perceived smoothness.

## CPU / Workload / Efficiency

- [ ] Post-migration CPU usage is re-established.
- [ ] Post-migration GPU usage is re-established.
- [ ] Efficiency gains come from removed waste/churn, not cadence/quality reduction.
- [ ] No unnecessary repeated cache/shadow/card/static raster construction.
- [ ] No task-per-paint architecture.
- [ ] IO/COMPUTE queues remain bounded.
- [ ] Runtime-owned provider work retires promptly with its generation.
- [ ] Same-machine utilization is credible for a screensaver workload.

## Lifecycle / Runtime Replacement

- [ ] Settings/Edit replacement retires the old generation before the new one publishes.
- [ ] Destruction barrier remains fail-closed.
- [ ] Slow provider work cannot strand a retiring runtime.
- [ ] No stale old-generation callback/result applies to replacement runtime.
- [ ] Strict GL deletion occurs on legal owner/context.
- [ ] Tracked GL ownership returns to zero on retired runtime/final teardown.
- [ ] No timeout extension/ignore-list used to paper over a live old owner.

## Physical Monitor / P5

- [ ] One topology decision authority.
- [ ] Trailing-edge topology settlement.
- [ ] Immutable accepted topology snapshot.
- [ ] Notify -> Settle -> Snapshot -> Retire -> Barrier -> Rebuild -> Reveal.
- [ ] Both-monitors-off -> long idle -> wake succeeds repeatedly.
- [ ] Simultaneous and staggered wake orders recover.
- [ ] Input/Escape/context menu remain responsive.
- [ ] No Ctrl+Alt+Delete required to break a wake hang.
- [ ] Temporary configured-monitor sleep/non-participation keeps ownership sticky.
- [ ] Genuine settled absence may fallback only under the owned confirmation policy.
- [ ] Recovery does not require synchronous waking-desktop capture.
- [ ] No monitor polling loop.

## Memory / Resources

- [ ] Equivalent-state RAM/private commit plateaus.
- [ ] Dedicated/shared VRAM plateaus.
- [ ] CPU image caches remain bounded.
- [ ] Texture/PBO/card/program ownership remains bounded.
- [ ] No unexplained multi-GiB private-commit growth.
- [ ] No fidelity/cadence reduction used to hit memory/resource targets.

## Logging / Diagnostics

- [ ] Main log remains readable with WARNING/ERROR/CRITICAL visibility.
- [ ] Sidecar routing remains bounded/semantic.
- [ ] No per-frame INFO flood.
- [ ] Diagnostics remain passive and cannot change admission/cadence.
- [ ] GPU timing does not synchronize the workload with routine `glFinish()`.
- [ ] A new diagnostic family exists only when it chooses between concrete unresolved mechanisms.

## Product

- [ ] Correct multi-display routing/geometry/overlays.
- [ ] Cursor/interaction overlays remain smooth.
- [ ] Image/transition fidelity is unchanged unless explicitly approved.
- [ ] Visualizer feels immediate and smooth, not merely numerically active.
- [ ] Screensaver workload is reasonably lightweight on the available same-machine evidence.
- [ ] No “energy saving” refresh/cadence throttle damages presentation or reactivity.

## Final comparison

Compare ordinary current work against the nearest valid accepted checkpoint on the same machine and
configuration. Historical commits are used only for named forensic/negative-control questions.

State remaining weaknesses explicitly. One favorable metric never equals release readiness.
