# Future Cleanup

Last updated: 2026-08-24

Deferred/deletion ledger. Active sequencing remains in `Current_Plan.md`.

This file records **caller-proven retirement**, not permission to preserve compatibility architecture.
Use `Docs/TestSuite.md` as the canonical test inventory/retirement ledger and
`Docs/Documentation_Maintenance.md` for documentation retirement rules.

## Retirement labels

```text
CURRENT-LEGACY — WILL BE OBSOLETE
    live callers still exist, but destination work must not deepen the owner

OBSOLETE NOW
    no meaningful live contract remains; delete at a safe bounded checkpoint

LANDED / PRESERVE
    survives the migration even if its original implementation/phase name is old
```

## 0. Immediate low-risk cleanup already identified

These items do not define migration sequencing and must not interrupt a higher-priority active slice,
but they are already classified by the TestSuite audit:

- [ ] delete `tests/test_settings_sync.py` — **OBSOLETE NOW**, zero-test QSettings tombstone;
- [ ] delete `tests/test_phase_e_effect_corruption.py` — **OBSOLETE NOW**, historical QWidget
      `QGraphicsEffect` investigation scaffolding rather than meaningful current regression coverage;
- [ ] update the three `UPDATE REQUIRED NOW` tests listed in `Docs/TestSuite.md` when their owning
      implementation/test slice is next touched; do not weaken assertions merely to make them green.
- [ ] repair `tests/test_spotify_visualizer_widget.py::test_on_tick_does_not_double_throttle_when_timer_already_paces`
      when the synthetic Bubble harness is next touched: it omits the now-required `runtime_controller`
      and reproduces on the pre-Media-owner baseline; do not interrupt an E1 ownership checkpoint for it.

If these test files change, update `Docs/TestSuite.md` in the same checkpoint.

## 1. Phase H/I — old production presenter deletion

The following are **CURRENT-LEGACY — WILL BE OBSOLETE at production cutover / Phase I**.

After production owner switches to `QuickDisplayRuntime`, replacement gates are green and callers are
proved absent:

- [ ] remove `DisplayWidget` as runtime physical presenter;
- [ ] remove retired QRhiWidget physical presentation ownership;
- [ ] remove `GLCompositorWidget` scheduling/presentation ownership;
- [ ] remove `ExternalOpenGLRhiWidget` / old borrowed-QRhi-context surface helpers with no caller;
- [ ] remove QRhiWidget-only lifecycle compatibility;
- [ ] remove obsolete GUI `present_tick`/physical-presentation callbacks after caller proof;
- [ ] remove old adaptive/compositor render scheduling that no live non-Quick owner needs;
- [ ] remove compositor-only transition resource helpers after Quick renderer caller proof;
- [ ] remove legacy `GLErrorHandler` capability-demotion architecture
      (`FULL_SHADERS -> COMPOSITOR_ONLY -> SOFTWARE_ONLY`) once no live pre-cutover caller requires it;
- [ ] remove `rendering/backends/software` and backend-selection/demotion plumbing existing solely for
      software/compositor fallback support;
- [ ] retain P0 comparison/raw evidence;
- [ ] retain cheap architecture-neutral timing diagnostics.

Software-only rendering is not a supported SRPSS destination capability. Intentional provider/cache/
network resilience remains feature-owned and is unrelated to presenter fallback deletion.

Each deletion batch:

```text
caller proof
-> replacement-contract test proof
-> focused tests
-> update TestSuite retirement rows
-> commit
-> push
```

## 2. Visualizer legacy deletion — H0/I

The logical/runtime contract is **LANDED / PRESERVE**. Old pixel/presenter machinery is
**CURRENT-LEGACY — WILL BE OBSOLETE**.

After visualizer pixels are fully Quick-owned and relevant old callers are gone:

