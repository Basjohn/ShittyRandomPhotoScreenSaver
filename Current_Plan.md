# Current Plan — Qt Quick Production Migration

Last updated: 2026-08-30

## Current checkpoint

G is independently audited and accepted. H is CLOSED on pushed `main`, including
the audited bounded correction of two visualizer-routing regressions found in
the first closure.

```text
81b8518b  ordinary-family admission filters each enabled instance through the
          canonical effective monitor route for its logical destination
9dcb02be  caller-proven legacy physical presentation host deleted
bc8fd6af  Quick visualizer admission resolves its monitor through the canonical
          descriptor/effective-route authority (Media outside CUSTOM; the
          visualizer's own route while CUSTOM), not the raw settings monitor
6f88cca9  presentation-neutral CUSTOM failover state + lifecycle re-homed under
          rendering/quick/ (deleted with the legacy host); 39/39 focused GREEN
28e95d64  DisplayManager admission drives the CUSTOM failover/reclaim lifecycle
          (one 30s grace, single temporary fallback, retire-confirmed reclaim);
          no second owner, no legacy host restored
```

Pushed-tree H audit:

- local `main` and `origin/main` are equal;
- production startup/orchestration is Quick-only;
- `DisplayWidget`, QRhiWidget/`GLCompositorWidget`, old widget/CUSTOM/input/
  auxiliary/transition hosts, legacy visualizer presenters and unsupported
  backend/fallback owners are absent from `HEAD`;
- production source contains no import of a deleted physical-host module;
- the maintained `h-destination` profile is **63/63 GREEN** (the routing +
  re-homed CUSTOM failover/capability bars are now part of the H boundary);
- focused neutral visualizer/Media deletion fallout is **31/31 GREEN**;
- no `DisplayWidget` compatibility facade, parallel old/Quick presenter,
  duplicate runtime/service/visualizer owner or product switch-back was added.

H durable topology is now:

```text
selected display
-> DisplayManager semantic orchestration
-> one QuickDisplayUnit
-> one QuickDisplayRuntime
-> one standalone threaded QQuickWindow
-> one retained Quick scene
-> one display-owned WidgetRuntimeManager
-> canonical capability + per-instance monitor admission
-> retained ordinary/CUSTOM/input/context/auxiliary/transition owners
-> zero-or-one admitted visualizer edge per display
-> exactly one product-level visualizer owner across participating displays
```

The full-tree collection diagnostic is intentionally not an H gate. On the H
deletion checkpoint it reached 2,846 tests and reported 58 legacy-owner
collection errors before one old visualizer test aborted collection. Those
obsolete/mixed tests and related tools/comments are admitted I inventory; they
must not cause production compatibility modules to return.

Detailed durable H authority remains in:

- `Docs/QtQuick_Migration/Remaining_H_Production_Cutover_Decomposition.md`;
- `Docs/QtQuick_Migration/H_Pre_Cutover_Visualizer_Edge_Corrections.md`;
- `Docs/TestSuite.md`;
- `Spec.md` and `Docs/Compositor_Architecture.md`.

## Active task — I residue reconciliation

I is the next admitted phase. It was not started by the H cutover or its bounded
routing/failover correction (closed at `28e95d64`). Begin the next execution with
exact current source and this live checklist; do not invent a speculative
migration redesign.

- [ ] Derive the exact post-H residue inventory from imports/callers and the
  complete-tree collection diagnostic.
- [ ] For each old-owner test, preserve or re-home only a contract that still
  falsifies a neutral/Quick product behavior; delete pure physical-presenter
  assertions instead of recreating their owner.
- [ ] Remove caller-dead old-presenter adapters, aliases, tools, logger routes,
  comments and migration spikes that have no destination consumer.
- [ ] Keep canonical settings, provider/backend business logic, BeatEngine/
  authored visualizer algorithms, neutral services/models, Quick transition
  math/shaders and accepted G/H contracts.
- [ ] Restore clean full-tree collection, then run the smallest focused tests
  for each reconciled contract before using bounded broad chunks.
- [ ] Keep `Docs/TestSuite.md`, `Future_Cleanup.md`, `Index.md` and `Spec.md`
  current after material residue slices; commit/push/audit each bounded GREEN
  checkpoint.
- [ ] Close I only when the broad suite is again a meaningful current-owner
  authority and no production/test/tool residue implies a second presenter.

`Docs/TestSuite.md` is the live test-file inventory. `Future_Cleanup.md` owns
unrelated debt. Exact source outranks both when their inventories drift.

## Binding invariants

- One selected physical display owns one standalone `QQuickWindow`, one
  retained scene and one display runtime/service owner chain.
- No `QQuickWidget`, second accelerated surface, hidden QWidget presenter,
  software/QRhi fallback presenter or presentation screenshot facade.
- No duplicate legacy/Quick production presenter, provider/service manager,
  visualizer controller/source/logical runtime/mailbox/render bridge or CUSTOM
  owner.
- Python owns semantic/settings/provider/runtime truth; QML consumes bounded
  presentation state and emits semantic actions.
- Ordinary family admission resolves activation/effectiveness, instance
  `enabled`, and canonical effective `monitor` routing before construction.
- CUSTOM keeps committed geometry separate from temporary working geometry;
  visualizer committed viewport extent remains authoritative outside editing.
- Visualizer authored cadence remains presentation-independent; the display's
  existing Quick frame pacer is the sole GUI synchronization opportunity.
- Old generation admission closes and logical work joins before legal
  scene/window retirement; generation `0` remains valid.
- Fallbacks are fail-loud, product-authorized and destination-owned; old
  presentation code is not a fallback.

## Deferred J acceptance

J owns compiled/installed and physical acceptance, not more presentation
migration. Follow
`Docs/QtQuick_Migration/Remaining_J_Final_Installed_Acceptance_Decomposition.md`.

Retain for J:

- real 1/2/N-display identity/topology, add/remove/off/wake and A->B->A focus/
  Ctrl/hardware-input checks;
- mixed refresh/DPR and physical performance-tail/resource-soak evidence;
- all-five visualizer baseline/wide/tall eyes-on evidence, including Bubble
  shrink/BTF/fidelity;
- ordinary widget, transition, auxiliary/context and startup/reveal eyes-on
  parity;
- compiled/frozen packaging and clean shutdown.

The two real-physical-display cells in `tests/test_qtquick_runtime.py` remain J
evidence. Do not weaken/delete them merely to manufacture an I broad-suite pass.

## Unrelated debt

`Future_Cleanup.md` is authoritative. Do not re-admit unrelated Settings theme,
Reddit helper or retired Presets work into I unless exact current callers make it
part of residue reconciliation.
