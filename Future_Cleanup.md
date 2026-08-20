# Future Cleanup

Last updated: 2026-08-20

Deferred debt only. `Current_Plan.md` owns active migration work.

## 1. Post-Quick-cutover presentation cleanup

After the Qt Quick production presenter passes cutover gates:

- [ ] remove retired QRhiWidget physical presentation ownership;
- [ ] remove old `GLCompositorWidget` scheduling/admission paths with no remaining caller;
- [ ] remove QRhiWidget-only lifecycle compatibility;
- [ ] remove obsolete GUI `present_tick`/presentation callbacks after caller proof;
- [ ] retire benchmark-only control plumbing that no longer has regression value;
- [ ] retain the P0 evidence report and raw evidence as architecture history;
- [ ] keep cheap architecture-neutral timing diagnostics;
- [ ] remove dead context/resource helpers that belonged only to the old presenter.

Do not perform this deletion ahead of migration parity/cutover.

## 2. Visualizer legacy cleanup

After visualizer pixels are fully Quick-owned:

- [ ] retire obsolete `SpotifyBarsGLOverlay` presentation/resource-host plumbing with no caller;
- [ ] remove compositor-only visualizer layer code;
- [ ] remove old card-texture ownership if the Quick implementation supersedes it;
- [ ] remove obsolete QWidget/QRhi reveal/fade plumbing;
- [ ] preserve logical runtime, source ownership, BTF, presets, and authored behaviour.

## 3. Runtime widget migration cleanup

After each runtime widget family cuts over:

- [ ] delete old QWidget runtime-pixel implementation only when no longer used;
- [ ] retain Python provider/model/settings logic where still canonical;
- [ ] remove dual-presentation bridges;
- [ ] remove temporary raster/adaptor layers that were migration-only.

## 4. Native code

There is no deferred "rewrite presenter in C++" task.

If later profiling finds a specific Quick renderer Python bottleneck:

- [ ] document measured ownership/cost;
- [ ] compare local native renderer vs other Quick primitives;
- [ ] preserve the same QQuickWindow topology;
- [ ] preserve state/lifecycle/fidelity contracts.

## 5. Logical-runtime cleanup

After active migration/correctness work:

- [ ] remove dead GUI visualizer timer helpers;
- [ ] remove comments calling GUI recurring timing the normal logical owner;
- [ ] audit monotonic-clock semantics;
- [ ] remove stale one-update-per-publication assumptions.

## 6. Test / harness debt

- [ ] retire tests that protect only the removed QRhiWidget presentation architecture;
- [ ] retain one-clock, generation-zero, BTF, source-freshness, and lifecycle gates;
- [ ] keep the Qt Quick P0 evidence as historical architecture selection;
- [ ] maintain production-shaped Quick presentation regression coverage;
- [ ] fix unrelated known shared-state/order flakes separately.

## 7. Long-run resources

Repeat long-soak resource work on the final Quick architecture.

Keep memory/handle retention separate from the physical-presentation decision unless evidence connects
them.

## 8. Repository / compatibility debris

- [ ] remove generated preview debris after clean-checkout proof;
- [ ] collapse deprecated class-global input authority;
- [ ] retire deprecated Imgur;
- [ ] add lightweight repository-hygiene checks.

## 9. Unrelated/product backlog

Keep unrelated product work here rather than allowing it to interrupt the presentation migration.

## 10. Documentation hygiene

- [ ] `Current_Plan.md` remains active-only;
- [ ] current owner docs match the migration/cutover state;
- [ ] phase reports/Historical_Bugs remain evidence-scoped;
- [ ] delete temporary migration doctrine once fully absorbed;
- [ ] never create a second live roadmap hierarchy.
