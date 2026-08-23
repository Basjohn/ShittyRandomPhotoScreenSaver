# Widget Creation and Runtime Presentation Guide

Last updated: 2026-08-23

Canonical guide for adding or deeply refactoring a non-visualizer widget during the Qt Quick runtime
presentation migration.

For current sequencing read `Current_Plan.md`. For the detailed E1/E3/E4/F decomposition read
`Docs/QtQuick_Migration/04_Widget_Runtime_Presentation.md`; for the **landed** application capability/
E2 contract read `Docs/QtQuick_Migration/07_Settings_Capability_Activation.md`.

## 1. Split the widget into two concerns

Every runtime widget is understood as:

```text
data / provider / model / settings / interaction logic
                    +
runtime pixel presentation
```

The Qt Quick migration primarily changes runtime pixel presentation.

Do not rewrite provider, persistence, authentication, refresh or business logic into QML merely
because pixels move to Quick.

## 2. Family activation and instance enabled are separate

Canonical application-level family activation and the E2 `SETUP` UI are landed.

Use the distinction consistently:

```text
family activated / deactivated
    = may this capability family resolve runtime ownership at all?

widget instance enabled / disabled
    = ordinary feature configuration inside an activated family
```

Do not use “disabled family” when you mean application-level `deactivated`.

Visualizers is a widget-family activation capability (family `visualizers`, member
`spotify_visualizer`) that requires the `media` family; its runtime/render ownership remains the
special visualizer subsystem rather than an ordinary Phase-F widget family.

At the currently landed foundation, factory-backed widget creation is filtered by family activation
before per-instance enabled handling. **E1 is active** to move model/provider/service ownership under
the presentation-neutral final runtime owner.

A deactivated family must ultimately own no family-exclusive model/provider/process/poll/timer/
presentation resource. Shared infrastructure remains while another activated capability still needs
it.

Do not claim full dormancy for an owner that has not yet migrated merely because concrete widget
creation was skipped.

## 3. Settings remain separate and lazy

Settings/configuration UI may remain QWidget-based.

Opening Settings must not:

- start runtime providers merely to hydrate controls;
- build every widget section;
- recreate live runtime;
- perform network work;
- trigger expensive pixel preparation for widgets the user did not open.

Preserve lazy section construction and canonical SettingsManager/defaults ownership.

Application-level deactivation preserves detailed stored configuration. An unbuilt/deactivated page
must not overwrite persisted values on Save.

The E2 navigation rule is landed and live: deactivation removes the family's normal settings pill
immediately; reactivation restores it immediately; `SETUP` remains available. Detailed page
construction remains lazy and built pages retire on deactivation.

## 4. Runtime presentation destination

Runtime widget pixels that coexist over the screensaver scene ultimately live inside the display's
single `QQuickWindow`.

Preferred shape:

```text
Python provider/model/runtime owner
        ↓ compact presentation state
retained Quick runtime item/layer
        ↓
display scene
```

No separate accelerated native window per widget.

No `QQuickWidget` runtime workaround.

## 5. Current-legacy widget presentation

Existing QWidget runtime widgets may remain temporarily while their Quick presentation equivalent is
built/validated.

Those runtime-pixel owners are **CURRENT-LEGACY — WILL BE OBSOLETE / REHOMED in E3/E4/F/I**. This
includes, where applicable:

- `BaseOverlayWidget` runtime pixel/card ownership;
- QWidget/QPainter card rendering;
- runtime painted-shadow/static-frame caches;
- old QWidget runtime effects/fades;
- old factory presentation products whose only purpose is producing runtime QWidget pixels.

Do not create permanent dual-presentation ownership and do not deepen these owners just because they
still have production callers.

A migration slice has a clear cutover after which only one presentation owner draws that widget.

A legacy descriptor/factory surviving for the old path is migration source/reference, not permission
to keep a parallel Quick-era factory architecture.

## 6. Canonical descriptor/family metadata

Stable identity/settings/family metadata belongs in presentation-neutral descriptor/catalog authority,
not in concrete QWidget factories.

Typical canonical facts include:

```text
widget id
family id
settings section/key
startup stage
monitor/routing keys
CUSTOM participation
base/inheritance keys
service/runtime requirements
```

Family membership comes from `core/settings/widget_family_catalog.py`. Do not create a second family
map in Settings, a widget factory or Quick presentation code.

Internal extensibility may be static/plugin-shaped. Do not turn it into dynamic third-party discovery,
manifests or hot loading without an explicit product decision.

## 7. Widget classification

Classify the visual/runtime shape before choosing its presentation primitive:

1. static/mostly-static information card;
2. service-backed card;
3. interactive control;
4. anchor-dependent item;
5. CUSTOM-editable item;
6. special high-frequency visual element.

Use ordinary retained Quick items for ordinary UI where practical.

Use custom rendering only when fidelity/performance requires it.

## 8. Provider/model contract

Keep canonical Python owners for:

- refresh policy;
- credentials;
- network access;
- caching;
- error/resilience policy;
- normalized state;
- settings persistence;
- semantic actions.

Publish compact presentation state instead of letting render/QML code reach into provider internals.

E1 should remove hidden QWidget construction as a prerequisite for retaining provider/model ownership.

## 9. Runtime update contract

Prefer state-driven invalidation.

Do not:

- rebuild stable pixels every frame;
- add private high-frequency timers when retained state is sufficient;
- perform blocking provider/file/cache work in render synchronization/render callbacks;
- emit one GUI/Quick update per source event when current state can coalesce safely;
- repaint/rebuild a large card for a tiny decoration without measured justification.

Deactivation and ordinary instance disable are different state transitions; route each to its actual
owner rather than broadcasting a full widget subtree rebuild.

## 10. CUSTOM layout

Committed CUSTOM geometry and authored/default geometry remain separate authorities.

The presentation item consumes authoritative geometry rather than inventing a QML-only layout system.

Live content refresh must not overwrite committed outer geometry.

Save and Cancel remain distinct lifecycle actions.

Phase G moves edit/session pixels away from old QWidget edit shells while preserving useful
presentation-neutral persistence/math.

## 11. Input/actions

Keep shared input semantics and business actions in Python routing where practical.

Quick presentation items may own hit regions/pointer handlers, but do not duplicate command, URL,
provider or persistence authority in QML.

## 12. Styling

Preserve the authored SRPSS visual language.

Shared style/chrome constants remain canonical rather than copied into every QML/item implementation.

If migration requires new Quick-side style tokens, bridge from an existing canonical source or define
one presentation-style authority deliberately.

Phase E4 owns the global eight-direction shadow orientation. Direction must not become a second shadow
magnitude authority.

Old QWidget runtime shadow/effect implementations are current-legacy; preserve appearance and rehome
tests rather than preserving their implementation indefinitely.

## 13. Performance

A new/migrated widget must not:

- introduce a second accelerated surface;
- block Quick render synchronization on provider work;
- allocate unbounded textures/images;
- force whole-scene rebuilds for small content changes;
- reduce authored animation/visualizer fidelity merely to hit counters;
- start family-exclusive work while its capability is deactivated.

Measure shared presentation effects/p95/p99/tails where relevant, not just widget-local paint time.

## 14. Lifecycle

Widget presentation/model state is generation-owned.

On recreation/deactivation as applicable:

- old presentation/model publication loses admission;
- delayed/stale provider results cannot publish into replacement state;
- family-exclusive resources retire through the legal owner;
- shared resources survive only while another valid consumer owns them;
- render resources retire legally;
- replacement geometry/state becomes authoritative;
- reveal occurs only when intentional content is ready.

## 15. Deprecated Imgur

Imgur is **CURRENT-LEGACY — WILL BE REMOVED in Phase F0**, not a Quick migration target.

A legacy/dev-gated Imgur descriptor may still exist before F0 cleanup, but new Quick widget work must
not create an Imgur component or repair its provider merely to port it.

Follow `Current_Plan.md` / `Future_Cleanup.md` for removal sequencing.

## 16. Feature-specific plans

Feature plans written before the Quick decision may remain valuable for product/provider/security/data
contracts while containing old runtime-pixel mappings.

In particular, `Docs/SRPSS_Steam_Widget_Family_Implementation_Plan.md` retains valuable Steam
provider/privacy/selection decisions, but its `BaseOverlayWidget`/painter/factory presentation mapping
is **CURRENT-LEGACY — WILL BE REHOMED in E1/F/I**. This guide + the Phase-E/F decomposition override
that old pixel-owner mapping.

## 17. Testing

Test separately and at the owner appropriate to the claim:

- family catalog/activation;
- per-instance enabled behavior;
- model/provider behavior;
- settings/defaults/lazy hydration;
- presentation-state mapping;
- Quick item/render output;
- CUSTOM geometry;
- input/action routing;
- lifecycle/recreation/deactivation;
- multi-display/DPR;
- installed visual parity.

Before deleting an old presenter/widget test, check `Docs/TestSuite.md`: rehome surviving behavior to
the destination owner, then retire tests whose implementation contract is intentionally gone.

Do not call migration complete merely because legacy Python model tests still pass.
