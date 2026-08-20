# Future Cleanup

Last updated: 2026-08-20

Deferred/deletion ledger. Active sequencing remains in `Current_Plan.md`.

During the Qt Quick migration, sections 1–3 become **immediate post-cutover deletion work** when
their caller-removal gate is reached. They are not permission to keep a second presenter
architecture indefinitely.

Technical decomposition:

- `Docs/QtQuick_Migration/README.md`

## 1. Post-Quick-cutover presentation deletion

After the production owner switches to `QuickDisplayRuntime` and focused/full gates are green:

- [ ] remove retired QRhiWidget physical presentation ownership;
- [ ] remove `GLCompositorWidget` scheduling/presentation ownership;
- [ ] remove `ExternalOpenGLRhiWidget` / old borrowed-QRhi-context surface helpers with no caller;
- [ ] remove QRhiWidget-only lifecycle compatibility;
- [ ] remove obsolete GUI `present_tick`/presentation callbacks after caller proof;
- [ ] remove old adaptive/compositor render scheduling that no live non-Quick owner needs;
- [ ] remove compositor-only transition resource helpers after Quick renderer caller proof;
- [ ] retain P0 comparison/raw evidence;
- [ ] keep cheap architecture-neutral timing diagnostics.

Each deletion batch:

```text
caller proof
-> focused tests
-> commit
-> push
```

## 2. Visualizer legacy deletion

After visualizer pixels are fully Quick-owned:

- [ ] remove `CompositorVisualizerLayer`;
- [ ] remove old compositor card texture owner;
- [ ] retire obsolete `SpotifyBarsGLOverlay` presentation/resource-host plumbing with no caller;
- [ ] remove QWidget visualizer card/presentation code that no remaining settings/model test uses;
- [ ] remove QWidget/QRhi reveal/fade ownership replaced by Quick;
- [ ] preserve logical runtime, BeatEngine/source, presets, BTF, mode algorithms/shaders.

## 3. Runtime widget legacy deletion

After production Quick cutover and each family's caller proof:

- [ ] delete old QWidget runtime-pixel class code no longer used by Settings/model tests;
- [ ] delete old QWidget-only widget factory paths;
- [ ] delete `BaseOverlayWidget` when no remaining runtime/settings owner requires it;
- [ ] delete old painted-shadow cache code after Quick shadow parity and caller proof;
- [ ] delete old effect invalidation code if no transient QWidget control UI still owns it;
- [ ] delete old `EditShellWidget` / `EditGridOverlayWidget` when Quick CUSTOM replaces them;
- [ ] retain Python providers/models/settings logic that remains canonical.

Do not retain screenshot-to-texture adapters or dual presentation registries "for safety."

## 4. Transition legacy deletion

After all active transitions are Quick-rendered:

- [ ] remove `gl_compositor_*_transition.py` classes whose only target was `GLCompositorWidget`;
- [ ] retain/move pure transition parameter/easing/direction math still used by Quick;
- [ ] remove old compositor-specific transition watchdog/animation glue;
- [ ] preserve canonical transition registry/settings identity.

## 5. Native code

There is no deferred "rewrite presenter in C++" task.

If later profiling finds a specific Quick renderer Python bottleneck:

- [ ] document measured cost/owner;
- [ ] compare a local native render node/renderer against current Quick primitive;
- [ ] preserve the same QQuickWindow topology;
- [ ] preserve state/lifecycle/fidelity contracts.

## 6. Logical-runtime cleanup

After migration/correctness work:

- [ ] remove dead GUI visualizer timer helpers;
- [ ] remove comments naming GUI recurring timing as logical owner;
- [ ] audit monotonic-clock semantics;
- [ ] remove stale one-update-per-publication assumptions.

## 7. Test / harness debt

- [ ] retire tests protecting only removed QRhiWidget architecture;
- [ ] retain one-clock, generation-zero, BTF, source-freshness, lifecycle gates;
- [ ] keep P0 evidence historical;
- [ ] maintain production-shaped Quick renderer/widget/lifecycle regression coverage;
- [ ] remove migration-only harnesses with no continuing guard value.

## 8. Long-run resources

Repeat long-soak resource work on final Quick architecture.

Keep memory/handle retention separate from physical-presentation decision unless evidence connects
them.

## 9. Repository / compatibility debris

- [ ] remove generated preview debris after clean-checkout proof;
- [ ] collapse deprecated class-global input authority after Quick input owner lands;
- [ ] retire deprecated Imgur only through an explicit product decision;
- [ ] add lightweight repository-hygiene checks.

## 10. Unrelated/product backlog

Keep unrelated feature/product work here rather than interrupting the presentation migration.

## 11. Documentation hygiene

- [ ] `Current_Plan.md` active-only;
- [ ] current owner docs match landed Quick class/file names;
- [ ] phase reports/Historical_Bugs remain evidence-scoped;
- [ ] remove temporary migration decomposition docs once fully absorbed;
- [ ] never create a second live roadmap hierarchy.