- [ ] remove `CompositorVisualizerLayer`;
- [ ] remove old compositor card texture owner;
- [ ] retire obsolete `SpotifyBarsGLOverlay` presentation/resource-host plumbing with no caller;
- [ ] remove QWidget visualizer card/presentation code not needed by remaining Settings/model logic;
- [ ] remove QWidget/QRhi reveal/fade ownership replaced by Quick;
- [ ] remove pre-Quick per-mode card-height/growth Settings controls/bindings/preset leaves/
      compatibility helpers (`card_height.py` / old growth-map paths) at the H0/I schema/caller gate;
- [ ] delete/retarget tests whose only purpose is preserving that retired presentation geometry;
- [ ] preserve `VisualizerLogicalRuntime`, BeatEngine/source, presets, BTF, mode algorithms/shaders,
      snapshot bridge and destination Quick render contracts.

Do not confuse a historical class name with the behavior it protected. Rehome surviving lifecycle/
scheduling/fidelity assertions before deleting old presentation tests.

## 3. E3/E4/F/I — runtime widget presentation deletion

Runtime QWidget pixel owners are **CURRENT-LEGACY — WILL BE OBSOLETE / REHOMED** as each family moves.

After the corresponding Quick primitive/family/cutover caller proof:

- [ ] delete old QWidget runtime-pixel class code no longer used by Settings/model tests;
- [ ] delete old QWidget-only widget factory presentation paths;
- [ ] delete `BaseOverlayWidget` after no remaining runtime/settings owner requires it;
- [ ] delete painted runtime-shadow/static-frame cache code after Quick shadow parity and caller proof;
- [ ] delete QWidget runtime `QGraphicsEffect` invalidation/fade/shadow code where no transient Settings
      control UI still owns it;
- [ ] delete old `EditShellWidget` / `EditGridOverlayWidget` when Quick CUSTOM replaces them;
- [ ] retain Python providers/models/settings/business logic that remains canonical.

Do not retain screenshot-to-texture adapters or dual presentation registries "for safety."

## 4. Transition legacy deletion — Phase I

All canonical transitions already have Quick renderers. The old presentation implementation may still
have live pre-cutover callers and is therefore **CURRENT-LEGACY — WILL BE OBSOLETE at I**.

After production cutover/caller proof:

- [ ] remove `gl_compositor_*_transition.py` classes whose only target was `GLCompositorWidget`;
- [ ] retain/move pure transition parameter/easing/direction math still used by Quick;
- [ ] remove old compositor-specific transition watchdog/animation glue;
- [ ] preserve canonical transition registry/settings identity and Quick renderer regressions.

## 5. Phase G/I — CUSTOM/input/auxiliary pixel deletion

After retained Quick edit/input ownership lands and callers are proven absent:

- [ ] remove QWidget edit-shell/grid pixel ownership;
- [ ] remove `DisplayWidget`-specific input assumptions superseded by `RuntimeInputController`;
- [ ] remove old auxiliary top-level/transient runtime pixel owners replaced by the Quick scene;
- [ ] preserve product-owned CUSTOM persistence/math/session semantics;
- [ ] preserve QWidget Settings/control UI where it remains the selected non-runtime owner.

Cross-monitor/CUSTOM retirement must not delete the saved geometry authority it was meant to preserve.

## 6. Native code

There is no deferred "rewrite presenter in C++" task.

If later profiling finds a specific Quick renderer Python bottleneck:

- [ ] document measured cost/owner;
- [ ] compare a local native render node/renderer against current Quick primitive;
- [ ] preserve the same QQuickWindow topology;
- [ ] preserve state/lifecycle/fidelity contracts.

## 7. Logical-runtime cleanup

After migration/correctness work:

- [ ] remove dead GUI visualizer timer helpers;
- [ ] remove comments naming GUI recurring timing as logical owner;
- [ ] audit monotonic-clock semantics;
- [ ] remove stale one-update-per-publication assumptions.

Do **not** delete `VisualizerLogicalRuntime` or its permanent tests merely because some files retain old
P2/Phase-D names.

## 8. Test / harness debt

`Docs/TestSuite.md` is authoritative for exact file status.

General retirement rules:

- [ ] retire tests protecting only removed QRhiWidget/GLCompositor/software-presentation architecture;
- [ ] remove/retarget `tests/test_gl_fallback_policy.py`, software-backend tests and related legacy
      capability-demotion assertions when their old runtime callers are deleted;
- [ ] rehome surviving semantics before deleting old owner-specific tests;
- [ ] retain one-clock, generation-zero, BTF, source-freshness, capability, lifecycle and Quick
      presentation gates;
- [ ] keep P0 evidence historical;
- [ ] maintain production-shaped Quick renderer/widget/lifecycle regression coverage;
- [ ] remove migration-only harnesses with no continuing guard value in Phase J.

Do not preserve an empty tombstone test module as historical documentation.

## 9. Post-migration Media artwork framing

This is **nonblocking post-migration presentation cleanup**, not a reason to alter the active migration
sequence or add a second Media acquisition path.

A 2026-08-24 standalone GSMTC probe against a playing Spotify video observed one static `300x300`
thumbnail across 897 successful reads at 59.78 Hz, with no `MediaPropertiesChanged` events. The useful
finding is geometric: the decoded square thumbnail contained approximately 50 px / 16.67% black
letterboxing at both top and bottom, leaving `300x200` visible content (aspect ratio `1.5`, or `3:2`).
Treating the transport canvas as intrinsic square artwork therefore preserves visible black bars in the
Media artwork slot.

After the Qt Quick Media presentation is landed and migration-critical parity is stable:

- [ ] add conservative Media-artwork letterbox/pillarbox normalization before final destination
      scaling: detect strong symmetric near-uniform black transport bars, crop those bars, then preserve
      the remaining content aspect ratio through the normal Quick artwork fit/fill path;
- [ ] never stretch non-square content merely to fill the artwork slot;
- [ ] keep the source-resolution/decoded artwork identity runtime-side and keep destination size/DPR
      projection presentation-side;
- [ ] avoid false-positive cropping of legitimate dark/square album art; require a bounded confidence
      rule rather than "black edge means crop";
- [ ] add fixture coverage for the observed `300x300 -> 300x200` letterboxed Spotify case, ordinary
      square album art, genuinely dark edge artwork, and pillarboxed content;
- [ ] do not add high-rate GSMTC thumbnail polling for video: this probe observed one unique decoded
      frame over the full 15-second sample, so current evidence does not support a usable video stream.

This cleanup may be generalized beyond Spotify only if other GSMTC providers demonstrate the same
transport-letterboxing behavior. Do not make Spotify-specific presentation architecture unless source
evidence requires it.

## 10. Long-run resources

Repeat long-soak resource work on final Quick architecture.

Keep memory/handle retention separate from the physical-presentation decision unless evidence connects
them.

## 11. Repository / compatibility debris

- [ ] remove generated preview debris after clean-checkout proof;
- [ ] collapse deprecated class-global input authority after Quick input owner lands;
- [ ] add lightweight repository-hygiene checks if they provide continuing value;
- [ ] remove migration-only compatibility aliases after caller proof rather than carrying them as a
      permanent translation layer.

## 12. Documentation hygiene — through J

At each owner/cutover change:

- [ ] `Current_Plan.md` current-next-work section matches actual phase state;
- [ ] `Index.md` / `Docs/Contracts.md` owner map matches landed source;
- [ ] current-legacy owners are labelled **WILL BE OBSOLETE** until removed;
- [ ] `Docs/TestSuite.md` matches test add/delete/rehome/retirement;
- [ ] phase reports/Historical_Bugs remain evidence-scoped;
- [ ] incident status headers are updated when audit/validation state changes;
- [ ] evidence/archive navigation READMEs do not call an old phase current;
- [ ] remove temporary migration decomposition docs only once their durable contracts are absorbed;
- [ ] never create a second live roadmap hierarchy.

## 13. New feature / implementation backlog

New features and deliberately deferred new implementations belong in `Future_Work.md`, not this
cleanup ledger.

`Future_Work.md` must not interrupt active `Current_Plan.md` or important admitted cleanup work unless
the operator explicitly selects one of its items.
